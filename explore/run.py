"""Run source-first EDA without a warehouse, SQL Server, SSIS or SSAS."""

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".tmp" / "matplotlib"))

from coffee_dw.config import SOURCE_PATH
from coffee_dw.exploration import run_exploration


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="EDA Coffee: bảng, phân tích và hình báo cáo.")
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, default=ROOT / "explore" / "results")
    args = parser.parse_args()
    manifest = run_exploration(args.source, args.output)
    print(f"Đã phân tích {manifest['source']['accepted_rows']:,} dòng hợp lệ; {manifest['source']['rejected_rows']} dòng reject.")
    print(f"Bảng CSV: {manifest['artifacts']['csv_count']} | Bộ hình: {manifest['artifacts']['figure_count']} (PNG + PDF + SVG).")
    print(f"Đọc báo cáo: {args.output.resolve() / 'report.html'}")
    print(f"Phân tích tiếng Việt: {args.output.resolve() / 'analysis.md'}")


if __name__ == "__main__":
    main()
