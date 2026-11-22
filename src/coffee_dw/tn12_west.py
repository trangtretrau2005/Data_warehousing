"""Reproduce the handbook's separate, exploratory West TN12 protocol.

This module never publishes its choice to ForecastSales or the main demo.
The six selection observations overlap the main study's validation and test.
"""

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
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from coffee_dw.config import ROOT, SOURCE_PATH
from coffee_dw.forecast import monthly_sales
from coffee_dw.source import read_source

PROTOCOL_ID = "tn12-west-201307-201312-lag1-lag2-mean3-alpha1-v1"
FEATURES = ("lag1", "lag2", "mean3")
METHODS = ("naive_last", "moving_average_3", "ridge")
LABELS = {"naive_last": "Tháng trước", "moving_average_3": "Trung bình 3 tháng", "ridge": "Ridge"}
TARGETS = pd.date_range("2013-07-01", "2013-12-01", freq="MS")
HISTORY = pd.date_range("2012-01-01", "2013-12-01", freq="MS")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def west_series(monthly):
    """Validate exactly the snapshot protocol; never impute a missing month."""
    required = {"MonthStart", "Market", "Sales"}
    if not required.issubset(monthly.columns):
        raise ValueError("Cần các cột MonthStart, Market, Sales.")
    part = monthly.loc[monthly.Market.eq("West"), ["MonthStart", "Sales"]].copy()
    part["MonthStart"] = pd.to_datetime(part.MonthStart)
    if part.MonthStart.duplicated().any():
        raise ValueError("West trùng grain tháng; không tự tổng hợp lại mart lỗi.")
    series = part.set_index("MonthStart").Sales.sort_index()
    if not series.index.equals(HISTORY):
        raise ValueError("West cần đủ 24 đầu tháng 01/2012–12/2013; không tự điền kỳ thiếu.")
    values = series.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Sales West phải hữu hạn; không đổi lỗi thành 0.")
    return series.astype(float)


def feature_table(series):
    """For target t, all three predictors are available at t-1."""
    return pd.DataFrame({"Actual": series, "lag1": series.shift(1),
                         "lag2": series.shift(2), "mean3": series.shift(1).rolling(3).mean()})


def evaluate_west(monthly):
    series = west_series(monthly)
    features = feature_table(series)
    predictions, audit, origins = [], [], []
    for target in TARGETS:
        history = series.loc[series.index < target]
        # Both training features and targets are restricted to the past origin.
        train = feature_table(history).dropna()
        current = pd.DataFrame([[history.iloc[-1], history.iloc[-2], history.iloc[-3:].mean()]], columns=list(FEATURES))
        model = make_pipeline(StandardScaler(), Ridge(alpha=1))
        model.fit(train[list(FEATURES)], train.Actual)
        scaler, ridge = model.steps[0][1], model.steps[1][1]
        issue = history.index[-1]
        common = {"Market": "West", "ForecastMonth": target, "IssueMonth": issue,
                  "TrainEnd": issue, "ModelVersion": PROTOCOL_ID, "Split": "exploratory_selection"}
        estimates = (float(history.iloc[-1]), float(history.iloc[-3:].mean()), float(model.predict(current)[0]))
        for method, estimate in zip(METHODS, estimates):
            predictions.append(common | {"ModelName": method, "Actual": float(series.loc[target]), "Prediction": estimate})
        origins.append(common | {"HistoryN": len(history), "FitN": len(train),
                                  "FirstFitTarget": train.index.min(), "LastFitTarget": train.index.max(),
                                  "lag1": float(current.lag1.iloc[0]), "lag2": float(current.lag2.iloc[0]),
                                  "mean3": float(current.mean3.iloc[0])})
        for i, name in enumerate(FEATURES):
            audit.append(common | {"Feature": name, "FitN": int(scaler.n_samples_seen_),
                                    "MeanTrain": float(scaler.mean_[i]), "ScaleTrain": float(scaler.scale_[i]),
                                    "CoefficientScaled": float(ridge.coef_[i]),
                                    "CoefficientRaw": float(ridge.coef_[i] / scaler.scale_[i]),
                                    "InterceptScaled": float(ridge.intercept_), "Alpha": 1.0})
    predictions = pd.DataFrame(predictions)
    predictions["Error"] = predictions.Prediction - predictions.Actual
    predictions["AbsoluteError"] = predictions.Error.abs()
    metrics = []
    for method in METHODS:
        part = predictions.loc[predictions.ModelName.eq(method)]
        nonzero = part.Actual.ne(0)
        metrics.append({"Market": "West", "ModelName": method, "N": len(part),
                        "MAE": float(part.AbsoluteError.mean()), "RMSE": float(np.sqrt(np.mean(part.Error ** 2))),
                        "Bias": float(part.Error.mean()), "MAPE_N": int(nonzero.sum()),
                        "MAPE": float((part.loc[nonzero, "AbsoluteError"] / part.loc[nonzero, "Actual"].abs()).mean() * 100) if nonzero.any() else np.nan})
    metrics = pd.DataFrame(metrics)
    # Stable order gives Naive -> MA3 -> Ridge for an exact MAE tie.
    selected = str(metrics.sort_values("MAE", kind="stable").iloc[0].ModelName)
    metrics["Selected"] = metrics.ModelName.eq(selected)
    future_target = pd.Timestamp("2014-01-01")
    if selected == "naive_last":
        value = float(series.iloc[-1])
    elif selected == "moving_average_3":
        value = float(series.iloc[-3:].mean())
    else:
        train = features.dropna()
        model = make_pipeline(StandardScaler(), Ridge(alpha=1)).fit(train[list(FEATURES)], train.Actual)
        current = pd.DataFrame([[series.iloc[-1], series.iloc[-2], series.iloc[-3:].mean()]], columns=list(FEATURES))
        value = float(model.predict(current)[0])
    future = pd.DataFrame([{"Market": "West", "ForecastMonth": future_target, "IssueMonth": series.index[-1],
                            "TrainEnd": series.index[-1], "ModelName": selected, "ModelVersion": PROTOCOL_ID,
                            "Prediction": value, "Actual": np.nan, "Split": "future_exploratory"}])
    return {"monthly": series, "features": features, "predictions": predictions, "metrics": metrics,
            "origins": pd.DataFrame(origins), "fit_audit": pd.DataFrame(audit), "future": future, "selected_method": selected}


