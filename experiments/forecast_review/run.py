"""Run the declared seasonal12/SES extension without publishing its selection."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from coffee_dw.config import SOURCE_PATH
from coffee_dw.forecast_review import run_review


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/forecast_review/results")
    args = parser.parse_args()
    result = run_review(args.source, args.output)
    print(f"Mở rộng thăm dò: {result['selected_configuration']} · {result['candidate_count']} cấu hình; không đổi MA3 phục vụ.")
    print(f"Bảng/phân tích: {args.output.resolve()}")
