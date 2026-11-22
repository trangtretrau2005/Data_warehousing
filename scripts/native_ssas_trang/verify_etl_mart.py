"""Capture SELECT-only ETL/mart acceptance for one exact isolated native database.

No schema/data/permission mutation, stored-procedure execution, or SSAS action.
TN05 missing groups are query-only CTE fixtures, never new business observations.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys

import pyodbc

from coffee_dw.source import MEASURES, LOCATION_ATTRIBUTES, PRODUCT_ATTRIBUTES, read_source


ROOT = Path(__file__).resolve().parents[2]
TARGET = "CoffeeDW_Trang_SSIS_TN03_20261120"
BASE = ROOT / "results/native_build_20261120/relational_acceptance"
MANIFEST = ROOT / "ssis/CoffeeETLTrangAcceptance/acceptance_manifest.json"
SOURCE = ROOT / "data/raw/Coffee.csv"
FACT_FROM = """FROM dw.FactSalesPerformance f
JOIN dw.DimDate d ON d.DateKey=f.DateKey
JOIN dw.DimLocation l ON l.LocationKey=f.LocationKey
JOIN dw.DimProduct p ON p.ProductKey=f.ProductKey"""
SUMS = ",".join(f"SUM({name}) [{name}]" for name in MEASURES)
FSUMS = ",".join(f"SUM(f.{name}) [{name}]" for name in MEASURES)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decimal(value):
    return Decimal(str(value)) if value is not None else None


def aggregate(records, keys, measures=MEASURES):
    result = {}
    for row in records:
        key = tuple(row[k] for k in keys)
        values = result.setdefault(key, {m: Decimal(0) for m in measures})
        for measure in measures:
            values[measure] += decimal(row[measure])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=TARGET)
    parser.add_argument("--output", type=Path, default=BASE)
    args = parser.parse_args()
    if args.database != TARGET:
        parser.error(f"Exact isolated target required: {TARGET}")
    output = args.output.resolve()
    if output != BASE.resolve() and BASE.resolve() not in output.parents:
        parser.error("Output must stay inside results/native_build_20261120/relational_acceptance")
    if output.exists() and any(output.iterdir()):
        parser.error("Refusing to overwrite an existing evidence directory; choose a fresh child output")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    if manifest["database"] != TARGET or manifest["server"] != ".":
        parser.error("Manifest is not bound to the exact local isolated target")
    output.mkdir(parents=True, exist_ok=True)
    (output / "queries").mkdir()
    (output / "definitions").mkdir()
    checks = []
    query_log = []
    source_hash_before = sha(SOURCE)

    def save_json(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    def check(name, passed, details=None):
        checks.append({"name": name, "passed": bool(passed), "details": details})

    connection = pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};SERVER=.;DATABASE=" + TARGET
        + ";Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;APP=TrangReadOnlyETLMartAcceptance",
        autocommit=True, readonly=True, timeout=15,
    )

    def capture(name, sql, parameters=()):
        # Every executed statement is a literal SELECT/CTE. No EXEC/DDL/DML/SELECT INTO.
        if not re.match(r"^\s*(SELECT|WITH)\b", sql, flags=re.I):
            raise ValueError("Only SELECT/CTE capture statements are permitted")
        if re.search(r"\b(?:INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|EXEC(?:UTE)?|DBCC)\b", sql, flags=re.I):
            raise ValueError("Mutation/execution keyword in a read-only capture statement")
        if re.search(r"\bINTO\b", sql, flags=re.I):
            raise ValueError("SELECT INTO is not permitted")
        (output / "queries" / f"{name}.sql").write_text(sql.strip() + "\n", encoding="utf-8")
        query_log.append({"name": name, "parameters": list(parameters)})
        cursor = connection.cursor()
        cursor.execute(sql, tuple(parameters))
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
        save_json(output / f"{name}.json", rows)
        if rows and all(not isinstance(value, (dict, list)) for value in rows[0].values()):
            with (output / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
        return rows

    try:
        environment = capture("environment", """SELECT DB_NAME() DatabaseName,
