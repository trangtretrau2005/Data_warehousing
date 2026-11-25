"""Business-contract checks for the separate read-only cube application."""

import hashlib
import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

import numpy as np
import pandas as pd
import pytest

from apps.cube_explorer import ai_sql, data, gemini, query, server
from coffee_dw.warehouse import load


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    path = tmp_path_factory.mktemp("cube") / "reference.sqlite"
    load(db_path=path)
    return path


def test_cube_reads_named_marts_without_changing_database(warehouse):
    checksum_before = hashlib.sha256(warehouse.read_bytes()).hexdigest()
    market, product = data.load_cube(db_path=warehouse)
    assert len(market) == 96 and len(product) == 1008
    assert market.MonthStart.nunique() == 24
    assert not product.duplicated(["MonthStart", "Market", "ProductName"]).any()
    assert market.Sales.sum() == 819811
    assert market.BudgetSales.sum() == 746160
    assert market.Profit.sum() == 259543
    selected = market.loc[market.MonthStart.eq("2013-08-01") & market.Market.eq("South")].iloc[0]
    assert (selected.Sales, selected.BudgetSales, selected.Gap) == (4601, 4610, -9)
    rows = product.loc[product.MonthStart.eq("2013-08-01") & product.Market.eq("South")]
    assert rows.set_index("ProductName").loc["Colombian", "Gap"] == -268
    states = data.load_state_drill(pd.Timestamp("2013-08-01"), "South", "Colombian", db_path=warehouse)
    assert states.Gap.sum() == -268
    assert states.Sales.sum() == rows.set_index("ProductName").loc["Colombian", "Sales"]
    assert hashlib.sha256(warehouse.read_bytes()).hexdigest() == checksum_before
    store = server.CubeStore(db_path=warehouse)
    assert store.linear_payload["meta"]["grain"] == "MonthStart × Market"
    assert len(store.linear_payload["markets"]) == 4
    assert all(model["n"] == 24 for model in store.linear_payload["markets"])


def test_quarter_drilldown_reconciles_every_level(warehouse):
    market, product = data.load_cube(db_path=warehouse)
    product_types = data.load_product_types(db_path=warehouse)
    market["Quarter"] = market.MonthStart.dt.to_period("Q").astype(str)
    product["Quarter"] = product.MonthStart.dt.to_period("Q").astype(str)
    product["ProductType"] = product.ProductName.map(product_types)

    market_quarter = market.groupby(["Market", "Quarter"])[["Sales", "BudgetSales", "Gap"]].sum()
    product_quarter = product.groupby(["Market", "Quarter"])[["Sales", "BudgetSales", "Gap"]].sum()
    pd.testing.assert_frame_equal(market_quarter, product_quarter, check_dtype=False)
    assert len(market_quarter) == 32

    south = product.loc[product.Market.eq("South") & product.Quarter.eq("2013Q3")]
    quarter = south[["Sales", "BudgetSales", "Gap"]].sum()
    assert tuple(quarter) == (13554, 13180, 374)
    assert south.groupby("MonthStart").Gap.sum().tolist() == [16, -9, 367]

    august = south.loc[south.MonthStart.eq("2013-08-01")]
    by_type = august.groupby("ProductType").Gap.sum().to_dict()
    assert by_type == {"Coffee": -373, "Espresso": 316, "Herbal Tea": 48}
    coffee = august.loc[august.ProductType.eq("Coffee")].set_index("ProductName")
    assert coffee.Gap.to_dict() == {"Colombian": -268, "Decaf Irish Cream": -105}


