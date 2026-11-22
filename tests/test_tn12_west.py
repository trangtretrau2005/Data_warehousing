import json

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from coffee_dw.config import SOURCE_PATH
from coffee_dw.forecast import monthly_sales
from coffee_dw.source import read_source
from coffee_dw import tn12_west as study


@pytest.fixture(scope="module")
def monthly():
    detail, rejected = read_source(SOURCE_PATH)
    assert rejected.empty
    return monthly_sales(detail)


def test_exactly_reproduces_independent_literal_handbook_example(monthly):
    # Keep the literal reference construction independent of implementation.
    raw = pd.read_csv(SOURCE_PATH)
    raw["m"] = pd.to_datetime(raw.Date, unit="D", origin="1899-12-30")
    s = raw.loc[raw.Market.eq("West")].groupby("m").Sales.sum().sort_index()
    z = pd.DataFrame({"y": s, "lag1": s.shift(1), "lag2": s.shift(2),
                      "mean3": s.shift(1).rolling(3).mean()}).dropna()
    rows = []
    for month in z.index[-6:]:
        past, obs = z.loc[z.index < month], z.loc[[month]]
        cols = ["lag1", "lag2", "mean3"]
        model = make_pipeline(StandardScaler(), Ridge(alpha=1)).fit(past[cols], past.y)
        rows.append([obs.lag1.iloc[0], obs.mean3.iloc[0], model.predict(obs[cols])[0]])
    result = study.evaluate_west(monthly)
    matrix = result["predictions"].pivot(index="ForecastMonth", columns="ModelName", values="Prediction")
    np.testing.assert_allclose(matrix[list(study.METHODS)].to_numpy(), rows, rtol=1e-12)
    assert result["selected_method"] == "naive_last"
    np.testing.assert_allclose(result["metrics"].MAE, [309, 396.7222222222, 320.17714086], atol=.005)
    assert len(result["predictions"]) == 18
    assert result["predictions"].TrainEnd.lt(result["predictions"].ForecastMonth).all()


def test_current_target_and_future_actual_cannot_change_a_forecast(monthly):
    before = study.evaluate_west(monthly)["predictions"]
    for target in study.TARGETS:
        changed = monthly.copy()
        changed.loc[changed.Market.eq("West") & changed.MonthStart.ge(target), "Sales"] += 100000
        after = study.evaluate_west(changed)["predictions"]
        np.testing.assert_array_equal(before.loc[before.ForecastMonth.le(target), "Prediction"],
                                      after.loc[after.ForecastMonth.le(target), "Prediction"])


def test_scaler_fits_15_to_20_past_samples_not_full_history(monthly):
    result = study.evaluate_west(monthly)
    assert result["origins"].FitN.tolist() == [15, 16, 17, 18, 19, 20]
    features = result["features"].dropna()
    for row in result["fit_audit"].itertuples():
        train = features.loc[features.index < row.ForecastMonth, row.Feature]
        assert row.FitN == len(train)
        assert row.MeanTrain == pytest.approx(train.mean())
        assert row.ScaleTrain == pytest.approx(train.std(ddof=0))


@pytest.mark.parametrize("defect", ["missing", "duplicate", "nonfinite", "non_month_start"])
def test_reject_invalid_west_input_without_imputation(monthly, defect):
    changed = monthly.copy()
    row = changed.index[changed.Market.eq("West")][0]
    if defect == "missing":
        changed = changed.drop(index=row)
    elif defect == "duplicate":
        changed = pd.concat([changed, changed.loc[[row]]], ignore_index=True)
    elif defect == "nonfinite":
        changed.loc[row, "Sales"] = np.inf
    else:
        changed.loc[row, "MonthStart"] += pd.Timedelta(days=1)
    with pytest.raises(ValueError):
        study.evaluate_west(changed)


def test_run_preserves_source_and_emits_exploratory_version_not_main(tmp_path):
    before = study.sha(SOURCE_PATH)
    manifest = study.run_study(output=tmp_path, render=False)
    assert manifest["source"]["sha256_before"] == manifest["source"]["sha256_after"] == before
    future = pd.read_csv(tmp_path / "future.csv")
    assert future.Prediction.tolist() == [11883]
    assert future.Actual.isna().all()
    assert future.ModelVersion.tolist() == [study.PROTOCOL_ID]
    assert future.Split.tolist() == ["future_exploratory"]
    protocol = json.loads((tmp_path / "protocol.json").read_text(encoding="utf-8"))
    assert protocol["independent_test"] is False
    assert protocol["writes_warehouse"] is False
    assert protocol["main_study_changed"] is False
    for artifact in manifest["artifacts"]:
        assert study.sha(tmp_path / artifact["path"]) == artifact["sha256"]
