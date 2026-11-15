# SSIS Chương 4 (`ssis/CoffeeETL/`)

Project Integration Services native được xây dựng tại `ssis/CoffeeETL/`:

- `CoffeeETL.dtproj`: Project Visual Studio SSDT (TargetServerVersion `SQLServer2022`).
- `Project.params`: Tham số cấp project (`ServerName`, `DatabaseName`, `SourceFilePath`).
- `LoadCoffee.dtsx`: Package ETL chính thực hiện đăng ký batch, tính SHA-256 checksum, đọc CSV UTF-8 20 cột, chuẩn hóa ngày Excel (`1899-12-30`), phân luồng lỗi (`RejectReason`, `RawJson`) vào `stg.CoffeeRaw`, gọi `EXEC dw.usp_LoadCoffee @BatchID` trong transaction có `sp_getapplock`, và có `OnError` event handler (`EST_OnError_LogFailedBatch`) cập nhật `Status = 'FAILED'` ngoài transaction nếu xảy ra rollback.
- `SCD_TN04.dtsx`: Package thực nghiệm biệt lập cho TN04 (`SCD Type 1`, `Type 2` đóng/mở phiên bản trong cùng transaction với tra cứu biên `[ValidFrom, ValidTo)` và kiểm tra replay bất biến, cùng `Type 3` minh họa giới hạn 2 bước lịch sử).

## Cách chạy thực nghiệm bằng `DTExec.exe` (64-bit)

Sau khi chạy `sql/sqlserver/00_create_database.sql` đến `03_load_staging.sql`:

```powershell
# Chạy nạp chuẩn Coffee.csv
& "C:\Program Files\Microsoft SQL Server\160\DTS\Binn\DTExec.exe" `
  /File "ssis\CoffeeETL\LoadCoffee.dtsx"

# Chạy với một file CSV bất kỳ (ví dụ tải tăng dần, sửa số hoặc dữ liệu lỗi)
& "C:\Program Files\Microsoft SQL Server\160\DTS\Binn\DTExec.exe" `
  /File "ssis\CoffeeETL\LoadCoffee.dtsx" `
  /Set "\Package.Variables[User::SourceFilePath].Properties[Value];C:\path\to\batch.csv"

# Chạy package kiểm thử SCD (TN04)
& "C:\Program Files\Microsoft SQL Server\160\DTS\Binn\DTExec.exe" `
  /File "ssis\CoffeeETL\SCD_TN04.dtsx"
```

## Bằng chứng đã thu

- Kết quả thực chạy 7 batch liên tiếp (23 tháng đầu → thêm 12/2013 → phát lại 12/2013 → sửa số `+10` → ca 8 dòng có 2 lỗi `Sales='abc'` và `Product=''` → nạp chuẩn toàn bộ nguồn → phát lại toàn bộ nguồn) trên `Microsoft SQL Server 2022 (16.0.1000.6)` + `DTExec.exe (16.0.1000.6 64-bit)`:
  - Biên bản: [`results/TN03/chi_2026-11-15/experiment.md`](../results/TN03/chi_2026-11-15/experiment.md)
  - Số liệu JSON: [`results/TN03/chi_2026-11-15/ssis_sqlserver_runs.json`](../results/TN03/chi_2026-11-15/ssis_sqlserver_runs.json)
  - Biên bản SCD TN04: [`results/TN04/chi_2026-11-15/experiment.md`](../results/TN04/chi_2026-11-15/experiment.md) và [`sql/sqlserver/12_tn04_scd_demo.sql`](../sql/sqlserver/12_tn04_scd_demo.sql)
- Phần còn cần khi ghép báo cáo Word: mở `ssis/CoffeeETL/CoffeeETL.dtproj` trong Visual Studio SSDT để chụp ảnh màn hình Control Flow / Data Flow Designer (`TN03_flow.png`).
