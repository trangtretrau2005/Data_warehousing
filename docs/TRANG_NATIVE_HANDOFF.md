# Bàn giao native cho Trang — 19/11/2026

## Phạm vi và nơi lưu

Máy có SQL Server local và Windows Authentication truy cập được. Thực nghiệm dùng **database biệt lập `CoffeeDW_Trang_20261119` trên instance `.`**, không tạo/sửa database `CoffeeDW` hoặc các database ứng dụng khác. SQL01–03 hiện có tạo star, mart và bảng `ml.ForecastSales`; loader dùng chung nạp nguồn CSV. Đây là bằng chứng chạy T-SQL/Python bridge, **không phải bằng chứng package SSIS hay cube SSAS** của Chi.

- [Kết quả TN07–TN10](../results/native_trang/20261119/analysis.md), [báo cáo HTML](../results/native_trang/20261119/report.html).
- [Summary](../results/native_trang/20261119/benchmark_summary.csv), [raw runs](../results/native_trang/20261119/benchmark_runs.csv).
- [Môi trường](../results/native_trang/20261119/environment.json), [audit nạp](../results/native_trang/20261119/load.json).
- [EXCEPT hai chiều](../results/native_trang/20261119/except_two_way.csv), [tổng bảng](../results/native_trang/20261119/table_totals.csv), [dung lượng](../results/native_trang/20261119/storage.csv).
- `results/native_trang/20261119/plans/`: actual `.sqlplan` và Messages IO/TIME của từng lượt.
- [HRU native](../results/native_trang/20261119/hru/protocol.json), [lựa chọn greedy](../results/native_trang/20261119/hru/hru_rounds.csv), [summary SQL](../results/native_trang/20261119/hru/benchmark_summary.csv).

Các output ở `results/` vẫn được ignore. Link chỉ mở được sau khi đã chạy hoặc nhận bộ minh chứng cục bộ. Không sửa ignore để đưa tất cả file lên Git. Trạng thái `measured` trong `environment.json`, đủ raw runs và actual plans là điều kiện xác nhận một run TN07–10 hoàn tất; file hướng dẫn này tự nó không phải số đo.

## Tái lập TN07–TN10

Từ root, dùng venv hiện có; extra `sqlserver` cài `pyodbc` nếu chưa có:

```powershell
.\.venv\Scripts\python -m pip install -e ".[sqlserver]"
.\.venv\Scripts\python scripts/run_native_benchmarks.py --database CoffeeDW_Trang_replay01 --output results/native_trang/replay01
.\.venv\Scripts\python scripts/render_native_report.py results/native_trang/replay01
.\.venv\Scripts\python -m pytest tests/test_native_benchmarks.py -p no:cacheprovider
```

Runner chỉ chấp nhận tên `CoffeeDW_Trang_<run>`, không drop database đã có. Nếu cần tách chuẩn bị và đo:

```powershell
.\.venv\Scripts\python scripts/run_native_benchmarks.py --database CoffeeDW_Trang_replay02 --output results/native_trang/replay02 --phase prepare
.\.venv\Scripts\python scripts/run_native_benchmarks.py --database CoffeeDW_Trang_replay02 --output results/native_trang/replay02 --phase measure
```

`--server` mặc định `.`; `--copies` mặc định 500, chỉ chấp nhận 1–500. Nhãn số dòng trong hình đọc từ cấu hình run. Không chạy lại `measure` ghi đè evidence cũ khi đang viết báo cáo; chọn output mới nếu muốn đo lại. Cần quyền tạo database, tạo schema/bảng/index/view và xem runtime metadata. Không lưu credential trong repo hoặc output.

Giao thức gồm:

1. Tạo star/mart bằng SQL hiện có, nạp CSV bằng quy tắc `coffee_dw.source` và loader SQL Server.
2. Nhân 500 bản trong **bench**: 2.124.000 dòng/bảng, Sales 409.905.500; không dùng dữ liệu nhân tải để học mô hình.
3. Đối soát số dòng/tổng và EXCEPT **đa tập** hai chiều qua `(grain, COUNT_BIG, SUM)`. Điều này kiểm tra cả số bản sao, tránh chỉ EXCEPT dòng phân biệt làm mất thông tin trùng.
4. Chạy sáu cặp: indexed view đọc; partition một tháng/toàn kỳ; NCI lát cắt hẹp/toàn bảng; INSERT có/không indexed view.
5. Mỗi cặp có 3 warm-up/phương án, 15 lượt chính/phương án, AB/BA xen kẽ. Giữ cache tự nhiên; không dùng DBCC dọn cache máy chung.
6. Mỗi lượt lưu **actual STATISTICS XML**, Messages IO/TIME và checksum tập kết quả. Lệch kết quả A/B dừng run. Postcheck sau INSERT xác nhận rollback và tổng không đổi.
7. Tổng hợp median/p95, CPU, logical reads, thời gian client và dung lượng. p95 dùng nội suy tuyến tính pandas; không làm tròn trước tổng hợp.

