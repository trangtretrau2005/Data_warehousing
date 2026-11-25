# CoffeeETLTrang — package SSIS native, 20/11/2026

Đây là bản thích nghi riêng cho máy đang làm việc; **không ghi đè** project Chi trong `.work/review_chi`. Package được dựng và serialize bằng **SSIS SDK16 có sẵn**, có Data Flow thật, không chỉ là Execute SQL hoặc ảnh minh họa.

## Trạng thái thực tế

- Đã build `LoadCoffeeTrang.dtsx` và `CoffeeETLTrang.ispac` bằng ManagedDTS/Pipeline SDK16; builder không tự cài phần mềm. Sau đó SSIS Projects 2.2 được cài riêng vào Visual Studio hiện có, chưa reboot.
- Data Flow: **Flat File Source UTF-8 → Derived Column thêm BatchID → OLE DB Destination**. Đủ 20 cột nguồn dạng chuỗi Unicode; đích có 21 mapping gồm BatchID. Có hai path native.
- Control Flow: đăng ký batch → Data Flow raw landing → ép kiểu/kiểm tra → `dw.usp_LoadCoffee`. OnError đánh dấu batch FAILED ngoài transaction của loader.
- Đã tạo **DB mới, trước đó không tồn tại** `CoffeeDW_Trang_SSIS_TN03_20261120`, nạp schema/mart/loader và DDL bổ sung. Không đụng DB đang phục vụ `CoffeeDW_Trang_20261119`.
- Package control-flow TN04 SCD chạy thành công bằng DTExec160 (exit 0) trên DB thử: synthetic Product P01 và Location A01; assert Type 1 overwrite, Type 2 replay/current/no-overlap/date-boundary, Type 3 giữ một bước; lưu JSON vào `audit.SCDNativeEvidence`. Chạy lại bằng `Run-SCD.ps1`; manifest/log ở [SCD evidence](../../results/native_build_20261120/ssis/scd/6f3301d7-87ff-44c5-a578-76666329f290/manifest.json). Đây chỉ chứng minh logic SCD tổng hợp trong Execute SQL Task, không phải Data Flow CSV.
- **Lịch sử trước khi chạy qua SSDT:** DTExec160 và 150 báo `0xC000F427`, cần Standard Edition trở lên của Integration Services khi chạy ngoài SQL Server Data Tools. DTExec120 cũng dừng cùng mã lỗi. Đã giữ log FAILED, không bypass license hoặc đổi quyền/cấu hình.
- Trong ba lần thử DTExec đó, Execute SQL đăng ký batch và OnError thực chạy được; ba batch có Status FAILED và fact/raw landing còn 0 ở snapshot đó. Đây là lịch sử, không phải số dòng sau nghiệm thu UI mới.
- **Kết quả 20/11/2026:** project chính và [suite Acceptance](../CoffeeETLTrangAcceptance/README.md) Build trong Visual Studio 0 lỗi / 0 cảnh báo; tám ca CSV chạy thật bằng SSDT F5, [verifier PASS/exit0](../../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/verification.json), đủ tám receipt và kho cuối 4248/Sales819811/Budget746160/Profit259543. [Ảnh thành công](../../results/native_build_20261120/ui/ssis_acceptance_success.png) có thông báo package success. [Ảnh Data Flow sau chạy](../../results/native_build_20261120/ui/ssis_data_flow_executed_viewport.png) là ảnh viewport với bộ đếm giao diện; không dùng ảnh để chốt tổng. Số dòng đầy đủ đã đối chiếu bằng landing/audit/verifier. Xem [biên bản](../../docs/TRANG_NATIVE_BUILD_20261120.md) cho counts từng ca và hash manifest.
- Bộ kiểm tra live SQL riêng đối chiếu parser, 11 số đo, ngày Excel, dimension, raw payload, duplicate/conflicting-parent/reject; mỗi ca rollback. **Đây là kiểm tra T-SQL, không thay chứng cứ SSIS.**

- **Rollback fault-injection đã đạt riêng:** [12/12 kiểm tra native](../../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/verification.json), [runner/giới hạn](../../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/README.md) và [5 safeguards tests](../../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/unit_tests.xml). Lỗi 50006 dòng 74 xảy ra sau UPDATE dimension/fact; transaction 1→0 trong CATCH, `XACT_STATE()=0`; 11 bảng / 47.315 dòng giữ nguyên hash logical, không residue hoặc commit business rows. Đây không phải ca SSIS thứ 9; nguồn và tám receipt CSV vẫn giữ nguyên. [Final summary](../../results/native_build_20261120/final_summary.json) có JUnit 141 tests đạt và các kiểm tra CLI/frontend riêng.

Chi tiết thực chạy ở [evidence](../../results/native_build_20261120/ssis/), [audit khởi tạo](../../results/native_build_20261120/ssis/initialize.json), [JUnit](../../results/native_build_20261120/ssis/sql_regression.xml). Các tệp output vẫn được Git ignore.

