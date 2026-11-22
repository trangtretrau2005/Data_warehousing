"""Acceptance boundaries that must not silently become plausible zero KPIs."""

from pathlib import Path
import json

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from coffee_dw import config, serving
from coffee_dw.warehouse import load, read_detail

APP = Path(__file__).resolve().parents[1] / "apps/dashboard/app.py"


def table_with_columns(app, *columns):
    """Find a displayed table by its contract, independent of page layout order."""
    matches = [item.value for item in app.dataframe if set(columns).issubset(item.value.columns)]
    assert len(matches) == 1, f"Expected one table with {columns}, found {len(matches)}"
    return matches[0]


def test_native_source_error_is_not_zero_kpi(tmp_path, monkeypatch):
    monkeypatch.setenv("COFFEE_DW_BACKEND", "sqlserver")
    def fail(*args):
        raise RuntimeError("private connection details")
    monkeypatch.setattr(serving, "dashboard_detail", fail)
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception and len(app.error) == 1 and len(app.metric) == 0
    assert "private" not in app.error[0].value
    assert "lỗi nguồn" in app.error[0].value


def test_empty_warehouse_is_not_connection_error(tmp_path, monkeypatch):
    db = tmp_path / "empty.sqlite"
    db.touch()
    monkeypatch.setenv("COFFEE_DW_BACKEND", "sqlite")
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(serving, "dashboard_detail", lambda *args: pd.DataFrame())
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception and not app.error and not app.metric
    assert "chưa có bản ghi" in app.info[0].value


def test_inventory_uses_last_month_and_drill_sort_is_signed(tmp_path, monkeypatch):
    db = tmp_path / "acceptance.sqlite"
    load(db_path=db)
    detail = read_detail(db)
    monkeypatch.setenv("COFFEE_DW_BACKEND", "sqlite")
    monkeypatch.setattr(config, "DB_PATH", db)
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.select_slider[0].set_range(pd.Timestamp("2012-01-01"), pd.Timestamp("2012-02-01"))
    app.multiselect[0].set_value(["West"]).run()
    products = app.dataframe[2].value
    assert list(products.Gap) == sorted(products.Gap)
    assert products.iloc[0].Gap < 0
    assert products.Sales.sum() == detail.loc[detail.Market.eq("West") & detail.MonthStart.between("2012-01-01", "2012-02-01"), "Sales"].sum()
    app.radio[0].set_value("Tồn kho và chi phí").run()
    inventory = app.dataframe[0].value
    expected = detail.loc[detail.Market.eq("West") & detail.MonthStart.eq("2012-02-01"), "Inventory"].sum()
    assert inventory.Inventory.sum() == expected
    assert not app.exception


def test_native_forecast_panel_and_experiments_read_precomputed_frames(tmp_path, monkeypatch):
    db = tmp_path / "acceptance.sqlite"
    load(db_path=db)
    from coffee_dw.forecast import evaluate_monthly, monthly_sales
    prediction, metric, future, summary = evaluate_monthly(monthly_sales(read_detail(db)))
    monkeypatch.setenv("COFFEE_DW_BACKEND", "sqlserver")
    monkeypatch.setattr(serving, "dashboard_detail", lambda *args: read_detail(db))
    monkeypatch.setattr(serving, "dashboard_forecast", lambda *args: (summary, metric, prediction, future))
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.multiselect[0].set_value(["West"]).run()
    app.radio[0].set_value("Dự báo AI").run()
    assert not app.exception and not app.error
    metrics = table_with_columns(app, "Market", "MAE", "RMSE", "N")
    future_tables = [item.value for item in app.dataframe
                     if {"Market", "Actual", "Split"}.issubset(item.value.columns)
                     and not item.value.empty and item.value.Split.eq("future").all()]
    assert len(future_tables) == 1
    future_table = future_tables[0]
    assert set(metrics.Market) == {"ALL", "West"}
    assert set(future_table.Market) == {"West"}
    assert future_table.Actual.isna().all()
    app.multiselect[0].set_value(["Central", "East", "South", "West"]).run()
    assert not app.exception and not app.error
    figure = json.loads(app.get("plotly_chart")[0].proto.spec)
    assert len(figure["data"]) == 8  # Two observable series per Market.
    assert {trace["name"] for trace in figure["data"]} == {"Thực tế", "Dự báo"}
    app.radio[0].set_value("Kết quả thực nghiệm").run()
    assert not app.exception


