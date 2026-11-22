import numpy as np
import pandas as pd
import pytest

from coffee_dw import exploration
from coffee_dw.exploration import build_exploration, make_scope
from coffee_dw.source import read_source


@pytest.fixture(scope="module")
def eda():
    return build_exploration()


def test_source_eda_reconciles_grain_totals_and_learning_rows(eda):
    s = eda["source"]
    assert (s["accepted_rows"], s["months"], s["monthly_cells"]) == (4248, 24, 96)
    assert (s["sales"], s["budget_sales"], s["profit"]) == (819811, 746160, 259543)
    assert s["rejected_rows"] == 0
    assert eda["tables"]["normalized_detail"].AreaCode.map(lambda x: isinstance(x, str)).all()
    for name, expected_rows, expected_fit in [("train_design",60,48),("full_history_descriptive",96,84)]:
        tables = eda["scopes"][name]["tables"]
        assert len(tables["monthly_market"]) == expected_rows
        assert tables["supervised_lag123"].CompleteLag123.sum() == expected_fit
        assert tables["monthly_market"].Sales.sum() == pytest.approx(eda["scopes"][name]["sales"])
        assert not tables["monthly_market"].duplicated(["Market","MonthStart"]).any()
    assert set(eda["scopes"]["train_design"]["tables"]["lag_correlations"].N) == {12}


def test_inventory_is_a_single_month_snapshot_and_ratios_are_weighted(eda):
    detail = eda["tables"]["normalized_detail"]
    for name, scope in eda["scopes"].items():
        source = detail.loc[detail.MonthStart.le(scope["end"])]
        for market in scope["tables"]["market_summary"].itertuples():
            rows = source.loc[source.Market.eq(market.Market)]
            latest = rows.loc[rows.MonthStart.eq(source.MonthStart.max())]
            assert market.InventoryLastMonth == pytest.approx(latest.Inventory.sum())
            assert market.BudgetAchievement == pytest.approx(rows.Sales.sum()/rows.BudgetSales.sum())
        assert "Inventory" not in scope["tables"]["product_summary"].columns


def test_missing_month_stays_missing_and_lags_use_calendar_months():
    detail, _ = read_source()
    missing = detail.loc[~(detail.Market.eq("East") & detail.MonthStart.eq("2012-08-01"))]
    scope = make_scope(missing,"full_history_descriptive")
    coverage = scope["tables"]["coverage"]
    row = coverage.loc[coverage.Market.eq("East") & coverage.MonthStart.eq("2012-08-01")].iloc[0]
    assert not row.Present and pd.isna(row.SourceRows)
    lag = scope["tables"]["supervised_lag123"]
    september = lag.loc[lag.Market.eq("East") & lag.MonthStart.eq("2012-09-01")].iloc[0]
    assert np.isnan(september.Lag1)
    assert not september.CompleteLag123


def test_future_sales_cannot_change_design_statistics_or_features(eda, monkeypatch):
    detail, rejected = read_source()
    changed = detail.copy()
    changed.loc[changed.MonthStart.gt("2013-03-01"), ["Sales","Profit","BudgetSales"]] += 1000
    monkeypatch.setattr(exploration, "read_source", lambda _: (changed,rejected))
    after = build_exploration()
    for table, original in eda["scopes"]["train_design"]["tables"].items():
        pd.testing.assert_frame_equal(original,after["scopes"]["train_design"]["tables"][table])


def test_bad_input_is_reported_as_reject_without_zero_imputation(tmp_path):
    source = pd.read_csv(exploration.SOURCE_PATH,dtype=str,keep_default_na=False)
    source.loc[0,"Sales"] = ""
    path = tmp_path/"one_bad_row.csv"
    source.to_csv(path,index=False,encoding="utf-8-sig")
    result = build_exploration(path)
    assert result["source"]["source_rows"] == 4248
    assert result["source"]["accepted_rows"] == 4247
    assert result["source"]["rejected_rows"] == 1
    assert "invalid numeric" in result["tables"]["rejected_rows"].iloc[0].Reason
    check = result["tables"]["quality_checks"].set_index("CheckID")
    assert check.loc["Q03","Status"] == "REVIEW"
