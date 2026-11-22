"""One authorized native SQL Server rollback probe on the exact SSIS test DB.

The sole injected batch lives inside an uncommitted outer transaction. An
intentional SourceCount mismatch reaches loader error50006 after dimension/fact
updates. The loader's CATCH must roll back that whole transaction. Never commit,
alter a procedure, create a trigger, reset data, or execute SSIS from this script.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
TARGET = "CoffeeDW_Trang_SSIS_TN03_20261120"
BASE = ROOT / "results/native_build_20261120/relational_acceptance/rollback"
RAW = ROOT / "data/raw/Coffee.csv"
RAW_SHA = "929bdcc7fd8f6bf21607618e7474df0683af6412b32b8c5af39a40e89b62ffce"
MANIFEST = ROOT / "ssis/CoffeeETLTrangAcceptance/acceptance_manifest.json"
MARKER = "__ROLLBACK_PROBE__"
MEASURES = ("Sales", "BudgetSales", "Profit", "BudgetProfit", "COGS", "BudgetCOGS",
            "Margin", "BudgetMargin", "Marketing", "Inventory", "TotalExpenses")
EXPECTED_STAR = {"dw.DimDate", "dw.DimLocation", "dw.DimProduct", "dw.FactSalesPerformance"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def quote(name):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_ ]*", name):
        raise ValueError("Unexpected SQL metadata identifier")
    return "[" + name + "]"


def typed(value):
    """Stable lossless encoding of the current schema's scalar query values."""
    if value is None:
        return ["null", None]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, Decimal):
        return ["decimal", format(value, "f")]
    if isinstance(value, (bytes, bytearray)):
        return ["binary", bytes(value).hex()]
    if isinstance(value, (datetime, date)):
        return [type(value).__name__, value.isoformat()]
    if isinstance(value, str):
        return ["str", value]
    raise TypeError(f"Unsupported snapshot scalar: {type(value).__name__}")


def row_bytes(values):
    return (json.dumps([typed(v) for v in values], ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def connect(autocommit=True):
    import pyodbc
    # Process-local ODBC setting: the final connect must create a fresh server
    # session rather than reuse a pooled logical handle from the mutation.
    pyodbc.pooling = False
    cn = pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};SERVER=.;DATABASE=" + TARGET
        + ";Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;APP=TrangLoaderRollbackProbe",
        autocommit=autocommit, timeout=15,
    )
    cn.timeout = 45
    return cn


def query(cn, sql, *parameters):
    cur = cn.cursor()
    try:
        cur.execute(sql, parameters)
        names = [c[0] for c in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]
    finally:
        cur.close()


def metadata(cn):
    columns = query(cn, """SELECT s.name SchemaName,t.name TableName,c.column_id Ordinal,
c.name ColumnName,ty.name DataType,c.max_length MaxLength,c.precision Precision,
c.scale [Scale],c.is_nullable Nullable,c.is_identity IsIdentity,ic.key_ordinal KeyOrdinal
FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
JOIN sys.columns c ON c.object_id=t.object_id JOIN sys.types ty ON ty.user_type_id=c.user_type_id
LEFT JOIN sys.indexes i ON i.object_id=t.object_id AND i.is_primary_key=1
LEFT JOIN sys.index_columns ic ON ic.object_id=t.object_id AND ic.index_id=i.index_id AND ic.column_id=c.column_id
WHERE s.name IN ('dw','audit','stg') ORDER BY s.name,t.name,c.column_id""")
    tables = {}
    for col in columns:
        tables.setdefault(col["SchemaName"] + "." + col["TableName"], []).append(col)
    if not EXPECTED_STAR.issubset(tables):
        raise RuntimeError("Missing required four star tables")
    for name, cols in tables.items():
        if not any(c["KeyOrdinal"] for c in cols):
            raise RuntimeError(f"No deterministic primary-key snapshot order for {name}")
    return tables


