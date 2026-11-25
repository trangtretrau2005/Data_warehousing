"""Optional live SQL-only regression. Every scenario rolls back its own writes.

Not SSIS execution proof. Set COFFEE_DW_NATIVE_TEST_DATABASE to an initialized
isolated experiment DB; no database, schema, permission or service is created.
"""
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
import re
from uuid import uuid4

import pytest
import pandas as pd
import pandas as pd

from coffee_dw.config import SOURCE_PATH
from coffee_dw.source import read_source, _scaled, MEASURES, COLUMN_MAP, LOCATION_ATTRIBUTES, PRODUCT_ATTRIBUTES


@pytest.fixture
def native_connection():
    database = os.getenv("COFFEE_DW_NATIVE_TEST_DATABASE")
    if not database:
        pytest.skip("Live SQL validation requires an explicitly selected isolated DB")
    if not re.fullmatch(r"CoffeeDW_Trang_[A-Za-z0-9_]+", database):
        raise ValueError("Refusing live tests outside an isolated CoffeeDW_Trang DB")
    pyodbc = pytest.importorskip("pyodbc")
    cn = pyodbc.connect(f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER=.;DATABASE={database};Trusted_Connection=yes;TrustServerCertificate=yes;", autocommit=False)
    try:
        yield cn
    finally:
        cn.rollback()
        cn.close()


def test_exact_decimal_and_excel_serial_lexical_parity(native_connection):
    cursor = native_connection.cursor()
    values = ["219", "-10", "+1.25", ".5", "1.", "  1.2500  ", "1.00000", "0.00000",
              "1e2", "1.2e-3", "1e-5", "1_000", "1.2.3", "", "abc", "NaN", "Infinity",
              "922337203685477.5807", "922337203685477.5808", "-922337203685477.5808",
              "1e200", "\u00a01.25\t", "-0", "0e-20", "1e 2", "1e+ 2", "1e- 2", "1\uff0e2", "\uff0b1"]
    for raw in values:
        try:
            expected = Decimal(_scaled(raw)) / 10000
        except (InvalidOperation, ValueError, OverflowError):
            expected = None
        actual = cursor.execute("SELECT stg.fn_CoffeeNumber(?,'M')", raw).fetchval()
        assert actual == expected, (raw, expected, actual)
    for raw in ["40909", "40909.00000", ".40909e5", "40909.1", "abc", "40909e0"]:
        try:
            number = Decimal(raw)
            expected = number if number.is_finite() and number == int(number) else None
        except (InvalidOperation, ValueError, OverflowError): expected = None
        actual = cursor.execute("SELECT stg.fn_CoffeeNumber(?,'D')", raw).fetchval()
        assert actual == expected
    for raw in ["-81183", "-81182", "-80842", "132320", "132321", "0.5"]:
        try:
            serial = Decimal(raw)
            timestamp = pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(serial))
            expected = timestamp if serial == int(serial) and timestamp.day == 1 else None
        except (InvalidOperation, ValueError, OverflowError, pd.errors.OutOfBoundsDatetime):
            expected = None
        actual = cursor.execute("""SELECT CASE WHEN stg.fn_CoffeeNumber(?,'D') BETWEEN -81182 AND 132320
            THEN DATEADD(day,CONVERT(int,stg.fn_CoffeeNumber(?,'D')),CONVERT(date,'18991230')) END""", raw,raw).fetchval()
        if actual is not None and actual.day != 1: actual=None
        assert actual == (expected.date() if expected is not None else None)


def test_native_scd_execute_sql_package_persisted_assertions(native_connection):
    row = native_connection.cursor().execute("""SELECT TOP (1) ResultJson FROM audit.SCDNativeEvidence
        WHERE JSON_VALUE(ResultJson,'$.Assertions')='PASS'
        ORDER BY CreatedAtUTC DESC""").fetchone()
    assert row is not None
    result = json.loads(row[0])
    assert result["Scope"].startswith("Synthetic P01/A01")
    assert result["ProductType1"] == [{"ProductKey": 1, "Code": "P01", "ProductName": "Amaretto"}]
    assert [x["ProductKey"] for x in result["ProductType2"]] == [1, 2]
    assert result["ProductType3"][0]["PreviousType"] == "Specialty"
    assert [x["Tier"] for x in result["LocationType2"]] == ["Minor", "Major"]
    assert result["LocationType3"][0]["PrevTier"] == "Major"


@pytest.mark.parametrize("scenario", ["full", "invalid8", "duplicate", "conflicting_parent", "precision"])
def test_sql_validator_matches_shared_parser_and_retains_all_raw_values(native_connection, tmp_path, scenario):
    with SOURCE_PATH.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers, original = reader.fieldnames, list(reader)
    records = [dict(r) for r in (original if scenario == "full" else original[:8])]
    if scenario == "invalid8": records[0]["Sales"], records[1]["Product"] = "abc", ""
    elif scenario == "duplicate": records.append(dict(records[0]))
    elif scenario == "conflicting_parent": records[1]["State"] = "Changed parent"
    elif scenario == "precision": records[0]["Sales"] = "1.00000"
    path = tmp_path / f"{scenario}.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\r\n")
        writer.writeheader(); writer.writerows(records)
    valid, rejected = read_source(path)
    cursor = native_connection.cursor()
    batch = str(uuid4())
    cursor.execute("INSERT audit.LoadBatch(BatchID,SourceFile,SourceChecksum,SourceCount) VALUES(?,?,?,?)",
                   batch, path.name, hashlib.sha256(path.read_bytes()).hexdigest(), len(records))
    insert = "INSERT stg.CoffeeCsvLanding(BatchID,"+",".join("["+c+"]" for c in headers)+") VALUES("+",".join("?" for _ in range(21))+")"
    cursor.fast_executemany = True
    cursor.executemany(insert, [(batch, *(r[c] for c in headers)) for r in records])
    cursor.fast_executemany = False
    cursor.execute("EXEC stg.usp_ValidateCoffeeLanding ?", batch)
    while cursor.nextset(): pass
    attributes = ["MonthStart", "DateKey", *LOCATION_ATTRIBUTES, *PRODUCT_ATTRIBUTES]
    cursor.execute("SELECT SourceRow,RawJson,RejectReason,"+",".join([*MEASURES,*attributes])+" FROM stg.CoffeeRaw WHERE BatchID=? ORDER BY SourceRow",batch)
    actual = cursor.fetchall()
    actual_rejects = {r[0] for r in actual if r[2]}
    assert actual_rejects == set(rejected.SourceRow)
    assert len(actual) == len(records)
    inverse = {v:k for k,v in COLUMN_MAP.items()}
    expected_valid = {int(r["SourceRow"]): r for r in valid.to_dict("records")}
    for row, raw in zip(actual, records):
        assert json.loads(row[1]) == raw
        if row[2] is None:
            for name, value in zip(MEASURES, row[3:3+len(MEASURES)]):
                assert value == Decimal(raw[inverse[name]])
            expected = expected_valid[row[0]]
            for name, value in zip(attributes, row[3+len(MEASURES):]):
                assert value == (expected[name].date() if name == "MonthStart" else expected[name])
    cursor.execute("EXEC dw.usp_LoadCoffee ?", batch)
    while cursor.nextset(): pass
    audit = cursor.execute("SELECT SourceCount,AcceptedCount,RejectedCount,Status FROM audit.LoadBatch WHERE BatchID=?",batch).fetchone()
    assert tuple(audit) == (len(records),len(valid),len(rejected),"COMPLETED")
