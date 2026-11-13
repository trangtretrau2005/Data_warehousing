"""Coffee dashboard: query a prepared warehouse, never mutate the source."""

from pathlib import Path
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from coffee_dw.config import DB_PATH, RESULTS_DIR
from coffee_dw.warehouse import read_detail


def aggregate(data: pd.DataFrame, dimensions: list[str]) -> pd.DataFrame:
    result = data.groupby(dimensions, as_index=False)[["Sales", "BudgetSales", "Profit", "Marketing", "COGS", "TotalExpenses"]].sum()
    result["Gap"] = result.Sales - result.BudgetSales
    result["AchievementPct"] = result.Sales.div(result.BudgetSales.where(result.BudgetSales.ne(0))) * 100
    return result


def forecast_panel(markets: list[str]) -> None:
    folder = RESULTS_DIR / "forecast"
    required = ("summary.json", "metrics.csv", "predictions.csv", "next_month.csv")
    if not all((folder / name).exists() for name in required):
        st.info("Chưa có kết quả dự báo. Chạy `python -m coffee_dw.cli forecast` rồi tải lại trang.")
        return
    try:
        summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        metrics = pd.read_csv(folder / "metrics.csv")
        predictions = pd.read_csv(folder / "predictions.csv", parse_dates=["ForecastMonth"])
        future = pd.read_csv(folder / "next_month.csv")
    except (ValueError, OSError, KeyError) as exc:
        st.error(f"Không đọc được kết quả dự báo: {exc}")
        return
    st.caption(f"Phạm vi dự báo: toàn bộ lịch sử đã nạp đến {summary['train_end']}; bộ lọc thị trường ở bên trái. Bộ lọc kỳ phân tích không thay đổi lịch đánh giá.")
    st.write(f"Phương pháp chọn trên validation: **{summary['selected_model']}**. Kiểm tra: {summary['test_start']} → {summary['test_end']}.")
    st.info("Dữ liệu mẫu thuộc 2012–2013. Kỳ ngoài mẫu tiếp theo không phải dự báo cho thời điểm hiện tại; chưa có actual để chấm sai số.")
    view = predictions.loc[predictions.Market.isin(markets) & predictions.ModelName.eq(summary["selected_model"])]
    if view.empty:
        st.info("Không có dự báo cho thị trường đang chọn.")
        return
    chart = view.melt(id_vars=["ForecastMonth", "Market", "Split"], value_vars=["Actual", "Prediction"], var_name="Series", value_name="Sales")
    st.plotly_chart(px.line(chart, x="ForecastMonth", y="Sales", color="Market", line_dash="Series", markers=True, hover_data=["Split"]), use_container_width=True)
    st.caption("Đường dự báo gồm validation và test, mỗi mốc chỉ dùng lịch sử trước tháng đích. MAE/RMSE theo đơn vị nguồn; MAPE tính theo %.")
    st.dataframe(metrics.loc[metrics.Market.isin(["ALL"] + markets)], hide_index=True)
    st.subheader("Dự báo một tháng sau kỳ cuối")
    st.dataframe(future.loc[future.Market.isin(markets)], hide_index=True)


def main() -> None:
    st.set_page_config(page_title="CoffeeDW", page_icon="☕", layout="wide")
    st.title("Coffee Chains · Kho dữ liệu")
    st.caption("Phân tích hiệu quả kinh doanh theo tháng · đơn vị giữ nguyên từ dữ liệu nguồn")
    if not Path(DB_PATH).exists():
        st.info("Chưa có kho dữ liệu cục bộ. Từ thư mục dự án, chạy `python -m coffee_dw.cli demo` rồi tải lại trang.")
        st.stop()
    try:
        data = read_detail(DB_PATH)
    except Exception as exc:
        st.error(f"Không đọc được kho dữ liệu: {exc}")
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
    page = st.sidebar.radio("Trang", ["Tổng quan", "Tồn kho và chi phí", "Dự báo AI"])
    filtered = data.loc[data.MonthStart.between(*selected_range) & data.Market.isin(markets)].copy()
    st.caption(f"Kỳ phân tích: {pd.Timestamp(selected_range[0]):%m/%Y} → {pd.Timestamp(selected_range[1]):%m/%Y} · {', '.join(markets) or 'chưa chọn thị trường'}")
    if not markets or filtered.empty:
        st.info("Không có dữ liệu trong phạm vi đang chọn. Hãy chọn ít nhất một thị trường và kỳ có dữ liệu.")
        st.stop()
    if page == "Dự báo AI":
        forecast_panel(markets)
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
        st.plotly_chart(px.line(trend, x="MonthStart", y="Sales", color="Market", markers=True), use_container_width=True)
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
        st.plotly_chart(px.line(chart, x="MonthStart", y="Giá trị", color="Chỉ tiêu", facet_row="Market"), use_container_width=True)
        st.caption("Các đường cùng tăng không chứng minh tác động nhân quả của Marketing lên Sales.")
    st.download_button("Xuất các dòng trong phạm vi bộ lọc", filtered.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8-sig"), "coffee_filtered.csv", "text/csv")


if __name__ == "__main__":
    main()
