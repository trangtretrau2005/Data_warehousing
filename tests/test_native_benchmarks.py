"""Validate actual-plan extraction and experiment isolation without fake measurements."""
import importlib.util
from pathlib import Path

import pytest
import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_native_benchmarks.py"
spec = importlib.util.spec_from_file_location("native_bench", SCRIPT)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def test_database_guard_rejects_serving_and_sql_injection():
    assert native.safe_database("CoffeeDW_Trang_20261119") == "CoffeeDW_Trang_20261119"
    for value in ("CoffeeDW", "master", "CoffeeDW_Trang_x]; DROP DATABASE CoffeeDW;--", "CoffeeDW_Trang_"):
        with pytest.raises(ValueError):
            native.safe_database(value)


def test_runtime_metrics_sum_threads_and_keep_partition_evidence():
    # A minimal XML fixture tests parsing only; it is never saved as measured evidence.
    xml = '''<ShowPlanXML xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan">
    <BatchSequence><Batch><Statements><StmtSimple><QueryPlan>
    <QueryTimeStats CpuTime="12" ElapsedTime="8"/>
    <RelOp NodeId="0" PhysicalOp="Table Scan"><RunTimeInformation>
    <RunTimeCountersPerThread Thread="1" ActualLogicalReads="7"/>
    <RunTimeCountersPerThread Thread="2" ActualLogicalReads="11"/>
    </RunTimeInformation><TableScan><Object Table="[SalesPart]"/>
    <RunTimePartitionSummary><PartitionsAccessed PartitionCount="1">
    <PartitionRange Start="10" End="10"/>
    </PartitionsAccessed></RunTimePartitionSummary></TableScan></RelOp>
    </QueryPlan></StmtSimple></Statements></Batch></BatchSequence></ShowPlanXML>'''
    result = native.plan_metrics(xml)
    assert (result["cpu_ms"], result["elapsed_ms"], result["logical_reads"]) == (12, 8, 18)
    assert result["partitions_accessed"] == [{"count": 1, "ranges": [{"Start": "10", "End": "10"}]}]
    assert result["operators"][0]["physical_op"] == "Table Scan"


def test_estimated_plan_is_not_accepted_as_runtime_evidence():
    with pytest.raises(ValueError, match="actual plan"):
        native.plan_metrics('<ShowPlanXML xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan"><QueryPlan/></ShowPlanXML>')


def test_summary_rejects_nonfinite_missing_and_duplicate_runs(tmp_path):
    spec = importlib.util.spec_from_file_location("summarize", SCRIPT.with_name("summarize_benchmarks.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = pd.DataFrame([dict(experiment="unit_fixture", variant="A", warmup=False,
                              elapsed_ms=n, logical_reads=10, run_number=n) for n in range(1, 16)])
    path = tmp_path / "fixture.csv"
    data.to_csv(path, index=False)
    result = module.summarize(path)
    assert result.iloc[0].median_ms == 8
    for column, value in (("elapsed_ms", float("inf")), ("warmup", "unknown"), ("run_number", 99)):
        broken = data.copy()
        broken[column] = broken[column].astype(object)
        broken.loc[0, column] = value
        broken.to_csv(path, index=False)
        with pytest.raises(ValueError):
            module.summarize(path)
    data.iloc[:-1].to_csv(path, index=False)
    with pytest.raises(ValueError, match="15 measured"):
        module.summarize(path)