**Consumer SSAS đã tích hợp nguồn mới:** [verification cuối](../../results/native_build_20261120/ssas/integrated_ssis_source/verification.json) xác nhận Data Source của `CoffeeCube_Trang_20261120` trỏ chính DB vừa nạp SSIS, ProcessFull lúc 14:58:07Z; 17/17 MDX và 6/6 pivot so SQL mới đạt. Service AS chỉ CONNECT+SELECT bốn bảng, không thay DB native 19/11 hoặc cube cũ. Đây là phép tích hợp sau suite, không thêm child/batch CSV.

## Cấu trúc và hợp đồng

`stg.CoffeeRaw` hiện có là staging **đã chuẩn hóa**, có kiểu date/decimal, nên không thể đổ 20 chuỗi gốc trực tiếp vào đó. Data Flow mới đổ vào `stg.CoffeeCsvLanding`, sau đó `stg.usp_ValidateCoffeeLanding` tạo đủ dòng hợp lệ/lỗi trong `stg.CoffeeRaw`; loader hiện có nạp dimension trước fact và chuyển lỗi sang `audit.RejectedRow`. Không đổi schema serving/mart.

Raw landing giữ 20 giá trị gốc và BatchID; LandingID tăng theo luồng duy nhất. Destination ở chế độ row-by-row, không Sort/Multicast/asynchronous transform; SourceRow được đánh lại theo thứ tự LandingID trong từng batch, bắt đầu 2. `Verify-NativeBatch.py` kiểm **mọi raw JSON và SourceRow so với CSV** sau mỗi lần chạy để không chỉ giả định đúng thứ tự.

Các cột nguồn giữ dạng `DT_WSTR`, length 1024; bản nguồn thực nằm trong giới hạn này. Nếu nguồn khác có trường quá dài, package phải lỗi rõ, không cắt hoặc đổi thành 0. Native numeric parser dùng số thập phân chính xác (không qua float), kiểm scale/range như nguồn tham chiếu; giữ Profit/Inventory âm và chênh đẳng thức kế toán. Ngày Excel dùng `1899-12-30`, chỉ nhận đầu tháng. Duplicate grain và parent conflict loại cả nhóm, không lấy tùy tiện một dòng.

Phạm vi lexical kiểm chứng là số ASCII thập phân/scientific, dấu, underscore và whitespace Unicode trong bộ regression; không tuyên bố đã nghiệm thu mọi dạng CSV/numeric Unicode có thể có. Hành vi Flat File với quoted/multiline bất thường ngoài bộ tám ca vẫn cần ca native thêm.

## Dựng lại package

Từ root, dùng **Windows PowerShell 5.1 64-bit** và SDK16 đã cài sẵn:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ssis/CoffeeETLTrang/Build-CoffeeETL.ps1
.\.venv\Scripts\python ssis/CoffeeETLTrang/Prepare-Fixtures.py
.\.venv\Scripts\python -m pytest tests/test_ssis_native_package.py -p no:cacheprovider
```

Builder chỉ đọc raw, compile C# vào `results/`, xuất `.dtsx` và `.ispac`; **không Execute package**. `.dtsx` ngoài và trong `.ispac` do builder xuất là cùng bytes. `CoffeeETLTrang.dtproj` đã mở designer và Build trong Visual Studio với extension2.2; các child giữ cùng Data Flow đã thực chạy trong suite Acceptance tám ca. `.ispac` được SDK tạo thật, target SQLServer2022 và package EntryPoint=1. Khi designer serialize lại file, giữ artifact/manifest đúng phiên đã chạy, không dùng equality của bản build cũ để thay hash phiên mới.

Sau khi build, `Sync-CoffeeETLProject.ps1` lấy `@Project.manifest` thật từ `.ispac` vào `<DeploymentModelSpecificContent><Manifest>…</Manifest></DeploymentModelSpecificContent>` trong `.dtproj`, và đồng bộ danh sách package. Không để `<Manifest />` rỗng: SSDT cần manifest có metadata package để mở/serialize project. Test đối chiếu XML manifest đã chuẩn hóa với bản trong ispac.

**Chế độ tham số hiện tại là standalone package variables**, không giả rằng `Project.params` có binding. `Project.params` do SDK tạo đang rỗng. Các biến `User::ServerName`, `DatabaseName`, `SourceFilePath` có expression binding tới connection managers; `BatchID`, `SourceChecksum`, `SourceFileName`, `SourceCount` được launcher cấp mỗi lần.

Default cho lần F5 đầu là raw snapshot gốc, SHA thật được builder đọc từ bytes, BatchID mới lúc build, count 4248 và DB mới ở trên. Nếu F5 lại mà giữ nguyên BatchID thì audit PK sẽ từ chối; dùng launcher hoặc đặt GUID mới. Khi đổi nguồn, phải cập nhật đồng thời SHA/count/tên nguồn; không chỉ đổi đường dẫn rồi giữ audit cũ. Launcher thực hiện các việc đó tự động và giữ source hash trước/sau.

## Chạy khi đã có môi trường SSIS hợp lệ

Các lệnh sau **có ghi DB**. Chỉ chạy vào DB thử đã chuẩn bị, không chạy trên serving hoặc database có công việc của người khác:

```powershell
# Chỉ chạy một lần; script từ chối nếu DB thử đã tồn tại, không drop/recreate.
.\.venv\Scripts\python ssis/CoffeeETLTrang/Initialize-NativeDb.py

