import sqlite3

import pandas as pd
import pytest

from coffee_dw.forecast import evaluate_monthly, monthly_sales, run_forecast
from coffee_dw.source import read_source
from coffee_dw.warehouse import load


@pytest.fixture(scope="module")
def monthly():
    data, _ = read_source()
    return monthly_sales(data)


def test_forecast_matches_report_protocol(monthly):
    predictions, metrics, future, summary = evaluate_monthly(monthly)
    assert summary["selected_model"] == "moving_average_3"
    assert summary["validation_predictions_per_model"] == 24
    assert summary["test_predictions_per_model"] == 12
    assert summary["forecast_month"] == "2014-01-01"
    assert (predictions.TrainEnd < predictions.ForecastMonth).all()
    assert predictions.IssueMonth.equals(predictions.TrainEnd)
    pooled = metrics.loc[metrics.Market.eq("ALL")].set_index(["ModelName", "Split"])
    assert pooled.loc[("moving_average_3", "validation"), "MAE"] == pytest.approx(223.28, abs=.01)
    assert pooled.loc[("moving_average_3", "test"), "MAE"] == pytest.approx(225.22, abs=.01)
    assert pooled.loc[("ridge", "test"), "MAE"] == pytest.approx(213.33, abs=.01)
    assert future.Actual.isna().all() and len(future) == 4


def test_future_actuals_cannot_change_validation_predictions_or_selection(monthly):
    before, _, _, original = evaluate_monthly(monthly)
    altered = monthly.copy()
    altered.loc[altered.MonthStart.ge("2013-10-01"), "Sales"] += 1_000_000
    after, _, _, changed = evaluate_monthly(altered)
    pd.testing.assert_frame_equal(before.loc[before.Split.eq("validation")].reset_index(drop=True),
                                  after.loc[after.Split.eq("validation")].reset_index(drop=True))
    assert changed["selected_model"] == original["selected_model"]
    # Predictions issued in September precede the changed October actuals.
    pd.testing.assert_series_equal(
        before.loc[before.ForecastMonth.eq("2013-10-01"), "Prediction"],
        after.loc[after.ForecastMonth.eq("2013-10-01"), "Prediction"])


def test_missing_market_month_fails_instead_of_zero_imputation(monthly):
    with pytest.raises(ValueError, match="thiếu tháng"):
        evaluate_monthly(monthly.drop(index=0))


def test_forecast_fact_replay_is_unique(tmp_path):
    db = tmp_path / "warehouse.sqlite"
    load(db_path=db)
    run_forecast(db, tmp_path / "outputs")
    run_forecast(db, tmp_path / "outputs")
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ForecastSales").fetchone()[0] == 112
        assert connection.execute("SELECT COUNT(*) FROM ForecastSales WHERE Actual IS NULL").fetchone()[0] == 4
    assert all((tmp_path / "outputs" / name).is_file() for name in
               ["metrics.csv", "predictions.csv", "next_month.csv", "summary.json"])
