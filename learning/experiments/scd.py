"""TN04: synthetic SCD1/2/3, isolated from serving dimensions and source CSV."""

import json
import sqlite3

from coffee_dw.config import RESULTS_DIR


def run() -> dict:
    with sqlite3.connect(":memory:") as db:
        db.executescript("""
            CREATE TABLE Type1(ProductKey INTEGER PRIMARY KEY,Code TEXT UNIQUE,Name TEXT);
            INSERT INTO Type1 VALUES(1,'P01','Amareto');
            UPDATE Type1 SET Name='Amaretto' WHERE Code='P01';
            CREATE TABLE Type2(ProductKey INTEGER PRIMARY KEY,Code TEXT,ProductType TEXT,
                ValidFrom TEXT,ValidTo TEXT,IsCurrent INTEGER,
                CHECK(ValidFrom<ValidTo),CHECK(IsCurrent IN (0,1)));
            CREATE UNIQUE INDEX OneCurrent ON Type2(Code) WHERE IsCurrent=1;
            INSERT INTO Type2 VALUES(1,'P01','Coffee','2012-01-01','9999-12-31',1);
            CREATE TABLE Type3(Code TEXT PRIMARY KEY,CurrentType TEXT,PreviousType TEXT);
            INSERT INTO Type3 VALUES('P01','Coffee',NULL);
        """)

        def change_type2(effective: str, category: str) -> None:
            with db:
                key, current_type, start = db.execute(
                    "SELECT ProductKey,ProductType,ValidFrom FROM Type2 WHERE Code='P01' AND IsCurrent=1"
                ).fetchone()
                if current_type == category:
                    return  # Replay of identical change creates no extra version.
                if effective <= start:
                    raise ValueError("Changes must arrive in effective-date order")
                db.execute("UPDATE Type2 SET ValidTo=?,IsCurrent=0 WHERE ProductKey=?", (effective, key))
                db.execute("INSERT INTO Type2(Code,ProductType,ValidFrom,ValidTo,IsCurrent) VALUES('P01',?,?,?,1)",
                           (category, effective, "9999-12-31"))

        change_type2("2013-01-01", "Specialty")
        change_type2("2013-01-01", "Specialty")
        lookups = []
        for month in ("2012-12-01", "2013-01-01", "2013-02-01"):
            matches = db.execute("SELECT ProductKey,ProductType FROM Type2 WHERE Code='P01' AND ValidFrom<=? AND ?<ValidTo",
                                 (month, month)).fetchall()
            assert len(matches) == 1
            lookups.append({"date": month, "key": matches[0][0], "type": matches[0][1]})
        overlaps = db.execute("""SELECT COUNT(*) FROM Type2 a JOIN Type2 b ON a.Code=b.Code
            AND a.ProductKey<b.ProductKey AND a.ValidFrom<b.ValidTo AND b.ValidFrom<a.ValidTo""").fetchone()[0]
        assert overlaps == 0
        assert db.execute("SELECT COUNT(*) FROM Type2 WHERE IsCurrent=1").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM Type2").fetchone()[0] == 2
        for category in ("Specialty", "Premium"):
            db.execute("UPDATE Type3 SET PreviousType=CurrentType,CurrentType=? WHERE Code='P01'", (category,))
        return {"synthetic": True, "engine": "SQLite in-memory", "source_modified": False,
                "type1": db.execute("SELECT * FROM Type1").fetchall(), "type2_lookups": lookups,
                "type2_versions_after_replay": 2, "overlaps": overlaps,
                "type3": db.execute("SELECT * FROM Type3").fetchall(),
                "type3_limit": "Only current and immediately previous category are retained"}


if __name__ == "__main__":
    result = run()
    destination = RESULTS_DIR / "TN04" / "scd.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
