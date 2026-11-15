import runpy
from pathlib import Path

EXPERIMENTS = Path(__file__).resolve().parents[1] / "learning" / "experiments"


def test_scd_boundary_replay_and_type3_limit():
    result = runpy.run_path(str(EXPERIMENTS / "scd.py"))["run"]()
    assert [row["key"] for row in result["type2_lookups"]] == [1, 2, 2]
    assert result["type2_versions_after_replay"] == 2
    assert result["type3"] == [("P01", "Premium", "Specialty")]


def test_hru_recomputes_marginal_benefits():
    select = runpy.run_path(str(EXPERIMENTS / "hru.py"))["select_views"]
    costs = {("M", "R"): 10, ("M",): 5, (): 1}
    rounds = select(costs, {("M",): 1}, 20, 100)
    # M alone answers the workload more cheaply; all later views have zero gain.
    assert rounds == [{"view": "M", "group_rows": 5,
                       "marginal_benefit_weighted_rows": 95, "remaining_rows": 15}]


def test_tn05_mart_and_drill_across_without_fanout():
    result = runpy.run_path(str(EXPERIMENTS / "mart_olap.py"))["run"]()
    tn05 = result["TN05"]
    assert tn05["mart_market_period_groups"] == 96
    assert tn05["mart_market_product_period_groups"] == 1008
    assert all(v == 0.0 for v in tn05["max_abs_diff_market_period"].values())
    assert all(v == 0.0 for v in tn05["max_abs_diff_market_product_period"].values())
    assert tn05["drill_across_baseline"] == {"groups": 96, "sales": 819811.0, "budget_sales": 746160.0}
    assert tn05["fanout_antipattern"]["west_jan2012_inflated_budget"] == 9460.0 * 56
    missing = tn05["full_outer_join_missing_groups"]
    assert len(missing) == 2
    assert missing[0]["MonthStart"] == "2012-01-01" and missing[0]["MissingBudget"] == 1 and missing[0]["BudgetSales"] is None
    assert missing[1]["MonthStart"] == "2014-01-01" and missing[1]["MissingActual"] == 1 and missing[1]["Sales"] is None


def test_tn06_olap_slice_dice_pivot_rollup_and_inventory():
    result = runpy.run_path(str(EXPERIMENTS / "mart_olap.py"))["run"]()
    tn06 = result["TN06"]
    assert tn06["slice_2012_01_central_total"] == {"Sales": 10346.0, "BudgetSales": 9970.0, "Profit": 2956.0}
    assert tn06["slice_2012_01_west_total"]["Sales"] == 10453.0
    assert tn06["slice_2012_01_west_total"]["BudgetSales"] == 9460.0
    assert tn06["dice_pivot_grand_total_sales"] == 4768.0
    assert tn06["south_2013_08_total"] == {"Sales": 4601.0, "BudgetSales": 4610.0, "Gap": -9.0}
    assert tn06["south_2013_08_products_by_gap"][0]["ProductName"] == "Colombian"
    assert tn06["south_2013_08_products_by_gap"][0]["Gap"] == -268.0
