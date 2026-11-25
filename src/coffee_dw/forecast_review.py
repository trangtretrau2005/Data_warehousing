"""Small exploratory extension: seasonal naive12 and fixed-alpha SES.

No synthetic observations, retuned serving model, or unseen-test claim. The
seven existing tuning candidates are reproduced on the same calendar targets.
"""

from __future__ import annotations

from dataclasses import asdict
import importlib.metadata
from pathlib import Path
import platform
import subprocess

import numpy as np
import pandas as pd

from coffee_dw.baseline_study import (
    MARKETS, TEST_MONTHS, VALIDATION_MONTHS, prepare_inputs, score, sha, utc,
    validate_monthly, write_json, write_table,
)
from coffee_dw.config import ROOT, SOURCE_PATH
from coffee_dw import tuning_study as baseline

MODEL_VERSION = "review-v1-seasonal12-ses-a0p2-0p5-0p8"
NEW_CONFIGS = (
    {"key": "seasonal_naive_12", "family": "SeasonalNaive", "label": "Cùng tháng năm trước", "alpha": None, "season_length": 12},
    {"key": "ses_a0p2", "family": "SES", "label": "SES · α = 0,2", "alpha": .2, "season_length": None},
    {"key": "ses_a0p5", "family": "SES", "label": "SES · α = 0,5", "alpha": .5, "season_length": None},
    {"key": "ses_a0p8", "family": "SES", "label": "SES · α = 0,8", "alpha": .8, "season_length": None},
)
EXTENSIONS = {c["key"]: c for c in NEW_CONFIGS}
KEYS = tuple(baseline.BY_KEY) + tuple(EXTENSIONS)
LABELS = baseline.LABELS | {c["key"]: c["label"] for c in NEW_CONFIGS}


