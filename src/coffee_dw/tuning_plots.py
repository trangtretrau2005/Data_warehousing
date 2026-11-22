"""Report figures for the seven-configuration study, exported at 300 dpi."""

import textwrap

import matplotlib.dates as mdates
from matplotlib import pyplot as plt, patches
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

from coffee_dw.exploration import vi
from coffee_dw.exploration_plots import (
    configure, frame as base_frame, finish, numeric_axis,
    NAVY, TEAL, GOLD, ROSE, INK, MUTED, GRID, REVENUE_CMAP,
)
from coffee_dw.tuning_study import CANDIDATES, BY_KEY, LABELS

FAMILY_COLORS = {"Naive": "#7D8FA4", "MA": TEAL, "Ridge": ROSE}
MARKETS = ["Central", "East", "South", "West"]


def frame(*args, **kwargs):
    fig, axes = base_frame(*args, **kwargs)
    fig.texts[0].set_text("COFFEE CHAINS  /  HYPERPARAMETER STUDY")
    return fig, axes


def save(fig, output, stage, name, title, note):
    result = finish(fig, output/stage/"figures", name, title, note)
    return result | {"stage": stage, "path": f"{stage}/figures/{name}"}


def table_figure(title, subtitle, headers, rows, widths, output, stage, name, note, *, height=8.2):
    fig, axes = frame(title, subtitle, size=(12.2, height), bottom=.13, top=.76)
    axis = axes[0, 0]
    axis.set_axis_off()
    table = axis.table(cellText=rows, colLabels=headers, colWidths=widths,
                       loc="center", cellLoc="left", colLoc="left", bbox=[0, 0, 1, 1])
    table.auto_set_font_size(False)
    table.set_fontsize(14)
    for (row, _), cell in table.get_celld().items():
        cell.set_edgecolor("#C1CEDA")
        cell.PAD = .045
        cell.set_facecolor(NAVY if row == 0 else "#EEF4F8" if row % 2 else "white")
        cell.get_text().set_color("white" if row == 0 else INK)
        if row == 0:
            cell.get_text().set_weight("bold")
    return save(fig, output, stage, name, title, note)


def configurations(s, output):
    rows = []
    for c in CANDIDATES:
        rows.append([c.label, "Không có" if c.family == "Naive" else f"Cửa sổ = {c.window}" if c.family == "MA" else f"alpha = {vi(c.alpha,1)}",
                     "Không học hệ số" if c.family != "Ridge" else "3 hệ số + intercept",
                     "Tháng trước" if c.family == "Naive" else f"{c.window} tháng gần nhất" if c.family == "MA" else "lag1, lag2, lag3"])
    return table_figure("Bảy cấu hình được thử đầy đủ", "Phân biệt siêu tham số đặt trước và tham số học từ lịch sử",
        ["Cấu hình", "Siêu tham số thử", "Tham số học", "Dữ liệu đầu vào"], rows, [.25,.23,.28,.24],
        output, "01_protocol", "01_configurations", "Ridge fit scaler trên quá khứ; Naive/MA là quy tắc, không có epoch.")


def protocol(s, output):
    title = "Cùng dữ liệu, cùng lịch thử, cùng tiêu chí chọn"
    fig, axes = frame(title, "Dự báo từng tháng bằng lịch sử mở rộng · không chia ngẫu nhiên", size=(11.2,6.5), top=.73, bottom=.17)
    axis = axes[0,0]
    axis.set_axis_off()
    cards = [("15 tháng", "Lịch sử ban đầu", "01/2012 – 03/2013", NAVY),
             ("6 tháng", "Chọn cấu hình", "04/2013 – 09/2013", TEAL),
             ("3 tháng", "Kiểm tra mô tả", "10/2013 – 12/2013", ROSE)]
    for i, (number, label, period, color) in enumerate(cards):
        x = i/3+.012
        axis.add_patch(patches.FancyBboxPatch((x,.35),.30,.60,boxstyle="round,pad=.01", facecolor="#EFF4F8",edgecolor=color,transform=axis.transAxes))
        axis.text(x+.15,.77,number,color=color,fontsize=26,weight="bold",ha="center",transform=axis.transAxes)
        axis.text(x+.15,.59,label,fontsize=17,ha="center",transform=axis.transAxes)
        axis.text(x+.15,.43,period,fontsize=14,ha="center",transform=axis.transAxes)
    axis.text(.5,.12,"Chọn theo MAE validation → lưu lựa chọn → mới tính test",ha="center",fontsize=17,color=TEAL,transform=axis.transAxes)
    return save(fig,output,"01_protocol","02_protocol",title,"Test đã được xem từ bước trước; đây là thử nghiệm mở rộng.")


