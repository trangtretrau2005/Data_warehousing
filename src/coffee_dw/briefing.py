"""Verified adapter from the completed tuning study to the narrated demo.

The narration uses validation evidence known by September 2013. Test actuals
remain a separate retrospective reveal and never enter a forecast explanation.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd

from coffee_dw.baseline_study import sha
from coffee_dw.config import DB_PATH, ROOT
from coffee_dw.demo import build_demo_bundle, number_vi, speech_number, spoken_month
from coffee_dw.forecast import monthly_sales
from coffee_dw.warehouse import read_detail

TUNING_DIR = ROOT/"experiments"/"tuning"/"results"
CONFIG_TO_METHOD = {"naive_last":"naive_last", "ma_w3":"moving_average_3", "ridge_a1":"ridge"}
METHOD_TO_CONFIG = {v:k for k,v in CONFIG_TO_METHOD.items()}
REQUIRED_FILES = (
    "01_protocol/monthly_market.csv", "01_protocol/configurations.csv", "01_protocol/protocol.json",
    "02_validation/selection.json", "02_validation/leaderboard.csv", "02_validation/predictions.csv",
    "02_validation/metrics.csv", "03_test/predictions.csv", "03_test/metrics.csv",
    "05_models/selected_next_month.csv",
)


def read_research(directory=TUNING_DIR):
    directory=Path(directory)
    manifest=json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
    records={row["path"]:row for row in manifest["files"]}
    for relative in REQUIRED_FILES:
        if relative not in records or sha(directory/relative)!=records[relative]["sha256"]:
            raise ValueError(f"Kết quả nghiên cứu bị thiếu/đổi: {relative}. Chạy lại thí nghiệm tuning.")
    selection=json.loads((directory/"02_validation/selection.json").read_text(encoding="utf-8"))
    if selection["selected_configuration"] not in CONFIG_TO_METHOD:
        raise ValueError("Cấu hình được chọn cần adapter dự báo mới; không tự đổi sang một phương pháp khác.")
    board=pd.read_csv(directory/"02_validation/leaderboard.csv")
    selected=selection["selected_configuration"]
    if len(board)!=7 or board.iloc[0].ModelName!=selected or not np.isclose(board.iloc[0].MAE,selection["validation_MAE"]):
        raise ValueError("Bảng validation không khớp lựa chọn đã lưu.")
    validation=pd.read_csv(directory/"02_validation/predictions.csv")
    if not set(validation.Split)=={"validation"} or not validation.ForecastMonth.between("2013-04-01","2013-09-01").all():
        raise ValueError("Bằng chứng origin chỉ được chứa sáu kỳ validation.")
    return {"manifest":manifest,"selection":selection,"leaderboard":board,"validation":validation,
        "validation_metrics":pd.read_csv(directory/"02_validation/metrics.csv"),
        "test":pd.read_csv(directory/"03_test/predictions.csv"),
        "test_metrics":pd.read_csv(directory/"03_test/metrics.csv"),
        "future":pd.read_csv(directory/"05_models/selected_next_month.csv"),
        "monthly":pd.read_csv(directory/"01_protocol/monthly_market.csv",parse_dates=["MonthStart"]),
        "manifest_sha256":sha(directory/"manifest.json"),"directory":str(directory.resolve())}


def reconcile_monthly(warehouse_monthly, research_monthly):
    result=warehouse_monthly.merge(research_monthly[["Market","MonthStart","Sales"]],
        on=["Market","MonthStart"],how="outer",suffixes=("Warehouse","Research"),validate="one_to_one",indicator=True)
    result["Difference"]=result.SalesWarehouse-result.SalesResearch
    result["Pass"]=result["_merge"].eq("both") & result.Difference.abs().le(1e-8)
    if len(result)!=96 or not result.Pass.all():
        raise ValueError("96 ô Market–tháng trong kho chưa khớp nghiên cứu; dừng công bố lời thuyết minh.")
    return result.drop(columns="_merge")


def narrative(case, research):
    """Three bounded chapters; every spoken figure is available at the origin."""
    target,issue=spoken_month(case["forecast_month"]),spoken_month(case["issue_month"])
    market={"West":"miền Tây","East":"miền Đông","South":"miền Nam","Central":"miền Trung"}[case["market"]]
    change=case["prediction"]-case["last_actual"]
    direction="tăng" if change>=0 else "giảm"
    intro=(f"Chúng ta đang xem thị trường {market}, chuẩn bị cho {target}.\n\n"
        f"Tại thời điểm lập báo cáo, dữ liệu đã kết thúc {issue}. Doanh số tháng gần nhất là khoảng {speech_number(case['last_actual'])}.\n\n"
        f"Phương pháp đã chọn dự báo khoảng {speech_number(case['prediction'])}, {direction} khoảng {speech_number(abs(change))} so với tháng gần nhất. "
        "Bây giờ, chúng ta cùng xem ba tháng nào tạo nên con số này.")
    terms=case["story"]["inputs"]
    values=".\n\n".join(f"{spoken_month(row['month'])}, doanh số {speech_number(row['sales'])}" for row in terms)
    mechanism=("Ba cột trên hình là ba tháng đã xảy ra, mỗi tháng có trọng số bằng nhau.\n\n"+values+".\n\n"
        f"Cộng ba doanh số rồi chia cho ba, kết quả khoảng {speech_number(case['prediction'])}. "
        "Đường ngang là giá trị trung bình đó. Đây là căn cứ tính toán, chưa phải lý do kinh doanh khiến doanh số thay đổi.")
    quality=("Tiếp theo, kiểm tra phương pháp này qua các tháng đã biết.\n\n"
        f"Nhóm đã so sánh bảy cấu hình. Trung bình ba tháng được giữ lại vì có sai số trung bình thấp nhất trên tập lựa chọn gộp bốn thị trường.\n\n"
        f"Riêng thị trường này, sáu lần dự báo validation có sai số tuyệt đối trung bình khoảng {speech_number(case['validation_market']['MAE'])}. "
        "Biểu đồ đang đối chiếu dự báo với số thực tế của sáu tháng đó. Sai số lịch sử là thông tin tham khảo, chưa phải giới hạn sai số tháng tới.\n\n"
        +("Bạn có thể mở số thực tế của tháng đích để kiểm chứng thêm. Số này không tham gia tính dự báo."
          if case["actual"] is not None else "Tháng đích chưa có số thực tế trong nguồn. Khi có dữ liệu mới, cần đối chiếu lại."))
    return [{"id":"forecast","title":"Dự kiến tháng tới","text":intro},
            {"id":"explain","title":"Ba tháng tạo dự báo","text":mechanism},
            {"id":"quality","title":"Kiểm chứng bằng lịch sử","text":quality}]


def build_briefing(db_path=DB_PATH, research_dir=TUNING_DIR):
    evidence=read_research(research_dir)
    bundle=build_demo_bundle(db_path)
    if bundle["dataset"]["source_sha256"]!=evidence["manifest"]["source"]["sha256"]:
        raise ValueError("Nguồn của nghiên cứu và demo khác checksum; cần đối soát trước khi công bố.")
    reconciliation=reconcile_monthly(monthly_sales(read_detail(db_path)),evidence["monthly"])
    selection=evidence["selection"]
    method=CONFIG_TO_METHOD[selection["selected_configuration"]]
    if method!=bundle["selected_method"]:
        raise ValueError("Consumer base và nghiên cứu chọn khác phương pháp; cần cập nhật adapter có kiểm chứng.")
    bundle=copy.deepcopy(bundle)
    bundle["briefing_version"]="v3-research-backed"
    bundle["research"]={"selected_configuration":selection["selected_configuration"],"selected_method":method,
        "validation_mae":selection["validation_MAE"],"validation_n":24,"candidate_count":7,
        "gain_vs_previous_pct":selection["validation_gain_vs_baseline_pct"],"known_at":"2013-09-01",
        "test_previously_seen":True,"study_type":"exploratory_extension_after_seen_test",
        "manifest_sha256":evidence["manifest_sha256"],"source_sha256":selection["source_sha256"],
        "leaderboard":evidence["leaderboard"][["ModelName","Label","MAE","RMSE","MAPE","N","Rank","Selected"]].to_dict("records"),
        "reconciled_monthly_cells":len(reconciliation),"warehouse":"SQLite reference; native handoff pending"}
    inputs,checks,validation_rows,step_rows=[],[],[],[]
    for case in bundle["cases"]:
        config=METHOD_TO_CONFIG[case["method"]]
        scope=evidence["validation"].loc[lambda x:x.Market.eq(case["market"])&x.ModelName.eq(config)].sort_values("ForecastMonth")
        if len(scope)!=6 or not scope.ForecastMonth.lt(case["forecast_month"]).all():
            raise ValueError("Bằng chứng validation chưa sẵn sàng tại origin của case.")
        history=case["history"][-3:]
        terms=[{"month":row["month"],"sales":row["sales"],"weight":1/3,"weighted_sales":row["sales"]/3} for row in history]
        is_selected=case["method"]==method
        story={"is_selected":is_selected,"known_at":bundle["research"]["known_at"],
               "validation_history":[{"month":r.ForecastMonth,"actual":float(r.Actual),"prediction":float(r.Prediction)} for r in scope.itertuples()],
               "inputs":terms if case["method"]=="moving_average_3" else [],
               "formula":f"({' + '.join(number_vi(row['sales'],0) for row in terms)}) / 3 = {number_vi(case['prediction'],2)}" if case["method"]=="moving_average_3" else None}
        if story["inputs"] and not np.isclose(sum(x["weighted_sales"] for x in terms),case["prediction"],atol=1e-8):
            raise ValueError("Phép tính trung bình không tái dựng được dự báo.")
        reference=evidence["future"] if case["forecast_month"]=="2014-01-01" else evidence["test"]
        if is_selected:
            observed=reference.loc[reference.Market.eq(case["market"])&reference.ForecastMonth.eq(case["forecast_month"])]
            if "ModelName" in observed:
                observed=observed.loc[observed.ModelName.eq(selection["selected_configuration"])]
            if len(observed)!=1 or not np.isclose(observed.iloc[0].Prediction,case["prediction"],atol=1e-8):
                raise ValueError("Dự báo phục vụ không khớp kết quả đã chốt trong nghiên cứu.")
        case["story"]=story
        if is_selected:
            if method!="moving_average_3":
                raise ValueError("Kịch bản thuyết trình được kiểm chứng hiện hỗ trợ MA3 đã chọn.")
            case["chapters"]=narrative(case,bundle["research"])
        checks.append({"CaseID":case["id"],"Selected":is_selected,"Market":case["market"],"ForecastMonth":case["forecast_month"],
            "OriginBeforeTarget":case["train_end"]<case["forecast_month"],"ValidationRows":len(scope),
            "ValidationBeforeTarget":scope.ForecastMonth.lt(case["forecast_month"]).all(),
            "FormulaError":abs(sum(x["weighted_sales"] for x in terms)-case["prediction"]) if story["inputs"] else None,
            "MatchesResearch":True if is_selected else None,"HasActual":case["actual"] is not None})
        inputs.extend({"CaseID":case["id"],"Market":case["market"],"ForecastMonth":case["forecast_month"],**term} for term in story["inputs"])
        validation_rows.extend({"CaseID":case["id"],**row} for row in story["validation_history"])
        step_rows.extend({"CaseID":case["id"],"Step":i+1,"Title":chapter["title"],"Text":chapter["text"],
            "Evidence":"origin_history" if i==0 else "last_3_months" if i==1 and is_selected else "validation_known_by_2013_09" if i==2 else "model_additive_explanation",
            "ActualRevealedAutomatically":False} for i,chapter in enumerate(case["chapters"]))
    tables={"01_reconciliation/monthly_reconciliation":reconciliation,
            "02_story/case_checks":pd.DataFrame(checks),"02_story/formula_inputs":pd.DataFrame(inputs),
            "02_story/validation_history":pd.DataFrame(validation_rows),"02_story/steps":pd.DataFrame(step_rows),
            "03_research/leaderboard":evidence["leaderboard"],"03_research/retrospective_test_metrics":evidence["test_metrics"]}
    return bundle,tables


def validate_briefing(bundle):
    research=bundle.get("research")
    if bundle.get("briefing_version")!="v3-research-backed" or not research or research.get("candidate_count")!=7:
        raise ValueError("Gói thuyết trình thiếu phiên bản/bằng chứng nghiên cứu; hãy tạo lại.")
    for case in bundle["cases"]:
        story=case.get("story",{})
        history=story.get("validation_history",[])
        if len(history)!=6 or any(row["month"]>=case["forecast_month"] for row in history):
            raise ValueError("Bằng chứng kiểm chứng phải có trước tháng dự báo.")
        if case["method"]=="moving_average_3":
            terms=story.get("inputs",[])
            expected={row["month"]:row["sales"] for row in case["history"][-3:]}
            if (len(terms)!=3 or {r["month"]:r["sales"] for r in terms}!=expected
                or not np.isclose(sum(r["sales"] for r in terms)/3,case["prediction"],atol=1e-8)
                or any(not np.isclose(r["weight"],1/3) or not np.isclose(r["weighted_sales"],r["sales"]/3) for r in terms)):
                raise ValueError("Công thức ba tháng không khớp lịch sử/dự báo; hãy tạo lại gói.")


def case_markdown(case,bundle):
    if case["method"] == "moving_average_3":
        calculation = [case["story"]["formula"], "",
            "| Tháng đầu vào | Sales | Trọng số |", "| --- | --- | --- |",
            *[f"| {pd.Timestamp(r['month']):%m/%Y} | {number_vi(r['sales'],2)} | 1/3 |" for r in case["story"]["inputs"]]]
    elif case["method"] == "naive_last":
        latest = case["history"][-1]
        calculation = [f"Lấy Sales tháng {pd.Timestamp(latest['month']):%m/%Y}: {number_vi(latest['sales'],2)} × 1 = {number_vi(case['prediction'],2)}."]
    else:
        explanation = case["explanation"]
        calculation = [f"Mức nền: {number_vi(explanation['base_value'],4)}. Dự báo = mức nền + tổng đóng góp.", "",
            "| Lag | Tháng đầu vào | Sales | Tham chiếu | Hệ số thang gốc | Đóng góp |",
            "| --- | --- | --- | --- | --- | --- |",
            *[f"| {r['lag']} | {pd.Timestamp(r['month']):%m/%Y} | {number_vi(r['value'],2)} | {number_vi(r['reference_value'],4)} | {number_vi(r['weight_raw'],6)} | {number_vi(r['contribution'],4)} |" for r in explanation['features']], "",
            f"Tái dựng: {number_vi(explanation['reconstructed_prediction'],4)}; sai lệch số học {explanation['reconstruction_error']:.3g}.",
            "Đóng góp là cơ chế tính của mô hình so với tham chiếu, không phải tác động nhân quả. Các số trong bảng được làm tròn để trình bày."]
    lines=[f"# {case['market']} — dự báo {pd.Timestamp(case['forecast_month']):%m/%Y}","",
        f"Phương pháp: {bundle['methods'][case['method']]}. Dữ liệu đã biết đến {pd.Timestamp(case['train_end']):%m/%Y}.","",
        f"Dự báo: **{number_vi(case['prediction'],2)} đơn vị Sales**. Đây là dữ liệu lịch sử 2012–2013, chưa xác định đơn vị tiền.","",
        "## 1. Căn cứ tính toán","",*calculation,"",
        "## 2. Kiểm chứng đã biết tại origin","",
        f"MAE validation tại thị trường: {number_vi(case['validation_market']['MAE'],2)} trên 6 kỳ 04–09/2013. Sai số lịch sử không phải khoảng dự báo.","",
        "| Tháng validation | Actual | Dự báo |", "| --- | --- | --- |",
        *[f"| {pd.Timestamp(r['month']):%m/%Y} | {number_vi(r['actual'],2)} | {number_vi(r['prediction'],2)} |" for r in case['story']['validation_history']], "",
        "## 3. Lời thuyết trình","",*[f"### {c['title']}\n\n{c['text']}\n" for c in case["chapters"]],"",
        "## 4. Đối chiếu sau dự báo","",
        "Chưa có actual trong nguồn." if case["actual"] is None else f"Actual: {number_vi(case['actual'],2)}; sai số tuyệt đối: {number_vi(abs(case['prediction']-case['actual']),2)}. Actual không tham gia tính dự báo.","",
        "Không suy ra nguyên nhân khuyến mãi, thời tiết hay nhu cầu nguyên liệu từ cơ chế trung bình. Bảy cấu hình đã thử trong nghiên cứu mở rộng trên test đã biết; lựa chọn dùng validation.",""]
    return "\n".join(lines)