def render_figures(result, output):
    """Two readable report figures, each available in PNG300/PDF/SVG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    from matplotlib import pyplot as plt

    plt.rcParams.update({"font.family": "Times New Roman", "font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False, "svg.fonttype": "none"})
    path = Path(output) / "figures"
    path.mkdir(exist_ok=True)
    def save(fig, name):
        for suffix in ("png", "pdf", "svg"):
            fig.savefig(path / f"{name}.{suffix}", dpi=300, facecolor="white")
        plt.close(fig)

    wide = result["predictions"].pivot(index="ForecastMonth", columns="ModelName", values="Prediction")
    actual = result["monthly"].loc[TARGETS]
    rows = [[date.strftime("%m/%Y"), f"{actual.loc[date]:,.2f}", *[f"{wide.loc[date, method]:,.2f}" for method in METHODS]] for date in TARGETS]
    fig, axes = plt.subplots(2, 1, figsize=(10, 6.5), gridspec_kw={"height_ratios": [1.8, 1]})
    fig.subplots_adjust(left=.04, right=.96, top=.84, bottom=.15, hspace=.20)
    fig.suptitle("TN12 West · Sáu kỳ thăm dò 07–12/2013", fontsize=18, fontweight="bold", y=.96)
    fig.text(.5, .89, "Cùng kỳ mục tiêu · Ridge: lag1, lag2, mean3 · alpha = 1", ha="center")
    for ax in axes:
        ax.set_axis_off()
    table = axes[0].table(cellText=rows, colLabels=["Tháng", "Thực tế", "Tháng trước", "TB 3 tháng", "Ridge"], loc="center", cellLoc="right")
    table.auto_set_font_size(False); table.set_fontsize(11); table.scale(1, 1.55)
    metric_rows = [[LABELS[row.ModelName], str(row.N), f"{row.MAE:.2f}", f"{row.RMSE:.2f}", "Có" if row.Selected else ""] for row in result["metrics"].itertuples()]
    table2 = axes[1].table(cellText=metric_rows, colLabels=["Phương pháp", "N", "MAE", "RMSE", "Chọn theo MAE"], loc="center", cellLoc="right")
    table2.auto_set_font_size(False); table2.set_fontsize(11); table2.scale(1, 1.55)
    for tab in (table, table2):
        for (r, c), cell in tab.get_celld().items():
            cell.set_edgecolor("#CCD6DF")
            if r == 0:
                cell.set_facecolor("#E8EFF5"); cell.set_text_props(weight="bold", color="#19344D")
    fig.text(.04, .065, "Nguồn: Coffee.csv, tổng hợp Market–tháng. Đơn vị Sales theo nguồn, chưa công bố tiền tệ.", fontsize=10)
    fig.text(.04, .03, "Sáu kỳ dùng chọn phương pháp; không phải test độc lập. Không trộn với protocol chính 15/6/3.", fontsize=10)
    save(fig, "TN12_eval")

    selected = result["selected_method"]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    fig.subplots_adjust(left=.12, right=.97, top=.82, bottom=.27)
    ax.plot(TARGETS, actual, marker="o", color="#19344D", label="Thực tế", linewidth=1.8)
    ax.plot(TARGETS, wide[selected], marker="s", linestyle="--", color="#207F83", label=f"Dự báo · {LABELS[selected]}", linewidth=1.8)
    ax.plot(pd.Timestamp("2014-01-01"), result["future"].Prediction.iloc[0], marker="D", markerfacecolor="white", markeredgecolor="#A25B38", linestyle="none", label="01/2014 · chưa có actual")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", color="#E1E7EC", linewidth=.7)
    ax.set_ylabel("Sales · đơn vị nguồn")
    fig.legend(*ax.get_legend_handles_labels(), loc="lower center", bbox_to_anchor=(.5, .075), ncol=2, frameon=False, fontsize=10)
    fig.suptitle("TN12 West · Thực tế và phương pháp chọn", fontsize=17, fontweight="bold", y=.96)
    fig.text(.5, .88, "Chọn trên 6 kỳ 07–12/2013; dự báo một bước, lịch sử mở rộng", ha="center")
    fig.text(.05, .04, "Nguồn: Coffee.csv. Kết quả thăm dò; không thay MA3 đã chọn của protocol chính.", fontsize=10)
    save(fig, "TN12_chart")


def run_study(source=SOURCE_PATH, output=ROOT / "experiments" / "tn12_west" / "results", *, render=True):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    before = sha(source)
    detail, rejected = read_source(source)
    if not rejected.empty:
        raise ValueError("Có dòng reject; cần rà soát nguồn trước khi chạy TN12.")
    monthly = monthly_sales(detail)
    result = evaluate_west(monthly)
    protocol = {"id": PROTOCOL_ID, "market": "West", "history_start": "2012-01-01", "history_end": "2013-12-01",
                "selection_start": "2013-07-01", "selection_end": "2013-12-01", "n_per_method": 6,
                "features": list(FEATURES), "ridge_alpha": 1.0, "scaler_fit_scope": "past training feature rows at each origin",
                "selection_rule": "minimum six-origin MAE; tie order naive_last, moving_average_3, ridge",
                "independent_test": False, "status": "reproduction_of_known_exploratory_example",
                "main_study_changed": False, "writes_warehouse": False,
                "reference": "docs/Huong_dan_Coffee_Chains_Kaggle.docx, mục TN12"}
    write_json(output / "protocol.json", protocol)
    for key in ("predictions", "metrics", "origins", "fit_audit", "future"):
        result[key].to_csv(output / f"{key}.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    result["features"].rename_axis("ForecastMonth").reset_index().to_csv(output / "features.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    result["monthly"].rename_axis("MonthStart").reset_index().to_csv(output / "west_monthly.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    wide = result["predictions"].pivot(index="ForecastMonth", columns="ModelName", values="Prediction")
    wide.insert(0, "Actual", result["monthly"].loc[TARGETS])
    wide.to_csv(output / "six_origin_comparison.csv", encoding="utf-8-sig", date_format="%Y-%m-%d")
    if render:
        render_figures(result, output)
    metric_lines = "\n".join(f"| {LABELS[r.ModelName]} | {r.N} | {r.MAE:.2f} | {r.RMSE:.2f} |" for r in result["metrics"].itertuples())
    selected = result["selected_method"]
    future_value = float(result["future"].Prediction.iloc[0])
    analysis = f"""# TN12 West — tái lập ví dụ riêng của sổ tay