@@SERVERNAME ServerName,CONVERT(nvarchar(100),SERVERPROPERTY('ProductVersion')) ProductVersion,
CONVERT(nvarchar(200),SERVERPROPERTY('Edition')) Edition,SYSUTCDATETIME() CapturedUTC,
@@TRANCOUNT OpenTransactions""")[0]
        if environment["DatabaseName"] != TARGET:
            raise RuntimeError("Connected to an unexpected database")
        check("exact_database_guard", environment["DatabaseName"] == TARGET)
        before = capture("fact_before", f"SELECT COUNT_BIG(*) Rows,{SUMS} FROM dw.FactSalesPerformance")[0]
        indexes = capture("unique_indexes", """SELECT s.name SchemaName,t.name TableName,
i.name IndexName,i.type_desc IndexType,i.is_primary_key IsPrimaryKey,
i.is_unique_constraint IsUniqueConstraint,i.is_unique IsUnique,i.is_disabled IsDisabled,
i.has_filter HasFilter,c.name ColumnName,ic.key_ordinal KeyOrdinal
FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
JOIN sys.indexes i ON i.object_id=t.object_id
JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
WHERE s.name='dw' AND t.name IN ('DimDate','DimLocation','DimProduct','FactSalesPerformance')
AND i.is_unique=1 AND ic.key_ordinal>0
ORDER BY t.name,i.name,ic.key_ordinal""")
        unique = {}
        for row in indexes:
            key = (row["TableName"], row["IndexName"])
            unique.setdefault(key, {"columns": [], "enabled": True, "unfiltered": True})
            unique[key]["columns"].append(row["ColumnName"])
            unique[key]["enabled"] &= not row["IsDisabled"]
            unique[key]["unfiltered"] &= not row["HasFilter"]
        required_keys = {
            "FactSalesPerformance": [("DateKey", "LocationKey", "ProductKey")],
            "DimDate": [("DateKey",), ("MonthStart",)],
            "DimLocation": [("LocationKey",), ("AreaCode",)],
            "DimProduct": [("ProductKey",), ("ProductName",)],
        }
        for table, keys in required_keys.items():
            for columns in keys:
                found = any(t == table and tuple(v["columns"]) == columns and v["enabled"] and v["unfiltered"] for (t, _), v in unique.items())
                check(f"enabled_unique:{table}:{','.join(columns)}", found)
        fact_pk = [r for r in indexes if r["TableName"] == "FactSalesPerformance" and r["IsPrimaryKey"]]
        check("fact_primary_key_exact_grain", [r["ColumnName"] for r in fact_pk] == ["DateKey", "LocationKey", "ProductKey"] and all(not r["IsDisabled"] for r in fact_pk))
        foreign_keys = capture("foreign_keys", """SELECT fk.name ConstraintName,
ps.name ParentSchema,pt.name ParentTable,pc.name ParentColumn,
rs.name ReferencedSchema,rt.name ReferencedTable,rc.name ReferencedColumn,
fk.is_disabled IsDisabled,fk.is_not_trusted IsNotTrusted
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id=fk.object_id
JOIN sys.tables pt ON pt.object_id=fk.parent_object_id
JOIN sys.schemas ps ON ps.schema_id=pt.schema_id
JOIN sys.columns pc ON pc.object_id=pt.object_id AND pc.column_id=fkc.parent_column_id
JOIN sys.tables rt ON rt.object_id=fk.referenced_object_id
JOIN sys.schemas rs ON rs.schema_id=rt.schema_id
JOIN sys.columns rc ON rc.object_id=rt.object_id AND rc.column_id=fkc.referenced_column_id
WHERE ps.name='dw' AND pt.name='FactSalesPerformance' ORDER BY pc.name""")
        expected_fks = {("DateKey", "DimDate", "DateKey"), ("LocationKey", "DimLocation", "LocationKey"),
                        ("ProductKey", "DimProduct", "ProductKey"), ("BatchID", "LoadBatch", "BatchID")}
        actual_fks = {(r["ParentColumn"], r["ReferencedTable"], r["ReferencedColumn"]) for r in foreign_keys}
        check("four_expected_fact_foreign_keys", actual_fks == expected_fks)
        check("foreign_key_target_schemas", all(r["ReferencedSchema"] == ("audit" if r["ParentColumn"] == "BatchID" else "dw") for r in foreign_keys))
        check("foreign_keys_enabled_and_trusted", len(foreign_keys) == 4 and all(not r["IsDisabled"] and not r["IsNotTrusted"] for r in foreign_keys))
        definitions = capture("deployed_definitions", """SELECT s.name SchemaName,o.name ObjectName,
