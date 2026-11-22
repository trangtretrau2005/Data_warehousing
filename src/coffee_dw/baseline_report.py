"""Vietnamese interpretation, presentation notes and an offline HTML gallery."""

from pathlib import Path
import html

import pandas as pd

from coffee_dw.baseline_study import LABELS
from coffee_dw.exploration import vi


STAGES={"01_input":"1. Chốt dữ liệu đầu vào","02_protocol":"2. Cách học, cách chấm và ba cấu hình",
        "03_validation":"3. So sánh validation và lưu lựa chọn","04_test":"4. Kiểm tra test và phân tích sai số",
        "05_future":"5. Áp dụng cho kỳ tiếp theo","06_summary":"6. Tóm tắt để báo cáo, thuyết trình"}


def pooled(study,split,method=None):
    metrics=study['validation_metrics'] if split=='validation' else study['test_metrics']
    return metrics.loc[metrics.Market.eq('ALL') & metrics.ModelName.eq(method or study['selected'])].iloc[0]


def presentation_summary(s):
    val,test=pooled(s,'validation'),pooled(s,'test')
    improvement=s['improvement'].loc[s['improvement'].Split.eq('test') & s['improvement'].ModelName.eq(s['selected'])].iloc[0]
    mae_direction='tốt hơn' if improvement.MAE_ImprovementPct>=0 else 'kém hơn'
    rows=[
        ('Dữ liệu',f"{vi(s['source']['accepted_rows'])} dòng nguồn → 96 ô Market–tháng; 0 reject.",'01_input/input_checks.csv','01_input'),
        ('Thiết kế',"15 tháng khởi tạo, 6 validation, 3 test; chỉ dùng quá khứ.",'02_protocol/protocol.json','02_protocol'),
        ('Lựa chọn',f"{LABELS[s['selected']]}; MAE validation {vi(val.MAE,2)}; N = {int(val.N)}.",'03_validation/selection.json','03_validation'),
        ('Kiểm tra',f"MAE {vi(test.MAE,2)}; RMSE {vi(test.RMSE,2)}; MAPE {vi(test.MAPE,2)}%; N = {int(test.N)}.",'04_test/selected_metrics.csv','04_test'),
        ('Giới hạn',f"MAE test {mae_direction} Naive {vi(abs(improvement.MAE_ImprovementPct),2)}%; không thắng mọi chỉ số.",'04_test/improvement_vs_naive.csv','04_test'),
        ('Áp dụng',"4 dự báo 01/2014; chưa có thực tế để chấm sai số.",'05_future/next_month.csv','05_future'),
    ]
    return pd.DataFrame(rows,columns=['Stage','Result','Evidence','Folder'])


def formatted_table(table,columns=None):
    copy=table[columns].copy() if columns else table.copy()
    for column in copy.columns:
        if pd.api.types.is_datetime64_any_dtype(copy[column]):
            copy[column]=copy[column].dt.strftime('%m/%Y')
        elif pd.api.types.is_float_dtype(copy[column]):
            copy[column]=copy[column].map(lambda x:vi(x,2))
    return copy.to_html(index=False,escape=True,na_rep='—',border=0)


def markdown_table(table,columns=None):
    # Avoid optional tabulate dependency and preserve all exact CSVs separately.
    copy=table[columns].copy() if columns else table.copy()
    def cell(value):
        if isinstance(value,float):return vi(value,2)
        if isinstance(value,pd.Timestamp):return value.strftime('%m/%Y')
        return str(value).replace('|','/')
    return '\n'.join(['| '+' | '.join(map(str,copy.columns))+' |','| '+' | '.join(['---']*len(copy.columns))+' |',
                      *['| '+' | '.join(cell(v) for v in row)+' |' for row in copy.itertuples(index=False,name=None)]])


