"""TN13: measured SQL cuboid cardinalities and a controlled HRU workload replay.

Materializations are ordinary dedicated bench tables. This verifies the HRU
selection mechanism, not automatic indexed-view matching or refresh machinery.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import itertools
from pathlib import Path
import runpy

import pandas as pd

from coffee_dw.config import ROOT, SOURCE_PATH
from run_native_benchmarks import (SET_OPTIONS, execute, rows, run_pairs,
                                   safe_database, write_json)


def run(server, database, output):
    import pyodbc
    if output.exists() and any(output.iterdir()):
        raise RuntimeError("Preserve existing HRU evidence; choose an empty run directory")
    connection = pyodbc.connect(
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};DATABASE={safe_database(database)};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;", autocommit=True, timeout=10)
    output.mkdir(parents=True, exist_ok=True)
    execute(connection, SET_OPTIONS)
    dimensions = {"M": "MonthStart", "R": "Market", "P": "ProductKey"}
    nodes = [tuple(c) for n in range(4) for c in itertools.combinations(dimensions, n)]
    costs = {}
    for node in nodes:
        label = "".join(node) or "ALL"
        columns = ",".join(dimensions[d] for d in node)
        select = f"{columns}," if columns else ""
        group = f" GROUP BY {columns}" if columns else ""
        if rows(connection, f"SELECT OBJECT_ID('bench.HRU_{label}') Id")[0]["Id"] is not None:
            raise RuntimeError("HRU tables already exist; preserve previous evidence and use a fresh experiment database")
        sql = f"SELECT {select}COUNT_BIG(*) N,SUM(SalesAmount) Sales INTO bench.HRU_{label} FROM bench.SalesPlain{group} OPTION(EXPAND VIEWS,MAXDOP 1,MAX_GRANT_PERCENT=1)"
        (output / f"materialize_{label}.sql").write_text(sql, encoding="utf-8")
        execute(connection, sql)
        costs[node] = rows(connection, f"SELECT COUNT_BIG(*) N FROM bench.HRU_{label}")[0]["N"]
    workload = {("M", "R"): 10, ("M", "P"): 4, ("R", "P"): 3, ("M",): 4, ("R",): 2, (): 1}
    base_rows = rows(connection, "SELECT COUNT_BIG(*) N FROM dw.FactSalesPerformance")[0]["N"]
    base_bench = rows(connection, "SELECT COUNT_BIG(*) N FROM bench.SalesPlain")[0]["N"]
    select_views = runpy.run_path(str(ROOT / "learning/experiments/hru.py"))["select_views"]
    rounds = select_views(costs, workload, 300, base_rows)
    selected = [tuple(r["view"]) if r["view"] != "ALL" else () for r in rounds]
    pairs, mappings = {}, []
    for query, weight in workload.items():
        label = "".join(query) or "ALL"
        columns = ",".join(dimensions[d] for d in query)
        select = f"{columns}," if columns else ""
        group = f" GROUP BY {columns}" if columns else ""
        a = f"SELECT {select}COUNT_BIG(*) N,SUM(SalesAmount) Sales FROM bench.SalesPlain{group} OPTION(EXPAND VIEWS)"
        usable = [node for node in selected if set(query).issubset(node)]
        best = min(usable, key=lambda node: costs[node]) if usable else None
        if best is None:
            b, source = a, "BASE"
        else:
            source = "".join(best) or "ALL"
            b = f"SELECT {select}SUM(N) N,SUM(Sales) Sales FROM bench.HRU_{source}{group}"
        pairs[f"TN13_{label}"] = (a, b)
        mappings.append({"query": label, "weight_assumed": weight, "selected_source": source,
                         "model_cost_before_source_rows": base_rows,
                         "model_cost_after_group_rows": costs[best] if best is not None else base_rows})
    pd.DataFrame(rounds).to_csv(output / "hru_rounds.csv", index=False)
    pd.DataFrame(mappings).to_csv(output / "workload_mapping.csv", index=False)
    pd.DataFrame([{"cuboid": "".join(node) or "ALL", "group_rows": cost} for node, cost in costs.items()]).to_csv(output / "cuboids.csv", index=False)
    storage = rows(connection, """SELECT OBJECT_NAME(object_id) ObjectName,
        SUM(reserved_page_count)*8 ReservedKB,SUM(used_page_count)*8 UsedKB
        FROM sys.dm_db_partition_stats WHERE OBJECT_SCHEMA_NAME(object_id)='bench'
        AND OBJECT_NAME(object_id) LIKE 'HRU[_]%' GROUP BY object_id""")
    pd.DataFrame(storage).to_csv(output / "cuboid_storage.csv", index=False)
    write_json(output / "protocol.json", {"database": database, "started_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest(), "base_source_rows": base_rows,
        "query_resource_policy": "All A/B queries MAXDOP 1, MAX_GRANT_PERCENT=1; no server setting changed",
        "base_benchmark_rows": base_bench, "budget_group_rows_assumed": 300,
        "selected_views": [r["view"] for r in rounds], "selected_group_rows": sum(costs[n] for n in selected),
        "materialization": "ordinary bench tables; SQL measured separately from theoretical group-row cost",
        "limitations": "Weights and 300-row budget are assumptions. All 8 candidates materialized only to inspect cardinality/storage; replay uses selected views only. No indexed-view maintenance claim. Shared warm-cache Express machine."})
    try:
        records = run_pairs(connection, pairs, output)
        write_json(output / "actual_plan_summary.json", records)
        from summarize_benchmarks import summarize
        summary = summarize(output / "benchmark_runs.csv")
        summary.to_csv(output / "benchmark_summary.csv", index=False)
        print(summary.to_string(index=False), flush=True)
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default=".")
    parser.add_argument("--database", type=safe_database, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.server, args.database, args.output)
