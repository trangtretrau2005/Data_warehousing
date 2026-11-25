"""Create a fresh SSIS experiment DB only; never drops/reuses an existing DB."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from coffee_dw.config import ROOT

DATABASE = "CoffeeDW_Trang_SSIS_TN03_20261120"


def main():
    import pyodbc
    cn = pyodbc.connect("DRIVER={ODBC Driver 18 for SQL Server};SERVER=.;DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;", autocommit=True)
    if cn.cursor().execute("SELECT DB_ID(?)", DATABASE).fetchval() is not None:
        raise RuntimeError("Experiment database already exists; preserve it, do not drop/recreate")
    manifest = {"database": DATABASE, "existed_before": False, "started_utc": datetime.now(timezone.utc).isoformat(), "scripts": []}
    cn.cursor().execute(f"CREATE DATABASE [{DATABASE}]")
    cn.cursor().execute(f"USE [{DATABASE}]")
    paths = [ROOT/"sql/sqlserver"/name for name in ("01_schema.sql", "02_marts.sql", "03_load_staging.sql")]
    paths.append(Path(__file__).with_name("01_raw_landing_and_validation.sql"))
    for path in paths:
        sql = path.read_text(encoding="utf-8-sig").replace("USE CoffeeDW;", f"USE [{DATABASE}];")
        for batch in re.split(r"^\s*GO\s*$", sql, flags=re.M|re.I):
            if not batch.strip(): continue
            cur = cn.cursor().execute(batch)
            while cur.nextset(): pass
        manifest["scripts"].append({"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest["initial_fact_rows"] = cn.cursor().execute("SELECT COUNT(*) FROM dw.FactSalesPerformance").fetchval()
    manifest["initial_landing_rows"] = cn.cursor().execute("SELECT COUNT(*) FROM stg.CoffeeCsvLanding").fetchval()
    manifest["completed_utc"] = datetime.now(timezone.utc).isoformat()
    out = ROOT/"results/native_build_20261120/ssis/initialize.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    cn.close()
    print(json.dumps(manifest,indent=2))


if __name__ == "__main__": main()
