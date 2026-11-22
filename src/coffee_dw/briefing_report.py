"""Saved visual evidence for the research-to-presentation integration step."""

import html
import textwrap

import matplotlib.dates as mdates
from matplotlib import pyplot as plt, patches
import numpy as np
import pandas as pd

from coffee_dw.exploration import vi
from coffee_dw.exploration_plots import configure, frame as base_frame, finish, numeric_axis, NAVY, TEAL, GOLD, MUTED, INK
from coffee_dw.briefing import case_markdown


def frame(*args,**kwargs):
    fig,axes=base_frame(*args,**kwargs)
    fig.texts[0].set_text("COFFEE CHAINS  /  RESEARCH TO BRIEFING")
    return fig,axes


def save(fig,output,stage,name,title,note):
    result=finish(fig,output/stage/"figures",name,title,note)
    return result|{"stage":stage,"path":f"{stage}/figures/{name}"}


def reconciliation_figure(table,output):
    title="Đầu vào nghiên cứu đã khớp dữ liệu phục vụ"
    fig,axes=frame(title,"96 ô Market–tháng · nguồn nghiên cứu và kho SQLite tham chiếu",size=(11.2,6.6),top=.76,bottom=.17)
    axis=axes[0,0];axis.set_axis_off()
    rows=[]
    for market,part in table.groupby("Market",sort=True):
        rows.append([market,str(len(part)),vi(part.SalesResearch.sum()),vi(part.SalesWarehouse.sum()),vi(part.Difference.abs().max(),4),"Đạt" if part.Pass.all() else "Lỗi"])
    chart=axis.table(cellText=rows,colLabels=["Market","Số kỳ","Sales nghiên cứu","Sales kho","Lệch lớn nhất","Đối soát"],
                     bbox=[0,.05,1,.88],cellLoc="left",colLoc="left",colWidths=[.13,.10,.23,.23,.19,.12])
    chart.auto_set_font_size(False);chart.set_fontsize(14)
    for (row,col),cell in chart.get_celld().items():
        cell.set_edgecolor("#c0cedc");cell.set_facecolor(NAVY if row==0 else "#eef4f8" if row%2 else "white")
        cell.get_text().set_color("white" if row==0 else INK);cell.PAD=.05
    return save(fig,output,"01_reconciliation","01_reconciliation",title,"Đây là đối soát SQLite; chưa phải nghiệm thu SSIS/SSAS hay mart native của Chi.")


def story_figure(output):
    title="Một mạch trình bày từ dự báo đến kiểm chứng"
    fig,axes=frame(title,"Bấm nghe ba phần liền nhau; biểu đồ đổi theo phần đang thuyết minh",size=(11.2,6.4),top=.74,bottom=.16)
    axis=axes[0,0];axis.set_axis_off()
    cards=[("01","Tháng tới dự kiến gì?","Lịch sử → điểm dự báo",NAVY),
           ("02","Con số được tính ra sao?","Ba tháng → chia trung bình",TEAL),
           ("03","Đã từng dự báo ra sao?","Sáu kỳ validation → sai số",GOLD)]
    for index,(number,title_card,note,color) in enumerate(cards):
        x=index/3+.008
        axis.add_patch(patches.FancyBboxPatch((x,.30),.30,.66,boxstyle="round,pad=.01",facecolor="#edf3f8",edgecolor=color,transform=axis.transAxes))
        axis.text(x+.15,.78,number,color=color,fontsize=29,weight="bold",ha="center",transform=axis.transAxes)
        axis.text(x+.15,.57,textwrap.fill(title_card,21),ha="center",va="center",fontsize=16,transform=axis.transAxes)
        axis.text(x+.15,.35,textwrap.fill(note,25),ha="center",fontsize=13,transform=axis.transAxes)
    axis.text(.5,.08,"Số thực tế tháng đích chỉ hiện khi người xem chủ động mở",ha="center",fontsize=16,color=TEAL,transform=axis.transAxes)
    return save(fig,output,"02_story","01_story_flow",title,"Thuyết minh theo mẫu có giới hạn; không suy diễn nguyên nhân kinh doanh.")