o.type_desc ObjectType,m.definition Definition FROM sys.objects o
JOIN sys.schemas s ON s.schema_id=o.schema_id JOIN sys.sql_modules m ON m.object_id=o.object_id
WHERE (s.name='dw' AND o.name='usp_LoadCoffee') OR
(s.name='mart' AND o.name IN ('vw_Detail','vw_MarketPeriod','vw_MarketProductPeriod'))
ORDER BY s.name,o.name""")
        by_name = {}
        for item in definitions:
            name = item["SchemaName"] + "." + item["ObjectName"]
            definition = item["Definition"] or ""
            by_name[name] = " ".join(definition.upper().split())
            (output / "definitions" / f"{name}.sql").write_text(definition, encoding="utf-8")
        check("four_deployed_objects_readable", len(by_name) == 4 and all(by_name.values()))
        loader = by_name.get("dw.usp_LoadCoffee", "")
        transaction_tokens = ("SET XACT_ABORT ON", "BEGIN TRANSACTION", "COMMIT TRANSACTION", "ROLLBACK TRANSACTION", "BEGIN TRY", "BEGIN CATCH")
        check("loader_transaction_control_deployed", all(token in loader for token in transaction_tokens),
              "Definition inspection plus successful native receipts; not a forced-failure rollback experiment")
        ordered_tokens = ("BEGIN TRANSACTION", "INSERT DW.DIMDATE", "INSERT DW.DIMLOCATION", "INSERT DW.DIMPRODUCT", "INTO #MAPPED", "UPDATE F SET", "INSERT DW.FACTSALESPERFORMANCE", "COMMIT TRANSACTION")
        positions = [loader.find(token) for token in ordered_tokens]
        check("dimensions_map_before_fact_inside_transaction", all(p >= 0 for p in positions) and positions == sorted(positions), dict(zip(ordered_tokens, positions)))
        orphans = capture("orphans_and_grain", """SELECT
