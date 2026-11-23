"""Validated read-only query builder for the Coffee warehouse detail mart."""

from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any

import pandas as pd

try:
    from .data import _native_query, _read_sqlite
except ImportError:  # `python apps/cube_explorer/server.py`
    from data import _native_query, _read_sqlite

from coffee_dw.config import DB_PATH


AGGREGATES = {"SUM": "Tổng", "AVG": "Trung bình trên ô fact"}
DIMENSIONS = {
    "MonthStart": "Tháng",
    "Market": "Thị trường",
    "State": "Bang",
    "ProductType": "Nhóm sản phẩm",
    "ProductName": "Sản phẩm",
}
MEASURES = {
    "Sales": "Doanh số thực tế",
    "BudgetSales": "Kế hoạch doanh số",
    "Gap": "Chênh lệch Sales − BudgetSales",
    "Profit": "Lợi nhuận",
    "BudgetProfit": "Kế hoạch lợi nhuận",
    "COGS": "Giá vốn",
    "BudgetCOGS": "Kế hoạch giá vốn",
    "Margin": "Biên gộp",
    "BudgetMargin": "Kế hoạch biên gộp",
    "Marketing": "Chi phí tiếp thị",
    "TotalExpenses": "Tổng chi phí",
}


def _choice_list(value: Any, allowed: Mapping[str, str] | set[str], label: str, maximum: int) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"Cần chọn ít nhất một {label}.")
    if len(value) > maximum or any(not isinstance(item, str) or item not in allowed for item in value):
        raise ValueError(f"{label.capitalize()} nằm ngoài danh sách hỗ trợ.")
    return list(dict.fromkeys(value))


