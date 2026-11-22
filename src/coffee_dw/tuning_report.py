"""Vietnamese research report and presentation notes from measured results."""

import html

import pandas as pd

from coffee_dw.baseline_report import formatted_table, markdown_table
from coffee_dw.exploration import vi
from coffee_dw.tuning_study import BY_KEY, LABELS

STAGES = {
    "01_protocol": "1. Dữ liệu, câu hỏi và phạm vi thử",
    "02_validation": "2. Thử siêu tham số và chọn cấu hình",
    "03_test": "3. Kiểm tra và phân tích sai số",
    "04_comparison": "4. So sánh với bước cơ sở",
    "05_models": "5. Tham số đã học, mô hình và dự báo",
    "06_summary": "6. Kết luận và cách đưa vào báo cáo",
}


def pooled(s, split, key=None):
    return s["pooled"].loc[lambda x:x.Split.eq(split) & x.ModelName.eq(key or s["selected"])].iloc[0]


def presentation_summary(s):
    val, test = pooled(s,"validation"), pooled(s,"test")
    return pd.DataFrame([
        ("Phạm vi", "7 cấu hình: Naive, MA cửa sổ 2/3/6, Ridge alpha 0,1/1/10; giữ lag1/2/3.", "01_protocol/configurations.csv"),
        ("Huấn luyện", "72 lần fit Ridge validation, 36 lần test, 12 lần fit cuối; scaler chỉ dùng quá khứ.", "02_validation/learned_parameters.csv"),
        ("Lựa chọn", f"{LABELS[s['selected']]}; MAE validation {vi(val.MAE,2)} trên 24 dự báo; chọn trước test.", "02_validation/selection.json"),
        ("So bước trước", f"MAE validation cải thiện {vi(s['decision']['validation_gain_vs_baseline_pct'],2)}%; cấu hình cơ sở vẫn được giữ.", "04_comparison/selected_vs_references.csv"),
        ("Kiểm tra", f"MAE {vi(test.MAE,2)}; RMSE {vi(test.RMSE,2)}; MAPE {vi(test.MAPE,2)}%; N = 12; test đã biết.", "03_test/selected_metrics.csv"),
        ("Bàn giao", "12 pipeline Ridge, 28 trạng thái cấu hình, gói chọn và 4 dự báo 01/2014 chưa có actual.", "05_models/model_index.csv"),
    ],columns=["Step","Result","Evidence"])


def final_parameter_table(s):
    part=s["final_parameters"]
    table=part.pivot(index=["Market","ModelName"],columns="Feature",values="CoefficientRaw").reset_index()
    info=part.groupby(["Market","ModelName"],as_index=False).first()[["Market","ModelName","Alpha","FitN","InterceptRaw"]]
    return info.merge(table,on=["Market","ModelName"],validate="one_to_one")


