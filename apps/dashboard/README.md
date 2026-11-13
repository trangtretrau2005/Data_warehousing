# Dashboard và AI

Trang phụ trách chương 6–7. Dashboard đọc `vw_Detail` của kho SQLite cục bộ, dùng chung quy tắc dữ liệu với phần thực nghiệm. Đây là luồng chạy tham chiếu; kết nối SQL Server và tài khoản chỉ đọc mart là bước tích hợp cần nghiệm thu riêng.

Từ thư mục gốc sau khi cài môi trường theo README:

```powershell
python -m coffee_dw.cli demo
python -m coffee_dw.cli forecast
python -m streamlit run apps/dashboard/app.py
```

Dashboard có tổng quan, chi tiết thị trường–bang–sản phẩm, tồn kho kỳ cuối, chi phí, xuất CSV theo bộ lọc và trang dự báo. Tỷ lệ đạt kế hoạch được tính bằng tổng Sales chia tổng BudgetSales; mẫu số bằng 0 hiển thị thiếu. Tồn kho không được cộng qua thời gian. Giá trị tiền giữ đơn vị nguồn vì CSV chưa công bố loại tiền.

AI là bài toán dự báo doanh số tháng bằng ba cách: tháng trước, trung bình ba tháng và Ridge với ba lag. Lịch sử ban đầu 01/2012–03/2013; chọn phương pháp theo MAE gộp bốn thị trường trong 04–09/2013; kiểm tra riêng 10–12/2013. Mỗi mốc chỉ dùng các tháng trước đó, gồm cả bước chuẩn hóa của Ridge. Mô hình chọn trên validation được giữ nguyên khi báo kết quả test.

`results/forecast/` chứa `summary.json`, `metrics.csv`, `predictions.csv`, `next_month.csv`; bảng `ForecastSales` lưu phiên bản phát hành để tránh nhân dòng khi drill-across. Dự báo 01/2014 chưa có actual trong nguồn. Dashboard chỉ đọc các tệp đã tạo, không tự huấn luyện khi mở trang. Bộ lọc kỳ áp dụng phần phân tích; trang AI luôn ghi rõ lịch sử huấn luyện và lịch đánh giá riêng.

Ca đối soát TN11: 01/2012–West: Sales 10.453, BudgetSales 9.460, Gap +993; East: 6.780/6.180/+600. Ca đi sâu: South–08/2013 tổng Gap −9, Colombian −268 và Decaf Irish Cream −105. Giữ nguyên kỳ khi đổi thị trường và khi xuất CSV. Thu ảnh, thời gian người dùng, đáp án và log thực tế theo `docs/REPORT_MAP.md`; chưa có bằng chứng thì giữ trạng thái chờ.

Tham khảo cách khởi chạy: [tài liệu Streamlit](https://docs.streamlit.io/develop/concepts/architecture/run-your-app).
