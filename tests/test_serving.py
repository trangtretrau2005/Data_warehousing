import numpy as np
import pandas as pd
import pytest

from coffee_dw.forecast import evaluate_monthly, monthly_sales
from coffee_dw import serving
from coffee_dw.serving import dashboard_backend, native_forecast_frames
from coffee_dw.source import read_source


@pytest.fixture(scope="module")
def publication():
    source, _ = read_source()
    predictions, _, future, _ = evaluate_monthly(monthly_sales(source))
    return pd.concat([predictions, future], ignore_index=True)


def test_backend_invalid_fails_explicitly(monkeypatch):
    monkeypatch.setenv("COFFEE_DW_BACKEND", "typo")
    with pytest.raises(ValueError, match="sqlite hoặc sqlserver"):
        dashboard_backend()


def test_native_publication_uses_validation_and_preserves_future_missing(publication):
    summary, metrics, predictions, future = native_forecast_frames(publication)
    assert summary["selected_model"] == "moving_average_3"
    assert len(predictions) == 108 and len(future) == 4
    assert future.Actual.isna().all()
    assert metrics.query("Market == 'ALL' and Split == 'validation' and ModelName == 'moving_average_3'").MAE.iloc[0] == pytest.approx(223.28, abs=.01)


def test_native_publication_rejects_ambiguous_issue(publication):
    duplicate = publication.iloc[[0]].copy()
    duplicate["IssueMonth"] -= pd.offsets.MonthBegin(1)
    with pytest.raises(ValueError, match="nhiều kỳ phát hành"):
        native_forecast_frames(pd.concat([publication, duplicate]))


def test_native_publication_rejects_future_actual(publication):
    frame = publication.copy()
    frame.loc[frame.Split.eq("future"), "Actual"] = 0
    with pytest.raises(ValueError, match="actual tương lai"):
        native_forecast_frames(frame)


@pytest.mark.parametrize("missing", ["one_prediction", "one_month", "one_method_at_market", "whole_market", "one_future"])
def test_native_publication_rejects_partial_upload(publication, missing):
    frame = publication.copy()
    if missing == "one_prediction":
        frame = frame.drop(index=0)
    elif missing == "one_month":
        frame = frame.loc[frame.ForecastMonth.ne("2013-04-01")]
    elif missing == "one_method_at_market":
        frame = frame.loc[~(frame.Market.eq("West") & frame.ModelName.eq("ridge"))]
    elif missing == "whole_market":
        frame = frame.loc[frame.Market.ne("West")]
    else:
        frame = frame.loc[~(frame.Market.eq("West") & frame.Split.eq("future"))]
    with pytest.raises(ValueError, match="Publication"):
        native_forecast_frames(frame)


@pytest.mark.parametrize("invalid", ["split", "unknown_method", "wrong_market", "infinite_prediction", "infinite_actual", "actual_mismatch", "wrong_origin", "mid_month", "missing_date", "future_target"])
def test_native_publication_rejects_incoherent_rows(publication, invalid):
    frame = publication.copy()
    if invalid == "split":
        frame.loc[0, "Split"] = "test"
    elif invalid == "unknown_method":
        frame.loc[0, "ModelName"] = "not_published"
    elif invalid == "wrong_market":
        frame.loc[0, "Market"] = "unknown"
    elif invalid == "infinite_prediction":
        frame.loc[0, "Prediction"] = np.inf
    elif invalid == "infinite_actual":
        frame.loc[0, "Actual"] = np.inf
    elif invalid == "actual_mismatch":
        frame.loc[0, "Actual"] += 1
    elif invalid == "wrong_origin":
        frame.loc[0, ["IssueMonth", "TrainEnd"]] -= pd.offsets.MonthBegin(1)
    elif invalid == "mid_month":
        frame.loc[0, "ForecastMonth"] += pd.Timedelta(days=1)
    elif invalid == "missing_date":
        frame.loc[0, "IssueMonth"] = pd.NaT
    else:
        idx = frame.index[frame.Split.eq("future")][0]
        frame.loc[idx, ["ForecastMonth", "IssueMonth", "TrainEnd"]] += pd.offsets.MonthBegin(1)
    with pytest.raises(ValueError):
        native_forecast_frames(frame)


def test_test_errors_do_not_choose_future_model(publication):
    frame = publication.copy()
    # Give Naive perfect test predictions, with MA3 very poor. Validation still
    # determines the publication; never replace the serving method from test.
    frame.loc[frame.Split.eq("test") & frame.ModelName.eq("naive_last"), "Prediction"] = frame.Actual
    frame.loc[frame.Split.eq("test") & frame.ModelName.eq("moving_average_3"), "Prediction"] = 1e9
    summary, _, _, _ = native_forecast_frames(frame)
    assert summary["selected_model"] == "moving_average_3"


def test_version_filter_excludes_other_protocol_before_scoring(publication):
    foreign = publication.iloc[[0]].copy()
    foreign["ModelVersion"] = "tn12-west-exploratory"
    foreign["Prediction"] = -1e9
    _, _, observed, _ = native_forecast_frames(pd.concat([publication, foreign]))
    assert len(observed) == 108
    assert observed.ModelVersion.nunique() == 1


def test_native_publication_rejects_inconsistent_future_choice(publication):
    frame = publication.copy()
    frame.loc[frame.Split.eq("future") & frame.Market.eq("West"), "ModelName"] = "naive_last"
    with pytest.raises(ValueError, match="không khớp lựa chọn validation"):
        native_forecast_frames(frame)


def test_coherent_schedule_can_move_with_an_extended_history(publication):
    frame = publication.copy()
    for column in ("ForecastMonth", "IssueMonth", "TrainEnd"):
        frame[column] += pd.offsets.MonthBegin(1)
    summary, _, predictions, future = native_forecast_frames(frame)
    assert summary["test_end"] == "2014-01-01"
    assert future.ForecastMonth.eq("2014-02-01").all()
    assert len(predictions) == 108


def test_query_uses_bound_publication_version(monkeypatch, publication, tmp_path):
    calls = []
    def query(sql, params=()):
        calls.append((sql, params))
        return publication.copy()
    monkeypatch.setattr(serving, "native_query", query)
    serving.dashboard_forecast(tmp_path, "sqlserver")
    assert len(calls) == 1
    assert "WHERE ModelVersion=?" in calls[0][0]
    assert calls[0][1] == (serving.MODEL_VERSION,)


def test_native_query_binds_values_and_closes_even_on_failure(monkeypatch):
    calls = []
    class Cursor:
        description = [("value",)]
        def execute(self, *args):
            calls.append(args)
            return self
        def fetchall(self):
            return [(1,)]
    class Connection:
        def cursor(self):
            return Cursor()
        def close(self):
            calls.append("closed")
    monkeypatch.setattr(serving, "connect_native", lambda: Connection())
    result = serving.native_query("SELECT ? AS value", ("x'; DROP TABLE business; --",))
    assert result.value.tolist() == [1]
    assert calls == [("SELECT ? AS value", "x'; DROP TABLE business; --"), "closed"]
    def fail(self):
        raise RuntimeError("query failed")
    monkeypatch.setattr(Cursor, "fetchall", fail)
    with pytest.raises(RuntimeError):
        serving.native_query("SELECT 1")
    assert calls[-1] == "closed"
