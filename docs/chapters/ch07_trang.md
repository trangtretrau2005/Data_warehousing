# Chương 7 — Triển khai và đánh giá hệ thống

Người phụ trách: **Trang**. Chương này tích hợp ứng dụng và thu bằng chứng thực nghiệm trên môi trường triển khai.

- [ ] Dashboard gồm tổng quan KPI, drill-down State/Product, Marketing/chi phí, tồn kho kỳ chọn, dự báo và kết quả thực nghiệm.
- [ ] Bộ lọc kỳ/Market đi cùng biểu đồ, KPI và CSV xuất; xếp Market/Product theo Gap có dấu tăng dần, quy định thứ tự khi đồng hạng.
- [ ] TN11: đổi West→East→West ở 01/2012; West Sales/Budget/Gap = 10.453/9.460/+993, East = 6.780/6.180/+600.
- [ ] Giao diện báo không có bản ghi khi lọc rỗng; lỗi kết nối nguồn có thông báo riêng, không biến thành KPI bằng 0.
- [ ] TN07: chuẩn bị bench riêng, đối chiếu số dòng/tổng và EXCEPT hai chiều trước khi đo; dữ liệu nhân bản chỉ dùng thử tải.
- [ ] TN08: indexed view so GROUP BY, kiểm tra SET options/SCHEMABINDING/COUNT_BIG, plan thực đọc bảng hoặc view, đo cả duy trì và dung lượng.
- [ ] TN09: bảng thường/partition RANGE RIGHT, cùng dữ liệu/chỉ mục; lọc một tháng và toàn khoảng, ghi partition thực truy cập.
- [ ] TN10: đối chứng độc lập có/không nonclustered index; thử lát cắt hẹp/rộng, selectivity, seek/scan/lookup.
- [ ] Mỗi cặp: ba warm-up, 15 lượt đo mỗi phương án xen kẽ, IO/TIME/actual plan, raw runs, median/p95 cùng quy ước.
- [ ] TN13 mở rộng: lattice tám cuboid MRP/MR/MP/RP/M/R/P/tổng, ngân sách lưu trữ, greedy tính lại lợi ích biên; so mô hình chi phí và đo SQL.
- [ ] Nghiệm thu người dùng: cùng người thử Excel và Streamlit, đổi thứ tự, ba tác vụ tương đương; ghi ẩn danh, đúng/sai, giây, trợ giúp.
- [ ] Lưu phiên bản môi trường, thông số, log, `.sqlplan`, ảnh và kết luận có giới hạn; không điền thời gian hay phản hồi người dùng chưa đo.
- [ ] Diễn tập tái lập từ checkout sạch và kịch bản bảo vệ bốn phút.

Điều kiện bàn giao: người khác chạy được theo README; SQL Server/SSIS/SSAS, benchmark và thử người dùng chỉ ghi đạt khi có minh chứng tương ứng. Nếu thời gian sát độ phân giải đồng hồ, kết luận chưa đủ bằng chứng về tốc độ dù plan cho thấy cơ chế hoạt động.
