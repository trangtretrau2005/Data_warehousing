"""Run the separate West handbook example without publishing to the demo."""

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".tmp" / "matplotlib"))

from coffee_dw.config import SOURCE_PATH
from coffee_dw.tn12_west import run_study


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="TN12 West: 07–12/2013; lag1/lag2/mean3; ví dụ thăm dò riêng.")
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/tn12_west/results")
    args = parser.parse_args()
    result = run_study(args.source, args.output)
    print(f"TN12 West: {result['selected_method']} · 18 dự báo · 6 kỳ/phương pháp.")
    print(f"West 01/2014: {result['forecast_201401']:.2f}; chưa có actual.")
    print(f"Báo cáo: {(args.output / 'report.html').resolve()}")


if __name__ == "__main__":
    main()
