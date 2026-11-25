"""Prepare isolated native SSIS scenarios. Never modifies the source or any DB."""
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from coffee_dw.config import ROOT, SOURCE_PATH
from coffee_dw.source import read_source


def main():
    output = ROOT / "results/native_build_20261120/ssis/fixtures"
    output.mkdir(parents=True, exist_ok=True)
    before = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
    with SOURCE_PATH.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns, rows = reader.fieldnames, list(reader)
    latest = max(Decimal(row["Date"]) for row in rows)
    first23 = [dict(row) for row in rows if Decimal(row["Date"]) < latest]
    final_month = [dict(row) for row in rows if Decimal(row["Date"]) == latest]
    invalid = [dict(row) for row in rows[:8]]
    invalid[0]["Sales"] = "abc"
    invalid[1]["Product"] = ""
    correction = [dict(row) for row in rows]
    correction[0]["Sales"] = str(Decimal(correction[0]["Sales"]) + 10)
    invalid_full = [dict(row) for row in rows]
    invalid_full[0]["Sales"] = "abc"
    cases = {"first_23_months": first23, "month_201312": final_month,
             "invalid_8_rows": invalid, "correction_sales_plus_10": correction,
             "invalid_full_one_numeric": invalid_full}
    manifest = {"source_sha256": before, "cases": {}}
    for name, records in cases.items():
        path = output / f"{name}.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\r\n")
            writer.writeheader()
            writer.writerows(records)
        valid, rejected = read_source(path)
        manifest["cases"][name] = {"rows": len(records), "accepted": len(valid),
            "rejected": len(rejected), "valid_sales": float(valid.Sales.sum()) if len(valid) else 0,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest["source_unchanged"] = before == hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    assert manifest["cases"]["first_23_months"]["rows"] == 4071
    assert manifest["cases"]["invalid_8_rows"]["accepted"] == 6
    assert manifest["cases"]["invalid_8_rows"]["valid_sales"] == 1139
    assert manifest["source_unchanged"]
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
