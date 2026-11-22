import numpy as np
import pandas as pd
import pytest

from coffee_dw.demo import build_demo_bundle, load_demo_bundle, save_demo_bundle, speech_number, spoken_month
from coffee_dw.explain import explain_history
from coffee_dw.forecast import METHODS, predict_next
from coffee_dw.warehouse import load


@pytest.mark.parametrize("method", METHODS)
def test_explanation_matches_reference_forecast(method):
    history = pd.Series([100, 120, 110, 150, 130, 160, 170, 140, 190],
                        index=pd.date_range("2012-01-01", periods=9, freq="MS"))
    result = explain_history(history, method)
    assert result["prediction"] == pytest.approx(predict_next(history, method))
    assert result["base_value"] + sum(f["contribution"] for f in result["features"]) == pytest.approx(result["prediction"])
    assert result["reconstruction_error"] < 1e-6
    if method == "naive_last":
        assert result["features"][1]["contribution"] == 0
        assert result["features"][2]["contribution"] == 0


@pytest.mark.parametrize("method", METHODS)
def test_constant_history_has_no_artificial_contributions(method):
    history = pd.Series(np.full(15, 125.), index=pd.date_range("2012-01-01", periods=15, freq="MS"))
    result = explain_history(history, method)
    assert result["prediction"] == pytest.approx(125)
    assert all(abs(f["contribution"]) < 1e-8 for f in result["features"])


def test_missing_history_month_is_rejected():
    history = pd.Series(range(9), index=pd.date_range("2012-01-01", periods=9, freq="MS")).drop(pd.Timestamp("2012-03-01"))
    with pytest.raises(ValueError, match="contiguous"):
        explain_history(history, "ridge")


@pytest.fixture(scope="module")
def demo_bundle(tmp_path_factory):
    directory = tmp_path_factory.mktemp("narrated_demo")
    db = directory / "warehouse.sqlite"
    load(db_path=db)
    return build_demo_bundle(db)


def test_all_48_cases_have_valid_origins_and_explanations(demo_bundle):
    assert len(demo_bundle["cases"]) == 48
    assert demo_bundle["selected_method"] == "moving_average_3"
    assert demo_bundle["dataset"]["monthly_rows"] == 96
    ids = set()
    for case in demo_bundle["cases"]:
        assert case["id"] not in ids
        ids.add(case["id"])
        assert case["train_end"] < case["forecast_month"]
        assert all(point["month"] < case["forecast_month"] for point in case["history"])
        assert all(f["month"] < case["forecast_month"] for f in case["explanation"]["features"])
        assert case["validation_market"]["N"] == 6
        assert case["explanation"]["reconstruction_error"] < 1e-6
        assert len(case["chapters"]) == 3
        if case["forecast_month"] == "2014-01-01":
            assert case["actual"] is None


def test_future_actual_does_not_change_earlier_case(demo_bundle, monkeypatch):
    import coffee_dw.demo as demo
    from coffee_dw.source import read_source
    detail, _ = read_source()
    detail.loc[detail.MonthStart.ge("2013-10-01"), "Sales"] += 1000
    monkeypatch.setattr(demo, "read_detail", lambda _: detail)
    altered = build_demo_bundle("unused.sqlite")
    old = {c["id"]: c for c in demo_bundle["cases"]}
    for case in altered["cases"]:
        if case["forecast_month"] == "2013-10-01":
            assert case["prediction"] == pytest.approx(old[case["id"]]["prediction"])
            assert case["explanation"] == old[case["id"]]["explanation"]
            assert case["chapters"] == old[case["id"]]["chapters"]
            assert case["report"] == old[case["id"]]["report"]


@pytest.mark.parametrize("value, expected", [(0,"không"), (15,"mười lăm"), (21,"hai mươi mốt"),
                                           (1005,"một nghìn không trăm lẻ năm"),
                                           (-11360,"âm mười một nghìn ba trăm sáu mươi")])
def test_speech_numbers_are_unambiguous_vietnamese(value, expected):
    assert speech_number(value) == expected
    assert not any(char.isdigit() for char in spoken_month("2013-10-01"))


def test_management_context_reconciles_to_real_warehouse_at_origin(demo_bundle):
    from coffee_dw.source import read_source
    detail, _ = read_source()
    for case in demo_bundle["cases"]:
        report = case["report"]
        rows = detail.loc[detail.Market.eq(case["market"]) & detail.MonthStart.eq(case["train_end"])]
        assert report["latest_sales"] == pytest.approx(rows.Sales.sum())
        assert report["latest_profit"] == pytest.approx(rows.Profit.sum())
        assert report["budget_ratio"] == pytest.approx(rows.Sales.sum()/rows.BudgetSales.sum())
        assert all(r["month"] < case["forecast_month"] for r in report["recent"])
        assert sum(p["share"] for p in report["products"]) <= 1.000001


def test_report_fingerprint_detects_budget_changes_even_when_forecast_sales_unchanged():
    from coffee_dw.source import read_source
    from coffee_dw.demo import report_fingerprint, monthly_fingerprint
    from coffee_dw.forecast import monthly_sales
    detail, _ = read_source()
    changed = detail.copy()
    changed.loc[changed.index[0], "BudgetSales"] += 1
    assert monthly_fingerprint(monthly_sales(detail)) == monthly_fingerprint(monthly_sales(changed))
    assert report_fingerprint(detail) != report_fingerprint(changed)
    assert report_fingerprint(detail) == report_fingerprint(detail.iloc[::-1])


def test_bundle_roundtrip_and_corruption_is_detected(demo_bundle, tmp_path):
    path = save_demo_bundle(demo_bundle, tmp_path)
    assert load_demo_bundle(path)["dataset"] == demo_bundle["dataset"]
    import json
    corrupt = json.loads(path.read_text(encoding="utf-8"))
    corrupt["cases"][0]["prediction"] += 5
    path.write_text(json.dumps(corrupt), encoding="utf-8")
    with pytest.raises(ValueError, match="không khớp"):
        load_demo_bundle(path)