def case_figure(case,output):
    target=pd.Timestamp(case["forecast_month"])
    title=f"{case['market']} · Báo cáo dự báo {target:%m/%Y}"
    fig,axes=frame(title,f"MA3 đã chọn · dữ liệu đến {pd.Timestamp(case['train_end']):%m/%Y} · thang Y riêng từng biểu đồ",rows=2,columns=2,
                   size=(12.8,10.7),top=.78,bottom=.15,hspace=.68,wspace=.35)
    a,b,c,d=axes.flat
    recent=case["history"][-9:]
    x=pd.to_datetime([r["month"] for r in recent]);y=[r["sales"] for r in recent]
    a.plot(x,y,"o-",color=NAVY,lw=2.2,ms=4)
    a.plot([x[-1],target],[y[-1],case["prediction"]],"o--",color=GOLD,lw=2,ms=6)
    a.set_title("01 · Nhìn sang tháng kế tiếp",loc="left",fontsize=17)
    a.xaxis.set_major_locator(mdates.MonthLocator(interval=3));a.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"));a.set_ylabel("Sales")
    numeric_axis(a)
    inputs=case["story"]["inputs"]
    bars=b.bar(range(3),[r["sales"] for r in inputs],color=["#a8bfd4","#638eb5",NAVY],width=.55,zorder=3)
    b.axhline(case["prediction"],color=GOLD,ls="--",lw=2)
    for bar,row in zip(bars,inputs):
        label_y=max(row["sales"]+max(r["sales"] for r in inputs)*.03,case["prediction"]+max(r["sales"] for r in inputs)*.05)
        b.text(bar.get_x()+bar.get_width()/2,label_y,vi(row["sales"]),ha="center",fontsize=12)
    b.set_xticks(range(3),[pd.Timestamp(r["month"]).strftime("%m/%y") for r in inputs]);b.set_ylim(0,max(r["sales"] for r in inputs)*1.2)
    b.set_title("02 · Ba tháng, trọng số bằng nhau",loc="left",fontsize=17);b.set_ylabel("Sales");numeric_axis(b)
    h=case["story"]["validation_history"]
    dates=pd.to_datetime([r["month"] for r in h])
    c.plot(dates,[r["actual"] for r in h],"o-",color=NAVY,lw=2,label="Thực tế validation",ms=4)
    c.plot(dates,[r["prediction"] for r in h],"s--",color=TEAL,lw=2,label="Dự báo validation",ms=4)
    c.set_title("03 · Sáu kỳ đã kiểm chứng",loc="left",fontsize=17)
    c.set_xticks(dates[::2]);c.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"));c.set_ylabel("Sales");numeric_axis(c)
    c.legend(fontsize=11,frameon=False,loc="upper center",bbox_to_anchor=(.5,-.22),ncol=2)
    d.set_axis_off()
    delta=case["prediction"]-case["last_actual"]
    text=[f"Dự báo: {vi(case['prediction'],2)}",f"So tháng gần nhất: {'+' if delta>=0 else '−'}{vi(abs(delta),2)}",
          f"MAE validation: {vi(case['validation_market']['MAE'],2)} · N = 6", "",
          case["story"]["formula"], "",
          "Actual tháng đích: chưa có trong nguồn." if case["actual"] is None else "Actual tháng đích được mở riêng khi kiểm chứng.",
          "Sai số lịch sử không phải khoảng dự báo."]
    d.text(.02,.96,"Các điểm cần trình bày",weight="bold",fontsize=18,color=NAVY,va="top",transform=d.transAxes)
    d.text(.02,.79,"\n".join(textwrap.fill(line,49) for line in text),fontsize=15,linespacing=1.65,va="top",transform=d.transAxes)
    return save(fig,output,"02_story",case["id"],title,"Hình xuất báo cáo từ dữ liệu; không phải ảnh chụp nghiệm thu giao diện hoặc chất giọng.")


