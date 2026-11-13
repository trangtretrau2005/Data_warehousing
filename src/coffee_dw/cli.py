"""Small explicit commands for team development and report evidence."""

import argparse
import json
import sys
from pathlib import Path

from coffee_dw.config import DB_PATH, RESULTS_DIR, SOURCE_PATH
from coffee_dw.source import profile
from coffee_dw.warehouse import load


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="CoffeeDW reproducible local reference pipeline")
    parser.add_argument("command", choices=["profile", "load", "demo", "forecast"])
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args(argv)
    output = {}
    if args.command in {"profile", "demo"}:
        output["profile"] = profile(args.source)
        write_json(RESULTS_DIR / "TN01" / "profile.json", output["profile"])
    if args.command in {"load", "demo"}:
        output["load"] = load(args.source, args.db)
        write_json(RESULTS_DIR / "TN03" / "load.json", output["load"])
    if args.command == "forecast":
        from coffee_dw.forecast import run_forecast
        output["forecast"] = run_forecast(db_path=args.db)
    print(json.dumps(output, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