def validation_ranking(s, output):
    title = "Cấu hình nào dự báo tốt nhất trên validation?"
    fig, axes = frame(title, "MAE gộp bốn thị trường · N = 24 / cấu hình · thấp hơn tốt hơn", size=(11.2,7.8), bottom=.16, top=.77)
    axis = axes[0,0]
    board = s["leaderboard"]
    colors = [TEAL if key == s["selected"] else "#9EB4C9" for key in board.ModelName]
    bars = axis.barh(range(len(board)), board.MAE, color=colors, height=.65, zorder=3)
    axis.set_yticks(range(len(board)), [LABELS[key] for key in board.ModelName])
    axis.invert_yaxis()
    for bar, value in zip(bars, board.MAE):
        axis.text(value+4,bar.get_y()+bar.get_height()/2,vi(value,2),va="center",fontsize=15)
    axis.set_xlim(0,board.MAE.max()*1.22)
    axis.set_xlabel("MAE · đơn vị Sales")
    numeric_axis(axis,which="x")
    return save(fig,output,"02_validation","01_ranking",title,"Tính thứ hạng bằng số chưa làm tròn; không dùng test để đổi lựa chọn.")


def moving_average_curve(s, output):
    title = "Lấy trung bình bao nhiêu tháng là phù hợp?"
    fig, axes = frame(title,"Chỉ thay cửa sổ 2, 3, 6 tháng; giữ nguyên các tháng chấm điểm",size=(11.2,6.9),bottom=.25)
    axis = axes[0,0]
    board = s["leaderboard"].set_index("ModelName")
    x, y = [2,3,6], [board.loc[f"ma_w{w}","MAE"] for w in [2,3,6]]
    axis.plot(x,y,"o-",color=TEAL,lw=2.6,ms=9,label="MAE validation")
    for window, value in zip(x,y):
        axis.annotate(vi(value,2),(window,value),xytext=(0,13),textcoords="offset points",ha="center",fontsize=16)
    axis.axhline(board.loc["naive_last","MAE"],ls="--",color=MUTED,label="Naive")
    axis.set_xticks(x)
    axis.set_xlabel("Số tháng lấy trung bình")
    axis.set_ylabel("MAE · đơn vị Sales")
    axis.set_ylim(min(y)*.90,board.loc["naive_last","MAE"]*1.14)
    numeric_axis(axis)
    handles,labels=axis.get_legend_handles_labels()
    fig.legend(handles,labels,frameon=False,loc="lower center",bbox_to_anchor=(.5,.085),ncol=2)
    return save(fig,output,"02_validation","02_ma_window",title,"Không có quy luật cửa sổ càng dài càng tốt; chọn bằng validation.")


def ridge_curve(s, output):
    title = "Tăng alpha có giúp Ridge dự báo tốt hơn?"
    fig, axes = frame(title,"Giữ lag1/2/3 và StandardScaler; chỉ thay alpha · N = 24 validation",size=(11.2,7.2),bottom=.30)
    axis = axes[0,0]
    keys = ["ridge_a0p1","ridge_a1","ridge_a10"]
    board = s["leaderboard"].set_index("ModelName")
    train = s["validation_origins"].groupby("ModelName").InSampleMAE.mean()
    x = [.1,1,10]
    axis.plot(x,[board.loc[k,"MAE"] for k in keys],"o-",color=ROSE,lw=2.5,ms=8,label="MAE validation")
    axis.plot(x,[train.loc[k] for k in keys],"s--",color=NAVY,lw=1.8,ms=7,label="MAE fit: trung bình 24 lần fit")
    axis.axhline(board.loc[s["selected"],"MAE"],color=TEAL,ls=":",label="Cấu hình được chọn")
    for alpha,key in zip(x,keys):
        axis.annotate(vi(board.loc[key,"MAE"],2),(alpha,board.loc[key,"MAE"]),xytext=(0,12),textcoords="offset points",ha="center",fontsize=15)
    axis.set_xscale("log")
    axis.set_xticks(x,["0,1","1","10"])
    axis.set_xlabel("Alpha · thang log")
    axis.set_ylabel("MAE · đơn vị Sales")
    numeric_axis(axis)
    low,high=axis.get_ylim();axis.set_ylim(low*.95,high*1.12)
    handles,labels=axis.get_legend_handles_labels()
    fig.legend(handles,labels,frameon=False,loc="lower center",bbox_to_anchor=(.5,.085),fontsize=12.5,ncol=2)
    return save(fig,output,"02_validation","03_ridge_alpha",title,"MAE fit là sai số trên mẫu học; số mẫu khác validation, không dùng để chọn.")


