from pathlib import Path

from streamlit.testing.v1 import AppTest

from coffee_dw import config, demo
from coffee_dw.demo import build_demo_bundle, save_demo_bundle
from coffee_dw.warehouse import load

APP = Path(__file__).resolve().parents[1] / "apps" / "forecast_demo" / "app.py"


def test_demo_empty_state(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "DEMO_DIR", tmp_path / "not_prepared")
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert "chưa có dữ liệu" in app.info[0].value


def test_demo_filters_and_future_target_without_actual(tmp_path, monkeypatch):
    db, outputs = tmp_path / "warehouse.sqlite", tmp_path / "demo"
    load(db_path=db)
    bundle = build_demo_bundle(db)
    save_demo_bundle(bundle, outputs)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(demo, "DEMO_DIR", outputs)
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not app.exception
    assert len(app.metric) == 3
    for market, target, method in [("Central", "2013-11-01", "moving_average_3"),
                                    ("South", "2013-12-01", "naive_last"),
                                    ("East", "2014-01-01", "ridge")]:
        app.selectbox[0].set_value(market)
        app.selectbox[1].set_value(target)
        app.selectbox[2].set_value(method).run()
        assert not app.exception
        expected = next(c for c in bundle["cases"] if
                        (c["market"], c["forecast_month"], c["method"]) == (market, target, method))
        assert app.metric[0].value == demo.number_vi(expected["prediction"])


def test_demo_does_not_present_stale_warehouse_snapshot(tmp_path, monkeypatch):
    db, outputs = tmp_path / "warehouse.sqlite", tmp_path / "demo"
    load(db_path=db)
    bundle = build_demo_bundle(db)
    bundle["dataset"]["monthly_sha256"] = "stale-snapshot"
    save_demo_bundle(bundle, outputs)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(demo, "DEMO_DIR", outputs)
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not app.exception
    assert "Kho đã thay đổi" in app.warning[0].value
    assert not app.metric
