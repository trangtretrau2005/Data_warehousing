"""Static report figures: Times New Roman, consistent palette, PNG/PDF/SVG."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.font_manager as font_manager
from matplotlib import pyplot as plt
from matplotlib import colors, patches, ticker
import numpy as np
import pandas as pd

from coffee_dw.exploration import SCOPE_LABELS, vi

NAVY, TEAL, GOLD, ROSE = "#244E7A", "#207F83", "#B47B25", "#AB5366"
INK, MUTED, GRID = "#18324E", "#486078", "#DEE6EE"
MARKET_COLORS = {"Central": NAVY, "East": TEAL, "South": GOLD, "West": ROSE}
REVENUE_CMAP = colors.LinearSegmentedColormap.from_list("coffee_navy", ["#EDF4F9", "#709BBB", "#173C65"])


def configure():
    try:
        font_manager.findfont("Times New Roman", fallback_to_default=False)
        family = "Times New Roman"
    except ValueError:
        family = "DejaVu Serif"
    plt.rcParams.update({"font.family": family, "font.size": 15, "axes.titlesize": 19,
                         "axes.labelsize": 15, "xtick.labelsize": 13, "ytick.labelsize": 14,
                         "text.color": INK, "axes.labelcolor": INK, "xtick.color": MUTED,
                         "ytick.color": MUTED, "axes.edgecolor": "#B6C5D4", "axes.spines.top": False,
                         "axes.spines.right": False, "figure.facecolor": "white", "axes.facecolor": "white",
                         "savefig.facecolor": "white", "pdf.fonttype": 42, "svg.fonttype": "none"})


def frame(title, subtitle, *, rows=1, columns=1, size=(11.2, 7.2), bottom=.18, top=.80, hspace=.52, wspace=.35):
    fig, axes = plt.subplots(rows, columns, figsize=size, squeeze=False)
    fig.subplots_adjust(left=.105, right=.96, top=top, bottom=bottom, hspace=hspace, wspace=wspace)
    fig.text(.055, .965, "COFFEE CHAINS  /  EXPLORE DATA", fontsize=11, color=TEAL, weight="bold", va="top")
    fig.text(.055, .91, title, fontsize=23, weight="bold", va="top")
    fig.text(.055, .85, subtitle, fontsize=14, color=MUTED, va="top")
    return fig, axes


def finish(fig, folder, name, title, note):
    fig.text(.055, .035, "Nguồn: Coffee.csv · Đơn vị nguồn · " + note, fontsize=11.5, color=MUTED, va="bottom")
    folder.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(folder / f"{name}.{suffix}", dpi=300, bbox_inches="tight", pad_inches=.18)
    plt.close(fig)
    return {"id": name, "title": title, "note": note}


def numeric_axis(axis, *, which="y"):
    target = axis.yaxis if which == "y" else axis.xaxis
    target.set_major_formatter(ticker.FuncFormatter(lambda value, _: vi(value)))
    axis.grid(axis=which, color=GRID, lw=.7, zorder=0)
    axis.set_axisbelow(True)


def line_history(data, folder):
    title = "Doanh số theo tháng tại bốn thị trường"
    fig, axes = frame(title, SCOPE_LABELS[data["name"]] + " · thang Y riêng để đọc biến động", rows=2, columns=2, size=(11.2, 9.2), bottom=.16, top=.79, hspace=.58)
    monthly = data["tables"]["monthly_market"]
    for axis, market in zip(axes.flat, sorted(monthly.Market.unique())):
        part = monthly.loc[monthly.Market.eq(market)]
        axis.plot(part.MonthStart, part.Sales, color=MARKET_COLORS.get(market, NAVY), lw=2.4, marker="o", ms=3.5, zorder=3)
        axis.set_title(f"{market} · N = {len(part)}", loc="left", pad=12, color=MARKET_COLORS.get(market, NAVY))
        if data["name"] == "full_history_descriptive":
            axis.axvspan(pd.Timestamp("2013-03-16"), pd.Timestamp("2013-09-16"), color=GOLD, alpha=.10)
            axis.axvspan(pd.Timestamp("2013-09-16"), pd.Timestamp("2013-12-15"), color=ROSE, alpha=.10)
        axis.set_xlim(part.MonthStart.min()-pd.Timedelta(days=10), part.MonthStart.max()+pd.Timedelta(days=20))
        axis.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"))
        axis.set_ylabel("Sales")
        numeric_axis(axis)
    note = "Thang Y riêng từng ô; không suy mùa vụ chắc chắn từ hai năm."
    if data["name"] == "full_history_descriptive":
        note = "Nền vàng: validation; nền hồng: test. Toàn kỳ chỉ mô tả; thang Y riêng."
    return finish(fig, folder, "01_sales_history", title, note)


def sales_heatmap(data, folder):
    title = "Nhịp doanh số qua từng tháng"
    monthly = data["tables"]["monthly_market"].copy()
    monthly["Year"] = monthly.MonthStart.dt.year
    monthly["Month"] = monthly.MonthStart.dt.month
    years = sorted(monthly.Year.unique())
    rows = [(year, market) for year in years for market in sorted(monthly.Market.unique())]
    grid = monthly.pivot(index=["Year", "Market"], columns="Month", values="Sales").reindex(index=pd.MultiIndex.from_tuples(rows), columns=range(1, 13)) / 1000
    fig, axes = frame(title, SCOPE_LABELS[data["name"]] + " · màu và số biểu diễn nghìn đơn vị Sales", size=(11.2, 7.7), bottom=.19)
    axis = axes[0,0]
    cmap = REVENUE_CMAP.copy(); cmap.set_bad("#EEF0F3")
    image = axis.imshow(grid.values, cmap=cmap, aspect="auto")
    axis.set_xticks(range(12), [f"{m:02d}" for m in range(1,13)])
    axis.set_yticks(range(len(rows)), [f"{y} · {m}" for y,m in rows])
    for i in range(len(rows)):
        for j in range(12):
            value = grid.iloc[i,j]
            if pd.notna(value):
                axis.text(j, i, vi(value,1), ha="center", va="center", fontsize=12, color="white" if value > np.nanmax(grid.values)*.66 else INK)
    axis.set_xlabel("Tháng trong năm")
    fig.colorbar(image, ax=axis, fraction=.035, pad=.025).set_label("Sales / 1.000")
    return finish(fig, folder, "02_sales_heatmap", title, "Ô xám: không thuộc phạm vi hoặc thiếu; không đổi thành 0.")


def market_budget(data, folder):
    title = "Thực hiện và ngân sách theo thị trường"
    fig, axes = frame(title, SCOPE_LABELS[data["name"]], columns=2, size=(11.2,7), wspace=.40, bottom=.23)
    table = data["tables"]["market_summary"].sort_values("Market")
    for axis, actual, budget, label in [(axes[0,0],"Sales","BudgetSales","Doanh số"),(axes[0,1],"Profit","BudgetProfit","Lợi nhuận")]:
        y=np.arange(len(table))
        axis.barh(y-.18, table[actual], height=.32, color=NAVY, label="Thực hiện", zorder=3)
        axis.barh(y+.18, table[budget], height=.32, color="#D9B579", label="Ngân sách", zorder=3)
        axis.set_yticks(y,table.Market); axis.invert_yaxis()
        axis.set_title(label, loc="left", pad=14)
        axis.set_xlabel("Nghìn đơn vị nguồn")
        axis.xaxis.set_major_formatter(ticker.FuncFormatter(lambda value,_:vi(value/1000)))
        axis.grid(axis="x",color=GRID,lw=.7,zorder=0);axis.set_axisbelow(True)
    handles, labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center",bbox_to_anchor=(.54,.09),ncol=2,frameon=False,fontsize=14)
    return finish(fig,folder,"03_market_budget",title,"Ngân sách và thực hiện cùng phạm vi; không gộp Inventory xuyên thời gian.")


def product_ranking(data, folder):
    title = "Sản phẩm bán nhiều và phần chênh lợi nhuận"
    fig,axes=frame(title,SCOPE_LABELS[data["name"]],columns=2,size=(11.2,9),bottom=.16,wspace=.55)
    table=data["tables"]["product_summary"].sort_values("Sales",ascending=True)
    left,right=axes[0]
    y=np.arange(len(table));left.barh(y,table.Sales,color=TEAL,height=.68,zorder=3)
    left.set_yticks(y,table.ProductName,fontsize=13);left.set_title("Xếp hạng Sales",loc="left",pad=14)
    left.set_xlabel("Nghìn đơn vị nguồn")
    left.xaxis.set_major_formatter(ticker.FuncFormatter(lambda value,_:vi(value/1000)))
    left.grid(axis="x",color=GRID,zorder=0);left.set_axisbelow(True)
    right.barh(y,table.ProfitGap,color=[ROSE if x<0 else NAVY for x in table.ProfitGap],height=.68,zorder=3)
    right.set_yticks(y,[""]*len(table));right.axvline(0,color=MUTED,lw=.9)
    right.set_title("Profit − BudgetProfit",loc="left",pad=14);right.set_xlabel("Chênh lệch · nghìn đơn vị")
    right.xaxis.set_major_formatter(ticker.FuncFormatter(lambda value,_:vi(value/1000)))
    right.grid(axis="x",color=GRID,zorder=0);right.set_axisbelow(True)
    return finish(fig,folder,"04_product_ranking",title,"Cùng thứ tự sản phẩm ở hai ô; hụt ngân sách chưa đồng nghĩa lỗ ròng.")


def distribution(data, folder):
    title="Phân bố và độ biến động doanh số tháng"
    fig,axes=frame(title,SCOPE_LABELS[data["name"]]+" · mỗi chấm là một ô Market–tháng",size=(11.2,7),bottom=.18)
    axis=axes[0,0];monthly=data["tables"]["monthly_market"];markets=sorted(monthly.Market.unique())
    samples=[monthly.loc[monthly.Market.eq(m),"Sales"].to_numpy() for m in markets]
    boxes=axis.boxplot(samples,patch_artist=True,widths=.42,showfliers=False,medianprops={"color":"white","lw":2.2})
    rng=np.random.default_rng(2026)
    for pos,(market,values,box) in enumerate(zip(markets,samples,boxes["boxes"]),start=1):
        box.set_facecolor(MARKET_COLORS.get(market,NAVY));box.set_alpha(.85)
        axis.scatter(pos+rng.uniform(-.11,.11,len(values)),values,c=MARKET_COLORS.get(market,NAVY),s=28,alpha=.75,edgecolors="white",lw=.5,zorder=3)
    axis.set_xticks(range(1,len(markets)+1),markets);axis.set_ylabel("Sales tháng · đơn vị nguồn")
    numeric_axis(axis)
    return finish(fig,folder,"05_monthly_distribution",title,"IQR chỉ đánh dấu điểm cần kiểm tra; không tự loại quan sát ngoài hộp.")


def lag_correlations(data,folder):
    title="Doanh số tháng trước liên hệ với tháng hiện tại ra sao?"
    fig,axes=frame(title,SCOPE_LABELS[data["name"]]+" · Pearson r trong từng Market, cùng tập dòng đủ lag123",size=(11.2,6.5),bottom=.18)
    axis=axes[0,0];table=data["tables"]["lag_correlations"]
    grid=table.pivot(index="Market",columns="Lag",values="PearsonR")
    image=axis.imshow(grid.values,cmap="RdBu",vmin=-1,vmax=1,aspect="auto")
    axis.set_xticks(range(3),["Trước 1 tháng","Trước 2 tháng","Trước 3 tháng"])
    axis.set_yticks(range(len(grid)),grid.index)
    for i,market in enumerate(grid.index):
        for j,lag in enumerate(grid.columns):
            value=grid.loc[market,lag];n=int(table.loc[table.Market.eq(market)&table.Lag.eq(lag),"N"].iloc[0])
            axis.text(j,i,f"r = {vi(value,2)}\nN = {n}",ha="center",va="center",fontsize=16,color="white" if pd.notna(value) and abs(value)>.6 else INK)
    fig.colorbar(image,ax=axis,fraction=.03,pad=.03).set_label("Pearson r")
    return finish(fig,folder,"06_lag_correlations",title,"Mô tả liên hệ, chưa chọn feature/model và không chứng minh nhân quả.")


def measure_correlations(data,folder):
    title="Liên hệ giữa các số đo trong cùng kỳ"
    fig,axes=frame(title,SCOPE_LABELS[data["name"]]+" · tổng hợp Market–tháng, gộp bốn thị trường",size=(11.2,9.2),bottom=.24)
    axis=axes[0,0];grid=data["tables"]["measure_correlations"].set_index("Measure")
    image=axis.imshow(grid.values,cmap="RdBu",vmin=-1,vmax=1,aspect="equal")
    axis.set_xticks(range(len(grid)),grid.columns,rotation=45,ha="right",fontsize=12)
    axis.set_yticks(range(len(grid)),grid.index,fontsize=13)
    for i in range(len(grid)):
        for j in range(len(grid)):
            value=grid.iloc[i,j]
            axis.text(j,i,vi(value,2),ha="center",va="center",fontsize=11.5,color="white" if abs(value)>.6 else INK)
    fig.colorbar(image,ax=axis,fraction=.035,pad=.03).set_label("Pearson r")
    return finish(fig,folder,"07_measure_correlations",title,"Có ảnh hưởng quy mô Market; số đo cùng kỳ không mặc nhiên là đầu vào dự báo.")


def inventory_snapshot(data,folder):
    title="Tồn kho: chỉ đọc trong một kỳ cuối"
    monthly=data["tables"]["monthly_market"];last=monthly.MonthStart.max();latest=monthly.loc[monthly.MonthStart.eq(last)].sort_values("Market")
    fig,axes=frame(title,f"Snapshot {last:%m/%Y} của phạm vi {data['name']} · tổng có dấu theo Market",size=(11.2,6.6),bottom=.18)
    axis=axes[0,0];axis.barh(latest.Market,latest.Inventory,color=[MARKET_COLORS.get(m,NAVY) for m in latest.Market],zorder=3,height=.55)
    axis.set_xlabel("Inventory · đơn vị nguồn chưa xác định");axis.invert_yaxis();numeric_axis(axis,which="x")
    for i,value in enumerate(latest.Inventory):
        axis.annotate(vi(value),(value,i),xytext=(8,0),textcoords="offset points",va="center",fontsize=14)
    xmin,xmax=axis.get_xlim();axis.set_xlim(min(0,xmin),xmax*1.17)
    return finish(fig,folder,"08_inventory_snapshot",title,"Không cộng các tháng; Inventory âm chưa phải bằng chứng số lần hết hàng.")


def common_figures(bundle,folder):
    result=[];scope=bundle["scopes"]["full_history_descriptive"]
    fig,axes=frame("Kiểm tra độ phủ thời gian của dữ liệu","Số quan sát nguồn hợp lệ tại mỗi Market–tháng",size=(12.5,5.8),bottom=.23)
    axis=axes[0,0];coverage=scope["tables"]["coverage"];grid=coverage.pivot(index="Market",columns="MonthStart",values="SourceRows")
    cmap=colors.ListedColormap(["#D7E6F2"]);cmap.set_bad("#F6D4D5")
    axis.imshow(np.where(grid.notna(),1,np.nan),cmap=cmap,aspect="auto")
    axis.set_yticks(range(len(grid)),grid.index)
    axis.set_xticks(range(len(grid.columns)),[d.strftime("%m/%y") for d in grid.columns],rotation=60,ha="right",fontsize=10.5)
    for i in range(len(grid)):
        for j in range(len(grid.columns)):
            axis.text(j,i,str(int(grid.iloc[i,j])) if pd.notna(grid.iloc[i,j]) else "Thiếu",ha="center",va="center",fontsize=10.5)
    result.append(finish(fig,folder,"01_month_coverage","Độ phủ dữ liệu","Ô hồng: thiếu; con số trong ô là số dòng tổng hợp, không phải số đơn hàng."))
    fig,axes=frame("Từ dòng nguồn đến dữ liệu chuẩn bị dự báo","Các số đếm lấy từ lần chạy thực; bước tổng hợp không phải loại dữ liệu",size=(11.2,6.8),bottom=.13)
    axis=axes[0,0];axis.set_axis_off();audit=bundle["tables"]["preprocessing_audit"]
    positions=[(.02,.63),(.36,.63),(.70,.63),(.36,.05),(.70,.05)]
    labels=["CSV nguồn","Hợp lệ sau chuẩn hóa","Market × tháng","Lịch sử thiết kế","Đủ đầu vào lag123"]
    for i,((x,y),label,row) in enumerate(zip(positions,labels,audit.itertuples())):
        axis.add_patch(patches.FancyBboxPatch((x,y),.27,.30,boxstyle="round,pad=0.014",facecolor="#E8EFF7" if i<3 else "#E2F0EE",edgecolor="#AAC0D3",transform=axis.transAxes))
        axis.text(x+.135,y+.225,label,ha="center",va="center",fontsize=13.5,transform=axis.transAxes)
        axis.text(x+.135,y+.105,vi(row.RowsAfter),ha="center",va="center",fontsize=25,weight="bold",color=NAVY,transform=axis.transAxes)
    for start,end in [((.30,.78),(.35,.78)),((.64,.78),(.69,.78)),((.83,.60),(.50,.40)),((.64,.20),(.69,.20))]:
        axis.annotate("",xy=end,xytext=start,xycoords="axes fraction",arrowprops={"arrowstyle":"->","color":MUTED,"lw":1.8})
    axis.text(.02,.20,f"Reject: {bundle['source']['rejected_rows']} dòng\nKhông fit scaler/model ở EDA",transform=axis.transAxes,fontsize=12.5,color=MUTED)
    result.append(finish(fig,folder,"02_preprocessing_flow","Quy trình tiền xử lý","Ba kỳ đầu mỗi Market chưa đủ lag; không phải dòng lỗi nguồn."))
    fig,axes=frame("Lịch sử học, chọn phương pháp và kiểm tra","Protocol chính của Coffee · chia theo thời gian, không chia ngẫu nhiên",size=(11.2,4.8),bottom=.23,top=.72)
    axis=axes[0,0]
    groups=[(0,15,NAVY,"Khởi tạo\n15 tháng"),(15,6,GOLD,"Validation\n6 tháng"),(21,3,ROSE,"Test\n3 tháng")]
    for start,length,color,label in groups:
        axis.broken_barh([(start,length)],(.15,.70),facecolors=color,edgecolors="white",linewidth=2)
        axis.text(start+length/2,.5,label,ha="center",va="center",fontsize=15,color="white",weight="bold")
    axis.set_xlim(0,24);axis.set_ylim(0,1);axis.set_yticks([])
    axis.set_xticks([0,15,21,24],["01/2012","04/2013","10/2013","Hết 12/2013"],fontsize=13)
    axis.spines["left"].set_visible(False);axis.spines["bottom"].set_visible(False)
    result.append(finish(fig,folder,"03_temporal_split","Lịch chia tập","EDA thiết kế chỉ dùng khối đầu; chưa huấn luyện hay chọn mô hình."))
    return result


def render_figures(bundle,output:Path):
    configure()
    result={"common":common_figures(bundle,output/"figures")}
    for key,data in bundle["scopes"].items():
        folder=output/key/"figures"
        result[key]=[draw(data,folder) for draw in [line_history,sales_heatmap,market_budget,product_ranking,distribution,lag_correlations,measure_correlations,inventory_snapshot]]
    return result