def market_heatmap(s, output):
    title = "Cấu hình thắng chung có thắng ở từng thị trường?"
    fig, axes = frame(title,"MAE validation · N = 6 / ô · màu đậm biểu thị sai số lớn",size=(11.2,8.1),top=.77,bottom=.15)
    axis=axes[0,0]
    keys=s["leaderboard"].ModelName.tolist()
    grid=s["validation_metrics"].loc[lambda x:~x.Market.eq("ALL")].pivot(index="ModelName",columns="Market",values="MAE").loc[keys,MARKETS]
    image=axis.imshow(grid,cmap=REVENUE_CMAP,aspect="auto")
    axis.set_yticks(range(len(keys)),[LABELS[k] for k in keys])
    axis.set_xticks(range(4),MARKETS)
    for i in range(len(keys)):
        for j in range(4):
            value=grid.iloc[i,j]
            axis.text(j,i,vi(value,1),ha="center",va="center",fontsize=14,color="white" if value>grid.to_numpy().max()*.65 else INK)
    fig.colorbar(image,ax=axis,fraction=.035,pad=.03).set_label("MAE · Sales")
    return save(fig,output,"02_validation","04_market_heatmap",title,"Chọn một cấu hình chung; không đổi riêng từng Market sau khi nhìn test.")


def sensitivity(s, output):
    rows=[[row.OmittedValidationMonth.strftime("%m/%Y"),LABELS[row.Winner],vi(row.MAE,2),str(row.N)] for row in s["stability"].itertuples()]
    return table_figure("Lựa chọn có phụ thuộc vào một tháng chấm điểm?",
        "Bỏ từng tháng khỏi bảng chấm validation, giữ nguyên các dự báo đã tạo",
        ["Tháng bỏ khỏi điểm", "Cấu hình đứng đầu", "MAE còn lại", "N"],rows,[.29,.35,.24,.12],
        output,"02_validation","05_sensitivity","Chỉ mô tả độ nhạy; không phải sáu tập kiểm định độc lập và không dùng chọn lại.")


def actual_forecast(s, output):
    title="Mô hình được chọn bám thực tế như thế nào?"
    fig,axes=frame(title,f"10–12/2013 · {LABELS[s['selected']]} và Naive · thang Y riêng mỗi ô",rows=2,columns=2,size=(12.2,9.8),top=.76,bottom=.19,hspace=.62)
    for axis,market in zip(axes.flat,MARKETS):
        scope=s["test"].loc[s["test"].Market.eq(market)]
        chosen=scope.loc[scope.ModelName.eq(s["selected"])].sort_values("ForecastMonth")
        axis.plot(chosen.ForecastMonth,chosen.Actual,"o-",color=NAVY,label="Thực tế",lw=2.4)
        axis.plot(chosen.ForecastMonth,chosen.Prediction,"s--",color=TEAL,label="Được chọn",lw=2.2)
        naive=scope.loc[scope.ModelName.eq("naive_last")].sort_values("ForecastMonth")
        axis.plot(naive.ForecastMonth,naive.Prediction,"^:",color=GOLD,label="Naive",lw=1.8)
        axis.set_title(f"{market} · N = 3",loc="left",fontsize=18)
        axis.set_xticks(chosen.ForecastMonth)
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
        axis.set_ylabel("Sales")
        numeric_axis(axis)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc="lower center",bbox_to_anchor=(.5,.075),ncol=3,frameon=False)
    return save(fig,output,"03_test","01_actual_forecast",title,"Test đã biết từ bước trước; mỗi dự báo chỉ dùng lịch sử trước tháng mục tiêu.")


