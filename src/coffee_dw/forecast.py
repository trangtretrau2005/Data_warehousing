"""One-month-ahead forecasts with time-ordered model selection.

The supplied Coffee data has 24 historical months (2012–2013). Forecasts for
January 2014 are outside this file; their accuracy cannot yet be measured.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from coffee_dw.config import DB_PATH, RESULTS_DIR
from coffee_dw.warehouse import read_detail

METHODS = ("naive_last", "moving_average_3", "ridge")
MODEL_VERSION = "v1-lag123-alpha1"


def monthly_sales(detail: pd.DataFrame) -> pd.DataFrame:
    """Aggregate actual sales before comparing them to a forecast fact."""
    result = detail.groupby(["MonthStart", "Market"], as_index=False)["Sales"].sum()
    result["MonthStart"] = pd.to_datetime(result["MonthStart"])
    return result.sort_values(["Market", "MonthStart"]).reset_index(drop=True)


def predict_next(history: pd.Series, method: str) -> float:
    """Predict solely from an already observed history, never a target row."""
    values = np.asarray(history, dtype=float)
    if len(values) < 6 or not np.isfinite(values).all():
        raise ValueError("Cần ít nhất 6 kỳ lịch sử liên tục với Sales hữu hạn.")
    if method == "naive_last":
        return float(values[-1])
    if method == "moving_average_3":
        return float(values[-3:].mean())
    if method != "ridge":
        raise ValueError(f"Phương pháp không hỗ trợ: {method}")
    # For each training target t, features are observations t-1, t-2, t-3.
    features = np.array([values[i - 3:i][::-1] for i in range(3, len(values))])
    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    model.fit(features, values[3:])
    return float(model.predict(values[-3:][::-1].reshape(1, -1))[0])


def _metric_rows(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    scopes = [("ALL", predictions)] + list(predictions.groupby("Market", sort=True))
    for market, scope in scopes:
        for (method, split), group in scope.groupby(["ModelName", "Split"], sort=True):
            error = group["Prediction"] - group["Actual"]
            nonzero = group["Actual"].ne(0)
            mape = (error[nonzero].abs() / group.loc[nonzero, "Actual"].abs()).mean() * 100
            rows.append({"Market": market, "ModelName": method, "Split": split,
                         "N": len(group), "MAE": float(error.abs().mean()),
                         "RMSE": float(np.sqrt((error ** 2).mean())),
                         "MAPE": None if pd.isna(mape) else float(mape)})
    return pd.DataFrame(rows)


def evaluate_monthly(monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Use six validation months to choose globally, then report three test months.

    For the supplied file the initial history is 15 months, validation is
    April–September 2013, and held-out test is October–December 2013. If history
    is extended, the final nine months retain these respective roles.
    """
    monthly = monthly.copy()
    monthly["MonthStart"] = pd.to_datetime(monthly["MonthStart"])
    if monthly.empty or monthly.duplicated(["MonthStart", "Market"]).any():
        raise ValueError("Dữ liệu dự báo phải duy nhất theo thị trường–tháng.")
    if not monthly["MonthStart"].dt.is_month_start.all():
        raise ValueError("MonthStart phải là ngày đầu tháng.")
    months = pd.DatetimeIndex(sorted(monthly["MonthStart"].unique()))
    if len(months) < 24:
        raise ValueError("Cần tối thiểu 24 tháng để có 15 kỳ lịch sử, 6 chọn mô hình, 3 kiểm tra.")
    expected = pd.date_range(months.min(), months.max(), freq="MS")
    if not months.equals(expected):
        raise ValueError("Chuỗi thiếu tháng; cần đối soát nguồn trước khi tạo lag.")
    rows = []
    market_series = {}
    for market, group in monthly.groupby("Market", sort=True):
        series = group.set_index("MonthStart")["Sales"].sort_index()
        if not series.index.equals(months) or not np.isfinite(series.to_numpy(dtype=float)).all():
            raise ValueError(f"Thị trường {market} thiếu tháng hoặc có Sales không hữu hạn.")
        market_series[market] = series
        for target in months[-9:]:
            history = series.loc[series.index < target]
            for method in METHODS:
                rows.append({"Market": market, "ForecastMonth": target,
                             "IssueMonth": history.index.max(), "TrainEnd": history.index.max(),
                             "ModelName": method, "ModelVersion": MODEL_VERSION,
                             "Prediction": predict_next(history, method),
                             "Actual": float(series.loc[target]),
                             "Split": "validation" if target < months[-3] else "test"})
    predictions = pd.DataFrame(rows)
    metrics = _metric_rows(predictions)
    candidates = metrics.loc[metrics.Market.eq("ALL") & metrics.Split.eq("validation")]
    selected = min(METHODS, key=lambda m: float(candidates.loc[candidates.ModelName.eq(m), "MAE"].iloc[0]))
    target = months[-1] + pd.offsets.MonthBegin(1)
    future = pd.DataFrame([
        {"Market": market, "ForecastMonth": target, "IssueMonth": months[-1],
         "TrainEnd": months[-1], "ModelName": selected, "ModelVersion": MODEL_VERSION,
         "Prediction": predict_next(series, selected), "Actual": np.nan, "Split": "future"}
        for market, series in market_series.items()
    ])
    summary = {
        "selected_model": selected, "selection_rule": "Minimum pooled validation MAE; test is not used for selection",
        "model_version": MODEL_VERSION, "markets": list(market_series),
        "initial_history_months": len(months) - 9,
        "validation_start": months[-9].strftime("%Y-%m-%d"),
        "validation_end": months[-4].strftime("%Y-%m-%d"),
        "test_start": months[-3].strftime("%Y-%m-%d"),
        "test_end": months[-1].strftime("%Y-%m-%d"),
        "forecast_month": target.strftime("%Y-%m-%d"),
        "train_end": months[-1].strftime("%Y-%m-%d"),
        "validation_predictions_per_model": len(market_series) * 6,
        "test_predictions_per_model": len(market_series) * 3,
        "limitation": "Historical one-step evaluation; future target has no actual in the supplied file.",
    }
    return predictions, metrics, future, summary