def write_reports(s,output:Path,figures,presentation):
    val,test=pooled(s,'validation'),pooled(s,'test')
    naive_val,naive_test=pooled(s,'validation','naive_last'),pooled(s,'test','naive_last')
    gain=s['improvement'].loc[s['improvement'].Split.eq('test')&s['improvement'].ModelName.eq(s['selected'])].iloc[0]
    selected_market=s['test_metrics'].loc[~s['test_metrics'].Market.eq('ALL') & s['test_metrics'].ModelName.eq(s['selected'])].sort_values('MAE',ascending=False)
    worst=selected_market.iloc[0]
    worst_case=s['errors'].loc[s['errors'].Split.eq('test')&s['errors'].ModelName.eq(s['selected'])].sort_values('AbsoluteError',ascending=False).iloc[0]
    best_test=s['test_metrics'].loc[s['test_metrics'].Market.eq('ALL')].sort_values('MAE').iloc[0]
    local_winners=s['validation_metrics'].loc[~s['validation_metrics'].Market.eq('ALL')].sort_values('MAE').groupby('Market',sort=True).first()
    chosen_wins=int(local_winners.ModelName.eq(s['selected']).sum())
    leaderboard=s['leaderboard'].copy();leaderboard['Phương pháp']=leaderboard.ModelName.map(LABELS)
    test_summary=s['test_metrics'].loc[s['test_metrics'].Market.eq('ALL')].copy();test_summary['Phương pháp']=test_summary.ModelName.map(LABELS)
    phase_notes={
        '01_input':[
            f"Đọc trực tiếp Coffee.csv: {vi(s['source']['accepted_rows'])} dòng hợp lệ, 0 reject. Tổng hợp thành 96 ô Market–tháng, Sales {vi(s['source']['sales'])}; số liệu được bảo toàn.",
            "Chưa cần code hoặc cơ sở dữ liệu của Chi. Đây là thí nghiệm trên nguồn chuẩn hóa; khi có kho, đối chiếu từng ô trước khi đổi đầu vào.",
            "4.248 dòng nguồn không phải 4.248 mẫu học theo thời gian. Mỗi Market có 24 tháng; ở lần fit đầu chỉ có 12 mẫu đủ lag123. Không tạo thêm doanh số giả.",
        ],
        '02_protocol':[
            "Giữ cố định ba cấu hình: lấy tháng trước, trung bình 3 tháng, Ridge(alpha=1) với lag1/2/3 và StandardScaler. Không chạy tìm kiếm siêu tham số ở bước này.",
            "15 tháng đầu 01/2012–03/2013 làm lịch sử khởi tạo. Sáu tháng 04–09/2013 dùng lựa chọn; ba tháng 10–12/2013 dùng đánh giá sau lựa chọn. Mỗi lần dự báo chỉ dùng các tháng đã kết thúc.",
            "Scaler được fit riêng từ đầu vào quá khứ tại từng origin; không chuẩn hóa toàn bộ 24 tháng. Bảng first_origin_training có 48 mẫu = 12 mỗi Market; các thông số fit ghi trong ridge_fit_audit.",
            "Chọn bằng MAE gộp bốn Market; MAE/RMSE thấp hơn là tốt hơn. MAPE bỏ actual bằng 0; Bias dương nghĩa là dự báo cao. Không gọi 100% − MAPE là accuracy.",
            "Đây là tái lập protocol tham chiếu đã biết kết quả test. Tệp lựa chọn được lưu trước pha test trong lần chạy, không đồng nghĩa chưa từng nhìn kết quả test trước đây.",
        ],
        '03_validation':[
            f"Có 72 dự báo validation = 4 Market × 6 tháng × 3 phương pháp. Mỗi phương pháp được chấm trên cùng 24 trường hợp.",
            f"Chọn {LABELS[s['selected']]} bằng MAE {vi(val.MAE,2)}. Naive có MAE {vi(naive_val.MAE,2)}; mức giảm MAE là {vi((naive_val.MAE-val.MAE)/naive_val.MAE*100,2)}% ở validation.",
            f"Phương pháp chọn cũng có MAE thấp nhất ở {chosen_wins}/4 Market validation. Lựa chọn tốt nhất theo điểm gộp chưa chắc tốt nhất ở từng Market; xem biểu đồ nhóm để nhận ra khác biệt.",
            "Thứ hạng dùng số chưa làm tròn. Nếu bằng MAE thì dùng thứ tự phương pháp đã khai báo. Không chọn bằng RMSE hoặc MAPE sau khi xem chỉ số nào có lợi.",
            "selection.json lưu phương pháp, tham số, MAE, N, checksum dữ liệu và dự báo validation. execution_events.csv ghi selection_saved trước test_started.",
        ],
        '04_test':[
            f"Có 36 dự báo test của cả ba phương pháp; phương pháp đã chọn có 12 dự báo, 3 tại mỗi Market. Kết quả: MAE {vi(test.MAE,2)}, RMSE {vi(test.RMSE,2)}, MAPE {vi(test.MAPE,2)}%.",
            f"So với Naive (MAE {vi(naive_test.MAE,2)}), MAE test của phương pháp chọn {'giảm' if gain.MAE_ImprovementPct>=0 else 'tăng'} {vi(abs(gain.MAE_ImprovementPct),2)}%. RMSE {'giảm' if gain.RMSE_ImprovementPct>=0 else 'tăng'} {vi(abs(gain.RMSE_ImprovementPct),2)}%. Vì vậy kết quả không thắng mọi tiêu chí.",
            f"Market có MAE lớn nhất của phương pháp chọn: {worst.Market}, {vi(worst.MAE,2)} (N = {int(worst.N)}). Đọc thêm sai số từng tháng, không kết luận từ trung bình duy nhất.",
            f"Ca lệch tuyệt đối lớn nhất: {worst_case.Market}, {worst_case.ForecastMonth:%m/%Y}; thực tế {vi(worst_case.Actual)}, dự báo {vi(worst_case.Prediction,2)}, lệch {vi(worst_case.AbsoluteError,2)}. Đây là ca để thảo luận, chưa có dữ liệu xác định nguyên nhân kinh doanh.",
            f"Đối chứng có MAE test thấp nhất là {LABELS[best_test.ModelName]} ({vi(best_test.MAE,2)}). Vẫn không đổi phương pháp theo bảng test; các đối chứng được hiển thị sau khi cấu hình đã khóa.",
            "Test chỉ có ba tháng/Market, có phụ thuộc thời gian. Chưa đủ để khẳng định ưu thế ổn định, kiểm định mù mới hoặc xác suất chính xác 95%.",
        ],
        '05_future':[
            f"Sau lựa chọn, cập nhật {LABELS[s['selected']]} bằng lịch sử đến 12/2013 để tạo bốn dự báo 01/2014.",
            "Để Actual trống vì nguồn kết thúc 12/2013. Không gán Actual=0, không chấm MAE tương lai, không gọi đây là dự báo hiện tại.",
            "selected_state.json lưu quy tắc/tham số và trạng thái phục vụ tái lập. Phương pháp trung bình trượt không có trọng số học như mạng nơ-ron nên không cần tạo file .pth.",
        ],
        '06_summary':[
            "Đóng góp của bước này: tái lập dữ liệu và protocol, thực thi các đối chứng, kiểm tra chống rò rỉ, phân tích sai số, trình bày bằng bảng/hình và ghi lựa chọn có dấu vết.",
            "Bước sau mới thử thay cửa sổ trung bình hoặc alpha/feature của Ridge. Giữ nguyên bộ cơ sở này làm mốc; mở rộng trên test đã biết phải ghi là thăm dò.",
        ],
    }
    stage_tables={
        '01_input':formatted_table(s['checks']),
        '02_protocol':formatted_table(s['specs'],['Label','Features','Parameters','LearnsCoefficients']),
        '03_validation':formatted_table(leaderboard,['Rank','Phương pháp','N','MAE','RMSE','MAPE','Selected']),
        '04_test':formatted_table(test_summary,['Phương pháp','N','MAE','RMSE','MAPE','Bias'])+ '<h3>Phương pháp đã chọn theo từng Market</h3>'+formatted_table(selected_market,['Market','N','MAE','RMSE','MAPE','Bias']),
        '05_future':formatted_table(s['future'],['Market','ForecastMonth','ModelName','LastActual','Prediction','Actual']),
        '06_summary':formatted_table(presentation,['Stage','Result','Evidence']),
    }
    lines=['# Thử nghiệm cơ sở: dự báo doanh số Coffee Chains','',
           '**Tái lập ba phương pháp cố định; chưa dò tham số mới.** Đọc dữ liệu nguồn, chạy được trước khi Chi bàn giao kho. Kết quả test tham chiếu đã được biết; không mô tả là thử nghiệm mù mới.','',
           '## Đọc nhanh kết quả','',markdown_table(presentation,['Stage','Result']), '']
    sections=[]
    for stage,title in STAGES.items():
        notes=phase_notes[stage]
        lines += [f'## {title}','',*[f'- {note}' for note in notes],'']
        if stage=='03_validation':
            lines += [markdown_table(leaderboard,['Rank','Phương pháp','N','MAE','RMSE','MAPE','Selected']),'']
        elif stage=='04_test':
            lines += [markdown_table(test_summary,['Phương pháp','N','MAE','RMSE','MAPE','Bias']),'',markdown_table(selected_market,['Market','N','MAE','RMSE','MAPE','Bias']),'']
        gallery=''
        for figure in [f for f in figures if f['stage']==stage]:
            path=figure['path']
            lines += [f"### {figure['title']}",'',f"![{figure['title']}]({path}.png)",'',figure['note'],'',f'[PNG 300 dpi]({path}.png) · [PDF]({path}.pdf) · [SVG]({path}.svg)','']
            gallery+=f'<figure><img src="{path}.png" alt="{html.escape(figure["title"])}" loading="lazy"><figcaption>{html.escape(figure["note"])}<br><a href="{path}.pdf">PDF vector</a> · <a href="{path}.svg">SVG</a></figcaption></figure>'
        csvs=sorted((output/stage).glob('*.csv'))
        links=' · '.join(f'<a href="{stage}/{p.name}">{p.name}</a>' for p in csvs)
        sections.append(f'<section id="{stage}"><h2>{title}</h2><ul>'+''.join(f'<li>{html.escape(n)}</li>' for n in notes)+'</ul>'+stage_tables[stage]+f'<p class="files">Bảng gốc: {links}</p>'+gallery+'</section>')
    lines += ['## Tái lập','', '```powershell','.\\.venv\\Scripts\\python experiments/baseline/run.py','```','',
              'Các CSV giữ số liệu chưa làm tròn. PNG 300 dpi để chèn Word; PDF/SVG vector để phóng to. Không sửa Coffee.csv, không ghi kho hoặc tự cập nhật dashboard từ bước này.']
    (output/'analysis.md').write_text('\n'.join(lines),encoding='utf-8')
    selection_note='# Lựa chọn đã lưu trước pha test\n\n'+ '\n\n'.join(phase_notes['03_validation'])+'\n\nXem selection.json và 06_summary/execution_events.csv. Test tham chiếu đã biết trước; đây là dấu vết thứ tự thực thi, không phải tuyên bố thử nghiệm mù.\n'
    (output/'03_validation'/'decision.md').write_text(selection_note,encoding='utf-8')
    slides=['# Gợi ý thuyết trình từ các kết quả đã chạy','',
            '| Trang/hình | Điều cần nói |','| --- | --- |',
            '| 01_input/figures/01_data_flow | Nguồn có 4.248 dòng nhưng chỉ 24 tháng mỗi thị trường; nhóm dự báo theo tháng. |',
            '| 02_protocol/figures/01_rolling_origin | Mỗi lần chỉ dùng các tháng đã xảy ra; 6 tháng lựa chọn, 3 tháng kiểm tra. |',
            '| 03_validation/figures/01_validation_mae | Nhóm thử ba cách trên cùng 24 dự báo validation và lưu lựa chọn theo MAE. |',
            '| 04_test/figures/01_actual_forecast + 03_selected_error_heatmap | Xem các ca bám tốt và ca lệch; báo cả điểm hạn chế. |',
            '| 04_test/figures/05_improvement_vs_naive | Phương pháp chọn chưa thắng mọi chỉ số; kết luận dựa trên bằng chứng. |',
            '| 05_future/figures/01_next_month | Có thể đưa bốn dự báo lên ứng dụng, nhưng chưa có actual 01/2014 để chấm. |','',
            '## Đoạn tóm tắt khoảng một phút','',
            f'Nhóm tổng hợp dữ liệu nguồn thành 96 ô tháng–thị trường và so sánh ba phương pháp dự báo. Mỗi lần dự báo chỉ dùng lịch sử đã xảy ra. Trên 24 dự báo validation, {LABELS[s["selected"]]} được chọn với MAE {vi(val.MAE,2)}. Khi kiểm tra ở ba tháng tiếp theo, MAE là {vi(test.MAE,2)} và RMSE là {vi(test.RMSE,2)}. Kết quả không thắng mọi chỉ số, nên nhóm trình bày cả các tháng lệch và giới hạn số mẫu. Sau đó nhóm cập nhật phương pháp đã chọn để dự báo 01/2014; đây là tháng chưa có số thực tế trong nguồn.','',
            'Đây là gợi ý lời nói dựa trên kết quả thực, không phải phản hồi UX hoặc bằng chứng triển khai SQL Server.']
    (output/'presentation.md').write_text('\n'.join(slides),encoding='utf-8')
    nav=''.join(f'<a href="#{stage}">{title}</a>' for stage,title in STAGES.items())
    page='''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Coffee · Thử nghiệm cơ sở</title><style>
    body{margin:0;background:#f0f4f8;color:#18324e;font:20px/1.65 'Times New Roman',Times,serif}main{max-width:1200px;margin:auto;padding:35px 30px}header{padding:30px;background:#183b62;color:white;border-radius:12px}h1{font-size:38px;margin:8px 0}h2{font-size:29px;color:#183b62}h3{font-size:23px}nav{display:flex;flex-wrap:wrap;gap:10px 20px;padding:20px 0}a{color:#1d5b83}section{padding-top:18px;margin-top:25px}li{margin:9px 0}figure{margin:26px 0;padding:16px;background:white;border:1px solid #c1cddd;border-radius:10px}img{width:100%;height:auto}figcaption{font-size:18px;margin-top:10px}table{border-collapse:collapse;width:100%;background:white;font-size:17px}th,td{border:1px solid #c1cddd;padding:9px;text-align:left}th{background:#dfe9f3}.note{background:#e2ebf5;border-left:4px solid #285d89;padding:17px 22px}.files{font-size:17px;overflow-wrap:anywhere}.metrics{display:flex;gap:35px;flex-wrap:wrap}.metrics strong{font-size:30px}@media print{body{background:white}main{padding:0}figure{break-inside:avoid}nav{display:none}}
    </style><main><header><div>COFFEE CHAINS · BASELINE STUDY</div><h1>Thử ba cách dự báo, chọn bằng kết quả</h1><p>Trang · từ dữ liệu nguồn đến kết quả có thể kiểm chứng</p><div class="metrics">__METRICS__</div></header><nav>__NAV__</nav><div class="note">Thử nghiệm cơ sở, chưa dò tham số. Kết quả test tham chiếu đã biết trước; lựa chọn trong lượt chạy được lưu trước khi tính test. Chưa cần kho của Chi; chưa nghiệm thu native hoặc UX.</div>__SECTIONS__<section><h2>Tệp nên mở tiếp</h2><p><a href="analysis.md">Phân tích Markdown</a> · <a href="presentation.md">Gợi ý thuyết trình</a> · <a href="manifest.json">Manifest / checksum</a> · <a href="03_validation/selection.json">Lựa chọn đã lưu</a></p></section></main></html>'''
    metrics=f'<div><strong>{LABELS[s["selected"]]}</strong><br>chọn trên validation</div><div><strong>{vi(val.MAE,2)}</strong><br>MAE validation · N = 24</div><div><strong>{vi(test.MAE,2)}</strong><br>MAE test · N = 12</div>'
    (output/'report.html').write_text(page.replace('__METRICS__',metrics).replace('__NAV__',nav).replace('__SECTIONS__',''.join(sections)),encoding='utf-8')
