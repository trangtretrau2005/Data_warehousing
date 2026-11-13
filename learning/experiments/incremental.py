"""TN03: initial, incremental, replay, correction and rejected-row experiments."""

import json
from tempfile import TemporaryDirectory
from pathlib import Path

import pandas as pd

from coffee_dw.config import RESULTS_DIR, SOURCE_PATH
from coffee_dw.warehouse import load


def run() -> dict:
    raw = pd.read_csv(SOURCE_PATH, dtype=str, keep_default_na=False)
    raw_months = pd.to_numeric(raw.Date)
    with TemporaryDirectory(prefix="coffee-incremental-") as temp:
        folder = Path(temp)
        history, new = folder / "history.csv", folder / "new.csv"
        raw.loc[raw_months < raw_months.max()].to_csv(history, index=False)
        latest = raw.loc[raw_months.eq(raw_months.max())].copy()
        latest.to_csv(new, index=False)
        db = folder / "incremental.sqlite"
        initial = load(history, db)
        incremental = load(new, db)
        replay = load(new, db)
        latest.loc[latest.index[0], "Sales"] = str(float(latest.iloc[0].Sales) + 10)
        latest.to_csv(new, index=False)
        correction = load(new, db)
        errors = raw.head(8).copy()
        errors.loc[0, "Sales"], errors.loc[1, "Product"] = "abc", ""
        bad_csv = folder / "invalid.csv"
        errors.to_csv(bad_csv, index=False)
        rejected = load(bad_csv, folder / "rejected.sqlite")
        assert (initial["warehouse_rows"], initial["warehouse_sales"]) == (4071, 784231)
        assert (incremental["warehouse_rows"], incremental["warehouse_sales"]) == (4248, 819811)
        assert replay["warehouse_sales"] == incremental["warehouse_sales"]
        assert (correction["updated_rows"], correction["warehouse_sales"]) == (1, 819821)
        assert (rejected["accepted_rows"], rejected["rejected_rows"], rejected["warehouse_sales"]) == (6, 2, 1139)
        return {"engine": "SQLite reference", "source_modified": False,
                "initial_23_months": initial, "new_month": incremental,
                "replay": replay, "synthetic_correction_plus_10": correction,
                "synthetic_errors": rejected}


if __name__ == "__main__":
    result = run()
    path = RESULTS_DIR / "TN03" / "incremental.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