def run_forecast(db_path: str | Path = DB_PATH, output_dir: str | Path = RESULTS_DIR / "forecast") -> dict:
    """Read the warehouse, evaluate, save reviewable artifacts and forecast fact."""
    predictions, metrics, future, summary = evaluate_monthly(monthly_sales(read_detail(db_path)))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(output_dir / "predictions.csv", index=False, date_format="%Y-%m-%d")
    metrics.to_csv(output_dir / "metrics.csv", index=False)
    future.to_csv(output_dir / "next_month.csv", index=False, date_format="%Y-%m-%d")
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    combined = pd.concat([predictions, future], ignore_index=True)
    columns = ["Market", "ForecastMonth", "IssueMonth", "TrainEnd", "ModelName", "ModelVersion", "Prediction", "Actual", "Split"]
    for col in ("ForecastMonth", "IssueMonth", "TrainEnd"):
        combined[col] = combined[col].dt.strftime("%Y-%m-%d")
    records = [tuple(None if pd.isna(value) else value for value in row)
               for row in combined[columns].itertuples(index=False, name=None)]
    with sqlite3.connect(db_path) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS ForecastSales (
            Market TEXT NOT NULL, ForecastMonth TEXT NOT NULL, IssueMonth TEXT NOT NULL,
            TrainEnd TEXT NOT NULL, ModelName TEXT NOT NULL, ModelVersion TEXT NOT NULL,
            Prediction REAL NOT NULL, Actual REAL, Split TEXT NOT NULL,
            PRIMARY KEY (Market, ForecastMonth, IssueMonth, ModelName, ModelVersion))""")
        conn.executemany("""INSERT INTO ForecastSales VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT (Market,ForecastMonth,IssueMonth,ModelName,ModelVersion)
            DO UPDATE SET Prediction=excluded.Prediction, Actual=excluded.Actual,
                          TrainEnd=excluded.TrainEnd, Split=excluded.Split""", records)
    return summary
