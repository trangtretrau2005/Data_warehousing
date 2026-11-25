import pandas as pd
import pytest

from coffee_dw.linear_marketing import build_linear_analysis, monthly_marketing_sales
from coffee_dw.source import read_source


@pytest.fixture(scope="module")
def monthly():
    source, _ = read_source()
    return monthly_marketing_sales(source)


def test_linear_marketing_uses_chronological_holdout_and_real_metrics(monthly):
    result = build_linear_analysis(monthly)
    assert result["meta"]["trainStart"] == "2012-01-01"
    assert result["meta"]["trainEnd"] == "2013-06-01"
    assert result["meta"]["testStart"] == "2013-07-01"
    assert result["meta"]["testEnd"] == "2013-12-01"
    assert len(result["markets"]) == 4
    west = next(model for model in result["markets"] if model["market"] == "West")
    assert (west["n"], west["trainN"], west["testN"]) == (24, 18, 6)
    assert west["coefficient"] == pytest.approx(3.23124, abs=1e-4)
    assert west["correlationAll"] == pytest.approx(0.7208, abs=1e-3)
    assert west["testMAE"] == pytest.approx(333.87, abs=.01)
    assert west["testRMSE"] == pytest.approx(397.89, abs=.01)
    assert west["testR2"] == pytest.approx(-1.53, abs=.01)
    assert west["baselineMAE"] == pytest.approx(536.0, abs=.01)
    assert [point["split"] for point in west["points"]].count("test") == 6


def test_test_actuals_do_not_change_fitted_linear_equation(monthly):
    before = build_linear_analysis(monthly)
    changed = monthly.copy()
    changed.loc[changed.MonthStart.ge("2013-07-01"), "Sales"] += 100_000
    after = build_linear_analysis(changed)
    for original, modified in zip(before["markets"], after["markets"], strict=True):
        assert original["market"] == modified["market"]
        assert original["coefficient"] == pytest.approx(modified["coefficient"])
        assert original["intercept"] == pytest.approx(modified["intercept"])
        assert original["line"] == modified["line"]
        assert original["testMAE"] != modified["testMAE"]


def test_missing_market_month_is_rejected_instead_of_imputed(monthly):
    broken = monthly.drop(monthly.index[0])
    with pytest.raises(ValueError, match="thiếu tháng"):
        build_linear_analysis(broken)