def test_metrics(s, output):
    title="Công bố kết quả test của cả bảy cấu hình"
    fig,axes=frame(title,"Thứ tự giữ theo validation; không chọn lại bằng test · N = 12 / cấu hình",rows=1,columns=2,size=(13,8.1),top=.76,bottom=.15,wspace=.60)
    keys=s["leaderboard"].ModelName.tolist()
    table=s["test_metrics"].loc[lambda x:x.Market.eq("ALL")].set_index("ModelName")
    for axis,metric in zip(axes.flat,["MAE","RMSE"]):
        values=table.loc[keys,metric]
        bars=axis.barh(range(7),values,color=[TEAL if k==s["selected"] else "#9EB4C9" for k in keys],height=.65,zorder=3)
        axis.set_yticks(range(7),[LABELS[k] for k in keys],fontsize=12)
        axis.invert_yaxis()
        axis.set_title(metric,loc="left",fontsize=18)
        for bar,value in zip(bars,values):
            axis.text(value+3,bar.get_y()+bar.get_height()/2,vi(value,1),va="center",fontsize=12)
        axis.set_xlim(0,values.max()*1.25)
        axis.set_xlabel("Đơn vị Sales")
        numeric_axis(axis,which="x")
    return save(fig,output,"03_test","02_all_metrics",title,"Màu xanh: cấu hình đã được chọn bằng validation; không phải người thắng test.")


def selected_errors(s, output):
    title="Dự báo lệch ở tháng nào, theo hướng nào?"
    fig,axes=frame(title,"Sai số = dự báo − thực tế · dương: cao hơn · âm: thấp hơn",size=(11.2,6.7),top=.76,bottom=.16)
    axis=axes[0,0]
    part=s["errors"].loc[lambda x:x.ModelName.eq(s["selected"]) & x.Split.eq("test")]
    grid=part.pivot(index="Market",columns="ForecastMonth",values="Error").loc[MARKETS]
    lim=max(1,float(np.abs(grid).to_numpy().max()))
    image=axis.imshow(grid,cmap="RdBu_r",norm=TwoSlopeNorm(0,-lim,lim),aspect="auto")
    axis.set_yticks(range(4),MARKETS)
    axis.set_xticks(range(3),[d.strftime("%m/%Y") for d in grid.columns])
    for i in range(4):
        for j in range(3):
            value=grid.iloc[i,j]
            axis.text(j,i,("+" if value>0 else "")+vi(value,1),ha="center",va="center",fontsize=16,color="white" if abs(value)>lim*.6 else INK)
    fig.colorbar(image,ax=axis,fraction=.035,pad=.03).set_label("Sai số · Sales")
    return save(fig,output,"03_test","03_selected_errors",title,"12 trường hợp; không suy nguyên nhân khuyến mãi/thời tiết từ biểu đồ này.")


def before_after(s, output):
    title="Thử thêm tham số có cải thiện mốc cơ sở không?"
    fig,axes=frame(title,"So cùng tiêu chí MAE, cùng các tháng đánh giá",size=(11.2,6.9),top=.76,bottom=.23)
    axis=axes[0,0]
    refs=[("naive_last","Naive",GOLD),(s["decision"]["previous_baseline_selected"],"Chọn ở bước cơ sở",NAVY),(s["selected"],"Chọn sau thử tham số",TEAL)]
    for i,(key,label,color) in enumerate(refs):
        values=[s["pooled"].loc[lambda x:x.ModelName.eq(key)&x.Split.eq(split),"MAE"].iloc[0] for split in ["validation","test"]]
        bars=axis.bar(np.arange(2)+(i-1)*.24,values,width=.22,color=color,label=label,zorder=3)
        for bar,value in zip(bars,values):
            axis.text(bar.get_x()+bar.get_width()/2,value+4,vi(value,2),ha="center",fontsize=12)
    axis.set_xticks([0,1],["Validation · N = 24","Test đã biết · N = 12"])
    axis.set_ylabel("MAE · đơn vị Sales")
    numeric_axis(axis)
    axis.set_ylim(0,axis.get_ylim()[1]*1.13)
    axis.legend(frameon=False,loc="upper center",bbox_to_anchor=(.5,-.17),ncol=3,fontsize=12)
    return save(fig,output,"04_comparison","01_before_after",title,"Không cải thiện vẫn là kết quả: cấu hình cơ sở giữ vị trí tốt nhất trong lưới thử.")


