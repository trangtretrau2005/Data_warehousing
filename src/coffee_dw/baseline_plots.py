"""Publication figures for the fixed baseline study, with readable Vietnamese labels."""

from pathlib import Path
import textwrap

import matplotlib.dates as mdates
from matplotlib import pyplot as plt, patches, ticker
import numpy as np
import pandas as pd

from coffee_dw.baseline_study import LABELS, COLORS, METHODS, MARKETS
from coffee_dw.exploration import vi
from coffee_dw.exploration_plots import configure, frame as eda_frame, finish, numeric_axis, NAVY, TEAL, GOLD, ROSE, INK, MUTED, GRID


def frame(*args,**kwargs):
    fig,axes=eda_frame(*args,**kwargs)
    fig.texts[0].set_text("COFFEE CHAINS  /  BASELINE STUDY")
    return fig,axes


def save(fig,output,stage,name,title,note):
    info=finish(fig,output/stage/"figures",name,title,note)
    info.update(stage=stage,path=f"{stage}/figures/{name}")
    return info


def input_flow(s,output):
    title="Dữ liệu nào thực sự đi vào thử nghiệm?"
    fig,axes=frame(title,"Đọc CSV nguồn qua bộ chuẩn hóa chung; chưa cần kho của Chi",size=(11.2,6.2),bottom=.15)
    axis=axes[0,0];axis.set_axis_off()
    values=[(s['source']['accepted_rows'],"Dòng nguồn hợp lệ"),(len(s['monthly']),"Ô Market–tháng"),(60,"Ô lịch sử ban đầu"),(48,"Mẫu Ridge ban đầu")]
    for i,(number,label) in enumerate(values):
        x=.005+i*.25
        axis.add_patch(patches.FancyBboxPatch((x,.35),.22,.45,boxstyle="round,pad=.01",facecolor="#E7EFF7",edgecolor="#AABFD2",transform=axis.transAxes))
        axis.text(x+.11,.63,vi(number),ha="center",va="center",weight="bold",fontsize=28,color=NAVY,transform=axis.transAxes)
        axis.text(x+.11,.45,textwrap.fill(label,17),ha="center",va="center",fontsize=13.5,transform=axis.transAxes)
        if i<3:
            axis.annotate("",xy=(x+.245,.57),xytext=(x+.225,.57),xycoords="axes fraction",arrowprops={"arrowstyle":"->","color":MUTED,"lw":1.8})
    axis.text(.5,.10,"15 tháng đầu − 3 tháng tạo lag = 12 mẫu học / Market",ha="center",fontsize=17,color=TEAL,transform=axis.transAxes)
    return save(fig,output,"01_input","01_data_flow",title,"Số dòng nguồn không phải số đơn hàng hoặc số mẫu học độc lập.")


def rolling_protocol(s,output):
    title="Mỗi dự báo chỉ sử dụng những tháng đã xảy ra"
    fig,axes=frame(title,"Lịch sử mở rộng · dự báo trước một tháng · không chia ngẫu nhiên",size=(11.2,8.4),bottom=.20,top=.77)
    axis=axes[0,0];months=pd.date_range('2012-01-01','2013-12-01',freq='MS')
    matrix=np.full((9,24),np.nan)
    for row,target in enumerate(range(15,24)):
        matrix[row,:target]=1
        matrix[row,target]=2 if row<6 else 3
    from matplotlib.colors import ListedColormap
    cmap=ListedColormap(['#DDE8F2',GOLD,ROSE]);cmap.set_bad('white')
    axis.imshow(matrix,cmap=cmap,vmin=1,vmax=3,aspect='auto')
    axis.set_yticks(range(9),[f"Dự báo {date:%m/%Y}" for date in months[-9:]],fontsize=13)
    positions=[0,3,6,9,12,15,18,21,23]
    axis.set_xticks(positions,[months[i].strftime('%m/%y') for i in positions],rotation=45,ha='right')
    axis.set_xticks(np.arange(-.5,24,1),minor=True);axis.set_yticks(np.arange(-.5,9,1),minor=True)
    axis.grid(which='minor',color='white',lw=1);axis.tick_params(which='minor',bottom=False,left=False)
    axis.axhline(5.5,color=MUTED,lw=1)
    for row,target in enumerate(range(15,24)):
        axis.text(target,row,'T',ha='center',va='center',fontsize=12,color='white')
    fig.legend(handles=[patches.Patch(color='#DDE8F2',label='Đã biết, được sử dụng'),patches.Patch(color=GOLD,label='Mục tiêu validation'),patches.Patch(color=ROSE,label='Mục tiêu test')],loc='lower center',bbox_to_anchor=(.52,.085),ncol=3,frameon=False,fontsize=12)
    return save(fig,output,"02_protocol","01_rolling_origin",title,"T: tháng cần dự báo; chỉ dùng actual đã xảy ra, giữ nguyên cấu hình qua test.")