def normalize_spec(raw: Any, meta: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a UI or LLM-produced query specification against fixed domains."""
    if not isinstance(raw, dict):
        raise ValueError("Đặc tả truy vấn phải là một object JSON.")
    allowed_fields = {"aggregate", "measures", "groupBy", "year", "month", "markets", "products"}
    if set(raw) - allowed_fields:
        raise ValueError("Đặc tả chứa trường không được hỗ trợ.")

    aggregate = str(raw.get("aggregate", "SUM")).upper()
    if aggregate not in AGGREGATES:
        raise ValueError("Phép tính chỉ hỗ trợ SUM hoặc AVG.")
    measures = _choice_list(raw.get("measures"), MEASURES, "chỉ tiêu", 4)

    group_by = raw.get("groupBy", [])
    if not isinstance(group_by, list) or len(group_by) > 3:
        raise ValueError("Chỉ được nhóm theo tối đa ba chiều.")
    if any(not isinstance(item, str) or item not in DIMENSIONS for item in group_by):
        raise ValueError("Chiều phân tích nằm ngoài danh sách hỗ trợ.")
    group_by = list(dict.fromkeys(group_by))

    years = {int(month[:4]) for month in meta["months"]}
    year = raw.get("year")
    if year in ("", None):
        year = None
    else:
        try:
            year = int(year)
        except (TypeError, ValueError):
            raise ValueError("Năm phải là một số hợp lệ.") from None
        if year not in years:
            raise ValueError(f"Kho chỉ có dữ liệu trong các năm {sorted(years)}.")

    month = raw.get("month")
    if month in ("", None):
        month = None
    else:
        try:
            month = int(month)
        except (TypeError, ValueError):
            raise ValueError("Tháng phải là một số từ 1 đến 12.") from None
        if month not in range(1, 13):
            raise ValueError("Tháng phải nằm trong khoảng 1 đến 12.")
        if year is None:
            raise ValueError("Chọn năm trước khi lọc theo tháng.")

    markets = raw.get("markets", [])
    products = raw.get("products", [])
    if not isinstance(markets, list) or any(item not in meta["markets"] for item in markets):
        raise ValueError("Market nằm ngoài bốn giá trị của kho.")
    if not isinstance(products, list) or any(item not in meta["products"] for item in products):
        raise ValueError("Sản phẩm nằm ngoài danh mục của kho.")

    return {
        "aggregate": aggregate,
        "measures": measures,
        "groupBy": group_by,
        "year": year,
        "month": month,
        "markets": list(dict.fromkeys(markets)),
        "products": list(dict.fromkeys(products)),
    }


def build_query(spec: Mapping[str, Any], backend: str) -> tuple[str, tuple[Any, ...]]:
    """Generate SQL exclusively from allowlisted identifiers and bound filter values."""
    if backend not in {"sqlite", "sqlserver"}:
        raise ValueError("Nguồn dữ liệu chỉ hỗ trợ sqlite hoặc sqlserver.")

    aggregate = spec["aggregate"]
    select_parts = [f"[{dimension}]" for dimension in spec["groupBy"]]
    for measure in spec["measures"]:
        if measure == "Gap":
            expression = (
                "SUM([Sales]) - SUM([BudgetSales])"
                if aggregate == "SUM"
                else "AVG([Sales] - [BudgetSales])"
            )
        else:
            expression = f"{aggregate}([{measure}])"
        select_parts.append(f"{expression} AS [{aggregate}_{measure}]")

    conditions: list[str] = []
    params: list[Any] = []
    if spec["month"] is not None:
        conditions.append("[MonthStart] = ?")
        params.append(f"{spec['year']:04d}-{spec['month']:02d}-01")
    elif spec["year"] is not None:
        conditions.extend(("[MonthStart] >= ?", "[MonthStart] < ?"))
        params.extend((f"{spec['year']:04d}-01-01", f"{spec['year'] + 1:04d}-01-01"))
    for column, values in (("Market", spec["markets"]), ("ProductName", spec["products"])):
        if values:
            conditions.append(f"[{column}] IN ({','.join('?' for _ in values)})")
            params.extend(values)

    prefix = "mart." if backend == "sqlserver" else ""
    sql = f"SELECT {', '.join(select_parts)} FROM {prefix}vw_Detail"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    if spec["groupBy"]:
        columns = ", ".join(f"[{dimension}]" for dimension in spec["groupBy"])
        sql += f" GROUP BY {columns} ORDER BY {columns}"
    return sql, tuple(params)


def execute_query(
    raw_spec: Any,
    meta: Mapping[str, Any],
    backend: str = "sqlite",
    db_path=DB_PATH,
) -> dict[str, Any]:
    spec = normalize_spec(raw_spec, meta)
    sql, params = build_query(spec, backend)
    frame = _native_query(sql, params) if backend == "sqlserver" else _read_sqlite(sql, db_path, params)
    row_count = len(frame)
    limited = frame.head(200)
    explanation = (
        "AVG là trung bình trên các ô fact tháng × AreaCode × Product trong phạm vi đã chọn."
        if spec["aggregate"] == "AVG"
        else "SUM cộng các ô fact trong cùng bộ lọc và nhóm phân tích."
    )
    return {
        "spec": spec,
        "sql": sql,
        "params": list(params),
        "columns": list(limited.columns),
        "rows": json.loads(limited.to_json(orient="records", date_format="iso", date_unit="s")),
        "rowCount": row_count,
        "truncated": row_count > len(limited),
        "explanation": explanation,
        "cubeContext": {
            "year": str(spec["year"]) if spec["year"] is not None else None,
            "month": f"{spec['year']:04d}-{spec['month']:02d}-01" if spec["month"] is not None else None,
            "market": spec["markets"][0] if len(spec["markets"]) == 1 else None,
            "product": spec["products"][0] if len(spec["products"]) == 1 else None,
            "products": spec["products"],
            "measure": next((item for item in spec["measures"] if item in {"Sales", "BudgetSales", "Profit", "Gap"}), "Gap"),
            "mode": "slice" if spec["month"] is not None else "all",
            "note": "Phạm vi lấy trực tiếp từ bộ lọc truy vấn.",
        },
    }


def query_config(meta: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "aggregates": AGGREGATES,
        "dimensions": DIMENSIONS,
        "measures": MEASURES,
        "years": sorted({int(month[:4]) for month in meta["months"]}),
        "markets": meta["markets"],
        "products": meta["products"],
    }
