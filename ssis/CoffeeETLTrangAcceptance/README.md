# Bộ nghiệm thu tám ca bằng một lần F5 trong SSDT

**Trạng thái: EXECUTED_PASS —20/11/2026.** Project này tách khỏi `CoffeeETLTrang` và không sửa package gốc. Builder chỉ tạo file; việc thực chạy sau đó đã làm bằng F5 trong SSDT, không gọi trực tiếp DebugHost để vượt lỗi edition.

Mở `CoffeeETLTrangAcceptance.slnx` (hoặc `.dtproj`) trong Visual Studio đã có SSIS Projects. Đặt **`00_AcceptAll.dtsx` làm Startup Object**, rồi **một lần F5 trong SSDT** khi môi trường runtime sẵn sàng. Không dùng trực tiếp DtsDebugHost để vượt lỗi edition của DTExec.

## Kết quả đã xác nhận

- Visual Studio Build 0 lỗi / 0 cảnh báo: [log](../../results/native_build_20261120/ui/ssis_acceptance_build.txt), [ảnh](../../results/native_build_20261120/ui/ssis_acceptance_build.png).
- SuiteID `63d2403b-e12f-495d-a3ce-69efce27f1a6`, ManifestSHA256 `88ba9eac77111bce13451ee5c504a81c699c41cc9d9319cc791d2d85a88645c1`. Native run `2026-11-20T13:41:12.439462Z`→`2026-11-20T13:41:44.562889Z`, receipt parent PASS và đủ tám receipt con.
- [Verification.json](../../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/verification.json): PASS, failures rỗng, Verify-Acceptance.py exit 0 và tám verifier con exit 0. [case_01.json](../../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/case_01.json) đến [case_08.json](../../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/case_08.json) đối chiếu từng raw payload/SourceRow, ngày/khóa/thuộc tính và 11 số đo staging trên dòng hợp lệ. Kho cuối 4248 fact, Sales 819811/Budget746160/Profit259543.
- [Ảnh UI thành công](../../results/native_build_20261120/ui/ssis_acceptance_success.png) và [AX text](../../results/native_build_20261120/ui/ssis_acceptance_success.txt) có `Package execution completed with success`. [Ảnh Data Flow sau chạy](../../results/native_build_20261120/ui/ssis_data_flow_executed_viewport.png) là ảnh viewport với bộ đếm giao diện; không dùng ảnh để chốt tổng. Số dòng đầy đủ đã đối chiếu bằng landing/audit/verifier.
- [Biên bản tổng hợp](../../docs/TRANG_NATIVE_BUILD_20261120.md) có bảng counts từng ca, SCD và SSAS riêng. Manifest/static build verification trong `acceptance_prepared/` giữ nguyên nhãn trước chạy; `acceptance_runs/` mới là bằng chứng thực thi.

- Loader còn có [fault-injection native 12/12 PASS](../../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/verification.json) thực hiện sau suite: lỗi 50006 sau UPDATE dẫn rollback outer transaction; 11 bảng / 47.315 dòng giữ hash logical, không residue, tám receipt gốc không đổi. Đây là T-SQL probe có guard, không phải child thứ 9 hoặc chạy lại suite trên kho đã có dữ liệu. [Final summary](../../results/native_build_20261120/final_summary.json) và [JUnit 141 tests](../../results/native_build_20261120/final_pytest.xml) giữ kiểm tra tích hợp cuối và các giới hạn IDE/UX.

- Sau suite, cube biệt lập đã [đổi Data Source thực sang DB SSIS này và ProcessFull](../../results/native_build_20261120/ssas/integrated_ssis_source/verification.json); 17/17 ca MDX và 6/6 pivot chạy lại đối chiếu SQL mới đạt. Không tính thao tác process/đối soát consumer thành ca CSV thứ 9; tám receipt SSIS giữ nguyên.

## Luồng native

Parent có 18 task và 17 success precedence links:

`Preflight → ExecutePackage Case1 → Verify1 → … → ExecutePackage Case8 → Verify8 → Complete`

Tám Execute Package Task native dùng **UseProjectReference=True**, PackageName trỏ đúng child trong cùng `.ispac`, ExecuteOutOfProcess=False. Chỉ parent là project entrypoint; tám child giữ Data Flow ba thành phần từ package gốc: Flat File → Derived BatchID → OLE DB raw landing.

Mỗi child đã có **BatchID riêng, SHA256 thật, SourceCount thật, tên/đường dẫn fixture và database**. Parent kiểm mỗi batch completed, read=accepted+rejected, inserted/updated/unchanged, reject count, tổng Sales hợp lệ của batch và warehouse rows/Sales/Budget/Profit sau từng bước. Complete chỉ ghi PASS nếu đủ tám receipt. OnError ghi FAILED; không có fallback sang ETL Python.