def test_safe_query_builder_sum_avg_and_gap(warehouse):
    store = server.CubeStore(db_path=warehouse)
    summed = query.execute_query(
        {
            "aggregate": "SUM",
            "measures": ["Sales", "BudgetSales", "Gap"],
            "groupBy": ["Market"],
            "year": 2013,
            "month": None,
            "markets": [],
            "products": [],
        },
        store.meta,
        db_path=warehouse,
    )
    assert summed["rowCount"] == 4
    assert summed["params"] == ["2013-01-01", "2014-01-01"]
    assert "SUM([Sales]) - SUM([BudgetSales]) AS [SUM_Gap]" in summed["sql"]
    assert all(row["SUM_Gap"] == row["SUM_Sales"] - row["SUM_BudgetSales"] for row in summed["rows"])
    assert summed["cubeContext"] == {
        "year": "2013",
        "month": None,
        "market": None,
        "product": None,
        "products": [],
        "measure": "Sales",
        "mode": "all",
        "note": "Phạm vi lấy trực tiếp từ bộ lọc truy vấn.",
    }

    averaged = query.execute_query(
        {
            "aggregate": "AVG",
            "measures": ["Marketing"],
            "groupBy": ["Market"],
            "year": None,
            "month": None,
            "markets": [],
            "products": [],
        },
        store.meta,
        db_path=warehouse,
    )
    expected = data._read_sqlite(
        "SELECT Market, AVG(Marketing) AS value FROM vw_Detail GROUP BY Market ORDER BY Market",
        warehouse,
    )
    assert [row["Market"] for row in averaged["rows"]] == expected.Market.tolist()
    assert np.allclose([row["AVG_Marketing"] for row in averaged["rows"]], expected.value)


def test_query_result_carries_exact_cube_slice(warehouse):
    store = server.CubeStore(db_path=warehouse)
    result = query.execute_query(
        {
            "aggregate": "SUM",
            "measures": ["Profit"],
            "groupBy": [],
            "year": 2013,
            "month": 8,
            "markets": ["South"],
            "products": ["Colombian"],
        },
        store.meta,
        db_path=warehouse,
    )
    assert result["cubeContext"] == {
        "year": "2013",
        "month": "2013-08-01",
        "market": "South",
        "product": "Colombian",
        "products": ["Colombian"],
        "measure": "Profit",
        "mode": "slice",
        "note": "Phạm vi lấy trực tiếp từ bộ lọc truy vấn.",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("measures", ["Inventory"]),
        ("measures", ["Sales); DROP TABLE FactSalesPerformance;--"]),
        ("groupBy", ["Market; DELETE FROM FactSalesPerformance"]),
        ("markets", ["South' OR 1=1 --"]),
    ],
)
def test_query_spec_rejects_inventory_and_unlisted_values(warehouse, field, value):
    store = server.CubeStore(db_path=warehouse)
    spec = {
        "aggregate": "SUM",
        "measures": ["Sales"],
        "groupBy": ["Market"],
        "year": None,
        "month": None,
        "markets": [],
        "products": [],
    }
    spec[field] = value
    with pytest.raises(ValueError):
        query.normalize_spec(spec, store.meta)


def test_gemini_falls_back_after_model_quota_without_generating_sql(monkeypatch):
    meta = {"months": ["2012-01-01", "2013-12-01"], "markets": ["South"], "products": ["Colombian"]}
    monkeypatch.setattr(
        gemini,
        "list_text_models",
        lambda: [
            {"id": "gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash Lite"},
            {"id": "gemini-3.1-flash-lite", "name": "Gemini 3.1 Flash Lite"},
        ],
    )
    calls = []

    def generate(model, question, metadata):
        calls.append(model)
        if len(calls) == 1:
            raise gemini.GeminiAPIError(429, "RESOURCE_EXHAUSTED", "quota")
        return {
            "aggregate": "AVG",
            "measures": ["Marketing"],
            "groupBy": ["Market"],
            "year": None,
            "month": None,
            "markets": [],
            "products": [],
        }

    monkeypatch.setattr(gemini, "_generate", generate)
    spec, model, attempts = gemini.question_to_spec("Marketing trung bình theo thị trường", meta)
    assert model == "gemini-3.1-flash-lite"
    assert calls == ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
    assert attempts == [{"model": "gemini-3.5-flash-lite", "reason": "HTTP 429 · RESOURCE_EXHAUSTED"}]
    assert spec["aggregate"] == "AVG" and spec["measures"] == ["Marketing"]
    assert "sql" not in spec


