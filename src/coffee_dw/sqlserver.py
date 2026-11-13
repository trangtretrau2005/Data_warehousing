"""Optional SQL Server bridge using the same source validation as the demo."""

from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from coffee_dw.config import SOURCE_PATH
from coffee_dw.source import COLUMN_MAP, MEASURES, read_source


def load_sqlserver(csv_path: str | Path = SOURCE_PATH) -> dict:
    try:
        import pyodbc
    except ImportError as exc:
        raise RuntimeError('Install SQL Server support: python -m pip install -e ".[sqlserver]"') from exc
    connection_string = os.getenv("COFFEE_DW_SQLSERVER_CONNECTION")
    if not connection_string:
        raise ValueError("Set COFFEE_DW_SQLSERVER_CONNECTION in .env; see .env.example")
    valid, rejected = read_source(csv_path)
    inverse = {target: source for source, target in COLUMN_MAP.items()}
    batch_id = str(uuid4())
    columns = ["BatchID", "SourceRow", "RawJson", "RejectReason", "MonthStart", "DateKey",
               "AreaCode", "State", "Market", "MarketSize", "ProductName", "ProductLine",
               "ProductType", "Type", *MEASURES]
    records = []
    for row in valid.to_dict("records"):
        original = json.loads(row["RawPayload"])
        values = {**row, "BatchID": batch_id, "RawJson": row["RawPayload"], "RejectReason": None}
        values["MonthStart"] = row["MonthStart"].date()
        for measure in MEASURES:
            values[measure] = Decimal(original[inverse[measure]])
        records.append(tuple(values[c] for c in columns))
    for row in rejected.to_dict("records"):
        values = {c: None for c in columns}
        values.update(BatchID=batch_id, SourceRow=row["SourceRow"], RawJson=row["RawPayload"],
                      RejectReason=row["Reason"])
        records.append(tuple(values[c] for c in columns))
    connection = pyodbc.connect(connection_string, autocommit=False)
    try:
        cursor = connection.cursor()
        cursor.execute("""INSERT audit.LoadBatch(BatchID,SourceFile,SourceChecksum,SourceCount)
                          VALUES (?,?,?,?)""", batch_id, Path(csv_path).name,
                       hashlib.sha256(Path(csv_path).read_bytes()).hexdigest(), len(records))
        if records:
            cursor.executemany(
                f"INSERT stg.CoffeeRaw ({','.join('['+c+']' for c in columns)}) "
                f"VALUES ({','.join('?' for _ in columns)})", records)
        cursor.execute("EXEC dw.usp_LoadCoffee ?", batch_id)
        while cursor.description is None:
            if not cursor.nextset():
                raise RuntimeError("Load procedure returned no audit result")
        summary = dict(zip((c[0] for c in cursor.description), cursor.fetchone()))
        connection.commit()
        return summary
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
