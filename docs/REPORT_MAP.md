# Ánh xạ báo cáo sang code và minh chứng

Hai tài liệu gốc được giữ nguyên trong `docs/`: `Bao_cao_Kho_du_lieu_Coffee_Chains.docx` và `Huong_dan_Coffee_Chains_Kaggle.docx`. Báo cáo định hướng bảy chương; sổ tay cung cấp thứ tự thực hành và TN01–TN13. Nhóm có thể bổ sung bài thử, nhưng cần hoàn thành các bước dưới đây và lưu bằng chứng thật.

## Hai phần của dự án

| Phần | Nơi làm việc | Kết quả cần bảo vệ |
| --- | --- | --- |
| Thực nghiệm kiến thức kho dữ liệu | `learning/`, `sql/sqlserver/`, `ssis/`, `ssas/`, `src/coffee_dw/` | Grain, mô hình sao, ETL/audit, SCD, mart/drill-across, OLAP, indexed view, index, partition, HRU |
| Dashboard và AI | `apps/dashboard/`, `src/coffee_dw/forecast.py`, `results/forecast/` | KPI và bộ lọc đúng, truy sâu, CSV đúng phạm vi, dự báo có đối chứng và đánh giá theo thời gian |

SQLite là bản tham chiếu chạy nhanh để phát triển chung. SQL Server là đích triển khai theo báo cáo; các package SSIS và project SSAS phải được nhóm tạo/chạy bằng công cụ native và thu minh chứng riêng. Kết quả trên SQLite không thay cho số đo SQL Server hoặc ảnh SSIS/SSAS.

## Bảy chương và điểm bàn giao

| Chương | Phụ trách | Code/tài sản chính | Bàn giao bắt buộc |
| --- | --- | --- | --- |
| [1. Bài toán và cơ sở lý thuyết](chapters/ch01_thanh.md) | Thanh | Định nghĩa trong `docs/architecture.md` | Câu hỏi quản trị; Inmon/Kimball; OLTP/OLAP; grain; KPI và tính cộng được |
| [2. Nguồn dữ liệu và quy tắc tích hợp](chapters/ch02_thanh.md) | Thanh | `data/raw/Coffee.csv`, `src/coffee_dw/source.py` | Hồ sơ đủ 20 cột, checksum, ngày Excel, phụ thuộc, đối soát nguồn, TN01 |
| [3. Thiết kế kho dữ liệu](chapters/ch03_thanh.md) | Thanh | `sql/sqlserver/00_create_database.sql`, `01_schema.sql`, `src/coffee_dw/warehouse.py` | DDL, PK/FK/UK, sao, bus matrix, mapping, tách–nối giữ số, TN02 |
| [4. ETL và chất lượng](chapters/ch04_chi.md) | Chi | `src/coffee_dw/warehouse.py`, `sql/sqlserver/03_load_staging.sql`, `04_checks.sql`, `ssis/`, `learning/experiments/` | Batch/reject, chạy lại/sửa số/tăng dần, SCD1/2/3, package và log, TN03–04 |
| [5. Phân tích đa chiều](chapters/ch05_chi.md) | Chi | `sql/sqlserver/02_marts.sql`, `ssas/`, `learning/experiments/` | Mart, drill-across không fan-out, cube có phân cấp, slice/dice/pivot/roll-up, TN05–06 |
| [6. Dự báo](chapters/ch06_trang.md) | Trang | `src/coffee_dw/forecast.py`, `results/forecast/` | Baseline/Ridge, validation/test riêng, dự báo có origin/target/version, TN12 |
| [7. Triển khai và đánh giá](chapters/ch07_trang.md) | Trang | `apps/dashboard/app.py`, `sql/sqlserver/05_bench_setup.sql` đến `08_indexes.sql`, `results/` | Web, số đối soát, benchmark, native evidence, UX, tái lập, TN07–11/TN13 |

Tên Trang được dùng theo tên trong báo cáo hiện có; nhóm có thể sửa thông tin thành viên trong tài liệu nếu cần.

## Bao phủ mười bước của sổ tay

