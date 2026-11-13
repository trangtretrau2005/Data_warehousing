# Chương 1 — Bài toán và cơ sở lý thuyết

Người phụ trách: **Thanh**. Đầu ra chương này là phạm vi, câu hỏi quản trị và quy tắc đo để mọi phần sau dùng cùng cách hiểu.

- [ ] Viết bối cảnh chuỗi cà phê và ba câu hỏi: thị trường đóng góp Sales lớn nhất, kỳ–thị trường hụt Budget Sales, sản phẩm đóng góp vào chênh lệch.
- [ ] Phân biệt mục tiêu kỹ thuật (đúng số, truy vết, chi phí truy vấn) và ứng dụng (tìm câu trả lời, dự báo tháng kế tiếp).
- [ ] Trình bày đặc điểm kho dữ liệu, OLTP/OLAP, Inmon/Kimball và lý do chọn mô hình chiều cho nguồn tổng hợp này.
- [ ] Công bố grain: **một sản phẩm × một mã vùng × một tháng**. Mã vùng không phải mã cửa hàng; số dòng không phải số đơn hàng.
- [ ] Phân loại tính cộng được: Sales/Budget/Profit được cộng trên quan sát độc lập; tỷ lệ tính lại từ tổng; Inventory là số ghi nhận theo kỳ.
- [ ] Định nghĩa KPI: Gap = SUM(Sales) − SUM(Budget Sales); Budget attainment = SUM(Sales)/SUM(Budget Sales); Profit rate = SUM(Profit)/SUM(Sales). Mẫu số 0 trả thiếu giá trị.
- [ ] Nêu giới hạn: chưa xác nhận đơn vị tiền/tồn, không có khách hàng/hóa đơn, không kết luận nhân quả từ Marketing và Sales.

Minh chứng chuyển sang chương 2–3: TN01 xác nhận grain và số gốc; TN02 lựa chọn kiến trúc và khóa. Danh mục đầy đủ ở [REPORT_MAP](../REPORT_MAP.md).

Điều kiện bàn giao: Thanh và Chi cùng xác nhận tên khóa, grain và 11 số đo; Trang xác nhận ý nghĩa KPI trước khi viết giao diện.