def method_cards(s,output):
    title="Ba cách dự báo được đặt lên cùng một bàn cân"
    fig,axes=frame(title,"Không dò tham số ở bước cơ sở; đầu vào chỉ gồm doanh số quá khứ",size=(11.2,7),bottom=.15)
    axis=axes[0,0];axis.set_axis_off()
    cards=[('naive_last','Tháng tới = tháng trước','Dùng lag1\nKhông học hệ số'),
           ('moving_average_3','Lấy trung bình 3 tháng','Dùng lag1, lag2, lag3\nCửa sổ cố định = 3'),
           ('ridge','Học cách kết hợp 3 tháng','Dùng lag1, lag2, lag3\nStandardScaler + alpha = 1')]
    for i,(method,rule,params) in enumerate(cards):
        x=.005+i*.335
        axis.add_patch(patches.FancyBboxPatch((x,.15),.30,.72,boxstyle='round,pad=.012',facecolor='#F1F5F9',edgecolor=COLORS[method],linewidth=1.5,transform=axis.transAxes))
        axis.text(x+.15,.75,LABELS[method],ha='center',fontsize=17,weight='bold',color=COLORS[method],transform=axis.transAxes)
        axis.text(x+.15,.55,textwrap.fill(rule,23),ha='center',va='center',fontsize=16,transform=axis.transAxes)
        axis.text(x+.15,.29,params,ha='center',va='center',fontsize=13.5,color=MUTED,transform=axis.transAxes)
    return save(fig,output,"02_protocol","02_method_specifications",title,"Ridge fit scaler và hệ số riêng trên lịch sử của từng lần dự báo.")


def validation_mae(s,output):
    title="Chọn phương pháp bằng sai số validation"
    fig,axes=frame(title,"04–09/2013 · 24 dự báo / phương pháp · MAE thấp hơn là tốt hơn",size=(11.2,6.6),bottom=.20)
    axis=axes[0,0];table=s['leaderboard']
    bars=axis.barh(range(3),table.MAE,color=[COLORS[m] for m in table.ModelName],height=.55,zorder=3)
    axis.set_yticks(range(3),[LABELS[m] for m in table.ModelName]);axis.invert_yaxis()
    numeric_axis(axis,which='x');axis.set_xlabel('MAE · đơn vị Sales')
    for row,bar in zip(table.itertuples(),bars):
        axis.text(row.MAE+5,bar.get_y()+bar.get_height()/2,vi(row.MAE,2)+('  ← chọn' if row.Selected else ''),va='center',fontsize=16,weight='bold' if row.Selected else 'normal')
    axis.set_xlim(0,table.MAE.max()*1.30)
    return save(fig,output,"03_validation","01_validation_mae",title,"Lựa chọn lưu trước pha test trong lượt tái lập; test tham chiếu đã biết trước.")


def validation_market(s,output):
    title="Phương pháp có ổn định giữa các thị trường không?"
    fig,axes=frame(title,"MAE validation theo Market · N = 6 dự báo / phương pháp / Market",size=(11.2,7),bottom=.23)
    axis=axes[0,0];x=np.arange(4)
    for i,method in enumerate(METHODS):
        part=s['validation_metrics'].loc[s['validation_metrics'].ModelName.eq(method)].set_index('Market').loc[list(MARKETS)]
        axis.bar(x+(i-1)*.24,part.MAE,width=.22,label=LABELS[method],color=COLORS[method],zorder=3)
    axis.set_xticks(x,MARKETS);axis.set_ylabel('MAE · đơn vị Sales');numeric_axis(axis)
    axis.legend(loc='upper center',bbox_to_anchor=(.5,-.14),ncol=3,frameon=False,fontsize=13)
    return save(fig,output,"03_validation","02_validation_by_market",title,"Chọn một phương pháp chung bằng MAE gộp; không chọn riêng theo test.")


