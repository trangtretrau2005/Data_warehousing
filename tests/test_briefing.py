import copy
import importlib.util
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from coffee_dw import briefing, config, demo, tuning_study
from coffee_dw.warehouse import load


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    folder=tmp_path_factory.mktemp("research_briefing")
    db=folder/"warehouse.sqlite"
    research=folder/"tuning"
    load(db_path=db)
    tuning_study.run_study(output=research,render=False)
    bundle,tables=briefing.build_briefing(db,research)
    return db,research,bundle,tables


def test_all_cases_have_origin_safe_evidence_and_selected_formula(prepared):
    _,_,bundle,tables=prepared
    checks=tables["02_story/case_checks"]
    assert len(checks)==48 and checks.Selected.sum()==16
    assert checks.OriginBeforeTarget.all() and checks.ValidationBeforeTarget.all()
    assert checks.ValidationRows.eq(6).all()
    assert tables["01_reconciliation/monthly_reconciliation"].Pass.sum()==96
    assert tables["02_story/formula_inputs"].shape[0]==48
    for case in bundle["cases"]:
        history=case["story"]["validation_history"]
        mae=np.mean([abs(r["prediction"]-r["actual"]) for r in history])
        assert mae==pytest.approx(case["validation_market"]["MAE"],abs=1e-8)
        if case["story"]["is_selected"]:
            assert np.mean([r["sales"] for r in case["story"]["inputs"]])==pytest.approx(case["prediction"])
            assert all(r["month"]<case["forecast_month"] for r in case["story"]["inputs"])
            assert len(case["chapters"])==3
    briefing.validate_briefing(bundle)


def test_disagreement_between_warehouse_and_research_blocks_publication(prepared):
    table=prepared[3]["01_reconciliation/monthly_reconciliation"]
    left=table[["Market","MonthStart","SalesWarehouse"]].rename(columns={"SalesWarehouse":"Sales"})
    right=table[["Market","MonthStart","SalesResearch"]].rename(columns={"SalesResearch":"Sales"})
    left.loc[left.index[0],"Sales"]+=1
    with pytest.raises(ValueError,match="chưa khớp"):
        briefing.reconcile_monthly(left,right)


@pytest.mark.parametrize("method", ["naive_last", "moving_average_3", "ridge"])
def test_download_report_has_calculation_for_every_method(prepared, method):
    bundle = prepared[2]
    case = next(c for c in bundle["cases"] if c["market"] == "West" and c["forecast_month"] == "2014-01-01" and c["method"] == method)
    result = briefing.case_markdown(case, bundle)
    assert "12/2013" in result and "11.883" in result
    assert "| Tháng validation | Actual | Dự báo |" in result
    assert "04/2013" in result and "09/2013" in result
    if method == "ridge":
        assert "Hệ số thang gốc" in result and "Tái dựng:" in result
    elif method == "naive_last":
        assert "× 1" in result
    else:
        assert "1/3" in result and "11.593" in result


def test_modified_research_file_is_rejected(prepared,tmp_path):
    folder=tmp_path/"modified"
    shutil.copytree(prepared[1],folder)
    with (folder/"02_validation/leaderboard.csv").open("a",encoding="utf-8") as handle:
        handle.write("changed")
    with pytest.raises(ValueError,match="bị thiếu/đổi"):
        briefing.read_research(folder)


def test_target_actual_value_does_not_enter_selected_narration(prepared):
    bundle=prepared[2]
    case=next(c for c in bundle["cases"] if c["story"]["is_selected"] and c["actual"] is not None)
    changed=copy.deepcopy(case)
    changed["actual"]+=1000000
    assert briefing.narrative(case,bundle["research"])==briefing.narrative(changed,bundle["research"])


def test_loader_detects_corrupted_formula_even_if_old_additive_explanation_matches(prepared,tmp_path):
    bundle=copy.deepcopy(prepared[2])
    case=next(c for c in bundle["cases"] if c["story"]["is_selected"])
    case["story"]["inputs"][0]["sales"]+=10
    path=demo.save_demo_bundle(bundle,tmp_path)
    with pytest.raises(ValueError,match="Công thức"):
        demo.load_demo_bundle(path)


def test_filtered_markdown_keeps_future_actual_missing(prepared):
    bundle=prepared[2]
    case=next(c for c in bundle["cases"] if c["market"]=="West" and c["forecast_month"]=="2014-01-01" and c["story"]["is_selected"])
    result=briefing.case_markdown(case,bundle)
    assert "11.593,00" in result
    assert "Chưa có actual" in result
    assert "11.596" in result and "11.300" in result and "11.883" in result


def test_integrated_app_defaults_to_selected_and_filter_roundtrip(prepared,tmp_path,monkeypatch):
    db,_,bundle,_=prepared
    demo.save_demo_bundle(bundle,tmp_path)
    monkeypatch.setattr(config,"DB_PATH",db)
    monkeypatch.setattr(demo,"DEMO_DIR",tmp_path)
    app_path=config.ROOT/"apps/forecast_demo/app.py"
    app=AppTest.from_file(str(app_path),default_timeout=25).run()
    assert not app.exception and not app.warning
    assert app.selectbox[2].value=="moving_average_3"
    assert app.selectbox[1].value=="2014-01-01"
    for market in ["West","East","West"]:
        app.selectbox[0].set_value(market).run()
        expected=next(c for c in bundle["cases"] if c["market"]==market and c["forecast_month"]=="2014-01-01" and c["story"]["is_selected"])
        assert not app.exception and app.metric[0].value==demo.number_vi(expected["prediction"])


def test_archived_artifacts_and_live_bundle_agree(prepared,tmp_path):
    spec=importlib.util.spec_from_file_location("run_briefing_test",config.ROOT/"experiments/briefing/run.py")
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    result=runner.run(prepared[0],prepared[1],tmp_path/"evidence",tmp_path/"live",render=False)
    assert result["cases"]==48 and result["selected_cases"]==16 and result["reconciled_cells"]==96
    assert result["source_sha256"]==result["source_sha256_after"]
    snapshot=json.loads((tmp_path/"evidence/bundle_snapshot.json").read_text(encoding="utf-8"))
    live=demo.load_demo_bundle(tmp_path/"live/bundle.json")
    assert snapshot==live and result["bundle_sha256"]==briefing.sha(tmp_path/"live/bundle.json")
    for item in result["files"]:
        assert briefing.sha(tmp_path/"evidence"/item["path"])==item["sha256"]
