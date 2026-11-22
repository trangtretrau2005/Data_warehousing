"""Read-only adapters for the Chapter 4–5 coffee warehouse marts.

This module deliberately does not import the old dashboard or forecasting code.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from coffee_dw.config import DB_PATH

MEASURES = ("Sales", "BudgetSales", "Profit", "Gap")


def _read_sqlite(query: str, db_path: str | Path, params: tuple = ()) -> pd.DataFrame:
    path = Path(db_path).resolve()
    if not path.is_file():
        raise FileNotFoundError("Chưa có kho tham chiếu. Chạy `python -m coffee_dw.cli demo` trước.")
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        return pd.read_sql_query(query, connection, params=params)
    finally:
        connection.close()


def _native_query(query: str, params: tuple = ()) -> pd.DataFrame:
    import pyodbc

    connection_string = os.getenv("COFFEE_DW_SQLSERVER_CONNECTION")
    if not connection_string:
        raise ValueError("Chưa cấu hình kết nối SQL Server; dùng --database hoặc COFFEE_DW_SQLSERVER_CONNECTION.")
    # readonly asks the ODBC driver for SQL_MODE_READ_ONLY. Only fixed SELECT
    # statements from this module can reach this connection.
    try:
        connection = pyodbc.connect(connection_string, timeout=10, readonly=True, autocommit=False)
        try:
            cursor = connection.cursor()
            cursor.execute(query, *params)
            return pd.DataFrame.from_records(cursor.fetchall(), columns=[column[0] for column in cursor.description])
        finally:
            connection.close()
    except pyodbc.Error:
        raise RuntimeError("Không đọc được mart SQL Server. Kiểm tra instance, database, schema và quyền SELECT.") from None


def validate_marts(market_period: pd.DataFrame, product_period: pd.DataFrame) -> None:
    """Refuse ambiguous keys, invalid numbers or inconsistent aggregate marts."""
    for frame, keys in (
        (market_period, ["MonthStart", "Market"]),
        (product_period, ["MonthStart", "Market", "ProductName"]),
    ):
        if frame.empty:
            raise ValueError("Mart chưa có dữ liệu để hiển thị.")
        if frame[keys].isna().any().any() or any(frame[key].astype(str).str.strip().eq("").any() for key in keys):
            raise ValueError("Mart có khóa thiếu hoặc rỗng.")
        frame["MonthStart"] = pd.to_datetime(frame["MonthStart"], errors="raise")
        dates = frame["MonthStart"]
        if dates.isna().any() or not dates.dt.is_month_start.all() or not dates.eq(dates.dt.normalize()).all():
            raise ValueError("MonthStart phải là ngày đầu tháng, không có giờ lẻ.")
        if frame.duplicated(keys).any():
            raise ValueError("Mart không duy nhất theo grain đã công bố.")
        for column in MEASURES:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not np.isfinite(frame[list(MEASURES)].to_numpy(dtype=float)).all():
            raise ValueError("Mart chứa số đo thiếu hoặc không hữu hạn.")
        if not np.allclose(frame["Sales"] - frame["BudgetSales"], frame["Gap"], rtol=0, atol=1e-7):
            raise ValueError("Gap trong mart không bằng Sales trừ BudgetSales.")

    actual = market_period.set_index(["MonthStart", "Market"])[list(MEASURES)].sort_index()
    aggregated = product_period.groupby(["MonthStart", "Market"])[list(MEASURES)].sum().sort_index()
    if not actual.index.equals(aggregated.index) or not np.allclose(
        actual.to_numpy(dtype=float), aggregated.to_numpy(dtype=float), rtol=0, atol=1e-7
    ):
        raise ValueError("Tổng mart sản phẩm không khớp mart Market–tháng theo từng ô.")
    ratio = pd.to_numeric(market_period["BudgetAchievement"], errors="raise")
    zero_budget = market_period["BudgetSales"].eq(0)
    if ratio.loc[zero_budget].notna().any():
        raise ValueError("Tỷ lệ với BudgetSales bằng 0 phải để thiếu.")
    expected = market_period.loc[~zero_budget, "Sales"] / market_period.loc[~zero_budget, "BudgetSales"]
    if not np.allclose(ratio.loc[~zero_budget], expected, rtol=0, atol=1e-6):
        raise ValueError("BudgetAchievement phải là tỷ lệ hai tổng trong cùng lát cắt.")
    market_period["BudgetAchievement"] = ratio


def load_cube(backend: str = "sqlite", db_path: str | Path = DB_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load both named marts; never infer empty product cells to be zero."""
    if backend not in {"sqlite", "sqlserver"}:
        raise ValueError("Nguồn dữ liệu chỉ hỗ trợ sqlite hoặc sqlserver.")
    prefix = "mart." if backend == "sqlserver" else ""
    queries = [
        f"SELECT MonthStart, Market, Sales, BudgetSales, Profit, Gap, BudgetAchievement FROM {prefix}vw_MarketPeriod ORDER BY MonthStart, Market",
        f"SELECT MonthStart, Market, ProductName, Sales, BudgetSales, Profit, Gap FROM {prefix}vw_MarketProductPeriod ORDER BY MonthStart, Market, ProductName",
    ]
    frames = [_native_query(query) if backend == "sqlserver" else _read_sqlite(query, db_path) for query in queries]
    market_period, product_period = frames
    validate_marts(market_period, product_period)
    return market_period, product_period


