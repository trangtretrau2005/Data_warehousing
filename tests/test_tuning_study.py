import json

import joblib
import numpy as np
import pandas as pd
import pytest

from coffee_dw import tuning_study as study
from coffee_dw.forecast import evaluate_monthly


@pytest.fixture(scope="module")
def prepared():
    return study.prepare_inputs(study.SOURCE_PATH)


def test_reference_candidates_reproduce_baseline_with_deterministic_solver(prepared):
    reference = evaluate_monthly(prepared[0])[0]
    results = pd.concat([study.evaluate_phase(prepared[0],split)[0] for split in ("validation","test")])
    mapping = {"naive_last":"naive_last","ma_w3":"moving_average_3","ridge_a1":"ridge"}
    actual = results.loc[results.ModelName.isin(mapping)].copy()
    actual["ModelName"] = actual.ModelName.map(mapping)
    columns = ["Market","ForecastMonth","ModelName","Split"]
    actual = actual.sort_values(columns).reset_index(drop=True)
    reference = reference.sort_values(columns).reset_index(drop=True)
    pd.testing.assert_frame_equal(actual[columns],reference[columns])
    np.testing.assert_allclose(actual.Prediction,reference.Prediction,rtol=1e-12,atol=1e-8)
    np.testing.assert_array_equal(actual.Actual,reference.Actual)


def test_future_actual_cannot_alter_validation_or_first_test_prediction(prepared):
    monthly = prepared[0]
    changed = monthly.copy()
    changed.loc[changed.MonthStart.ge("2013-10-01"),"Sales"] += 100000
    before,bm,_,bp = study.evaluate_phase(monthly,"validation")
    after,am,_,ap = study.evaluate_phase(changed,"validation")
    pd.testing.assert_frame_equal(before,after)
    pd.testing.assert_frame_equal(bp,ap)
    assert study.choose_configuration(bm)[0] == study.choose_configuration(am)[0]
    tb = study.evaluate_phase(monthly,"test")[0]
    ta = study.evaluate_phase(changed,"test")[0]
    np.testing.assert_array_equal(tb.loc[tb.ForecastMonth.eq("2013-10-01"),"Prediction"],
                                  ta.loc[ta.ForecastMonth.eq("2013-10-01"),"Prediction"])


def test_scaler_and_raw_coefficients_reproduce_first_forecast(prepared):
    _,_,origins,audit = study.evaluate_phase(prepared[0],"validation")
    first = audit.loc[audit.ForecastMonth.eq("2013-04-01")]
    features = prepared[1]
    predictions = study.evaluate_phase(prepared[0],"validation")[0]
    for (market,key),part in first.groupby(["Market","ModelName"]):
        train = features.loc[features.Market.eq(market)&features.CompleteLag123&features.Split.eq("initial_history")]
        assert part.FitN.eq(12).all()
        for row in part.itertuples():
            assert row.MeanTrain == pytest.approx(train[row.Feature.capitalize()].mean())
            assert row.ScaleTrain == pytest.approx(train[row.Feature.capitalize()].std(ddof=0))
        origin = origins.loc[origins.Market.eq(market)&origins.ModelName.eq(key)&origins.ForecastMonth.eq("2013-04-01")].iloc[0]
        manual = part.InterceptRaw.iloc[0] + sum(row.CoefficientRaw*origin[row.Feature.capitalize()] for row in part.itertuples())
        expected = predictions.loc[predictions.Market.eq(market)&predictions.ModelName.eq(key)&predictions.ForecastMonth.eq("2013-04-01"),"Prediction"].iloc[0]
        assert manual == pytest.approx(expected,abs=1e-8)
        assert origin.FitN == origin.HistoryN-3


