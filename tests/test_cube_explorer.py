"""Business-contract checks for the separate read-only cube application."""

import hashlib
import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen
from http.server import ThreadingHTTPServer

import numpy as np
import pandas as pd
import pytest

from apps.cube_explorer import data, server
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
        drill = json.load(urlopen(base + "/api/drill?month=2013-08-01&market=South&product=Colombian"))
        assert sum(row["Gap"] for row in drill["rows"]) == -268
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