def test_gemini_model_filter_excludes_agents_and_non_text_models():
    assert gemini._eligible(
        {"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]}
    )
    for name in (
        "deep-research-pro-preview",
        "gemini-3.1-flash-image",
        "gemini-3.1-flash-lite-image",
        "gemini-3.8-flash-lite-tts",
        "gemini-3.1-pro",
        "gemini-embedding-2",
    ):
        assert not gemini._eligible({"name": f"models/{name}", "supportedGenerationMethods": ["generateContent"]})
    schema = gemini._response_schema(
        {"months": ["2012-01-01", "2013-12-01"], "markets": ["South"], "products": ["Colombian"]}
    )
    assert schema["properties"]["aggregate"] == {"type": "string", "enum": ["SUM", "AVG"]}
    assert schema["additionalProperties"] is False


def test_ai_sql_rejects_year_outside_snapshot_before_generation(warehouse, monkeypatch):
    store = server.CubeStore(db_path=warehouse)
    called = False

    def should_not_generate(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("Gemini must not be called for an impossible year")

    monkeypatch.setattr(ai_sql, "generate_sql_candidate", should_not_generate)
    with pytest.raises(ai_sql.QuestionScopeError, match="không có dữ liệu năm 2015"):
        ai_sql.answer_question("Tổng lợi nhuận năm 2015", store.meta, "sqlite", warehouse)
    assert not called


def test_ai_sql_executes_valid_select_and_limits_rows(warehouse):
    result = ai_sql.execute_select(
        "SELECT Market, SUM(Profit) AS TotalProfit FROM vw_Detail "
        "WHERE MonthStart >= '2013-01-01' AND MonthStart < '2014-01-01' "
        "GROUP BY Market ORDER BY TotalProfit DESC",
        "sqlite",
        warehouse,
    )
    assert result["mode"] == "ai_sql"
    assert result["rowCount"] == 4
    assert sum(row["TotalProfit"] for row in result["rows"]) == pytest.approx(153717)
    assert "LIMIT 201" not in result["sql"]
    assert "LIMIT 201" in result["executionSql"]


def test_ai_sql_cube_context_uses_question_and_explicitly_labels_result_focus(warehouse):
    store = server.CubeStore(db_path=warehouse)
    scalar = {"rowCount": 1, "columns": ["TotalSales"], "rows": [{"TotalSales": 1}]}
    year_only = ai_sql.cube_context("Tổng Sales năm 2013", scalar, store.meta)
    assert year_only == {
        "year": "2013",
        "month": None,
        "market": None,
        "product": None,
        "products": [],
        "measure": "Sales",
        "mode": "all",
        "note": "Phạm vi lấy từ câu hỏi.",
        "rollup": None,
    }

    exact = ai_sql.cube_context("Profit tháng 8 năm 2013 của South và Colombian", scalar, store.meta)
    assert exact["month"] == "2013-08-01"
    assert exact["market"] == "South"
    assert exact["product"] == "Colombian"
    assert exact["measure"] == "Profit"
    assert exact["mode"] == "slice"
    assert ai_sql.cube_context("BudgetSales năm 2013", scalar, store.meta)["measure"] == "BudgetSales"

    ranking = {
        "rowCount": 2,
        "columns": ["ProductName", "TotalSales"],
        "rows": [
            {"ProductName": "Colombian", "TotalSales": 100},
            {"ProductName": "Caffe Mocha", "TotalSales": 90},
        ],
    }
    focused = ai_sql.cube_context("2 sản phẩm Sales cao nhất năm 2013", ranking, store.meta)
    assert focused["product"] is None
    assert focused["products"] == ["Colombian", "Caffe Mocha"]
    assert "đủ 2 sản phẩm" in focused["note"]

    count_by_market = {
        "rowCount": 4,
        "truncated": False,
        "columns": ["Market", "RecordCount"],
        "rows": [
            {"Market": "East", "RecordCount": 444},
            {"Market": "South", "RecordCount": 336},
            {"Market": "West", "RecordCount": 672},
            {"Market": "Central", "RecordCount": 672},
        ],
    }
    rolled = ai_sql.cube_context("Đếm số ô dữ liệu theo Market năm 2012", count_by_market, store.meta)
    assert rolled["rollup"] == {
        "dimension": "Market",
        "metric": "RecordCount",
        "title": "RecordCount theo Market",
        "items": [
            {"label": "East", "value": 444},
            {"label": "South", "value": 336},
            {"label": "West", "value": 672},
            {"label": "Central", "value": 672},
        ],
    }
    assert "đúng 4 ô" in rolled["note"]


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE vw_Detail",
        "SELECT * FROM vw_Detail; DROP TABLE FactSalesPerformance",
        "SELECT * FROM sqlite_master",
        "SELECT SecretColumn FROM vw_Detail",
        "SELECT CURRENT_USER FROM vw_Detail",
        "SELECT * FROM vw_Detail a JOIN vw_Detail b ON 1=1",
        "SELECT SUM(Inventory) FROM vw_Detail",
        "SELECT * FROM OPENROWSET('x','y','z')",
    ],
)
def test_ai_sql_ast_rejects_unsafe_or_contract_breaking_queries(sql):
    with pytest.raises(ValueError):
        ai_sql.validate_select(sql, "sqlite")


