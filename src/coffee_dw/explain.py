"""Exact additive explanations relative to training-feature means.

These are model contributions, not causal explanations of business outcomes.
No future actual, test error, or external context is used to build a forecast.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from coffee_dw.forecast import METHODS, fit_ridge_model, predict_next


def explain_history(history: pd.Series, method: str) -> dict:
    if method not in METHODS:
        raise ValueError(f"Unknown forecast method: {method}")
    history = history.sort_index()
    values = np.asarray(history, dtype=float)
    if len(values) < 6 or not np.isfinite(values).all():
        raise ValueError("Explanation requires at least six finite historical values")
    dates = pd.DatetimeIndex(history.index)
    if not dates.equals(pd.date_range(dates.min(), dates.max(), freq="MS")):
        raise ValueError("History must have a unique, contiguous month-start index")
    train_x = np.array([values[i - 3:i][::-1] for i in range(3, len(values))])
    reference = train_x.mean(axis=0)
    observed = values[-3:][::-1]
    if method == "ridge":
        pipeline = fit_ridge_model(values)
        scaler, ridge = pipeline.steps[0][1], pipeline.steps[1][1]
        weights = ridge.coef_ / scaler.scale_
        base = float(ridge.intercept_)
    else:
        weights = np.array([1., 0., 0.]) if method == "naive_last" else np.full(3, 1 / 3)
        base = float(np.dot(weights, reference))
    contributions = weights * (observed - reference)
    prediction = predict_next(history, method)
    reconstructed = base + float(contributions.sum())
    error = abs(reconstructed - prediction)
    if error > 1e-6:
        raise ArithmeticError("Explanation does not reconstruct the reference forecast")
    return {
        "prediction": prediction, "base_value": base,
        "reconstructed_prediction": reconstructed, "reconstruction_error": error,
        "history_n": len(values), "ridge_training_rows": len(train_x),
        "reference_policy": "Mean of each lag column in historical supervised training rows",
        "features": [
            {"lag": i + 1, "month": dates[-(i + 1)].strftime("%Y-%m-%d"),
             "label": f"Tháng {dates[-(i + 1)]:%m/%Y}", "value": float(observed[i]),
             "reference_value": float(reference[i]), "weight_raw": float(weights[i]),
             "contribution": float(contributions[i])}
            for i in range(3)
        ],
        "caveat": "Đóng góp so với mức nền của mô hình; không phải nguyên nhân kinh doanh hay tác động nhân quả.",
    }
