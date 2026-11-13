"""Run only after SQL Server scripts 00..03; connection details remain in .env."""

import argparse
import json

from coffee_dw.config import SOURCE_PATH
from coffee_dw.sqlserver import load_sqlserver

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=SOURCE_PATH)
    args = parser.parse_args()
    print(json.dumps(load_sqlserver(args.source), indent=2, default=str, ensure_ascii=False))
