"""Small, predeclared hyperparameter study; never publishes to the dashboard.

Validation selects a single configuration globally. Previously seen test months
are descriptive checks of an exploratory extension, not a fresh blind test.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from coffee_dw.baseline_study import (
    TEST_MONTHS, VALIDATION_MONTHS, error_table, prepare_inputs,
    relative_improvement, score, sha, utc, validate_monthly, write_json, write_table,
)
from coffee_dw.config import ROOT, SOURCE_PATH


@dataclass(frozen=True)
class Candidate:
    key: str
    family: str
    label: str
    window: int | None = None
    alpha: float | None = None
    lags: int = 3


CANDIDATES = (
    Candidate("naive_last", "Naive", "Naive"),
    Candidate("ma_w2", "MA", "MA · 2 tháng", window=2),
    Candidate("ma_w3", "MA", "MA · 3 tháng", window=3),
    Candidate("ma_w6", "MA", "MA · 6 tháng", window=6),
    Candidate("ridge_a0p1", "Ridge", "Ridge · α = 0,1", alpha=0.1),
    Candidate("ridge_a1", "Ridge", "Ridge · α = 1", alpha=1.0),
    Candidate("ridge_a10", "Ridge", "Ridge · α = 10", alpha=10.0),
)
BY_KEY = {c.key: c for c in CANDIDATES}
LABELS = {c.key: c.label for c in CANDIDATES}
REFERENCE_KEYS = ("naive_last", "ma_w3", "ridge_a1")
MODEL_VERSION = "tuning-v1-ma236-ridge-a0p1-1-10-lag123"


def specifications():
    return pd.DataFrame([
        {"ModelName": c.key, "Label": c.label, "Family": c.family,
         "Window": c.window, "Alpha": c.alpha,
         "Features": "lag1, lag2, lag3" if c.family == "Ridge" else "lag1" if c.family == "Naive" else f"last {c.window} months",
         "LearnsCoefficients": c.family == "Ridge",
         "LearnedParameters": "3 coefficients + intercept; scaler mean/scale" if c.family == "Ridge" else "No learned coefficients; history state only",
         "FixedSettings": "StandardScaler; fit_intercept=True; solver=svd; no random split" if c.family == "Ridge" else "arithmetic rule; no epochs",
         "InPreviousBaseline": c.key in REFERENCE_KEYS, "TieOrder": i}
        for i, c in enumerate(CANDIDATES)
    ])


def history_values(history):
    values = np.asarray(history, dtype=float)
    if values.ndim != 1 or len(values) < 6 or not np.isfinite(values).all():
        raise ValueError("Cần ít nhất 6 tháng lịch sử hữu hạn, liên tục.")
    return values


def lag_matrix(values):
    return np.array([values[i - 3:i][::-1] for i in range(3, len(values))])


def fit_candidate(history, candidate):
    values = history_values(history)
    if candidate.family != "Ridge":
        return None
    # Deterministic solver, fixed before any validation scores are inspected.
    pipeline = make_pipeline(StandardScaler(), Ridge(alpha=candidate.alpha, solver="svd"))
    pipeline.fit(lag_matrix(values), values[3:])
    return pipeline


def predict_fitted(history, candidate, pipeline=None):
    values = history_values(history)
    if candidate.family == "Naive":
        return float(values[-1])
    if candidate.family == "MA":
        return float(values[-candidate.window:].mean())
    if pipeline is None:
        raise ValueError("Ridge cần pipeline đã fit trên lịch sử.")
    return float(pipeline.predict(values[-3:][::-1].reshape(1, -1))[0])


def learned_parameters(pipeline, common):
    scaler, ridge = pipeline.steps[0][1], pipeline.steps[1][1]
    raw_coef = ridge.coef_ / scaler.scale_
    raw_intercept = float(ridge.intercept_ - np.dot(raw_coef, scaler.mean_))
    return [common | {"Feature": f"lag{i+1}", "FitN": int(scaler.n_samples_seen_),
                      "MeanTrain": float(scaler.mean_[i]), "ScaleTrain": float(scaler.scale_[i]),
                      "CoefficientScaled": float(ridge.coef_[i]), "CoefficientRaw": float(raw_coef[i]),
                      "InterceptScaled": float(ridge.intercept_), "InterceptRaw": raw_intercept,
                      "Alpha": float(ridge.alpha), "Solver": ridge.solver}
            for i in range(3)]


def evaluate_phase(monthly, split):
    if split not in ("validation", "test"):
        raise ValueError("Pha phải là validation hoặc test.")
    validate_monthly(monthly)
    targets = VALIDATION_MONTHS if split == "validation" else TEST_MONTHS
    predictions, origins, parameters = [], [], []
    for market, part in monthly.groupby("Market", sort=True):
        series = part.set_index("MonthStart").Sales.sort_index()
        for target in targets:
            history = series.loc[series.index < target]
            values = history.to_numpy(dtype=float)
            for c in CANDIDATES:
                start = time.perf_counter()
                pipeline = fit_candidate(history, c)
                prediction = predict_fitted(history, c, pipeline)
                elapsed = time.perf_counter() - start
                common = {"Market": market, "ForecastMonth": target, "IssueMonth": history.index[-1],
                          "TrainEnd": history.index[-1], "ModelName": c.key,
                          "ModelVersion": MODEL_VERSION, "Split": split}
                predictions.append(common | {"Prediction": prediction, "Actual": float(series.loc[target])})
                training_mae = training_rmse = np.nan
                if pipeline is not None:
                    residual = pipeline.predict(lag_matrix(values)) - values[3:]
                    training_mae = float(np.abs(residual).mean())
                    training_rmse = float(np.sqrt(np.mean(residual**2)))
                    parameters.extend(learned_parameters(pipeline, common))
                origins.append(common | {"Family": c.family, "Window": c.window, "Alpha": c.alpha,
                    "HistoryStart": history.index[0], "HistoryN": len(history),
                    "TrainingTargetStart": history.index[3] if pipeline is not None else pd.NaT,
                    "FitN": len(history)-3 if pipeline is not None else 0,
                    "FitPredictSeconds": elapsed, "InSampleMAE": training_mae,
                    "InSampleRMSE": training_rmse, "Lag1": float(values[-1]),
                    "Lag2": float(values[-2]), "Lag3": float(values[-3])})
    predictions = pd.DataFrame(predictions)
    return predictions, score(predictions), pd.DataFrame(origins), pd.DataFrame(parameters)


def choose_configuration(metrics):
    if set(metrics.Split) != {"validation"}:
        raise ValueError("Chỉ lựa chọn bằng validation; không dùng test.")
    board = metrics.loc[metrics.Market.eq("ALL")].copy()
    if len(board) != len(CANDIDATES) or set(board.ModelName) != set(BY_KEY):
        raise ValueError("Cần đủ bảy cấu hình, mỗi cấu hình một dòng ALL.")
    if not np.isfinite(board.MAE).all() or not board.N.eq(24).all():
        raise ValueError("Mỗi cấu hình cần cùng 24 dự báo validation hữu hạn.")
    order = {c.key: i for i, c in enumerate(CANDIDATES)}
    board["TieOrder"] = board.ModelName.map(order)
    board = board.sort_values(["MAE", "TieOrder"]).reset_index(drop=True)
    board["Rank"] = np.arange(1, len(board)+1)
    selected = str(board.iloc[0].ModelName)
    board["Selected"] = board.ModelName.eq(selected)
    board["Label"] = board.ModelName.map(LABELS)
    return selected, board


def previous_baseline(metrics):
    part = metrics.loc[metrics.ModelName.isin(REFERENCE_KEYS)].copy()
    return part.sort_values(["MAE", "ModelName"]).iloc[0]


def validation_diagnostics(predictions):
    rows = []
    for (key, month), part in predictions.groupby(["ModelName", "ForecastMonth"], sort=True):
        rows.append({"ModelName": key, "ForecastMonth": month, "N": len(part),
                     "MAE": float((part.Prediction-part.Actual).abs().mean())})
    per_month = pd.DataFrame(rows)
    stability = []
    for omitted in VALIDATION_MONTHS:
        retained = predictions.loc[predictions.ForecastMonth.ne(omitted)]
        pooled = score(retained).loc[lambda x: x.Market.eq("ALL")].copy()
        pooled["TieOrder"] = pooled.ModelName.map({c.key: i for i, c in enumerate(CANDIDATES)})
        pooled = pooled.sort_values(["MAE", "TieOrder"])
        winner = pooled.iloc[0]
        stability.append({"OmittedValidationMonth": omitted, "Winner": winner.ModelName,
                          "MAE": float(winner.MAE), "N": int(winner.N),
                          "Purpose": "descriptive sensitivity; not selection or independent CV"})
    return per_month, pd.DataFrame(stability)


def export_final_states(monthly, selected, output):
    """Refit each Ridge on all 24 known months; save every candidate's state."""
    output = Path(output)
    rows, states, parameters, exports = [], [], [], []
    for market, part in monthly.groupby("Market", sort=True):
        history = part.set_index("MonthStart").Sales.sort_index()
        for c in CANDIDATES:
            pipeline = fit_candidate(history, c)
            prediction = predict_fitted(history, c, pipeline)
            common = {"Market": market, "ForecastMonth": pd.Timestamp("2014-01-01"),
                      "IssueMonth": history.index[-1], "TrainEnd": history.index[-1],
                      "ModelName": c.key, "ModelVersion": MODEL_VERSION, "Split": "future"}
            rows.append(common | {"Prediction": prediction, "Actual": np.nan,
                                  "LastActual": float(history.iloc[-1]), "Selected": c.key == selected})
            state_path = f"05_models/{c.key}/{market}.json"
            state = {"candidate": asdict(c), "market": market, "train_end": "2013-12-01",
                     "forecast_month": "2014-01-01", "prediction": prediction,
                     "history_n": len(history), "selected": c.key == selected,
                     "observations": [{"month": date.strftime("%Y-%m-%d"), "sales": float(value)}
                                      for date, value in history.tail(c.window if c.family == "MA" else 3 if pipeline is not None else 1).items()]}
            model_path = None
            if pipeline is not None:
                learned = learned_parameters(pipeline, common)
                state["estimator_settings"] = {
                    "scaler": pipeline.steps[0][1].get_params(deep=False),
                    "ridge": pipeline.steps[1][1].get_params(deep=False),
                }
                parameters.extend(learned)
                state["learned_parameters"] = learned
                # Timestamps in the audit are stored as strings for portable JSON.
                state["learned_parameters"] = [
                    {k: v.strftime("%Y-%m-%d") if isinstance(v, pd.Timestamp) else v for k, v in row.items()}
                    for row in learned]
                model_path = f"05_models/{c.key}/{market}.joblib"
                (output/model_path).parent.mkdir(parents=True, exist_ok=True)
                joblib.dump(pipeline, output/model_path)
                reloaded = joblib.load(output/model_path)
                if not np.isclose(predict_fitted(history, c, reloaded), prediction, rtol=1e-12):
                    raise RuntimeError("Model nạp lại không tái tạo dự báo.")
            write_json(output/state_path, state)
            states.append(state)
            exports.append({"Market": market, "ModelName": c.key, "Selected": c.key == selected,
                            "StatePath": state_path, "ModelPath": model_path,
                            "LearnsCoefficients": pipeline is not None,
                            "FitN": len(history)-3 if pipeline is not None else 0,
                            "Prediction": prediction})
    return pd.DataFrame(rows), pd.DataFrame(parameters), pd.DataFrame(exports), states


