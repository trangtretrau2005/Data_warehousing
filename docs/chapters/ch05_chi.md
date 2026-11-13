# Chương 5 — Phân tích đa chiều và kết quả kinh doanh

Người phụ trách: **Chi**. Dùng cùng kỳ và bộ lọc khi đối soát nguồn, SQL, cube và web.

- [ ] Tạo mart tháng–Market, chi tiết State/Product và đầu vào dự báo Market–tháng; đối chiếu theo từng ô, không chỉ tổng toàn chuỗi.
- [ ] TN05: dựng actual và budget độc lập ở cùng grain rồi FULL OUTER JOIN; giữ cờ thiếu, thử một kỳ thiếu budget và một kỳ chỉ có kế hoạch.
- [ ] Minh họa lỗi fan-out nếu nối budget tổng vào actual chi tiết trước khi SUM; không cộng lặp ngân sách.
- [ ] Tạo project SSAS Multidimensional, Data Source/DSV, ba dimension và measure group từ fact; kiểm tra Regular relationships trong Dimension Usage.
- [ ] Phân cấp Year→Quarter→Month có khóa chứa năm, Market→State→Area Code, Product Type→Product.
- [ ] Sales/Budget/Profit dùng SUM; tỷ lệ tính trên tổng; không đưa Inventory vào SUM mặc định xuyên thời gian.
- [ ] Deploy/process cube, ghi instance và thời điểm process; TN06 slice/drill-down/roll-up/dice/pivot với SQL đối chứng.
- [ ] Tháng 01/2012 Central: Sales 10.346, Budget 9.970; cộng sáu bang phải khớp cấp Market.
- [ ] Dice Coffee tháng 01/2012: Central 2.663 + East 2.105 = 4.768; pivot giữ nguyên tổng lát cắt.
- [ ] Phân tích South tháng 08/2013: Sales 4.601, Budget 4.610, Gap −9; xếp sản phẩm theo Gap có dấu tăng dần.
- [ ] Lưu ảnh DSV, Dimension Usage, Browser có bộ lọc, SQL và bảng đối soát nguồn–cube.

Trong lát cắt South 08/2013, Colombian có Gap −268, Decaf Irish Cream −105 và Chamomile +22 theo tài liệu nguồn. Sản phẩm dương có thể bù phần hụt của sản phẩm âm; tổng một vài dòng không đại diện tổng Market.

Điều kiện bàn giao cho Trang: tên view/cột và định nghĩa KPI ổn định, dữ liệu truy vấn đã đối soát; phiên bản SQL Server/SSAS và quyền đọc mart được ghi trong cấu hình cục bộ.