def test_ai_sql_falls_back_when_first_model_writes_invalid_sql(warehouse, monkeypatch):
    store = server.CubeStore(db_path=warehouse)
    monkeypatch.setattr(ai_sql, "ordered_model_ids", lambda selected: ["first", "second"])

    def candidate(model, question, meta, backend):
        if model == "first":
            return {"status": "query", "sql": "SELECT CURRENT_USER FROM vw_Detail", "explanation": "bad"}
        return {
            "status": "query",
            "sql": "SELECT SUM(Profit) AS TotalProfit FROM vw_Detail WHERE MonthStart >= '2013-01-01' AND MonthStart < '2014-01-01'",
            "explanation": "Lợi nhuận năm 2013.",
        }

    monkeypatch.setattr(ai_sql, "generate_sql_candidate", candidate)
    result = ai_sql.answer_question("Tổng lợi nhuận năm 2013", store.meta, "sqlite", warehouse)
    assert result["ai"]["model"] == "second"
    assert len(result["ai"]["fallbackAttempts"]) == 1
    assert result["rows"] == [{"TotalProfit": 153717.0}]


def test_sqlite_adapter_refuses_writes_and_missing_file(warehouse, tmp_path):
    with pytest.raises(Exception, match="readonly|read-only"):
        data._read_sqlite("DELETE FROM FactSalesPerformance", warehouse)
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(FileNotFoundError, match="Chưa có kho"):
        data.load_cube(db_path=missing)
    assert not missing.exists()


def _one_cell(budget=100, sales=90):
    row = {"MonthStart": "2013-08-01", "Market": "South", "Sales": sales, "BudgetSales": budget, "Profit": -5, "Gap": sales - budget}
    market = pd.DataFrame([{**row, "BudgetAchievement": sales / budget if budget else None}])
    product = pd.DataFrame([{**row, "ProductName": "Colombian"}])
    return market, product


def test_zero_budget_ratio_stays_missing_and_negative_profit_preserved():
    market, product = _one_cell(budget=0)
    data.validate_marts(market, product)
    assert pd.isna(market.BudgetAchievement.iloc[0])
    assert product.Profit.iloc[0] == -5
    market.BudgetAchievement = 0
    with pytest.raises(ValueError, match="bằng 0 phải để thiếu"):
        data.validate_marts(market, product)


