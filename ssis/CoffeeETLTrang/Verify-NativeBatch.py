"""Read-only comparison of native SSIS raw/typed staging with the shared parser."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import re
from uuid import UUID

from coffee_dw.source import read_source, MEASURES, LOCATION_ATTRIBUTES, PRODUCT_ATTRIBUTES


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--batch-id", required=True, type=UUID)
    p.add_argument("--database", default="CoffeeDW_Trang_20261119")
    p.add_argument("--server", default=".")
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if not re.fullmatch(r"CoffeeDW_Trang_[A-Za-z0-9_]+", args.database):
        raise ValueError("Use isolated experiment DB only")
    import pyodbc
    cn = pyodbc.connect(f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={args.server};DATABASE={args.database};Trusted_Connection=yes;TrustServerCertificate=yes;", autocommit=True)
    def fetch(sql, *parameters):
        cursor = cn.cursor().execute(sql, parameters)
        return [dict(zip((d[0] for d in cursor.description), row)) for row in cursor.fetchall()]
    batch_id = str(args.batch_id)
    batch = fetch("SELECT * FROM audit.LoadBatch WHERE BatchID=?", batch_id)[0]
    staging = fetch("SELECT * FROM stg.CoffeeRaw WHERE BatchID=? ORDER BY SourceRow", batch_id)
    rejects = fetch("SELECT SourceRow,Reason FROM audit.RejectedRow WHERE BatchID=? ORDER BY SourceRow", batch_id)
    valid, rejected = read_source(args.source)
    expected = {int(r["SourceRow"]): r for r in valid.to_dict("records")}
    expected_raw = {int(r["SourceRow"]): json.loads(r["RawPayload"]) for r in [*valid.to_dict("records"), *rejected.to_dict("records")]}
    failures = []
    if batch["Status"] != "COMPLETED": failures.append("batch_not_completed")
    if batch["SourceCount"] != len(valid)+len(rejected): failures.append("source_count")
    if batch["AcceptedCount"] != len(valid) or batch["RejectedCount"] != len(rejected): failures.append("accepted_rejected_counts")
    if len(staging) != len(expected_raw): failures.append("staging_count")
    if {r["SourceRow"] for r in rejects} != set(rejected.SourceRow): failures.append("reject_source_rows")
    for row in staging:
        index = row["SourceRow"]
        if json.loads(row["RawJson"]) != expected_raw.get(index): failures.append(f"raw_payload_or_source_order:{index}")
        if index not in expected:
            if not row["RejectReason"]: failures.append(f"missing_reject_reason:{index}")
            continue
        e = expected[index]
        if row["RejectReason"] is not None: failures.append(f"unexpected_reject:{index}")
        for column in MEASURES:
            if row[column] != Decimal(str(e[column])): failures.append(f"measure:{index}:{column}")
        for column in [*LOCATION_ATTRIBUTES, *PRODUCT_ATTRIBUTES, "DateKey"]:
            if row[column] != e[column]: failures.append(f"attribute:{index}:{column}")
        if row["MonthStart"] != e["MonthStart"].date(): failures.append(f"date:{index}")
    warehouse = fetch("SELECT COUNT_BIG(*) Rows,SUM(Sales) Sales,SUM(BudgetSales) BudgetSales,SUM(Profit) Profit FROM dw.FactSalesPerformance")[0]
    report = {"BatchID": batch_id, "source": args.source.name, "database": args.database,
              "batch": batch, "normalized_rows_checked": len(staging),
              "raw_payload_and_row_order_checked": len(staging),
              "all_11_measures_checked_on_accepted_rows": len(valid),
              "warehouse_snapshot": warehouse, "failures": failures, "status": "PASS" if not failures else "FAIL",
              "scope": "Native staging/audit checked against shared parser; no SSAS or UX claim"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    cn.close()
    print(json.dumps({k:v for k,v in report.items() if k not in ("batch",)}, ensure_ascii=False, default=str))
    if failures: raise RuntimeError("Native batch disagrees with shared source parser")


if __name__ == "__main__":
    main()