## Thiết kế và kết quả

West có 24 tháng 01/2012–12/2013. Ba phương pháp cùng dự báo sáu tháng 07–12/2013,
mỗi lần chỉ dùng lịch sử đến tháng trước. Ridge alpha=1, có StandardScaler fit trên
các mẫu quá khứ, dùng lag1, lag2 và mean3 = trung bình ba Sales trước tháng đích.
Origin đầu có 18 tháng lịch sử và 15 mẫu fit; origin cuối có 23 tháng và 20 mẫu fit.

| Phương pháp | N | MAE | RMSE |
| --- | ---: | ---: | ---: |
{metric_lines}

Chọn **{LABELS[selected]}** bằng MAE trên sáu kỳ. Dự báo West 01/2014 = **{future_value:,.2f}**
đơn vị Sales nguồn; TrainEnd 12/2013, chưa có actual tháng 01/2014 để chấm sai số.
Ridge không vượt baseline ở ví dụ này; không có căn cứ bắt buộc dùng ML chỉ vì mô hình phức tạp hơn.

## Cách đọc và giới hạn

- Đây là ví dụ thăm dò **đã biết kết quả tham chiếu** từ tài liệu gốc, không phải kiểm định mù mới.
- Sáu kỳ vừa dùng so sánh vừa dùng chọn; không có test độc lập trong TN12 West này.
- Protocol chính vẫn là 15 tháng khởi tạo, validation 04–09/2013, test 10–12/2013, Ridge lag123 và chọn MA3 gộp bốn Market.
  Không so trực tiếp MAE giữa hai protocol, không thay model phục vụ của demo bằng lựa chọn West này.
