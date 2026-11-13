"""Read the immutable source, reject structural errors, and retain business anomalies."""

from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

import pandas as pd

from coffee_dw.config import SOURCE_PATH

COLUMN_MAP = {
    "Area Code": "AreaCode", "Date": "ExcelDate", "Market": "Market",
    "Market Size": "MarketSize", "Product": "ProductName", "Product Line": "ProductLine",
    "Product Type": "ProductType", "State": "State", "Type": "Type",
    "Budget COGS": "BudgetCOGS", "Budget Margin": "BudgetMargin",
    "Budget Profit": "BudgetProfit", "Budget Sales": "BudgetSales", "COGS": "COGS",
    "Inventory": "Inventory", "Margin": "Margin", "Marketing": "Marketing",
    "Profit": "Profit", "Sales": "Sales", "Total Expenses": "TotalExpenses",
}
MEASURES = ["Sales", "BudgetSales", "Profit", "BudgetProfit", "COGS", "BudgetCOGS",
            "Margin", "BudgetMargin", "Marketing", "Inventory", "TotalExpenses"]
LOCATION_ATTRIBUTES = ["AreaCode", "State", "Market", "MarketSize"]
PRODUCT_ATTRIBUTES = ["ProductName", "ProductLine", "ProductType", "Type"]
GRAIN = ["DateKey", "AreaCode", "ProductName"]
NORMALIZED_COLUMNS = ["MonthStart", "DateKey", *LOCATION_ATTRIBUTES, *PRODUCT_ATTRIBUTES,
                      *MEASURES, "SourceRow", "RawPayload"]
SCALE = 10_000


def _scaled(value: str) -> int:
    amount = Decimal(str(value).strip())
    if not amount.is_finite() or amount.as_tuple().exponent < -4:
        raise ValueError("expected a finite number with at most four decimal places")
    scaled = amount * SCALE
    # Both SQLite's scaled integer and SQL Server DECIMAL(19,4) must accommodate it.
    if abs(scaled) > 9_223_372_036_854_775_807:
        raise ValueError("amount outside supported fixed-point range")
    return int(scaled)


def read_source(path: str | Path = SOURCE_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return valid normalized rows and rejected rows with physical CSV row numbers.

    A conflicting grain is rejected in full, rather than arbitrarily picking a winner.
    Source rows use CSV record positions (header is row 1); quoted multiline cells can
    span multiple physical lines. Accounting discrepancies and negative values remain.
    """
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, skip_blank_lines=False,
                      encoding="utf-8-sig")
    missing = set(COLUMN_MAP) - set(raw.columns)
    if missing:
        raise ValueError(f"Missing source columns: {', '.join(sorted(missing))}")
    records, rejected = [], []
    for source_row, payload in enumerate(raw.to_dict("records"), start=2):
        row = {target: str(payload[source]).strip() for source, target in COLUMN_MAP.items()}
        errors = []
        for name in [*LOCATION_ATTRIBUTES, *PRODUCT_ATTRIBUTES]:
            if not row[name]:
                errors.append(f"{name}: required")
        try:
            serial = Decimal(row.pop("ExcelDate"))
            if not serial.is_finite() or serial != int(serial):
                raise ValueError("date serial must be an integer")
            month = pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(serial))
            if month.day != 1:
                raise ValueError("expected month-start date")
            row.update(MonthStart=month, DateKey=int(month.strftime("%Y%m%d")))
        except (InvalidOperation, ValueError, OverflowError, pd.errors.OutOfBoundsDatetime) as exc:
            errors.append(f"Date: {exc}")
        for name in MEASURES:
            try:
                row[name] = _scaled(row[name]) / SCALE
            except (InvalidOperation, ValueError, OverflowError) as exc:
                errors.append(f"{name}: invalid numeric value ({exc})")
        row.update(SourceRow=source_row, RawPayload=json.dumps(payload, ensure_ascii=False))
        if errors:
            rejected.append({"SourceRow": source_row, "Reason": "; ".join(errors),
                             "RawPayload": row["RawPayload"]})
        else:
            records.append(row)
    valid = pd.DataFrame(records, columns=NORMALIZED_COLUMNS)
    if not valid.empty:
        # Conflicting parent attributes would multiply joins or overwrite history.
        bad_indices: set[int] = set(valid.index[valid.duplicated(GRAIN, keep=False)])
        reasons: dict[int, list[str]] = {i: ["duplicate candidate grain"] for i in bad_indices}
        for key, attrs in [("AreaCode", LOCATION_ATTRIBUTES[1:]),
                           ("ProductName", PRODUCT_ATTRIBUTES[1:])]:
            inconsistent = valid.groupby(key)[attrs].nunique().max(axis=1).gt(1)
            keys = set(inconsistent[inconsistent].index)
            for i in valid.index[valid[key].isin(keys)]:
                bad_indices.add(i)
                reasons.setdefault(i, []).append(f"conflicting attributes for {key}")
        for i in sorted(bad_indices):
            rejected.append({"SourceRow": int(valid.loc[i, "SourceRow"]),
                             "Reason": "; ".join(reasons[i]),
                             "RawPayload": valid.loc[i, "RawPayload"]})
        valid = valid.drop(index=sorted(bad_indices)).reset_index(drop=True)
        valid["MonthStart"] = pd.to_datetime(valid["MonthStart"])
    errors_frame = pd.DataFrame(rejected, columns=["SourceRow", "Reason", "RawPayload"])
    if not errors_frame.empty:
        errors_frame = errors_frame.sort_values("SourceRow").reset_index(drop=True)
    return valid, errors_frame


def profile(path: str | Path = SOURCE_PATH) -> dict:
    valid, rejected = read_source(path)
    result = {"source": str(Path(path)), "source_rows": len(valid) + len(rejected),
              "accepted_rows": len(valid), "rejected_rows": len(rejected),
              "grain": GRAIN, "date_origin": "1899-12-30",
              "currency": "Unspecified in source", "observed_time_grain": "month"}
    if valid.empty:
        return result
    result.update(
        date_start=valid.MonthStart.min().strftime("%Y-%m-%d"),
        date_end=valid.MonthStart.max().strftime("%Y-%m-%d"),
        months=int(valid.MonthStart.nunique()), markets=int(valid.Market.nunique()),
        states=int(valid.State.nunique()), locations=int(valid.AreaCode.nunique()),
        products=int(valid.ProductName.nunique()),
        totals={name: float(valid[name].sum()) for name in MEASURES if name != "Inventory"},
        warnings={
            "negative_profit": int(valid.Profit.lt(0).sum()),
            "negative_inventory": int(valid.Inventory.lt(0).sum()),
            "sales_not_cogs_plus_margin": int((valid.Sales - valid.COGS - valid.Margin).abs().gt(0.00005).sum()),
            "profit_not_margin_minus_expenses": int((valid.Profit - valid.Margin + valid.TotalExpenses).abs().gt(0.00005).sum()),
        },
        inventory_policy="Snapshot: do not sum across months; display the selected month.",
    )
    return result
