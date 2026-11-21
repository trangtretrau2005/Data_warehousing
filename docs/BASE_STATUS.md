# Trạng thái bộ khung ngày 13 tháng 11 năm 2026

Base đã có code chạy cục bộ cho profile nguồn, ETL staging–star–mart, audit/reject, nạp lại, sửa số, dashboard và dự báo theo protocol báo cáo. Script thực nghiệm có SCD1/2/3, nạp tăng dần và lựa chọn view HRU. Cấu trúc, checklist và code được chia theo Thanh1–3, Chi4–5, Trang6–7.

## Đã chạy trên bản tham chiếu

- Profile: 4248 dòng hợp lệ, 24 tháng, 4 thị trường, 156 mã vùng, 13 sản phẩm; giữ đủ các cảnh báo số nguồn.
- ETL: tổng Sales819811, BudgetSales746160, Profit259543; phát lại không nhân bản; sửa cùng grain cập nhật số đo.
- Tải tăng dần: 23 kỳ4071 dòng/Sales784231; thêm kỳ mới thành4248/819811; lỗi mô phỏng6 hợp lệ/2 loại/Sales1139.
- SCD: Type2 lookup trước/đúng biên ra key1/key2, replay giữ2 phiên bản, không chồng khoảng; Type3 chỉ giữ một bước trước.
- Forecast: chọn moving_average_3 trên24 prediction validation, MAE223.28; test12 prediction MAE225.22; tương lai01/2014 chưa có actual.
- Dashboard AppTest: thiếu kho có hướng dẫn; bộ lọc01/2012 West→East→West trả đúng KPI; các trang, trạng thái rỗng và AI đọc kết quả tạo sẵn chạy được.

Đây là kết quả thực thi Python/SQLite và kiểm tra giao diện bằng Streamlit AppTest. Chưa phải kết quả người dùng thực hiện tác vụ hay bằng chứng xử lý trên SQL Server.

## Phần nhóm tiếp tục

| Hạng mục | Bộ khung đã có | Cần thực hiện |
| --- | --- | --- |
| SQL Server | DDL, ETL proc, cầu nối ODBC, mart, đối soát | Cấu hình instance/driver, chạy script và kiểm tra trên engine thật |
| SSIS | Quy tắc, mapping và hướng dẫn Control/Data Flow | Tạo/chạy project native, capture batch và đường lỗi |
| SSAS | Đặc tả dimension/hierarchy/measure và MDX mẫu | Tạo/deploy/process cube, đối chiếu Browser/MDX/SQL |
| Benchmark | Bản sao500 lần, indexed view/partition/index, protocol và mẫu raw runs | Thu plans, IO/TIME, dung lượng, chi phí ghi;15 lượt mỗi cấu hình |
| Dashboard SQL Server | Hợp đồng mart trùng tên/cột | Kết nối chỉ đọc mart và lưu forecast về ml.ForecastSales khi tích hợp native |
| UX | Tác vụ, đáp án và mẫu ẩn danh | Mời người thử Excel/web, đổi thứ tự và ghi số đo thật |
| Báo cáo | Bảy checklist và ánh xạ đủ bước/TN | Viết nội dung, chèn ảnh thật, kết luận sau khi đo |

Nhánh tích hợp/chạy thử là `dev`; các nhánh làm việc là `thanh`, `chi`, `trang`. `main` được giữ nguyên tại bản base cho tới khi Trang xác nhận bản tích hợp OK và yêu cầu cập nhật. Remote `origin` là repository GitHub của nhóm. Xem commit cụ thể bằng `git log` và GitHub; các thành viên bắt đầu theo [START_HERE](START_HERE.md) trên `dev` hoặc nhánh cá nhân. Các file Word nguồn và CSV gốc được giữ nguyên.