(SELECT COUNT_BIG(*) FROM dw.FactSalesPerformance f LEFT JOIN dw.DimDate d ON d.DateKey=f.DateKey WHERE d.DateKey IS NULL) DateOrphans,
(SELECT COUNT_BIG(*) FROM dw.FactSalesPerformance f LEFT JOIN dw.DimLocation l ON l.LocationKey=f.LocationKey WHERE l.LocationKey IS NULL) LocationOrphans,
(SELECT COUNT_BIG(*) FROM dw.FactSalesPerformance f LEFT JOIN dw.DimProduct p ON p.ProductKey=f.ProductKey WHERE p.ProductKey IS NULL) ProductOrphans,
(SELECT COUNT_BIG(*) FROM dw.FactSalesPerformance f LEFT JOIN audit.LoadBatch b ON b.BatchID=f.BatchID WHERE b.BatchID IS NULL) BatchOrphans,
(SELECT COUNT_BIG(*) FROM (SELECT DateKey,LocationKey,ProductKey FROM dw.FactSalesPerformance GROUP BY DateKey,LocationKey,ProductKey HAVING COUNT_BIG(*)<>1) q) DuplicateFactGroups,
(SELECT COUNT_BIG(*) FROM dw.DimDate) DateRows,
(SELECT COUNT_BIG(*) FROM dw.DimLocation) LocationRows,
(SELECT COUNT_BIG(*) FROM dw.DimProduct) ProductRows""")[0]
        check("zero_orphans_and_duplicate_fact_grains", all(orphans[name] == 0 for name in ("DateOrphans", "LocationOrphans", "ProductOrphans", "BatchOrphans", "DuplicateFactGroups")), orphans)
        check("expected_dimensions_24_156_13", [orphans[n] for n in ("DateRows", "LocationRows", "ProductRows")] == [24, 156, 13])
        joined = capture("joined_fact_totals", f"SELECT COUNT_BIG(*) Rows,{FSUMS} {FACT_FROM}")[0]
        check("fact_join_preserves_rows_and_all_11_sums", before == joined and before["Rows"] == 4248)
        valid, rejected = read_source(SOURCE)
        source_records = valid.to_dict("records")
        source_totals = {name: sum((decimal(r[name]) for r in source_records), Decimal(0)) for name in MEASURES}
        check("final_fact_all_11_sums_match_original", len(rejected) == 0 and all(before[name] == source_totals[name] for name in MEASURES), source_totals)
        detail = capture("mart_detail", "SELECT * FROM mart.vw_Detail ORDER BY DateKey,AreaCode,ProductName")
        expected_detail = {(r["DateKey"], r["AreaCode"], r["ProductName"]): r for r in source_records}
        mismatch = []
        attributes = [*LOCATION_ATTRIBUTES, *PRODUCT_ATTRIBUTES]
        seen = set()
        for row in detail:
            key = (row["DateKey"], row["AreaCode"], row["ProductName"])
            expected = expected_detail.get(key)
            if expected is None or key in seen:
                mismatch.append({"key": key, "reason": "missing source key or duplicate mart grain"})
            elif any(row[a] != expected[a] for a in attributes) or any(row[m] != decimal(expected[m]) for m in MEASURES) or row["MonthStart"] != expected["MonthStart"].date():
                mismatch.append({"key": key, "reason": "dimension/date/measure mismatch"})
            seen.add(key)
        check("mart_detail_4248_rows_all_attributes_and_measures_match", len(detail) == 4248 and set(expected_detail) == seen and not mismatch, mismatch[:10])
        month_rows = capture("mart_market_period", "SELECT * FROM mart.vw_MarketPeriod ORDER BY MonthStart,Market")
        month_expected = aggregate(source_records, ("DateKey", "Market"))
        month_mismatch = []
        for row in month_rows:
            key = (int(row["MonthStart"].strftime("%Y%m%d")), row["Market"])
            expected = month_expected.get(key)
            if expected is None:
                month_mismatch.append(str(key)); continue
            ratio = expected["Sales"] / expected["BudgetSales"] if expected["BudgetSales"] else None
            if any(row[m] != expected[m] for m in ("Sales", "BudgetSales", "Profit")) or row["Gap"] != expected["Sales"] - expected["BudgetSales"] or (ratio is None and row["BudgetAchievement"] is not None) or (ratio is not None and (row["BudgetAchievement"] is None or abs(row["BudgetAchievement"] - ratio) > Decimal("0.000001"))):
                month_mismatch.append(str(key))
        check("monthly_market_96_cells_and_forecast_input", len(month_rows) == len(month_expected) == 96 and len({(r['MonthStart'], r['Market']) for r in month_rows}) == 96 and not month_mismatch, month_mismatch)
        product_rows = capture("mart_market_product_period", "SELECT * FROM mart.vw_MarketProductPeriod ORDER BY MonthStart,Market,ProductName")
        product_expected = aggregate(source_records, ("DateKey", "Market", "ProductName"))
        product_mismatch = []
        for row in product_rows:
            key = (int(row["MonthStart"].strftime("%Y%m%d")), row["Market"], row["ProductName"])
            expected = product_expected.get(key)
            if expected is None or any(row[m] != expected[m] for m in ("Sales", "BudgetSales", "Profit")) or row["Gap"] != expected["Sales"] - expected["BudgetSales"]:
                product_mismatch.append(str(key))
        check("product_mart_cells_and_grain", len(product_rows) == len(product_expected) and len({(r['MonthStart'], r['Market'], r['ProductName']) for r in product_rows}) == len(product_expected) and not product_mismatch, product_mismatch[:10])
        state_rows = capture("mart_state_product_totals", f"SELECT DateKey,Market,State,ProductName,{SUMS} FROM mart.vw_Detail GROUP BY DateKey,Market,State,ProductName ORDER BY DateKey,Market,State,ProductName")
        state_expected = aggregate(source_records, ("DateKey", "Market", "State", "ProductName"))
        check("state_product_all_11_sums_match", len(state_rows) == len(state_expected) and all(tuple(r[k] for k in ("DateKey", "Market", "State", "ProductName")) in state_expected and all(r[m] == state_expected[tuple(r[k] for k in ("DateKey", "Market", "State", "ProductName"))][m] for m in MEASURES) for r in state_rows))
        batch_checks = []
        for case in manifest["cases"]:
            batch_id = case["batch_id"]
            audit = capture(f"batch_{case['number']:02d}_audit", "SELECT * FROM audit.LoadBatch WHERE BatchID=?", (batch_id,))[0]
            stage = capture(f"batch_{case['number']:02d}_valid", f"SELECT COUNT_BIG(*) Rows,{SUMS} FROM stg.CoffeeRaw WHERE BatchID=? AND RejectReason IS NULL", (batch_id,))[0]
            mapped = capture(f"batch_{case['number']:02d}_mapped", f"SELECT COUNT_BIG(*) Rows,{','.join(f'SUM(v.{m}) [{m}]' for m in MEASURES)} FROM stg.CoffeeRaw v JOIN dw.DimDate d ON d.DateKey=v.DateKey AND d.MonthStart=v.MonthStart JOIN dw.DimLocation l ON l.AreaCode=v.AreaCode JOIN dw.DimProduct p ON p.ProductName=v.ProductName WHERE v.BatchID=? AND v.RejectReason IS NULL", (batch_id,))[0]
            accepted, errors = read_source(case["source_path"])
            expected_sums = {m: sum((decimal(v) for v in accepted[m]), Decimal(0)) for m in MEASURES}
            passed = (audit["Status"] == "COMPLETED" and audit["SourceCount"] == audit["AcceptedCount"] + audit["RejectedCount"] and audit["AcceptedCount"] == audit["InsertedCount"] + audit["UpdatedCount"] + audit["UnchangedCount"] and audit["AcceptedCount"] == len(accepted) and audit["RejectedCount"] == len(errors) and stage == mapped and stage["Rows"] == len(accepted) and all(stage[m] == expected_sums[m] for m in MEASURES) and sha(case["source_path"]) == case["source_sha256"])
            check(f"batch_{case['number']:02d}_accounting_and_mapping_11_sums", passed)
            batch_checks.append({"case": case["number"], "batch_id": batch_id, "passed": passed, "accepted": len(accepted), "rejected": len(errors), "valid_rows_before_join": stage["Rows"], "valid_rows_after_join": mapped["Rows"]})
        ctes = """WITH Actual AS (SELECT MonthStart,Market,SUM(Sales) Sales FROM mart.vw_Detail GROUP BY MonthStart,Market),
