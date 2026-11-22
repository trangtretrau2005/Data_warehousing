# Dashboard và AI

Trang phụ trách chương 6–7. Dashboard hỗ trợ SQLite tham chiếu (mặc định) và SQL Server qua `mart.vw_Detail`/`ml.ForecastSales`. Ngày19/11/2026 đã đối soát và thao tác browser trên database native biệt lập; khi chuyển sang database Chi bàn giao phải nghiệm thu lại đúng batch và quyền tài khoản. Luồng xem trang chỉ thực hiện đọc; bước công bố forecast chạy riêng.

Từ thư mục gốc sau khi cài môi trường theo README:

```powershell
python -m coffee_dw.cli demo
python -m coffee_dw.cli forecast
python -m streamlit run apps/dashboard/app.py
```

Dashboard có tổng quan, chi tiết thị trường–bang–sản phẩm, tồn kho kỳ cuối, chi phí, xuất CSV theo bộ lọc và trang dự báo. Tỷ lệ đạt kế hoạch được tính bằng tổng Sales chia tổng BudgetSales; mẫu số bằng 0 hiển thị thiếu. Tồn kho không được cộng qua thời gian. Giá trị tiền giữ đơn vị nguồn vì CSV chưa công bố loại tiền.

Trang **Kết quả thực nghiệm** đọc các bảng đã lưu của tuning, TN12 West và benchmark SQL Server; có nhãn phạm vi riêng, không lọc lại kết quả thực nghiệm theo slider. Đường dẫn benchmark mặc định `results/native_trang/20261119`, đổi bằng `COFFEE_DW_BENCHMARK_RESULTS` khi dùng run khác.

## Backend SQL Server

Đặt `COFFEE_DW_BACKEND=sqlserver` và `COFFEE_DW_SQLSERVER_CONNECTION` trong môi trường tiến trình hoặc cấu hình cục bộ được ignore. Cài extra `.[sqlserver]`. Chỉ trỏ tới database đã có schema/mart nhóm; không in credential vào log. [verify_native_serving.py](../../scripts/verify_native_serving.py) đối soát toàn bộ11 số đo và phát hành/replay112 forecast vào native, không nạp fact nghiệp vụ. Dashboard không ghi DB. Dùng tài khoản chỉ đọc mart/forecast khi bàn giao triển khai; Windows auth hiện tại là môi trường thử cục bộ, chưa phải nghiệm thu phân quyền production.

Khởi chạy hai app bằng [launcher](../../scripts/start_trang_demo.ps1):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_trang_demo.ps1 -Backend sqlserver -NativeDatabase CoffeeDW_Trang_20261119
```

Launcher không thay connection đã có và không chiếm cổng của tiến trình đang chạy. Kiểm nhãn **Nguồn phục vụ** trong app; đổi backend cần khởi động lại đúng tiến trình. Phiên bản native chỉ đọc publication chính đủ4Market ×9tháng ×3phương pháp và4dự báo tương lai; gói dở dang/sai split/mốc/actual bị chặn thay vì tính metric trên dữ liệu thiếu. Dòng `ALL` là metric gộp bốn Market, được ghi rõ cạnh bảng.

AI là bài toán dự báo doanh số tháng bằng ba cách: tháng trước, trung bình ba tháng và Ridge với ba lag. Lịch sử ban đầu 01/2012–03/2013; chọn phương pháp theo MAE gộp bốn thị trường trong 04–09/2013; kiểm tra riêng 10–12/2013. Mỗi mốc chỉ dùng các tháng trước đó, gồm cả bước chuẩn hóa của Ridge. Mô hình chọn trên validation được giữ nguyên khi báo kết quả test.

Với SQLite, `results/forecast/` chứa `summary.json`, `metrics.csv`, `predictions.csv`, `next_month.csv`; bảng `ForecastSales` lưu phiên bản phát hành để tránh nhân dòng khi drill-across. Với native, đọc `ml.ForecastSales` theo ModelVersion chính và tính lại metric trên publication đủ. Dự báo 01/2014 chưa có actual trong nguồn. Dashboard không tự huấn luyện khi mở trang. Bộ lọc kỳ áp dụng phần phân tích; trang AI luôn ghi rõ lịch sử huấn luyện và lịch đánh giá riêng. CSV dự báo xuất đúng Market đang chọn.

Ca đối soát TN11: 01/2012–West: Sales 10.453, BudgetSales 9.460, Gap +993; East: 6.780/6.180/+600. Ca đi sâu: South–08/2013 tổng Gap −9, Colombian −268 và Decaf Irish Cream −105. Giữ nguyên kỳ khi đổi thị trường và khi xuất CSV. Thu ảnh, thời gian người dùng, đáp án và log thực tế theo `docs/REPORT_MAP.md`; chưa có bằng chứng thì giữ trạng thái chờ.

## Xem thực tế và sai lệch từng dự báo

Trong **Dự báo AI**, chọn Market ở sidebar rồi dùng **Khoảng tháng đối chiếu dự báo** và **Tháng đối chiếu**. Hai điều khiển này chọn các target đã có dự báo, độc lập với slider phân tích kinh doanh. Mặc định xem test10–12/2013. Mỗi điểm là dự báo một tháng trước ở origin riêng; chọn một khoảng không đổi thành dự báo nhiều bước từ cùng một origin.

Ví dụ West11/2013: MA3 dự báo11777,3333, actual11300, Error=Prediction−Actual=+477,3333, lệch tuyệt đối4,2242%. Dữ liệu để dự báo chỉ đến10/2013. Biểu đồ dùng xanh liền cho thực tế, cam nét đứt cho dự báo; nhiều Market tách ô và ghi rõ thangY riêng. Bảng có signed/absolute/percentage error; CSV chứa đúng Market và khoảng target đang xem. Actual0 giữ tỷ lệ thiếu. Metric MAE/RMSE gộp protocol đặt trong phần mở rộng riêng, không gọi lỗi một tháng là MAE cả mô hình.

01/2014 là target chưa có actual trong nguồn, nằm riêng ở bảng tương lai và không được tính lỗi. [FAQ và cách trả lời bảo vệ](../../docs/trang/forecast_questions.md) phân biệt khoảng xem, horizon và khoảng bất định; [review thăm dò](../../experiments/forecast_review/README.md) so thêm SES/mùa vụ, giữ MA3 phục vụ.

Tham khảo cách khởi chạy: [tài liệu Streamlit](https://docs.streamlit.io/develop/concepts/architecture/run-your-app).
