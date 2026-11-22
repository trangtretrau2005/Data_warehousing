"""Reconcile SQLite/native detail and publish forecasts to an existing native mart.

This never loads or modifies business facts. Set COFFEE_DW_SQLSERVER_CONNECTION
to an isolated/approved database created using the team's native schema.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

from coffee_dw.config import DB_PATH, SOURCE_PATH
from coffee_dw.forecast import evaluate_monthly, monthly_sales
from coffee_dw.serving import connect_native, dashboard_detail, dashboard_forecast, native_query
from coffee_dw.source import MEASURES


def run(output: Path, db_path: Path = DB_PATH):
    output.mkdir(parents=True, exist_ok=True)
    reference = dashboard_detail(db_path, "sqlite")
    native = dashboard_detail(db_path, "sqlserver")
    keys = ["MonthStart", "AreaCode", "ProductName"]
    dimensions = ["State", "Market", "MarketSize", "ProductLine", "ProductType", "Type", "DateKey", "SourceRow"]
    columns = keys + dimensions + list(MEASURES)
    for label, frame in (("sqlite", reference), ("sqlserver", native)):
        if frame.duplicated(keys).any():
            raise ValueError(f"Trùng grain: {label}")
    left = reference[columns].sort_values(keys).reset_index(drop=True)
    right = native[columns].sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right, check_dtype=False, atol=0.00005, rtol=0)
    source_monthly = monthly_sales(reference).rename(columns={"Sales": "SQLiteSales"})
    native_monthly = monthly_sales(native).rename(columns={"Sales": "NativeSales"})
    reconciled = source_monthly.merge(native_monthly, on=["Market", "MonthStart"], validate="one_to_one", how="outer")
    reconciled["Delta"] = reconciled.NativeSales - reconciled.SQLiteSales
    assert len(reconciled) == 96 and reconciled.Delta.abs().max() < 0.00005
    reconciled.to_csv(output / "monthly_reconciliation.csv", index=False)
    predictions, metrics, future, summary = evaluate_monthly(monthly_sales(native))
    combined = pd.concat([predictions, future], ignore_index=True)
    columns = ["Market", "ForecastMonth", "IssueMonth", "TrainEnd", "ModelName", "ModelVersion", "Prediction", "Actual", "Split"]
    for column in ("ForecastMonth", "IssueMonth", "TrainEnd"):
        combined[column] = combined[column].dt.date
    records = [tuple(None if pd.isna(v) else v for v in row) for row in combined[columns].itertuples(index=False, name=None)]
    connection = connect_native()
    try:
        cursor = connection.cursor()
        # Replay twice to verify idempotence. Only keys being published are touched.
        for _ in range(2):
            for row in records:
                market, target, issue, train_end, model, version, prediction, actual, split = row
                key = (market, target, issue, model, version)
                cursor.execute("UPDATE ml.ForecastSales SET TrainEnd=?,Prediction=?,Actual=?,Split=? "
                               "WHERE Market=? AND ForecastMonth=? AND IssueMonth=? AND ModelName=? AND ModelVersion=?",
                               train_end, prediction, actual, split, *key)
                if cursor.rowcount == 0:
                    cursor.execute("INSERT ml.ForecastSales (Market,ForecastMonth,IssueMonth,TrainEnd,ModelName,ModelVersion,Prediction,Actual,Split) "
                                   "VALUES (?,?,?,?,?,?,?,?,?)", *row)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    returned_summary, returned_metrics, returned_predictions, returned_future = dashboard_forecast(output, "sqlserver")
    for expected, observed in ((predictions, returned_predictions), (future, returned_future)):
        key = ["Market", "ForecastMonth", "ModelName"]
        a = expected.sort_values(key).reset_index(drop=True)
        b = observed.sort_values(key).reset_index(drop=True)
        assert len(a) == len(b)
        assert np.allclose(a.Prediction, b.Prediction, atol=0.00005, rtol=0)
    assert returned_summary["selected_model"] == summary["selected_model"]
    observed_count = int(native_query("SELECT COUNT(*) N FROM ml.ForecastSales WHERE ModelVersion=?", (summary["model_version"],)).iloc[0, 0])
    assert observed_count == len(combined), "Có bản phát hành khác; cần chỉ rõ phạm vi nghiệm thu."
    returned_metrics.to_csv(output / "native_metrics.csv", index=False)
    returned_predictions.to_csv(output / "native_predictions.csv", index=False)
    returned_future.to_csv(output / "native_future.csv", index=False)
    report = {
        "status": "passed", "source_sha256": hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest(),
        "detail_rows": len(native), "detail_measures_checked": len(MEASURES), "monthly_cells": len(reconciled),
        "sales": float(native.Sales.sum()), "budget_sales": float(native.BudgetSales.sum()), "profit": float(native.Profit.sum()),
        "forecast_rows_after_replay": observed_count, "future_actual_nulls": int(returned_future.Actual.isna().sum()),
        "selected_model": summary["selected_model"], "max_publication_rounding": 0.00005,
        "limits": "Native integration on an isolated database; not Chi's SSIS/SSAS acceptance or a human UX trial.",
    }
    (output / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/trang_completion/native_serving"))
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.db), ensure_ascii=False, indent=2))