def identities(cn):
    return query(cn, """SELECT s.name SchemaName,t.name TableName,c.name ColumnName,
CONVERT(nvarchar(100),c.last_value) LastValue
FROM sys.identity_columns c JOIN sys.tables t ON t.object_id=c.object_id
JOIN sys.schemas s ON s.schema_id=t.schema_id WHERE s.name IN ('dw','audit','stg')
ORDER BY s.name,t.name,c.name""")


def snapshot(cn, folder):
    """Export every column/row under one read transaction, then roll it back."""
    folder.mkdir()
    cn.cursor().execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE; BEGIN TRANSACTION;")
    result = {}
    try:
        tables = metadata(cn)
        save(folder / "schema.json", tables)
        for name, columns in tables.items():
            schema, table = name.split(".")
            projections = []
            for c in columns:
                col = quote(c["ColumnName"])
                # Preserve full server precision; pyodbc datetime objects have
                # only microseconds, while SQL datetime2 may have seven digits.
                if c["DataType"] in {"datetime2", "datetime", "smalldatetime", "datetimeoffset", "time"}:
                    projections.append(f"CONVERT(varchar(48),{col},126) AS {col}")
                elif c["DataType"] == "uniqueidentifier":
                    projections.append(f"CONVERT(binary(16),{col}) AS {col}")
                else:
                    projections.append(col)
            keys = [c["ColumnName"] for c in sorted(columns, key=lambda x: x["KeyOrdinal"] or 9999) if c["KeyOrdinal"]]
            sql = "SELECT " + ",".join(projections) + " FROM " + quote(schema) + "." + quote(table) + " ORDER BY " + ",".join(map(quote, keys))
            (folder / (name + ".sql")).write_text(sql + ";\n", encoding="utf-8")
            cur = cn.cursor().execute(sql)
            digest = hashlib.sha256()
            header = json.dumps({"columns": columns, "primary_key": keys}, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
            digest.update(header)
            count = 0
            path = folder / (name + ".jsonl.gz")
            with gzip.open(path, "wb") as stream:
                stream.write(header)
                while True:
                    rows = cur.fetchmany(500)
                    if not rows:
                        break
                    for row in rows:
                        data = row_bytes(row)
                        stream.write(data)
                        digest.update(data)
                        count += 1
            cur.close()
            result[name] = {"rows": count, "logical_sha256": digest.hexdigest(), "columns": [c["ColumnName"] for c in columns], "file": path.name}
        identity = identities(cn)
        totals = query(cn, "SELECT COUNT_BIG(*) Rows," + ",".join(f"SUM({quote(m)}) {quote(m)}" for m in MEASURES) + " FROM dw.FactSalesPerformance")[0]
        state = query(cn, "SELECT DB_NAME() DatabaseName,@@TRANCOUNT SnapshotTransactions")[0]
        result_metadata = {"tables": result, "identities": identity, "all_11_measure_totals": totals, "database": state["DatabaseName"]}
        save(folder / "summary.json", result_metadata)
        return result_metadata
    finally:
        cn.cursor().execute("IF @@TRANCOUNT>0 ROLLBACK TRANSACTION; SET TRANSACTION ISOLATION LEVEL READ COMMITTED;")


def validate_loader(definition):
    upper = definition.upper()
    ordered = ["SET XACT_ABORT ON", "BEGIN TRANSACTION", "SP_GETAPPLOCK", "UPDATE L SET STATE", "UPDATE F SET SALES", "THROW 50006", "COMMIT TRANSACTION", "BEGIN CATCH", "ROLLBACK TRANSACTION"]
    positions = [upper.find(marker) for marker in ordered]
    if -1 in positions or positions != sorted(positions) or upper.count("THROW 50006") != 1:
        raise RuntimeError("Actual loader no longer has the reviewed update/error/rollback order")
    return dict(zip(ordered, positions))


def is_outer_rollback266(error):
    message = str(error)
    return "Transaction count after EXECUTE" in message and "(266)" in message


def consume_results(cursor, persist, limit=32):
    """Persist each receipt before SQLMoreResults can emit nested-rollback266.

    SQL266 can precede or follow a caller CATCH SELECT. Drain that diagnostic,
    but do not classify it as expected until the caller verifies receipt50006.
    """
    frames, diagnostics = [], []
    for _ in range(limit):
        if cursor.description:
            names = [c[0] for c in cursor.description]
            frames += [dict(zip(names, row)) for row in cursor.fetchall()]
            persist(frames, diagnostics)
        try:
            if not cursor.nextset():
                return frames, diagnostics
        except Exception as exc:
            diagnostics.append({"type": type(exc).__name__, "message": str(exc)})
            persist(frames, diagnostics)
            if not is_outer_rollback266(exc):
                raise
    raise RuntimeError("Too many native resultsets/diagnostics; stop and read back")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Perform the explicitly authorized uncommitted fault injection once")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.execute:
        parser.error("Explicit --execute required for this one rollback-only mutation probe")
    output = (args.output or BASE / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:8])).resolve()
    if BASE.resolve() not in output.parents:
        parser.error("Evidence must be a new child of the rollback evidence folder")
    if output.exists():
        parser.error("Refusing to overwrite any existing rollback evidence")
    output.mkdir(parents=True)
    probe_id = str(uuid4())
    report = {"status": "NOT_EXECUTED", "started_utc": datetime.now(timezone.utc).isoformat(), "database": TARGET,
              "probe_batch_id": probe_id, "scope": "Native T-SQL rollback fault injection; not another SSIS scenario or a production source observation.",
              "hash_semantics": "All columns and rows in PK order; type-tagged exact Unicode/decimals/GUID bytes/full-precision server datetime strings; logical values, not SQL storage pages.",
              "checks": [], "failures": [], "unexpected_errors": []}
    before = after = None
    mutation = None
    definition = None

    def check(name, passed, details=None):
        report["checks"].append({"name": name, "passed": bool(passed), "details": details})
        if not passed:
            report["failures"].append(name)

    try:
        if sha(RAW) != RAW_SHA:
            raise RuntimeError("Immutable source SHA guard failed before any DB mutation")
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
        if manifest["database"] != TARGET or manifest["server"] != ".":
            raise RuntimeError("Acceptance manifest targets a different database")
        source_case = next(c for c in manifest["cases"] if c["number"] == 8)
        report["source_case"] = source_case
        report["raw_sha256_before"] = sha(RAW)
        report["script_sha256"] = sha(__file__)
        with closing(connect()) as read:
            environment = query(read, "SELECT DB_NAME() DatabaseName,@@SERVERNAME ServerName,CONVERT(nvarchar(100),SERVERPROPERTY('ProductVersion')) ProductVersion,@@TRANCOUNT OpenTransactions")[0]
            if environment["DatabaseName"] != TARGET or environment["OpenTransactions"] != 0:
                raise RuntimeError("Exact DB/clean read connection guard failed")
            report["environment"] = environment
            definition = query(read, "SELECT OBJECT_DEFINITION(OBJECT_ID('dw.usp_LoadCoffee')) Definition")[0]["Definition"]
            if not definition:
                raise RuntimeError("Cannot read loader definition")
            (output / "loader_definition_before.sql").write_text(definition, encoding="utf-8")
            (output / "loader_repository_reference.sql").write_bytes((ROOT / "sql/sqlserver/03_load_staging.sql").read_bytes())
            report["loader_statement_order"] = validate_loader(definition)
            triggers = query(read, "SELECT tr.name TriggerName FROM sys.triggers tr JOIN sys.tables t ON t.object_id=tr.parent_id JOIN sys.schemas s ON s.schema_id=t.schema_id WHERE s.name IN ('dw','stg','audit') AND tr.is_disabled=0")
            if triggers:
                raise RuntimeError("Unexpected enabled DML trigger; stop before injection")
            suite_before = query(read, "SELECT * FROM audit.SSISAcceptanceSuite WHERE SuiteID=?", manifest["suite_id"])
            receipts_before = query(read, "SELECT * FROM audit.SSISAcceptanceCase WHERE SuiteID=? ORDER BY CaseNumber", manifest["suite_id"])
            if len(suite_before) != 1 or suite_before[0]["Status"] != "PASS" or len(receipts_before) != 8:
                raise RuntimeError("Original eight-case acceptance guard failed")
            baseline = query(read, "SELECT TOP(1) * FROM stg.CoffeeRaw WHERE BatchID=? AND RejectReason IS NULL ORDER BY SourceRow", source_case["batch_id"])[0]
            if baseline["State"] == MARKER or baseline["Sales"] is None:
                raise RuntimeError("Unexpected source probe row")
            fact = query(read, "SELECT f.*,l.State FROM dw.FactSalesPerformance f JOIN dw.DimLocation l ON l.LocationKey=f.LocationKey JOIN dw.DimProduct p ON p.ProductKey=f.ProductKey WHERE f.DateKey=? AND l.AreaCode=? AND p.ProductName=?", baseline["DateKey"], baseline["AreaCode"], baseline["ProductName"])
            if len(fact) != 1 or any(fact[0][m] != baseline[m] for m in MEASURES):
                raise RuntimeError("Source case8 is not identical to existing fact on all eleven measures")
            report["baseline_source_row"] = baseline
            report["baseline_fact_and_state"] = fact[0]
            before = snapshot(read, output / "before")
            if (before["all_11_measure_totals"]["Rows"], before["all_11_measure_totals"]["Sales"]) != (4248, Decimal(819811)):
                raise RuntimeError("Original warehouse totals guard failed")
        mutation = connect(autocommit=False)
        guard = query(mutation, "SELECT DB_NAME() DatabaseName")[0]
        if guard["DatabaseName"] != TARGET:
            raise RuntimeError("Mutation connection exact DB guard failed")
        mutation.cursor().execute("SET XACT_ABORT ON; IF @@TRANCOUNT=0 BEGIN TRANSACTION;")
        mutation.cursor().execute("INSERT audit.LoadBatch(BatchID,SourceFile,SourceChecksum,SourceCount,Status) VALUES(?,?,?,?,?)", probe_id, "__rollback_probe__case08_count_mismatch", RAW_SHA, 2, "STAGED")
        stage_columns = list(baseline)
        expressions = []
        parameters = []
        for col in stage_columns:
            if col == "BatchID":
                expressions.append("CONVERT(uniqueidentifier,?)"); parameters.append(probe_id)
            elif col == "SourceRow":
                expressions.append("CONVERT(int,1)")
            elif col == "Sales":
                expressions.append("Sales+CONVERT(decimal(19,4),1)")
            elif col == "State":
                expressions.append("CONVERT(nvarchar(100),?)"); parameters.append(MARKER)
            else:
                expressions.append(quote(col))
        stage_sql = "INSERT stg.CoffeeRaw(" + ",".join(map(quote, stage_columns)) + ") SELECT " + ",".join(expressions) + " FROM stg.CoffeeRaw WHERE BatchID=? AND SourceRow=? AND RejectReason IS NULL"
        (output / "probe_insert.sql").write_text(stage_sql + ";\n", encoding="utf-8")
        mutation.cursor().execute(stage_sql, (*parameters, source_case["batch_id"], baseline["SourceRow"]))
        probe = query(mutation, "SELECT * FROM stg.CoffeeRaw WHERE BatchID=?", probe_id)
        expected_probe = dict(baseline, BatchID=probe_id, SourceRow=1, State=MARKER, Sales=baseline["Sales"] + Decimal(1))
        if len(probe) != 1 or any(str(probe[0][k]).lower() != str(v).lower() if k == "BatchID" else probe[0][k] != v for k, v in expected_probe.items()):
            raise RuntimeError("Injected copy does not match exact intended transformation")
        pre_exec = query(mutation, "SELECT @@TRANCOUNT OpenTransactions,XACT_STATE() TransactionState,(SELECT SourceCount FROM audit.LoadBatch WHERE BatchID=?) DeclaredSourceCount,(SELECT COUNT(*) FROM stg.CoffeeRaw WHERE BatchID=?) ActualStageCount", probe_id, probe_id)[0]
        if pre_exec["OpenTransactions"] < 1 or pre_exec["DeclaredSourceCount"] != 2 or pre_exec["ActualStageCount"] != 1:
            raise RuntimeError("Outer transaction/count mismatch not established")
        save(output / "probe_before_execute.json", {"stage_row": probe[0], "transaction": pre_exec, "source_row_note": "Source case8 first valid CSV data row is SourceRow2; the synthetic copy deliberately has SourceRow1. Raw file and RawJson are unchanged."})
        call_sql = """SET NOCOUNT ON;
BEGIN TRY
 EXEC dw.usp_LoadCoffee @BatchID=?;
 SELECT 'UNEXPECTED_SUCCESS' Result,CONVERT(int,0) ErrorNumber,CONVERT(nvarchar(4000),'No exception') ErrorMessage,CONVERT(nvarchar(128),NULL) ErrorProcedure,CONVERT(int,NULL) ErrorLine,@@TRANCOUNT OpenTransactions,XACT_STATE() TransactionState;
END TRY
BEGIN CATCH
 SELECT 'CAUGHT_NATIVE_ERROR' Result,ERROR_NUMBER() ErrorNumber,ERROR_MESSAGE() ErrorMessage,ERROR_PROCEDURE() ErrorProcedure,ERROR_LINE() ErrorLine,@@TRANCOUNT OpenTransactions,XACT_STATE() TransactionState;
END CATCH;"""
        (output / "execute_probe.sql").write_text(call_sql, encoding="utf-8")
        cur = mutation.cursor().execute(call_sql, probe_id)
        def persist_receipts(frames, diagnostics):
            save(output / "native_error_receipt.json", frames)
            save(output / "native_driver_diagnostics.json", diagnostics)
        frames, diagnostics = consume_results(cur, persist_receipts)
        report["native_call_messages"] = list(cur.messages or [])
        cur.close()
        report["native_call_receipts"] = frames
        report["native_driver_diagnostics"] = diagnostics
        save(output / "native_error_receipt.json", frames)
        expected_error = len(frames) == 1 and frames[0].get("ErrorNumber") == 50006 and frames[0].get("ErrorMessage") == "Source row accounting failed" and str(frames[0].get("ErrorProcedure", "")).split(".")[-1] == "usp_LoadCoffee"
        check("exact_native_error50006", expected_error, frames)
        check("loader_catch_rolled_back_entire_outer_transaction", len(frames) == 1 and frames[0].get("OpenTransactions") == 0, {"note": "Explicit transaction count must be zero; XACT_STATE is retained in the receipt because an autocommit SELECT can itself be active.", "receipts": frames})
        check("driver266_only_accepted_with_native50006_receipt", all(is_outer_rollback266(d["message"]) for d in diagnostics) and (not diagnostics or expected_error), diagnostics)
        check("native_final_guard_reached_after_reviewed_dim_and_fact_updates", expected_error and report["loader_statement_order"]["UPDATE F SET SALES"] < report["loader_statement_order"]["THROW 50006"], "Actual unchanged procedure has a unique THROW50006 after both UPDATE statements; probe changes an existing key's Sales and State.")
        report["status"] = "INJECTION_FINISHED_READBACK_REQUIRED"
    except Exception as exc:
        report["unexpected_errors"].append({"type": type(exc).__name__, "message": str(exc)})
    finally:
        if mutation is not None:
            try:
                mutation.rollback()
                report["defensive_final_rollback_called"] = True
            except Exception as exc:
                report["unexpected_errors"].append({"type": "FinalRollbackError", "message": str(exc)})
            finally:
                mutation.close()
        try:
            with closing(connect()) as readback:
                clean = query(readback, "SELECT DB_NAME() DatabaseName,@@TRANCOUNT OpenTransactions,XACT_STATE() TransactionState")[0]
                # XACT_STATE can report the SELECT statement's own autocommit
                # transaction. @@TRANCOUNT is the explicit-transaction guard.
                check("new_connection_transaction_count_zero", clean["DatabaseName"] == TARGET and clean["OpenTransactions"] == 0, clean)
                if before is not None:
                    after = snapshot(readback, output / "after")
                    comparisons = {name: {"same_rows": before["tables"][name]["rows"] == after["tables"].get(name, {}).get("rows"), "same_all_columns_sha256": before["tables"][name]["logical_sha256"] == after["tables"].get(name, {}).get("logical_sha256")} for name in before["tables"]}
                    check("all_dw_audit_stg_tables_identical", set(before["tables"]) == set(after["tables"]) and all(all(v.values()) for v in comparisons.values()), comparisons)
                    check("all_11_measure_totals_identical", before["all_11_measure_totals"] == after["all_11_measure_totals"])
                    check("all_11_fact_measures_and_lineage_in_full_row_hash", all(c in before["tables"]["dw.FactSalesPerformance"]["columns"] for c in (*MEASURES, "BatchID", "SourceRow")))
                    report["identity_state"] = {"before": before["identities"], "after": after["identities"], "unchanged": before["identities"] == after["identities"], "note": "Identity allocation is nontransactional; a gap alone would not be a business-row rollback failure. This probe updates existing dimension/fact keys."}
                residue = query(readback, "SELECT (SELECT COUNT(*) FROM audit.LoadBatch WHERE BatchID=?) AuditRows,(SELECT COUNT(*) FROM stg.CoffeeRaw WHERE BatchID=?) StageRows,(SELECT COUNT(*) FROM audit.RejectedRow WHERE BatchID=?) RejectRows,(SELECT COUNT(*) FROM stg.CoffeeCsvLanding WHERE BatchID=?) LandingRows,(SELECT COUNT(*) FROM dw.FactSalesPerformance WHERE BatchID=?) FactLineageRows,(SELECT COUNT(*) FROM dw.DimLocation WHERE State=?) MarkerRows", probe_id, probe_id, probe_id, probe_id, probe_id, MARKER)[0]
                check("no_probe_batch_staging_reject_landing_fact_or_marker_residue", all(v == 0 for v in residue.values()), residue)
                if definition is not None:
                    current = query(readback, "SELECT OBJECT_DEFINITION(OBJECT_ID('dw.usp_LoadCoffee')) Definition")[0]["Definition"]
                    check("loader_definition_unchanged", current == definition)
                if "source_case" in report:
                    suite_after = query(readback, "SELECT * FROM audit.SSISAcceptanceSuite WHERE SuiteID=?", manifest["suite_id"])
                    receipts_after = query(readback, "SELECT * FROM audit.SSISAcceptanceCase WHERE SuiteID=? ORDER BY CaseNumber", manifest["suite_id"])
                    check("original_eight_case_suite_receipts_unchanged", suite_before == suite_after and receipts_before == receipts_after)
        except Exception as exc:
            report["unexpected_errors"].append({"type": "ReadbackError", "message": str(exc)})
        check("immutable_raw_source_unchanged", sha(RAW) == RAW_SHA)
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        report["status"] = "PASS" if before is not None and after is not None and not report["unexpected_errors"] and not report["failures"] and report.get("native_call_receipts") else "FAIL_STOP_READBACK_REVIEW_REQUIRED"
        save(output / "verification.json", report)
        files = [{"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(output.rglob("*")) if p.is_file()]
        save(output / "manifest.json", {"script_sha256": sha(__file__), "files": files})
    print(json.dumps({"status": report["status"], "probe_batch_id": probe_id, "checks": len(report["checks"]), "failures": report["failures"], "unexpected_errors": report["unexpected_errors"], "output": str(output)}, ensure_ascii=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
