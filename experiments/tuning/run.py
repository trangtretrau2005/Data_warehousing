"""Run all seven declared configurations and export report/model evidence."""

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT/".tmp"/"matplotlib"))

from coffee_dw.config import SOURCE_PATH
from coffee_dw.tuning_study import run_study


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Thử đủ 7 cấu hình Naive/MA/Ridge và xuất báo cáo.")
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, default=ROOT/"experiments"/"tuning"/"results")
    args = parser.parse_args()
    result = run_study(args.source, args.output)
    print(f"Hoàn tất {result['candidate_count']} cấu hình; chọn {result['selected_configuration']}.")
    print(f"{result['csv_count']} CSV · {result['figure_count']} bộ hình · {len(result['files'])} artifact.")
    print(f"Báo cáo: {args.output.resolve()/'report.html'}")


if __name__ == "__main__":
    main()
