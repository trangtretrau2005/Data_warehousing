"""Reproducible answers and honest, participant-only UX summaries for TN11."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from coffee_dw.config import SOURCE_PATH
from coffee_dw.source import read_source


TRIAL_COLUMNS = ["participant_id", "tool", "task", "set", "order", "answer",
                 "correct", "seconds", "help_count", "notes"]
TASK_SETS = {
    "A": {"year": 2012, "state_month": "2012-01-01", "state_market": "Central",
          "gap_month": "2013-08-01"},
    "B": {"year": 2013, "state_month": "2013-01-01", "state_market": "East",
          "gap_month": "2012-08-01"},
}


def _aggregate(data: pd.DataFrame, dimensions: list[str]) -> pd.DataFrame:
    result = data.groupby(dimensions, as_index=False)[["Sales", "BudgetSales", "Profit"]].sum()
    result["Gap"] = result.Sales - result.BudgetSales
    result["BudgetAchievement"] = result.Sales.div(result.BudgetSales.where(result.BudgetSales.ne(0)))
    return result


def build_answer_key(data: pd.DataFrame) -> dict:
    """Compute all answers; no frozen source-specific answer is used by the runner."""
    answers = {}
    for label, config in TASK_SETS.items():
        yearly = data.loc[data.MonthStart.dt.year.eq(config["year"])]
        markets = _aggregate(yearly, ["Market"]).sort_values(["Sales", "Market"], ascending=[False, True])
        scoped = data.loc[data.MonthStart.eq(pd.Timestamp(config["state_month"])) &
                          data.Market.eq(config["state_market"])]
        states = _aggregate(scoped, ["State"]).sort_values(["Gap", "State"])
        month = data.loc[data.MonthStart.eq(pd.Timestamp(config["gap_month"]))]
        gaps = _aggregate(month, ["Market"]).sort_values(["Gap", "Market"])
        if markets.empty or states.empty or gaps.empty:
            raise ValueError(f"Missing source scope for UX set {label}")
        worst = gaps.iloc[0]
        products = _aggregate(month.loc[month.Market.eq(worst.Market)], ["ProductName"])
        products = products.sort_values(["Gap", "ProductName"])
        product = products.iloc[0]
        answers[label] = {
            "T1": {"year": config["year"], "Market": str(markets.iloc[0].Market),
                   "Sales": float(markets.iloc[0].Sales)},
            "T2": {"month": config["state_month"], "Market": config["state_market"],
                   "Sales": float(scoped.Sales.sum()), "BudgetSales": float(scoped.BudgetSales.sum()),
                   "Gap": float(scoped.Sales.sum() - scoped.BudgetSales.sum()),
                   "state_count": len(states), "states": states.to_dict("records")},
            "T3": {"month": config["gap_month"], "Market": str(worst.Market),
                   "Sales": float(worst.Sales), "BudgetSales": float(worst.BudgetSales),
                   "Gap": float(worst.Gap), "ProductName": str(product.ProductName),
                   "ProductGap": float(product.Gap), "product_rows": len(products)},
        }
    return answers


def prepare_acceptance(output: str | Path, source: str | Path = SOURCE_PATH) -> dict:
    """Export source-derived Pivot inputs and facilitator answers, leaving trials empty."""
    source, output = Path(source), Path(output)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    data, rejects = read_source(source)
    if not rejects.empty:
        raise ValueError("Resolve source rejects before freezing a UX dataset")
    answers = build_answer_key(data)
    output.mkdir(parents=True, exist_ok=True)
    # Remove internal trace payloads; keep raw source untouched and all 11 measures.
    data.drop(columns=["RawPayload"]).to_csv(output / "excel_input.csv", index=False,
                                             date_format="%Y-%m-%d", encoding="utf-8-sig")
    _aggregate(data, ["MonthStart", "Market"]).to_csv(
        output / "monthly_market.csv", index=False, date_format="%Y-%m-%d", encoding="utf-8-sig")
    for label, values in answers.items():
        month = data.loc[data.MonthStart.eq(pd.Timestamp(values["T3"]["month"])) &
                         data.Market.eq(values["T3"]["Market"])]
        _aggregate(month, ["Market", "ProductName"]).sort_values(["Gap", "ProductName"]).to_csv(
            output / f"expected_products_{label}.csv", index=False, encoding="utf-8-sig")
    (output / "answer_key.json").write_text(json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8")
    trials = output / "ux_trials.csv"
    # A rerun must not erase an actual human session.
    if not trials.exists():
        pd.DataFrame(columns=TRIAL_COLUMNS).to_csv(trials, index=False, encoding="utf-8-sig")
    after = hashlib.sha256(source.read_bytes()).hexdigest()
    if before != after:
        raise RuntimeError("Source changed during acceptance export")
    generated = ["excel_input.csv", "monthly_market.csv", "expected_products_A.csv",
                 "expected_products_B.csv", "answer_key.json"]
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "source_sha256": before,
        "source_unchanged": True, "source_rows": len(data),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_totals": {name: float(data[name].sum()) for name in ["Sales", "BudgetSales", "Profit"]},
        "task_sets": TASK_SETS, "human_trials_created": 0,
        "status": "protocol_and_answers_prepared_not_human_acceptance",
        "artifacts": {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in generated},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def summarize_trials(path: str | Path) -> tuple[pd.DataFrame, dict]:
    """Validate observed human trials; summarize time only for correct answers."""
    trials = pd.read_csv(path, keep_default_na=False)
    missing = set(TRIAL_COLUMNS) - set(trials.columns)
    if missing:
        raise ValueError(f"Missing trial columns: {sorted(missing)}")
    if trials.empty:
        return pd.DataFrame(columns=["tool", "trials", "correct", "accuracy", "median_correct_seconds", "help_count"]), {
            "status": "not_measured", "participants": 0, "trials": 0,
            "note": "No human trial: no accuracy or speed claim is supported.",
        }
    if trials.participant_id.astype(str).str.strip().eq("").any() or trials.answer.astype(str).str.strip().eq("").any():
        raise ValueError("Every trial needs an anonymous participant and the recorded answer")
    if not set(trials.tool).issubset({"Excel", "Streamlit"}):
        raise ValueError("tool must be Excel or Streamlit")
    if not set(trials.task).issubset({"T1", "T2", "T3"}) or not set(trials["set"]).issubset({"A", "B"}):
        raise ValueError("Use task T1/T2/T3 and set A/B")
    for col in ["correct", "seconds", "help_count", "order"]:
        trials[col] = pd.to_numeric(trials[col], errors="raise")
        if not np.isfinite(trials[col]).all():
            raise ValueError(f"Non-finite {col}")
    if not trials.correct.isin([0, 1]).all() or not trials.order.isin([1, 2]).all():
        raise ValueError("correct must be 0/1, order must be 1/2")
    if trials.seconds.le(0).any() or trials.help_count.lt(0).any() or trials.help_count.mod(1).ne(0).any():
        raise ValueError("seconds must be positive; help_count must be a nonnegative integer")
    if trials.duplicated(["participant_id", "tool", "task"]).any():
        raise ValueError("Repeated participant/tool/task; keep retests in a separate run")
    incomplete = []
    for participant, group in trials.groupby("participant_id"):
        for tool, sub in group.groupby("tool"):
            if sub.order.nunique() != 1 or sub["set"].nunique() != 1:
                raise ValueError(f"Inconsistent order/set within {participant}/{tool}")
        if group.tool.nunique() == 2:
            blocks = group.groupby("tool")[["order", "set"]].first()
            if blocks.order.nunique() != 2 or blocks["set"].nunique() != 2:
                raise ValueError("Paired tools require different order and task set")
        if len(group) != 6:
            incomplete.append(str(participant))
    rows = []
    for tool, group in trials.groupby("tool"):
        good = group.loc[group.correct.eq(1)]
        rows.append({"tool": tool, "trials": len(group), "correct": int(group.correct.sum()),
                     "accuracy": float(group.correct.mean()),
                     "median_correct_seconds": float(good.seconds.median()) if len(good) else np.nan,
                     "help_count": int(group.help_count.sum())})
    return pd.DataFrame(rows), {"status": "observed_trials", "participants": int(trials.participant_id.nunique()),
                               "trials": len(trials), "incomplete_participants": incomplete,
                               "note": "Descriptive only; tools, task sets, order and familiarity can affect the result."}
