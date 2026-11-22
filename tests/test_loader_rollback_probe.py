"""Pure safeguards for the optional native rollback probe; never connects to SQL."""
from decimal import Decimal
import importlib.util
from pathlib import Path

import pytest


PATH = Path(__file__).resolve().parents[1] / "scripts/native_ssas_trang/verify_loader_rollback.py"
SPEC = importlib.util.spec_from_file_location("native_rollback_probe", PATH)
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


def test_snapshot_encoding_preserves_types_nulls_and_whitespace():
    assert PROBE.row_bytes([Decimal("1.0000"), "1.0000", 1, None]) == b'[["decimal","1.0000"],["str","1.0000"],["int","1"],["null",null]]\n'
    assert PROBE.row_bytes(["West "]) != PROBE.row_bytes(["West"])
    assert PROBE.row_bytes([b"\x00\xff"]) == b'[["binary","00ff"]]\n'


def test_metadata_identifiers_cannot_be_sql_fragments():
    assert PROBE.quote("FactSalesPerformance") == "[FactSalesPerformance]"
    assert PROBE.quote("Area Code") == "[Area Code]"
    with pytest.raises(ValueError):
        PROBE.quote("FactSalesPerformance]; DELETE x;--")


def test_loader_guard_requires_error_after_updates_before_commit_and_rollback():
    source = (PATH.parents[2] / "sql/sqlserver/03_load_staging.sql").read_text(encoding="utf-8-sig")
    positions = PROBE.validate_loader(source)
    assert positions["UPDATE F SET SALES"] < positions["THROW 50006"] < positions["COMMIT TRANSACTION"]
    with pytest.raises(RuntimeError):
        PROBE.validate_loader(source.replace("THROW 50006", "THROW 59999"))
    with pytest.raises(RuntimeError):
        PROBE.validate_loader(source.replace("ROLLBACK TRANSACTION", "PRINT 'rollback omitted'"))


@pytest.mark.parametrize("diagnostic_first", [False, True])
def test_native_receipt_persists_across_266_before_or_after_resultset(diagnostic_first):
    receipt = ("CAUGHT_NATIVE_ERROR", 50006, 0)

    class Cursor:
        messages = []
        description = None if diagnostic_first else [(n,) for n in ("Result", "ErrorNumber", "OpenTransactions")]
        step = 0
        fetched = False

        def fetchall(self):
            if self.fetched:
                return []
            self.fetched = True
            return [receipt]

        def nextset(self):
            self.step += 1
            if self.step == 1:
                if diagnostic_first:
                    self.description = [(n,) for n in ("Result", "ErrorNumber", "OpenTransactions")]
                raise RuntimeError("Transaction count after EXECUTE indicates mismatch. (266)")
            self.description = None
            return False

    persisted = []
    frames, diagnostics = PROBE.consume_results(Cursor(), lambda rows, diag: persisted.append((list(rows), list(diag))))
    assert frames == [{"Result": "CAUGHT_NATIVE_ERROR", "ErrorNumber": 50006, "OpenTransactions": 0}]
    assert len(diagnostics) == 1 and PROBE.is_outer_rollback266(diagnostics[0]["message"])
    assert persisted and persisted[-1][0] == frames
