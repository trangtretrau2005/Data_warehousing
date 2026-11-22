"""Read-only final receipt for the authorized SSIS -> SQL -> SSAS integration.

Reuses the existing canonical SQL audit rather than generating new test data.
Run only after integrate_ssis_source.ps1 and the existing 17+6 native cases.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import pyodbc

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/native_build_20261120/ssas/integrated_ssis_source"
NEW = "CoffeeDW_Trang_SSIS_TN03_20261120"
NS = {"a": "http://schemas.microsoft.com/analysisservices/2003/engine"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(name):
    return json.loads((OUT / name).read_text(encoding="utf-8-sig"))


def main():
    spec = importlib.util.spec_from_file_location("existing_sql_audit", Path(__file__).with_name("recheck_readonly.py"))
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    frames, profiles = zip(*(audit.read_database(name) for name in audit.DATABASES))
    left, right = (frame.sort_values(list(audit.KEYS)).reset_index(drop=True) for frame in frames)
    pd.testing.assert_frame_equal(left.drop(columns="SourceRow"), right.drop(columns="SourceRow"), check_dtype=False, check_exact=True)
    delta = left.SourceRow.ne(right.SourceRow)
    lineage = left.loc[delta, [*audit.KEYS, "SourceRow"]].rename(columns={"SourceRow": "OriginalSourceRow"})
    lineage["SSISSourceRow"] = right.loc[delta, "SourceRow"].to_numpy()
    lineage.to_csv(OUT / "source_row_lineage_differences.csv", index=False, encoding="utf-8-sig")
    totals = []
    for measure in audit.MEASURES:
        a, b = left[measure].sum(), right[measure].sum()
        if a != b:
            raise RuntimeError("Source amount mismatch: " + measure)
        totals.append({"Measure": measure, "OriginalSQL": str(a), "SSISSource": str(b), "Delta": str(b - a)})
    pd.DataFrame(totals).to_csv(OUT / "all_11_source_measure_totals.csv", index=False, encoding="utf-8-sig")
    cells = [frame.groupby(["MonthStart", "Market"], as_index=False)[list(audit.MEASURES)].sum() for frame in (left, right)]
    pd.testing.assert_frame_equal(*cells, check_exact=True)
    if len(cells[1]) != 96:
        raise RuntimeError("Expected 96 canonical Market-month cells.")
    cells[1].to_csv(OUT / "canonical_ssis_monthly_source.csv", index=False, encoding="utf-8-sig")

    migration, comparison, pivot = (read_json(name) for name in ("migration.json", "comparison.json", "pivot_acceptance/verification.json"))
    if not all(item["status"] == "passed" for item in (migration, comparison, pivot)):
        raise RuntimeError("Native operation or acceptance did not pass.")
    metadata = migration["after"]
    if metadata["relational_database"] != NEW or metadata["state"] != "Processed" or metadata["provider"] != "MSOLEDBSQL":
        raise RuntimeError("Exact processed source/provider read-back is wrong.")
    if metadata["inventory_aggregate"] != "LastChild" or metadata["measure_count"] != 11:
        raise RuntimeError("Native inventory/measure contract changed.")
    if comparison["passed"] != 17 or comparison["case_count"] != 17 or comparison["source_database"] != NEW:
        raise RuntimeError("The fixed 17 cases were not compared against the new source.")
    if pivot["cells_compared"] != 6 or not pivot["exact_transpose"] or pivot["source_database"] != NEW:
        raise RuntimeError("The fixed six pivot cells were not compared against the new source.")
    expected_tables = {"dw_DimDate", "dw_DimLocation", "dw_DimProduct", "dw_FactSalesPerformance"}
    if metadata["dsv_source_id"] != "CoffeeDW" or set(metadata["dsv_tables"]) != expected_tables:
        raise RuntimeError("Deployed DSV bindings are unexpected.")
    for dimension in metadata["dimensions"]:
        if any(dimension[key] != "ReportAndStop" for key in ("key_duplicate", "key_not_found", "null_key", "null_converted")):
            raise RuntimeError("A dimension lost strict error handling.")
    local_sources = {}
    for name in ("CoffeeDW.ds", "CreateCoffeeCubeTrang.xmla", "CoffeeCube.dwproj"):
        path = ROOT / "ssas/CoffeeCubeTrang" / name
        text = path.read_text(encoding="utf-8-sig")
        if "Initial Catalog=" + NEW not in text or "Initial Catalog=CoffeeDW_Trang_20261119" in text:
            raise RuntimeError("Local source mapping does not match deployed integration: " + name)
        local_sources[name] = sha(path)
    local_dsv = ET.parse(ROOT / "ssas/CoffeeCubeTrang/CoffeeDW.dsv").getroot()
    if local_dsv.findtext("a:DataSourceID", namespaces=NS) != metadata["source_id"]:
        raise RuntimeError("Local/deployed DSV datasource IDs differ.")

    conn = pyodbc.connect("DRIVER={ODBC Driver 18 for SQL Server};SERVER=.;DATABASE=" + NEW + ";Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes", timeout=15)
    principal = r"NT Service\MSOLAP$TRANGTRETRAU"
    try:
        cursor = conn.cursor()
        permissions = cursor.execute("SELECT dp.state_desc,dp.permission_name,SCHEMA_NAME(o.schema_id),o.name FROM sys.database_permissions dp JOIN sys.database_principals p ON p.principal_id=dp.grantee_principal_id LEFT JOIN sys.objects o ON dp.class=1 AND o.object_id=dp.major_id WHERE p.name=?", principal).fetchall()
        actual_permissions = {tuple(row) for row in permissions}
        expected_permissions = {("GRANT", "CONNECT", None, None)} | {("GRANT", "SELECT", "dw", table[3:]) for table in expected_tables}
        if actual_permissions != expected_permissions:
            raise RuntimeError("Service principal permissions are not exactly CONNECT plus four table SELECT grants.")
        database_roles = [r[0] for r in cursor.execute("SELECT r.name FROM sys.database_role_members rm JOIN sys.database_principals r ON r.principal_id=rm.role_principal_id JOIN sys.database_principals p ON p.principal_id=rm.member_principal_id WHERE p.name=?", principal)]
        server_roles = [r[0] for r in cursor.execute("SELECT r.name FROM sys.server_role_members rm JOIN sys.server_principals r ON r.principal_id=rm.role_principal_id JOIN sys.server_principals p ON p.principal_id=rm.member_principal_id WHERE p.name=?", principal)]
        if database_roles or server_roles:
            raise RuntimeError("Unexpected explicit server/database role membership.")
    finally:
        conn.close()
    raw = sha(ROOT / "data/raw/Coffee.csv")
    if raw != migration["raw_sha256"] or migration["my_sales_cube_last_processed_before"] != migration["my_sales_cube_last_processed_after"]:
        raise RuntimeError("Unrelated source or cube changed during integration.")
    report = {"status": "passed", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "Existing isolated cube rewired to native SSIS-populated SQL source; no database/cube create/drop",
              "server": migration["server"], "ssas_database": migration["cube_database"], "actual_deployed_source": metadata,
              "profiles": profiles, "business_rows_identical": len(right), "canonical_grain": list(audit.KEYS),
              "canonical_month_market_cells_identical": len(cells[1]), "source_measures_compared": len(audit.MEASURES),
              "source_row_lineage_differences": int(delta.sum()),
              "lineage_note": "SourceRow is relative to each input batch; lineage differences are saved separately. All business keys, dimension attributes and 11 amounts match exactly.",
              "inventory_audit_note": "Source Inventory totals audit stored input amounts only; business Inventory KPI uses LastChild, never a sum across time.",
              "native_cases_passed": comparison["passed"], "native_pivot_cells_passed": pivot["cells_compared"],
              "exact_pivot_transpose": pivot["exact_transpose"], "service_grants": [list(p) for p in sorted(actual_permissions, key=str)],
              "explicit_database_roles": database_roles, "explicit_server_roles": server_roles,
              "local_source_metadata_sha256": local_sources, "unrelated_metadata_unchanged": migration["unrelated_local_metadata_unchanged"],
              "runner_sha256": {p.name: sha(p) for p in sorted(Path(__file__).parent.iterdir()) if p.is_file() and p.suffix in {".py", ".ps1"}},
              "raw_sha256": raw, "my_sales_cube_last_processed_unchanged": migration["my_sales_cube_last_processed_after"],
              "this_verifier_writes_to_database": False,
              "permissions_before_format_note": "The empty pre-grant query result was normalized to valid JSON [] after the PowerShell pipeline serializer emitted an empty file; the original empty file is preserved alongside it. The runner now uses ConvertTo-Json -InputObject.",
              "evidence": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)} for p in sorted(OUT.rglob("*")) if p.is_file() and p not in {OUT / "verification.json", OUT / "final_verification.log"} and not any(part.startswith(("backup_", "runner_backup_")) for part in p.parts)]}
    (OUT / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "business_rows_identical", "canonical_month_market_cells_identical", "source_measures_compared", "source_row_lineage_differences", "native_cases_passed", "native_pivot_cells_passed")}))


if __name__ == "__main__":
    main()