def write_reports(s, output, figures, summary):
    selected=s["selected"]
    val,test=pooled(s,"validation"),pooled(s,"test")
    naive_val,naive_test=pooled(s,"validation","naive_last"),pooled(s,"test","naive_last")
    gain=s["improvement"].loc[lambda x:x.ModelName.eq(selected)&x.Split.eq("test")].iloc[0]
    board=s["leaderboard"].copy()
    test_all=s["pooled"].loc[s["pooled"].Split.eq("test")].set_index("ModelName").loc[board.ModelName].reset_index()
    selected_market=s["test_metrics"].loc[lambda x:x.ModelName.eq(selected)&~x.Market.eq("ALL")]
    ma=board.loc[board.ModelName.str.startswith("ma_")].sort_values("MAE")
    ridge=board.loc[board.ModelName.str.startswith("ridge_")].sort_values("MAE")
    worst=s["errors"].loc[lambda x:x.ModelName.eq(selected)&x.Split.eq("test")].nlargest(1,"AbsoluteError").iloc[0]
    best_test=test_all.sort_values("MAE").iloc[0]
    sensitivity_wins=int(s["stability"].Winner.eq(selected).sum())
    weights=final_parameter_table(s)
    weights.to_csv(output/"05_models/final_coefficients_readable.csv",index=False,encoding="utf-8-sig")
    val_gain=100*(naive_val.MAE-val.MAE)/naive_val.MAE
    ridge_gain=100*(pooled(s,"validation","ridge_a0p1").MAE-ridge.iloc[0].MAE)/pooled(s,"validation","ridge_a0p1").MAE
    winner_count=s["validation_metrics"].loc[lambda x:~x.Market.eq("ALL")].sort_values("MAE").groupby("Market").first()
    market_wins=int(winner_count.ModelName.eq(selected).sum())
    stage_notes={
        "01_protocol": [
            "Câu hỏi nghiên cứu: thay cửa sổ trung bình và alpha của Ridge có giảm MAE validation so với thí nghiệm cơ sở không? Mục tiêu ứng dụng là cung cấp một mốc Sales tháng sau theo thị trường, kèm lịch sử sai số để người quản lý cân nhắc.",
            f"Đầu vào giữ nguyên: {vi(s['source']['accepted_rows'])} dòng hợp lệ, 0 reject; 96 ô Market–tháng; tổng Sales {vi(s['source']['sales'])}. Đây là 24 tháng mỗi thị trường, không phải 4.248 mẫu thời gian độc lập hoặc 4.248 đơn hàng.",
            "Chạy trực tiếp nguồn qua bộ chuẩn hóa chung, chưa cần kho của Chi; không tạo thêm doanh số giả. Khi Chi bàn giao mart cần đối soát từng ô Market–tháng trước khi thay nguồn.",
            "Thử toàn bộ bảy cấu hình đã công bố: Naive; MA cửa sổ 2, 3, 6; Ridge alpha 0,1, 1, 10. Đây là toàn bộ lưới nhỏ đã thống nhất, không phải mọi thuật toán hoặc mọi giá trị tham số có thể tồn tại.",
            "15 tháng đầu 01/2012–03/2013 làm lịch sử; 04–09/2013 dùng chọn; 10–12/2013 kiểm tra. Mỗi lần dự báo một tháng, lịch sử mở rộng sau khi tháng mới được quan sát. Không dự báo đồng thời cả ba tháng bằng một mốc phát hành.",
            "Ridge giữ cố định lag1/2/3, StandardScaler, fit_intercept=True và solver=svd để tái lập tất định. So với solver tự động của base, cấu hình alpha=1 được kiểm tra tương đương dự báo trong sai số số học; không xem solver là tham số đã dò.",
        ],
        "02_validation": [
            "Siêu tham số là lựa chọn trước khi học: window của MA và alpha của Ridge. Tham số học là ba hệ số hồi quy cùng intercept; mean/scale của scaler cũng được ước lượng từ lịch sử. Không gọi các hệ số này là siêu tham số.",
            "MA2/MA3/MA6 chỉ lấy trung bình số tháng tương ứng, không học trọng số và không có epoch/loss curve. Ridge được giải bằng SVD, không phải mạng nơ-ron huấn luyện theo epoch.",
            "Tại origin đầu, mỗi Market có 15 tháng; sau tạo ba lag còn 12 mẫu học Ridge. Scaler fit đúng 12 mẫu quá khứ này. Mỗi alpha được fit lại theo từng origin; tổng cộng 72 lần fit Ridge validation và 168 dự báo của bảy cấu hình.",
            f"Chọn {LABELS[selected]} với MAE {vi(val.MAE,2)} trên 24 dự báo validation. So Naive ({vi(naive_val.MAE,2)}), giảm {vi(val_gain,2)}%. Trong lưới mở rộng, cấu hình chọn có MAE tốt nhất tại {market_wins}/4 Market; không suy ra mọi Market đều nên dùng cấu hình này riêng lẻ.",
            f"Trong nhóm MA: cửa sổ 3 tháng đứng đầu; MA6 có MAE {vi(pooled(s,'validation','ma_w6').MAE,2)}, MA2 có MAE {vi(pooled(s,'validation','ma_w2').MAE,2)}. Trên các kỳ này, cửa sổ 3 tháng cân bằng phản ứng với biến động và làm mượt tốt hơn hai lựa chọn còn lại; đây là diễn giải từ kết quả, chưa phải quy luật chung.",
            f"Trong nhóm Ridge: {LABELS[ridge.iloc[0].ModelName]} tốt nhất với MAE {vi(ridge.iloc[0].MAE,2)}, giảm {vi(ridge_gain,2)}% so alpha=0,1. Tăng alpha trong lưới giúp validation tốt hơn nhưng vẫn chưa vượt MA3. Đường MAE fit chỉ mô tả mẫu học của từng origin, không phải tiêu chí chọn.",
            f"Khi lần lượt bỏ một tháng khỏi bảng chấm validation, {LABELS[selected]} đứng đầu {sensitivity_wins}/6 trường hợp. Việc này chỉ kiểm tra độ nhạy trên các dự báo đã có, không tạo sáu lần kiểm định độc lập và không được dùng để đổi lựa chọn.",
            "Xếp hạng theo MAE gộp bốn Market, dùng số chưa làm tròn. Nếu bằng nhau, dùng thứ tự cấu hình đã lưu trong protocol. Lưu selection.json trước khi gọi pha test; execution_events.csv ghi lại thứ tự thực thi.",
        ],
        "03_test": [
            f"Tạo 84 dự báo test của bảy cấu hình; cấu hình đã chọn có 12 dự báo, ba tháng mỗi Market. Kết quả {LABELS[selected]}: MAE {vi(test.MAE,2)}, RMSE {vi(test.RMSE,2)}, MAPE {vi(test.MAPE,2)}%, Bias {vi(test.Bias,2)}.",
            f"So Naive, MAE test {'giảm' if gain.MAE_ImprovementPct>=0 else 'tăng'} {vi(abs(gain.MAE_ImprovementPct),2)}%, RMSE {'giảm' if gain.RMSE_ImprovementPct>=0 else 'tăng'} {vi(abs(gain.RMSE_ImprovementPct),2)}%. Phải trình bày cả hai mặt, không gọi đây là mô hình thắng mọi metric.",
            f"Cấu hình có MAE test thấp nhất trong bảng là {LABELS[best_test.ModelName]} ({vi(best_test.MAE,2)}). Không chuyển sang cấu hình đó dựa vào test; kết quả được công bố để đối chiếu sau khi đã khóa lựa chọn.",
            f"Ca lệch lớn nhất của cấu hình chọn: {worst.Market} {worst.ForecastMonth:%m/%Y}, actual {vi(worst.Actual)}, prediction {vi(worst.Prediction,2)}, sai số tuyệt đối {vi(worst.AbsoluteError,2)}. Chưa có dữ liệu xác định nguyên nhân thời tiết, khuyến mãi hoặc thiếu hàng.",
            "MAE là trung bình độ lệch tuyệt đối; RMSE nhạy với các lần lệch lớn; MAPE là trung bình tỷ lệ sai số trên actual khác 0, với MAPE_N ghi số trường hợp hợp lệ. Bias = Prediction − Actual; dương nghĩa là dự báo cao. Không gọi 100% − MAPE là accuracy, không coi MAE là khoảng tin cậy.",
            "Các tháng test đã được xem trong bước cơ sở trước khi thiết kế lưới này. Vì vậy đây là thử nghiệm mở rộng mang tính thăm dò; tệp lựa chọn trước test chỉ chứng minh thứ tự thực thi lần này, không biến test thành một kiểm định mù mới. Chỉ ba tháng mỗi Market, chưa đủ chứng minh ưu thế bền vững.",
        ],
        "04_comparison": [
            f"So phương pháp chọn ở bước cơ sở ({LABELS[s['decision']['previous_baseline_selected']]}), mức cải thiện MAE validation là {vi(s['decision']['validation_gain_vs_baseline_pct'],2)}%. Kết quả lựa chọn không thay đổi; thử thêm tham số chưa tạo ra một phương pháp phục vụ tốt hơn trong phạm vi lưới đã thử.",
            "Đóng góp không phải tạo ra thuật toán mới: Trang thiết kế phép so sánh cùng thời gian, thực thi đủ cấu hình, lưu thông số học, kiểm tra rò rỉ, phân tích sai số và đưa ra quyết định có căn cứ. Kết quả không cải thiện vẫn cần được báo cáo.",
            "Không tiếp tục mở rộng tham số chỉ để tìm một con số test đẹp hơn. Chốt vòng nhỏ này làm bằng chứng nghiên cứu; các mở rộng tiếp theo cần một câu hỏi mới và, nếu muốn kiểm định độc lập, thêm các kỳ dữ liệu thực chưa quan sát.",
        ],
        "05_models": [
            "Sau khi chọn, fit lại cả ba Ridge trên toàn bộ 24 tháng đã biết: 21 mẫu có đủ lag/Market, 12 pipeline cuối. Tổng Ridge có 120 lần fit = 72 validation + 36 test + 12 cuối; các model ở origin trung gian được lưu bằng bảng thông số, không phải 120 file nhị phân.",
            "Lưu 12 pipeline .joblib (cả scaler và Ridge), 28 trạng thái .json cho 7 cấu hình × 4 Market, model_index.csv và selected_bundle.json. Có 28 dự báo 01/2014 để đối chiếu, trong đó 4 dự báo thuộc cấu hình chọn. Đã nạp lại các pipeline vừa xuất để đối chiếu dự báo.",
            "Các hệ số trên thang gốc biểu diễn: Sales dự báo = InterceptRaw + CoefficientRaw(lag1) × Sales tháng trước + CoefficientRaw(lag2) × Sales hai tháng trước + CoefficientRaw(lag3) × Sales ba tháng trước. Hệ số không phải tác động nhân quả hoặc phần trăm đóng góp.",
            f"Gói phục vụ được chọn vẫn là {LABELS[selected]}. Với MA3, dự báo bằng trung bình ba tháng gần nhất; trạng thái và quy tắc JSON là đủ, không cần tạo .pth. Các pipeline Ridge được giữ lại làm minh chứng đối chứng.",
            "Actual 01/2014 để trống vì nguồn kết thúc 12/2013. Chưa đo được sai số kỳ này, chưa có khoảng dự báo được hiệu chuẩn. Các dự báo là tháng lịch sử ngoài nguồn, không phải dự báo cho thời điểm hiện tại.",
        ],
        "06_summary": [
            "Kết luận: đã thử đủ lưới bảy cấu hình; MA3 tiếp tục có MAE validation tốt nhất. Ridge cải thiện khi tăng alpha trong lưới, nhưng chưa vượt phương pháp trung bình. Thử tham số xác nhận giữ cấu hình cơ sở, chưa tạo mức cải thiện mới.",
            "Bước tiếp theo là đưa kết quả đã chốt vào luồng thuyết trình: chọn Market → xem dự báo → xem ba tháng tạo dự báo → xem sai số lịch sử và giới hạn. Không cần tiếp tục huấn luyện nhiều thuật toán chỉ để tăng số lượng thí nghiệm.",
            "Chưa nghiệm thu bàn giao mart của Chi, TN12 West với protocol riêng, SQL Server/SSIS/SSAS, benchmark hay UX từ thí nghiệm này. Không tự thay gói dữ liệu hoặc logic của dashboard đang chạy.",
        ],
    }
    views={
        "01_protocol": [("Bảy cấu hình",s["specs"],["Label","Family","Window","Alpha","Features","LearnsCoefficients"])],
        "02_validation": [("Xếp hạng validation",board,["Rank","Label","N","MAE","RMSE","MAPE","Bias","Selected"]),
                          ("Độ nhạy khi bỏ một tháng khỏi điểm",s["stability"],["OmittedValidationMonth","Winner","MAE","N"])],
        "03_test": [("Toàn bộ cấu hình trên test",test_all,["Label","N","MAE","RMSE","MAPE","Bias","Selected"]),
                    ("Cấu hình đã chọn theo từng Market",selected_market,["Market","N","MAE","RMSE","MAPE","Bias"])],
        "04_comparison": [("Cải thiện dương là giảm sai số",s["comparison"],None)],
        "05_models": [("Hệ số Ridge trên thang Sales gốc",weights,["Market","ModelName","Alpha","FitN","InterceptRaw","lag1","lag2","lag3"]),
                      ("Bốn dự báo được chọn",s["future"].loc[lambda x:x.Selected],["Market","ForecastMonth","LastActual","Prediction","Actual"])],
        "06_summary": [("Các kết quả để trình bày",summary,["Step","Result"])],
    }
    lines=["# Báo cáo thử nghiệm siêu tham số dự báo Coffee Chains", "",
        "**Kết luận:** đã thử đủ bảy cấu hình đã thống nhất; MA3 tiếp tục được chọn theo MAE validation. Thử tham số chưa cải thiện so cấu hình cơ sở. Test đã được xem trước nên đây là nghiên cứu mở rộng thăm dò.", "",
        markdown_table(summary,["Step","Result"]), ""]
    html_sections=[]
    for stage,title in STAGES.items():
        lines += [f"## {title}", "", *[f"- {note}" for note in stage_notes[stage]], ""]
        tables_html=""
        for table_title,table,columns in views[stage]:
            lines += [f"### {table_title}","",markdown_table(table,columns),""]
            tables_html+=f"<h3>{html.escape(table_title)}</h3><div class='table-wrap'>{formatted_table(table,columns)}</div>"
        gallery=""
        for f in [f for f in figures if f["stage"]==stage]:
            path=f["path"]
            lines += [f"### {f['title']}","",f"![{f['title']}]({path}.png)","",f["note"],"",
                      f"[PNG 300 dpi]({path}.png) · [PDF vector]({path}.pdf) · [SVG]({path}.svg)",""]
            gallery+=f"<figure><img src='{path}.png' alt='{html.escape(f['title'])}' loading='lazy'><figcaption>{html.escape(f['note'])}<br><a href='{path}.png'>PNG 300 dpi</a> · <a href='{path}.pdf'>PDF vector</a> · <a href='{path}.svg'>SVG</a></figcaption></figure>"
        csvs=sorted((output/stage).glob("*.csv"))
        links=" · ".join(f"<a href='{stage}/{p.name}'>{p.name}</a>" for p in csvs)
        lines += ["Bảng số liệu gốc: "+" · ".join(f"[{p.name}]({stage}/{p.name})" for p in csvs),""]
        html_sections.append(f"<section id='{stage}'><h2>{title}</h2><ul>"+"".join(f"<li>{html.escape(n)}</li>" for n in stage_notes[stage])+"</ul>"+tables_html+gallery+f"<p class='files'>Bảng gốc: {links}</p></section>")
    sources=[
        "Ridge: alpha điều chỉnh mức phạt hệ số; mô tả solver và các tham số trong [tài liệu scikit-learn Ridge](https://scikit-learn.org/1.7/modules/generated/sklearn.linear_model.Ridge.html).",
        "Fit tiền xử lý trên train, tránh rò rỉ: [scikit-learn Common pitfalls](https://scikit-learn.org/1.7/common_pitfalls.html).",
        "Đánh giá dự báo theo thời gian và rolling origin: [Forecasting: Principles and Practice](https://otexts.com/fpp3/toolbox.html).",
    ]
    lines += ["## Tái lập và giới hạn", "", "```powershell", ".\\.venv\\Scripts\\python experiments/tuning/run.py", "```", "",
              "CSV giữ số chưa làm tròn; PNG 300 dpi, PDF/SVG để chèn báo cáo. Manifest ghi phiên bản thư viện, checksum nguồn/mã/artifact. Các kết quả và model được sinh cục bộ, giữ nguyên Coffee.csv và output nghiên cứu cơ sở.","",
              "## Tài liệu phương pháp","", *["- "+x for x in sources],""]
    (output/"analysis.md").write_text("\n".join(lines),encoding="utf-8")
    (output/"02_validation/decision.md").write_text("# Quyết định sau vòng thử siêu tham số\n\n"+
        "\n\n".join(stage_notes["02_validation"]+stage_notes["04_comparison"][:1])+"\n\nTest đã biết từ trước; đây là mở rộng thăm dò. [Lựa chọn JSON](selection.json) · [Nhật ký thứ tự thực thi](../06_summary/execution_events.csv).\n",encoding="utf-8")
    (output/"05_models/README.md").write_text("# Các mô hình và trạng thái đã xuất\n\n"+
        "\n\n".join(stage_notes["05_models"])+"\n\nXem [chỉ mục](model_index.csv), [gói cấu hình chọn](selected_bundle.json), [hệ số cuối](final_coefficients_readable.csv). Pipeline được lưu bằng phiên bản scikit-learn/joblib trong [manifest](../manifest.json); dùng môi trường cùng phiên bản để tái lập.\n",encoding="utf-8")
    speech=(f"Sau thí nghiệm cơ sở, nhóm kiểm tra liệu thay đổi tham số có giúp dự báo tốt hơn không. "
        f"Nhóm thử bảy cấu hình trên cùng dữ liệu và lịch đánh giá. Với Ridge, nhóm giữ ba tháng doanh số quá khứ làm đầu vào, "
        f"thử ba mức alpha và lưu cả hệ số mô hình học được. Với trung bình trượt, nhóm thử hai, ba và sáu tháng. "
        f"Kết quả, {LABELS[selected]} vẫn đứng đầu với MAE validation {vi(val.MAE,2)}; vòng thử chưa cải thiện cấu hình cơ sở. "
        f"Trên các tháng test đã biết, MAE là {vi(test.MAE,2)}, RMSE {vi(test.RMSE,2)}. Nhóm trình bày cả trường hợp sai số lớn và giới hạn chỉ ba tháng kiểm tra mỗi thị trường. "
        f"Nhóm giữ MA3 để xây báo cáo dự báo có giải thích, thay vì chọn lại theo kết quả test.")
    slides=["# Gợi ý trình bày kết quả thử tham số", "",
        "| Trang | Hình nên chèn | Điều cần nói |", "| --- | --- | --- |",
        "| 1 | [Bảy cấu hình](01_protocol/figures/01_configurations.png) | Đã thử gì; siêu tham số khác hệ số học như thế nào. |",
        "| 2 | [Cửa sổ MA](02_validation/figures/02_ma_window.png), [alpha Ridge](02_validation/figures/03_ridge_alpha.png) | Thay từng tham số ảnh hưởng MAE ra sao; giữ cùng lịch chấm. |",
        "| 3 | [Xếp hạng](02_validation/figures/01_ranking.png) | Chọn bằng validation; MA3 vẫn tốt nhất. |",
        "| 4 | [Thực tế – dự báo](03_test/figures/01_actual_forecast.png), [sai số](03_test/figures/03_selected_errors.png) | Cho thấy cả ca bám tốt và ca lệch; test đã biết. |",
        "| 5 | [Trước – sau](04_comparison/figures/01_before_after.png), [tóm tắt](06_summary/figures/01_summary.png) | Tuning chưa cải thiện; giữ cấu hình có căn cứ, chuẩn bị gắn dashboard. |", "",
        "## Lời nói khoảng một đến hai phút", "", speech, "",
        "## Nếu cô hỏi đóng góp của Trang", "",
        "Em tổ chức và thực thi thí nghiệm trên dữ liệu nhóm, kiểm soát lịch sử đầu vào, thử đủ cấu hình, lưu siêu tham số và tham số học được, đo các chỉ số trên cùng kỳ, phân tích sai số và trình bày quyết định lựa chọn. Em sử dụng thuật toán thư viện; em không tuyên bố tự phát minh Ridge. Kết quả thử tham số không cải thiện cũng được giữ lại để báo cáo.", ""]
    (output/"presentation.md").write_text("\n".join(slides),encoding="utf-8")
    nav="".join(f"<a href='#{stage}'>{title}</a>" for stage,title in STAGES.items())
    source_html="".join(f"<li><a href='{url}'>{label}</a></li>" for label,url in [
        ("scikit-learn 1.7 · Ridge","https://scikit-learn.org/1.7/modules/generated/sklearn.linear_model.Ridge.html"),
        ("scikit-learn 1.7 · tránh rò rỉ dữ liệu","https://scikit-learn.org/1.7/common_pitfalls.html"),
        ("Forecasting: Principles and Practice","https://otexts.com/fpp3/toolbox.html")])
    page="""<!doctype html><html lang='vi'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>Coffee · Báo cáo thử siêu tham số</title><style>
    *{box-sizing:border-box}body{margin:0;background:#f1f5f9;color:#18324e;font:20px/1.7 'Times New Roman',Times,serif}main{max-width:1260px;margin:auto;padding:36px 30px}header{background:#183b62;color:white;padding:32px;border-radius:14px}h1{font-size:39px;line-height:1.25;margin:12px 0}h2{font-size:29px;color:#183b62}h3{font-size:23px}a{color:#1a5f86}nav{display:flex;flex-wrap:wrap;gap:10px 22px;padding:23px 0}section{margin-top:34px;padding-top:10px}li{margin:10px 0}figure{margin:28px 0;padding:16px;background:white;border:1px solid #bdccda;border-radius:10px}img{width:100%;height:auto}figcaption{font-size:18px}.table-wrap{overflow:auto;margin:15px 0}table{border-collapse:collapse;width:100%;background:white;font-size:17px}th,td{padding:10px;border:1px solid #bdccda;text-align:left}th{background:#dfebf4}.note{padding:20px 24px;background:#e1edf2;border-left:5px solid #207f83}.metrics{display:flex;gap:38px;flex-wrap:wrap;margin-top:24px}.metrics strong{font-size:32px}.files{font-size:17px;overflow-wrap:anywhere}@media print{body{background:white}main{padding:0}nav{display:none}figure{break-inside:avoid}header{color:#18324e;background:white;border:1px solid #bdccda}}
    </style><main><header><div>COFFEE CHAINS · THỬ NGHIỆM CỦA TRANG</div><h1>Thử tham số, đo kết quả,<br>giữ quyết định có căn cứ</h1><p>Báo cáo nghiên cứu mở rộng sau thí nghiệm cơ sở</p><div class='metrics'>__METRICS__</div></header>
    <nav>__NAV__</nav><div class='note'><strong>Kết luận: MA3 vẫn được chọn.</strong> Thử đủ lưới bảy cấu hình chưa cải thiện MAE validation so bước cơ sở. Test đã được xem trước; đây là thử nghiệm mở rộng, chưa phải kiểm định mù mới.</div>
    __SECTIONS__<section><h2>Tệp bàn giao và nguồn phương pháp</h2><p><a href='analysis.md'>Phân tích đầy đủ</a> · <a href='presentation.md'>Gợi ý thuyết trình</a> · <a href='manifest.json'>Manifest / checksum</a> · <a href='05_models/model_index.csv'>Chỉ mục mô hình</a> · <a href='05_models/selected_bundle.json'>Gói cấu hình chọn</a></p><ul>__SOURCES__</ul></section></main></html>"""
    metric_html=f"<div><strong>7 cấu hình</strong><br>thử đủ lưới đã công bố</div><div><strong>{vi(val.MAE,2)}</strong><br>MAE validation · N = 24</div><div><strong>{vi(test.MAE,2)}</strong><br>MAE test đã biết · N = 12</div>"
    (output/"report.html").write_text(page.replace("__METRICS__",metric_html).replace("__NAV__",nav).replace("__SECTIONS__","".join(html_sections)).replace("__SOURCES__",source_html),encoding="utf-8")
