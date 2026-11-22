"""Rehearse a clean working-source snapshot using a new, isolated virtualenv.

No Git checkout, commit, reset or credentials are copied. Source selection uses
Git's tracked/untracked nonignored file inventory, then a strict allowlist.
`prepare` creates the snapshot/venv and installs dependencies; `verify` refreshes
source, then runs the pipeline and tests. The latter must be scheduled after any
native benchmark measurements to avoid adding concurrent CPU load.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from uuid import uuid4
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "results/trang_completion/clean_snapshot"
ALLOWED_ROOT_FILES = {"AGENTS.md", "CONTRIBUTING.md", "README.md", "pyproject.toml", "requirements.txt", ".gitignore", ".gitattributes", ".env.example"}
ALLOWED_DIRECTORIES = {"src", "apps", "tests", "docs", "scripts", "learning", "experiments", "explore", "sql", "ssas", "ssis"}
ALLOWED_SUFFIXES = {".py", ".ps1", ".md", ".toml", ".txt", ".sql", ".mdx", ".js", ".json", ".csv", ".html", ".css", ".svg", ".docx"}
BLOCKED_PARTS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".tmp", ".work", "results", "models", "audio", "node_modules"}


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()


def selected_source():
    listing = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")
    selected, excluded = [], []
    for relative in sorted(set(filter(None, listing.split("\0")))):
        path = Path(relative)
        lower_parts = {p.lower() for p in path.parts}
        allowed = (relative in ALLOWED_ROOT_FILES or relative == "data/raw/Coffee.csv" or
                   (path.parts[0] in ALLOWED_DIRECTORIES and (path.suffix.lower() in ALLOWED_SUFFIXES or path.name == ".gitignore")))
        safe = not (lower_parts & BLOCKED_PARTS) and not path.name.startswith("~$")
        safe = safe and (not path.name.lower().startswith(".env") or path.name == ".env.example")
        safe = safe and not any(word in path.name.lower() for word in ("secret", "credential", "password", "token"))
        origin = ROOT / path
        if allowed and safe and origin.is_file() and not origin.is_symlink():
            selected.append(relative)
        else:
            excluded.append(relative)
    return selected, excluded


def snapshot_environment(source, venv):
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("COFFEE_DW_") or key in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PYTEST_ADDOPTS", "GIT_DIR", "GIT_WORK_TREE"}:
            env.pop(key, None)
    env.update(PYTHONNOUSERSITE="1", PYTHONIOENCODING="utf-8", MPLCONFIGDIR=str(source / ".tmp/matplotlib"),
               GIT_CEILING_DIRECTORIES=str(source.parent), VIRTUAL_ENV=str(venv),
               PATH=str(venv / "Scripts") + os.pathsep + env.get("PATH", ""))
    return env


def copy_source(source, evidence):
    selected, excluded = selected_source()
    records = []
    previous_path = evidence / "source_inventory.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {}
    for relative in selected:
        origin, target = ROOT / relative, source / relative
        require_inside(target, source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, target)
        original_hash, copied_hash = sha(origin), sha(target)
        if original_hash != copied_hash:
            raise RuntimeError(f"File thay đổi khi copy: {relative}; cần refresh lại snapshot.")
        records.append({"path": relative, "bytes": target.stat().st_size, "sha256": copied_hash})
    for old in previous.get("files", []):
        if old["path"] not in selected:
            obsolete = source / old["path"]
            require_inside(obsolete, source)
            if obsolete.is_file():
                obsolete.unlink()
    inventory = {"created_utc": utc(), "source_root": str(source), "source_file_count": len(records),
                 "files": records, "excluded_paths": excluded, "git_commit_of_origin": git("rev-parse", "HEAD"),
                 "git_branch_of_origin": git("branch", "--show-current"),
                 "origin_working_tree_dirty": bool(git("status", "--porcelain")),
                 "snapshot_type": "clean working-source snapshot, not a Git committed checkout",
                 "copied_git_metadata": False, "copied_existing_outputs_or_database": False}
    write_json(previous_path, inventory)
    return inventory


def require_inside(path, parent):
    if not path.resolve().is_relative_to(parent.resolve()):
        raise ValueError("Đường dẫn snapshot không nằm trong vùng đã chỉ định.")


def command(args, cwd, env, log):
    with Path(log).open("w", encoding="utf-8") as stream:
        result = subprocess.run([str(a) for a in args], cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Lệnh thất bại (exit {result.returncode}), xem {log}")
    return {"exit_code": result.returncode, "log": str(log), "log_sha256": sha(log)}


def prepare(output):
    output = output.resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    workspace = ROOT / ".work/trang_release" / run_id
    source, venv = workspace / "source", workspace / "venv"
    evidence = output / "runs" / run_id
    source.mkdir(parents=True, exist_ok=False)
    evidence.mkdir(parents=True, exist_ok=False)
    print(f"Copy source snapshot: {source}", flush=True)
    inventory = copy_source(source, evidence)
    distributions = sorted({d.metadata["Name"]: d.version for d in importlib.metadata.distributions() if d.metadata["Name"].lower().replace("_", "-") != "coffee-dw"}.items())
    constraints = evidence / "constraints.txt"
    constraints.write_text("\n".join(f"{name}=={version}" for name, version in distributions) + "\n", encoding="utf-8")
    print("Create fresh venv (system-site-packages disabled).", flush=True)
    command([sys.executable, "-m", "venv", venv], ROOT, os.environ.copy(), evidence / "venv_create.log")
    python = venv / "Scripts/python.exe"
    env = snapshot_environment(source, venv)
    print("Install project extras dev, explore, sqlserver into fresh venv.", flush=True)
    command([python, "-m", "pip", "install", "--disable-pip-version-check", "--constraint", constraints, "--editable", ".[dev,explore,sqlserver]"], source, env, evidence / "install.log")
    command([python, "-m", "pip", "check"], source, env, evidence / "pip_check.log")
    command([python, "-m", "pip", "freeze"], source, env, evidence / "installed_packages.txt")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Thiếu Node để tái lập frontend tests.")
    command([node, "--version"], source, env, evidence / "node_version.txt")
    preparation = {"status": "prepared", "run_id": run_id, "prepared_utc": utc(), "workspace": str(workspace),
                   "source_root": str(source), "venv": str(venv), "python": str(python), "node": node,
                   "evidence_directory": str(evidence), "output_directory": str(output), "source_files_at_prepare": inventory["source_file_count"],
                   "new_virtualenv": True, "system_site_packages": False, "extras": ["dev", "explore", "sqlserver"],
                   "voice_extra_installed": False, "voice_model_redownloaded": False,
                   "limitations": ["Voice/model/audio not installed or downloaded; automated audio state tests use fixtures.",
                                   "Compiler/build isolation may resolve its own build tools; runtime versions constrained to installed working environment.",
                                   "This is a source snapshot of local changes, not a committed Git checkout."]}
    write_json(evidence / "preparation.json", preparation)
    write_json(output / "preparation.json", preparation)
    print(json.dumps(preparation, ensure_ascii=False, indent=2), flush=True)
    return preparation


def verify(preparation_path):
    state = json.loads(preparation_path.read_text(encoding="utf-8"))
    source, evidence = Path(state["source_root"]), Path(state["evidence_directory"])
    output, python, venv = Path(state["output_directory"]), Path(state["python"]), Path(state["venv"])
    require_inside(source, ROOT / ".work/trang_release")
    archived_source = None
    if (source / "results").exists() or (source / "data/warehouse/coffee_dw.sqlite").exists():
        # Keep every previous output, but rerun from a genuinely empty source
        # directory at the same editable-install path. No recursive deletion.
        attempt = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
        archived_source = source.with_name("source_before_" + attempt)
        require_inside(archived_source, ROOT / ".work/trang_release")
        if archived_source.exists():
            raise RuntimeError("Thư mục lưu snapshot cũ đã tồn tại.")
        source.rename(archived_source)
        source.mkdir(exist_ok=False)
        evidence = evidence / ("reverify_" + attempt)
        evidence.mkdir(parents=True, exist_ok=False)
    env = snapshot_environment(source, venv)
    report = {"status": "running", "run_id": state["run_id"], "started_utc": utc(), "preparation": state,
              "snapshot_type": "clean working-source snapshot with new venv", "committed_checkout": False,
              "evidence_directory": str(evidence), "previous_source_archive": str(archived_source) if archived_source else None,
              "venv_reused_from_this_preparation": archived_source is not None}
    try:
        # Refresh after the coordinating agent freezes code, keeping the new
        # virtualenv but taking the final source changes into the same snapshot.
        inventory = copy_source(source, evidence)
        report["source_inventory_sha256"] = sha(evidence / "source_inventory.json")
        for path in (source / "data/warehouse/coffee_dw.sqlite", source / "results/forecast/predictions.csv", source / ".env", source / ".git"):
            if path.exists():
                raise RuntimeError("Snapshot đã có dữ liệu/kết quả/metadata cũ trước khi diễn tập; tạo prepare mới.")
        report["cli_demo"] = command([python, "-m", "coffee_dw.cli", "demo"], source, env, evidence / "cli_demo.log")
        report["cli_forecast"] = command([python, "-m", "coffee_dw.cli", "forecast"], source, env, evidence / "cli_forecast.log")
        report["pytest"] = command([python, "-m", "pytest", "-p", "no:cacheprovider", f"--junitxml={evidence / 'pytest.xml'}"], source, env, evidence / "pytest.log")
        suite = ET.parse(evidence / "pytest.xml").getroot()
        counts = {key: sum(int(s.get(key, "0")) for s in suite.findall("testsuite")) for key in ("tests", "failures", "errors", "skipped")}
        report["pytest_counts"] = counts
        report["frontend"] = command([state["node"], "--test", "tests/test_presenter_frontend.js"], source, env, evidence / "frontend.log")
        # Test runs must not modify the code/data we packaged.
        for item in inventory["files"]:
            if sha(source / item["path"]) != item["sha256"]:
                raise RuntimeError(f"Source snapshot đã bị sửa trong khi kiểm tra: {item['path']}")
        db = source / "data/warehouse/coffee_dw.sqlite"
        with sqlite3.connect(db) as connection:
            rows, sales, budget, profit = connection.execute("SELECT COUNT(*),SUM(Sales),SUM(BudgetSales),SUM(Profit) FROM vw_Detail").fetchone()
            forecast_rows, future_rows, future_nulls = connection.execute("SELECT COUNT(*),SUM(CASE WHEN Split='future' THEN 1 ELSE 0 END),SUM(CASE WHEN Split='future' AND Actual IS NULL THEN 1 ELSE 0 END) FROM ForecastSales").fetchone()
        if (rows, sales, budget, profit, forecast_rows, future_rows, future_nulls) != (4248, 819811, 746160, 259543, 112, 4, 4):
            raise RuntimeError("Snapshot CLI không khớp số đối soát chuẩn.")
        report.update(status="passed", finished_utc=utc(), source_files=inventory["source_file_count"],
                      source_unchanged=True, raw_sha256=sha(source / "data/raw/Coffee.csv"),
                      detail_rows=rows, sales=sales, budget_sales=budget, profit=profit,
                      forecast_rows=forecast_rows, future_actual_nulls=future_nulls,
                      new_virtualenv=True, used_copied_database=False, used_preexisting_outputs=False,
                      voice_model_redownloaded=False, voice_audio_recreated=False,
                      limits=state["limitations"])
    except Exception as exc:
        report.update(status="failed", finished_utc=utc(), error_type=type(exc).__name__, message=str(exc))
        write_json(evidence / "verification.json", report)
        write_json(output / "verification.json", report)
        raise
    write_json(evidence / "verification.json", report)
    write_json(output / "verification.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return report


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "verify"])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--preparation", type=Path, default=DEFAULT_OUTPUT / "preparation.json")
    args = parser.parse_args()
    if args.stage == "prepare":
        prepare(args.output)
    else:
        verify(args.preparation)