Lần đầu đối soát gặp `RESOURCE_SEMAPHORE` khi máy nhiều instance SQL và tải nền. Đã hủy đúng session của runner; query đo A/B sau đó cùng dùng **MAXDOP 1, MAX_GRANT_PERCENT=1**. Không thay `max server memory`, dịch vụ hoặc cấu hình hệ thống. Đây là điều kiện thực nghiệm phải ghi trong báo cáo, không phải cấu hình khuyến nghị cho sản xuất.

Thời gian server là `QueryTimeStats` của actual plan (ms), reads là tổng `ActualLogicalReads` được engine ghi ở runtime operators/threads. Messages nguyên gốc được giữ để kiểm tra. Client elapsed đo riêng bao gồm lấy kết quả/plan và instrumentation. INSERT nằm trong transaction rồi rollback: statement elapsed **không** gồm rollback, client elapsed có gồm rollback. Không gọi đây là throughput commit.

## TN13: lựa chọn HRU và đo SQL

Sau benchmark chính, trên cùng database biệt lập:

```powershell
.\.venv\Scripts\python scripts/run_native_hru.py --database CoffeeDW_Trang_replay01 --output results/native_trang/replay01/hru
```

Tạo đủ tám cuboid MRP/MR/MP/RP/M/R/P/ALL để đo cardinality và storage thực, dùng hàm greedy hiện có tính lại lợi ích biên với workload giả định và ngân sách 300 **group-row**. Sau lựa chọn, mỗi truy vấn chỉ dùng view đã chọn có thể trả lời truy vấn đó; nếu không có thì quay về base. Replay sáu cặp workload với 3 warm-up + 15 lượt chính, lưu actual plan và đối chiếu checksum kết quả.

Các materialization HRU là bảng tổng hợp thường trong `bench`, không phải indexed view tự cập nhật. Cardinality/byte và CPU/time SQL là số đo thật; trọng số và ngân sách group-row là giả định. Dữ liệu hiệu năng là nguồn nhân 500 lần; cardinality cuboid bằng nguồn gốc nhưng không coi base 2.124.000 dòng là thêm lịch sử học. Các candidate không được chọn chỉ được tạo để khảo sát; không dùng trong replay phương án B. Chưa đo refresh/maintenance HRU; TN08 có phép đo indexed-view maintenance riêng.

## Tích hợp và phần bàn giao cho Chi

Mart native theo `docs/architecture.md`: `mart.vw_Detail`, `mart.vw_MarketPeriod`, `mart.vw_MarketProductPeriod`; bảng forecast là `ml.ForecastSales`. Root đang kiểm tra consumer/publish forecast trong cùng đợt hoàn thiện. Dùng Windows auth, ODBC18 và trust certificate cục bộ; không đổi `.env` cá nhân. Các ví dụ connection không phải cấu hình bảo mật triển khai sản xuất.

Chi vẫn cần bàn giao project/package native SSIS, project/cube SSAS và minh chứng process/OLAP trên môi trường nhóm. Khi đổi sang mart Chi, chạy lại đối soát từng ô và nghiệm thu dashboard; không nhận database thí nghiệm này là package SSIS/SSAS đã hoàn thành.

## Giới hạn nghiệm thu

- Không suy tốc độ người dùng hoặc phản hồi UX từ số đo SQL.
- Thời gian 0 ms là giới hạn độ phân giải, không phải miễn chi phí hay speedup vô hạn.
- Partition cùng PRIMARY; không kết luận cải thiện phân bố đĩa.
- Covering NCI có thể không xuất hiện Lookup. Chỉ báo operator thực sự có trong actual plan.
- Máy dùng chung, Express và giới hạn query làm kết quả phụ thuộc môi trường; giữ cả p95 và kết quả không cải thiện.
- Kết quả cuối dựa trên raw/plan/manifest thực tồn tại, không dựa trên tên file hoặc đánh dấu kế hoạch.
