"""TN11 answer/export integrity and measured-only UX summaries."""

import json

import pandas as pd
import pytest

from coffee_dw.acceptance import TRIAL_COLUMNS, prepare_acceptance, summarize_trials


def test_answer_export_retains_source_and_never_erases_human_trial(tmp_path):
    manifest = prepare_acceptance(tmp_path)
    answers = json.loads((tmp_path / "answer_key.json").read_text(encoding="utf-8"))
    assert manifest["source_rows"] == 4248 and manifest["source_unchanged"]
    assert manifest["source_totals"] == {"Sales": 819811.0, "BudgetSales": 746160.0, "Profit": 259543.0}
    assert answers["A"]["T3"]["Market"] == "South" and answers["A"]["T3"]["Gap"] == -9
    assert answers["A"]["T3"]["ProductName"] == "Colombian" and answers["A"]["T3"]["ProductGap"] == -268
    assert sum(row["Sales"] for row in answers["A"]["T2"]["states"]) == answers["A"]["T2"]["Sales"]
    trial = tmp_path / "ux_trials.csv"
    assert pd.read_csv(trial).empty
    trial.write_text("preserve recorded human session", encoding="utf-8")
    prepare_acceptance(tmp_path)
    assert trial.read_text(encoding="utf-8") == "preserve recorded human session"


def test_empty_trials_do_not_generate_accuracy_or_timing(tmp_path):
    path = tmp_path / "trials.csv"
    pd.DataFrame(columns=TRIAL_COLUMNS).to_csv(path, index=False)
    summary, audit = summarize_trials(path)
    assert summary.empty and audit["status"] == "not_measured"
    assert audit["participants"] == 0


def _trials():
    return pd.DataFrame([
        ["synthetic_test_fixture", "Excel", "T1", "A", 1, "example", 1, 20, 0, "unit test only"],
        ["synthetic_test_fixture", "Excel", "T2", "A", 1, "example", 0, 100, 1, "unit test only"],
        ["synthetic_test_fixture", "Streamlit", "T1", "B", 2, "example", 1, 15, 0, "unit test only"],
    ], columns=TRIAL_COLUMNS)


def test_summary_uses_correct_trials_only_and_flags_incomplete_pairs(tmp_path):
    path = tmp_path / "trials.csv"
    _trials().to_csv(path, index=False)
    summary, audit = summarize_trials(path)
    excel = summary.set_index("tool").loc["Excel"]
    assert excel.accuracy == .5 and excel.median_correct_seconds == 20
    assert audit["incomplete_participants"] == ["synthetic_test_fixture"]


@pytest.mark.parametrize("column,value", [("seconds", 0), ("seconds", float("inf")),
                                        ("help_count", .5), ("correct", 2), ("tool", "agent")])
def test_invalid_measurements_fail_closed(tmp_path, column, value):
    path = tmp_path / "trials.csv"
    trials = _trials()
    trials[column] = trials[column].astype(object)
    trials.loc[0, column] = value
    trials.to_csv(path, index=False)
    with pytest.raises(ValueError):
        summarize_trials(path)
