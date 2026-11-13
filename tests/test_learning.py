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