def actual_forecast(s,output):
    title="Đặt dự báo cạnh doanh số thực tế"
    fig,axes=frame(title,"10–12/2013 là pha test · N = 3 / Market · thang Y riêng từng ô",rows=2,columns=2,size=(11.2,9.6),bottom=.18,top=.78,hspace=.53)
    styles={'naive_last':':','moving_average_3':'--','ridge':'-.'}
    for axis,market in zip(axes.flat,MARKETS):
        actual=s['monthly'].loc[s['monthly'].Market.eq(market)&s['monthly'].MonthStart.ge('2013-07-01')]
        axis.plot(actual.MonthStart,actual.Sales,color=INK,lw=2.6,marker='o',ms=4,label='Thực tế')
        axis.axvspan(pd.Timestamp('2013-09-16'),pd.Timestamp('2013-12-15'),color=GOLD,alpha=.08)
        for method in METHODS:
            part=s['test'].loc[s['test'].Market.eq(market)&s['test'].ModelName.eq(method)]
            axis.plot(part.ForecastMonth,part.Prediction,color=COLORS[method],ls=styles[method],lw=2.1,marker='s',ms=3.7,label=LABELS[method])
        axis.set_title(market,loc='left',pad=12);axis.set_ylabel('Sales');numeric_axis(axis)
        axis.xaxis.set_major_locator(mdates.MonthLocator(interval=1));axis.xaxis.set_major_formatter(mdates.DateFormatter('%m/%y'))
        axis.tick_params(axis='x',labelsize=11)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',bbox_to_anchor=(.53,.075),ncol=4,frameon=False,fontsize=12)
    return save(fig,output,"04_test","01_actual_forecast",title,"Nền vàng: kỳ test; tháng 7–9 chỉ là lịch sử làm ngữ cảnh.")


def test_metrics(s,output):
    title="Test cho thấy các phương pháp mạnh ở điểm nào?"
    fig,axes=frame(title,"10–12/2013 · 12 dự báo / phương pháp · thấp hơn là tốt hơn",columns=2,size=(11.2,7),bottom=.22,top=.72,wspace=.35)
    table=s['test_metrics'].loc[s['test_metrics'].Market.eq('ALL')].set_index('ModelName').loc[list(METHODS)]
    for axis,metric in zip(axes.flat,['MAE','RMSE']):
        values=table[metric]
        bars=axis.bar(range(3),values,color=[COLORS[m] for m in METHODS],width=.6,zorder=3)
        axis.set_xticks(range(3),['Tháng\ntrước','Trung bình\n3 tháng','Ridge'],fontsize=13)
        axis.set_title(metric,loc='left',pad=14);axis.set_ylabel('Đơn vị Sales');numeric_axis(axis)
        axis.set_ylim(0,values.max()*1.20)
        for bar,value in zip(bars,values):
            axis.text(bar.get_x()+bar.get_width()/2,value+4,vi(value,2),ha='center',fontsize=14)
    return save(fig,output,"04_test","02_test_metrics",title,"So sánh mô tả sau lựa chọn; không dùng kết quả này để đổi phương pháp đã chốt.")


def error_heatmap(s,output):
    title="Phương pháp được chọn dự báo lệch ở đâu?"
    chosen=s['errors'].loc[s['errors'].Split.eq('test')&s['errors'].ModelName.eq(s['selected'])]
    grid=chosen.pivot(index='Market',columns='ForecastMonth',values='AbsoluteError').loc[list(MARKETS)]
    fig,axes=frame(title,LABELS[s['selected']]+" · sai số tuyệt đối từng Market–tháng",size=(11.2,6.6),bottom=.18)
    axis=axes[0,0];image=axis.imshow(grid.values,cmap='YlOrBr',aspect='auto',vmin=0)
    axis.set_yticks(range(4),grid.index);axis.set_xticks(range(3),[m.strftime('%m/%Y') for m in grid.columns])
    for i in range(4):
        for j in range(3):
            value=grid.iloc[i,j];axis.text(j,i,vi(value,1),ha='center',va='center',fontsize=18,color='white' if value>grid.values.max()*.63 else INK)
    fig.colorbar(image,ax=axis,fraction=.035,pad=.03).set_label('|Dự báo − thực tế|')
    return save(fig,output,"04_test","03_selected_error_heatmap",title,"Chỉ 12 ô test; một ô lệch lớn có thể ảnh hưởng đáng kể tới metric.")


def bias_chart(s,output):
    title="Có xu hướng dự báo cao hay thấp hơn thực tế?"
    fig,axes=frame(title,LABELS[s['selected']]+" · Bias test = trung bình (dự báo − thực tế)",size=(11.2,6.6),bottom=.18)
    axis=axes[0,0];table=s['test_metrics'].loc[s['test_metrics'].ModelName.eq(s['selected']) & ~s['test_metrics'].Market.eq('ALL')].set_index('Market').loc[list(MARKETS)]
    axis.barh(range(4),table.Bias,color=[ROSE if x<0 else TEAL for x in table.Bias],height=.55,zorder=3)
    axis.set_yticks(range(4),table.index);axis.axvline(0,color=MUTED);axis.set_xlabel('Bias · đơn vị Sales');numeric_axis(axis,which='x');axis.invert_yaxis()
    span=max(table.Bias.abs().max(),1)
    axis.set_xlim(-span*1.5,span*1.5)
    for i,value in enumerate(table.Bias):
        axis.annotate(vi(value,2),(value,i),xytext=(8 if value>=0 else -8,0),textcoords='offset points',ha='left' if value>=0 else 'right',va='center',fontsize=15)
    return save(fig,output,"04_test","04_selected_bias",title,"Dương: dự báo cao; âm: dự báo thấp. Chỉ N = 3 mỗi Market.")


