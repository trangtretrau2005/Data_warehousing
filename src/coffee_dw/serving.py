"""Read-only dashboard adapters; forecasting is performed offline, never in the UI."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from coffee_dw.forecast import METHODS, MODEL_VERSION, _metric_rows
from coffee_dw.warehouse import read_detail


def dashboard_backend() -> str:
    backend = os.getenv("COFFEE_DW_BACKEND", "sqlite").lower()
    if backend not in {"sqlite", "sqlserver"}:
        raise ValueError("COFFEE_DW_BACKEND phải là sqlite hoặc sqlserver.")
    return backend


def forecast_comparison_frame(predictions, markets, model_name, start_month, end_month):
    """Select historical targets and compute errors without changing the forecast."""
    start, end = pd.Timestamp(start_month), pd.Timestamp(end_month)
    if start > end:
        raise ValueError("Tháng bắt đầu phải trước hoặc bằng tháng kết thúc.")
    frame = predictions.copy()
    frame["ForecastMonth"] = pd.to_datetime(frame.ForecastMonth)
    frame = frame.loc[frame.Market.isin(markets) & frame.ModelName.eq(model_name)
                      & frame.Split.isin(["validation", "test"])
                      & frame.ForecastMonth.between(start, end)].copy()
    frame["Error"] = frame.Prediction - frame.Actual
    frame["AbsoluteError"] = frame.Error.abs()
    frame["AbsolutePercentageError"] = frame.AbsoluteError.div(frame.Actual.abs().where(frame.Actual.ne(0))) * 100
    return frame.sort_values(["ForecastMonth", "Market"]).reset_index(drop=True)


def connect_native():
    import pyodbc

    connection = os.getenv("COFFEE_DW_SQLSERVER_CONNECTION")
    if not connection:
        raise ValueError("Chưa cấu hình COFFEE_DW_SQLSERVER_CONNECTION; xem .env.example.")
    # Do not include connection strings or driver exceptions (possibly secrets) in UI errors.
    try:
        return pyodbc.connect(connection, timeout=10, autocommit=False)
    except pyodbc.Error:
        raise RuntimeError("Không kết nối được SQL Server. Kiểm tra instance, quyền và cấu hình cục bộ.") from None


def native_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    connection = connect_native()
    try:
        cursor = connection.cursor()
        cursor.execute(sql, *params)
        return pd.DataFrame.from_records(cursor.fetchall(), columns=[c[0] for c in cursor.description])
    finally:
        connection.close()


def dashboard_detail(db_path: str | Path, backend: str) -> pd.DataFrame:
    if backend == "sqlite":
        return read_detail(db_path)
    if backend != "sqlserver":
        raise ValueError("Backend không được hỗ trợ.")
    from coffee_dw.source import MEASURES

    detail = native_query("SELECT * FROM mart.vw_Detail")
    detail["MonthStart"] = pd.to_datetime(detail.MonthStart)
    for column in MEASURES:
        detail[column] = pd.to_numeric(detail[column])
    detail["AreaCode"] = detail.AreaCode.astype(str)
    return detail


def native_forecast_frames(frame: pd.DataFrame):
    """Read one coherent four-Market publication, never score a partial upload.

    The current model version has six validation months, three test months and
    one future month. Dates are derived from the future target so an extended
    history retains the same serving contract. An incomplete publication must
    not silently change the comparison population or the validation choice.
    """
    if frame.empty:
        raise FileNotFoundError("Chưa công bố dự báo vào ml.ForecastSales.")
    columns = {"Market", "ForecastMonth", "IssueMonth", "TrainEnd", "ModelName", "ModelVersion", "Prediction", "Actual", "Split"}
    if not columns.issubset(frame.columns):
        raise ValueError("Gói dự báo thiếu cột của hợp đồng ForecastSales.")
    frame = frame.loc[frame.ModelVersion.eq(MODEL_VERSION)].copy()
    if frame.empty:
        raise ValueError("Chưa có phiên bản dự báo tương thích với ứng dụng.")
    for column in ("ForecastMonth", "IssueMonth", "TrainEnd"):
        frame[column] = pd.to_datetime(frame[column])
        dates = frame[column]
        if dates.isna().any() or not dates.dt.is_month_start.all() or not dates.eq(dates.dt.normalize()).all():
            raise ValueError("Mốc dự báo phải là đầu tháng hợp lệ, không chứa ngày thiếu hoặc giờ lẻ.")
    for column in ("Actual", "Prediction"):
        frame[column] = pd.to_numeric(frame[column])
    if frame.duplicated(["Market", "ForecastMonth", "ModelName"]).any():
        raise ValueError("Có nhiều kỳ phát hành cho cùng mục tiêu; cần chọn publication tường minh.")
    if not frame.IssueMonth.eq(frame.ForecastMonth - pd.offsets.MonthBegin(1)).all() or not frame.IssueMonth.eq(frame.TrainEnd).all():
        raise ValueError("Mốc phát hành dự báo không hợp lệ.")
    if not frame.Split.isin(["validation", "test", "future"]).all():
        raise ValueError("Gói dự báo chứa split không thuộc publication chính.")
    predictions = frame.loc[frame.Split.isin(["validation", "test"])].copy()
    future = frame.loc[frame.Split.eq("future")].copy()
    if predictions.empty or future.empty or predictions.Actual.isna().any() or future.Actual.notna().any():
        raise ValueError("Gói dự báo chưa đủ đánh giá hoặc chứa actual tương lai.")
    if not np.isfinite(frame.Prediction.to_numpy(dtype=float)).all() or not np.isfinite(predictions.Actual.to_numpy(dtype=float)).all():
        raise ValueError("Actual và Prediction đánh giá phải hữu hạn; không đổi lỗi thành 0.")
    markets = {"Central", "East", "South", "West"}
    if set(frame.Market) != markets or set(future.Market) != markets:
        raise ValueError("Publication phải đủ đúng bốn Market Central, East, South, West.")
    if len(future) != len(markets) or future.ForecastMonth.nunique() != 1:
        raise ValueError("Publication cần một dự báo tương lai cho mỗi Market, cùng một kỳ mục tiêu.")
    target = future.ForecastMonth.iloc[0]
    months = pd.date_range(end=target - pd.offsets.MonthBegin(1), periods=9, freq="MS")
    expected = pd.MultiIndex.from_product([sorted(markets), months, METHODS], names=["Market", "ForecastMonth", "ModelName"])
    actual_keys = pd.MultiIndex.from_frame(predictions[["Market", "ForecastMonth", "ModelName"]])
    if len(actual_keys) != len(expected) or len(expected.difference(actual_keys)) or len(actual_keys.difference(expected)):
        raise ValueError("Publication thiếu hoặc thừa mục tiêu/phương pháp: cần đủ 9 tháng × 4 Market × 3 đối chứng.")
    expected_split = predictions.ForecastMonth.isin(months[:6]).map({True: "validation", False: "test"})
    if not predictions.Split.eq(expected_split).all():
        raise ValueError("Lịch publication phải giữ sáu tháng validation rồi ba tháng test trước kỳ tương lai.")
    if predictions.groupby(["Market", "ForecastMonth"]).Actual.nunique().ne(1).any():
        raise ValueError("Actual cùng Market–tháng phải nhất quán giữa các phương pháp.")
    metrics = _metric_rows(predictions)
    candidates = metrics.loc[metrics.Market.eq("ALL") & metrics.Split.eq("validation")].set_index("ModelName")
    if not set(METHODS).issubset(candidates.index):
        raise ValueError("Thiếu phương pháp đối chứng trên validation.")
    selected = min(METHODS, key=lambda m: candidates.loc[m, "MAE"])
    if not future.ModelName.eq(selected).all():
        raise ValueError("Phương pháp công bố không khớp lựa chọn validation.")
    test = predictions.loc[predictions.Split.eq("test")]
    summary = {
        "selected_model": selected,
        "train_end": future.TrainEnd.max().strftime("%Y-%m-%d"),
        "test_start": test.ForecastMonth.min().strftime("%Y-%m-%d"),
        "test_end": test.ForecastMonth.max().strftime("%Y-%m-%d"),
        "model_version": MODEL_VERSION,
    }
    return summary, metrics, predictions, future


def dashboard_forecast(folder: Path, backend: str):
    if backend == "sqlserver":
        return native_forecast_frames(native_query(
            "SELECT Market,ForecastMonth,IssueMonth,TrainEnd,ModelName,ModelVersion,Prediction,Actual,Split "
            "FROM ml.ForecastSales WHERE ModelVersion=?", (MODEL_VERSION,)))
    if backend != "sqlite":
        raise ValueError("Backend không được hỗ trợ.")
    return (
        json.loads((folder / "summary.json").read_text(encoding="utf-8")),
        pd.read_csv(folder / "metrics.csv"),
        pd.read_csv(folder / "predictions.csv", parse_dates=["ForecastMonth"]),
        pd.read_csv(folder / "next_month.csv"),
    )