| Bước | Công việc | Đầu ra/điều kiện để chuyển bước |
| --- | --- | --- |
| 1 | Chuẩn bị Python, SQL Server, SSMS, SSDT/SSIS, SSAS Multidimensional và nguồn | Ghi phiên bản, hai instance SQL/SSAS; mở được hai mẫu project |
| 2 | Profile nguồn và xác định tần suất | 24 tháng trên bản nguồn hiện tại; kiểm tra khóa và số gốc, không biến doanh số tháng thành ngày |
| 3 | Mô hình sao và mapping | DDL, sơ đồ khóa, 11 số đo, join nhiều–một giữ nguyên tổng |
| 4 | ETL/SSIS | Audit và reject; nạp lại không nhân đôi; sửa số cùng grain có chính sách |
| 5 | Lịch sử và data mart | SCD với ngày biên; mart; hai fact tổng hợp về cùng grain trước drill-across |
| 6 | Cube/SSAS | Dimension Usage đúng; deploy/process; SQL và Browser khớp bộ lọc |
| 7 | Dashboard | KPI, kỳ/Market, State/Product, export CSV và trạng thái rỗng/lỗi |
| 8 | Ba cấu hình truy vấn | EXCEPT hai chiều, plan, IO/TIME, ba warm-up và 15 lượt/biến thể |
| 9 | Dự báo | MAE/RMSE trên cùng kỳ; chọn bằng validation trước test; ghi kết quả có phiên bản |
| 10 | Nghiệm thu và trình diễn | Bảng nguồn–SQL–cube–web, tác vụ quản lý, README tái lập và minh chứng đầy đủ |

MCP/DAB trong sổ tay là phần kết nối tùy chọn sau khi đã có mart. Nếu thử, chỉ công bố tập kết quả đọc và lưu đối soát từng dòng. Chưa có kết nối MCP tới SQL Server trong bộ khung này; không dùng thời gian chatbot trả lời làm thời gian truy vấn.

## Ma trận TN01–TN13

Chi tiết thao tác nằm ở [hướng dẫn thực nghiệm](../learning/README.md). Mỗi hàng có thư mục `results/TNxx/` để lưu phiếu, output, SQL và ảnh khi nhóm thực hiện.

| TN | Nội dung | Chủ trì | Chương | Mốc chấp nhận và bằng chứng |
| --- | --- | --- | --- | --- |
| 01 | Grain và số nguồn | Thanh | 2 | Profile, Pivot, 4.248 dòng; West 01/2012 Sales 10.453/Budget 9.460 |
| 02 | Kiến trúc, dimension/fact và FK | Thanh | 3 | Sơ đồ PK/FK/UK, phép nối giữ số, lỗi FK thật trong transaction rollback |
| 03 | ETL đầy đủ/phát lại/dòng lỗi | Chi | 4 | Audit từng batch; read=accepted+rejected; số/tổng không tăng khi phát lại |
| 04 | SCD Type 1/2/3 | Chi | 4 | Bản thử biệt lập; lookup trước/đúng biên; không overlap; replay không thêm phiên bản |
| 05 | Mart và drill-across | Chi | 5 | 96 nhóm tháng–Market; FULL OUTER JOIN giữ nhóm thiếu; không nhân budget |
| 06 | Cube/OLAP | Chi | 5 | DSV/Dimension Usage/Browser/SQL; slice/dice/pivot/roll-up giữ tổng |
| 07 | Dữ liệu và giao thức benchmark | Trang | 7 | Cấu hình máy, rowcount/checksum/tổng A/B, EXCEPT hai chiều, raw runs |
| 08 | View thường/indexed view | Trang | 7 | Plan đúng đối tượng, logical reads, CPU/elapsed, dung lượng và chi phí ghi |
| 09 | Partition theo tháng | Trang | 7 | RANGE RIGHT, actual partitions truy cập, một tháng và toàn kỳ, cùng index |
| 10 | Nonclustered index | Trang | 7 | Lát cắt hẹp/rộng, selectivity, seek/scan/lookup, median/p95 |
| 11 | Web và tác vụ quản lý | Trang | 7 | West→East→West, drill-down/CSV, tồn theo kỳ, UX Excel/web và ca rỗng/lỗi |
| 12 | Dự báo và baseline | Trang | 6 | Origin trước target, split tường minh, từng dự báo và MAE/RMSE |
| 13 | HRU lựa chọn view | Trang; Thanh hỗ trợ lý thuyết | 7 mở rộng | Lattice tám nút, workload/budget, lợi ích biên theo vòng và đối chiếu SQL |

## Các mốc không được trộn

**Dự báo chính của chương 6:** 15 kỳ lịch sử đầu, sáu kỳ validation 04–09/2013, ba kỳ test 10–12/2013; Ridge dùng ba lag. Chọn một phương pháp theo MAE validation gộp bốn thị trường rồi đánh giá trên test đã giữ lại.

**Ví dụ TN12 của sổ tay:** West, sáu tháng 07–12/2013, feature lag1/lag2/mean3. Đây là phép thử thăm dò khác; số MAE của nó không so trực tiếp với bảng chương 6. Nếu mở rộng, đặt tên protocol và lưu cấu hình riêng.

**Số nguồn và số thực đo:** các giá trị tài liệu cho trước là đáp án đối chiếu, không phải kết quả chạy tại máy của nhóm. Chỉ đánh dấu TN đạt khi có output thật; benchmark/SSIS/SSAS/UX còn cần nhóm thực hiện trên môi trường tương ứng.
