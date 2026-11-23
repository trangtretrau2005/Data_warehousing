"""Gemini text-to-query adapter with model discovery and quota fallback.

The API key is read only from GEMINI_API_KEY or GOOGLE_API_KEY.  Gemini never
supplies SQL: it returns a small JSON query spec that query.py validates again.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
AUTO_MODEL = "__auto__"

# Ordered from the quota table supplied for this project: Flash Lite models
# with 500 RPD first, then text Flash models with 20 RPD.  Discovery still
# intersects this list with models.list, so stale/unavailable names disappear.
MODEL_PRIORITY = (
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3-flash",
    "gemini-2.5-flash",
    "gemini-4-hydrogen",
)
FALLBACK_HTTP_CODES = {400, 404, 408, 429, 500, 502, 503, 504}
_model_cache: tuple[float, list[dict[str, Any]]] | None = None


class GeminiAPIError(RuntimeError):
    def __init__(self, code: int, status: str, message: str):
        super().__init__(message)
        self.code = code
        self.status = status


def _api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def _request(path: str, payload: dict[str, Any] | None = None, timeout: float = 12) -> dict[str, Any]:
    key = _api_key()
    if not key:
        raise ValueError("Chưa cấu hình GEMINI_API_KEY trong môi trường local.")
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        API_ROOT + path,
        data=data,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="GET" if payload is None else "POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(1_000_001)
    except HTTPError as exc:
        body = exc.read(65_537)
        try:
            error = json.loads(body.decode("utf-8")).get("error", {})
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            error = {}
        raise GeminiAPIError(
            exc.code,
            str(error.get("status", "HTTP_ERROR")),
            str(error.get("message", f"Gemini API trả HTTP {exc.code}."))[:500],
        ) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("Không kết nối được Gemini API. Kiểm tra mạng rồi thử lại.") from exc
    if len(body) > 1_000_000:
        raise RuntimeError("Phản hồi Gemini vượt quá giới hạn an toàn.")
    try:
        result = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Gemini API trả dữ liệu không đúng JSON.") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Gemini API trả dữ liệu không đúng cấu trúc.")
    return result


def _priority(model_id: str) -> int:
    for index, preferred in enumerate(MODEL_PRIORITY):
        if model_id == preferred or model_id.startswith(preferred + "-"):
            return index
    return len(MODEL_PRIORITY)


def _eligible(model: dict[str, Any]) -> bool:
    name = model.get("name")
    methods = model.get("supportedGenerationMethods", [])
    if not isinstance(name, str) or "generateContent" not in methods:
        return False
    model_id = name.removeprefix("models/")
    # Deliberately exclude agents, Pro/zero-quota families, image, TTS, Live,
    # embedding, Decision, Robotics and Computer Use models.
    excluded_tokens = (
        "image",
        "tts",
        "audio",
        "live",
        "embedding",
        "computer-use",
        "robotics",
        "banana",
        "decision",
        "omni",
    )
    return not any(token in model_id for token in excluded_tokens) and _priority(model_id) < len(MODEL_PRIORITY)


def list_text_models(force: bool = False) -> list[dict[str, Any]]:
    global _model_cache
    now = time.monotonic()
    if not force and _model_cache and now - _model_cache[0] < 300:
        return _model_cache[1]

    models: list[dict[str, Any]] = []
    page_token: str | None = None
    for _ in range(10):
        suffix = "?pageSize=100" + (f"&pageToken={page_token}" if page_token else "")
        response = _request("/models" + suffix)
        for item in response.get("models", []):
            if isinstance(item, dict) and _eligible(item):
                model_id = item["name"].removeprefix("models/")
                models.append(
                    {
                        "id": model_id,
                        "name": item.get("displayName") or model_id,
                        "inputTokenLimit": item.get("inputTokenLimit"),
                        "outputTokenLimit": item.get("outputTokenLimit"),
                    }
                )
        page_token = response.get("nextPageToken")
        if not isinstance(page_token, str) or not page_token:
            break
    unique = {item["id"]: item for item in models}
    ordered = sorted(unique.values(), key=lambda item: (_priority(item["id"]), item["id"]))
    _model_cache = (now, ordered)
    return ordered


def gemini_status() -> dict[str, Any]:
    if not _api_key():
        return {
            "available": False,
            "keyConfigured": False,
            "models": [],
            "defaultModel": AUTO_MODEL,
            "message": "Chưa cấu hình GEMINI_API_KEY. Bộ chọn SQL vẫn hoạt động độc lập.",
        }
    try:
        models = list_text_models()
        return {
            "available": bool(models),
            "keyConfigured": True,
            "models": models,
            "defaultModel": AUTO_MODEL,
            "message": (
                f"Gemini API sẵn sàng · {len(models)} model text có fallback."
                if models
                else "Key hợp lệ nhưng không có model text được chọn từ hạn mức hiện tại."
            ),
        }
    except (GeminiAPIError, RuntimeError, ValueError) as exc:
        return {
            "available": False,
            "keyConfigured": True,
            "models": [],
            "defaultModel": AUTO_MODEL,
            "message": f"Chưa dùng được Gemini API: {str(exc)[:240]}",
        }


def _json_content(response: dict[str, Any]) -> dict[str, Any]:
    candidates = response.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("Gemini không trả kết quả; câu hỏi có thể bị chặn bởi safety filter.")
    try:
        parts = candidates[0]["content"]["parts"]
        value = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    except (KeyError, TypeError):
        raise RuntimeError("Gemini trả kết quả không đúng cấu trúc text.") from None
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", value.strip(), flags=re.IGNORECASE)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Gemini chưa tạo được bộ lọc JSON hợp lệ. Hãy hỏi ngắn và nêu rõ chỉ tiêu.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Gemini chưa tạo được đặc tả truy vấn hợp lệ.")
    return parsed


def _prompt(meta: dict[str, Any]) -> str:
    domain = {
        "aggregate": ["SUM", "AVG"],
        "measures": ["Sales", "BudgetSales", "Gap", "Profit", "BudgetProfit", "COGS", "BudgetCOGS", "Margin", "BudgetMargin", "Marketing", "TotalExpenses"],
        "groupBy": ["MonthStart", "Market", "State", "ProductType", "ProductName"],
        "years": sorted({int(month[:4]) for month in meta["months"]}),
        "months": list(range(1, 13)),
        "markets": meta["markets"],
        "products": meta["products"],
    }
    return (
        "Bạn chỉ ánh xạ câu hỏi sang JSON cho kho Coffee. Không viết SQL, không giải thích, không Markdown. "
        "JSON phải có đúng 7 trường: aggregate, measures, groupBy, year, month, markets, products. "
        "measures là mảng 1-4 giá trị; groupBy tối đa 3; markets/products là mảng và dùng [] nếu không lọc; "
        "year/month dùng null nếu không nêu. Dùng AVG khi người dùng nói trung bình, còn lại mặc định SUM. "
        f"Chỉ dùng miền sau: {json.dumps(domain, ensure_ascii=False)}"
    )


def _response_schema(meta: dict[str, Any]) -> dict[str, Any]:
    measures = ["Sales", "BudgetSales", "Gap", "Profit", "BudgetProfit", "COGS", "BudgetCOGS", "Margin", "BudgetMargin", "Marketing", "TotalExpenses"]
    dimensions = ["MonthStart", "Market", "State", "ProductType", "ProductName"]
    years = sorted({int(month[:4]) for month in meta["months"]})
    return {
        "type": "object",
        "properties": {
            "aggregate": {"type": "string", "enum": ["SUM", "AVG"]},
            "measures": {
                "type": "array",
                "minItems": 1,
                "maxItems": 4,
                "uniqueItems": True,
                "items": {"type": "string", "enum": measures},
            },
            "groupBy": {
                "type": "array",
                "maxItems": 3,
                "uniqueItems": True,
                "items": {"type": "string", "enum": dimensions},
            },
            "year": {"anyOf": [{"type": "integer", "enum": years}, {"type": "null"}]},
            "month": {"anyOf": [{"type": "integer", "minimum": 1, "maximum": 12}, {"type": "null"}]},
            "markets": {
                "type": "array",
                "uniqueItems": True,
                "items": {"type": "string", "enum": meta["markets"]},
            },
            "products": {
                "type": "array",
                "uniqueItems": True,
                "items": {"type": "string", "enum": meta["products"]},
            },
        },
        "required": ["aggregate", "measures", "groupBy", "year", "month", "markets", "products"],
        "additionalProperties": False,
    }


def _generate(model_id: str, question: str, meta: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "systemInstruction": {"parts": [{"text": _prompt(meta)}]},
        "contents": [{"role": "user", "parts": [{"text": question}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 800,
            "responseMimeType": "application/json",
            "responseJsonSchema": _response_schema(meta),
        },
    }
    return _json_content(_request(f"/models/{model_id}:generateContent", payload, timeout=35))


def _sql_prompt(meta: dict[str, Any], backend: str) -> str:
    years = sorted({int(month[:4]) for month in meta["months"]})
    table = "mart.vw_Detail" if backend == "sqlserver" else "vw_Detail"
    dialect = "Microsoft SQL Server T-SQL" if backend == "sqlserver" else "SQLite"
    columns = [
        "MonthStart", "DateKey", "AreaCode", "State", "Market", "MarketSize",
        "ProductName", "ProductLine", "ProductType", "Type", "Sales", "BudgetSales",
        "Profit", "BudgetProfit", "COGS", "BudgetCOGS", "Margin", "BudgetMargin",
        "Marketing", "Inventory", "TotalExpenses", "SourceRow", "BatchID",
    ]
    return (
        f"Bạn là bộ lập kế hoạch SQL cho kho Coffee, dialect {dialect}. Chỉ trả JSON theo schema. "
        f"Chỉ được đọc đúng một view {table}; cột hợp lệ: {columns}. Dữ liệu chỉ có năm {years}; "
        f"Market: {meta['markets']}; ProductName: {meta['products']}. Grain là tháng × AreaCode × sản phẩm, "
        "không phải đơn hàng. Viết đúng một SELECT hoặc WITH...SELECT, không dấu chấm phẩy, không markdown, "
        "không DDL/DML, không system table, không JOIN nguồn khác. Hỗ trợ SUM, AVG, COUNT, MIN, MAX, "
        "tỷ lệ, CASE, HAVING, top-N, ORDER BY, nhóm theo thời gian/Market/sản phẩm. "
        "BudgetAchievement phải là SUM(Sales)/NULLIF(SUM(BudgetSales),0). ProfitMargin phải là "
        "SUM(Profit)/NULLIF(SUM(Sales),0). Không SUM/AVG Inventory xuyên nhiều tháng; chỉ dùng Inventory "
        "khi lọc đúng một MonthStart. Nếu câu hỏi không thể trả lời từ các cột trên, trả status cannot_answer, "
        "sql rỗng và giải thích ngắn. Không được bỏ qua điều kiện người dùng nêu."
    )


def _sql_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["query", "cannot_answer"]},
            "sql": {"type": "string"},
            "explanation": {"type": "string"},
        },
        "required": ["status", "sql", "explanation"],
        "additionalProperties": False,
    }


def generate_sql_candidate(model_id: str, question: str, meta: dict[str, Any], backend: str) -> dict[str, Any]:
    payload = {
        "systemInstruction": {"parts": [{"text": _sql_prompt(meta, backend)}]},
        "contents": [{"role": "user", "parts": [{"text": question}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 1600,
            "responseMimeType": "application/json",
            "responseJsonSchema": _sql_response_schema(),
        },
    }
    return _json_content(_request(f"/models/{model_id}:generateContent", payload, timeout=40))


def ordered_model_ids(selected: Any = AUTO_MODEL) -> list[str]:
    models = list_text_models()
    if not models:
        raise RuntimeError("Key không có model text phù hợp để chạy truy vấn.")
    available = [item["id"] for item in models]
    selected = AUTO_MODEL if selected in (None, "", AUTO_MODEL) else selected
    if not isinstance(selected, str) or (selected != AUTO_MODEL and selected not in available):
        raise ValueError("Model Gemini không thuộc danh sách key đang sử dụng được.")
    return available if selected == AUTO_MODEL else [selected] + [item for item in available if item != selected]


def question_to_spec(question: Any, meta: dict[str, Any], model: Any = AUTO_MODEL) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Hãy nhập một câu hỏi dữ liệu.")
    question = question.strip()
    if len(question) > 600:
        raise ValueError("Câu hỏi tối đa 600 ký tự.")

    candidates = ordered_model_ids(model)

    attempts: list[dict[str, str]] = []
    for model_id in candidates:
        try:
            return _generate(model_id, question, meta), model_id, attempts
        except GeminiAPIError as exc:
            attempts.append({"model": model_id, "reason": f"HTTP {exc.code} · {exc.status}"})
            if exc.code not in FALLBACK_HTTP_CODES:
                raise RuntimeError(f"Gemini từ chối xác thực hoặc quyền truy cập: {exc.status}.") from None
        except RuntimeError as exc:
            attempts.append({"model": model_id, "reason": str(exc)[:120]})
    tried = ", ".join(item["model"] for item in attempts)
    raise RuntimeError(f"Tất cả model Gemini fallback đều chưa chạy được: {tried}.")