def load_product_types(backend: str = "sqlite", db_path: str | Path = DB_PATH) -> dict[str, str]:
    prefix = "dw." if backend == "sqlserver" else ""
    query = f"SELECT ProductName, ProductType FROM {prefix}DimProduct ORDER BY ProductName"
    frame = _native_query(query) if backend == "sqlserver" else _read_sqlite(query, db_path)
    if frame.empty or frame["ProductName"].duplicated().any() or frame.isna().any().any():
        raise ValueError("DimProduct thiếu hoặc không duy nhất theo ProductName.")
    return dict(zip(frame["ProductName"], frame["ProductType"]))


def load_state_drill(
    month_start: pd.Timestamp,
    market: str,
    product_name: str,
    backend: str = "sqlite",
    db_path: str | Path = DB_PATH,
) -> pd.DataFrame:
    """Decompose one product cell into State via a parameterized SELECT."""
    if backend not in {"sqlite", "sqlserver"}:
        raise ValueError("Nguồn dữ liệu chỉ hỗ trợ sqlite hoặc sqlserver.")
    month = pd.Timestamp(month_start)
    if pd.isna(month) or not month.is_month_start or month != month.normalize():
        raise ValueError("Tháng phải là ngày đầu tháng hợp lệ.")
    prefix = "mart." if backend == "sqlserver" else ""
    query = (
        "SELECT MonthStart, Market, State, ProductName, SUM(Sales) AS Sales, "
        "SUM(BudgetSales) AS BudgetSales, SUM(Profit) AS Profit, "
        "SUM(Sales) - SUM(BudgetSales) AS Gap "
        f"FROM {prefix}vw_Detail WHERE MonthStart = ? AND Market = ? AND ProductName = ? "
        "GROUP BY MonthStart, Market, State, ProductName ORDER BY Gap, State"
    )
    params = (month.strftime("%Y-%m-%d"), market, product_name)
    frame = _native_query(query, params) if backend == "sqlserver" else _read_sqlite(query, db_path, params)
    if frame.empty:
        return frame
    frame["MonthStart"] = pd.to_datetime(frame["MonthStart"], errors="raise")
    for column in MEASURES:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    if not np.isfinite(frame[list(MEASURES)].to_numpy(dtype=float)).all():
        raise ValueError("Drill-down có số đo thiếu hoặc không hữu hạn.")
    return frame
