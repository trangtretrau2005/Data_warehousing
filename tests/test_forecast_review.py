import json

import numpy as np
import pandas as pd
import pytest

from coffee_dw import forecast_review as study
from coffee_dw import tuning_study as baseline


@pytest.fixture(scope="module")
def monthly():
    return study.prepare_inputs(study.SOURCE_PATH)[0]


def test_seasonal_naive_uses_target_minus_12_not_previous_year_last(monthly):
    history = pd.Series(np.arange(15, dtype=float))
    assert study.predict_extension(history, "seasonal_naive_12") == 3
    with pytest.raises(ValueError, match="12 tháng"):
        study.predict_extension(history.iloc[:11], "seasonal_naive_12")
    predictions, _, origins, _ = study.evaluate_phase(monthly, "validation")
    part = predictions.loc[predictions.ModelName.eq("seasonal_naive_12")]
    for row in part.itertuples():
        expected = monthly.loc[monthly.Market.eq(row.Market) & monthly.MonthStart.eq(row.ForecastMonth - pd.DateOffset(years=1)), "Sales"].iloc[0]
        assert row.Prediction == expected
    sources = origins.loc[origins.ModelName.eq("seasonal_naive_12")]
    assert sources.SeasonalSourceMonth.eq(sources.ForecastMonth - pd.DateOffset(years=1)).all()


def test_ses_has_declared_initial_value_and_causal_recursion():
    assert study.ses_level([10, 20, 30], .5) == 22.5
    assert study.ses_level([10, 20, 30], 1) == 30
    assert study.ses_level([0, 0, 0], .2) == 0
    assert study.ses_level([-10, -20, -30], .5) == -22.5
    assert study.ses_level([8], .5) == 8
    for alpha in (0, -1, 1.1, np.inf, np.nan):
        with pytest.raises(ValueError):
            study.ses_level([10, 20], alpha)
    for history in ([], [1, np.nan], [np.inf], [[1, 2]]):
        with pytest.raises(ValueError):
            study.ses_level(history, .5)


def test_existing_seven_match_tuning_on_same_targets(monthly):
    current = study.evaluate_phase(monthly, "validation")[0]
    expected = baseline.evaluate_phase(monthly, "validation")[0]
    keys = ["Market", "ForecastMonth", "ModelName"]
    observed = current.loc[current.ModelName.isin(baseline.BY_KEY)].sort_values(keys).reset_index(drop=True)
    expected = expected.sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(observed.drop(columns="ModelVersion"), expected.drop(columns="ModelVersion"))
    assert len(current) == 264 and current.groupby("ModelName").size().eq(24).all()


def test_target_and_future_cannot_change_issued_predictions(monthly):
    before = study.evaluate_phase(monthly, "validation")[0]
    for target in (pd.Timestamp("2013-04-01"), pd.Timestamp("2013-07-01")):
        changed = monthly.copy()
        changed.loc[changed.MonthStart.ge(target), "Sales"] += 100000
        after = study.evaluate_phase(changed, "validation")[0]
        np.testing.assert_array_equal(before.loc[before.ForecastMonth.le(target), "Prediction"],
                                      after.loc[after.ForecastMonth.le(target), "Prediction"])


def test_test_actuals_cannot_change_validation_selection_or_first_test_issue(monthly):
    changed = monthly.copy()
    changed.loc[changed.MonthStart.ge("2013-10-01"), "Sales"] += 100000
    before, metrics_before, _, _ = study.evaluate_phase(monthly, "validation")
    after, metrics_after, _, _ = study.evaluate_phase(changed, "validation")
    pd.testing.assert_frame_equal(before, after)
    assert study.choose_configuration(metrics_before)[0] == study.choose_configuration(metrics_after)[0]
    first_before = study.evaluate_phase(monthly, "test")[0]
    first_after = study.evaluate_phase(changed, "test")[0]
    np.testing.assert_array_equal(first_before.loc[first_before.ForecastMonth.eq("2013-10-01"), "Prediction"],
                                  first_after.loc[first_after.ForecastMonth.eq("2013-10-01"), "Prediction"])


def test_selection_rejects_test_partial_or_nonfinite_metrics(monthly):
    metrics = study.evaluate_phase(monthly, "validation")[1]
    with pytest.raises(ValueError, match="validation"):
        study.choose_configuration(metrics.assign(Split="test"))
    with pytest.raises(ValueError, match="11 cấu hình"):
        study.choose_configuration(metrics.loc[~metrics.ModelName.eq("ses_a0p2")])
    broken = metrics.copy()
    broken.loc[broken.Market.eq("ALL"), "MAE"] = np.nan
    with pytest.raises(ValueError, match="hữu hạn"):
        study.choose_configuration(broken)
    tied = metrics.copy()
    tied.loc[tied.Market.eq("ALL"), "MAE"] = 1
    assert study.choose_configuration(tied)[0] == "naive_last"


def test_protocol_and_selection_written_before_scoring_test(tmp_path, monkeypatch):
    real = study.evaluate_phase
    stages = []
    def checked(monthly, split):
        protocol = json.loads((tmp_path / "protocol.json").read_text(encoding="utf-8"))
        assert len(protocol["new_candidates"]) == 4 and len(protocol["candidates"]) == 11
        assert protocol["synthetic_observations"] == 0
        if split == "test":
            decision = json.loads((tmp_path / "selection.json").read_text(encoding="utf-8"))
            assert decision["test_used_for_selection"] is False
            assert decision["test_previously_seen"] is True
            assert decision["changes_serving_model"] is False
        stages.append(split)
        return real(monthly, split)
    monkeypatch.setattr(study, "evaluate_phase", checked)
    result = study.run_review(output=tmp_path)
    assert stages == ["validation", "test"]
    assert (result["validation_predictions"], result["test_predictions"], result["future_predictions"]) == (264, 132, 44)
    assert result["source_sha256_before"] == result["source_sha256_after"]
    events = pd.read_csv(tmp_path / "execution_events.csv").set_index("Stage")
    assert events.loc["protocol_saved", "Sequence"] < events.loc["selection_saved", "Sequence"] < events.loc["test_started", "Sequence"]
    future = pd.read_csv(tmp_path / "future.csv")
    assert future.Actual.isna().all() and future.Selected.sum() == 4
    assert future.TrainEnd.lt(future.ForecastMonth).all()
    assert result["selection_sha256"] == study.sha(tmp_path / "selection.json")
    assert result["protocol_sha256"] == study.sha(tmp_path / "protocol.json")
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    for artifact in manifest["files"]:
        assert study.sha(tmp_path / artifact["path"]) == artifact["sha256"]


def test_calendar_missing_is_not_filled_with_fake_zero(monthly):
    with pytest.raises(ValueError, match="24 tháng"):
        study.evaluate_phase(monthly.drop(index=0), "validation")
