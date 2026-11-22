"""Reproduce the fixed three-method forecast study from the immutable CSV."""

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".tmp" / "matplotlib"))

from coffee_dw.baseline_study import run_study
from coffee_dw.config import SOURCE_PATH


def main():
    if hasattr(sys.stdout,"reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description="Thử nghiệm cơ sở: Naive, MA3, Ridge; đầy đủ bảng/hình/nhận xét.")
    parser.add_argument("--source",type=Path,default=SOURCE_PATH)
    parser.add_argument("--output",type=Path,default=ROOT/"experiments"/"baseline"/"results")
    args=parser.parse_args()
    result=run_study(args.source,args.output)
    print(f"Đã hoàn tất: {result['selected_method']} · {result['csv_count']} bảng CSV · {result['figure_count']} bộ hình.")
    print(f"Báo cáo: {args.output.resolve()/'report.html'}")
    print(f"Phân tích: {args.output.resolve()/'analysis.md'}")


if __name__=="__main__":
    main()