Budget AS (SELECT MonthStart,Market,SUM(BudgetSales) BudgetSales FROM mart.vw_Detail GROUP BY MonthStart,Market)
"""
        full = capture("tn05_full_outer_baseline", ctes + """SELECT COALESCE(a.MonthStart,b.MonthStart) MonthStart,COALESCE(a.Market,b.Market) Market,
a.Sales,b.BudgetSales,a.Sales-b.BudgetSales Gap,CASE WHEN a.MonthStart IS NULL THEN 1 ELSE 0 END MissingActual,
CASE WHEN b.MonthStart IS NULL THEN 1 ELSE 0 END MissingBudget FROM Actual a FULL OUTER JOIN Budget b
ON a.MonthStart=b.MonthStart AND a.Market=b.Market ORDER BY MonthStart,Market""")
        check("tn05_independent_aggregate_full_join_96", len(full) == 96 and all(r["MissingActual"] == r["MissingBudget"] == 0 for r in full) and sum(r["Sales"] for r in full) == before["Sales"] and sum(r["BudgetSales"] for r in full) == before["BudgetSales"])
        missing = capture("tn05_query_only_missing_fixture", ctes.rstrip() + """,
BudgetFixture AS (SELECT MonthStart,Market,BudgetSales FROM Budget WHERE NOT(MonthStart=CONVERT(date,'20120101') AND Market=N'West')
UNION ALL SELECT CONVERT(date,'20140101'),N'West',CONVERT(decimal(38,4),1000))
SELECT COALESCE(a.MonthStart,b.MonthStart) MonthStart,COALESCE(a.Market,b.Market) Market,
a.Sales,b.BudgetSales,a.Sales-b.BudgetSales Gap,CASE WHEN a.MonthStart IS NULL THEN 1 ELSE 0 END MissingActual,
CASE WHEN b.MonthStart IS NULL THEN 1 ELSE 0 END MissingBudget FROM Actual a FULL OUTER JOIN BudgetFixture b
ON a.MonthStart=b.MonthStart AND a.Market=b.Market WHERE a.MonthStart IS NULL OR b.MonthStart IS NULL
ORDER BY MonthStart,Market""")
        check("tn05_missing_groups_preserve_null_and_flags", len(missing) == 2 and missing[0]["Sales"] == 10453 and missing[0]["BudgetSales"] is None and missing[0]["MissingBudget"] == 1 and missing[1]["Sales"] is None and missing[1]["BudgetSales"] == 1000 and missing[1]["MissingActual"] == 1 and all(r["Gap"] is None for r in missing), "CTE-only teaching fixture matching SQL11; same CSV split, not two real upstream facts or a deployed stored mart")
        fanout = capture("tn05_incorrect_fanout", ctes + """SELECT d.MonthStart,d.Market,COUNT_BIG(*) DetailRows,