def test_selection_rejects_test_incomplete_or_nonfinite_comparisons(prepared):
    metrics = study.evaluate_phase(prepared[0],"validation")[1]
    with pytest.raises(ValueError,match="validation"):
        study.choose_configuration(metrics.assign(Split="test"))
    with pytest.raises(ValueError,match="bảy"):
        study.choose_configuration(metrics.loc[~metrics.ModelName.eq("ma_w6")])
    broken = metrics.copy()
    broken.loc[broken.Market.eq("ALL"),"MAE"] = np.nan
    with pytest.raises(ValueError,match="hữu hạn"):
        study.choose_configuration(broken)


def test_rule_predictions_are_hand_calculable_and_have_no_learned_model():
    history = pd.Series([10.,20.,30.,40.,50.,60.])
    for key,expected in [("naive_last",60),("ma_w2",55),("ma_w3",50),("ma_w6",35)]:
        candidate = study.BY_KEY[key]
        assert study.fit_candidate(history,candidate) is None
        assert study.predict_fitted(history,candidate) == expected
    with pytest.raises(ValueError,match="ít nhất"):
        study.fit_candidate(history.iloc[:3],study.BY_KEY["ridge_a1"])


def test_full_export_locks_selection_before_test_and_reloads_all_models(tmp_path,monkeypatch):
    real = study.evaluate_phase
    stages = []
    def checked(monthly,split):
        protocol = json.loads((tmp_path/"01_protocol/protocol.json").read_text(encoding="utf-8"))
        assert len(protocol["candidates"]) == 7
        if split == "test":
            decision = json.loads((tmp_path/"02_validation/selection.json").read_text(encoding="utf-8"))
            assert decision["selected_configuration"] == "ma_w3"
            assert decision["test_used_for_selection"] is False
            assert decision["test_previously_seen"] is True
        stages.append(split)
        return real(monthly,split)
    monkeypatch.setattr(study,"evaluate_phase",checked)
    result = study.run_study(output=tmp_path,render=False)
    assert stages == ["validation","test"]
    assert (result["validation_predictions"],result["test_predictions"],result["future_predictions"]) == (168,84,28)
    assert (result["ridge_fits_validation"],result["ridge_fits_test"],result["ridge_fits_final"]) == (72,36,12)
    assert result["source"]["sha256"] == result["source_sha256_after"]
    assert result["selection_sha256"] == study.sha(tmp_path/"02_validation/selection.json")
    future = pd.read_csv(tmp_path/"05_models/all_next_month.csv")
    assert future.Actual.isna().all() and future.Selected.sum() == 4
    index = pd.read_csv(tmp_path/"05_models/model_index.csv")
    assert len(index) == 28 and index.ModelPath.notna().sum() == 12
    for row in index.itertuples():
        state = json.loads((tmp_path/row.StatePath).read_text(encoding="utf-8"))
        values = np.array([x["sales"] for x in state["observations"]])
        if row.LearnsCoefficients:
            pipeline = joblib.load(tmp_path/row.ModelPath)
            assert pipeline.steps[0][1].n_samples_seen_ == 21
            prediction = pipeline.predict(values[::-1].reshape(1,-1))[0]
            assert prediction == pytest.approx(row.Prediction,abs=1e-8)
        else:
            assert values.mean() == pytest.approx(row.Prediction)
    events = pd.read_csv(tmp_path/"06_summary/execution_events.csv").set_index("Stage")
    assert events.loc["grid_saved","Sequence"] < events.loc["selection_saved","Sequence"] < events.loc["test_started","Sequence"]
    for record in result["files"]:
        assert study.sha(tmp_path/record["path"]) == record["sha256"]


def test_missing_calendar_month_is_rejected(prepared):
    with pytest.raises(ValueError,match="24 tháng"):
        study.evaluate_phase(prepared[0].drop(index=0),"validation")


def test_sensitivity_only_omits_scoring_rows(prepared):
    predictions = study.evaluate_phase(prepared[0],"validation")[0]
    by_month,stability = study.validation_diagnostics(predictions)
    assert len(by_month) == 42 and by_month.N.eq(4).all()
    assert len(stability) == 6 and stability.N.eq(20).all()
    assert stability.Purpose.str.contains("not selection").all()
