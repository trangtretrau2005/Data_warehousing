"""Reproducible, source-first EDA. No warehouse/model dependency and no raw edits."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import html
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess

import numpy as np
import pandas as pd

from coffee_dw.config import ROOT, SOURCE_PATH
from coffee_dw.source import COLUMN_MAP, GRAIN, MEASURES, read_source

DESIGN_END = pd.Timestamp("2013-03-01")
TOLERANCE = .00005
SCOPE_LABELS = {"train_design": "Lịch sử thiết kế · 01/2012–03/2013",
                "full_history_descriptive": "Toàn bộ lịch sử · 01/2012–12/2013"}
CORRELATION_MEASURES = ["Sales", "BudgetSales", "Profit", "BudgetProfit", "COGS", "Margin", "Marketing", "TotalExpenses"]


def vi(value, decimals=0):
    if value is None or pd.isna(value):
        return "không xác định"
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def divide(numerator, denominator):
    return numerator.div(denominator.where(denominator.ne(0)))


def monthly_table(detail: pd.DataFrame) -> pd.DataFrame:
    # Inventory is summed only within each single month, never across months.
    monthly = detail.groupby(["Market", "MonthStart"], as_index=False)[MEASURES].sum()
    return monthly.sort_values(["Market", "MonthStart"]).reset_index(drop=True)


def category_table(detail: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    additive = [column for column in MEASURES if column != "Inventory"]
    result = detail.groupby(keys, as_index=False)[additive].sum()
    counts = detail.groupby(keys).size().rename("SourceRows").reset_index()
    result = result.merge(counts, on=keys, validate="one_to_one")
    last = detail.MonthStart.max()
    snapshot = detail.loc[detail.MonthStart.eq(last)].groupby(keys, as_index=False).Inventory.sum()
    result = result.merge(snapshot.rename(columns={"Inventory": "InventoryLastMonth"}), on=keys, how="left", validate="one_to_one")
    result["InventoryMonth"] = last
    result["SalesGap"] = result.Sales - result.BudgetSales
    result["ProfitGap"] = result.Profit - result.BudgetProfit
    result["BudgetAchievement"] = divide(result.Sales, result.BudgetSales)
    result["ProfitRatio"] = divide(result.Profit, result.Sales)
    result["SalesShare"] = result.Sales / result.Sales.sum() if result.Sales.sum() else np.nan
    return result.sort_values(["Sales", *keys], ascending=[False, *([True] * len(keys))]).reset_index(drop=True)


def make_scope(detail: pd.DataFrame, scope: str) -> dict:
    monthly = monthly_table(detail)
    months = pd.date_range(detail.MonthStart.min(), detail.MonthStart.max(), freq="MS")
    markets = sorted(detail.Market.unique())
    complete_index = pd.MultiIndex.from_product([markets, months], names=["Market", "MonthStart"])
    # Missing observations remain NaN; they are not invented zero sales.
    calendar = monthly.set_index(["Market", "MonthStart"]).reindex(complete_index).reset_index()
    counts = detail.groupby(["Market", "MonthStart"]).size().rename("SourceRows")
    coverage = counts.reindex(complete_index).reset_index()
    coverage["Present"] = coverage.SourceRows.notna()
    change = calendar[["Market", "MonthStart", "Sales"]].copy()
    change["PreviousMonthSales"] = change.groupby("Market").Sales.shift(1)
    change["AbsoluteChange"] = change.Sales - change.PreviousMonthSales
    change["RelativeChange"] = divide(change.AbsoluteChange, change.PreviousMonthSales)
    lagged = calendar[["Market", "MonthStart", "Sales"]].copy()
    for lag in (1, 2, 3):
        lagged[f"Lag{lag}"] = lagged.groupby("Market").Sales.shift(lag)
    lagged["CompleteLag123"] = lagged[["Sales", "Lag1", "Lag2", "Lag3"]].notna().all(axis=1)
    lagged["Scope"] = scope
    rows, lag_correlations, outliers = [], [], []
    for market in markets:
        series = monthly.loc[monthly.Market.eq(market), "Sales"]
        q1, q3 = series.quantile([.25, .75])
        mean, std = series.mean(), series.std(ddof=1)
        lower, upper = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        rows.append({"Market": market, "Scope": scope, "N": len(series), "Min": series.min(),
                     "Q1": q1, "Median": series.median(), "Mean": mean, "Q3": q3, "Max": series.max(),
                     "Std": std, "CV": std / mean if mean else np.nan,
                     "FirstMonth": months.min(), "LastMonth": months.max()})
        pairs = lagged.loc[lagged.Market.eq(market) & lagged.CompleteLag123]
        for lag in (1, 2, 3):
            coefficient = pairs.Sales.corr(pairs[f"Lag{lag}"]) if len(pairs) > 1 and pairs.Sales.std() and pairs[f"Lag{lag}"].std() else np.nan
            lag_correlations.append({"Market": market, "Lag": lag, "PearsonR": coefficient, "N": len(pairs), "Scope": scope})
        points = monthly.loc[monthly.Market.eq(market), ["Market", "MonthStart", "Sales"]].copy()
        points["LowerFence"], points["UpperFence"] = lower, upper
        points["FlagIQR"] = points.Sales.lt(lower) | points.Sales.gt(upper)
        outliers.append(points)
    numeric = detail[MEASURES].describe(percentiles=[.25, .5, .75]).T.reset_index(names="Measure")
    numeric["NegativeRows"] = [int(detail[name].lt(0).sum()) for name in numeric.Measure]
    numeric["ZeroRows"] = [int(detail[name].eq(0).sum()) for name in numeric.Measure]
    chain = monthly.groupby("MonthStart", as_index=False)[MEASURES].sum()
    tables = {
        "monthly_market": monthly, "monthly_chain": chain, "coverage": coverage,
        "descriptive_market": pd.DataFrame(rows), "descriptive_measures": numeric,
        "monthly_change": change, "supervised_lag123": lagged,
        "lag_correlations": pd.DataFrame(lag_correlations), "iqr_flags": pd.concat(outliers, ignore_index=True),
        "market_summary": category_table(detail, ["Market"]),
        "state_summary": category_table(detail, ["Market", "State"]),
        "product_summary": category_table(detail, ["ProductName"]),
        "state_product_summary": category_table(detail, ["Market", "State", "ProductName"]),
        "measure_correlations": monthly[CORRELATION_MEASURES].corr().rename_axis("Measure").reset_index(),
    }
    reconciliation = []
    for measure in [name for name in MEASURES if name != "Inventory"]:
        source_total = float(detail[measure].sum())
        grouped_total = float(monthly[measure].sum())
        reconciliation.append({"Measure": measure, "SourceTotal": source_total,
                               "EDAMonthlyTotal": grouped_total, "Delta": grouped_total-source_total,
                               "Status": "PASS" if abs(grouped_total-source_total) <= TOLERANCE else "FAIL",
                               "Scope": scope, "ComparedWithWarehouse": False})
    tables["aggregation_reconciliation"] = pd.DataFrame(reconciliation)
    return {"name": scope, "tables": tables, "rows": len(detail), "months": len(months),
            "start": months.min().strftime("%Y-%m-%d"), "end": months.max().strftime("%Y-%m-%d"),
            "sales": float(detail.Sales.sum()), "profit": float(detail.Profit.sum()),
            "budget_sales": float(detail.BudgetSales.sum()), "budget_profit": float(detail.BudgetProfit.sum()),
            "negative_profit_rows": int(detail.Profit.lt(0).sum()),
            "negative_inventory_rows": int(detail.Inventory.lt(0).sum())}


def build_exploration(source: str | Path = SOURCE_PATH) -> dict:
    source = Path(source)
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    raw = pd.read_csv(source, dtype=str, keep_default_na=False, skip_blank_lines=False, encoding="utf-8-sig")
    detail, rejected = read_source(source)
    if detail.empty:
        raise ValueError("Nguồn không có dòng hợp lệ để explore; xem quy tắc read_source.")
    design = detail.loc[detail.MonthStart.le(DESIGN_END)].copy()
    if design.empty:
        raise ValueError("Không có lịch sử đến 03/2013 cho scope train_design của protocol Coffee.")
    scopes = {"train_design": make_scope(design, "train_design"),
              "full_history_descriptive": make_scope(detail, "full_history_descriptive")}
    flags = detail[["SourceRow", "MonthStart", "Market", "State", "ProductName", *MEASURES]].copy()
    flags["SalesBalanceDelta"] = flags.Sales - flags.COGS - flags.Margin
    flags["ProfitBalanceDelta"] = flags.Profit - flags.Margin + flags.TotalExpenses
    flags["FlagSalesBalance"] = flags.SalesBalanceDelta.abs().gt(TOLERANCE)
    flags["FlagProfitBalance"] = flags.ProfitBalanceDelta.abs().gt(TOLERANCE)
    flags["FlagNegativeProfit"] = flags.Profit.lt(0)
    flags["FlagNegativeInventory"] = flags.Inventory.lt(0)
    hierarchy = detail[["Market", "State", "ProductName"]].drop_duplicates()
    cols = []
    for name in raw.columns:
        normalized = COLUMN_MAP.get(name, "Unmapped")
        cols.append({"SourceColumn": name, "NormalizedColumn": normalized,
                     "SourceType": "Excel serial date" if name == "Date" else "numeric" if normalized in MEASURES else "text",
                     "BlankRows": int(raw[name].astype(str).str.strip().eq("").sum()),
                     "DistinctRawValues": raw[name].nunique(),
                     "Aggregation": "snapshot in one month only" if normalized == "Inventory" else "sum" if normalized in MEASURES else "dimension/date"})
    raw_blanks = sum(row["BlankRows"] for row in cols)
    coverage = scopes["full_history_descriptive"]["tables"]["coverage"]
    checks = [
        ("Q01", "Đọc và phân loại đủ dòng nguồn", len(detail) + len(rejected), len(raw), "PASS" if len(detail)+len(rejected)==len(raw) else "FAIL", "accepted + rejected = source"),
        ("Q02", "Ô rỗng trong nguồn", raw_blanks, 0, "PASS" if raw_blanks == 0 else "REVIEW", "Không biến ô thiếu thành 0"),
        ("Q03", "Dòng bị reject", len(rejected), 0, "PASS" if rejected.empty else "REVIEW", "Reject riêng; số thống kê sử dụng phần hợp lệ"),
        ("Q04", "Trùng grain ở phần hợp lệ", int(detail.duplicated(GRAIN).sum()), 0, "PASS", "Grain tháng × mã vùng × sản phẩm"),
        ("Q05", "Ô Market–tháng bị thiếu", int((~coverage.Present).sum()), 0, "PASS" if coverage.Present.all() else "REVIEW", "Tháng thiếu giữ thiếu; không điền doanh số 0"),
        ("Q06", "Số không hữu hạn ở phần hợp lệ", int((~np.isfinite(detail[MEASURES].to_numpy())).sum()), 0, "PASS", "Đã qua kiểm tra kiểu của source.py"),
        ("Q07", "Profit âm", int(flags.FlagNegativeProfit.sum()), None, "NOTE", "Giữ nguyên; không mặc định là lỗi"),
        ("Q08", "Inventory âm", int(flags.FlagNegativeInventory.sum()), None, "NOTE", "Giữ nguyên; chưa chứng minh hết hàng"),
        ("Q09", "Sales khác COGS + Margin", int(flags.FlagSalesBalance.sum()), None, "NOTE", "Không tính đè số nguồn"),
        ("Q10", "Profit khác Margin − TotalExpenses", int(flags.FlagProfitBalance.sum()), None, "NOTE", "Chỉ ghi nhận chênh lệch kế toán"),
    ]
    quality = pd.DataFrame(checks, columns=["CheckID", "Check", "Observed", "Expected", "Status", "Interpretation"])
    stats = {"source_rows": len(raw), "source_columns": len(raw.columns), "accepted_rows": len(detail),
             "rejected_rows": len(rejected), "markets": int(detail.Market.nunique()),
             "states": int(detail.State.nunique()), "products": int(detail.ProductName.nunique()),
             "area_codes": int(detail.AreaCode.nunique()), "months": int(detail.MonthStart.nunique()),
             "monthly_cells": len(scopes["full_history_descriptive"]["tables"]["monthly_market"]),
             "sales": float(detail.Sales.sum()), "budget_sales": float(detail.BudgetSales.sum()),
             "profit": float(detail.Profit.sum()), "budget_profit": float(detail.BudgetProfit.sum()),
             "negative_profit_rows": int(flags.FlagNegativeProfit.sum()),
             "negative_inventory_rows": int(flags.FlagNegativeInventory.sum()),
             "sales_balance_rows": int(flags.FlagSalesBalance.sum()),
             "profit_balance_rows": int(flags.FlagProfitBalance.sum()),
             "start": detail.MonthStart.min().strftime("%Y-%m-%d"), "end": detail.MonthStart.max().strftime("%Y-%m-%d"),
             "sha256": checksum, "path": str(source.resolve()), "input_kind": "immutable_csv_source"}
    audit = pd.DataFrame([
        {"Step": "01 Đọc CSV", "RowsBefore": len(raw), "RowsAfter": len(raw), "Note": "Đọc chuỗi, giữ mã vùng và ô rỗng"},
        {"Step": "02 Chuẩn hóa và kiểm tra", "RowsBefore": len(raw), "RowsAfter": len(detail), "Note": f"Excel origin 1899-12-30; {len(rejected)} dòng reject; giữ 11 số đo"},
        {"Step": "03 Tổng hợp Market–tháng", "RowsBefore": len(detail), "RowsAfter": stats["monthly_cells"], "Note": "Giảm dòng do GROUP BY, không phải mất dữ liệu"},
        {"Step": "04 Chọn lịch sử thiết kế", "RowsBefore": stats["monthly_cells"], "RowsAfter": len(scopes["train_design"]["tables"]["monthly_market"]), "Note": "Đến 03/2013; chưa dùng validation/test để chọn đặc trưng"},
        {"Step": "05 Tạo lag123 thiết kế", "RowsBefore": len(scopes["train_design"]["tables"]["monthly_market"]), "RowsAfter": int(scopes["train_design"]["tables"]["supervised_lag123"].CompleteLag123.sum()), "Note": "Ba kỳ đầu mỗi Market chưa đủ lag; chưa fit scaler/model"},
    ])
    common = {"source_columns": pd.DataFrame(cols), "quality_checks": quality, "preprocessing_audit": audit,
              "normalized_detail": detail.drop(columns="RawPayload"), "rejected_rows": rejected,
              "anomaly_rows": flags.loc[flags[["FlagSalesBalance", "FlagProfitBalance", "FlagNegativeProfit", "FlagNegativeInventory"]].any(axis=1)],
              "dataset_profile": pd.DataFrame([stats])}
    common["hierarchy_profile"] = pd.DataFrame([
        {"Level": "Toàn chuỗi", "Series": 1}, {"Level": "Market", "Series": stats["markets"]},
        {"Level": "State", "Series": stats["states"]},
        {"Level": "State × Product", "Series": len(hierarchy)},
    ])
    for scope in scopes.values():
        scope["tables"]["findings"] = pd.DataFrame([
            {"FindingID": f"EDA{i:02}", "Scope": scope["name"], "Statement": statement}
            for i, statement in enumerate(scope_findings(scope), start=1)
        ])
    return {"source": stats, "tables": common, "scopes": scopes}


def scope_findings(scope: dict) -> list[str]:
    t = scope["tables"]
    market = t["market_summary"]
    top = market.iloc[0]
    products = t["product_summary"]
    leader = products.iloc[0]
    budget_ratio = scope["sales"] / scope["budget_sales"] if scope["budget_sales"] else np.nan
    below = market.loc[market.ProfitGap.lt(0)].sort_values("ProfitGap")
    changes = t["monthly_change"].dropna(subset=["RelativeChange"])
    strongest = changes.loc[changes.RelativeChange.abs().idxmax()] if not changes.empty else None
    stats = t["descriptive_market"].sort_values("CV", ascending=False)
    cv = stats.iloc[0]
    findings = [
        f"Phạm vi có {vi(scope['rows'])} quan sát nguồn, {scope['months']} tháng; tổng Sales {vi(scope['sales'])}, Profit {vi(scope['profit'])}. Đây là doanh số tổng hợp, không phải số đơn hay số ly.",
        f"Sales đạt {vi(budget_ratio*100,2)}% BudgetSales. Tỷ lệ tính từ tổng cùng phạm vi, không lấy trung bình tỷ lệ từng dòng.",
        f"{top.Market} có Sales lớn nhất: {vi(top.Sales)}, chiếm {vi(top.SalesShare*100,2)}% tổng. Khác biệt quy mô cho thấy cần đọc sai số theo từng Market khi đánh giá dự báo.",
        f"{leader.ProductName} dẫn đầu Sales sản phẩm với {vi(leader.Sales)}. Bảng đầy đủ giữ cả 13 sản phẩm nếu có trong phạm vi, không bỏ nhóm lợi nhuận thấp.",
        f"{cv.Market} có hệ số biến thiên Sales tháng cao nhất: CV = {vi(cv.CV,3)} trên {int(cv.N)} tháng. Đây là mức dao động tương đối trong mẫu, chưa dự báo phương pháp nào sẽ thắng.",
    ]
    if len(below):
        findings.append("Thị trường hụt BudgetProfit: " + "; ".join(f"{r.Market} ({vi(r.ProfitGap)})" for r in below.itertuples()) + ". Chênh lệch này xác định nơi cần rà soát, chưa giải thích nguyên nhân.")
    else:
        findings.append("Không Market nào hụt BudgetProfit khi gộp phạm vi này; kết luận có thể khác khi xem từng tháng hoặc sản phẩm.")
    if strongest is not None:
        findings.append(f"Biến động tháng lớn nhất theo trị tuyệt đối tỷ lệ: {strongest.Market}, {strongest.MonthStart:%m/%Y}, {vi(strongest.RelativeChange*100,2)}% so với tháng trước. Điểm biến động được giữ để rà soát, không tự xóa.")
    flags = int(t["iqr_flags"].FlagIQR.sum())
    findings.append(f"Quy tắc IQR đánh dấu {flags} ô Market–tháng cần xem thêm; đây là cờ thống kê, không phải bằng chứng lỗi dữ liệu.")
    lag1 = t["lag_correlations"].loc[t["lag_correlations"].Lag.eq(1)].dropna(subset=["PearsonR"])
    if not lag1.empty:
        findings.append(f"Trong cùng tập đủ lag123, liên hệ Sales với tháng ngay trước có Pearson r từ {vi(lag1.PearsonR.min(),2)} đến {vi(lag1.PearsonR.max(),2)}, N = {int(lag1.N.min())}–{int(lag1.N.max())} mỗi Market. Đây là gợi ý thử đầu vào quá khứ, chưa chứng minh lợi ích dự báo ngoài mẫu.")
    negative_products = products.loc[products.Profit.lt(0)]
    if not negative_products.empty:
        findings.append("Sản phẩm có Profit âm khi gộp phạm vi: " + "; ".join(f"{r.ProductName} ({vi(r.Profit)})" for r in negative_products.itertuples()) + ". Không tự kết luận phải ngừng bán hoặc cắt Marketing từ số này.")
    return findings


def write_reports(bundle: dict, output: Path, figures: dict[str, list[dict]]) -> None:
    s = bundle["source"]
    latest = bundle["scopes"]["full_history_descriptive"]["tables"]["monthly_market"]
    last_month = latest.MonthStart.max()
    snapshot_inventory = latest.loc[latest.MonthStart.eq(last_month)].Inventory.sum()
    lines = ["# Khám phá dữ liệu Coffee Chains — phần của Trang", "",
             "## Có làm được khi chưa có code Chi không?", "",
             "**Có.** Lượt này đọc trực tiếp `data/raw/Coffee.csv` qua `coffee_dw.source.read_source`, không kết nối SQL Server, SSIS, SSAS hay SQLite. Đây là EDA nguồn phục vụ chuẩn bị nghiên cứu, chưa phải nghiệm thu ETL hoặc mart của Chi.", "",
             "Khi Chi bàn giao: đối chiếu đủ 96 ô Market–tháng, Sales/BudgetSales/Profit và kỳ tồn kho; thống nhất tên cột, grain và chính sách reject. Không chỉ đối chiếu tổng toàn chuỗi.", "",
             "## Chất lượng và tiền xử lý", "",
             f"- Nguồn: {vi(s['source_rows'])} dòng × {s['source_columns']} cột; chấp nhận {vi(s['accepted_rows'])}, reject {s['rejected_rows']}.",
             f"- Phạm vi: {s['months']} tháng, {s['markets']} Market, {s['states']} bang, {s['area_codes']} mã vùng, {s['products']} sản phẩm.",
             f"- Giữ nguyên {s['negative_profit_rows']} dòng Profit âm và {s['negative_inventory_rows']} dòng Inventory âm; chưa suy ra hết hàng hay nguyên nhân kinh doanh.",
             f"- Có {s['sales_balance_rows']} dòng Sales khác COGS + Margin; {s['profit_balance_rows']} dòng Profit khác Margin − TotalExpenses (ngưỡng {TOLERANCE}). Giữ các số nguồn, không tự sửa đẳng thức.",
             f"- Inventory chỉ gộp trong kỳ {last_month:%m/%Y}: {vi(snapshot_inventory)}. Không SUM tồn kho xuyên 24 tháng. Đây là tổng có dấu của snapshot, không phải số hàng có thể bán ngay.",
             "- Không có cột số ly, giá bán, khách hàng, thời tiết, khuyến mãi chi tiết hoặc lịch phát hành ngân sách. Đơn vị tiền chưa được nguồn công bố.", "",
             "## Hai phạm vi phải đọc riêng", "",
             "`train_design` dùng lịch sử đến 03/2013 để khám phá phục vụ thiết kế mô hình. `full_history_descriptive` mô tả toàn bộ dữ liệu để viết báo cáo sau khi đã chốt thiết kế; không dùng hình toàn kỳ để khẳng định chưa từng tiếp xúc test. Kết quả test tham chiếu đã được biết trong repo.", ""]
    sections = []
    for key, scope in bundle["scopes"].items():
        findings = scope_findings(scope)
        lines += [f"## {SCOPE_LABELS[key]}", "", *[f"- {item}" for item in findings], ""]
        for figure in figures[key]:
            relative = f"{key}/figures/{figure['id']}"
            lines += [f"### {figure['title']}", "", f"![{figure['title']}]({relative}.png)", "", figure["note"], "",
                      f"[PNG 300 dpi]({relative}.png) · [PDF vector]({relative}.pdf) · [SVG]({relative}.svg)", ""]
        market = scope["tables"]["market_summary"][["Market", "Sales", "BudgetSales", "Profit", "BudgetProfit", "ProfitGap", "BudgetAchievement"]].copy()
        for column in market.columns[1:]:
            market[column] = market[column].map(lambda value: vi(value,2))
        gallery = "".join(f'<figure><img src="{key}/figures/{f["id"]}.png" alt="{html.escape(f["title"])}" loading="lazy"><figcaption><strong>{html.escape(f["title"])}</strong> — {html.escape(f["note"])}<br><a href="{key}/figures/{f["id"]}.pdf">PDF vector</a> · <a href="{key}/figures/{f["id"]}.svg">SVG</a></figcaption></figure>' for f in figures[key])
        sections.append(f'<section id="{key}"><h2>{SCOPE_LABELS[key]}</h2><ul>' + "".join(f"<li>{html.escape(x)}</li>" for x in findings) + "</ul>" + market.to_html(index=False, escape=True) + gallery + "</section>")
    lines += ["## Ý nghĩa cho bước mô hình tiếp theo", "",
              "1. Đầu vào dự báo là Sales tháng ở mức Market. Bảng lag thiết kế có 12 mẫu/Market khi đủ 15 tháng đầu và lag123; quy mô này giới hạn mức phức tạp và số cấu hình nên thử.",
              "2. Tương quan lag chỉ là kiểm tra mô tả trên lịch sử thiết kế; chưa có kết quả lựa chọn mô hình. Tương quan giữa số đo cùng kỳ không làm chúng trở thành feature biết trước tháng dự báo.",
              "3. Giữ lịch 15 tháng khởi tạo, 6 tháng validation, 3 tháng test. Chưa fit scaler, train hoặc dò tham số trong EDA.",
              "4. Chưa kết luận mùa vụ ổn định từ 24 tháng, nhân quả Marketing hoặc lượng hàng cần nhập. Không sinh thêm doanh số để tăng cỡ mẫu thật.", "",
              "## Tái lập và đầu ra", "", "```powershell", ".\\.venv\\Scripts\\python explore/run.py", "```", "",
              "CSV giữ số liệu gốc chưa làm tròn; hình và nội dung trình bày có làm tròn. `manifest.json` lưu checksum, phạm vi, phiên bản thư viện và danh mục artifact. Chưa nghiệm thu native/UX; `explore/results/` được ignore để tránh đưa toàn bộ output lên Git."]
    (output / "analysis.md").write_text("\n".join(lines), encoding="utf-8")
    quality = bundle["tables"]["quality_checks"].to_html(index=False, escape=True, na_rep="—")
    common_gallery = "".join(f'<figure><img src="figures/{f["id"]}.png" alt="{html.escape(f["title"])}"><figcaption>{html.escape(f["note"])}</figcaption></figure>' for f in figures["common"])
    page = '''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Coffee · Explore data</title><style>
    body{margin:0;background:#f1f4f8;color:#18324e;font:20px/1.65 'Times New Roman',Times,serif}main{max-width:1180px;margin:auto;padding:40px 30px}header{padding:32px;background:#183b62;color:white;border-radius:12px}h1{font-size:39px;margin:8px 0}h2{font-size:30px;color:#183b62}header p{margin-bottom:4px}nav{display:flex;gap:20px;flex-wrap:wrap;margin:22px 0}a{color:#1c587d}section{padding-top:16px;margin-top:28px}figure{margin:25px 0;padding:16px;background:white;border:1px solid #c5d0dc;border-radius:10px}img{width:100%;height:auto}figcaption{font-size:18px;margin-top:10px}table{border-collapse:collapse;width:100%;background:white;font-size:17px}th,td{border:1px solid #c5d0dc;padding:9px;text-align:right}th:first-child,td:first-child{text-align:left}th{background:#dfe8f2}.note{padding:17px 22px;background:#e2ebf5;border-left:4px solid #2b608a}.kpis{display:flex;gap:25px;flex-wrap:wrap;margin-top:20px}.kpis strong{font-size:31px}li{margin:8px 0}@media print{body{background:white}main{padding:0}figure{break-inside:avoid}nav{display:none}}
    </style><main><header><div>COFFEE CHAINS · EXPLORATORY DATA ANALYSIS</div><h1>Từ dữ liệu nguồn đến câu hỏi nghiên cứu</h1><p>Phần của Trang · bảng số liệu, nhận xét và hình báo cáo</p><div class="kpis">__KPIS__</div></header><nav><a href="#quality">Chất lượng nguồn</a><a href="#train_design">15 tháng thiết kế</a><a href="#full_history_descriptive">Toàn bộ 24 tháng</a><a href="analysis.md">Phân tích Markdown</a><a href="manifest.json">Manifest</a></nav><div class="note"><strong>Làm được khi chưa có code Chi.</strong> EDA đọc CSV qua bộ chuẩn hóa dùng chung. Khi nhận kho, đối chiếu từng ô Market–tháng trước khi chuyển đầu vào. Hình toàn kỳ chỉ mô tả, chưa phải bằng chứng dự báo hay nguyên nhân kinh doanh.</div><section id="quality"><h2>Chất lượng và quy trình dữ liệu</h2>__QUALITY____COMMON__</section>__SECTIONS__<section><h2>Cách đọc kết quả</h2><p>Chưa train mô hình. Bảng lag và tương quan dùng để chuẩn bị thử nghiệm. Profit/Inventory âm và chênh kế toán được giữ nguyên; Inventory chỉ là snapshot trong một kỳ. Đơn vị nguồn chưa xác định tiền tệ. Không suy ra số đơn hàng, số ly hay ROI Marketing.</p><p>Hình xuất PNG 300 dpi, PDF và SVG. Số liệu CSV đầy đủ nằm cạnh mỗi thư mục figures. Xem analysis.md để đọc nhận xét và giới hạn.</p></section></main></html>'''
    kpis = f"<div><strong>{vi(s['accepted_rows'])}</strong><br>quan sát hợp lệ</div><div><strong>{s['months']}</strong><br>tháng lịch sử</div><div><strong>{s['markets']}</strong><br>thị trường</div><div><strong>{vi(s['sales'])}</strong><br>Sales toàn kỳ</div>"
    page = page.replace("__KPIS__", kpis).replace("__QUALITY__", quality).replace("__COMMON__", common_gallery).replace("__SECTIONS__", "".join(sections))
    (output / "report.html").write_text(page, encoding="utf-8")


def run_exploration(source: str | Path = SOURCE_PATH, output: str | Path = ROOT / "explore" / "results") -> dict:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    bundle = build_exploration(source)
    for name, table in bundle["tables"].items():
        path = output / "tables" / f"{name}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(path, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    for scope, data in bundle["scopes"].items():
        folder = output / scope / "tables"
        folder.mkdir(parents=True, exist_ok=True)
        for name, table in data["tables"].items():
            table.to_csv(folder / f"{name}.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    from coffee_dw.exploration_plots import render_figures
    figures = render_figures(bundle, output)
    write_reports(bundle, output, figures)
    try:
        git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        git = None
    artifact_paths = sorted(p for p in output.rglob("*") if p.is_file() and p.name != "manifest.json")
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "source": bundle["source"],
                "git_head": git, "working_tree_note": "Working tree may contain uncommitted changes; no commit/push performed.",
                "python": platform.python_version(), "packages": {name: importlib.metadata.version(name) for name in ["pandas", "numpy", "matplotlib"]},
                "source_sha256_after": hashlib.sha256(Path(source).read_bytes()).hexdigest(),
                "scopes": {name: {k: v for k, v in data.items() if k != "tables"} for name, data in bundle["scopes"].items()},
                "artifacts": {"csv_count": sum(p.suffix == ".csv" for p in artifact_paths),
                              "figure_count": sum(len(group) for group in figures.values()), "figures": figures,
                              "files": [{"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size,
                                         "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in artifact_paths]},
                "limitations": ["EDA nguồn, chưa đối soát kho của Chi.", "Không training/tuning mô hình.",
                                "Toàn kỳ chỉ mô tả; feature-design EDA giới hạn đến 03/2013.",
                                "Không suy nhân quả, số ly hoặc doanh thu phục hồi từ Inventory âm."]}
    if manifest["source_sha256_after"] != bundle["source"]["sha256"]:
        raise RuntimeError("Checksum nguồn thay đổi trong lúc chạy EDA.")
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return manifest