def history_values(history):
    values = np.asarray(history, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError("Lịch sử phải là chuỗi một chiều không rỗng, mọi Sales hữu hạn.")
    return values


def ses_level(history, alpha):
    """Initialize at y0, then update through each available observation once."""
    values = history_values(history)
    if not np.isfinite(alpha) or not 0 < alpha <= 1:
        raise ValueError("SES alpha phải hữu hạn và thuộc (0, 1].")
    level = float(values[0])
    for observed in values[1:]:
        level = alpha * float(observed) + (1 - alpha) * level
    return float(level)


def predict_extension(history, key):
    values = history_values(history)
    if key not in EXTENSIONS:
        raise ValueError("Cấu hình không thuộc bốn mở rộng đã khai báo.")
    candidate = EXTENSIONS[key]
    if candidate["family"] == "SeasonalNaive":
        if len(values) < 12:
            raise ValueError("Seasonal naive12 cần ít nhất 12 tháng liên tục.")
        return float(values[-12])
    return ses_level(values, candidate["alpha"])


def specifications():
    rows = []
    for order, candidate in enumerate(baseline.CANDIDATES):
        rows.append({"ModelName": candidate.key, "Label": candidate.label, "Family": candidate.family,
                     "Alpha": candidate.alpha, "Window": candidate.window, "SeasonLength": None,
                     "NewInThisReview": False, "TieOrder": order,
                     "Parameters": str(asdict(candidate)), "Initialization": "existing tuning implementation"})
    for candidate in NEW_CONFIGS:
        rows.append({"ModelName": candidate["key"], "Label": candidate["label"], "Family": candidate["family"],
                     "Alpha": candidate["alpha"], "Window": None, "SeasonLength": candidate["season_length"],
                     "NewInThisReview": True, "TieOrder": len(rows),
                     "Parameters": "y[t-12]" if candidate["family"] == "SeasonalNaive" else f"level=alpha*y+(1-alpha)*previous; alpha={candidate['alpha']}",
                     "Initialization": "12 observed months" if candidate["family"] == "SeasonalNaive" else "first observed value; no optimized initial level"})
    return pd.DataFrame(rows)


def evaluate_phase(monthly, split):
    if split not in {"validation", "test"}:
        raise ValueError("Pha phải là validation hoặc test.")
    validate_monthly(monthly)
    existing, _, existing_origins, ridge_parameters = baseline.evaluate_phase(monthly, split)
    existing["ModelVersion"] = MODEL_VERSION
    existing_origins["ModelVersion"] = MODEL_VERSION
    ridge_parameters["ModelVersion"] = MODEL_VERSION
    targets = VALIDATION_MONTHS if split == "validation" else TEST_MONTHS
    new_predictions, origins = [], []
    for market, part in monthly.groupby("Market", sort=True):
        series = part.set_index("MonthStart").Sales.sort_index()
        for target in targets:
            history = series.loc[series.index < target]
            for candidate in NEW_CONFIGS:
                prediction = predict_extension(history, candidate["key"])
                common = {"Market": market, "ForecastMonth": target, "IssueMonth": history.index[-1],
                          "TrainEnd": history.index[-1], "ModelName": candidate["key"], "ModelVersion": MODEL_VERSION, "Split": split}
                new_predictions.append(common | {"Prediction": prediction, "Actual": float(series.loc[target])})
                origins.append(common | {"Family": candidate["family"], "Alpha": candidate["alpha"],
                                          "HistoryStart": history.index[0], "HistoryN": len(history), "FitN": 0,
                                          "StateObservationN": len(history) if candidate["family"] == "SES" else 1,
                                          "InitialLevel": float(history.iloc[0]) if candidate["family"] == "SES" else np.nan,
                                          "FinalLevel": prediction if candidate["family"] == "SES" else np.nan,
                                          "SeasonalSourceMonth": history.index[-12] if candidate["family"] == "SeasonalNaive" else pd.NaT,
                                          "Lag1": float(history.iloc[-1]), "Lag2": float(history.iloc[-2]), "Lag3": float(history.iloc[-3])})
    predictions = pd.concat([existing, pd.DataFrame(new_predictions)], ignore_index=True)
    return predictions, score(predictions), pd.concat([existing_origins, pd.DataFrame(origins)], ignore_index=True), ridge_parameters


def choose_configuration(metrics):
    if set(metrics.Split) != {"validation"}:
        raise ValueError("Chỉ chọn bằng validation, không dùng test.")
    board = metrics.loc[metrics.Market.eq("ALL")].copy()
    if len(board) != len(KEYS) or set(board.ModelName) != set(KEYS):
        raise ValueError("Cần đủ 11 cấu hình, mỗi cấu hình đúng một dòng ALL.")
    if not board.N.eq(24).all() or not np.isfinite(board.MAE).all():
        raise ValueError("Mỗi cấu hình phải có cùng 24 sai số validation hữu hạn.")
    board["TieOrder"] = board.ModelName.map({key: i for i, key in enumerate(KEYS)})
    board = board.sort_values(["MAE", "TieOrder"]).reset_index(drop=True)
    board["Rank"] = range(1, len(board) + 1)
    selected = str(board.iloc[0].ModelName)
    board["Selected"] = board.ModelName.eq(selected)
    board["Label"] = board.ModelName.map(LABELS)
    return selected, board


def future_predictions(monthly, selected):
    rows = []
    for market, part in monthly.groupby("Market", sort=True):
        history = part.set_index("MonthStart").Sales.sort_index()
        for key in KEYS:
            if key in EXTENSIONS:
                value = predict_extension(history, key)
            else:
                candidate = baseline.BY_KEY[key]
                value = baseline.predict_fitted(history, candidate, baseline.fit_candidate(history, candidate))
            rows.append({"Market": market, "ForecastMonth": pd.Timestamp("2014-01-01"),
                         "IssueMonth": history.index[-1], "TrainEnd": history.index[-1],
                         "ModelName": key, "ModelVersion": MODEL_VERSION, "Prediction": value,
                         "Actual": np.nan, "Split": "future_exploratory", "Selected": key == selected})
    return pd.DataFrame(rows)


def sensitivity(predictions):
    rows = []
    for omitted in VALIDATION_MONTHS:
        retained = predictions.loc[predictions.ForecastMonth.ne(omitted)]
        board = score(retained).loc[lambda x: x.Market.eq("ALL")].copy()
        board["TieOrder"] = board.ModelName.map({key: i for i, key in enumerate(KEYS)})
        winner = board.sort_values(["MAE", "TieOrder"]).iloc[0]
        rows.append({"OmittedValidationMonth": omitted, "Winner": winner.ModelName, "MAE": float(winner.MAE),
                     "N": int(winner.N), "Purpose": "descriptive sensitivity only; do not change selection or refit"})
    return pd.DataFrame(rows)


def comparison_against_ma3(metrics):
    references = metrics.loc[metrics.ModelName.eq("ma_w3"), ["Market", "Split", "MAE", "RMSE"]].rename(columns={"MAE": "MA3_MAE", "RMSE": "MA3_RMSE"})
    result = metrics.merge(references, on=["Market", "Split"], validate="many_to_one")
    for metric in ("MAE", "RMSE"):
        result[f"Delta{metric}VsMA3"] = result[metric] - result[f"MA3_{metric}"]
        result[f"{metric}ImprovementVsMA3Pct"] = (result[f"MA3_{metric}"] - result[metric]) / result[f"MA3_{metric}"].where(result[f"MA3_{metric}"].ne(0)) * 100
    return result


def run_review(source=SOURCE_PATH, output=ROOT / "experiments/forecast_review/results"):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    events = []
    def event(stage, note):
        events.append({"Sequence": len(events) + 1, "TimestampUTC": utc(), "Stage": stage, "Note": note})
        write_table(output, "execution_events.csv", pd.DataFrame(events))
    protocol = {"model_version": MODEL_VERSION, "created_utc": utc(), "source_sha256": sha(source),
                "markets": list(MARKETS), "initial_history": ["2012-01-01", "2013-03-01"],
                "validation": ["2013-04-01", "2013-09-01"], "test": ["2013-10-01", "2013-12-01"],
                "candidates": list(KEYS), "new_candidates": list(NEW_CONFIGS), "existing_candidates": [asdict(c) for c in baseline.CANDIDATES],
                "selection": "minimum pooled validation MAE over 4 Markets x 6 targets; tie by candidate order",
                "ses_rule": "level starts at first observed Sales; level <- alpha*Sales+(1-alpha)*level for remaining past observations",
                "seasonal_rule": "one-step prediction y[t-12], not y[t-11]",
                "test_previously_seen": True, "exploratory_not_blind": True,
                "synthetic_observations": 0, "writes_serving_or_warehouse": False,
                "serving_model_unchanged": "moving_average_3, original main protocol"}
    # Persist the fixed grid and selection rule before any candidate is scored.
    write_json(output / "protocol.json", protocol)
    protocol_sha = sha(output / "protocol.json")
    write_table(output, "configurations.csv", specifications())
    event("protocol_saved", "Fixed four new configurations plus seven existing; no scores inspected in this run")
    monthly, _, checks, _, source_info = prepare_inputs(source)
    write_table(output, "source_profile.csv", pd.DataFrame([source_info]))
    write_table(output, "input_checks.csv", checks)
    write_table(output, "monthly_market.csv", monthly)
    validation, val_metrics, val_origins, val_parameters = evaluate_phase(monthly, "validation")
    selected, board = choose_configuration(val_metrics)
    write_table(output, "validation_predictions.csv", validation)
    write_table(output, "validation_metrics.csv", val_metrics)
    write_table(output, "validation_leaderboard.csv", board)
    decision = {"created_utc": utc(), "selected_configuration": selected, "criterion": "pooled validation MAE",
                "protocol_sha256": protocol_sha, "validation_predictions_per_candidate": 24,
                "test_used_for_selection": False, "test_previously_seen": True,
                "changes_serving_model": False, "exploratory_not_blind": True}
    write_json(output / "selection.json", decision)
    selection_sha = sha(output / "selection.json")
    event("selection_saved", selected)
    event("test_started", "Selection already persisted; previously seen test is descriptive only")
    test, test_metrics, test_origins, test_parameters = evaluate_phase(monthly, "test")
    write_table(output, "test_predictions.csv", test)
    write_table(output, "test_metrics.csv", test_metrics)
    predictions = pd.concat([validation, test], ignore_index=True)
    predictions["Error"] = predictions.Prediction - predictions.Actual
    predictions["AbsoluteError"] = predictions.Error.abs()
    predictions["Selected"] = predictions.ModelName.eq(selected)
    all_metrics = pd.concat([val_metrics, test_metrics], ignore_index=True)
    write_table(output, "all_predictions.csv", predictions)
    write_table(output, "all_metrics.csv", all_metrics)
    write_table(output, "origins.csv", pd.concat([val_origins, test_origins], ignore_index=True))
    write_table(output, "baseline_ridge_parameters.csv", pd.concat([val_parameters, test_parameters], ignore_index=True))
    comparison = comparison_against_ma3(all_metrics)
    write_table(output, "improvement_vs_ma3.csv", comparison)
    stability = sensitivity(validation)
    write_table(output, "validation_sensitivity.csv", stability)
    future = future_predictions(monthly, selected)
    write_table(output, "future.csv", future)
    selected_rows = comparison.loc[comparison.Market.eq("ALL") & comparison.ModelName.eq(selected)]
    new_board = board.loc[board.ModelName.isin(EXTENSIONS)]
    best_extension = new_board.iloc[0]
    summary = {"model_version": MODEL_VERSION, "status": "exploratory_completed", "selected_configuration": selected,
               "best_new_configuration": str(best_extension.ModelName), "best_new_validation_mae": float(best_extension.MAE),
               "candidate_count": len(KEYS), "new_candidate_count": len(NEW_CONFIGS),
               "validation_predictions": len(validation), "test_predictions": len(test), "future_predictions": len(future),
               "selected_future_predictions": int(future.Selected.sum()), "synthetic_observations": 0,
               "selected_metrics": selected_rows[["Split", "N", "MAE", "RMSE", "MAPE", "Bias", "MAEImprovementVsMA3Pct", "RMSEImprovementVsMA3Pct"]].astype(object).where(pd.notna(selected_rows), None).to_dict("records"),
               "serving_model_unchanged": "moving_average_3", "test_previously_seen": True, "independent_blind_test": False,
               "source_sha256_before": protocol["source_sha256"], "source_sha256_after": sha(source),
               "selection_sha256": selection_sha, "protocol_sha256": protocol_sha,
               "sensitivity_winners": {str(k): int(v) for k, v in stability.Winner.value_counts().items()},
               "limits": ["Test and prior validation scores were already known; this is a declared exploratory extension, not fresh confirmation.",
                          "Only 24 months per Market, six validation and three test targets per Market; no independent evidence of stable yearly seasonality.",
                          "No synthetic source, new history, causal drivers or calibrated prediction interval.",
                          "No warehouse/demo publication or replacement of original MA3 selection."]}
    if sha(output / "protocol.json") != protocol_sha or sha(output / "selection.json") != selection_sha or sha(source) != protocol["source_sha256"]:
        raise RuntimeError("Protocol, selection hoặc nguồn đã đổi trong lần chạy.")
    write_json(output / "summary.json", summary)
    lines = "\n".join(f"| {r.Label} | {r.MAE:.2f} | {r.RMSE:.2f} | {'Có' if r.Selected else ''} |" for r in board.itertuples())
    added_comparison = comparison.loc[comparison.Market.eq("ALL") & comparison.ModelName.isin(EXTENSIONS)]
    new_lines = "\n".join(f"| {LABELS[r.ModelName]} | {r.Split} | {r.MAE:.2f} | {r.RMSE:.2f} | {r.MAEImprovementVsMA3Pct:+.2f}% |" for r in added_comparison.itertuples())
    selected_text = "\n".join(f"- {r.Split}: N={r.N}, MAE={r.MAE:.2f}, RMSE={r.RMSE:.2f}; MAE cải thiện so MA3={r.MAEImprovementVsMA3Pct:.2f}%." for r in selected_rows.itertuples())
    analysis = f"""# Đợt mở rộng dự báo có kiểm soát

Giữ nguyên dữ liệu thật Coffee.csv, bốn Market và lịch15/6/3. Không tạo thêm nguồn.
Trước khi chấm, protocol.json chốt hai family mới: seasonal naive12 và SES cố định alpha0.2/0.5/0.8.
Bảy cấu hình cũ được tính lại bằng đúng code tuning trên cùng target, không chỉ nạp số đã làm tròn.
Tổng11 cấu hình; chọn một cấu hình bằng pooled validation MAE trên24 dự báo/cấu hình.

| Cấu hình | MAE validation | RMSE validation | Chọn |
| --- | ---: | ---: | --- |
{lines}

Lựa chọn thăm dò: **{selected}**. Cấu hình mới tốt nhất là **{best_extension.ModelName}**,
MAE validation **{best_extension.MAE:.2f}**. Tệp selection.json đã lưu trước lời gọi pha test.

{selected_text}

## Bốn cấu hình mới so với MA3

| Cấu hình mới | Pha | MAE | RMSE | Cải thiện MAE so MA3 |
| --- | --- | ---: | ---: | ---: |
{new_lines}

Không có cấu hình mới nào vượt MA3 theo tiêu chí validation đã chốt. SES alpha0.5 là đối chứng mới gần nhất.
Một số cấu hình mới có MAE test thấp hơn MA3 nhưng **không được chọn lại theo test**.
Seasonal naive12 có sai số test lớn hơn nhiều; không mặc nhiên coi hai năm dữ liệu là bằng chứng nên dùng mùa vụ.

## Ý nghĩa và giới hạn

Mô hình phức tạp không được ưu tiên mặc định: tiêu chí là sai số trên cùng kỳ và cùng nhóm.
SES chỉ cập nhật một mức từ quan sát quá khứ; seasonal naive12 dùng đúng tháng cách12kỳ.
Không có epoch hoặc training loss cho các quy tắc này. Các alpha là cấu hình định trước,
không phải tham số tối ưu bằng test. Kiểm tra bỏ lần lượt từng tháng khỏi bảng chấm validation
chỉ mô tả độ nhạy, không fit lại, không dùng để đổi lựa chọn.

Test10–12/2013 đã được xem trong các vòng trước; cả đợt này là **thăm dò, không phải kiểm định mù mới**.
Một cải thiện ở đây chưa chứng minh tổng quát hóa hoặc hiệu quả vận hành. Dữ liệu chỉ24tháng/Market,
chỉ hai quan sát mỗi tháng trong năm; seasonal12 được thử như đối chứng, chưa đủ khẳng định mùa vụ ổn định.
Mỗi phương pháp chỉ có12 dự báo test gộp bốn Market, không coi là12 thử nghiệm độc lập.

Không sinh dữ liệu giả để làm đẹp metric hoặc tăng N. Muốn kết luận độc lập cần thêm quan sát thật ở kỳ chưa xem,
cùng định nghĩa Sales/grain, và khóa lựa chọn trước khi mở actual. Cần dữ liệu nghiệp vụ có thời điểm phát hành
rõ ràng nếu nghiên cứu biến giá/khuyến mãi/ngày lễ; không lấy số thực hiện tháng đích làm feature.

**MA3 phục vụ hiện tại giữ nguyên.** future.csv gồm44 dự báo01/2014 của11 cấu hình,
bốn dòng Selected là kết quả thăm dò; mọi actual tương lai để trống. Đây là mô phỏng lịch sử,
không phải dự báo tháng tới ở thời điểm hiện tại và không ghi ForecastSales/bundle demo.

## Truy vết

Nguồn trước/sau: `{protocol['source_sha256']}`. Protocol checksum và selection checksum nằm trong summary/manifest.
execution_events.csv chứng minh protocol_saved → selection_saved → test_started.
all_predictions.csv giữ396 dự báo đánh giá; all_metrics.csv có N, MAE/RMSE/MAPE và Bias theoMarket/ALL.
origins.csv giữ mốc dữ liệu được biết, trạng thái SES hoặc tháng nguồn seasonal; baseline_ridge_parameters.csv
giữ scaler/hệ số cho đối chứng Ridge. Code/phiên bản/hash output nằm trong manifest.json.
"""
    (output / "analysis.md").write_text(analysis, encoding="utf-8")
    event("completed", "Reports saved; serving unchanged; all future actuals missing")
    try:
        git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        git_head = None
    code = ["src/coffee_dw/forecast_review.py", "src/coffee_dw/tuning_study.py", "src/coffee_dw/baseline_study.py", "experiments/forecast_review/run.py", "tests/test_forecast_review.py"]
    files = sorted(p for p in output.rglob("*") if p.is_file() and p.name != "manifest.json")
    manifest = summary | {"created_utc": utc(), "source": source_info, "git_head": git_head,
                           "working_tree": "local changes; no commit or publication", "python": platform.python_version(),
                           "packages": {p: importlib.metadata.version(p) for p in ("numpy", "pandas", "scikit-learn")},
                           "code_sha256": {name: sha(ROOT / name) for name in code},
                           "files": [{"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)} for p in files]}
    write_json(output / "manifest.json", manifest)
    return summary
