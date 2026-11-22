"""Source-first baseline study with an explicit validation -> decision -> test gate.

The study reproduces a previously known reference protocol. It is not a fresh
blind test and does not tune hyperparameters, alter the warehouse, or publish
new results to the demo application.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import time

import numpy as np
import pandas as pd

from coffee_dw.config import ROOT, SOURCE_PATH
from coffee_dw.forecast import METHODS, MODEL_VERSION, _metric_rows, fit_ridge_model, monthly_sales, predict_next
from coffee_dw.source import read_source

LABELS={"naive_last":"Tháng trước", "moving_average_3":"Trung bình 3 tháng", "ridge":"Ridge · alpha = 1"}
COLORS={"naive_last":"#7D8FA4", "moving_average_3":"#207F83", "ridge":"#AB5366"}
MARKETS=("Central","East","South","West")
INITIAL_END=pd.Timestamp("2013-03-01")
VALIDATION_MONTHS=pd.date_range("2013-04-01","2013-09-01",freq="MS")
TEST_MONTHS=pd.date_range("2013-10-01","2013-12-01",freq="MS")


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, content):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(content,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    temporary.replace(path)


def write_table(output,relative,table):
    path=Path(output)/relative;path.parent.mkdir(parents=True,exist_ok=True)
    table.to_csv(path,index=False,encoding="utf-8-sig",date_format="%Y-%m-%d")


def validate_monthly(monthly):
    if monthly.duplicated(["Market","MonthStart"]).any():
        raise ValueError("Trùng grain Market–tháng; không chạy dự báo.")
    expected=pd.date_range("2012-01-01","2013-12-01",freq="MS")
    if sorted(monthly.Market.unique())!=list(MARKETS):
        raise ValueError("Protocol này cần đúng bốn Market của Coffee.")
    for market,part in monthly.groupby("Market"):
        if not pd.DatetimeIndex(part.MonthStart.sort_values()).equals(expected):
            raise ValueError(f"{market}: cần đủ 24 tháng 01/2012–12/2013; không tự điền kỳ thiếu.")
        if not np.isfinite(part.Sales).all():
            raise ValueError(f"{market}: Sales không hữu hạn.")


def prepare_inputs(source):
    detail,rejected=read_source(source)
    if not rejected.empty:
        raise ValueError(f"Có {len(rejected)} dòng reject; cần rà soát nguồn trước khi chạy nghiên cứu cơ sở.")
    monthly=monthly_sales(detail)
    validate_monthly(monthly)
    monthly["Split"]=np.select([monthly.MonthStart.le(INITIAL_END),monthly.MonthStart.isin(VALIDATION_MONTHS)],
                              ["initial_history","validation"],default="test")
    features=monthly.rename(columns={"Sales":"TargetSales"}).copy()
    for lag in (1,2,3):
        features[f"Lag{lag}"]=features.groupby("Market").TargetSales.shift(lag)
        features[f"Lag{lag}Month"]=features.MonthStart-pd.DateOffset(months=lag)
    features["CompleteLag123"]=features[["TargetSales","Lag1","Lag2","Lag3"]].notna().all(axis=1)
    checks=pd.DataFrame([
        {"Check":"Nguồn hợp lệ","Observed":len(detail),"Status":"PASS","Note":"Đã qua source.read_source; 0 reject"},
        {"Check":"Ô Market–tháng duy nhất","Observed":len(monthly),"Status":"PASS","Note":"96 = 4 Market × 24 tháng liên tục"},
        {"Check":"Sales được bảo toàn khi tổng hợp","Observed":float(monthly.Sales.sum()),"Status":"PASS" if abs(monthly.Sales.sum()-detail.Sales.sum())<1e-6 else "FAIL","Note":"Đối soát nguồn với bảng tổng hợp, chưa phải kho của Chi"},
        {"Check":"Mẫu ban đầu đủ lag123","Observed":int((features.CompleteLag123 & features.Split.eq('initial_history')).sum()),"Status":"PASS","Note":"12 mẫu/Market; chưa phải 4.248 mẫu học độc lập"},
    ])
    specs=pd.DataFrame([
        {"ModelName":"naive_last","Label":LABELS['naive_last'],"Features":"lag1","Parameters":"last observation","LearnsCoefficients":False,"Purpose":"Mốc đối chứng quản lý dễ hiểu"},
        {"ModelName":"moving_average_3","Label":LABELS['moving_average_3'],"Features":"lag1, lag2, lag3","Parameters":"window=3","LearnsCoefficients":False,"Purpose":"Kiểm tra làm trơn dao động"},
        {"ModelName":"ridge","Label":LABELS['ridge'],"Features":"lag1, lag2, lag3","Parameters":"StandardScaler + Ridge(alpha=1)","LearnsCoefficients":True,"Purpose":"Đối chứng hồi quy với tham số cố định"},
    ])
    source_info={"path":str(Path(source).resolve()),"sha256":sha(source),"accepted_rows":len(detail),"rejected_rows":len(rejected),
                 "monthly_cells":len(monthly),"months_per_market":24,"sales":float(detail.Sales.sum()),
                 "budget_sales":float(detail.BudgetSales.sum()),"profit":float(detail.Profit.sum()),"input":"CSV_source_not_warehouse"}
    return monthly,features,checks,specs,source_info


def score(predictions):
    result=_metric_rows(predictions)
    extra=[]
    for market,scope in [("ALL",predictions),*list(predictions.groupby("Market",sort=True))]:
        for (method,split),part in scope.groupby(["ModelName","Split"],sort=True):
            extra.append({"Market":market,"ModelName":method,"Split":split,
                          "Bias":float((part.Prediction-part.Actual).mean()),"MAPE_N":int(part.Actual.ne(0).sum())})
    return result.merge(pd.DataFrame(extra),on=["Market","ModelName","Split"],validate="one_to_one")


def evaluate_phase(monthly,split):
    if split not in ("validation","test"):
        raise ValueError("Pha đánh giá phải là validation hoặc test.")
    targets=VALIDATION_MONTHS if split=="validation" else TEST_MONTHS
    predictions,origins,fit_audit=[],[],[]
    for market,part in monthly.groupby("Market",sort=True):
        series=part.set_index("MonthStart").Sales.sort_index()
        for target in targets:
            history=series.loc[series.index<target]
            for method in METHODS:
                started=time.perf_counter()
                prediction=predict_next(history,method)
                elapsed=time.perf_counter()-started
                common={"Market":market,"ForecastMonth":target,"IssueMonth":history.index[-1],"TrainEnd":history.index[-1],
                        "ModelName":method,"ModelVersion":MODEL_VERSION,"Split":split}
                predictions.append(common|{"Prediction":prediction,"Actual":float(series.loc[target])})
                origins.append(common|{"HistoryStart":history.index[0],"HistoryN":len(history),
                                       "EffectiveFitN":len(history)-3 if method=="ridge" else None,
                                       "Lag1":float(history.iloc[-1]),"Lag2":float(history.iloc[-2]),"Lag3":float(history.iloc[-3]),
                                       "FitPredictSeconds":elapsed,"RuntimeNote":"Local diagnostic; not a benchmark"})
                if method=="ridge":
                    model=fit_ridge_model(history)
                    scaler,ridge=model.steps[0][1],model.steps[1][1]
                    for index in range(3):
                        fit_audit.append(common|{"Feature":f"lag{index+1}","FitN":int(scaler.n_samples_seen_),
                                                 "MeanTrain":float(scaler.mean_[index]),"ScaleTrain":float(scaler.scale_[index]),
                                                 "CoefficientScaled":float(ridge.coef_[index]),
                                                 "CoefficientRaw":float(ridge.coef_[index]/scaler.scale_[index]),
                                                 "InterceptScaled":float(ridge.intercept_),"Alpha":1.0})
    predictions=pd.DataFrame(predictions)
    return predictions,score(predictions),pd.DataFrame(origins),pd.DataFrame(fit_audit)


def choose_method(validation_metrics):
    if set(validation_metrics.Split)!={"validation"}:
        raise ValueError("Chỉ được chọn bằng validation; không đưa test vào lựa chọn.")
    leaderboard=validation_metrics.loc[validation_metrics.Market.eq("ALL")].copy()
    if set(leaderboard.ModelName)!=set(METHODS):
        raise ValueError("Leaderboard cần đủ ba phương pháp đối chứng.")
    leaderboard["TieOrder"]=leaderboard.ModelName.map({name:i for i,name in enumerate(METHODS)})
    leaderboard=leaderboard.sort_values(["MAE","TieOrder"]).reset_index(drop=True)
    leaderboard["Rank"]=range(1,len(leaderboard)+1)
    selected=str(leaderboard.iloc[0].ModelName)
    leaderboard["Selected"]=leaderboard.ModelName.eq(selected)
    return selected,leaderboard


def error_table(predictions):
    result=predictions.copy()
    result["Error"]=result.Prediction-result.Actual
    result["AbsoluteError"]=result.Error.abs()
    result["SquaredError"]=result.Error**2
    result["APE"]=result.AbsoluteError.div(result.Actual.abs().where(result.Actual.ne(0)))*100
    return result


def relative_improvement(metrics):
    rows=[]
    for split,scope in metrics.loc[metrics.Market.eq("ALL")].groupby("Split"):
        base=scope.loc[scope.ModelName.eq("naive_last")].iloc[0]
        for row in scope.itertuples():
            rows.append({"Split":split,"ModelName":row.ModelName,
                         **{f"{metric}_ImprovementPct":100*(float(base[metric])-getattr(row,metric))/float(base[metric]) if base[metric] else np.nan for metric in ("MAE","RMSE")}})
    return pd.DataFrame(rows)


def forecast_future(monthly,selected):
    rows,states=[],[]
    for market,part in monthly.groupby("Market",sort=True):
        history=part.set_index("MonthStart").Sales.sort_index()
        target=history.index[-1]+pd.offsets.MonthBegin(1)
        rows.append({"Market":market,"ForecastMonth":target,"IssueMonth":history.index[-1],"TrainEnd":history.index[-1],
                     "HistoryN":len(history),"ModelName":selected,"ModelVersion":MODEL_VERSION,
                     "Prediction":predict_next(history,selected),"LastActual":float(history.iloc[-1]),"Actual":np.nan,"Split":"future"})
        state={"Market":market,"observations_for_rule":[{"month":date.strftime("%Y-%m-%d"),"sales":float(value)} for date,value in history.tail(3).items()]}
        if selected=="ridge":
            model=fit_ridge_model(history);scaler,ridge=model.steps[0][1],model.steps[1][1]
            state.update(scaler_mean=scaler.mean_.tolist(),scaler_scale=scaler.scale_.tolist(),coefficients=ridge.coef_.tolist(),intercept=float(ridge.intercept_))
        states.append(state)
    return pd.DataFrame(rows),{"selected_method":selected,"parameters":"window=3" if selected=="moving_average_3" else "last observation" if selected=="naive_last" else "lag123; alpha=1",
                               "model_version":MODEL_VERSION,"format":"readable_json_state_not_pth","markets":states}


def run_study(source=SOURCE_PATH,output=ROOT/"experiments"/"baseline"/"results",*,render=True):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    events=[]
    def event(stage,note):
        events.append({"Sequence":len(events)+1,"TimestampUTC":utc(),"Stage":stage,"Note":note})
    def save(relative,table):
        write_table(output,relative,table)
    event("input","Bắt đầu; không đọc/ghi kho hoặc output dashboard")
    monthly,features,checks,specs,source_info=prepare_inputs(source)
    save("01_input/monthly_market.csv",monthly);save("01_input/input_checks.csv",checks)
    save("01_input/source_profile.csv",pd.DataFrame([source_info]))
    save("02_protocol/model_specifications.csv",specs)
    save("02_protocol/split_manifest.csv",monthly[["Market","MonthStart","Split"]])
    save("02_protocol/feature_availability.csv",features)
    save("02_protocol/supervised_complete.csv",features.loc[features.CompleteLag123])
    save("02_protocol/first_origin_training.csv",features.loc[features.CompleteLag123 & features.Split.eq("initial_history")])
    definitions=pd.DataFrame([
        {"Metric":"MAE","Meaning":"Trung bình trị tuyệt đối sai số","Direction":"lower","SelectionMetric":True},
        {"Metric":"RMSE","Meaning":"Nhạy với các lần lệch lớn","Direction":"lower","SelectionMetric":False},
        {"Metric":"MAPE","Meaning":"Trung bình % sai số; chỉ actual khác 0","Direction":"lower","SelectionMetric":False},
        {"Metric":"Bias","Meaning":"Prediction − Actual; dương là dự báo cao","Direction":"near_zero","SelectionMetric":False},
    ])
    save("02_protocol/metric_dictionary.csv",definitions)
    protocol={"created_at_utc":utc(),"target":"Sales per Market next month","source_sha256":source_info["sha256"],
              "initial_history":"2012-01 to 2013-03 (15 months)","validation":"2013-04 to 2013-09 (6 months)",
              "test":"2013-10 to 2013-12 (3 months)","methods":list(METHODS),"model_version":MODEL_VERSION,
              "selection":"Minimum pooled validation MAE; ties follow METHODS order", "rolling_origin":"expanding history; one step ahead",
              "previous_test_actual_allowed":"Only after its month ends, at the next forecast origin",
              "study_type":"reproduction_of_previously_known_reference","test_results_previously_known":True,"hyperparameter_search":False}
    write_json(output/"02_protocol/protocol.json",protocol)
    event("validation_started","Chỉ tạo dự báo validation; chưa tính test trong lượt chạy này")
    val,val_metrics,val_origins,val_fit=evaluate_phase(monthly,"validation")
    save("03_validation/predictions.csv",val);save("03_validation/metrics.csv",val_metrics)
    save("03_validation/origin_schedule.csv",val_origins);save("03_validation/ridge_fit_audit.csv",val_fit)
    save("02_protocol/first_origin_scaler.csv",val_fit.loc[val_fit.ForecastMonth.eq(VALIDATION_MONTHS[0])])
    selected,leaderboard=choose_method(val_metrics)
    save("03_validation/leaderboard.csv",leaderboard)
    decision={"created_at_utc":utc(),"selected_method":selected,"selected_label":LABELS[selected],
              "parameters":specs.loc[specs.ModelName.eq(selected),"Parameters"].iloc[0],
              "validation_MAE":float(leaderboard.iloc[0].MAE),"validation_N":int(leaderboard.iloc[0].N),
              "criterion":"Minimum pooled validation MAE","test_used_for_this_selection":False,
              "previously_known_reference_test":True,"validation_predictions_sha256":sha(output/"03_validation/predictions.csv"),
              "source_sha256":source_info["sha256"]}
    write_json(output/"03_validation/selection.json",decision)
    decision_hash=sha(output/"03_validation/selection.json")
    event("selection_saved",f"Đã ghi selection.json và checksum {decision_hash} trước khi gọi pha test")
    event("test_started","Đọc lựa chọn đã lưu; không thay tham số/phương pháp theo test")
    test,test_metrics,test_origins,test_fit=evaluate_phase(monthly,"test")
    if sha(output/"03_validation/selection.json")!=decision_hash:
        raise RuntimeError("Selection record bị thay đổi trong khi chạy test.")
    save("04_test/predictions.csv",test);save("04_test/metrics.csv",test_metrics)
    save("04_test/origin_schedule.csv",test_origins);save("04_test/ridge_fit_audit.csv",test_fit)
    save("04_test/selected_metrics.csv",test_metrics.loc[test_metrics.ModelName.eq(selected)])
    errors=error_table(pd.concat([val,test],ignore_index=True))
    selected_errors=errors.loc[errors.Split.eq("test") & errors.ModelName.eq(selected)]
    save("04_test/prediction_errors.csv",errors)
    save("04_test/largest_selected_errors.csv",selected_errors.sort_values("AbsoluteError",ascending=False).head(5))
    metrics=pd.concat([val_metrics,test_metrics],ignore_index=True)
    improvement=relative_improvement(metrics)
    save("04_test/improvement_vs_naive.csv",improvement)
    save("04_test/all_method_summary.csv",metrics.loc[metrics.Market.eq("ALL")])
    future,state=forecast_future(monthly,selected)
    save("05_future/next_month.csv",future)
    state["source_sha256"]=source_info["sha256"]
    write_json(output/"05_future/selected_state.json",state)
    event("test_and_future_completed","Kỳ 01/2014 không có actual; không chấm điểm")
    study={"source":source_info,"monthly":monthly,"features":features,"checks":checks,"specs":specs,"protocol":protocol,
           "validation":val,"validation_metrics":val_metrics,"leaderboard":leaderboard,"decision":decision,"selected":selected,
           "test":test,"test_metrics":test_metrics,"errors":errors,"improvement":improvement,"future":future}
    from coffee_dw.baseline_report import presentation_summary, write_reports
    presentation=presentation_summary(study)
    save("06_summary/presentation_summary.csv",presentation)
    if render:
        from coffee_dw.baseline_plots import render_figures
        figures=render_figures(study,output)
    else:
        figures=[]
    write_reports(study,output,figures,presentation)
    event("reports_completed","Đã xuất bảng/nhận xét; hình nếu bật render")
    save("06_summary/execution_events.csv",pd.DataFrame(events))
    checksum_after=sha(source)
    if checksum_after!=source_info["sha256"]:
        raise RuntimeError("Nguồn bị thay đổi trong khi chạy nghiên cứu.")
    try:
        git_head=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    except (OSError,subprocess.CalledProcessError):
        git_head=None
    artifacts=sorted(p for p in output.rglob("*") if p.is_file() and p.name!="manifest.json")
    manifest={"created_at_utc":utc(),"source":source_info,"source_sha256_after":checksum_after,
              "selected_method":selected,"selection_record_sha256":decision_hash,"selection_before_test":True,
              "validation_predictions":len(val),"test_predictions":len(test),"future_predictions":len(future),
              "csv_count":sum(p.suffix==".csv" for p in artifacts),"figure_count":len(figures),"figures":figures,
              "python":platform.python_version(),"packages":{p:importlib.metadata.version(p) for p in ["numpy","pandas","scikit-learn",*(["matplotlib"] if render else [])]},
              "code_sha256":{name:sha(Path(__file__).with_name(name)) for name in ["source.py","forecast.py","baseline_study.py","baseline_plots.py","baseline_report.py"]},
              "git_head":git_head,"working_tree":"Includes local changes; no commit or push performed",
              "limitations":["Reference test previously known; not a new blind experiment.","Only 3 test months per Market.",
                             "CSV source study; warehouse handoff/native evidence pending.","No hyperparameter search; future actual unknown."],
              "files":[{"path":p.relative_to(output).as_posix(),"bytes":p.stat().st_size,"sha256":sha(p)} for p in artifacts]}
    write_json(output/"manifest.json",manifest)
    return manifest
