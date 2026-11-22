"""Prepare a bounded, reproducible narrated-forecast demo from the real warehouse."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path

import pandas as pd

from coffee_dw.config import DB_PATH, RESULTS_DIR, SOURCE_PATH
from coffee_dw.explain import explain_history
from coffee_dw.forecast import METHODS, MODEL_VERSION, evaluate_monthly, monthly_sales
from coffee_dw.warehouse import read_detail

DEMO_DIR = RESULTS_DIR / "forecast_demo"
METHOD_LABELS = {"naive_last": "Tháng trước", "moving_average_3": "Trung bình 3 tháng", "ridge": "Ridge · 3 độ trễ"}
TARGET_MONTHS = ("2013-10-01", "2013-11-01", "2013-12-01", "2014-01-01")
MARKETS = ("Central", "East", "South", "West")


def number_vi(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def speech_number(value: float) -> str:
    """Spell numbers out so the Vietnamese phonemizer never reads digit runs."""
    digits = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
    def group(n, full=False):
        h, rest = divmod(n, 100)
        t, u = divmod(rest, 10)
        words = [digits[h], "trăm"] if h or full else []
        if t >= 2:
            words += [digits[t], "mươi"]
        elif t == 1:
            words += ["mười"]
        elif u and words:
            words += ["lẻ"]
        if u:
            words += ["mốt" if u == 1 and t >= 2 else "lăm" if u == 5 and t else digits[u]]
        return " ".join(words)
    n = int(round(abs(value)))
    if n == 0:
        return "không"
    parts = []
    for scale, label in [(10**9, "tỷ"), (10**6, "triệu"), (1000, "nghìn"), (1, "")]:
        q, n = divmod(n, scale)
        if q:
            parts.append((group(q, bool(parts) and q < 100) + " " + label).strip())
    return ("âm " if value < 0 else "") + " ".join(parts)


def spoken_month(value: str) -> str:
    date = pd.Timestamp(value)
    return f"tháng {speech_number(date.month)}, năm {speech_number(date.year)}"


def report_context(detail: pd.DataFrame, market: str, target: pd.Timestamp) -> dict:
    """Management context available at the forecast origin; no target-month actual."""
    past = detail.loc[detail.Market.eq(market) & detail.MonthStart.lt(target)]
    totals = past.groupby("MonthStart")[["Sales", "BudgetSales", "Profit"]].sum().sort_index()
    latest = totals.iloc[-1]
    prior = totals.iloc[-2]
    same_last_year = target - pd.DateOffset(years=1)
    products = past.loc[past.MonthStart.eq(totals.index[-1])].groupby("ProductName").Sales.sum().sort_values(ascending=False)
    sales = float(latest.Sales)
    return {
        "known_through": totals.index[-1].strftime("%Y-%m-%d"),
        "recent": [{"month": date.strftime("%Y-%m-%d"), "sales": float(row.Sales),
                    "budget": float(row.BudgetSales), "profit": float(row.Profit)}
                   for date, row in totals.tail(6).iterrows()],
        "latest_sales": sales, "latest_budget": float(latest.BudgetSales),
        "latest_profit": float(latest.Profit),
        "budget_ratio": sales / float(latest.BudgetSales) if latest.BudgetSales else None,
        "profit_ratio": float(latest.Profit) / sales if sales else None,
        "last_change": sales - float(prior.Sales),
        "same_target_last_year": float(totals.loc[same_last_year, "Sales"]) if same_last_year in totals.index else None,
        "products": [{"name": str(name), "sales": float(value), "share": float(value) / sales if sales else None}
                     for name, value in products.head(5).items()],
    }


def monthly_fingerprint(monthly: pd.DataFrame) -> str:
    stable = monthly.sort_values(["Market", "MonthStart"]).to_csv(index=False, date_format="%Y-%m-%d")
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def report_fingerprint(detail: pd.DataFrame) -> str:
    columns = ["MonthStart", "Market", "AreaCode", "ProductName", "Sales", "BudgetSales", "Profit"]
    stable = detail[columns].sort_values(columns[:4]).to_csv(index=False, date_format="%Y-%m-%d")
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def narration(case: dict) -> list[dict]:
    target = spoken_month(case["forecast_month"])
    issue = spoken_month(case["issue_month"])
    explanation = case["explanation"]
    features = explanation["features"]
    context = case["report"]
    market = {"West": "miền Tây", "East": "miền Đông", "South": "miền Nam", "Central": "miền Trung"}[case["market"]]
    change = case["prediction"] - case["last_actual"]
    direction = "tăng" if change >= 0 else "giảm"
    intro = (f"Chúng ta đang xem báo cáo thị trường {market}, chuẩn bị cho {target}.\n\n"
             f"Trước hết, nhìn lại {issue}. Doanh số ghi nhận khoảng {speech_number(case['last_actual'])}. "
             f"So với ngân sách, chênh lệch là {speech_number(context['latest_sales'] - context['latest_budget'])}.\n\n"
             f"Từ nền dữ liệu này, mô hình dự kiến tháng tới đạt khoảng {speech_number(case['prediction'])}. "
             f"Tức là {direction} khoảng {speech_number(abs(change))}, so với tháng vừa kết thúc. "
             "Đường xanh là những gì đã xảy ra. Điểm cam là điều chúng ta đang dự kiến.")
    parts = []
    for feature in features:
        contribution = feature["contribution"]
        if abs(contribution) < .05:
            continue
        else:
            direction = "nâng" if contribution > 0 else "hạ"
            parts.append(f"Dữ liệu {spoken_month(feature['month'])}, {direction} dự báo khoảng {speech_number(abs(contribution))}")
    explain = ("Vậy, con số dự kiến được hình thành như thế nào?\n\n"
               f"Biểu đồ bắt đầu từ mức tham chiếu khoảng {speech_number(explanation['base_value'])}. "
               + ".\n\n".join(parts) + ".\n\nCộng các phần đóng góp, ta được kết quả dự báo ở cột cuối. "
               "Đây là cách mô hình tính toán. Chưa đủ dữ liệu để kết luận về khuyến mãi hay hành vi khách hàng.")
    action = ("Nên rà soát nhóm sản phẩm có doanh số lớn trước khi điều chỉnh kế hoạch. "
              "Chưa nên tăng mua hàng chỉ dựa vào điểm dự báo này." if change >= 0 else
              "Nên kiểm tra nhóm sản phẩm chủ lực và ngân sách trước khi điều chỉnh kế hoạch. "
              "Dự báo giảm chưa đủ để quyết định cắt hàng hoặc giảm nhân sự.")
    quality = ("Cuối cùng, chúng ta nên sử dụng kết quả này đến mức nào?\n\n"
               f"Trên sáu lần dự báo trong giai đoạn đánh giá, mức lệch tuyệt đối trung bình tại thị trường này "
               f"khoảng {speech_number(case['validation_market']['MAE'])}. "
               "Đây là sai số đã quan sát, chưa phải giới hạn sai số cho tháng tới.\n\n"
               + action + "\n\n"
               + ("Bây giờ, bạn có thể mở kết quả thực tế để đối chiếu. Kết quả đó được giữ riêng khi lập dự báo."
                  if case["actual"] is not None else "Kỳ này chưa có kết quả thực tế. Khi có dữ liệu mới, cần đối chiếu lại dự báo."))
    return [{"id": "forecast", "title": "Bối cảnh và dự kiến", "text": intro},
            {"id": "explain", "title": "Động lực của dự báo", "text": explain},
            {"id": "quality", "title": "Kết luận và điều cần theo dõi", "text": quality}]


def build_demo_bundle(db_path: str | Path = DB_PATH) -> dict:
    detail = read_detail(db_path)
    monthly = monthly_sales(detail)
    if (sorted(monthly.Market.unique()) != list(MARKETS)
            or len(monthly) != 96 or monthly.MonthStart.min() != pd.Timestamp("2012-01-01")
            or monthly.MonthStart.max() != pd.Timestamp("2013-12-01")):
        raise ValueError("Demo này cần snapshot Coffee gốc: 4 Market, đủ 24 tháng 01/2012–12/2013.")
    _, metrics, _, summary = evaluate_monthly(monthly)
    metric_lookup = {(r.Market, r.ModelName): {"MAE": float(r.MAE), "RMSE": float(r.RMSE), "N": int(r.N)}
                     for r in metrics.loc[metrics.Split.eq("validation")].itertuples()}
    cases = []
    for market in MARKETS:
        series = monthly.loc[monthly.Market.eq(market)].set_index("MonthStart").Sales.sort_index()
        for target_text in TARGET_MONTHS:
            target = pd.Timestamp(target_text)
            history = series.loc[series.index < target]
            for method in METHODS:
                explanation = explain_history(history, method)
                case = {
                    "id": f"{market.lower()}_{target:%Y%m}_{method}", "market": market,
                    "forecast_month": target_text, "issue_month": history.index[-1].strftime("%Y-%m-%d"),
                    "train_end": history.index[-1].strftime("%Y-%m-%d"), "method": method,
                    "model_version": MODEL_VERSION, "prediction": explanation["prediction"],
                    "last_actual": float(history.iloc[-1]),
                    "actual": float(series.loc[target]) if target in series.index else None,
                    "history": [{"month": date.strftime("%Y-%m-%d"), "sales": float(value)}
                                for date, value in history.items()],
                    "explanation": explanation, "validation_market": metric_lookup[(market, method)],
                    "report": report_context(detail, market, target),
                    "validation_all": metric_lookup[("ALL", method)],
                    "market_comparison": [{"method": m, "label": METHOD_LABELS[m],
                                           **metric_lookup[(market, m)]} for m in METHODS],
                }
                case["chapters"] = narration(case)
                cases.append(case)
    return {
        "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {"detail_rows": len(detail), "monthly_rows": len(monthly), "source_columns": 20,
                    "start": "2012-01-01", "end": "2013-12-01", "sales_total": float(monthly.Sales.sum()),
                    "monthly_sha256": monthly_fingerprint(monthly),
                    "report_sha256": report_fingerprint(detail),
                    "source_sha256": hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()},
        "methods": METHOD_LABELS, "markets": list(MARKETS), "targets": list(TARGET_MONTHS),
        "selected_method": summary["selected_model"], "selection_rule": summary["selection_rule"],
        "selection_period": "04–09/2013", "selection_known_at": "2013-09-01",
        "comparison": [{"method": method, "label": METHOD_LABELS[method], **metric_lookup[("ALL", method)]}
                       for method in METHODS], "cases": cases,
        "voice": {"status": "not_prepared", "engine": None},
        "limitations": ["Dữ liệu lịch sử, không phải dự báo hiện tại.",
                        "Các độ trễ có tương quan; đóng góp phụ thuộc mô hình và mức tham chiếu.",
                        "Giải thích cơ chế mô hình, không suy ra nguyên nhân kinh doanh.",
                        "Chỉ 6 kỳ validation/Market; không phải khoảng dự báo được hiệu chuẩn."],
        "packages": {name: importlib.metadata.version(name)
                     for name in ("numpy", "pandas", "scikit-learn")},
    }


def save_demo_bundle(bundle: dict, output_dir: str | Path = DEMO_DIR) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "bundle.json"
    temporary = path.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    rows, contributions, scripts = [], [], []
    for case in bundle["cases"]:
        rows.append({k: case[k] for k in ("id", "market", "forecast_month", "issue_month", "method", "prediction", "actual")}
                    | {"base_value": case["explanation"]["base_value"],
                       "reconstruction_error": case["explanation"]["reconstruction_error"],
                       "latest_budget": case["report"]["latest_budget"],
                       "latest_profit": case["report"]["latest_profit"],
                       "budget_ratio": case["report"]["budget_ratio"]})
        contributions.extend({"case_id": case["id"], **row} for row in case["explanation"]["features"])
        scripts.extend({"case_id": case["id"], **chapter} for chapter in case["chapters"])
    for name, records in [("case_summary", rows), ("contributions", contributions),
                          ("narration", scripts), ("validation_metrics", bundle["comparison"])]:
        pd.DataFrame(records).to_csv(output_dir / f"{name}.csv", index=False, encoding="utf-8-sig")
    return path


def load_demo_bundle(path: str | Path = DEMO_DIR / "bundle.json") -> dict:
    bundle = json.loads(Path(path).read_text(encoding="utf-8"))
    if bundle.get("schema_version") != 1 or len(bundle.get("cases", [])) != 48:
        raise ValueError("Gói demo không đúng phiên bản hoặc chưa đủ 48 trường hợp.")
    for case in bundle["cases"]:
        explanation = case["explanation"]
        rebuilt = explanation["base_value"] + sum(row["contribution"] for row in explanation["features"])
        if abs(rebuilt - case["prediction"]) > 1e-6:
            raise ValueError("Gói demo có giải thích không khớp dự báo; hãy tạo lại.")
    if "briefing_version" in bundle:
        from coffee_dw.briefing import validate_briefing
        validate_briefing(bundle)
    return bundle
