# SSIS Chương 4 (`ssis/CoffeeETL/`)

Chi chủ trì project Integration Services native tại đây. Base ban đầu cung cấp schema/procedure và bản Python tham chiếu; hướng dẫn dưới đây giữ các quy tắc triển khai chung. Dùng Visual Studio/SSDT có phần mở rộng SSIS phù hợp SQL Server của nhóm.

**Đã thực chạy 20/11/2026 trên máy Trang:** bản thích nghi riêng [CoffeeETLTrang](CoffeeETLTrang/README.md) và [CoffeeETLTrangAcceptance](CoffeeETLTrangAcceptance/README.md) Build trong Visual Studio 0 lỗi / 0 cảnh báo. Suite tám ca CSV qua SSDT F5 có đủ tám receipt, [verifier PASS/exit0](../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/verification.json); kho thử `CoffeeDW_Trang_SSIS_TN03_20261120` cuối 4248/Sales819811/Budget746160/Profit259543. SCD package có run riêng PASS. Xem [biên bản](../docs/TRANG_NATIVE_BUILD_20261120.md) để phân biệt lỗi DTExec trước đây, crash IDE sau thành công và giới hạn ảnh viewport; không tự ghi bản trên máy Chi đã chạy.

Data Flow của bản Trang chạy Flat File UTF-8→Derived BatchID→OLE DB raw landing; validator T-SQL chuyển raw landing sang `stg.CoffeeRaw`, giữ reject/raw payload rồi gọi loader. Đây là phương án triển khai thực tế cho các yêu cầu dưới đây, không mô tả ép kiểu/reject đều nằm trong component Data Flow. Tham số của bản Trang là standalone package variables có expression binding, không phải `Project.params` đã bind; xem README riêng trước khi đổi nguồn/DB.

[Rollback native riêng](../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/verification.json) đã đạt 12/12: loader phát lỗi 50006 sau UPDATE rồi rollback outer transaction; 11 bảng / 47.315 dòng giữ hash logical và không residue. Đây là T-SQL probe có guard/không commit business rows, không phải ca CSV thứ 9. [Tổng hợp kiểm tra cuối](../results/native_build_20261120/final_summary.json) giữ kết quả SSIS/SSAS/pytest/CLI và giới hạn IDE tách riêng.

[Cube cuối đã đọc chính DB này](../results/native_build_20261120/ssas/integrated_ssis_source/verification.json), ProcessFull lúc 14:58:07Z và chạy lại 17 ca MDX/pivot 6 ô trên SQL mới đều đạt; đó là minh chứng consumer SSAS sau nạp SSIS. Nguồn native 19/11 và receipt trước tích hợp vẫn được giữ riêng.

## Project của Chi

`CoffeeETL/LoadCoffee.dtsx` trỏ mặc định tới `CoffeeDW`. Package dùng Execute SQL Task để đọc file phía SQL Server bằng `OPENROWSET`/`BULK INSERT`, staging rồi gọi `dw.usp_LoadCoffee`. `CoffeeETLTrang/LoadCoffeeTrang.dtsx` dùng SSIS Pipeline cho CSV raw landing, sau đó kiểm tra bằng T-SQL trước khi gọi loader trên database nghiệm thu riêng. Hai đường nạp cần được kiểm riêng khi đổi máy hoặc đổi database.


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
