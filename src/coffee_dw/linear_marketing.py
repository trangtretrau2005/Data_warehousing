"""Explainable Marketing–Sales linear regression at Market-month grain.

This is a descriptive/scenario model. It uses same-month Marketing, so it must
not be presented as a one-month-ahead forecast or as a causal effect.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


TEST_MONTHS = 6
MODEL_VERSION = "marketing-sales-linear-v1-time-split"


def monthly_marketing_sales(detail: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the warehouse fact to one observation per Market and month."""
    required = {"MonthStart", "Market", "Marketing", "Sales"}
    if not required.issubset(detail.columns):
        raise ValueError("Dữ liệu hồi quy thiếu MonthStart, Market, Marketing hoặc Sales.")
    frame = detail.groupby(["MonthStart", "Market"], as_index=False)[["Marketing", "Sales"]].sum()
    frame["MonthStart"] = pd.to_datetime(frame["MonthStart"], errors="raise")
    return frame.sort_values(["Market", "MonthStart"]).reset_index(drop=True)


def _validate_monthly(frame: pd.DataFrame, test_months: int) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    required = {"MonthStart", "Market", "Marketing", "Sales"}
    if not required.issubset(frame.columns) or frame.empty:
        raise ValueError("Cần bảng Market–tháng có Marketing và Sales.")
    if not isinstance(test_months, int) or test_months < 2:
        raise ValueError("Cần ít nhất hai tháng test.")
    frame = frame[list(required)].copy()
    frame["MonthStart"] = pd.to_datetime(frame["MonthStart"], errors="raise")
    if not frame["MonthStart"].dt.is_month_start.all() or frame.duplicated(["MonthStart", "Market"]).any():
        raise ValueError("Dữ liệu hồi quy phải duy nhất theo Market–tháng và dùng ngày đầu tháng.")
    for column in ("Marketing", "Sales"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    if not np.isfinite(frame[["Marketing", "Sales"]].to_numpy(dtype=float)).all():
        raise ValueError("Marketing và Sales phải là số hữu hạn; không đổi thiếu thành 0.")
    months = pd.DatetimeIndex(sorted(frame["MonthStart"].unique()))
    if len(months) < test_months + 6 or not months.equals(pd.date_range(months.min(), months.max(), freq="MS")):
        raise ValueError("Chuỗi cần đủ tháng liên tục để tách train và test theo thời gian.")
    expected = set(months)
    for market, group in frame.groupby("Market"):
        if set(group["MonthStart"]) != expected or len(group) != len(months):
            raise ValueError(f"Market {market} thiếu tháng; không nội suy hoặc bù 0 cho hồi quy.")
    return frame.sort_values(["Market", "MonthStart"]).reset_index(drop=True), months


def build_linear_analysis(monthly: pd.DataFrame, test_months: int = TEST_MONTHS) -> dict[str, Any]:
    """Fit one explainable model per Market using a chronological holdout."""
    frame, months = _validate_monthly(monthly, test_months)
    test_start = months[-test_months]
    markets: list[dict[str, Any]] = []
    for market, group in frame.groupby("Market", sort=True):
        group = group.sort_values("MonthStart").reset_index(drop=True)
        train = group.loc[group["MonthStart"].lt(test_start)].copy()
        test = group.loc[group["MonthStart"].ge(test_start)].copy()
        model = LinearRegression().fit(train[["Marketing"]], train["Sales"])
        group["Prediction"] = model.predict(group[["Marketing"]])
        group["Split"] = np.where(group["MonthStart"].lt(test_start), "train", "test")
        group["Residual"] = group["Sales"] - group["Prediction"]
        test_prediction = model.predict(test[["Marketing"]])
        baseline_prediction = np.repeat(float(train["Sales"].mean()), len(test))
        mae = float(mean_absolute_error(test["Sales"], test_prediction))
        baseline_mae = float(mean_absolute_error(test["Sales"], baseline_prediction))
        x_min = float(group["Marketing"].min() * 0.7)
        x_max = float(group["Marketing"].max() * 1.5)
        line_x = pd.DataFrame({"Marketing": [x_min, x_max]})
        reference = group.iloc[-1]
        points = [
            {
                "month": row.MonthStart.strftime("%Y-%m-%d"),
                "marketing": float(row.Marketing),
                "sales": float(row.Sales),
                "prediction": float(row.Prediction),
                "residual": float(row.Residual),
                "split": row.Split,
            }
            for row in group.itertuples(index=False)
        ]
        markets.append(
            {
                "market": str(market),
                "n": len(group),
                "trainN": len(train),
                "testN": len(test),
                "coefficient": float(model.coef_[0]),
                "intercept": float(model.intercept_),
                "correlationAll": float(group["Marketing"].corr(group["Sales"])),
                "trainR2": float(model.score(train[["Marketing"]], train["Sales"])),
                "testR2": float(r2_score(test["Sales"], test_prediction)),
                "testMAE": mae,
                "testRMSE": float(np.sqrt(mean_squared_error(test["Sales"], test_prediction))),
                "baselineMAE": baseline_mae,
                "maeImprovementPct": float((baseline_mae - mae) / baseline_mae * 100) if baseline_mae else 0.0,
                "referenceMonth": reference.MonthStart.strftime("%Y-%m-%d"),
                "referenceMarketing": float(reference.Marketing),
                "referenceSales": float(reference.Sales),
                "referencePrediction": float(reference.Prediction),
                "line": [
                    {"marketing": float(x), "prediction": float(y)}
                    for x, y in zip(line_x["Marketing"], model.predict(line_x), strict=True)
                ],
                "points": points,
            }
        )
    return {
        "meta": {
            "model": "LinearRegression",
            "modelVersion": MODEL_VERSION,
            "grain": "MonthStart × Market",
            "feature": "SUM(Marketing) cùng tháng",
            "target": "SUM(Sales) cùng tháng",
            "trainStart": months[0].strftime("%Y-%m-%d"),
            "trainEnd": (test_start - pd.offsets.MonthBegin(1)).strftime("%Y-%m-%d"),
            "testStart": test_start.strftime("%Y-%m-%d"),
            "testEnd": months[-1].strftime("%Y-%m-%d"),
            "testMonths": test_months,
            "scenarioMinPct": -30,
            "scenarioMaxPct": 50,
            "warning": (
                "Marketing và Sales cùng tháng chỉ cho thấy liên hệ. Kịch bản không chứng minh Marketing gây ra Sales "
                "và không thay dự báo một tháng tới từ lịch sử Sales."
            ),
        },
        "markets": markets,
    }