def gain_chart(s,output):
    title="Phương pháp được chọn cải thiện gì so với tháng trước?"
    fig,axes=frame(title,"Phần trăm giảm sai số so với Naive · dương tốt hơn, âm kém hơn",size=(11.2,6.6),bottom=.22)
    axis=axes[0,0];part=s['improvement'].loc[s['improvement'].ModelName.eq(s['selected'])].set_index('Split')
    x=np.arange(2)
    for i,(split,label,color) in enumerate([('validation','Validation',GOLD),('test','Test',NAVY)]):
        values=part.loc[split,['MAE_ImprovementPct','RMSE_ImprovementPct']].astype(float).to_numpy()
        bars=axis.bar(x+(i-.5)*.28,values,width=.26,label=label,color=color,zorder=3)
        for bar,value in zip(bars,values):
            axis.text(bar.get_x()+bar.get_width()/2,value+(.6 if value>=0 else -.6),vi(value,2)+'%',ha='center',va='bottom' if value>=0 else 'top',fontsize=14)
    axis.set_xticks(x,['MAE','RMSE']);axis.axhline(0,color=MUTED,lw=1);axis.set_ylabel('Giảm sai số (%)');numeric_axis(axis)
    low,high=axis.get_ylim();axis.set_ylim(min(low,-5),high*1.22)
    axis.legend(loc='upper center',bbox_to_anchor=(.5,-.14),ncol=2,frameon=False)
    return save(fig,output,"04_test","05_improvement_vs_naive",title,"Báo cả kết quả kém hơn; không gọi 100% − MAPE là accuracy.")


def future_chart(s,output):
    title="Dự báo kỳ tiếp theo sau khi đã chốt phương pháp"
    fig,axes=frame(title,"01/2014 · "+LABELS[s['selected']]+" · chưa có actual trong nguồn",size=(11.2,7),bottom=.24)
    axis=axes[0,0];table=s['future'].set_index('Market').loc[list(MARKETS)];x=np.arange(4)
    axis.bar(x-.17,table.LastActual,width=.31,color='#B7C9D9',label='Thực tế 12/2013',zorder=3)
    bars=axis.bar(x+.17,table.Prediction,width=.31,color=TEAL,label='Dự báo 01/2014',zorder=3)
    for bar,value in zip(bars,table.Prediction):
        axis.text(bar.get_x()+bar.get_width()/2,value+100,vi(value,1),ha='center',fontsize=13)
    axis.set_xticks(x,MARKETS);axis.set_ylabel('Sales · đơn vị nguồn');numeric_axis(axis);axis.set_ylim(0,max(table.Prediction.max(),table.LastActual.max())*1.16)
    axis.legend(loc='upper center',bbox_to_anchor=(.5,-.13),ncol=2,frameon=False,fontsize=14)
    return save(fig,output,"05_future","01_next_month",title,"Không có khoảng dự báo được hiệu chuẩn; đây không phải dự báo cho hiện tại.")


def summary_table(s,output):
    from coffee_dw.baseline_report import presentation_summary
    title="Một trang tóm tắt toàn bộ thử nghiệm cơ sở"
    fig,axes=frame(title,"Các số liệu lấy từ lần chạy thực; không dò tham số ở bước này",size=(12.2,8.7),bottom=.12,top=.79)
    axis=axes[0,0];axis.set_axis_off()
    source=presentation_summary(s)
    cells=[[textwrap.fill(str(row.Stage),18),textwrap.fill(str(row.Result),45)] for row in source.itertuples()]
    table=axis.table(cellText=cells,colLabels=['Bước','Kết quả cần nhớ'],loc='center',cellLoc='left',colLoc='left',colWidths=[.27,.73])
    table.auto_set_font_size(False);table.set_fontsize(14)
    for (row,col),cell in table.get_celld().items():
        cell.set_edgecolor('#C0CEDB');cell.set_height(.115 if row else .085);cell.PAD=.06
        cell.set_facecolor(NAVY if row==0 else '#EDF3F8' if row%2 else 'white')
        cell.get_text().set_color('white' if row==0 else INK)
        if row==0:cell.get_text().set_weight('bold')
    return save(fig,output,"06_summary","01_study_summary",title,"MAE/RMSE đọc cùng nhau; lựa chọn dựa trên validation, test tham chiếu đã biết trước.")


def render_figures(study,output:Path):
    configure()
    return [draw(study,output) for draw in [input_flow,rolling_protocol,method_cards,validation_mae,validation_market,
                                          actual_forecast,test_metrics,error_heatmap,bias_chart,gain_chart,future_chart,summary_table]]