def test_month_comparison_displays_actual_and_error_for_west_november(tmp_path, monkeypatch):
    db = tmp_path / "comparison.sqlite"
    load(db_path=db)
    from coffee_dw.forecast import run_forecast

    run_forecast(db, tmp_path / "forecast")
    monkeypatch.setenv("COFFEE_DW_BACKEND", "sqlite")
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(config, "RESULTS_DIR", tmp_path)
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.select_slider[0].set_range(pd.Timestamp("2012-01-01"), pd.Timestamp("2012-01-01"))
    app.multiselect[0].set_value(["West"]).run()
    app.radio[0].set_value("Dự báo AI").run()
    assert not app.exception

    comparison_range = next(item for item in app.select_slider if item.label == "Khoảng tháng đối chiếu dự báo")
    comparison_range.set_range(pd.Timestamp("2013-10-01"), pd.Timestamp("2013-11-01")).run()
    month = next(item for item in app.selectbox if item.label == "Tháng đối chiếu")
    month.set_value(pd.Timestamp("2013-11-01")).run()
    assert not app.exception

    # Only November should appear in the point comparison; the graph/export may show the range.
    candidates = [item.value for item in app.dataframe
                  if {"Market", "ForecastMonth", "Prediction", "Actual", "Error", "AbsoluteError", "AbsolutePercentageError"}.issubset(item.value.columns)]
    point = next(frame for frame in candidates
                 if len(frame) == 1 and pd.to_datetime(frame.ForecastMonth).eq("2013-11-01").all())
    row = point.iloc[0]
    assert row.Market == "West"
    assert row.Actual == 11300
    assert row.Prediction == pytest.approx(11777.333333333334)
    assert row.Error == pytest.approx(477.333333333334)
    assert row.AbsoluteError == pytest.approx(477.333333333334)
    assert row.AbsolutePercentageError == pytest.approx(477.333333333334 / 11300 * 100)
    assert pd.Timestamp(row.TrainEnd) == pd.Timestamp("2013-10-01")
    assert row.Split == "test"
    figure = json.loads(app.get("plotly_chart")[0].proto.spec)
    traces = {trace["name"]: trace for trace in figure["data"]}
    assert set(traces) == {"Thực tế", "Dự báo"}
    assert traces["Thực tế"]["line"]["color"] != traces["Dự báo"]["line"]["color"]
    assert traces["Thực tế"]["line"]["dash"] == "solid"
    assert traces["Dự báo"]["line"]["dash"] == "dash"


def test_comparison_export_scope_and_errors_do_not_change_published_forecasts():
    from coffee_dw.forecast import evaluate_monthly, monthly_sales
    from coffee_dw.serving import forecast_comparison_frame
    from coffee_dw.source import read_source

    source, _ = read_source()
    predictions, _, _, _ = evaluate_monthly(monthly_sales(source))
    before = predictions.copy(deep=True)
    scope = forecast_comparison_frame(predictions, ["West", "East"], "moving_average_3",
                                      pd.Timestamp("2013-10-01"), pd.Timestamp("2013-11-01"))
    assert len(scope) == 4
    assert set(scope.Market) == {"West", "East"}
    assert set(scope.ModelName) == {"moving_average_3"}
    assert set(pd.to_datetime(scope.ForecastMonth)) == {pd.Timestamp("2013-10-01"), pd.Timestamp("2013-11-01")}
    assert not scope.duplicated(["Market", "ForecastMonth"]).any()
    assert (pd.to_datetime(scope.TrainEnd) < pd.to_datetime(scope.ForecastMonth)).all()
    pd.testing.assert_series_equal(scope.Error, scope.Prediction - scope.Actual, check_names=False)
    pd.testing.assert_series_equal(scope.AbsoluteError, scope.Error.abs(), check_names=False)
    pd.testing.assert_frame_equal(predictions, before)

    # CSV serialization of exactly this frame is the dashboard export contract.
    from io import StringIO
    exported = pd.read_csv(StringIO(scope.to_csv(index=False)))
    assert len(exported) == 4 and set(exported.Market) == {"West", "East"}
    one_month = forecast_comparison_frame(predictions, ["West"], "moving_average_3",
                                          pd.Timestamp("2013-11-01"), pd.Timestamp("2013-11-01"))
    assert len(one_month) == 1 and one_month.iloc[0].Actual == 11300


def test_comparison_zero_actual_has_missing_percentage_instead_of_infinity():
    from coffee_dw.serving import forecast_comparison_frame

    predictions = pd.DataFrame([{
        "Market": "West", "ForecastMonth": pd.Timestamp("2013-11-01"),
        "TrainEnd": pd.Timestamp("2013-10-01"), "ModelName": "moving_average_3",
        "Prediction": 15.0, "Actual": 0.0, "Split": "test",
    }])
    scope = forecast_comparison_frame(predictions, ["West"], "moving_average_3",
                                      pd.Timestamp("2013-11-01"), pd.Timestamp("2013-11-01"))
    assert scope.iloc[0].Error == 15
    assert scope.iloc[0].AbsoluteError == 15
    assert pd.isna(scope.iloc[0].AbsolutePercentageError)