# Sau khi runtime/SSDT hợp lệ: chạy một package, tạo GUID/SHA/count mới và log riêng.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ssis/CoffeeETLTrang/Run-CoffeeETL.ps1 -SourceFile results/native_build_20261120/ssis/fixtures/first_23_months.csv

# Toàn bộ protocol, đòi hỏi fact ban đầu rỗng:
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ssis/CoffeeETLTrang/Run-ScenarioSuite.ps1
```

`Initialize-NativeDb.py` đã chạy một lần tại máy này; không chạy lại để xóa lịch sử. Nếu cần DB thử khác, chọn tên mới và điều chỉnh initializer sau khi kiểm tra tồn tại. Không drop database đang có.

Scenario suite fail-fast, không tự chuyển sang Python ETL khi Data Flow lỗi. Thứ tự và đáp án:

| Bước | Input | Accepted/rejected | Warehouse kỳ vọng |
|---|---|---|---|
|1|23 tháng đầu|4071/0|4071 dòng, Sales 784231|
|2|Thêm 12/2013|177/0|4248 dòng, Sales 819811|
|3|Phát lại 12/2013|177/0|Giữ4248/819811; không insert/update|
|4|Bản đầy đủ sửa Sales dòng đầu+10|4248/0|4248 dòng, Sales 819821; đúng 1update|
|5|Raw gốc|4248/0|4248 dòng, Sales 819811; khôi phục đúng 1update|
|6|Đầy đủ 4248 dòng,1Sales=`abc`|4247/1|Giữ4248/819811 do bản hợp lệ cũ vẫn có trong fact|
|7|8 dòng:1Sales=`abc`,1Product rỗng|6/2|Batch valid Sales 1139; warehouse vẫn 4248/819811|
|8|Raw gốc lần cuối|4248/0|4248 dòng, Sales 819811, Budget 746160, Profit 259543|

Sau từng batch, `Verify-NativeBatch.py` đối chiếu raw payload, số dòng, khóa, ngày và đủ 11 số đo với `coffee_dw.source`. Ví dụ thay GUID thực trong manifest:

```powershell
.\.venv\Scripts\python ssis/CoffeeETLTrang/Verify-NativeBatch.py --source data/raw/Coffee.csv --batch-id <GUID-thuc> --database CoffeeDW_Trang_SSIS_TN03_20261120 --output results/native_build_20261120/ssis/verification.json
```

## Regression T-SQL riêng

```powershell
$env:COFFEE_DW_NATIVE_TEST_DATABASE='CoffeeDW_Trang_SSIS_TN03_20261120'
.\.venv\Scripts\python -m pytest tests/test_pipeline.py tests/test_learning.py tests/test_forecast.py tests/test_ssis_native_package.py tests/test_ssis_sql_validation.py -p no:cacheprovider --junitxml=results/native_build_20261120/ssis/sql_regression.xml
```

Live tests chỉ nhận tên DB biệt lập; mỗi test tự rollback audit/landing/staging/fact do chính test tạo. Không dọn dữ liệu của lần chạy trước. Không có biến môi trường thì bảy test live được skip rõ, không ghi PASS giả. Kết quả cần đọc JUnit thực của lần chạy.

SCD native có bằng chứng riêng. Lỗi edition của CSV khi chạy DTExec ngoài SSDT không ngăn Execute SQL package SCD chạy; CSV sau đó đã có suite PASS qua SSDT. Giữ hai receipt riêng, không dùng PASS của phần này để suy phần kia.

## Phần cần làm tiếp

1. Giữ suite manifest, tám receipt/case verifier, Output/ảnh thành công và lịch sử FAILED. Không F5 lại suite trên DB đã có 4248 fact; preflight đòi DB thử ban đầu rỗng. [Verification.json](../../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/verification.json) là kết quả cuối cho suite hiện tại.
2. Nếu cần tái lập từ đầu, dùng DB thử mới và manifest mới theo README Acceptance. Không nâng quyền admin hoặc gọi trực tiếp DebugHost để chữa lỗi edition. Không đổi snapshot nguồn.
3. IDE đã đóng/crash sau thành công lúc đổi viewport theo phiên UI; giữ log/event lần đó riêng. Chưa reboot sau cài extension nên cần hoàn tất yêu cầu restart khi người dùng sẵn sàng, rồi nghiệm thu độ ổn định riêng. Một run native PASS không chứng minh IDE hết crash; ảnh viewport không thay số hàng đầy đủ trong audit.