def run_study(source=SOURCE_PATH, output=ROOT/"experiments"/"tuning"/"results", *, render=True):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    events = []
    def event(stage, note):
        events.append({"Sequence": len(events)+1, "TimestampUTC": utc(), "Stage": stage, "Note": note})
    def save(path, table):
        write_table(output, path, table)

    event("input", "Nguồn CSV; không ghi kho hoặc gói dữ liệu dashboard")
    monthly, features, checks, _, source_info = prepare_inputs(source)
    save("01_protocol/source_profile.csv", pd.DataFrame([source_info]))
    save("01_protocol/input_checks.csv", checks)
    save("01_protocol/monthly_market.csv", monthly)
    save("01_protocol/feature_availability.csv", features)
    save("01_protocol/first_origin_training.csv", features.loc[features.CompleteLag123 & features.Split.eq("initial_history")])
    save("01_protocol/configurations.csv", specifications())
    protocol = {"created_at_utc": utc(), "study_type": "exploratory_extension_after_seen_test",
        "source_sha256": source_info["sha256"], "target": "Sales per Market, one month ahead",
        "initial_history": "2012-01 to 2013-03; 15 months", "validation": "2013-04 to 2013-09; 6 months",
        "test": "2013-10 to 2013-12; 3 previously seen months", "test_previously_seen": True,
        "candidates": [asdict(c) for c in CANDIDATES], "model_version": MODEL_VERSION,
        "selection": "Minimum pooled validation MAE; exact ties follow declared candidate order",
        "rolling_origin": "expanding past history; actual from a test month can enter the next month's history after observed",
        "ridge_fixed": {"features": ["lag1", "lag2", "lag3"], "scaler": "StandardScaler; fit only historical training features",
                        "fit_intercept": True, "solver": "svd", "random_state": "not used by deterministic SVD"},
        "metrics": {"primary": "MAE", "secondary": ["RMSE", "MAPE", "Bias"], "MAPE_zero_actual": "exclude; report MAPE_N"},
        "not_searched": ["lag count", "solver", "algorithms outside the seven declared configurations"],
        "training_metric_note": "InSampleMAE/RMSE describe fitted Ridge training residuals only; never select by them",
        "sensitivity_note": "Omit one validation month descriptively; not independent folds and not used to reselect"}
    write_json(output/"01_protocol/protocol.json", protocol)
    write_json(output/"01_protocol/estimator_settings.json", {
        c.key: {"candidate": asdict(c),
                "scaler": StandardScaler().get_params(deep=False) if c.family == "Ridge" else None,
                "estimator": Ridge(alpha=c.alpha, solver="svd").get_params(deep=False) if c.family == "Ridge" else None}
        for c in CANDIDATES
    })
    event("grid_saved", "Đã lưu toàn bộ 7 cấu hình trước đánh giá validation")
    val, val_metrics, val_origins, val_fit = evaluate_phase(monthly, "validation")
    for name, table in [("predictions", val), ("metrics", val_metrics), ("origin_schedule", val_origins), ("learned_parameters", val_fit)]:
        save(f"02_validation/{name}.csv", table)
    selected, board = choose_configuration(val_metrics)
    save("02_validation/leaderboard.csv", board)
    save("01_protocol/first_origin_scaler.csv", val_fit.loc[val_fit.ForecastMonth.eq(VALIDATION_MONTHS[0])])
    per_month, stability = validation_diagnostics(val)
    save("02_validation/mae_by_month.csv", per_month)
    save("02_validation/sensitivity.csv", stability)
    ref = previous_baseline(board)
    decision = {"created_at_utc": utc(), "selected_configuration": selected, "label": LABELS[selected],
        "hyperparameters": asdict(BY_KEY[selected]), "validation_MAE": float(board.iloc[0].MAE), "validation_N": 24,
        "previous_baseline_selected": str(ref.ModelName), "previous_baseline_validation_MAE": float(ref.MAE),
        "validation_gain_vs_baseline_pct": float(100*(ref.MAE-board.iloc[0].MAE)/ref.MAE),
        "test_used_for_selection": False, "test_previously_seen": True,
        "criterion": protocol["selection"], "source_sha256": source_info["sha256"],
        "validation_predictions_sha256": sha(output/"02_validation/predictions.csv")}
    write_json(output/"02_validation/selection.json", decision)
    decision_sha = sha(output/"02_validation/selection.json")
    event("selection_saved", f"Khóa lựa chọn từ validation: {selected}; sha256={decision_sha}")
    event("test_started", "Kiểm tra mô tả trên test đã biết; không thay cấu hình theo test")
    test, test_metrics, test_origins, test_fit = evaluate_phase(monthly, "test")
    if sha(output/"02_validation/selection.json") != decision_sha:
        raise RuntimeError("Lựa chọn bị đổi trong pha test.")
    for name, table in [("predictions", test), ("metrics", test_metrics), ("origin_schedule", test_origins), ("learned_parameters", test_fit)]:
        save(f"03_test/{name}.csv", table)
    save("03_test/selected_metrics.csv", test_metrics.loc[test_metrics.ModelName.eq(selected)])
    errors = error_table(pd.concat([val, test], ignore_index=True))
    save("03_test/prediction_errors.csv", errors)
    selected_errors = errors.loc[errors.Split.eq("test") & errors.ModelName.eq(selected)]
    save("03_test/largest_selected_errors.csv", selected_errors.nlargest(5, "AbsoluteError"))
    metrics = pd.concat([val_metrics, test_metrics], ignore_index=True)
    improvement = relative_improvement(metrics)
    save("03_test/improvement_vs_naive.csv", improvement)
    pooled = metrics.loc[metrics.Market.eq("ALL")].copy()
    pooled["Label"] = pooled.ModelName.map(LABELS)
    pooled["Selected"] = pooled.ModelName.eq(selected)
    save("04_comparison/all_configurations.csv", pooled)
    comparison = []
    for split in ("validation", "test"):
        table = pooled.loc[pooled.Split.eq(split)].set_index("ModelName")
        for reference in ("naive_last", str(ref.ModelName)):
            comparison.append({"Split": split, "Selected": selected, "Reference": reference,
                **{f"{metric}_GainPct": float(100*(table.loc[reference, metric]-table.loc[selected, metric])/table.loc[reference, metric])
                   for metric in ("MAE", "RMSE")}, "N": int(table.loc[selected, "N"])})
    comparison = pd.DataFrame(comparison)
    save("04_comparison/selected_vs_references.csv", comparison)
    future, final_parameters, exports, states = export_final_states(monthly, selected, output)
    save("05_models/all_next_month.csv", future)
    save("05_models/selected_next_month.csv", future.loc[future.Selected])
    save("05_models/learned_parameters.csv", final_parameters)
    save("05_models/model_index.csv", exports)
    write_json(output/"05_models/selected_bundle.json", {"model_version": MODEL_VERSION,
        "source_sha256": source_info["sha256"], "selection_sha256": decision_sha,
        "configuration": asdict(BY_KEY[selected]), "markets": [x for x in states if x["selected"]]})
    event("models_saved", "12 pipeline Ridge và 28 trạng thái; dự báo 01/2014 không có actual")
    study = {"source": source_info, "monthly": monthly, "features": features, "checks": checks,
        "specs": specifications(), "protocol": protocol, "selected": selected, "decision": decision,
        "leaderboard": board, "validation": val, "validation_metrics": val_metrics, "validation_origins": val_origins,
        "validation_parameters": val_fit, "per_month": per_month, "stability": stability,
        "test": test, "test_metrics": test_metrics, "errors": errors, "pooled": pooled,
        "improvement": improvement, "comparison": comparison, "future": future,
        "final_parameters": final_parameters, "exports": exports}
    from coffee_dw.tuning_report import presentation_summary, write_reports
    summary = presentation_summary(study)
    save("06_summary/presentation_summary.csv", summary)
    if render:
        from coffee_dw.tuning_plots import render_figures
        figures = render_figures(study, output)
    else:
        figures = []
    write_reports(study, output, figures, summary)
    event("reports_completed", "Đã lưu số liệu đầy đủ, phân tích và gợi ý thuyết trình")
    save("06_summary/execution_events.csv", pd.DataFrame(events))
    if sha(source) != source_info["sha256"]:
        raise RuntimeError("Nguồn bị thay đổi trong khi chạy.")
    try:
        git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        git_head = None  # Source archives need not include Git metadata.
    files = sorted(p for p in output.rglob("*") if p.is_file() and p.name != "manifest.json")
    manifest = {"created_at_utc": utc(), "source": source_info, "source_sha256_after": sha(source),
        "selected_configuration": selected, "selection_sha256": decision_sha, "selection_before_test": True,
        "test_previously_seen": True, "validation_predictions": len(val), "test_predictions": len(test),
        "future_predictions": len(future), "ridge_fits_validation": len(val_fit)//3,
        "ridge_fits_test": len(test_fit)//3, "ridge_fits_final": len(final_parameters)//3,
        "candidate_count": len(CANDIDATES), "csv_count": sum(p.suffix == ".csv" for p in files),
        "figure_count": len(figures), "figures": figures, "python": platform.python_version(),
        "packages": {p: importlib.metadata.version(p) for p in ["numpy", "pandas", "scikit-learn", "joblib", *(["matplotlib"] if render else [])]},
        "code_sha256": {name: sha(Path(__file__).with_name(name)) for name in ["source.py", "forecast.py", "baseline_study.py", "tuning_study.py", "tuning_report.py", "tuning_plots.py"]},
        "git_head": git_head, "working_tree": "Local uncommitted changes; no push performed",
        "limitations": ["Exploratory after previously seen test; not fresh blind evaluation.",
                        "Only 24 historical months; 3 test months per Market.", "Seven declared configurations, not exhaustive over possible models.",
                        "Source-first; warehouse reconciliation pending.", "No future actual and no calibrated prediction interval."],
        "files": [{"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)} for p in files]}
    write_json(output/"manifest.json", manifest)
    return manifest
