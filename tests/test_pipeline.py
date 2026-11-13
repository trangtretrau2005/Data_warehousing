"""Tests target data correctness, replay safety and error isolation."""

import sqlite3

import pandas as pd
import pytest

from coffee_dw.config import SOURCE_PATH
from coffee_dw.source import MEASURES, profile, read_source
from coffee_dw.warehouse import load, read_detail


def test_full_source_profile_and_star_roundtrip(tmp_path):
    result = profile()
    assert result["source_rows"] == 4248
    assert (result["months"], result["markets"], result["locations"], result["products"]) == (24, 4, 156, 13)
    assert result["warnings"] == {"negative_profit": 528, "negative_inventory": 88,
                                  "sales_not_cogs_plus_margin": 2088,
                                  "profit_not_margin_minus_expenses": 2105}
    db = tmp_path / "dw.sqlite"
    first = load(db_path=db)
    assert (first["inserted_rows"], first["warehouse_sales"]) == (4248, 819811)
    second = load(db_path=db)
    assert second["status"] == "skipped"
    assert second["warehouse_rows"] == 4248
    detail = read_detail(db)
    source, _ = read_source()
    pd.testing.assert_frame_equal(
        detail.groupby(["MonthStart", "Market", "ProductName"])[MEASURES].sum(),
        source.groupby(["MonthStart", "Market", "ProductName"])[MEASURES].sum(),
        check_dtype=False)
    central = detail.loc[detail.MonthStart.eq("2012-01-01") & detail.Market.eq("Central")]
    assert (central.Sales.sum(), central.BudgetSales.sum()) == (10346, 9970)


def test_rejected_rows_and_corrected_batch(tmp_path):
    raw = pd.read_csv(SOURCE_PATH).head(8)
    csv = tmp_path / "source.csv"
    db = tmp_path / "dw.sqlite"
    raw.to_csv(csv, index=False)
    assert load(csv, db)["inserted_rows"] == 8
    raw.loc[0, "Sales"] += 10
    raw.to_csv(csv, index=False)
    correction = load(csv, db)
    assert (correction["updated_rows"], correction["inserted_rows"], correction["warehouse_rows"]) == (1, 0, 8)
    bad = raw.copy()
    bad["Sales"] = bad.Sales.astype(str)
    bad.loc[0, "Sales"] = "abc"
    bad.loc[1, "Product"] = ""
    bad.to_csv(csv, index=False)
    clean, errors = read_source(csv)
    assert len(clean) == 6 and len(errors) == 2
    assert clean.Sales.sum() == 1139
    isolated = tmp_path / "isolated.sqlite"
    summary = load(csv, isolated)
    assert summary["source_rows"] == summary["accepted_rows"] + summary["rejected_rows"]
    assert summary["warehouse_sales"] == 1139
    with sqlite3.connect(isolated) as connection:
        assert connection.execute("SELECT SourceRow FROM RejectedRow ORDER BY SourceRow").fetchall() == [(2,), (3,)]
        assert connection.execute("SELECT COUNT(*) FROM CoffeeRaw").fetchone()[0] == 8


def test_candidate_grain_and_dimension_conflicts_are_rejected(tmp_path):
    raw = pd.read_csv(SOURCE_PATH).head(3)
    raw = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
    csv = tmp_path / "duplicate.csv"
    raw.to_csv(csv, index=False)
    clean, errors = read_source(csv)
    assert len(clean) == 2 and len(errors) == 2
    assert errors.Reason.str.contains("duplicate candidate grain").all()
    raw = pd.read_csv(SOURCE_PATH).head(3)
    raw.loc[2, "State"] = "Different State"
    raw.to_csv(csv, index=False)
    clean, errors = read_source(csv)
    assert len(clean) == 1 and len(errors) == 2
    assert errors.Reason.str.contains("conflicting attributes for AreaCode").all()


def test_failed_load_rolls_back_batch(tmp_path, monkeypatch):
    import coffee_dw.warehouse as warehouse
    csv = tmp_path / "one.csv"
    pd.read_csv(SOURCE_PATH).head(1).to_csv(csv, index=False)
    db = tmp_path / "dw.sqlite"
    monkeypatch.setattr(warehouse, "_scaled", lambda _: (_ for _ in ()).throw(ValueError("injected failure")))
    with pytest.raises(ValueError, match="injected failure"):
        load(csv, db)
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM LoadBatch").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM FactSalesPerformance").fetchone()[0] == 0


def test_fixed_point_storage_uses_original_decimal_strings(tmp_path):
    raw = pd.read_csv(SOURCE_PATH, dtype=str).head(1)
    raw.loc[0, "Sales"] = "123456789012345.1234"
    csv, db = tmp_path / "decimal.csv", tmp_path / "decimal.sqlite"
    raw.to_csv(csv, index=False)
    load(csv, db)
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT SalesScaled FROM FactSalesPerformance").fetchone()[0] == 1234567890123451234
