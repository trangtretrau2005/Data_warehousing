"""Summarize actual recorded measurements; never substitute synthetic timings."""

import argparse
import math
from pathlib import Path

import pandas as pd


def summarize(path: str | Path) -> pd.DataFrame:
    data = pd.read_csv(path)
    required = {"experiment", "variant", "warmup", "elapsed_ms", "logical_reads", "run_number"}
    if not required.issubset(data.columns):
        raise ValueError(f"Missing fields: {sorted(required - set(data.columns))}")
    warmup = data.warmup.astype(str).str.lower()
    if not warmup.isin(["true", "1", "yes", "false", "0", "no"]).all():
        raise ValueError("warmup must be an explicit true/false flag")
    data = data.loc[warmup.isin(["false", "0", "no"])].copy()
    if data.empty:
        raise ValueError("No measured runs. Fill benchmark_runs.csv after running SQL Server.")
    for name in ("elapsed_ms", "logical_reads"):
        data[name] = pd.to_numeric(data[name], errors="raise")
        if not data[name].map(math.isfinite).all() or data[name].lt(0).any():
            raise ValueError(f"{name} must be recorded as a nonnegative measurement")
    keys = ["experiment", "variant", "run_number"]
    if data.duplicated(keys).any():
        raise ValueError("Duplicate run identifier; separate different workloads/parameters")
    result = data.groupby(["experiment", "variant"]).agg(
        runs=("elapsed_ms", "size"), median_ms=("elapsed_ms", "median"),
        p95_ms=("elapsed_ms", lambda x: x.quantile(.95)),
        median_logical_reads=("logical_reads", "median")).reset_index()
    if result.runs.ne(15).any():
        raise ValueError("Protocol requires 15 measured runs per experiment/variant")
    for _, group in data.groupby(["experiment", "variant"]):
        if set(pd.to_numeric(group.run_number, errors="raise")) != set(range(1, 16)):
            raise ValueError("Measured run numbers must be exactly 1..15")
    for column in ("cpu_ms", "client_elapsed_ms"):
        if column in data and data[column].notna().all():
            values = pd.to_numeric(data[column], errors="raise")
            if not values.map(math.isfinite).all() or values.lt(0).any():
                raise ValueError(f"{column} must be finite and nonnegative")
            extra = data.assign(**{column: values}).groupby(["experiment", "variant"])[column].agg(
                **{f"median_{column}": "median", f"p95_{column}": lambda x: x.quantile(.95)}).reset_index()
            result = result.merge(extra, on=["experiment", "variant"], validate="one_to_one")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    args = parser.parse_args()
    output = summarize(args.csv)
    output.to_csv(args.csv.with_name("benchmark_summary.csv"), index=False)
    print(output.to_string(index=False))