def coefficients(s, output):
    title="Ridge đã học những hệ số nào từ dữ liệu?"
    fig,axes=frame(title,"Các mô hình Ridge đối chứng fit đến 12/2013 · hệ số trên Sales gốc",rows=2,columns=2,size=(12.2,9.3),top=.76,bottom=.20,hspace=.56)
    keys=["ridge_a0p1","ridge_a1","ridge_a10"]
    for axis,market in zip(axes.flat,MARKETS):
        table=s["final_parameters"].loc[lambda x:x.Market.eq(market)].pivot(index="Feature",columns="ModelName",values="CoefficientRaw")
        for i,key in enumerate(keys):
            axis.bar(np.arange(3)+(i-1)*.24,table.loc[["lag1","lag2","lag3"],key],width=.22,label=LABELS[key],color=["#B8C9D8",NAVY,ROSE][i])
        axis.axhline(0,color=MUTED,lw=.8)
        axis.set_xticks(range(3),["lag1","lag2","lag3"])
        axis.set_title(market,loc="left",fontsize=18)
        axis.set_ylabel("Hệ số hồi quy")
        axis.grid(axis="y",color=GRID,lw=.6)
        axis.set_axisbelow(True)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc="lower center",bbox_to_anchor=(.5,.075),ncol=3,frameon=False,fontsize=13)
    return save(fig,output,"05_models","01_coefficients",title,"Các Ridge không được chọn; hệ số không phải tác động nhân quả hoặc % đóng góp.")


def future(s, output):
    title="Bốn dự báo để chuẩn bị đưa vào ứng dụng"
    fig,axes=frame(title,f"01/2014 · {LABELS[s['selected']]} · cập nhật từ lịch sử đến 12/2013",size=(11.2,7),top=.77,bottom=.22)
    axis=axes[0,0]
    part=s["future"].loc[lambda x:x.Selected].set_index("Market").loc[MARKETS]
    axis.bar(np.arange(4)-.17,part.LastActual,width=.31,color="#B7C9D9",label="Thực tế 12/2013",zorder=3)
    bars=axis.bar(np.arange(4)+.17,part.Prediction,width=.31,color=TEAL,label="Dự báo 01/2014",zorder=3)
    for bar,value in zip(bars,part.Prediction):
        axis.text(bar.get_x()+bar.get_width()/2,value+110,vi(value,1),ha="center",fontsize=14)
    axis.set_xticks(range(4),MARKETS)
    axis.set_ylabel("Sales · đơn vị nguồn")
    numeric_axis(axis)
    axis.set_ylim(0,max(part.LastActual.max(),part.Prediction.max())*1.17)
    axis.legend(loc="upper center",bbox_to_anchor=(.5,-.16),ncol=2,frameon=False)
    return save(fig,output,"05_models","02_next_month",title,"Chưa có actual 01/2014; chưa chấm sai số, không phải dự báo cho hiện tại.")


def summary(s, output):
    from coffee_dw.tuning_report import presentation_summary
    rows=[[textwrap.fill(str(r.Step),19),textwrap.fill(str(r.Result),64)] for r in presentation_summary(s).itertuples()]
    return table_figure("Kết quả thử tham số trên một trang", "Đưa vào báo cáo cùng biểu đồ cửa sổ, alpha và thực tế – dự báo",
        ["Bước", "Kết quả cần trình bày"],rows,[.23,.77],output,"06_summary","01_summary",
        "Thử đủ lưới đã công bố; kết luận có giới hạn, không ép mô hình phức tạp thắng.",height=9.5)


def render_figures(study, output):
    configure()
    return [draw(study,output) for draw in [configurations,protocol,validation_ranking,moving_average_curve,
        ridge_curve,market_heatmap,sensitivity,actual_forecast,test_metrics,selected_errors,before_after,coefficients,future,summary]]
