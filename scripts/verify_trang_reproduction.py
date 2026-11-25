"""Reproduce the reference pipeline in a new isolated database on this working tree.

This does not claim a clean checkout, does not reset Git, and never overwrites the
serving warehouse. Each run gets its own directory and retains its audit files.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import traceback
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd

from coffee_dw.config import DB_PATH, SOURCE_PATH
from coffee_dw.forecast import run_forecast
from coffee_dw.serving import native_forecast_frames
from coffee_dw.source import GRAIN, MEASURES, profile, read_source
from coffee_dw.warehouse import load, read_detail


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(output: Path, source: Path = SOURCE_PATH):
    output, source = Path(output).resolve(), Path(source).resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    run_dir = output / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    db_path = run_dir / "isolated_warehouse.sqlite"
    forecast_dir = run_dir / "forecast"
    require(not db_path.exists(), "Database tái lập phải là đường dẫn mới.")
    require(db_path != Path(DB_PATH).resolve(), "Không dùng kho phục vụ làm kho tái lập.")
    log_path = run_dir / "execution.jsonl"
    def event(stage, **details):
        entry = {"timestamp_utc": utc(), "stage": stage, **details}
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False, allow_nan=False) + "\n")
        print(json.dumps(entry, ensure_ascii=False))
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()
    source_before = sha(source)
    serving_db = Path(DB_PATH).resolve()
    serving_before = sha(serving_db) if serving_db.exists() else None
    code_files = sorted({*ROOT.glob("src/**/*.py"), *ROOT.glob("scripts/*.py"), *ROOT.glob("apps/**/*.py"), ROOT / "pyproject.toml"})
    code_before = {p.relative_to(ROOT).as_posix(): sha(p) for p in code_files if "__pycache__" not in p.parts}
    metadata = {"run_id": run_id, "started_utc": utc(), "execution_context": "isolated data reproduction on the current working tree",
                "clean_checkout_verified": False, "git_commit": git("rev-parse", "HEAD"), "git_branch": git("branch", "--show-current"),
                "git_status": git("status", "--porcelain=v1", "-uall").splitlines(), "python": platform.python_version(),
                "sqlite_engine": sqlite3.sqlite_version,
                "packages": {name: importlib.metadata.version(name) for name in ("coffee-dw", "numpy", "pandas", "scikit-learn", "streamlit", "pytest")},
                "code_sha256": code_before, "source_path": str(source), "source_sha256_before": source_before,
                "serving_warehouse_existed_before": serving_before is not None, "serving_warehouse_sha256_before": serving_before}
    metadata["working_tree_dirty"] = bool(metadata["git_status"])
    write_json(run_dir / "environment.json", metadata)
    event("start", run_id=run_id, working_tree_dirty=metadata["working_tree_dirty"], clean_checkout_verified=False)
    try:
        source_profile = profile(source)
        write_json(run_dir / "source_profile.json", source_profile)
        normalized, rejected = read_source(source)
        require(len(normalized) == 4248 and rejected.empty, "Snapshot gốc phải có 4248 dòng hợp lệ, không reject.")
        require(not normalized.duplicated(GRAIN).any(), "Nguồn trùng grain.")
        require(normalized.MonthStart.nunique() == 24 and normalized.Market.nunique() == 4, "Sai phạm vi snapshot nguồn.")
        event("source_verified", rows=len(normalized), months=24, markets=4, rejected=0)

        first_load = load(source, db_path)
        require(first_load["status"] == "completed" and first_load["inserted_rows"] == 4248, "Nạp kho mới phải chèn 4248 dòng.")
        write_json(run_dir / "first_load.json", first_load)
        detail = read_detail(db_path)
        require(len(detail) == 4248 and not detail.duplicated(GRAIN).any(), "Kho không bảo toàn số dòng/grain.")
        dimensions = ["DateKey", "AreaCode", "ProductName", "MonthStart", "State", "Market", "MarketSize", "ProductLine", "ProductType", "Type", "SourceRow"]
        comparison_columns = dimensions + list(MEASURES)
        pd.testing.assert_frame_equal(normalized[comparison_columns].sort_values(GRAIN).reset_index(drop=True),
                                      detail[comparison_columns].sort_values(GRAIN).reset_index(drop=True),
                                      check_dtype=False, atol=0, rtol=0)
        measures = pd.DataFrame({"Measure": MEASURES, "SourceTotal": normalized[MEASURES].sum().to_numpy(), "WarehouseTotal": detail[MEASURES].sum().to_numpy()})
        measures["Delta"] = measures.WarehouseTotal - measures.SourceTotal
        require(measures.Delta.eq(0).all(), "Tổng 11 số đo không khớp.")
        for measure, expected in (("Sales", 819811), ("BudgetSales", 746160), ("Profit", 259543)):
            require(float(detail[measure].sum()) == expected, f"Sai tổng tham chiếu {measure}.")
        measures.to_csv(run_dir / "measure_totals.csv", index=False, encoding="utf-8-sig")
        source_cells = normalized.groupby(["Market", "MonthStart"], as_index=False)[MEASURES].sum()
        warehouse_cells = detail.groupby(["Market", "MonthStart"], as_index=False)[MEASURES].sum()
        reconciliation = source_cells.merge(warehouse_cells, on=["Market", "MonthStart"], how="outer", validate="one_to_one", suffixes=("Source", "Warehouse"), indicator=True)
        require(len(reconciliation) == 96 and reconciliation._merge.eq("both").all(), "Không đủ 96 ô đối soát.")
        for measure in MEASURES:
            reconciliation[f"{measure}Delta"] = reconciliation[f"{measure}Warehouse"] - reconciliation[f"{measure}Source"]
            require(reconciliation[f"{measure}Delta"].eq(0).all(), f"Đối soát từng ô sai {measure}.")
        reconciliation.to_csv(run_dir / "monthly_reconciliation.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
        with sqlite3.connect(db_path) as connection:
            require(connection.execute("PRAGMA foreign_key_check").fetchall() == [], "Có khóa ngoại lỗi.")
            require(connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity_check lỗi.")
            mart = pd.read_sql_query("SELECT * FROM vw_MarketPeriod ORDER BY Market,MonthStart", connection, parse_dates=["MonthStart"])
        require(len(mart) == 96 and not mart.duplicated(["Market", "MonthStart"]).any(), "Mart không đúng 96 grain.")
        expected_mart = source_cells[["MonthStart", "Market", "Sales", "BudgetSales", "Profit"]].sort_values(["Market", "MonthStart"]).reset_index(drop=True)
        pd.testing.assert_frame_equal(expected_mart, mart[expected_mart.columns], check_dtype=False, atol=0, rtol=0)
        require(np.allclose(mart.BudgetAchievement, mart.Sales / mart.BudgetSales, atol=1e-12, rtol=0), "Tỷ lệ ngân sách không theo tổng/tổng.")
        mart.to_csv(run_dir / "mart_market_period.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
        event("warehouse_verified", rows=len(detail), measures=len(MEASURES), monthly_cells=len(mart), foreign_keys="pass", integrity="ok")

        replay = load(source, db_path)
        require(replay["status"] == "skipped" and replay["batch_id"] == first_load["batch_id"], "Phát lại phải bỏ qua batch checksum cũ.")
        pd.testing.assert_frame_equal(detail, read_detail(db_path))
        write_json(run_dir / "load_replay.json", replay)
        event("etl_replay_verified", status=replay["status"], rows=replay["warehouse_rows"], sales=replay["warehouse_sales"])

        summary = run_forecast(db_path, forecast_dir)
        with sqlite3.connect(db_path) as connection:
            first_publication = pd.read_sql_query("SELECT * FROM ForecastSales ORDER BY Market,ForecastMonth,IssueMonth,ModelName,ModelVersion", connection)
            require(connection.execute("SELECT COUNT(*) FROM LoadBatch").fetchone()[0] == 1, "Replay đã tạo batch thừa.")
        require(len(first_publication) == 112, "ForecastSales phải có 108 đánh giá và 4 tương lai.")
        require(not first_publication.duplicated(["Market", "ForecastMonth", "IssueMonth", "ModelName", "ModelVersion"]).any(), "ForecastSales trùng grain.")
        selected, _, predictions, future = native_forecast_frames(first_publication)
        require(len(predictions) == 108 and len(future) == 4 and future.Actual.isna().all(), "Sai phạm vi dự báo/actual tương lai.")
        require(selected["selected_model"] == summary["selected_model"] == "moving_average_3", "Lựa chọn không khớp tham chiếu validation.")
        second_summary = run_forecast(db_path, forecast_dir)
        with sqlite3.connect(db_path) as connection:
            replay_publication = pd.read_sql_query("SELECT * FROM ForecastSales ORDER BY Market,ForecastMonth,IssueMonth,ModelName,ModelVersion", connection)
        pd.testing.assert_frame_equal(first_publication, replay_publication)
        require(summary == second_summary, "Replay forecast thay summary.")
        event("forecast_replay_verified", rows=len(replay_publication), evaluation_rows=len(predictions), future_rows=len(future), future_actual_nulls=int(future.Actual.isna().sum()), selected=summary["selected_model"])

        source_after = sha(source)
        serving_after = sha(serving_db) if serving_db.exists() else None
        require(source_before == source_after, "Nguồn raw đã thay đổi trong lần chạy.")
        require(serving_before == serving_after, "Kho phục vụ đã thay đổi trong lần tái lập; cần rà soát writer đồng thời.")
        code_after = {relative: sha(ROOT / relative) for relative in code_before}
        changed = [relative for relative in code_before if code_before[relative] != code_after[relative]]
        # Concurrent editing is disclosed rather than calling this a fixed-code checkout.
        report = {"status": "passed", "run_id": run_id, "finished_utc": utc(), "run_directory": str(run_dir),
                  "execution_context": metadata["execution_context"], "clean_checkout_verified": False,
                  "working_tree_dirty_at_start": metadata["working_tree_dirty"], "code_files_changed_during_run": changed,
                  "source_sha256_before": source_before, "source_sha256_after": source_after,
                  "source_unchanged": source_before == source_after, "serving_warehouse_unchanged": serving_before == serving_after,
                  "detail_rows": len(detail), "months": int(detail.MonthStart.nunique()), "markets": int(detail.Market.nunique()),
                  "measure_totals_checked": len(MEASURES), "detail_grain_unique": True, "all_detail_values_reconciled": True,
                  "monthly_cells_reconciled": len(reconciliation), "sales": float(detail.Sales.sum()),
                  "budget_sales": float(detail.BudgetSales.sum()), "profit": float(detail.Profit.sum()),
                  "etl_replay": "skipped_same_batch_values_identical", "forecast_rows": len(replay_publication),
                  "forecast_replay": "same_112_unique_rows_and_values", "future_actual_nulls": int(future.Actual.isna().sum()),
                  "selected_model": summary["selected_model"], "forecast_summary": summary,
                  "limits": ["Isolated data reproduction on a dirty working tree; not a clean-checkout installation rehearsal.",
                             "SQLite evidence only; not SQL Server/SSIS/SSAS or human UX acceptance."]}
        event("completed", status="passed", source_unchanged=True, serving_warehouse_unchanged=True, concurrent_code_changes=changed)
        report["artifacts"] = [{"path": p.relative_to(run_dir).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(run_dir.rglob("*")) if p.is_file()]
        write_json(run_dir / "verification.json", report)
        write_json(output / "verification.json", report)
        return report
    except Exception as exc:
        event("failed", error_type=type(exc).__name__, message=str(exc))
        (run_dir / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        failure = {"status": "failed", "run_id": run_id, "run_directory": str(run_dir), "clean_checkout_verified": False,
                   "error_type": type(exc).__name__, "message": str(exc)}
        write_json(run_dir / "verification.json", failure)
        write_json(output / "verification.json", failure)
        raise


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, default=ROOT / "results/trang_completion/reproduction")
    args = parser.parse_args()
    report = run(args.output, args.source)
    print(json.dumps(report, ensure_ascii=False, indent=2))