@pytest.mark.parametrize("corruption", ["duplicate", "missing_group", "bad_gap", "bad_ratio", "infinite", "missing_key", "midmonth"])
def test_incoherent_marts_are_rejected(corruption):
    market, product = _one_cell()
    if corruption == "duplicate":
        product = pd.concat([product, product])
    elif corruption == "missing_group":
        product.Market = "West"
    elif corruption == "bad_gap":
        product.Gap += 1
    elif corruption == "bad_ratio":
        market.BudgetAchievement = .4
    elif corruption == "infinite":
        product.Sales = np.inf
    elif corruption == "missing_key":
        product.ProductName = None
    else:
        product.MonthStart = "2013-08-02"
    with pytest.raises(ValueError):
        data.validate_marts(market, product)


def test_drill_parameters_cannot_turn_into_sql(warehouse):
    rows = data.load_state_drill(pd.Timestamp("2013-08-01"), "South' OR 1=1 --", "Colombian", db_path=warehouse)
    assert rows.empty
    with pytest.raises(ValueError, match="đầu tháng"):
        data.load_state_drill(pd.Timestamp("2013-08-15"), "South", "Colombian", db_path=warehouse)


def test_http_payload_and_traversal_protection(warehouse, tmp_path):
    store = server.CubeStore(db_path=warehouse)
    (tmp_path / "index.html").write_text("<h1>Cube</h1>", encoding="utf-8")
    (tmp_path / "server.py").write_text("not public", encoding="utf-8")
    http = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(store, tmp_path))
    worker = Thread(target=http.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{http.server_port}"
    try:
        payload = json.load(urlopen(base + "/api/data"))
        assert payload["meta"]["productTypes"]["Colombian"] == "Coffee"
        assert payload["meta"]["totals"]["Sales"] == 819811
        assert payload["productPeriod"][0]["MonthStart"] == "2012-01-01"
        assert len(payload["productPeriod"]) == 1008
        assert json.load(urlopen(base + "/api/health"))["status"] == "ok"
        linear = json.load(urlopen(base + "/api/linear"))
        assert linear["meta"]["grain"] == "MonthStart × Market"
        assert len(linear["markets"]) == 4
        assert all(model["testN"] == 6 for model in linear["markets"])
        drill = json.load(urlopen(base + "/api/drill?month=2013-08-01&market=South&product=Colombian"))
        assert sum(row["Gap"] for row in drill["rows"]) == -268
        query_body = {
            "aggregate": "SUM",
            "measures": ["Sales", "Gap"],
            "groupBy": ["Market"],
            "year": 2013,
            "month": None,
            "markets": ["South"],
            "products": [],
        }
        request = Request(
            base + "/api/query",
            data=json.dumps(query_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        query_result = json.load(urlopen(request))
        assert query_result["rowCount"] == 1
        assert query_result["rows"][0]["Market"] == "South"
        assert query_result["sql"].count("?") == len(query_result["params"]) == 3
        assert urlopen(base + "/").read() == b"<h1>Cube</h1>"
        for path in ("/server.py", "/%2e%2e/README.md", "/vendor/%2e%2e/server.py"):
            with pytest.raises(HTTPError) as error:
                urlopen(base + path)
            assert error.value.code == 404
        with pytest.raises(HTTPError) as error:
            urlopen(base + "/api/drill?month=2013-08-01&market=South&product=invalid")
        assert error.value.code == 400
    finally:
        http.shutdown()
        http.server_close()
        worker.join(timeout=3)


def test_state_readback_detects_snapshot_drift(warehouse, monkeypatch):
    store = server.CubeStore(db_path=warehouse)
    rows = data.load_state_drill(pd.Timestamp("2013-08-01"), "South", "Colombian", db_path=warehouse)
    rows.loc[rows.index[0], "Sales"] += 1
    monkeypatch.setattr(server, "load_state_drill", lambda *args, **kwargs: rows)
    with pytest.raises(RuntimeError, match="không khớp snapshot"):
        store.drill("2013-08-01", "South", "Colombian")
