"""Run auditable TN07--TN10 on an isolated SQL Server experiment database.

Never drops an existing database and never clears a shared server's caches.
Actual plans, not estimated plans, supply server CPU/time and runtime reads.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time
import xml.etree.ElementTree as ET

import pandas as pd

from coffee_dw.config import ROOT, SOURCE_PATH

NS = {"s": "http://schemas.microsoft.com/sqlserver/2004/07/showplan"}
SET_OPTIONS = """SET NOCOUNT ON; SET ANSI_NULLS ON; SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON; SET ARITHABORT ON; SET CONCAT_NULL_YIELDS_NULL ON;
SET QUOTED_IDENTIFIER ON; SET NUMERIC_ROUNDABORT OFF; SET XACT_ABORT ON;"""


def safe_database(value: str) -> str:
    if not re.fullmatch(r"CoffeeDW_Trang_[A-Za-z0-9_]+", value):
        raise ValueError("Use a dedicated database named CoffeeDW_Trang_<run>")
    return value


def drain(cursor):
    result_sets = []
    while True:
        if cursor.description:
            result_sets.append(([c[0] for c in cursor.description], [tuple(r) for r in cursor.fetchall()]))
        if not cursor.nextset():
            break
    return result_sets


def execute(connection, sql):
    connection.timeout = 180
    cursor = connection.cursor()
    return drain(cursor.execute(sql))


def rows(connection, sql):
    sets = execute(connection, sql)
    return [dict(zip(sets[0][0], row)) for row in sets[0][1]] if sets else []


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def plan_metrics(xml: str) -> dict:
    """Sum runtime counters across all threads; retain actual accessed partitions.

    Reads are the sum of nonzero ActualLogicalReads counters in actual RelOps,
    including worktables if SQL Server exposes them. They are plan runtime reads,
    not a substitute for server-wide I/O or physical disk bytes.
    """
    root = ET.fromstring(xml)
    timings = root.findall(".//s:QueryTimeStats", NS)
    if not timings:
        raise ValueError("No runtime QueryTimeStats; an actual plan is required")
    ops, partitions, logical_reads = [], [], 0
    for op in root.findall(".//s:RelOp", NS):
        counters = op.findall("./s:RunTimeInformation/s:RunTimeCountersPerThread", NS)
        logical_reads += sum(int(c.attrib.get("ActualLogicalReads", 0)) for c in counters)
        obj = op.find("./*/s:Object", NS)
        if counters and obj is not None:
            ops.append({"node": op.attrib.get("NodeId"), "physical_op": op.attrib.get("PhysicalOp"),
                        "table": obj.attrib.get("Table"), "index": obj.attrib.get("Index")})
    for access in root.findall(".//s:RunTimePartitionSummary/s:PartitionsAccessed", NS):
        partitions.append({"count": int(access.attrib["PartitionCount"]),
                           "ranges": [dict(x.attrib) for x in access]})
    return {"elapsed_ms": sum(int(t.attrib["ElapsedTime"]) for t in timings),
            "cpu_ms": sum(int(t.attrib["CpuTime"]) for t in timings),
            "logical_reads": logical_reads, "operators": ops, "partitions_accessed": partitions}


def measure(connection, sql: str, plan_path: Path) -> dict:
    start = time.perf_counter_ns()
    cursor = connection.cursor().execute("SET STATISTICS IO ON; SET STATISTICS TIME ON; SET STATISTICS XML ON;\n" + sql + ";\nSET STATISTICS XML OFF; SET STATISTICS IO OFF; SET STATISTICS TIME OFF;")
    result_sets, messages = [], []
    while True:
        if cursor.description:
            result_sets.append(([c[0] for c in cursor.description], [tuple(r) for r in cursor.fetchall()]))
        messages.extend(str(message) for _, message in cursor.messages)
        if not cursor.nextset():
            break
    client_ms = (time.perf_counter_ns() - start) / 1_000_000
    xmls, data = [], []
    for _, result in result_sets:
        if len(result) == 1 and len(result[0]) == 1 and isinstance(result[0][0], str) and "<ShowPlanXML" in result[0][0]:
            xmls.append(result[0][0])
        else:
            data.extend(result)
    if len(xmls) != 1:
        raise RuntimeError(f"Expected one measured statement/plan, observed {len(xmls)}")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(xmls[0], encoding="utf-8")
    plan_path.with_suffix(".messages.txt").write_text("\n".join(messages), encoding="utf-8")
    metrics = plan_metrics(xmls[0])
    canonical = sorted(json.dumps(row, default=str, ensure_ascii=False) for row in data)
    metrics.update(client_elapsed_ms=client_ms, output_rows=len(data), plan_path=plan_path.as_posix(),
                   result_sha256=hashlib.sha256("\n".join(canonical).encode()).hexdigest())
    return metrics


def prepare(connection, database, copies, output):
    # Scripts are applied only inside a newly created, explicitly scoped database.
    for filename in ("01_schema.sql", "02_marts.sql", "03_load_staging.sql"):
        script = (ROOT / "sql/sqlserver" / filename).read_text(encoding="utf-8-sig")
        script = script.replace("USE CoffeeDW;", f"USE [{database}];")
        for batch in re.split(r"^\s*GO\s*$", script, flags=re.M | re.I):
            if batch.strip():
                execute(connection, batch)
    from coffee_dw.sqlserver import load_sqlserver
    previous = os.environ.get("COFFEE_DW_SQLSERVER_CONNECTION")
    os.environ["COFFEE_DW_SQLSERVER_CONNECTION"] = os.environ["TRANG_BENCH_CONNECTION"]
    try:
        load_result = load_sqlserver(SOURCE_PATH)
    finally:
        if previous is None:
            os.environ.pop("COFFEE_DW_SQLSERVER_CONNECTION", None)
        else:
            os.environ["COFFEE_DW_SQLSERVER_CONNECTION"] = previous
    write_json(output / "load.json", load_result)
    for filename in ("05_bench_setup.sql", "06_indexed_view.sql", "07_partition.sql", "08_indexes.sql"):
        script = (ROOT / "sql/sqlserver" / filename).read_text(encoding="utf-8-sig")
        script = script.replace("USE CoffeeDW;", f"USE [{database}];")
        script = script.replace("DECLARE @Copies int=500;", f"DECLARE @Copies int={copies};")
        sets = []
        for batch in re.split(r"^\s*GO\s*$", script, flags=re.M | re.I):
            if batch.strip():
                sets.extend(execute(connection, batch))
        write_json(output / "setup" / f"{filename}.json", sets)
    execute(connection, "SELECT * INTO bench.WriteA FROM bench.SalesPlain; SELECT * INTO bench.WriteB FROM bench.SalesPlain;")
    execute(connection, """CREATE VIEW bench.vWriteAgg WITH SCHEMABINDING AS
    SELECT MonthStart,Market,ProductKey,COUNT_BIG(*) N,SUM(SalesAmount) Sales
    FROM bench.WriteB GROUP BY MonthStart,Market,ProductKey;""")
    execute(connection, "CREATE UNIQUE CLUSTERED INDEX CX_vWriteAgg ON bench.vWriteAgg(MonthStart,Market,ProductKey);")
    for table in ("SalesPlain", "SalesPart", "IdxA", "IdxB", "WriteA", "WriteB"):
        execute(connection, f"UPDATE STATISTICS bench.{table} WITH FULLSCAN;")
    print("PREPARED " + database, flush=True)


def reconcile(connection, copies, output):
    totals = []
    differences = []
    group = "MonthStart,Market,LocationKey,ProductKey"
    reference = f"SELECT {group},COUNT_BIG(*) N,SUM(SalesAmount) Sales FROM bench.SalesPlain GROUP BY {group}"
    for table in ("SalesPlain", "SalesPart", "IdxA", "IdxB", "WriteA", "WriteB"):
        total = rows(connection, f"SELECT COUNT_BIG(*) Rows,SUM(SalesAmount) Sales FROM bench.{table}")[0]
        total["table"] = table
        totals.append(total)
        if total["Rows"] != 4248 * copies or total["Sales"] != Decimal(819811) * copies:
            raise RuntimeError(f"Unexpected cardinality/totals in {table}")
        query = f"SELECT {group},COUNT_BIG(*) N,SUM(SalesAmount) Sales FROM bench.{table} GROUP BY {group}"
        for label, left, right in (("base_minus_variant", reference, query), ("variant_minus_base", query, reference)):
            n = rows(connection, f"SELECT COUNT_BIG(*) N FROM ({left} EXCEPT {right}) q OPTION(EXPAND VIEWS,MAXDOP 1,MAX_GRANT_PERCENT=1)")[0]["N"]
            differences.append({"table": table, "direction": label, "differences": n})
            if n:
                raise RuntimeError(f"EXCEPT reconciliation failed for {table}")
    pd.DataFrame(totals).to_csv(output / "table_totals.csv", index=False)
    pd.DataFrame(differences).to_csv(output / "except_two_way.csv", index=False)
    return totals


def workloads(connection):
    location = rows(connection, "SELECT LocationKey FROM dw.DimLocation WHERE AreaCode=N'719'")[0]["LocationKey"]
    product = rows(connection, "SELECT ProductKey FROM dw.DimProduct WHERE ProductName=N'Amaretto'")[0]["ProductKey"]
    pairs = {
        "TN08_read": (
            "SELECT MonthStart,Market,ProductKey,SUM(SalesAmount) Sales FROM bench.SalesPlain GROUP BY MonthStart,Market,ProductKey OPTION(EXPAND VIEWS)",
            "SELECT MonthStart,Market,ProductKey,Sales FROM bench.vSalesAgg WITH(NOEXPAND)"),
    }
    for label, lo, hi in (("month", "20121001", "20121101"), ("all", "20120101", "20140101")):
        pairs[f"TN09_{label}"] = tuple(
            f"SELECT Market,SUM(SalesAmount) Sales FROM bench.{table} WHERE MonthStart>='{lo}' AND MonthStart<'{hi}' GROUP BY Market OPTION(RECOMPILE,EXPAND VIEWS)"
            for table in ("SalesPlain", "SalesPart"))
    pairs["TN10_narrow"] = tuple(
        f"SELECT MonthStart,SUM(SalesAmount) Sales FROM bench.{table} WHERE LocationKey={location} AND ProductKey={product} AND MonthStart>='20120101' AND MonthStart<'20120401' GROUP BY MonthStart OPTION(RECOMPILE)"
        for table in ("IdxA", "IdxB"))
    pairs["TN10_broad"] = tuple(f"SELECT SUM(SalesAmount) Sales FROM bench.{table}" for table in ("IdxA", "IdxB"))
    pairs["TN08_insert"] = tuple(
        f"BEGIN TRANSACTION; INSERT bench.{table} SELECT d.MonthStart,l.Market,f.LocationKey,f.ProductKey,f.Sales FROM dw.FactSalesPerformance f JOIN dw.DimDate d ON d.DateKey=f.DateKey JOIN dw.DimLocation l ON l.LocationKey=f.LocationKey; ROLLBACK TRANSACTION"
        for table in ("WriteA", "WriteB"))
    selectivity = rows(connection, f"""SELECT COUNT_BIG(*) MatchedRows,
        CAST(COUNT_BIG(*) AS float)/(SELECT COUNT_BIG(*) FROM bench.IdxA) Selectivity
        FROM bench.IdxA WHERE LocationKey={location} AND ProductKey={product}
        AND MonthStart>='20120101' AND MonthStart<'20120401'""")[0]
    return pairs, {"LocationKey": location, "ProductKey": product, **selectivity}


def run_pairs(connection, pairs, output, existing=None):
    records = [] if existing is None else existing
    expected = {}
    for experiment, queries in pairs.items():
        # A common query-level resource policy avoids memory starvation on a
        # shared Express instance. This never changes server configuration.
        bounded = []
        for sql in queries:
            if "OPTION(" in sql:
                sql = sql.replace("OPTION(", "OPTION(MAXDOP 1,MAX_GRANT_PERCENT=1,")
            elif "ROLLBACK TRANSACTION" in sql:
                sql = sql.replace("; ROLLBACK TRANSACTION", " OPTION(MAXDOP 1,MAX_GRANT_PERCENT=1); ROLLBACK TRANSACTION")
            else:
                sql += " OPTION(MAXDOP 1,MAX_GRANT_PERCENT=1)"
            bounded.append(sql)
        queries = tuple(bounded)
        write_json(output / "queries" / f"{experiment}.json", dict(zip(("A", "B"), queries)))
        for warmup, count in ((True, 3), (False, 15)):
            for number in range(1, count + 1):
                for index in ((0, 1) if number % 2 else (1, 0)):
                    variant = "AB"[index]
                    name = f"{experiment}_{'warmup' if warmup else 'run'}_{number:02d}_{variant}"
                    record = measure(connection, queries[index], output / "plans" / f"{name}.sqlplan")
                    signature = (record["output_rows"], record["result_sha256"])
                    if experiment in expected and signature != expected[experiment]:
                        raise RuntimeError(f"A/B output mismatch in {name}")
                    expected[experiment] = signature
                    record.update(experiment=experiment, variant=variant, warmup=warmup, run_number=number)
                    records.append(record)
                    pd.DataFrame([{k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in records]).to_csv(output / "benchmark_runs.csv", index=False)
        print(f"MEASURED {experiment}: 3 warm-up + 15 runs per variant", flush=True)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default=".")
    parser.add_argument("--database", required=True, type=safe_database)
    parser.add_argument("--copies", type=int, default=500)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("all", "prepare", "measure"), default="all")
    args = parser.parse_args()
    if not 1 <= args.copies <= 500:
        parser.error("copies must be between 1 and 500")
    import pyodbc
    if args.output.exists() and args.phase != "measure" and any(args.output.iterdir()):
        raise RuntimeError("Output directory is not empty; choose a new run directory")
    if args.phase == "measure" and (args.output / "benchmark_runs.csv").exists():
        raise RuntimeError("Recorded runs already exist; preserve them and choose a new output directory")
    args.output.mkdir(parents=True, exist_ok=True)
    base = f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={args.server};Trusted_Connection=yes;TrustServerCertificate=yes;"
    master = pyodbc.connect(base + "DATABASE=master;", autocommit=True, timeout=10)
    present = rows(master, "SELECT name FROM sys.databases")
    exists = args.database in {row["name"] for row in present}
    if args.phase != "measure":
        if exists:
            raise RuntimeError("Database already exists; choose a fresh name, or --phase measure to reuse")
        execute(master, f"CREATE DATABASE [{args.database}]")
    elif not exists:
        raise RuntimeError("Database does not exist; prepare first")
    connection_string = base + f"DATABASE={args.database};"
    connection = pyodbc.connect(connection_string, autocommit=True, timeout=10)
    execute(connection, SET_OPTIONS)
    os.environ["TRANG_BENCH_CONNECTION"] = connection_string
    meta = {"started_utc": datetime.now(timezone.utc).isoformat(), "database": args.database,
            "engine": rows(connection, "SELECT CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(40)) ProductVersion,CAST(SERVERPROPERTY('Edition') AS nvarchar(100)) Edition"),
            "engine_resources": rows(connection, "SELECT cpu_count,physical_memory_kb,committed_kb,committed_target_kb FROM sys.dm_os_sys_info"),
            "platform": platform.platform(), "python": platform.python_version(), "pyodbc": pyodbc.version,
            "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "source_sha256": hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest(), "copies": args.copies,
            "cache_policy": "warm cache; no global flush; 3 warm-up/variant, 15 AB/BA measured runs/variant",
            "query_resource_policy": "All measured A/B queries MAXDOP 1, MAX_GRANT_PERCENT=1; shared Express memory pressure; no server setting changed",
            "measurement": "actual STATISTICS XML plan QueryTimeStats + ActualLogicalReads; client elapsed separately includes result/plan transfer; millisecond server resolution",
            "warning": "Shared development computer; not an isolated production performance laboratory"}
    write_json(args.output / "environment.json", meta)
    try:
        if args.phase != "measure":
            prepare(connection, args.database, args.copies, args.output)
        totals = reconcile(connection, args.copies, args.output)
        if args.phase == "prepare":
            return
        pairs, parameters = workloads(connection)
        write_json(args.output / "parameters.json", parameters)
        records = run_pairs(connection, pairs, args.output)
        # Rollbacks must preserve counts/totals after measuring write maintenance.
        reconcile(connection, args.copies, args.output)
        storage = rows(connection, """SELECT OBJECT_SCHEMA_NAME(object_id) SchemaName,
            OBJECT_NAME(object_id) ObjectName,index_id,SUM(reserved_page_count)*8 ReservedKB,
            SUM(used_page_count)*8 UsedKB FROM sys.dm_db_partition_stats
            WHERE OBJECT_SCHEMA_NAME(object_id)='bench' GROUP BY object_id,index_id""")
        pd.DataFrame(storage).to_csv(args.output / "storage.csv", index=False)
        write_json(args.output / "actual_plan_summary.json", records)
        from summarize_benchmarks import summarize
        summary = summarize(args.output / "benchmark_runs.csv")
        summary.to_csv(args.output / "benchmark_summary.csv", index=False)
        meta.update(completed_utc=datetime.now(timezone.utc).isoformat(), status="measured",
                    records=len(records), table_totals=totals,
                    source_unchanged=meta["source_sha256"] == hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest())
        write_json(args.output / "environment.json", meta)
        print(summary.to_string(index=False), flush=True)
    finally:
        connection.close()
        master.close()


if __name__ == "__main__":
    main()
