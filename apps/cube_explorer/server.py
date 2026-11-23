"""Local, read-only HTTP host for the independent Coffee Datacube application."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, unquote, urlsplit

import numpy as np
import pandas as pd

try:
    from .ai_sql import answer_question
    from .data import MEASURES, load_cube, load_product_types, load_state_drill
    from .gemini import gemini_status
    from .query import execute_query, query_config
except ImportError:  # `python apps/cube_explorer/server.py`
    from ai_sql import answer_question
    from data import MEASURES, load_cube, load_product_types, load_state_drill
    from gemini import gemini_status
    from query import execute_query, query_config

from coffee_dw.config import DB_PATH, RESULTS_DIR
from coffee_dw.linear_marketing import build_linear_analysis

STATIC_ROOT = Path(__file__).resolve().parent
STATIC_FILES = {
    "index.html",
    "styles.css",
    "app.js",
    "cube.js",
    "favicon.ico",
    "an-south.wav",
    "triage.html",
    "triage.json",
    "quarter.html",
    "quarter.js",
    "quarter.css",
    "query.html",
    "query.js",
    "query.css",
    "linear.html",
    "linear.js",
    "linear.css",
}


def records(frame: pd.DataFrame) -> list[dict]:
    """Serialize timestamps, NumPy values and nullable ratios as strict JSON."""
    return json.loads(frame.to_json(orient="records", date_format="iso", date_unit="s").replace("T00:00:00", ""))


def published_forecasts() -> list[dict]:
    """Read the optional forecast publication without training in the UI."""
    folder = RESULTS_DIR / "forecast"
    try:
        future = pd.read_csv(folder / "next_month.csv")
        metrics = pd.read_csv(folder / "metrics.csv")
        test = metrics.loc[metrics["Split"].eq("test"), ["Market", "ModelName", "N", "MAE"]]
        joined = future.loc[future["Split"].eq("future")].merge(test, on=["Market", "ModelName"], validate="one_to_one")
        fields = ["Market", "ForecastMonth", "IssueMonth", "ModelName", "ModelVersion", "Prediction", "N", "MAE"]
        return records(joined[fields].dropna())
    except (OSError, ValueError, KeyError):
        return []


class CubeStore:
    """A validated mart snapshot for one local presentation session."""

    def __init__(self, backend: str = "sqlite", db_path: str | Path = DB_PATH, database: str | None = None):
        self.backend = backend
        self.db_path = Path(db_path)
        self.market_period, self.product_period = load_cube(backend, self.db_path)
        types = load_product_types(backend, self.db_path)
        missing = set(self.product_period["ProductName"]) - set(types)
        if missing:
            raise ValueError("DimProduct không đủ sản phẩm đang có trong mart.")
        self.meta = {
            "backend": backend,
            "sourceLabel": "SQL Server · mart Chi" if backend == "sqlserver" else "SQLite · bản tham chiếu",
            "database": database if backend == "sqlserver" else self.db_path.name,
            "loadedAt": datetime.now(timezone.utc).isoformat(),
            "months": sorted(self.market_period["MonthStart"].dt.strftime("%Y-%m-%d").unique().tolist()),
            "markets": sorted(self.market_period["Market"].unique().tolist()),
            "products": sorted(self.product_period["ProductName"].unique().tolist()),
            "productTypes": types,
            "grain": "MonthStart × Market × ProductName",
            "marketRows": len(self.market_period),
            "productRows": len(self.product_period),
            "totals": {column: float(self.market_period[column].sum()) for column in MEASURES},
            "views": ["mart.vw_MarketPeriod", "mart.vw_MarketProductPeriod", "mart.vw_Detail"] if backend == "sqlserver" else ["vw_MarketPeriod", "vw_MarketProductPeriod", "vw_Detail"],
            "reconciliation": "passed",
        }
        self.payload = {
            "meta": self.meta,
            "publishedForecasts": published_forecasts(),
            "marketPeriod": records(self.market_period),
            "productPeriod": records(self.product_period),
        }
        linear_result = execute_query(
            {
                "aggregate": "SUM",
                "measures": ["Marketing", "Sales"],
                "groupBy": ["MonthStart", "Market"],
                "year": None,
                "month": None,
                "markets": [],
                "products": [],
            },
            self.meta,
            self.backend,
            self.db_path,
        )
        if linear_result["truncated"] or linear_result["rowCount"] != len(self.market_period):
            raise ValueError("Bảng Marketing–Sales không khớp số ô Market–tháng của mart.")
        linear_monthly = pd.DataFrame(linear_result["rows"]).rename(
            columns={"SUM_Marketing": "Marketing", "SUM_Sales": "Sales"}
        )
        self.linear_payload = build_linear_analysis(linear_monthly)
        self.linear_payload["meta"]["sourceLabel"] = self.meta["sourceLabel"]

    def drill(self, month: str, market: str, product: str) -> dict:
        if month not in self.meta["months"] or market not in self.meta["markets"] or product not in self.meta["products"]:
            raise ValueError("Lát cắt không thuộc các giá trị của khối dữ liệu.")
        rows = load_state_drill(pd.Timestamp(month), market, product, self.backend, self.db_path)
        selected = self.product_period.loc[
            self.product_period["MonthStart"].eq(pd.Timestamp(month))
            & self.product_period["Market"].eq(market)
            & self.product_period["ProductName"].eq(product)
        ]
        if selected.empty:
            if not rows.empty:
                raise RuntimeError("Kho đã đổi sau khi mở ứng dụng. Khởi động lại để đọc một snapshot mới.")
        elif rows.empty or not np.allclose(
            rows[list(MEASURES)].sum().to_numpy(dtype=float),
            selected[list(MEASURES)].iloc[0].to_numpy(dtype=float),
            rtol=0,
            atol=1e-7,
        ):
            raise RuntimeError("Drill-down không khớp snapshot mart. Khởi động lại ứng dụng và kiểm tra nguồn.")
        return {"rows": records(rows), "month": month, "market": market, "product": product, "reconciliation": "passed"}


def make_handler(store: CubeStore, static_root: Path = STATIC_ROOT):
    static_root = static_root.resolve()

    class CubeHandler(BaseHTTPRequestHandler):
        server_version = "CoffeeCube/1.0"

        def log_message(self, format: str, *args) -> None:
            # Do not write request values or connection strings into logs.
            pass

        def _send(self, code: int, content: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(content)

        def _json(self, code: int, data: dict) -> None:
            self._send(code, json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8"), "application/json; charset=utf-8")

        def _read_json(self) -> dict:
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Yêu cầu phải dùng Content-Type application/json.")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ValueError("Content-Length không hợp lệ.") from None
            if length <= 0 or length > 16_384:
                raise ValueError("Nội dung yêu cầu phải từ 1 byte đến 16 KB.")
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ValueError("Nội dung JSON không hợp lệ.") from None
            if not isinstance(body, dict):
                raise ValueError("Nội dung JSON phải là một object.")
            return body

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            if path == "/api/health":
                self._json(200, {"status": "ok", "backend": store.backend, "reconciliation": "passed"})
                return
            if path == "/api/data":
                self._json(200, store.payload)
                return
            if path == "/api/query/config":
                self._json(200, {"config": query_config(store.meta), "source": store.meta["sourceLabel"]})
                return
            if path == "/api/ai/status":
                self._json(200, gemini_status())
                return
            if path == "/api/linear":
                self._json(200, store.linear_payload)
                return
            if path == "/api/drill":
                params = parse_qs(parsed.query, keep_blank_values=True)
                try:
                    if set(params) != {"month", "market", "product"} or any(len(value) != 1 for value in params.values()):
                        raise ValueError("Cần đúng một month, market và product.")
                    self._json(200, store.drill(params["month"][0], params["market"][0], params["product"][0]))
                except ValueError as exc:
                    self._json(400, {"error": str(exc)})
                except Exception:
                    self._json(503, {"error": "Chưa đọc được drill-down nhất quán. Kiểm tra nguồn và khởi động lại ứng dụng."})
                return
            relative = path.lstrip("/") or "index.html"
            # Restrict the static surface to this app, rather than expose data.py,
            # server.py or files elsewhere in the user's repository.
            target = (static_root / relative).resolve()
            allowed = relative in STATIC_FILES or (relative.startswith("vendor/") and target.suffix in {".js", ".css", ".txt", ".woff2"})
            if not allowed or not target.is_relative_to(static_root) or not target.is_file():
                self._json(404, {"error": "Không tìm thấy tài nguyên."})
                return
            content_type = {".js": "text/javascript", ".css": "text/css", ".html": "text/html"}.get(target.suffix, mimetypes.guess_type(str(target))[0] or "application/octet-stream")
            self._send(200, target.read_bytes(), content_type + ("; charset=utf-8" if target.suffix in {".js", ".css", ".html", ".txt"} else ""))

        def do_POST(self) -> None:
            path = unquote(urlsplit(self.path).path)
            try:
                body = self._read_json()
                if path == "/api/query":
                    result = execute_query(body, store.meta, store.backend, store.db_path)
                    self._json(200, result)
                    return
                if path == "/api/ai/query":
                    if set(body) - {"question", "model"}:
                        raise ValueError("Yêu cầu Gemini chứa trường không được hỗ trợ.")
                    result = answer_question(
                        body.get("question"), store.meta, store.backend, store.db_path, body.get("model")
                    )
                    self._json(200, result)
                    return
                self._json(404, {"error": "Không tìm thấy API."})
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
            except RuntimeError as exc:
                self._json(503, {"error": str(exc)})
            except Exception:
                self._json(503, {"error": "Chưa chạy được truy vấn trên mart. Kiểm tra nguồn dữ liệu rồi thử lại."})

    return CubeHandler


def main(argv: list[str] | None = None) -> int:
    # PowerShell/redirected consoles can inherit a cp949 codepage even on a
    # Vietnamese workstation. Keep CLI help and diagnostics reproducible.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Mở riêng ứng dụng phân tích Coffee Datacube; không ghi kho hoặc gọi dự báo.")
    parser.add_argument("--host", choices=("127.0.0.1", "localhost"), default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8503)
    parser.add_argument("--backend", choices=("sqlite", "sqlserver"), default=os.getenv("COFFEE_DW_BACKEND", "sqlite"))
    parser.add_argument("--db", type=Path, default=DB_PATH, help="Đường dẫn kho SQLite có sẵn.")
    parser.add_argument("--database", help="Tên SQL Server database local, dùng Windows authentication.")
    args = parser.parse_args(argv)
    if not 0 < args.port < 65536:
        parser.error("Port phải nằm trong 1–65535.")
    if args.database:
        if args.backend != "sqlserver" or not re.fullmatch(r"[A-Za-z0-9_]+", args.database):
            parser.error("--database cần --backend sqlserver và tên database gồm chữ, số, dấu gạch dưới.")
        if os.getenv("COFFEE_DW_SQLSERVER_CONNECTION"):
            parser.error("Đã có COFFEE_DW_SQLSERVER_CONNECTION; bỏ --database để dùng kết nối hiện có.")
        os.environ["COFFEE_DW_SQLSERVER_CONNECTION"] = (
            "DRIVER={ODBC Driver 18 for SQL Server};SERVER=.;"
            f"DATABASE={args.database};Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes"
        )
    try:
        store = CubeStore(args.backend, args.db, args.database)
        server = ThreadingHTTPServer((args.host, args.port), make_handler(store))
    except Exception:
        print("Cannot start Coffee Datacube: check the selected database, mart schema, data reconciliation and local port.", file=sys.stderr)
        return 1
    print(f"Coffee Datacube: http://{args.host}:{args.port}", flush=True)
    print(f"Read-only backend: {args.backend}; {len(store.market_period)} market cells / {len(store.product_period)} product cells; reconciliation PASS", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
