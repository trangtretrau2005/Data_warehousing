"""Render an honest forecast review without changing models or baseline artifacts.

Reads the fixed 15/6/3 study, checks every MA3 point against the source, and shows
six validation plus three test origins. An optional later exploratory study is
displayed separately; this renderer never fits, selects or publishes a model.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import platform
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib.dates as mdates
from matplotlib import pyplot as plt, patches, ticker
import numpy as np
import pandas as pd

from coffee_dw.config import SOURCE_PATH
from coffee_dw.exploration import vi
from coffee_dw.exploration_plots import configure, frame, numeric_axis, NAVY, TEAL, GOLD, ROSE, INK, MUTED, GRID
from coffee_dw.forecast import monthly_sales
from coffee_dw.source import read_source

MARKETS = ["Central", "East", "South", "West"]
BASELINE = ROOT / "experiments/baseline/results"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_review_inputs(baseline=BASELINE):
    source_hash = sha(SOURCE_PATH)
    manifest = json.loads((baseline / "manifest.json").read_text(encoding="utf-8"))
    if manifest["source"]["sha256"] != source_hash or manifest["selected_method"] != "moving_average_3":
        raise ValueError("Baseline source or selected method no longer matches this review")
    files = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
    inputs, parts = {}, []
    for relative, split in [("03_validation/predictions.csv", "validation"), ("04_test/predictions.csv", "test")]:
        path = baseline / relative
        if sha(path) != files[relative]:
            raise ValueError(f"Changed baseline artifact: {relative}")
        inputs[str(path.relative_to(ROOT))] = sha(path)
        predictions = pd.read_csv(path, parse_dates=["ForecastMonth", "IssueMonth", "TrainEnd"])
        predictions = predictions.loc[predictions.ModelName.eq("moving_average_3")].copy()
        if not predictions.Split.eq(split).all():
            raise ValueError("Split labels do not match input folders")
        parts.append(predictions)
    chosen = pd.concat(parts, ignore_index=True).sort_values(["Market", "ForecastMonth"]).reset_index(drop=True)
    source, rejects = read_source(SOURCE_PATH)
    if len(rejects):
        raise ValueError("Source has rejects; do not plot a stale evaluation")
    monthly = monthly_sales(source).sort_values(["Market", "MonthStart"])
    if len(monthly) != 96 or monthly.duplicated(["Market", "MonthStart"]).any():
        raise ValueError("The fixed review needs the original 96-cell monthly source")
    expected_dates = pd.date_range("2013-04-01", "2013-12-01", freq="MS")
    if len(chosen) != 36 or chosen.duplicated(["Market", "ForecastMonth"]).any():
        raise ValueError("Expected 36 unique MA3 predictions, not duplicated forecasts")
    for market in MARKETS:
        part = chosen.loc[chosen.Market.eq(market)]
        if not pd.DatetimeIndex(part.ForecastMonth).equals(expected_dates):
            raise ValueError(f"Missing evaluation month for {market}")
        history = monthly.loc[monthly.Market.eq(market)].set_index("MonthStart").Sales
        for row in part.itertuples():
            train_end = row.ForecastMonth - pd.offsets.MonthBegin(1)
            if row.TrainEnd != train_end or row.IssueMonth != train_end:
                raise ValueError("Review is for one-step origins only")
            np.testing.assert_allclose(row.Actual, history.loc[row.ForecastMonth], atol=1e-9, rtol=0)
            previous = history.loc[history.index < row.ForecastMonth].tail(3)
            np.testing.assert_allclose(row.Prediction, previous.mean(), atol=1e-8, rtol=0)
            expected_split = "validation" if row.ForecastMonth <= pd.Timestamp("2013-09-01") else "test"
            if row.Split != expected_split:
                raise ValueError("Validation/test boundary drifted")
    if not np.isfinite(chosen[["Actual", "Prediction"]]).all().all():
        raise ValueError("Non-finite plotted value")
    chosen["Error"] = chosen.Prediction - chosen.Actual
    chosen["AbsoluteError"] = chosen.Error.abs()
    chosen["APE"] = chosen.AbsoluteError.div(chosen.Actual.abs().where(chosen.Actual.ne(0))) * 100
    inputs["data/raw/Coffee.csv"] = source_hash
    return chosen, monthly, inputs


def save_figure(fig, output, name, title, note):
    fig.texts[0].set_text("COFFEE CHAINS  /  FORECAST REVIEW")
    fig.text(.055, .025, textwrap.fill(note, 140), fontsize=11, color=MUTED, va="bottom")
    folder = output / "figures"
    folder.mkdir(parents=True, exist_ok=True)
    for suffix in ["png", "pdf", "svg"]:
        fig.savefig(folder / f"{name}.{suffix}", dpi=300, bbox_inches="tight", pad_inches=.18)
    plt.close(fig)
    return {"name": name, "title": title, "note": note}


def nine_origins(chosen, output):
    title = "Đọc dự báo trên chín kỳ có kết quả thực tế"
    fig, axes = frame(title, "MA3 chính thức · 04–12/2013 · mỗi điểm dự báo trước 1 tháng · thang Y riêng từng Market",
                      rows=2, columns=2, size=(12, 10), top=.79, bottom=.17, hspace=.43, wspace=.27)
    for axis, market in zip(axes.flat, MARKETS):
        part = chosen.loc[chosen.Market.eq(market)]
        axis.axvspan(pd.Timestamp("2013-03-16"), pd.Timestamp("2013-09-16"), color=GOLD, alpha=.075, zorder=0)
        axis.axvspan(pd.Timestamp("2013-09-16"), pd.Timestamp("2013-12-16"), color=ROSE, alpha=.09, zorder=0)
        axis.axvline(pd.Timestamp("2013-09-16"), color=MUTED, lw=.8, ls=":")
        axis.plot(part.ForecastMonth, part.Actual, color=INK, lw=2.35, marker="o", ms=4.7, label="Actual", zorder=3)
        axis.plot(part.ForecastMonth, part.Prediction, color=TEAL, lw=2.25, ls="--", marker="s", ms=4.2, label="MA3", zorder=3)
        axis.set_title(f"{market}  ·  6 validation + 3 test", fontsize=16, loc="left", pad=11)
        axis.set_ylabel("Sales · đơn vị nguồn", fontsize=13)
        numeric_axis(axis)
        axis.set_xlim(pd.Timestamp("2013-03-20"), pd.Timestamp("2013-12-13"))
        axis.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
        axis.tick_params(axis="x", labelsize=11)
        if market == "West":
            row = part.loc[part.ForecastMonth.eq("2013-11-01")].iloc[0]
            axis.plot([row.ForecastMonth] * 2, [row.Actual, row.Prediction], color=ROSE, lw=2.2, zorder=4)
            axis.annotate("11/2013: +477,33\nAPE 4,22%", xy=(row.ForecastMonth, (row.Actual+row.Prediction)/2),
                          xytext=(.12, .12), textcoords="axes fraction", fontsize=11.5, color=ROSE,
                          bbox=dict(boxstyle="round,pad=.32", fc="white", ec="#D7BEC5", lw=.7),
                          arrowprops=dict(arrowstyle="->", color=ROSE, lw=1.05))
    fig.legend(handles=[plt.Line2D([], [], color=INK, marker="o", lw=2.2, label="Actual"),
                        plt.Line2D([], [], color=TEAL, marker="s", lw=2.2, ls="--", label="MA3 chính thức"),
                        patches.Patch(facecolor=GOLD, alpha=.18, label="Validation · dùng chọn"),
                        patches.Patch(facecolor=ROSE, alpha=.18, label="Test · dùng báo cáo")],
               loc="lower center", bbox_to_anchor=(.52, .073), ncol=4, frameon=False, fontsize=11.5)
    return save_figure(fig, output, "01_ma3_nine_origins", title,
                       "Nguồn: Coffee.csv và baseline đã khóa. 36 điểm = 24 validation + 12 test; không phải 36 điểm test. Không vẽ dải 95% chưa hiệu chuẩn.")


def error_dots(chosen, output):
    test = chosen.loc[chosen.Split.eq("test")].sort_values(["AbsoluteError", "Market", "ForecastMonth"], ascending=[False, True, True])
    title = "Nhìn rõ cả mười hai sai số test"
    fig, axes = frame(title, "MA3 · 10–12/2013 · Error = dự báo − actual · xếp theo độ lệch tuyệt đối",
                      size=(11.5, 8.7), top=.79, bottom=.18)
    axis = axes[0, 0]
    axis.axvline(0, color=MUTED, lw=1.1)
    for i, row in enumerate(test.itertuples()):
        color = ROSE if row.Error > 0 else TEAL
        axis.hlines(i, 0, row.Error, color=color, lw=2, alpha=.6)
        axis.scatter(row.Error, i, s=60, color=color, edgecolor="white", linewidth=.7, zorder=3)
        label = f"{row.Error:+,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
        label += f"  |  APE {vi(row.APE,2)}%"
        axis.annotate(label, (row.Error, i), xytext=(8 if row.Error >= 0 else -8, 0), textcoords="offset points",
                      ha="left" if row.Error >= 0 else "right", va="center", fontsize=11.5, color=color)
    axis.set_yticks(range(len(test)), [f"{r.Market} · {r.ForecastMonth:%m/%Y}" for r in test.itertuples()], fontsize=12)
    axis.invert_yaxis()
    axis.set_xlim(-680, 850)
    axis.set_xlabel("Sai số có dấu · đơn vị Sales", fontsize=13)
    numeric_axis(axis, which="x")
    fig.legend(handles=[patches.Patch(color=ROSE, label="Dương: dự báo cao"), patches.Patch(color=TEAL, label="Âm: dự báo thấp")],
               loc="lower center", bbox_to_anchor=(.52, .078), ncol=2, frameon=False, fontsize=12)
    return save_figure(fig, output, "02_twelve_test_errors", title,
                       "Chỉ 3 kỳ test / Market. Sai số lớn nhất là West 11/2013: dự báo cao hơn actual 477,33 (4,224%). Không che ca dự báo kém.")


def audit_table(chosen, output):
    test = chosen.loc[chosen.Split.eq("test")].sort_values(["Market", "ForecastMonth"])
    title = "Bảng kiểm tra thực tế và dự báo trên test"
    fig, axes = frame(title, "MA3 chính thức · 12 ô Market–tháng · số gốc chưa làm tròn lưu trong CSV", size=(11.7, 8.4), top=.78, bottom=.12)
    axis = axes[0, 0]
    axis.set_axis_off()
    cells = [[r.Market, r.ForecastMonth.strftime("%m/%Y"), vi(r.Actual, 0), vi(r.Prediction, 2),
              ("+" if r.Error >= 0 else "−") + vi(abs(r.Error), 2), vi(r.APE, 3) + "%"] for r in test.itertuples()]
    table = axis.table(cellText=cells, colLabels=["Market", "Tháng", "Actual", "MA3", "MA3 − Actual", "APE"],
                       cellLoc="right", colLoc="right", colWidths=[.16, .14, .16, .18, .20, .16], loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(13)
    for (row, col), cell in table.get_celld().items():
        cell.set_height(.068)
        cell.set_edgecolor("#D5DFE8")
        cell.set_linewidth(.6)
        cell.PAD = .085
        cell.set_facecolor(NAVY if row == 0 else "#F3F6F9" if row % 2 else "white")
        cell.get_text().set_color("white" if row == 0 else INK)
        if col < 2:
            cell.get_text().set_ha("left")
    return save_figure(fig, output, "03_test_audit_table", title,
                       "Actual theo từng Market, không phải tổng toàn quốc. APE = |MA3 − Actual| / |Actual| × 100%; không đổi 100% − MAPE thành accuracy.")


def west_case(chosen, monthly, output):
    row = chosen.loc[chosen.Market.eq("West") & chosen.ForecastMonth.eq("2013-11-01")].iloc[0]
    inputs = monthly.loc[monthly.Market.eq("West") & monthly.MonthStart.lt(row.ForecastMonth)].tail(3)
    title = "West tháng 11 năm 2013 đã lệch bao nhiêu"
    fig, axes = frame(title, "Origin 10/2013 · MA3 dự báo một tháng trước · actual đã có để đối chiếu", size=(10.5, 7.4), top=.77, bottom=.23)
    axis = axes[0, 0]
    bars = axis.bar([0, 1], [row.Actual, row.Prediction], color=[INK, TEAL], width=.48, zorder=3)
    for bar, value in zip(bars, [row.Actual, row.Prediction]):
        axis.text(bar.get_x()+bar.get_width()/2, value+180, vi(value, 2), ha="center", fontsize=18, weight="bold")
    axis.set_xticks([0, 1], ["Actual 11/2013", "MA3 phát hành 10/2013"])
    axis.set_ylabel("Sales · đơn vị nguồn")
    axis.set_ylim(0, 14000)
    numeric_axis(axis)
    formula = "(" + " + ".join(vi(v, 0) for v in inputs.Sales) + ") / 3 = " + vi(row.Prediction, 2)
    fig.text(.5, .14, "Đầu vào 08–10/2013: " + formula, ha="center", fontsize=14, color=TEAL)
    fig.text(.5, .09, "Dự báo cao hơn actual 477,33 · APE 4,224%", ha="center", fontsize=15, weight="bold", color=ROSE)
    return save_figure(fig, output, "04_west_november_case", title,
                       "Trục cột bắt đầu từ 0. Giá trị actual West là 11.300; không nhầm với actual Central 10.885, East 7.438, South 4.480 cùng tháng.")


def exploratory_plot(folder, output):
    leaderboard = pd.read_csv(folder / "validation_leaderboard.csv")
    table = leaderboard.loc[leaderboard.Market.eq("ALL")].sort_values("MAE").reset_index(drop=True)
    if len(table) != 11:
        raise ValueError("Expected the declared 11-configuration exploratory review")
    title = "Mở rộng thăm dò có cải thiện validation không"
    labels = {"naive_last": "Naive", "ma_w2": "MA2", "ma_w3": "MA3 · bản chính", "ma_w6": "MA6",
              "ridge_a0p1": "Ridge α0,1", "ridge_a1": "Ridge α1", "ridge_a10": "Ridge α10",
              "seasonal_naive_12": "Seasonal Naive 12", "ses_a0p2": "SES α0,2", "ses_a0p5": "SES α0,5", "ses_a0p8": "SES α0,8"}
    fig, axes = frame(title, "11 cấu hình · cùng 24 target validation · test đã biết nên chưa phải đánh giá mù mới",
                      size=(11.8, 8.8), top=.79, bottom=.15)
    axis = axes[0, 0]
    colors = [TEAL if key == "ma_w3" else NAVY if i == 0 else "#ACBECE" for i, key in enumerate(table.ModelName)]
    axis.barh(range(len(table)), table.MAE, color=colors, height=.62, zorder=3)
    axis.set_yticks(range(len(table)), [labels.get(key, key) for key in table.ModelName], fontsize=12)
    axis.invert_yaxis()
    axis.set_xlabel("MAE validation · đơn vị Sales · thấp hơn tốt hơn")
    numeric_axis(axis, which="x")
    axis.set_xlim(0, table.MAE.max()*1.17)
    for i, value in enumerate(table.MAE):
        axis.text(value+table.MAE.max()*.014, i, vi(value, 2), va="center", fontsize=12)
    return save_figure(fig, output, "05_exploratory_validation", title,
                       "Kết quả thăm dò tách riêng. Không đổi MA3 trong dashboard/bundle từ script vẽ; không chọn cấu hình bằng lỗi test.")


def run(output, review_folder):
    configure()
    chosen, monthly, inputs = read_review_inputs()
    output.mkdir(parents=True, exist_ok=True)
    chosen.to_csv(output / "ma3_all_evaluated.csv", index=False, date_format="%Y-%m-%d", encoding="utf-8-sig")
    test = chosen.loc[chosen.Split.eq("test")]
    test.to_csv(output / "ma3_test_audit.csv", index=False, date_format="%Y-%m-%d", encoding="utf-8-sig")
    november = chosen.loc[chosen.ForecastMonth.eq("2013-11-01")]
    november.to_csv(output / "november_all_markets.csv", index=False, date_format="%Y-%m-%d", encoding="utf-8-sig")
    figures = [nine_origins(chosen, output), error_dots(chosen, output), audit_table(chosen, output), west_case(chosen, monthly, output)]
    exploratory = (review_folder / "validation_leaderboard.csv").exists()
    if exploratory:
        figures.append(exploratory_plot(review_folder, output))
        for name in ["validation_leaderboard.csv", "summary.json", "protocol.json", "selection.json"]:
            path = review_folder / name
            if path.exists():
                inputs[str(path.relative_to(ROOT))] = sha(path)
    west = test.loc[test.Market.eq("West") & test.ForecastMonth.eq("2013-11-01")].iloc[0]
    checks = {"status": "passed", "source_unchanged": sha(SOURCE_PATH) == inputs["data/raw/Coffee.csv"],
              "ma3_points_checked_against_source": len(chosen), "validation_points": int(chosen.Split.eq("validation").sum()),
              "test_points": len(test), "west_november_actual": float(west.Actual),
              "west_november_prediction": float(west.Prediction), "west_november_signed_error": float(west.Error),
              "west_november_APE": float(west.APE), "synthetic_rows_created": 0,
              "model_publication_changed": False, "prediction_intervals_created": False}
    for relative, value in inputs.items():
        if sha(ROOT / relative) != value:
            raise RuntimeError(f"An input changed during render: {relative}")
    (output / "checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = "".join(f"<section><h2>{html.escape(item['title'])}</h2><img src='figures/{item['name']}.png' alt='{html.escape(item['title'])}'><p>{html.escape(item['note'])}</p></section>" for item in figures)
    body = """<!doctype html><html lang='vi'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Đối chiếu dự báo Coffee DW</title><style>body{font-family:'Times New Roman',serif;background:#edf1f5;color:#18324e;margin:0;line-height:1.5;font-size:19px}main{max-width:1160px;margin:24px auto;background:white;padding:34px 46px}h1{font-size:31px}h2{font-size:25px;margin-bottom:8px}section{margin:38px 0}img{width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:17px}td,th{border:1px solid #d9dfe7;padding:8px;text-align:right}th{background:#eaf0f5}a{color:#244e7a}.note{background:#eff5f7;padding:15px 20px}code{font-size:.85em}@media print{body{background:white}main{padding:0;margin:0}section{break-inside:avoid}h2{break-after:avoid}thead{display:table-header-group}}</style><main>
<h1>Đối chiếu thực tế và dự báo Coffee DW</h1><p class='note'>MA3 chính thức được giữ nguyên. Đồ thị đầu mở rộng phần nhìn thành 6 kỳ validation + 3 kỳ test; số kỳ test không tăng. Mỗi điểm vẫn dự báo trước một tháng. Không sinh doanh số giả hoặc dải 95% chưa hiệu chuẩn.</p>""" + rows
    display = test[["Market", "ForecastMonth", "Actual", "Prediction", "Error", "APE"]].copy()
    display["ForecastMonth"] = display.ForecastMonth.dt.strftime("%m/%Y")
    body += "<h2>Dữ liệu kiểm tra mười hai ô test</h2>" + display.to_html(index=False, float_format=lambda x: f"{x:,.3f}", border=0)
    body += "<p><a href='ma3_test_audit.csv'>CSV số gốc</a> · <a href='ma3_all_evaluated.csv'>36 điểm có nhãn split</a> · <a href='november_all_markets.csv'>Actual và dự báo bốn Market 11/2013</a> · <a href='checks.json'>Kết quả đối soát</a></p>"
    faq = ROOT / "docs/trang/forecast_questions.md"
    import os
    faq_relative = Path(os.path.relpath(faq, output)).as_posix()
    body += f"<p><a href='{html.escape(faq_relative)}'>Câu hỏi và cách bảo vệ phương pháp</a>. Tài liệu nền: <a href='https://otexts.com/fpp3/toolbox.html'>Hyndman và Athanasopoulos, Forecasting Principles and Practice, chương 5</a>.</p></main></html>"
    (output / "report.html").write_text(body, encoding="utf-8")
    metadata = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
                "purpose": "presentation and audit only; no model training or publication",
                "source_inputs_sha256": inputs, "script_sha256": sha(Path(__file__)), "figures": figures,
                "exploratory_ranking_included": exploratory,
                "files": [{"path": str(p.relative_to(output)), "sha256": sha(p)} for p in sorted(output.rglob("*")) if p.is_file() and p.name != "manifest.json"]}
    (output / "manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/trang_forecast_review")
    parser.add_argument("--review-dir", type=Path, default=ROOT / "experiments/forecast_review/results")
    args = parser.parse_args()
    print(json.dumps(run(args.output.resolve(), args.review_dir.resolve()), ensure_ascii=True))