|Case|Source|Accepted/rejected|Inserted/updated/unchanged|Warehouse rows/Sales|
|---|---|---:|---|---|
|1|23 tháng đầu|4071/0|4071/0/0|4071 /784231|
|2|Thêm 12/2013|177/0|177/0/0|4248 /819811|
|3|Replay 12/2013|177/0|0/0/177|4248 /819811|
|4|Bản đủ, Sales đầu+10|4248/0|0/1/4247|4248 /819821|
|5|Raw gốc phục hồi|4248/0|0/1/4247|4248 /819811|
|6|Bản đủ,1Sales=`abc`|4247/1|0/0/4247|4248 /819811|
|7|8 dòng,2 lỗi|6/2|0/0/6|4248 /819811; batch valid Sales 1139|
|8|Raw gốc cuối|4248/0|0/0/4248|4248 /819811|

Ở case 6/7, các dòng reject đã có bản hợp lệ cũ nên warehouse vẫn đủ 4248; package không xóa fact của các batch trước. Cuối cùng BudgetSales 746160, Profit 259543; nguồn raw giữ nguyên.

## Điều kiện và tái lập

Database mặc định: **`CoffeeDW_Trang_SSIS_TN03_20261120`**. Cần schema/mart/loader và `stg.CoffeeCsvLanding`/validator từ project trước. **Fact phải rỗng trước khi parent chạy.** Preflight từ chối database khác hoặc fact đã có dữ liệu; không tự drop/delete/reset.

DB này hiện đã có 4248 fact sau suite PASS, nên không F5 lại để tái lập từ đầu trên cùng kho. Verifier đọc lại được; một run mới phải có DB thử rỗng và manifest mới theo quy trình dưới đây, không xóa evidence hoặc dữ liệu của run đã chốt.

Tạo lại file cấu hình/package bằng SDK16 đã cài sẵn:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ssis/CoffeeETLTrangAcceptance/Build-Acceptance.ps1
```

Builder tạo GUID mới cho suite, tám BatchID và chín package; đọc checksum/count từ các fixture hiện có, xuất `.ispac`, `.dtsx`, `.dtproj`, `.database`, `.slnx`, manifest và static build verification. Nó không thực thi SQL hay package. Nếu dùng DB thử rỗng khác, chuẩn bị schema riêng trước rồi thêm `-Database CoffeeDW_Trang_<ten_moi>` lúc build; không chỉ đổi parent variable vì child cũng cần cùng database và SQL guard.

Đóng designer trước khi rebuild. Không regenerate manifest giữa lần F5 và verifier; manifest đã dùng được sao lưu theo SuiteID tại `results/native_build_20261120/ssis/acceptance_prepared/`. Nếu chạy lỗi sau khi một phần fact đã nạp, giữ bằng chứng rồi dùng DB thử mới; không xóa dữ liệu để làm như lần trước chưa xảy ra. Nếu lỗi trước khi fact được nạp và fact vẫn rỗng, có thể rebuild GUID mới nhưng vẫn giữ manifest/log cũ.

## Đọc lại bằng chứng sau F5

Sau khi parent chạy, dùng verifier **chỉ đọc**:

```powershell
.\.venv\Scripts\python ssis/CoffeeETLTrangAcceptance/Verify-Acceptance.py
```

Verifier yêu cầu receipt PASS và tám case đúng SuiteID/ManifestSHA256; sau đó đối chiếu mọi raw payload, SourceRow, ngày/khóa và 11 số đo của từng batch với parser nguồn chung. Không có bảng/receipt hoặc chưa restore đủ 4248 thì trả `NOT_EXECUTED_OR_FAILED`, không ghi pass từ cấu trúc project.

Minh chứng cần giữ: manifest theo SuiteID, Output/Progress lúc F5, ảnh parent và child Data Flow có số dòng, audit suite/case/batch/reject, `verification.json` và tám kết quả kiểm từng batch. Các file build chỉ chứng minh đã chuẩn bị native project, không phải Data Flow đã thành công.

## Lịch sử crash và giới hạn ổn định IDE

Trước run thành công, VS Insiders18.13 từng bị BEX64/0xc0000409 quanh F5; xem [chẩn đoán cũ](diagnostics/README.md). Sau suite PASS, VS đóng/crash khi đổi viewport theo phiên UI; event/log mới cần giữ riêng, không lấy crash cũ làm nguyên nhân đã xác định của lần mới. Extension 2.2 đã cài nhưng chưa reboot theo yêu cầu installer. Không diễn giải một run PASS thành IDE ổn định hoàn toàn; không lặp F5 để tạo batch thiếu, tắt kiểm tra license hoặc tự khởi động lại máy từ script.
