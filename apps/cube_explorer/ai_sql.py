"""Validated Gemini-to-SQL execution for the Coffee detail mart."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
from sqlglot import exp, parse
from sqlglot.errors import ParseError

try:
    from .data import _native_query, _read_sqlite
    from .gemini import FALLBACK_HTTP_CODES, GeminiAPIError, generate_sql_candidate, ordered_model_ids
except ImportError:  # `python apps/cube_explorer/server.py`
    from data import _native_query, _read_sqlite
    from gemini import FALLBACK_HTTP_CODES, GeminiAPIError, generate_sql_candidate, ordered_model_ids

from coffee_dw.config import DB_PATH


ALLOWED_COLUMNS = {
    "MonthStart", "DateKey", "AreaCode", "State", "Market", "MarketSize",
    "ProductName", "ProductLine", "ProductType", "Type", "Sales", "BudgetSales",
    "Profit", "BudgetProfit", "COGS", "BudgetCOGS", "Margin", "BudgetMargin",
    "Marketing", "Inventory", "TotalExpenses", "SourceRow", "BatchID",
}
ALLOWED_FUNCTIONS = {
    "SUM", "AVG", "MIN", "MAX", "COUNT", "ROUND", "ABS", "NULLIF", "COALESCE",
    "CASE", "IF", "AND", "OR", "YEAR", "MONTH", "DATEPART", "EXTRACT",
    "TS_OR_DS_TO_DATE", "RANK", "DENSE_RANK", "ROW_NUMBER", "LAG", "LEAD",
    "STDDEV", "STDDEV_POP", "VARIANCE", "VAR_POP", "POWER", "SQRT", "CONCAT",
    "CAST", "TRY_CAST",
}
MAX_FETCH_ROWS = 201


class QuestionScopeError(ValueError):
    """The question explicitly requests data outside the warehouse contract."""


def validate_question_scope(question: str, meta: dict[str, Any]) -> None:
    available_years = sorted({int(month[:4]) for month in meta["months"]})
    requested_years = {int(value) for value in re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", question)}
    unsupported = sorted(requested_years - set(available_years))
    if unsupported:
        years = ", ".join(map(str, available_years))
        asked = ", ".join(map(str, unsupported))
        raise QuestionScopeError(f"Kho không có dữ liệu năm {asked}; chỉ có năm {years}. Hãy đổi phạm vi câu hỏi.")


def _existing_limit(tree: exp.Expression) -> int | None:
    limit = tree.args.get("limit")
    if not limit:
        return None
    expression = limit.args.get("expression")
    try:
        return int(expression.name) if expression is not None else None
    except (TypeError, ValueError):
        return None


def validate_select(sql: Any, backend: str, enforce_row_guard: bool = True) -> str:
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("Gemini không tạo câu SELECT.")
    sql = sql.strip()
    if len(sql) > 5_000 or ";" in sql or "--" in sql or "/*" in sql:
        raise ValueError("SQL chứa dấu phân tách, comment hoặc vượt giới hạn.")
    dialect = "tsql" if backend == "sqlserver" else "sqlite"
    try:
        statements = parse(sql, read=dialect)
    except ParseError as exc:
        raise ValueError("SQL do Gemini tạo không parse được theo dialect của nguồn.") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError("Chỉ cho phép đúng một SELECT hoặc WITH…SELECT.")
    tree = statements[0]

    forbidden_names = {
        "Insert", "Update", "Delete", "Drop", "Create", "Alter", "Merge", "Command",
        "Execute", "Transaction", "Grant", "Revoke", "Copy", "Pragma", "Attach", "Into",
        "Lock", "Use", "Set", "TruncateTable",
    }
    if any(type(node).__name__ in forbidden_names for node in tree.walk()):
        raise ValueError("SQL chứa thao tác không phải đọc dữ liệu.")
    if any(isinstance(node, exp.Parameter) for node in tree.walk()):
        raise ValueError("SQL không được đọc biến hệ thống hoặc parameter tự do.")
    if any(isinstance(node, exp.Join) for node in tree.walk()):
        raise ValueError("View chi tiết đã denormalize; không cho phép JOIN hoặc self-join.")

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    base_tables = []
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        schema = table.db.lower()
        if name in cte_names and not schema:
            continue
        if name != "vw_detail":
            raise ValueError("SQL chỉ được đọc view mart.vw_Detail.")
        expected_schema = "mart" if backend == "sqlserver" else ""
        if schema != expected_schema:
            raise ValueError("SQL dùng sai schema của view chi tiết.")
        if not isinstance(table.this, exp.Identifier):
            raise ValueError("Không cho phép table-valued function hoặc nguồn động.")
        base_tables.append(table)
    if len(base_tables) != 1:
        raise ValueError("SQL phải đọc đúng một lần từ view chi tiết; không cho phép self-join hoặc nguồn khác.")

    aliases = {alias.alias.lower() for alias in tree.find_all(exp.Alias) if alias.alias}
    allowed_columns = {column.lower() for column in ALLOWED_COLUMNS} | aliases
    invalid_columns = sorted({column.name for column in tree.find_all(exp.Column) if column.name.lower() not in allowed_columns})
    if invalid_columns:
        raise ValueError(f"SQL dùng cột không có trong mart: {', '.join(invalid_columns)}.")

    invalid_functions = sorted(
        {
            function.sql_name()
            for function in tree.find_all(exp.Func)
            if function.sql_name().upper() not in ALLOWED_FUNCTIONS
        }
    )
    if invalid_functions:
        raise ValueError(f"SQL dùng hàm ngoài allowlist: {', '.join(invalid_functions)}.")

    inventory_used = any(column.name.lower() == "inventory" for column in tree.find_all(exp.Column))
    if inventory_used:
        canonical = tree.sql(dialect=dialect).lower()
        exact_month = bool(re.search(r"monthstart\s*=\s*'\d{4}-\d{2}-01'", canonical))
        if not exact_month:
            raise ValueError("Inventory chỉ được truy vấn khi lọc đúng một MonthStart.")

    limit = _existing_limit(tree)
    if enforce_row_guard and (limit is None or limit > MAX_FETCH_ROWS):
        tree = tree.limit(MAX_FETCH_ROWS)
    return tree.sql(dialect=dialect, pretty=True)


def execute_select(sql: str, backend: str, db_path: str | Path = DB_PATH) -> dict[str, Any]:
    display_sql = validate_select(sql, backend, enforce_row_guard=False)
    safe_sql = validate_select(sql, backend, enforce_row_guard=True)
    frame = _native_query(safe_sql) if backend == "sqlserver" else _read_sqlite(safe_sql, db_path)
    truncated = len(frame) >= MAX_FETCH_ROWS
    limited = frame.head(MAX_FETCH_ROWS - 1)
    return {
        "mode": "ai_sql",
        "sql": display_sql,
        "executionSql": safe_sql,
        "params": [],
        "columns": list(limited.columns),
        "rows": json.loads(limited.to_json(orient="records", date_format="iso", date_unit="s")),
        "rowCount": len(frame),
        "truncated": truncated,
        "explanation": (
            "SQL do Gemini đề xuất đã được parse AST, kiểm tra allowlist và chạy qua kết nối chỉ-đọc. "
            "Server thêm giới hạn nội bộ 201 dòng khi thực thi để chỉ hiển thị tối đa 200 và phát hiện phần dư; "
            "giới hạn kỹ thuật này không làm đổi kết quả nhỏ hơn 201 dòng."
        ),
    }


def market_rollup(result: dict[str, Any]) -> dict[str, Any] | None:
    """Return a compact, faithful 3D roll-up for one numeric value per Market."""
    if result.get("truncated") or not 0 < result.get("rowCount", 0) <= 10 or "Market" not in result.get("columns", []):
        return None
    numeric_columns = [
        column
        for column in result["columns"]
        if column != "Market"
        and result["rows"]
        and all(isinstance(row.get(column), (int, float)) and not isinstance(row.get(column), bool) for row in result["rows"])
    ]
    other_columns = [column for column in result["columns"] if column not in {"Market", *numeric_columns}]
    if len(numeric_columns) != 1 or other_columns:
        return None
    metric = numeric_columns[0]
    items = [{"label": row["Market"], "value": row[metric]} for row in result["rows"]]
    if len({item["label"] for item in items}) != len(items):
        return None
    return {
        "dimension": "Market",
        "metric": metric,
        "title": f"{metric} theo Market",
        "items": items,
    }


def cube_context(question: str, result: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    requested_years = [value for value in re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", question)]
    year = requested_years[0] if len(set(requested_years)) == 1 else None
    month = None
    if year:
        month_match = re.search(r"\bth[aá]ng\s*(1[0-2]|0?[1-9])\b", question, re.IGNORECASE)
        if month_match:
            candidate = f"{year}-{int(month_match.group(1)):02d}-01"
            if candidate in meta["months"]:
                month = candidate

    folded_question = question.casefold()
    markets = [market for market in meta["markets"] if re.search(rf"(?<!\w){re.escape(market.casefold())}(?!\w)", folded_question)]
    products = [product for product in meta["products"] if product.casefold() in folded_question]
    market = markets[0] if len(markets) == 1 else None
    focus_products = list(dict.fromkeys(products))
    focus_note = "Phạm vi lấy từ câu hỏi."

    if 0 < result["rowCount"] <= 10 and "ProductName" in result["columns"] and result["rows"]:
        result_products = list(
            dict.fromkeys(row.get("ProductName") for row in result["rows"] if row.get("ProductName") in meta["products"])
        )
        if result_products:
            focus_products = result_products
            focus_note = (
                f"Làm nổi bật đủ {len(result_products)} sản phẩm từ kết quả truy vấn; "
                "các chiều khác giữ theo câu hỏi."
            )
    product = focus_products[0] if len(focus_products) == 1 else None
    if not market and result["rowCount"] == 1 and "Market" in result["columns"] and result["rows"]:
        candidate = result["rows"][0].get("Market")
        if candidate in meta["markets"]:
            market = candidate

    if "profit" in folded_question or "lợi nhuận" in folded_question:
        measure = "Profit"
    elif any(term in folded_question for term in ("gap", "chênh lệch", "hụt", "vượt", "tỷ lệ đạt")):
        measure = "Gap"
    elif "budgetsales" in folded_question or "budget sales" in folded_question or "ngân sách" in folded_question or "budget" in folded_question:
        measure = "BudgetSales"
    else:
        measure = "Sales"
    rollup = market_rollup(result)
    if rollup:
        focus_note = f"Mở đúng {len(rollup['items'])} ô đã GROUP BY Market; không bung lại xuống tháng và sản phẩm."
    return {
        "year": year,
        "month": month,
        "market": market,
        "product": product,
        "products": focus_products,
        "measure": measure,
        "mode": "slice" if month else "all",
        "note": focus_note,
        "rollup": rollup,
    }


def answer_question(
    question: Any,
    meta: dict[str, Any],
    backend: str,
    db_path: str | Path = DB_PATH,
    model: Any = None,
) -> dict[str, Any]:
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Hãy nhập một câu hỏi dữ liệu.")
    question = question.strip()
    if len(question) > 600:
        raise ValueError("Câu hỏi tối đa 600 ký tự.")
    validate_question_scope(question, meta)

    attempts: list[dict[str, str]] = []
    for model_id in ordered_model_ids(model):
        try:
            plan = generate_sql_candidate(model_id, question, meta, backend)
            if plan.get("status") != "query":
                message = str(plan.get("explanation") or "Câu hỏi không thể trả lời từ mart hiện tại.")
                raise QuestionScopeError(message)
            result = execute_select(plan.get("sql"), backend, db_path)
            result["cubeContext"] = cube_context(question, result, meta)
            result["ai"] = {
                "provider": "Google Gemini API",
                "model": model_id,
                "question": question,
                "explanation": str(plan.get("explanation") or ""),
                "fallbackAttempts": attempts,
            }
            return result
        except QuestionScopeError:
            raise
        except GeminiAPIError as exc:
            attempts.append({"model": model_id, "reason": f"HTTP {exc.code} · {exc.status}"})
            if exc.code not in FALLBACK_HTTP_CODES:
                raise RuntimeError(f"Gemini từ chối xác thực hoặc quyền truy cập: {exc.status}.") from None
        except (ValueError, RuntimeError) as exc:
            attempts.append({"model": model_id, "reason": str(exc)[:160]})
    tried = ", ".join(item["model"] for item in attempts)
    raise RuntimeError(f"Không model nào tạo được SELECT hợp lệ. Đã thử: {tried}.")
