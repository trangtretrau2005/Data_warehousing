# Chương 2 — Nguồn dữ liệu và quy tắc tích hợp

Người phụ trách: **Thanh**. Dùng `data/raw/Coffee.csv` làm bản nguồn bất biến; tạo bản thử khi cần chèn lỗi.

- [ ] Lưu nguồn tải, ngày tải, tên file, SHA-256, số dòng/cột và phạm vi thời gian thực đọc được.
- [ ] Chứng minh Date là số ngày Excel, mốc `1899-12-30`: 40909 → 2012-01-01. Chuỗi có tần suất tháng, không tạo dữ liệu ngày giả.
- [ ] Kiểm tra thiếu dữ liệu, số âm, dòng trùng hoàn toàn, khóa tháng–mã vùng–sản phẩm trùng và phụ thuộc cha–con.
- [ ] Viết từ điển đủ 20 cột nguồn; ánh xạ 11 số đo, ba chiều và kiểu số chính xác.
- [ ] Đọc Area Code như mã chuỗi; kiểm tra mỗi mã vùng thuộc đúng một State, mỗi State một Market, mỗi Product một Product Type, mỗi Product Type một Product Line.
- [ ] Lưu các chênh `Sales − COGS − Margin` và `Profit − Margin + Total Expenses` thành cờ đối soát; giữ nguyên số nguồn.
- [ ] Lập PivotTable độc lập trên Excel cho toàn chuỗi và West tháng 01/2012.
- [ ] Lưu TN01: profile, checksum, bảng đối soát, ảnh bộ lọc và kết luận grain.

Mốc tham chiếu trong tài liệu gốc, phải tính lại sau khi đổi file:

| Kiểm tra | Giá trị tham chiếu |
| --- | ---: |
| Dòng × cột | 4.248 × 20 |
| Kỳ tháng | 24; 01/2012–12/2013 |
| Dòng mỗi tháng | 177 |
| Market / State / Area Code / Product | 4 / 20 / 156 / 13 |
| Sales / Budget Sales / Profit | 819.811 / 746.160 / 259.543 |
| Profit âm / Inventory âm | 528 / 88 |
| Sales khác COGS + Margin | 2.088 dòng |
| Profit khác Margin − Total Expenses | 2.105 dòng |

Điều kiện bàn giao: hồ sơ nguồn chạy lại được, định nghĩa grain rõ, chưa xóa số âm hay sửa số liệu theo đẳng thức giả định.
