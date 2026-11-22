"""Compare actual ADOMD SELECT exports with independently queried SQL values."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "results/native_build_20261120/ssas/integrated_ssis_source"


def normalized(name):
    parts = re.findall(r"\[([^]]+)\]", str(name))
    return re.sub(r"[^a-z0-9]", "", (parts[-1] if parts else str(name)).lower())


def caption(value):
    parts = re.findall(r"\[([^]]+)\]", str(value))
    return parts[-1] if parts else str(value)


def main():
    bundle = json.loads((EVIDENCE / "acceptance_cases.json").read_text(encoding="utf-8"))
    require(bundle["source_database"] == "CoffeeDW_Trang_SSIS_TN03_20261120", "Expected-source catalog guard failed.")
    execution = json.loads((EVIDENCE / "mdx_actual/execution.json").read_text(encoding="utf-8-sig"))
    executed = {case["id"]: case for case in execution["results"]}
    results = []
    for case in bundle["cases"]:
        result = {"id": case["id"], "status": "failed"}
        try:
            if executed.get(case["id"], {}).get("status") != "executed":
                raise ValueError("MDX query did not execute successfully.")
            expected = pd.read_csv(ROOT / case["sql_expected_csv"], encoding="utf-8-sig")
            actual = pd.read_csv(EVIDENCE / "mdx_actual" / (case["id"] + ".csv"), encoding="utf-8-sig")
            key = expected.columns[0]
            expected_members = set(expected[key].astype(str))
            # ADOMD flattened rowsets can include ancestor columns for a user
            # hierarchy. Resolve the actual leaf caption by the expected key
            # population instead of assuming that the first field is the leaf.
            member_columns = [name for name in actual.columns if "[Measures]" not in name and
                              set(actual[name].map(caption)) == expected_members]
            if not member_columns and len(expected) == len(actual) == 1 and all("[Measures]" in name for name in actual.columns):
                # ADOMD omits the All-member caption field in a flattened
                # single-All rowset. Its measure values are still compared.
                actual[key] = expected[key].astype(str).iloc[0]
                result["single_all_row_caption_omitted_by_adomd"] = True
            else:
                require(bool(member_columns), f"Cannot identify row-member field {key}.")
                preferred = [name for name in member_columns if "MEMBER_CAPTION" in name.upper()]
                actual[key] = actual[(preferred or member_columns)[0]].map(caption)
            require(expected[key].is_unique and actual[key].is_unique, "Duplicate row keys.")
            require(set(actual[key]) == set(expected[key]), "Missing or unexpected member rows.")
            expected = expected.set_index(key).sort_index()
            actual = actual.set_index(key).sort_index()
            differences = {}
            for column in expected.columns:
                matching = [name for name in actual.columns if normalized(name) == normalized(column)]
                require(len(matching) == 1, f"Cannot identify unique measure column {column}: {list(actual.columns)}")
                values = pd.to_numeric(actual[matching[0]], errors="raise")
                comparison = pd.to_numeric(expected[column], errors="raise")
                tolerance = 0.000001 if column in {"BudgetAchievement", "ProfitMargin"} else 0.00005
                require(np.allclose(values, comparison, atol=tolerance, rtol=0, equal_nan=True), f"Numeric mismatch in {column}.")
                delta = (values - comparison).abs()
                differences[column] = float(delta.max()) if delta.notna().any() else None
            result.update(status="passed", rows=len(expected), measures=len(expected.columns), max_abs_difference=differences)
        except Exception as exc:
            result["error"] = str(exc)
        results.append(result)
    report = {"status": "passed" if all(x["status"] == "passed" for x in results) else "failed",
              "timestamp_utc": datetime.now(timezone.utc).isoformat(), "cases": results, "case_count": len(results),
              "passed": sum(r["status"] == "passed" for r in results), "database": bundle["database"],
              "source_database": bundle["source_database"],
              "verification": "actual read-only ADOMD results versus independent SQL results; no server writes"}
    (EVIDENCE / "comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if report["status"] != "passed":
        raise SystemExit(1)


def require(condition, message):
    if not condition:
        raise ValueError(message)


if __name__ == "__main__":
    main()