SUM(d.Sales) Sales,MAX(b.BudgetSales) CorrectBudget,SUM(b.BudgetSales) IncorrectRepeatedBudget
FROM mart.vw_Detail d JOIN Budget b ON d.MonthStart=b.MonthStart AND d.Market=b.Market
GROUP BY d.MonthStart,d.Market ORDER BY d.MonthStart,d.Market""")
        check("tn05_fanout_demonstrated_96_groups", len(fanout) == 96 and all(r["IncorrectRepeatedBudget"] == r["CorrectBudget"] * r["DetailRows"] and r["IncorrectRepeatedBudget"] > r["CorrectBudget"] for r in fanout))
        zero = capture("zero_budget_real_slice", """SELECT SUM(Sales) Sales,SUM(BudgetSales) BudgetSales,
SUM(Sales)/NULLIF(SUM(BudgetSales),0) BudgetAchievement FROM mart.vw_Detail
WHERE DateKey=20120101 AND AreaCode=N'702' AND ProductName=N'Green Tea'""")[0]
        check("zero_budget_is_null", zero["Sales"] == 17 and zero["BudgetSales"] == 0 and zero["BudgetAchievement"] is None and "NULLIF(SUM(BUDGETSALES),0)" in by_name.get("mart.vw_MarketPeriod", ""))
        inventory = capture("inventory_latest_selected_period", """WITH Latest AS
(SELECT MAX(MonthStart) MonthStart FROM dw.DimDate WHERE MonthStart BETWEEN CONVERT(date,'20130101') AND CONVERT(date,'20130201'))
SELECT x.MonthStart, v.Market,SUM(v.Inventory) Inventory FROM Latest x JOIN mart.vw_Detail v ON v.MonthStart=x.MonthStart
GROUP BY x.MonthStart,v.Market ORDER BY v.Market""")
        expected_inventory = aggregate([r for r in source_records if r["DateKey"] == 20130201], ("Market",), ("Inventory",))
        check("inventory_latest_selected_month_matches_source", len(inventory) == 4 and all(r["MonthStart"].strftime("%Y%m%d") == "20130201" and r["Inventory"] == expected_inventory[(r["Market"],)]["Inventory"] for r in inventory), "SUM Inventory across all24 months above is only a join-preservation statistic, not a business KPI")
        empty_inventory = capture("inventory_selected_latest_missing_no_fallback", """WITH SelectedPeriods AS