- Chỉ có sáu lỗi dự báo ở một thị trường; không suy rộng sang mọi Market hoặc hiệu quả vận hành.
- Dữ liệu là nguồn lịch sử; 01/2014 không phải tháng tới của thời điểm hiện tại. Không có đơn vị tiền tệ công bố.
- Không ghi ForecastSales hoặc kho SQLite/SQL Server; kết quả độc lập ở thư mục này để tránh lẫn phiên bản.

## Minh chứng

- `six_origin_comparison.csv`: sáu dòng actual và ba dự báo; `predictions.csv`: 18 dự báo với origin/version/error.
- `origins.csv`: số tháng lịch sử, số mẫu fit, thời điểm fit và feature dùng dự báo.
- `fit_audit.csv`: mean/scale/hệ số theo từng feature tại từng origin; `features.csv` giữ thiếu ở ba tháng đầu.
- `future.csv`: dự báo West 01/2014, actual trống; `protocol.json` khóa cấu hình; `manifest.json` truy vết nguồn/mã/output.
- `figures/TN12_eval.png` và `TN12_chart.png`: bảng kết quả và hình thời gian, kèm PDF/SVG.

Tái lập: `.\\.venv\\Scripts\\python experiments/tn12_west/run.py`.
Kiểm tra: `.\\.venv\\Scripts\\python -m pytest tests/test_tn12_west.py`.
"""
    (output / "analysis.md").write_text(analysis, encoding="utf-8")
    body = f"<h1>TN12 West — kết quả tái lập</h1><p>07–12/2013 · N=6/phương pháp · thăm dò, không có test độc lập.</p>{result['metrics'].to_html(index=False, float_format=lambda x: f'{x:,.2f}')}<h2>Sáu dự báo từng phương pháp</h2>{wide.to_html(float_format=lambda x: f'{x:,.2f}')}"
    if render:
        body += '<img src="figures/TN12_eval.png" alt="Sáu kỳ và MAE RMSE"><img src="figures/TN12_chart.png" alt="West actual và dự báo">'
    body += f"<h2>Phân tích, quy trình và giới hạn</h2><pre>{html.escape(analysis)}</pre>"
    (output / "report.html").write_text('<!doctype html><html lang="vi"><meta charset="utf-8"><title>TN12 West</title><style>body{max-width:1050px;margin:40px auto;font:18px Georgia,serif;color:#19344d}table{border-collapse:collapse;width:100%;font-size:16px}th,td{padding:9px;border:1px solid #ccd6df}img{max-width:100%}pre{white-space:pre-wrap;font:16px Georgia,serif;line-height:1.6}</style>' + body + '</html>', encoding="utf-8")
    after = sha(source)
    if before != after:
        raise RuntimeError("Checksum nguồn thay đổi trong khi chạy.")
    def git(*args):
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None  # A distributable working-source snapshot may omit .git.
    manifest = {"protocol_id": PROTOCOL_ID, "generated_utc": datetime.now(timezone.utc).isoformat(),
                "source": {"path": str(source.resolve()), "sha256_before": before, "sha256_after": after,
                           "accepted_rows": len(detail), "rejected_rows": len(rejected), "monthly_cells": len(monthly),
                           "west_months": len(result["monthly"]), "sales": float(detail.Sales.sum()),
                           "budget_sales": float(detail.BudgetSales.sum()), "profit": float(detail.Profit.sum())},
                "selected_method": selected, "forecast_201401": future_value, "predictions": len(result["predictions"]),
                "python": platform.python_version(), "packages": {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "scikit-learn", "matplotlib")},
                "git_commit": git("rev-parse", "HEAD"), "git_branch": git("branch", "--show-current"),
                "working_tree_dirty": None if git("rev-parse", "HEAD") is None else bool(git("status", "--porcelain")),
                "code_sha256": {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in [Path(__file__), ROOT / "experiments/tn12_west/run.py"]},
                "artifacts": [{"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(output.rglob("*")) if p.is_file() and p.name != "manifest.json"],
                "limitations": ["known exploratory handbook example; no independent test", "source CSV; not SQL Server evidence", "does not change main model selection or warehouse"]}
    write_json(output / "manifest.json", manifest)
    return manifest
