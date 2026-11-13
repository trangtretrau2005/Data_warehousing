"""Transactional SQLite reference implementation of staging -> star -> marts.

This is a local teaching backend. SQL Server, SSIS and SSAS experiments must be
validated separately on their own engine. Money is stored as scaled integers.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

import pandas as pd

from coffee_dw.config import DB_PATH, SOURCE_PATH
from coffee_dw.source import COLUMN_MAP, MEASURES, SCALE, _scaled, read_source


def connect(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    measures_ddl = ",\n".join(f"{m}Scaled INTEGER NOT NULL" for m in MEASURES)
    connection.executescript(f"""
        CREATE TABLE IF NOT EXISTS LoadBatch (
            BatchID TEXT PRIMARY KEY, SourceFile TEXT NOT NULL, Checksum TEXT NOT NULL UNIQUE,
            StartedAt TEXT NOT NULL, FinishedAt TEXT, SourceRows INTEGER NOT NULL,
            AcceptedRows INTEGER NOT NULL, RejectedRows INTEGER NOT NULL,
            InsertedRows INTEGER NOT NULL DEFAULT 0, UpdatedRows INTEGER NOT NULL DEFAULT 0,
            UnchangedRows INTEGER NOT NULL DEFAULT 0, Status TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS CoffeeRaw (
            BatchID TEXT NOT NULL REFERENCES LoadBatch(BatchID), SourceRow INTEGER NOT NULL,
            RawPayload TEXT NOT NULL, PRIMARY KEY (BatchID, SourceRow));
        CREATE TABLE IF NOT EXISTS RejectedRow (
            BatchID TEXT NOT NULL REFERENCES LoadBatch(BatchID), SourceRow INTEGER NOT NULL,
            Reason TEXT NOT NULL, RawPayload TEXT NOT NULL, PRIMARY KEY (BatchID, SourceRow));
        CREATE TABLE IF NOT EXISTS DimDate (
            DateKey INTEGER PRIMARY KEY, MonthStart TEXT NOT NULL UNIQUE,
            Month INTEGER NOT NULL, Quarter INTEGER NOT NULL, Year INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS DimLocation (
            LocationKey INTEGER PRIMARY KEY, AreaCode TEXT NOT NULL UNIQUE,
            State TEXT NOT NULL, Market TEXT NOT NULL, MarketSize TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS DimProduct (
            ProductKey INTEGER PRIMARY KEY, ProductName TEXT NOT NULL UNIQUE,
            ProductLine TEXT NOT NULL, ProductType TEXT NOT NULL, Type TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS FactSalesPerformance (
            DateKey INTEGER NOT NULL REFERENCES DimDate(DateKey),
            LocationKey INTEGER NOT NULL REFERENCES DimLocation(LocationKey),
            ProductKey INTEGER NOT NULL REFERENCES DimProduct(ProductKey),
            {measures_ddl}, BatchID TEXT NOT NULL REFERENCES LoadBatch(BatchID),
            SourceRow INTEGER NOT NULL, PRIMARY KEY (DateKey, LocationKey, ProductKey));
        CREATE VIEW IF NOT EXISTS vw_Detail AS
        SELECT d.MonthStart, d.DateKey, l.AreaCode, l.State, l.Market, l.MarketSize,
               p.ProductName, p.ProductLine, p.ProductType, p.Type,
               {','.join(f'f.{m}Scaled / {SCALE}.0 AS {m}' for m in MEASURES)},
               f.SourceRow, f.BatchID
        FROM FactSalesPerformance f JOIN DimDate d ON d.DateKey=f.DateKey
        JOIN DimLocation l ON l.LocationKey=f.LocationKey
        JOIN DimProduct p ON p.ProductKey=f.ProductKey;
        CREATE VIEW IF NOT EXISTS vw_MarketPeriod AS
        SELECT MonthStart, Market, SUM(Sales) AS Sales, SUM(BudgetSales) AS BudgetSales,
               SUM(Profit) AS Profit, SUM(Sales)-SUM(BudgetSales) AS Gap,
               SUM(Sales)/NULLIF(SUM(BudgetSales),0) AS BudgetAchievement
        FROM vw_Detail GROUP BY MonthStart, Market;
        CREATE VIEW IF NOT EXISTS vw_MarketProductPeriod AS
        SELECT MonthStart, Market, ProductName, SUM(Sales) AS Sales,
               SUM(BudgetSales) AS BudgetSales, SUM(Profit) AS Profit,
               SUM(Sales)-SUM(BudgetSales) AS Gap
        FROM vw_Detail GROUP BY MonthStart, Market, ProductName;
    """)


def load(csv_path: str | Path = SOURCE_PATH, db_path: str | Path = DB_PATH) -> dict:
    """Replay an identical file safely; update corrected measures by business grain.

    The main dimension policy is Type 1 (new attributes overwrite existing ones).
    Type 2 is a separate synthetic experiment, because this CSV has no effective
    dates or stable product codes for observed classification changes.
    """
    csv_path = Path(csv_path)
    checksum = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    valid, rejected = read_source(csv_path)
    connection = connect(db_path)
    try:
        initialize(connection)
        previous = connection.execute(
            "SELECT BatchID FROM LoadBatch WHERE Checksum=? AND Status='completed'", (checksum,)
        ).fetchone()
        if previous:
            count, total = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(SalesScaled),0) FROM FactSalesPerformance"
            ).fetchone()
            return {"batch_id": previous[0], "checksum": checksum, "status": "skipped",
                    "source_rows": len(valid) + len(rejected), "accepted_rows": len(valid),
                    "rejected_rows": len(rejected), "inserted_rows": 0, "updated_rows": 0,
                    "unchanged_rows": len(valid), "warehouse_rows": count,
                    "warehouse_sales": total / SCALE}
        batch_id = uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        inserted = updated = unchanged = 0
        expected_rows = []
        source_names = {target: source for source, target in COLUMN_MAP.items()}
        with connection:
            connection.execute("""INSERT INTO LoadBatch
                (BatchID,SourceFile,Checksum,StartedAt,SourceRows,AcceptedRows,RejectedRows,Status)
                VALUES (?,?,?,?,?,?,?,?)""", (batch_id, csv_path.name, checksum, now,
                    len(valid) + len(rejected), len(valid), len(rejected), "running"))
            for frame in (valid, rejected):
                connection.executemany("INSERT INTO CoffeeRaw VALUES (?,?,?)",
                    [(batch_id, int(r.SourceRow), r.RawPayload) for r in frame.itertuples()])
            connection.executemany("INSERT INTO RejectedRow VALUES (?,?,?,?)",
                [(batch_id, int(r.SourceRow), r.Reason, r.RawPayload) for r in rejected.itertuples()])
            for row in valid.itertuples(index=False):
                month = row.MonthStart
                connection.execute("INSERT OR IGNORE INTO DimDate VALUES (?,?,?,?,?)",
                    (int(row.DateKey), month.strftime("%Y-%m-%d"), month.month,
                     (month.month - 1) // 3 + 1, month.year))
                connection.execute("""INSERT INTO DimLocation (AreaCode,State,Market,MarketSize)
                    VALUES (?,?,?,?) ON CONFLICT(AreaCode) DO UPDATE SET
                    State=excluded.State, Market=excluded.Market, MarketSize=excluded.MarketSize""",
                    (row.AreaCode, row.State, row.Market, row.MarketSize))
                connection.execute("""INSERT INTO DimProduct (ProductName,ProductLine,ProductType,Type)
                    VALUES (?,?,?,?) ON CONFLICT(ProductName) DO UPDATE SET
                    ProductLine=excluded.ProductLine, ProductType=excluded.ProductType, Type=excluded.Type""",
                    (row.ProductName, row.ProductLine, row.ProductType, row.Type))
                location_key = connection.execute("SELECT LocationKey FROM DimLocation WHERE AreaCode=?",
                                                   (row.AreaCode,)).fetchone()[0]
                product_key = connection.execute("SELECT ProductKey FROM DimProduct WHERE ProductName=?",
                                                  (row.ProductName,)).fetchone()[0]
                key = (int(row.DateKey), location_key, product_key)
                # Use original numeric strings so fixed-point storage never
                # round-trips through the floating-point display DataFrame.
                raw_payload = json.loads(row.RawPayload)
                amounts = tuple(_scaled(raw_payload[source_names[m]]) for m in MEASURES)
                expected_rows.append((*key, *amounts))
                existing = connection.execute(
                    f"SELECT {','.join(f'{m}Scaled' for m in MEASURES)} FROM FactSalesPerformance "
                    "WHERE DateKey=? AND LocationKey=? AND ProductKey=?", key).fetchone()
                if existing is None:
                    connection.execute(
                        f"INSERT INTO FactSalesPerformance VALUES ({','.join('?' for _ in range(len(MEASURES)+5))})",
                        (*key, *amounts, batch_id, int(row.SourceRow)))
                    inserted += 1
                elif tuple(existing) != amounts:
                    connection.execute(
                        f"UPDATE FactSalesPerformance SET {','.join(f'{m}Scaled=?' for m in MEASURES)}, "
                        "BatchID=?, SourceRow=? WHERE DateKey=? AND LocationKey=? AND ProductKey=?",
                        (*amounts, batch_id, int(row.SourceRow), *key))
                    updated += 1
                else:
                    unchanged += 1
            # Each accepted grain must resolve exactly once with all source measures.
            if expected_rows:
                keys = ["DateKey", "LocationKey", "ProductKey"]
                amounts_columns = [f"{m}Scaled" for m in MEASURES]
                expected = pd.DataFrame(expected_rows, columns=keys + amounts_columns)
                stored = pd.read_sql_query(
                    f"SELECT {','.join(keys + amounts_columns)} FROM FactSalesPerformance", connection)
                comparison = expected.merge(stored, on=keys, validate="one_to_one",
                                            suffixes=("_source", "_dw"))
                if len(comparison) != len(expected_rows):
                    raise ValueError("Warehouse does not preserve the accepted source grain")
                for measure in MEASURES:
                    if comparison[f"{measure}Scaled_source"].ne(comparison[f"{measure}Scaled_dw"]).any():
                        raise ValueError(f"Warehouse reconciliation failed for {measure}")
            connection.execute("""UPDATE LoadBatch SET FinishedAt=?,InsertedRows=?,UpdatedRows=?,
                               UnchangedRows=?,Status='completed' WHERE BatchID=?""",
                               (datetime.now(timezone.utc).isoformat(), inserted, updated, unchanged, batch_id))
        count, sales = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(SalesScaled),0) FROM FactSalesPerformance").fetchone()
        return {"batch_id": batch_id, "checksum": checksum, "status": "completed",
                "source_rows": len(valid) + len(rejected), "accepted_rows": len(valid),
                "rejected_rows": len(rejected), "inserted_rows": inserted, "updated_rows": updated,
                "unchanged_rows": unchanged, "warehouse_rows": count, "warehouse_sales": sales / SCALE}
    finally:
        connection.close()


def read_detail(db_path: str | Path = DB_PATH) -> pd.DataFrame:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Warehouse not found: {path}. Run python -m coffee_dw.cli demo first.")
    connection = connect(path)
    try:
        return pd.read_sql_query("SELECT * FROM vw_Detail ORDER BY MonthStart,Market,AreaCode,ProductName",
                                 connection, parse_dates=["MonthStart"])
    finally:
        connection.close()
