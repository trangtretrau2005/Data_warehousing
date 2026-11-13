from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from coffee_dw import config
from coffee_dw.forecast import run_forecast
from coffee_dw.warehouse import load

APP = Path(__file__).resolve().parents[1] / "apps" / "dashboard" / "app.py"


def test_missing_warehouse_shows_setup_instruction(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "missing.sqlite")
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert "coffee_dw.cli demo" in app.info[0].value


def test_filter_changes_kpis_and_all_pages_render(tmp_path, monkeypatch):
    db = tmp_path / "warehouse.sqlite"
    load(db_path=db)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(config, "RESULTS_DIR", tmp_path)
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not app.exception
    assert app.metric[0].value == "819,811"
    app.select_slider[0].set_range(pd.Timestamp("2012-01-01"), pd.Timestamp("2012-01-01"))
    app.multiselect[0].set_value(["West"]).run()
    assert not app.exception
    assert [m.value for m in app.metric[:3]] == ["10,453", "9,460", "+993"]
    app.multiselect[0].set_value(["East"]).run()
    assert [m.value for m in app.metric[:3]] == ["6,780", "6,180", "+600"]
    app.multiselect[0].set_value(["West"]).run()
    assert app.metric[0].value == "10,453"
    app.radio[0].set_value("Tồn kho và chi phí").run()
    assert not app.exception
    app.radio[0].set_value("Dự báo AI").run()
    assert not app.exception
    assert "coffee_dw.cli forecast" in app.info[0].value
    run_forecast(db, tmp_path / "forecast")
    app.run()
    assert not app.exception
    app.multiselect[0].set_value([]).run()
    assert not app.exception and len(app.info) > 0
