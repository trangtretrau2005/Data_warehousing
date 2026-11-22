"""Coffee dashboard: query a prepared warehouse, never mutate the source."""

from pathlib import Path
import os

import pandas as pd
import plotly.express as px
import streamlit as st

from coffee_dw.config import DB_PATH, RESULTS_DIR
from coffee_dw.serving import dashboard_backend, dashboard_detail, dashboard_forecast, forecast_comparison_frame


def aggregate(data: pd.DataFrame, dimensions: list[str]) -> pd.DataFrame:
    result = data.groupby(dimensions, as_index=False)[["Sales", "BudgetSales", "Profit", "Marketing", "COGS", "TotalExpenses"]].sum()
    result["Gap"] = result.Sales - result.BudgetSales
    result["AchievementPct"] = result.Sales.div(result.BudgetSales.where(result.BudgetSales.ne(0))) * 100
    return result


def monthly_axes(figure, months: pd.Series):
    figure.update_xaxes(tickformat="%m/%Y")
    if months.nunique() == 1:
        month = pd.Timestamp(months.iloc[0])
        figure.update_xaxes(range=[month - pd.Timedelta(days=15), month + pd.Timedelta(days=15)], tickvals=[month])
        figure.update_yaxes(rangemode="tozero")
    return figure


def forecast_panel(markets: list[str], backend: str = "sqlite") -> None:
    folder = RESULTS_DIR / "forecast"
    required = ("summary.json", "metrics.csv", "predictions.csv", "next_month.csv")
    if backend == "sqlite" and not all((folder / name).exists() for name in required):
        st.info("Chưa có kết quả dự báo. Chạy `python -m coffee_dw.cli forecast` rồi tải lại trang.")
        return
    try:
        summary, metrics, predictions, future = dashboard_forecast(folder, backend)
    except Exception:
        st.error("Không đọc được kết quả dự báo. Kiểm tra gói đã công bố và kết nối nguồn; không thay dữ liệu thiếu bằng 0.")
        return
    st.caption(f"Dữ liệu lịch sử đến {summary['train_end']}. Chọn thị trường ở bên trái; khoảng tháng đối chiếu dự báo được chọn riêng bên dưới.")
    st.write(f"Phương pháp chọn trên validation: **{summary['selected_model']}**. Kiểm tra: {summary['test_start']} → {summary['test_end']}.")
    st.info("Dữ liệu mẫu thuộc 2012–2013. Kỳ ngoài mẫu tiếp theo không phải dự báo cho thời điểm hiện tại; chưa có actual để chấm sai số.")
    available = predictions.loc[predictions.Market.isin(markets) & predictions.ModelName.eq(summary["selected_model"])].copy()
    available["ForecastMonth"] = pd.to_datetime(available.ForecastMonth)
    if available.empty:
        st.info("Không có dự báo cho thị trường đang chọn.")
        return
    target_months = sorted(available.ForecastMonth.unique())
    default_range = (pd.Timestamp(summary["test_start"]), pd.Timestamp(summary["test_end"]))
    comparison_range = st.select_slider("Khoảng tháng đối chiếu dự báo", options=target_months,
        value=default_range, format_func=lambda value: pd.Timestamp(value).strftime("%m/%Y"))
    st.caption("Đây là khoảng để xem các dự báo một tháng trước đã phát hành ở nhiều origin. Không phải dự báo nhiều tháng cùng lúc từ một origin; không huấn luyện lại khi kéo bộ lọc.")
    view = forecast_comparison_frame(predictions, markets, summary["selected_model"], *comparison_range)
    selected_month = st.selectbox("Tháng đối chiếu", sorted(view.ForecastMonth.unique()),
        index=view.ForecastMonth.nunique()-1, format_func=lambda value: pd.Timestamp(value).strftime("%m/%Y"))
    point = view.loc[view.ForecastMonth.eq(selected_month)].copy()
    st.subheader(f"Dự báo và thực tế · {pd.Timestamp(selected_month):%m/%Y}")
    if len(point) == 1:
        row = point.iloc[0]
        def vi(value, signed=False):
            return format(float(value), "+,.2f" if signed else ",.2f").translate(str.maketrans({",": ".", ".": ","}))
        cols = [*st.columns(2), *st.columns(2)]
        cols[0].metric("Dự báo", vi(row.Prediction))
        cols[1].metric("Thực tế", vi(row.Actual))
        cols[2].metric("Dự báo − thực tế", vi(row.Error, signed=True))
        cols[3].metric("Sai số tuyệt đối (%)", "—" if pd.isna(row.AbsolutePercentageError) else vi(row.AbsolutePercentageError) + "%")
        st.caption(f"{row.Market} · chỉ dùng dữ liệu đến {pd.Timestamp(row.TrainEnd):%m/%Y} để dự báo {pd.Timestamp(selected_month):%m/%Y}. "
                   + ("Dự báo cao hơn thực tế." if row.Error > 0 else "Dự báo thấp hơn thực tế." if row.Error < 0 else "Dự báo bằng thực tế."))
    comparison_columns = ["Market", "ForecastMonth", "TrainEnd", "Prediction", "Actual", "Error", "AbsoluteError", "AbsolutePercentageError", "Split"]
    column_labels = {"Market": "Thị trường", "ForecastMonth": "Tháng đích", "TrainEnd": "Dữ liệu đến",
        "Prediction": "Dự báo", "Actual": "Thực tế", "Error": "Dự báo − thực tế", "AbsoluteError": "Lệch tuyệt đối",
        "AbsolutePercentageError": "Lệch tuyệt đối (%)", "Split": "Pha đánh giá"}
    st.dataframe(point[comparison_columns], hide_index=True, column_config=column_labels)
    st.caption("Dấu + là dự báo cao hơn thực tế; dấu − là thấp hơn. Tỷ lệ lệch = |dự báo − thực tế| / |thực tế| × 100%; actual bằng 0 thì tỷ lệ để thiếu. Đây là lỗi của từng dự báo, khác MAE trung bình nhiều kỳ.")
    chart = view.rename(columns={"Actual": "Thực tế", "Prediction": "Dự báo"}).melt(
        id_vars=["ForecastMonth", "Market", "Split", "TrainEnd"], value_vars=["Thực tế", "Dự báo"], var_name="Chuỗi", value_name="Sales")
    figure = px.line(chart, x="ForecastMonth", y="Sales", color="Chuỗi", line_dash="Chuỗi", symbol="Chuỗi",
        color_discrete_map={"Thực tế": "#1f4e79", "Dự báo": "#c76b28"},
        line_dash_map={"Thực tế": "solid", "Dự báo": "dash"}, markers=True,
        facet_col="Market" if len(markets) > 1 else None, facet_col_wrap=2,
        hover_data={"Split": True, "TrainEnd": "|%m/%Y", "ForecastMonth": "|%m/%Y"},
        labels={"ForecastMonth": "Tháng đích", "Sales": "Sales · đơn vị nguồn"})
    figure.update_traces(line_width=2.5, marker_size=8)
    figure.update_layout(height=650 if len(markets) > 2 else 410, legend_title_text="",
                         template="plotly_white", paper_bgcolor="white", plot_bgcolor="white", font_color="#172b45")
    figure.update_xaxes(dtick="M1")
    figure.update_yaxes(matches=None)
    st.plotly_chart(monthly_axes(figure, view.ForecastMonth), use_container_width=True, theme=None)
    st.caption("Xanh liền: doanh số thực tế. Cam nét đứt: dự báo. Khi có nhiều Market, mỗi ô dùng thang Y riêng; không so độ dốc giữa các ô. Chỉ có actual trong nguồn mới chấm sai số.")
    with st.expander("Từng tháng trong khoảng đã chọn"):
        st.dataframe(view[comparison_columns], hide_index=True, column_config=column_labels)
    with st.expander("Sai số tổng hợp theo protocol đã chốt"):
        st.caption("MAE/RMSE/MAPE ở đây dùng đủ kỳ validation hoặc test của protocol, không tính lại theo khoảng đang xem. Dòng ALL gộp cả bốn Market để chọn phương pháp.")
        st.dataframe(metrics.loc[metrics.Market.isin(["ALL"] + markets)], hide_index=True)
    st.subheader("Dự báo một tháng sau kỳ cuối")
    st.caption("Kỳ này chưa có actual trong Coffee.csv: chỉ có dự báo, chưa thể nói lệch bao nhiêu. Không vẽ actual giả hoặc lấy 0 để tính lỗi.")
    st.dataframe(future.loc[future.Market.isin(markets)], hide_index=True)
    st.download_button("Xuất dự báo thị trường đang chọn", view.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8-sig"), "coffee_forecast_filtered.csv", "text/csv")


def experiment_panel() -> None:
    st.subheader("Kết quả thực nghiệm đã lưu")
    st.caption("Các kết quả dưới đây có phạm vi và protocol riêng, không thay đổi theo bộ lọc kỳ/Market của dashboard.")
    root = Path(__file__).resolve().parents[2]
    artifacts = [
        ("Bảy cấu hình · validation để lựa chọn", root / "experiments/tuning/results/02_validation/leaderboard.csv"),
        ("Mở rộng thăm dò · 11 cấu hình · không đổi phương pháp phục vụ", root / "experiments/forecast_review/results/validation_leaderboard.csv"),
        ("TN12 West · 07–12/2013 · phép thử riêng", root / "experiments/tn12_west/results/metrics.csv"),
        ("TN07–TN10 · SQL Server · 15 lượt mỗi phương án", Path(os.getenv("COFFEE_DW_BENCHMARK_RESULTS", str(root / "results/native_trang/20261119"))) / "benchmark_summary.csv"),
    ]
    for label, path in artifacts:
        st.markdown("**" + label + "**")
        if not path.is_file():
            st.info("Chưa có kết quả thực chạy cho mục này trên máy.")
            continue
        try:
            result = pd.read_csv(path)
            st.dataframe(result, hide_index=True)
            st.download_button("Xuất bảng " + label, path.read_bytes(), path.name, "text/csv", key=str(path))
        except (ValueError, OSError):
            st.error("Không đọc được bảng kết quả; kiểm tra artifact của lần chạy.")
    st.info("Test đã được biết trong quá trình tái lập; TN12 riêng không có test độc lập. Benchmark là phép đo engine trên máy này, không phải thời gian người dùng. UX cần phiên thử với người thật.")


def main() -> None:
    st.set_page_config(page_title="CoffeeDW", page_icon="☕", layout="wide")
    st.title("Coffee Chains · Kho dữ liệu")
    st.caption("Phân tích hiệu quả kinh doanh theo tháng · đơn vị giữ nguyên từ dữ liệu nguồn")
    try:
        backend = dashboard_backend()
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    st.caption("Nguồn phục vụ: " + ("SQL Server · mart.vw_Detail / ml.ForecastSales" if backend == "sqlserver" else "SQLite · bản tham chiếu"))
    if backend == "sqlite" and not Path(DB_PATH).exists():
        st.info("Chưa có kho dữ liệu cục bộ. Từ thư mục dự án, chạy `python -m coffee_dw.cli demo` rồi tải lại trang.")
        st.stop()
    try:
        data = dashboard_detail(DB_PATH, backend)
    except Exception:
        st.error("Không đọc được kho dữ liệu. Kiểm tra kết nối, quyền đọc và cấu trúc mart; đây là lỗi nguồn, không phải doanh số bằng 0.")
        if backend == "sqlite":
            st.code("python -m coffee_dw.cli demo")
        st.stop()
    if data.empty:
        st.info("Kho chưa có bản ghi hợp lệ. Kiểm tra nhật ký ETL trước khi phân tích.")
        st.stop()
    data["MonthStart"] = pd.to_datetime(data.MonthStart)
    months = sorted(data.MonthStart.unique())
    available_markets = sorted(data.Market.unique().tolist())
    st.sidebar.header("Bộ lọc phân tích")
    selected_range = st.sidebar.select_slider("Khoảng tháng", options=months, value=(months[0], months[-1]), format_func=lambda d: pd.Timestamp(d).strftime("%m/%Y"))
    markets = st.sidebar.multiselect("Thị trường", available_markets, default=available_markets)
    page = st.sidebar.radio("Trang", ["Tổng quan", "Tồn kho và chi phí", "Dự báo AI", "Kết quả thực nghiệm"])
    if page == "Kết quả thực nghiệm":
        experiment_panel()
        return
    filtered = data.loc[data.MonthStart.between(*selected_range) & data.Market.isin(markets)].copy()
    st.caption(f"Kỳ phân tích: {pd.Timestamp(selected_range[0]):%m/%Y} → {pd.Timestamp(selected_range[1]):%m/%Y} · {', '.join(markets) or 'chưa chọn thị trường'}")
    if not markets or filtered.empty:
        st.info("Không có dữ liệu trong phạm vi đang chọn. Hãy chọn ít nhất một thị trường và kỳ có dữ liệu.")
        st.stop()
    if page == "Dự báo AI":
        forecast_panel(markets, backend)
        return
    sales, budget, profit = filtered[["Sales", "BudgetSales", "Profit"]].sum()
    cols = st.columns(5)
    cols[0].metric("Doanh số", f"{sales:,.0f}")
    cols[1].metric("Ngân sách", f"{budget:,.0f}")
    cols[2].metric("Chênh lệch", f"{sales - budget:+,.0f}")
    cols[3].metric("Đạt ngân sách", f"{sales / budget:.2%}" if budget else "—")
    cols[4].metric("Lợi nhuận", f"{profit:,.0f}")
    if page == "Tổng quan":
        trend = aggregate(filtered, ["MonthStart", "Market"])
        st.plotly_chart(monthly_axes(px.line(trend, x="MonthStart", y="Sales", color="Market", markers=True), trend.MonthStart), use_container_width=True)
        st.subheader("Thị trường xếp theo chênh lệch tăng dần")
        st.dataframe(aggregate(filtered, ["Market"]).sort_values(["Gap", "Market"]), hide_index=True)
        drill_market = st.selectbox("Mở chi tiết thị trường", sorted(filtered.Market.unique()))
        drilled = filtered.loc[filtered.Market.eq(drill_market)]
        st.caption("Chi tiết giữ nguyên khoảng tháng; các chỉ tiêu có thể đối chiếu bằng tệp xuất bên dưới.")
        st.subheader("Bang")
        st.dataframe(aggregate(drilled, ["Market", "State"]).sort_values(["Gap", "State"]), hide_index=True)
        st.subheader("Sản phẩm")
        products = aggregate(drilled, ["Market", "ProductName"]).sort_values(["Gap", "ProductName"])
        st.dataframe(products, hide_index=True)
        st.download_button("Xuất chi tiết sản phẩm đang xem", products.to_csv(index=False).encode("utf-8-sig"), "coffee_products_filtered.csv", "text/csv")
    else:
        last_month = filtered.MonthStart.max()
        inventory = filtered.loc[filtered.MonthStart.eq(last_month)]
        st.subheader(f"Tồn kho tại kỳ cuối đang chọn · {last_month:%m/%Y}")
        st.caption("Inventory là số đo theo kỳ: cộng theo địa bàn/sản phẩm trong kỳ cuối, không cộng qua các tháng. Giữ nguyên các giá trị âm để đối soát; đơn vị tồn kho chưa được nguồn mô tả.")
        st.dataframe(inventory.groupby("Market", as_index=False).Inventory.sum(), hide_index=True)
        st.subheader("Doanh số, lợi nhuận và chi phí theo cùng phạm vi")
        costs = aggregate(filtered, ["MonthStart", "Market"])
        st.dataframe(costs, hide_index=True)
        chart = costs.melt(id_vars=["MonthStart", "Market"], value_vars=["Sales", "Profit", "Marketing"], var_name="Chỉ tiêu", value_name="Giá trị")
        st.plotly_chart(monthly_axes(px.line(chart, x="MonthStart", y="Giá trị", color="Chỉ tiêu", facet_row="Market"), chart.MonthStart), use_container_width=True)
        st.caption("Các đường cùng tăng không chứng minh tác động nhân quả của Marketing lên Sales.")
    st.download_button("Xuất các dòng trong phạm vi bộ lọc", filtered.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8-sig"), "coffee_filtered.csv", "text/csv")


if __name__ == "__main__":
    main()