def write_reports(bundle,tables,output,*,render=True):
    selected=[case for case in bundle["cases"] if case["story"]["is_selected"]]
    figures=[]
    if render:
        configure()
        figures=[reconciliation_figure(tables["01_reconciliation/monthly_reconciliation"],output),story_figure(output)]
        figures.extend(case_figure(case,output) for case in selected)
    lines=["# Bước tích hợp nghiên cứu vào thuyết trình", "",
        "Đã nối kết quả 7 cấu hình với 48 case của demo, trong đó 16 case MA3 được chọn có công thức trực tiếp, bằng chứng validation và lời thuyết trình mới.","",
        "## Bước 1 — kiểm tra đầu vào","",
        "96 ô Market–tháng khớp nguồn nghiên cứu với kho SQLite tham chiếu. Tổng Sales 819811. Đây chưa phải bàn giao native của Chi.","",
        "## Bước 2 — giải thích đúng bộ lọc","",
        "Mỗi Market/tháng có ba phần: dự kiến → ba tháng tạo dự báo → sáu kỳ validation. Các trường hợp đối chứng giữ phân rã mô hình. Mọi đầu vào và bằng chứng validation có trước tháng mục tiêu.","",
        "## Bước 3 — công bố vào demo","",
        "MA3 làm mặc định; có bảng bảy cấu hình và quyết định lựa chọn. Bấm nghe để chuyển ba phần theo sự kiện kết thúc âm thanh, hoặc tự chuyển phần. Actual tháng đích không tự hiện. Có tải báo cáo Markdown và bảng validation theo bộ lọc.","",
        "## Các case được chọn","",
        "| Market | Tháng | Dự báo | Hồ sơ / lời đọc | Hình báo cáo |", "| --- | --- | --- | --- | --- |"]
    items=[]
    for case in selected:
        name=case["id"]
        lines.append(f"| {case['market']} | {pd.Timestamp(case['forecast_month']):%m/%Y} | {vi(case['prediction'],2)} | [Markdown](02_story/cases/{name}.md) | [PNG](02_story/figures/{name}.png) |")
        items.append(f"<article><h3>{case['market']} · {pd.Timestamp(case['forecast_month']):%m/%Y}</h3><p>{html.escape(case['story']['formula'])}</p>"+
            f"<a href='02_story/cases/{name}.md'>Hồ sơ / lời thuyết trình</a> · <a href='02_story/cases/{name}.json'>JSON</a>"+
            (f"<figure><img src='02_story/figures/{name}.png' loading='lazy' alt='Ba bước dự báo {case['market']}'></figure>" if render else "")+"</article>")
    lines += ["", "## Giới hạn và bước tiếp theo","",
        "- Đây là diễn giải cơ chế MA3; không tạo mô hình mới hoặc nguyên nhân kinh doanh giả.",
        "- Test đã được xem; vòng tuning là thăm dò. Bằng chứng origin chỉ dùng validation đã kết thúc 09/2013.",
        "- Actual 01/2014 chưa có; không thay bằng 0 hoặc chấm sai số tương lai.",
        "- Công cụ browser host chưa khả dụng trong lượt này. Kiểm tra tự động và hình báo cáo không thay nghiệm thu nghe/nhìn bằng trình duyệt thật.",
        "- Bước tiếp theo: Trang thử giọng/bố cục bằng trình duyệt, đối soát mart của Chi khi bàn giao, rồi lưu phiên nghiệm thu người dùng thật.","",
        "## Tái lập","","```powershell",".\\.venv\\Scripts\\python experiments/briefing/run.py --voice","```",""]
    (output/"analysis.md").write_text("\n".join(lines),encoding="utf-8")
    page="""<!doctype html><html lang='vi'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Coffee · Nghiên cứu đến thuyết trình</title><style>
    body{margin:0;background:#f1f5f9;color:#18324e;font:20px/1.65 'Times New Roman',Times,serif}main{max-width:1180px;margin:auto;padding:35px}header{padding:30px;background:#183b62;color:white;border-radius:12px}h1{font-size:38px}h2{font-size:29px}a{color:#1a5f86}article{background:white;border:1px solid #bacbda;border-radius:12px;padding:22px;margin:25px 0}figure{margin:16px 0}img{width:100%;height:auto}.note{background:#e1edf2;border-left:5px solid #207f83;padding:18px;margin:25px 0}
    </style><main><header><div>COFFEE CHAINS · TRANG</div><h1>Từ kết quả thử nghiệm đến bài thuyết trình</h1><p>96 ô dữ liệu đã khớp · 16 báo cáo MA3 theo bộ lọc · 3 phần mỗi bài</p></header><div class='note'>MA3 tiếp tục được chọn sau thử bảy cấu hình. Phần giải thích dùng phép tính trực tiếp; phần kiểm chứng dùng sáu kỳ validation đã biết trước tháng đích. Hình dưới đây là hình báo cáo, chưa phải ảnh nghiệm thu browser.</div><p><a href='analysis.md'>Phân tích</a> · <a href='02_story/steps.csv'>Toàn bộ lời đọc</a> · <a href='01_reconciliation/monthly_reconciliation.csv'>Đối soát 96 ô</a> · <a href='manifest.json'>Manifest</a></p>__ITEMS__</main></html>"""
    (output/"report.html").write_text(page.replace("__ITEMS__","".join(items)),encoding="utf-8")
    return figures