(SELECT CONVERT(date,'20130101') MonthStart UNION ALL SELECT CONVERT(date,'20130801')),
Latest AS (SELECT MAX(MonthStart) MonthStart FROM SelectedPeriods)
SELECT MAX(x.MonthStart) SelectedLastMonth,SUM(v.Inventory) Inventory FROM Latest x
LEFT JOIN mart.vw_Detail v ON v.MonthStart=x.MonthStart AND v.AreaCode=N'720' AND v.ProductName=N'Chamomile'""")[0]
        check("inventory_missing_latest_returns_null", empty_inventory["SelectedLastMonth"].strftime("%Y%m%d") == "20130801" and empty_inventory["Inventory"] is None, "Consumer SELECT policy; Inventory is not a stateful field on vw_MarketPeriod")
        forecast_count = capture("forecast_storage_scope", "SELECT COUNT_BIG(*) ForecastRows FROM ml.ForecastSales")[0]
        after = capture("fact_after", f"SELECT COUNT_BIG(*) Rows,{SUMS} FROM dw.FactSalesPerformance")[0]
        check("fact_snapshot_unchanged_during_readonly_capture", before == after)
        check("source_file_unchanged", source_hash_before == sha(SOURCE))
        summary = {
            "status": "PASS" if all(item["passed"] for item in checks) else "FAIL",
            "created_utc": datetime.now(timezone.utc).isoformat(), "database": TARGET,
            "read_only": True, "driver_readonly_requested": True, "executed_statement_policy": "SELECT/CTE only; no EXEC, DDL, DML, SELECT INTO or SSAS command",
            "script_sha256": sha(__file__), "raw_sha256": source_hash_before,
            "suite_id": manifest["suite_id"], "manifest_sha256": sha(MANIFEST),
            "environment": environment, "fact": before, "joined_fact": joined,
            "orphans_and_grain": orphans, "monthly_market_groups": len(month_rows),
            "product_mart_groups": len(product_rows), "state_product_groups": len(state_rows),
            "batch_checks": batch_checks, "tn05_missing_fixture": missing,
            "forecast_storage": forecast_count, "checks": checks,
            "native_rollback_fault_injection": "Not performed by this SELECT-only script. The 22-test JUnit includes SQLite rollback and live-SQL rollback cleanup; neither is claimed as native loader fault-injection proof.",
            "limitations": [
                "TN05 actual/budget are independently aggregated measures from the same supplied CSV; missing/plan-only groups are explicitly query-only CTE fixtures. No new stored mart/tables or real upstream fact were deployed.",
                "Monthly Market Sales is verified as forecast input; this does not publish or validate forecast rows in this isolated ETL database.",
                "Inventory business checks select the last period first; all-period Inventory totals serve only as arithmetic row-preservation checks.",
                "SELECT-only audit observes current deployed constraints/definitions and committed data; it does not demonstrate a forced-failure transaction rollback, SSAS Browser UI, or human UX.",
            ],
        }
        save_json(output / "query_log.json", query_log)
        save_json(output / "summary.json", summary)
        report = ["# Nghiệm thu quan hệ/mart chỉ đọc —20/11/2026", "",
                  f"Trạng thái: **{summary['status']}**; database đúng đích `{TARGET}`; {len(checks)} phép kiểm; {len(query_log)} SELECT/CTE.",
                  "", "Có guard exact DB và yêu cầu ODBC readonly. Không EXEC loader, không DDL/DML, không schema/permission/cube change.",
                  "", "Các file queries/ lưu câu SQL thực chạy; JSON/CSV lưu kết quả. definitions/ là văn bản định nghĩa đã đọc, không phải script đã thực thi.", "",
                  "## Phạm vi đã kiểm", "",
                  f"- Fact/join: {before['Rows']} dòng;11 tổng số đo khớp nguồn và không đổi trước/sau JOIN.",
                  "- PK/FK/UNIQUE: đọc sys catalog; bốn FK fact enabled/trusted; zero orphans và zero duplicate grain.",
                  f"- Mart tháng–Market: {len(month_rows)} ô; mart Product: {len(product_rows)} ô; nhóm State/Product: {len(state_rows)}; đối chiếu nguồn theo từng ô.",
                  "- Tám batch native: accounting, valid staging→dimension mapping và11 tổng không fan-out.",
                  "- TN05: FULL OUTER JOIN sau aggregate hai phía; fixture CTE thiếu budget và plan-only giữ NULL/flags; nối budget tổng vào detail được đo là sai.",
                  "- Mẫu ngân sách0 trả NULL; Inventory lấy kỳ cuối trước khi lọc dữ liệu thiếu, không fallback.",
                  "", "## Giới hạn", ""]
        report.extend("- " + item for item in summary["limitations"])
        report.extend(["- " + summary["native_rollback_fault_injection"], "", "Xem summary.json cho từng phép kiểm, hash và số liệu đầy đủ."])
        (output / "analysis.md").write_text("\n".join(report) + "\n", encoding="utf-8")
        artifacts = [{"path": str(path.relative_to(output)), "bytes": path.stat().st_size, "sha256": sha(path)} for path in sorted(output.rglob("*")) if path.is_file()]
        save_json(output / "manifest.json", {"script_sha256": sha(__file__), "files": artifacts})
        print(json.dumps({"status": summary["status"], "database": TARGET, "checks": len(checks), "failures": [c for c in checks if not c["passed"]], "queries": len(query_log), "output": str(output)}, ensure_ascii=True, default=str))
        if summary["status"] != "PASS":
            raise SystemExit(1)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
