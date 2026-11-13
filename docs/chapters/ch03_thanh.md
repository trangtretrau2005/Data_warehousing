# Chương 3 — Thiết kế kho dữ liệu

Người phụ trách: **Thanh**. Thiết kế là hợp đồng chung giữa ETL, cube, dashboard và dự báo.

- [ ] Trình bày đủ bốn quyết định Kimball: quy trình, grain, chiều, số đo.
- [ ] Vẽ luồng raw → staging → dimension/fact → mart; nhánh audit/reject và schema bench tách dữ liệu thử tải.
- [ ] Vẽ một fact và ba chiều, ghi PK/FK/UK, quan hệ một–nhiều, BatchID và nguồn của từng cột.
- [ ] Tạo DimDate tháng/quý/năm; DateKey YYYYMMDD và khóa tháng/quý chứa năm.
- [ ] Tạo DimLocation với surrogate key và Area Code/State/Market/Market Size; DimProduct với Product/Product Type/Product Line/Type.
- [ ] Đặt UNIQUE(DateKey, LocationKey, ProductKey), FK và kiểu DECIMAL cho 11 số đo; ghi rõ chính sách sửa số khi nạp lại cùng grain.
- [ ] Tách–nối lại dữ liệu với kiểm tra nhiều–một: giữ 4.248 dòng và Sales 819.811 trên bản nguồn hiện tại.
- [ ] TN02: thử FK không tồn tại trong transaction thử rồi rollback; lưu lỗi thật và sơ đồ vật lý.
- [ ] Lập bus matrix cho fact hiệu quả kinh doanh và dự báo. Actual phải tổng hợp lên Market–tháng trước khi nối forecast.
- [ ] Thống nhất khóa phiên bản forecast: thị trường, kỳ phát hành, kỳ mục tiêu, phiên bản phương pháp.

SCD Type 2 trong TN04 là bộ thử có mã nghiệp vụ ổn định và ngày hiệu lực tự tạo. Nếu áp dụng vào dimension nghiệp vụ, phải bổ sung phiên bản, điều kiện lookup theo khoảng `[ValidFrom, ValidTo)` và ràng buộc một phiên bản hiện hành; không suy lịch sử từ ảnh chụp CSV.

Điều kiện bàn giao cho Chi: DDL, sơ đồ, từ điển mapping, query đối soát một dòng và một ô tổng hợp. Bất kỳ đổi tên cột nào cần cập nhật đồng thời ETL và mart.
