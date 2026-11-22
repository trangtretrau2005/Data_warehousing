"""Prepare TN11 answer sheets, or summarize real human trials without fabricating any."""

import argparse
import json
from pathlib import Path

from coffee_dw.acceptance import prepare_acceptance, summarize_trials
from coffee_dw.config import ROOT, SOURCE_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "trang_acceptance")
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--trials", type=Path, help="Summarize actual recorded trials instead of exporting inputs")
    args = parser.parse_args()
    if args.trials:
        summary, audit = summarize_trials(args.trials)
        args.output.mkdir(parents=True, exist_ok=True)
        summary.to_csv(args.output / "ux_summary.csv", index=False, encoding="utf-8-sig")
        (args.output / "ux_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(audit, ensure_ascii=True))
    else:
        manifest = prepare_acceptance(args.output, args.source)
        print(json.dumps({k: manifest[k] for k in ["status", "source_rows", "human_trials_created", "source_unchanged"]}))


if __name__ == "__main__":
    main()
