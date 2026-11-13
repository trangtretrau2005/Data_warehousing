# Phần 1 Thực nghiệm kiến thức kho dữ liệu

Đây là không gian học và kiểm chứng theo báo cáo. Dùng chung `src/coffee_dw` để tránh mỗi thành viên làm một bản định nghĩa KPI. Tài liệu từng chương và tiêu chí hoàn thành ở [REPORT_MAP](../docs/REPORT_MAP.md).

## Thực nghiệm có code chạy cục bộ

Từ root, sau setup:

```powershell
.\.venv\Scripts\python -m coffee_dw.cli demo
.\.venv\Scripts\python learning/experiments/incremental.py
.\.venv\Scripts\python learning/experiments/scd.py
.\.venv\Scripts\python learning/experiments/hru.py
.\.venv\Scripts\python -m coffee_dw.cli forecast
```

Output trong `results/TN01`, `TN03`, `TN04`, `TN13` và `forecast`. Thử tăng dần tạo CSV/database tạm, không sửa nguồn hoặc kho dashboard. SCD dùng dữ liệu mô phỏng P01, không khẳng định nguồn đã có thay đổi phân loại. HRU dùng số nhóm thật, trọng số workload và ngân sách group-row giả định; không coi đó là số byte hay tốc độ SQL Server.

## Quy trình TN01–TN13

Mỗi TN sao chép `results/templates/experiment.md`, ghi commit, engine, input, ngày/người và đường dẫn minh chứng. Tên ảnh theo TN giúp ghép lại Word.

| TN | Thao tác và code khởi đầu | Kết quả cần thu |
| --- | --- | --- |
| TN01 | Chạy profile, kiểm tra ngày Excel và unique grain; Pivot độc lập cùng bộ lọc | 4248 dòng, 24 tháng, 11 số đo, cảnh báo, West 01/2012=10453/9460 |
| TN02 | Chạy SQL 00–01, xem PK/FK; thử INSERT khóa chiều không tồn tại trong transaction rồi rollback | Sơ đồ sao, lỗi FK thật và tổng sau join bằng nguồn |
| TN03 | Chạy demo/incremental; SQL 03–04 và SSIS; lỗi Sales abc/Product rỗng ở bản thử | 4071→4248→4248; sửa một số tăng Sales10; 6 hợp lệ/2 lỗi, Sales1139 |
| TN04 | `experiments/scd.py`; triển khai lại với SSIS/SQL Server | Type1 sửa typo; Type2 lookup tháng12/2012→key1,01/2013→key2; replay không thêm; Type3 chỉ giữ một bước |
| TN05 | SQL02 mart, [11_tn05_budget_demo.sql](../sql/sqlserver/11_tn05_budget_demo.sql) và [10_drill_across.sql](../sql/sqlserver/10_drill_across.sql); aggregate hai phía trước nối | 96 tháng–Market, đối soát từng ô, nhóm thiếu vẫn hiện, không nhân actual/budget |
| TN06 | Làm theo [SSAS](../ssas/README.md), mở Browser/MDX/SQL cùng kỳ | Slice/dice/drill-down/roll-up/pivot, Central01/2012=10346 và tổng bang khớp |
| TN07 | SQL05 tạo bản thử 500 bản sao; ghi máy, engine, N và SUM | 2124000 dòng, cùng dữ liệu A/B; kiểm tra tương đương trước đo |
| TN08 | SQL06 + SQL09; A EXPAND VIEWS, B NOEXPAND | Actual plan đúng đối tượng, IO/TIME, dung lượng và chi phí duy trì khi ghi |
| TN09 | SQL07; cùng heap/index, một tháng và cả khoảng | Số partition thực truy cập, I/O; 23 biên RANGE RIGHT→24 partition |
| TN10 | SQL08; lát cắt 719/Amaretto và đối chứng rộng | Selectivity, Seek/Scan/Lookup, giữ nguyên tham số, hai chiều EXCEPT |
| TN11 | Dashboard West→East→West; drill sản phẩm và xuất CSV; test tồn kho | KPI/bộ lọc đúng, ca rỗng/offline, ảnh và UX Excel/web thật |
| TN12 | Forecast theo protocol chính 15/6/3; đối chiếu từng prediction | Validation chọn model, test độc lập, lag không rò rỉ, origin/version, tháng01/2014 chưa có actual |
| TN13 | `experiments/hru.py`; lattice MRP/MR/MP/RP/M/R/P/ALL | Lợi ích biên tính lại sau mỗi vòng, ngân sách còn lại; tạo view và đo SQL để kiểm chứng |

Sổ tay còn có ví dụ TN12 thăm dò West sáu tháng cuối, Ridge lag1/lag2/mean3. Đó là protocol khác chương6. Đặt thư mục kết quả riêng nếu thử; không trộn MAE hai lịch kiểm định.

## Giao thức hiệu năng

Đối soát hai chiều EXCEPT có khóa nhóm duy nhất, số dòng và tổng trước khi đo. Ba lượt làm nóng, 15 lượt đo mỗi cấu hình, xen kẽ AB/BA. Dùng cùng dữ liệu, engine, cache policy, kiểu tham số và bộ lọc; ghi elapsed/CPU ms, logical reads, dung lượng và actual plans. Không dọn cache của server dùng chung.

Copy mẫu `benchmark_runs.csv` vào thư mục TN, điền số thật, rồi chạy:

```powershell
python scripts/summarize_benchmarks.py results/TN08/benchmark_runs.csv
```

Kết quả median và p95 không tự chứng minh cấu hình tốt hơn ở mọi workload. Nếu thời gian sát độ phân giải, ghi giới hạn; partition bị bỏ qua không đồng nghĩa tiết kiệm thời gian theo cùng tỷ lệ. TN08 phải đo thêm duy trì khi INSERT/UPDATE trên hai bản sao cùng trạng thái và rollback sau đo.

## Các hướng thử thêm

Sau khi hoàn thành checklist có thể bổ sung late-arriving dimension/unknown member; CDC và watermark; columnstore so với rowstore; aggregate snapshot; OLTP/OLAP workload; snowflake so với star; phân quyền chỉ đọc mart; incremental cube process. Mỗi hướng cần câu hỏi, đối chứng, phạm vi dữ liệu và minh chứng riêng. Chưa có code cho các mục mở rộng này trong base.
