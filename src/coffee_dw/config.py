"""Project paths. No current-working-directory assumptions or embedded secrets."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)
SOURCE_PATH = ROOT / "data" / "raw" / "Coffee.csv"
DB_PATH = Path(os.getenv("COFFEE_DW_SQLITE_PATH", str(ROOT / "data" / "warehouse" / "coffee_dw.sqlite")))
if not DB_PATH.is_absolute():
    DB_PATH = ROOT / DB_PATH
RESULTS_DIR = ROOT / "results"
