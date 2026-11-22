# Bàn giao native SSIS/SSAS — 20/11/2026

Tài liệu này ghi riêng đợt dựng native trên máy Trang, bổ sung cho [bàn giao SQL Server ngày 19/11](TRANG_NATIVE_HANDOFF.md). Đây là bản thích nghi từ tài sản Chi để chạy trên môi trường biệt lập; không thay lịch sử công việc hoặc project gốc trong `.work/review_chi`. Trạng thái dưới đây là mốc đã có bằng chứng khi rà soát ngày 20/11/2026, không tự cập nhật theo phiên Visual Studio đang mở.

**Kết luận hiện tại:** SSAS đã deploy/process và đạt 17/17 ca MDX đối chiếu SQL. Hai project SSIS đã build thành công; package SCD đã chạy PASS riêng. **Bộ tám ca CSV Data Flow đã chạy native trong SSDT, đủ tám receipt và verifier PASS (exit 0)**; kho thử cuối có 4.248 fact, Sales 819811, BudgetSales 746160, Profit 259543. SQL chỉ đọc bổ sung đạt 39 phép kiểm về khóa/JOIN/11 tổng, ba mart và TN05 bằng CTE; rollback fault-injection native đạt riêng 12/12. Browser đã có slice/drill/dice, pivot native đạt 6/6 ô dù Query Designer UI chặn đổi trục. [Tổng hợp máy đọc được](../results/native_build_20261120/final_summary.json) ghi `PASS_WITH_RECORDED_IDE_LIMITATIONS`; UX người thật vẫn chưa được thực hiện.

## 1. Phạm vi và môi trường

| Thành phần | Đích/phạm vi | Trạng thái có bằng chứng |
|---|---|---|
| SSIS Projects | Visual Studio 18 Insiders hiện có; extension SQL Server Integration Services Projects 2022+ v2.2 | Đã cài, mở designer và Build được. Installer yêu cầu restart; phiên này chưa reboot |
| SSIS CSV | SQL Server `.`, DB `CoffeeDW_Trang_SSIS_TN03_20261120` | Tám ca native PASS; tám receipt, verifier exit 0; kho cuối 4248 và các tổng gốc |
| SSIS SCD/TN04 | DB thử trên; P01/A01 mô phỏng biệt lập | DTExec160 exit 0, assertions PASS |
| SSAS | `localhost\TRANGTRETRAU`, DB mới `CoffeeCube_Trang_20261120`, cube `[Coffee Performance]` | `Processed`; 17/17 ca MDX–SQL đạt |
| Nguồn SSAS cuối | SQL Server `.`, DB `CoffeeDW_Trang_SSIS_TN03_20261120` vừa được SSIS nạp | AlterDataSource/ProcessFull đạt; 17 ca và pivot 6 ô chạy lại trên nguồn mới |
| Cube cũ | `MySalesCube` | `final_acceptance.json` xác nhận được giữ nguyên và vẫn Processed |

Nguồn `data/raw/Coffee.csv` được đọc lại SHA-256 là `929bdcc7fd8f6bf21607618e7474df0683af6412b32b8c5af39a40e89b62ffce`, trùng hash trong bằng chứng SSIS/SSAS. Các fixture sửa số, dòng lỗi và SCD là dữ liệu thử riêng; không phải thay đổi lịch sử kinh doanh thật.

Extension được cài vào `C:/Program Files/Microsoft Visual Studio/18/Insiders/Common7/IDE/CommonExtensions/Microsoft/SSIS/extension.vsixmanifest`; manifest có Identity `193F609A-0084-45AA-AA5D-33BCBFAFC11E`, Version `2.2`, Publisher `Microsoft`. [Xác minh installer](../results/native_build_20261120/install/installer_verification.json) ghi chữ ký Authenticode Valid của Microsoft Corporation và SHA-256. [Kết quả setup](../results/native_build_20261120/install/setup_result.txt) có `Apply complete, result: 0x0, restart: Required` và `restarting: No`. Cài extension thành công không đồng nghĩa mọi phiên F5 đã chạy thành công; cần giữ riêng kết quả sau reboot khi có.

## 2. SSAS đã thực chạy

Project riêng ở [ssas/CoffeeCubeTrang](../ssas/CoffeeCubeTrang/README.md). SSAS server version `17.0.25.218`. Lần đầu process lúc `2026-11-20T08:11:51.936667Z` dùng nguồn `CoffeeDW_Trang_20261119`; đó là mốc lịch sử. **Lần chốt tích hợp ProcessFull lúc `2026-11-20T14:58:07.690Z` (21:58:07 Bangkok) đọc chính `CoffeeDW_Trang_SSIS_TN03_20261120` đã nạp qua SSIS.** [Migration](../results/native_build_20261120/ssas/integrated_ssis_source/migration.json) và [verification cuối](../results/native_build_20261120/ssas/integrated_ssis_source/verification.json) xác nhận nguồn deploy thật, trạng thái Processed, 11 số đo/Inventory LastChild và cấu hình lỗi nghiêm của ba chiều. [Quyền nguồn mới](../results/native_build_20261120/ssas/integrated_ssis_source/permissions_after.json) chỉ CONNECT+SELECT bốn bảng cho service identity, không role DB/server rộng; source cũ và cube cũ giữ nguyên.

Bằng chứng đã kiểm tra có thật:

- [17/17 ca trên SQL mới](../results/native_build_20261120/ssas/integrated_ssis_source/comparison.json) và [pivot 6/6 ô trên nguồn mới](../results/native_build_20261120/ssas/integrated_ssis_source/pivot_acceptance/verification.json). [Verification tích hợp](../results/native_build_20261120/ssas/integrated_ssis_source/verification.json) còn so đủ 4.248 business rows/all thuộc tính/11 số đo và 96 ô tháng–Market, raw và `MySalesCube` không đổi. Đây là bằng chứng nối SSIS→SQL→SSAS, không suy từ hai bản dữ liệu chỉ giống tổng.
- [Final acceptance đầu đợt](../results/native_build_20261120/ssas/final_acceptance.json): status `passed`, database `Processed`,17 passed,0 failed trên nguồn cũ; giữ nguyên để truy lịch sử.
- [Deploy/process ban đầu](../results/native_build_20261120/ssas/deploy_process.json), [metadata trước chuyển nguồn](../results/native_build_20261120/ssas/final_environment.json) và [quyền nguồn cũ](../results/native_build_20261120/ssas/source_read_permissions.txt).
- [Bảng so sánh](../results/native_build_20261120/ssas/comparison.json); thư mục [MDX thực nhận](../results/native_build_20261120/ssas/mdx_actual/) có 17 CSV, [SQL kỳ vọng](../results/native_build_20261120/ssas/sql_expected/) có 17 CSV tương ứng.
- [Các truy vấn nghiệm thu](../ssas/CoffeeCubeTrang/acceptance_cases.mdx) và [manifest ca](../results/native_build_20261120/ssas/acceptance_cases.json) giúp đọc lại bộ lọc và đáp án.
- Ảnh UI [DSV đủ 4 bảng (mốc 21:34)](../results/native_build_20261120/ui/ssas_dsv_final.png), [Dimension Usage](../results/native_build_20261120/ui/ssas_dimension_usage.png), [Cube Structure](../results/native_build_20261120/ui/ssas_cube_structure.png). [Build ban đầu](../results/native_build_20261120/ui/ssas_build_initial.txt) là 0 lỗi / 11 cảnh báo; [Build sau tích hợp lúc 22:17](../results/native_build_20261120/ui/ssas_integrated_build.txt) và [ảnh](../results/native_build_20261120/ui/ssas_integrated_build.png) là **0 lỗi / 8 cảnh báo**, vẫn còn cảnh báo provider/attribute best practices.
- Browser có [slice 01/2012](../results/native_build_20261120/ui/ssas_integrated_browser_slice_201201.png), [drill State Central](../results/native_build_20261120/ui/ssas_integrated_browser_central_states.png), [dice Coffee Central+East](../results/native_build_20261120/ui/ssas_integrated_browser_dice_coffee.png), kèm file `.txt` cùng tên chứa query WHERE/filter và kết quả. Central Sales 10346/Budget9970; dice Sales 2663+2105=4768.
- [Query Designer UI chặn pivot](../results/native_build_20261120/ui/ssas_browser_pivot_designer_limit.png) vì axis đầu phải là Measures. [Hai MDX gốc/đổi trục](../results/native_build_20261120/ssas/integrated_ssis_source/pivot_acceptance/) đã chạy bằng ADOMD ExecuteCellSet SELECT: [6/6 ô khớp SQL, transpose chính xác](../results/native_build_20261120/ssas/integrated_ssis_source/pivot_acceptance/verification.json). Đây là pivot native PASS, không phải pivot UI PASS.
- [Read-only recheck trước chuyển nguồn](../results/native_build_20261120/ssas/readonly_recheck/verification.json) so 4.248 business keys, 11 số đo và 96 ô tháng–Market giống nhau giữa DB nguồn cube cũ và DB SSIS. Có 177 SourceRow tháng 12/2013 khác do lineage theo file/batch, cũng được ghi lại trong verification tích hợp cuối; không nhầm thành khác business data. Việc đổi Data Source đã được xác nhận bằng migration thật, không suy từ parity.

Các ca không chỉ kiểm tổng: có lát cắt/drill State West và Central 01/2012, dice Coffee Central+East, South 08/2013 theo Gap có dấu, tỷ lệ nhiều kỳ/nhiều Market, mẫu ngân sách bằng0 và Inventory đa kỳ. Inventory physical measure dùng **LastChild**, không phải LastNonEmpty: lấy tháng cuối trong tập được chọn, kể cả tháng đó thiếu dòng cho sản phẩm/địa bàn đang lọc. Ca tháng cuối thiếu actual trả NULL, không quay về Inventory 1091 trước đó. Các chiều dùng lỗi Duplicate/NotFound/NullKey `ReportAndStop`; Quarter key chứa năm. Phạm vi xác nhận là 17 ca này trên snapshot hiện có, chưa phải kiểm mọi tập MDX có thể tạo ra.

Ảnh Browser chính ở trên được thu **sau tích hợp nguồn SSIS**. Các ảnh [slice cũ](../results/native_build_20261120/ui/ssas_browser_slice_201201.png), [drill cũ](../results/native_build_20261120/ui/ssas_browser_central_states.png), [dice cũ](../results/native_build_20261120/ui/ssas_browser_dice_coffee.png) lúc 21:18–21:26 và [Build 21:07](../results/native_build_20261120/ui/ssas_build_final.txt) vẫn giữ theo lịch sử trước chuyển nguồn. Ảnh DSV 21:34 mô tả cấu trúc bốn bảng; migration xác nhận cấu trúc đó không đổi sau rewire. Ảnh giới hạn pivot UI cũng thuộc phiên trước chuyển nguồn; phép pivot ADOMD cuối đã chạy lại trên nguồn mới.

## 3. SSIS đã build và thực chạy tám ca CSV

Project [CoffeeETLTrang](../ssis/CoffeeETLTrang/README.md) có Data Flow native **Flat File Source UTF-8 → Derived Column thêm BatchID → OLE DB Destination**; 20 cột nguồn dạng chuỗi và 21 mapping đích gồm BatchID. Raw landing đi qua validator T-SQL rồi `dw.usp_LoadCoffee`, với batch/audit/reject và OnError riêng. Việc dùng validator/loader SQL sau Data Flow phải được trình bày đúng trong sơ đồ; không mô tả tất cả ép kiểu và reject đều là component Data Flow.

- [Build project chính](../results/native_build_20261120/ui/ssis_build.txt): 0 errors, 0 warnings; [ảnh Build](../results/native_build_20261120/ui/ssis_build.png).
- [Ảnh Control Flow](../results/native_build_20261120/ui/ssis_control_flow.png) và [Data Flow](../results/native_build_20261120/ui/ssis_data_flow.png) chứng minh designer đã mở. Sau F5 có [ảnh native thành công](../results/native_build_20261120/ui/ssis_acceptance_success.png) và [AX text](../results/native_build_20261120/ui/ssis_acceptance_success.txt) với `Package execution completed with success`. [Ảnh Data Flow sau chạy](../results/native_build_20261120/ui/ssis_data_flow_executed_viewport.png) là ảnh viewport với bộ đếm giao diện; không dùng ảnh để chốt tổng. Số dòng đầy đủ đã đối chiếu bằng landing/audit/verifier.
- [Bộ nghiệm thu CoffeeETLTrangAcceptance](../ssis/CoffeeETLTrangAcceptance/README.md): parent 18 task/17 success link, tám Execute Package Task gọi tám child có Data Flow thật. [Build trong Visual Studio](../results/native_build_20261120/ui/ssis_acceptance_build.txt) và [ảnh](../results/native_build_20261120/ui/ssis_acceptance_build.png): 0 errors, 0 warnings.
- [Manifest suite đã chuẩn bị](../results/native_build_20261120/ssis/acceptance_prepared/63d2403b-e12f-495d-a3ce-69efce27f1a6/acceptance_manifest.json) và [static build verification](../results/native_build_20261120/ssis/acceptance_prepared/63d2403b-e12f-495d-a3ce-69efce27f1a6/build_verification.json) giữ nguyên trạng thái lịch sử `PREPARED_NOT_EXECUTED` của bước build. Kết quả chạy được ghi riêng trong [verification.json](../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/verification.json): `PASS`, `failures=[]`, đủ tám receipt và tám verifier con exit 0. Không sửa bằng chứng trước chạy để làm như đã chạy từ đầu.

Các lần DTExec120/150/160 trước đây đều thất bại Data Flow với `0xC000F427` (yêu cầu edition khi chạy ngoài SSDT); giữ [snapshot trước SSDT](../results/native_build_20261120/ssis/readonly_diagnostics/post_2045_20261120T2100/status_before_ssdt_acceptance.json), [run logs](../results/native_build_20261120/ssis/runs/) và [chẩn đoán](../ssis/CoffeeETLTrangAcceptance/diagnostics/README.md). Sau cài extension 2.2, suite chạy thành công qua F5 trong SSDT; không gọi trực tiếp DebugHost để vượt edition. [status.json tổng hợp](../results/native_build_20261120/ssis/status.json) đã cập nhật `PASS_SSDT_EIGHT_CASES`, fact 4.248 và vẫn giữ ba lỗi CLI cũ; không gọi file này là snapshot trước UI. Theo phiên UI, VS sau đó đóng/crash lúc đổi viewport; event/log mới giữ riêng, không suy nguyên nhân từ log crash cũ hoặc gọi môi trường debug đã ổn định hoàn toàn.

### SCD/TN04 có kết quả độc lập

[Manifest SCD](../results/native_build_20261120/ssis/scd/6f3301d7-87ff-44c5-a578-76666329f290/manifest.json) và [DTExec log](../results/native_build_20261120/ssis/scd/6f3301d7-87ff-44c5-a578-76666329f290/dtexec.log) ghi `SUCCEEDED`, ExitCode 0, `Assertions: PASS`. Package kiểm Type 1 overwrite; Type 2 đóng/mở phiên bản trong transaction, replay, một current, không overlap và lookup đúng biên; Type 3 chỉ giữ một bước trước. P01/A01 là synthetic temp-table test, không chứng minh nguồn Coffee có sự kiện đổi thuộc tính thật. Đây là Execute SQL package thực chạy, không chứng minh CSV Data Flow đã chạy.

[JUnit SQL regression cuối](../results/native_build_20261120/ssis/sql_regression_final.xml) và [log](../results/native_build_20261120/ssis/sql_regression_final.log) là bằng chứng kiểm tra SQL/package riêng. Các ca live SQL dùng rollback; không thay receipt của tám child Data Flow.

## 4. Kết quả tám ca CSV đã đối chiếu

SuiteID `63d2403b-e12f-495d-a3ce-69efce27f1a6`, ManifestSHA256 `88ba9eac77111bce13451ee5c504a81c699c41cc9d9319cc791d2d85a88645c1`; hash đọc lại từ manifest hiện tại khớp receipt. Native parent bắt đầu `2026-11-20T13:41:12.439462Z`, kết thúc `2026-11-20T13:41:44.562889Z`. Các giá trị dưới đây đã khớp đáp án protocol; trạng thái kho sau từng bước lấy từ **receipt native tại bước đó**. `warehouse_snapshot` trong các file verifier con được đọc sau khi suite hoàn tất nên cùng phản ánh kho cuối, không phải ảnh chụp lịch sử từng bước.

| Ca/bằng chứng verifier | Nguồn | Accepted/rejected | Inserted/updated/unchanged | Kho sau ca: rows/Sales |
|---|---|---|---|---|
|[1 PASS](../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/case_01.json)|23 tháng đầu|4071/0|4071/0/0|4071/784231|
|[2 PASS](../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/case_02.json)|Thêm 12/2013|177/0|177/0/0|4248/819811|
|[3 PASS](../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/case_03.json)|Replay 12/2013|177/0|0/0/177|4248/819811|
|[4 PASS](../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/case_04.json)|Bản đủ, Sales dòng đầu+10|4248/0|0/1/4247|4248/819821|
|[5 PASS](../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/case_05.json)|Raw gốc phục hồi|4248/0|0/1/4247|4248/819811|
|[6 PASS](../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/case_06.json)|Bản đủ, 1Sales=`abc`|4247/1|0/0/4247|4248/819811|
|[7 PASS](../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/case_07.json)|8 dòng, 2 lỗi|6/2|0/0/6|4248/819811; batch valid Sales 1139|
|[8 PASS](../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/case_08.json)|Raw gốc cuối|4248/0|0/0/4248|4248/819811; Budget 746160; Profit 259543|

Verifier đã kiểm mọi raw payload/SourceRow, ngày/khóa/thuộc tính và 11 số đo trên dòng hợp lệ của tám batch; `read=accepted+rejected`, source hash và tám BatchID khớp manifest. Ca6/7 không xóa fact hợp lệ cũ vì đây là nạp tăng dần, không phải snapshot replacement.

Tái lập và đọc lại evidence:

1. Giữ manifest đúng SuiteID của lần F5, Output/Progress và ảnh số hàng. Không regenerate manifest giữa run và verifier.
2. Đọc lại bằng verifier chỉ đọc: `.\.venv\Scripts\python ssis/CoffeeETLTrangAcceptance/Verify-Acceptance.py`. Lệnh đã trả exit 0 cho suite này; không huấn luyện, không thực thi lại package.
3. Không F5 lại suite này trên kho đã có 4248 fact: preflight đòi fact ban đầu rỗng. Nếu cần tái lập từ đầu, dùng database thử mới và manifest mới theo README; giữ nguyên receipt hiện có.
4. Nếu lỗi/partial, giữ nguyên log và trạng thái DB để chẩn đoán. Không xóa fact hay audit để làm mất lần thử. Xem yêu cầu DB rỗng và điều kiện chạy lại trong README suite.

## 5. Đối soát relational và TN05 chỉ đọc

Script mới [verify_etl_mart.py](../scripts/native_ssas_trang/verify_etl_mart.py) chỉ chấp nhận đúng DB `CoffeeDW_Trang_SSIS_TN03_20261120` trên SQL Server local, yêu cầu ODBC readonly và chỉ thực thi SELECT/CTE. Lệnh với `--database CoffeeDW` bị guard từ chối trước kết nối. Run cuối trả exit 0: [summary.json](../results/native_build_20261120/relational_acceptance/final/summary.json), [analysis.md](../results/native_build_20261120/relational_acceptance/final/analysis.md), [manifest 136 artifact](../results/native_build_20261120/relational_acceptance/final/manifest.json); toàn bộ hash đã đối chiếu khớp. Định nghĩa procedure/view được đọc thành văn bản trong `definitions/`, không được thực thi như script ghi DB.

Kết quả 39 phép kiểm,43 SELECT/CTE:

- PK fact đúng `(DateKey,LocationKey,ProductKey)`; UNIQUE khóa dimension enabled; bốn FK fact enabled/trusted. Không có orphan hoặc duplicate grain; dimension 24/156/13 dòng.
- Fact trước/sau JOIN ba chiều giữ 4.248 dòng và cả 11 tổng khớp nguồn gốc. Tám batch giữ số dòng và 11 tổng từ staging hợp lệ qua lookup, accounting đúng và hash fixture không đổi. SUM Inventory toàn kỳ ở phép kiểm này chỉ là bất biến đối soát, không phải KPI tồn kho xuyên thời gian.
- Ba view mart đã tồn tại và có định nghĩa đọc trực tiếp:96 ô tháng–Market,1.008 ô tháng–Market–Product và 4.248 nhóm State/Product khớp nguồn theo từng ô. Sales Market–tháng đủ 96 ô làm đầu vào forecast; `ml.ForecastSales` ở DB ETL này 0 dòng nên không công bố đã publish forecast tại đây.
- [TN05 FULL OUTER JOIN](../results/native_build_20261120/relational_acceptance/final/tn05_full_outer_baseline.csv) aggregate actual/budget riêng trước khi nối, giữ 96 nhóm. [Fixture thiếu nhóm](../results/native_build_20261120/relational_acceptance/final/tn05_query_only_missing_fixture.csv) giữ NULL/flags cho West 01/2012 thiếu budget và West 01/2014 chỉ có plan 1000. **Đây là CTE mô phỏng trong truy vấn từ cùng CSV**, không phải hai nguồn fact thật, ngân sách tương lai thật hoặc stored mart mới được deploy.
- [Fan-out thực đo](../results/native_build_20261120/relational_acceptance/final/tn05_incorrect_fanout.csv): West 01/2012 có 56 dòng, budget đúng 9460 bị lặp thành 529760 khi nối aggregate budget vào detail trước SUM.
- Ca budget 0 trên dữ liệu thật trả NULL. Query Inventory lấy kỳ cuối trong tập chọn trước rồi lọc; tháng cuối thiếu dòng trả NULL, không lấy kỳ cũ.

Định nghĩa loader trên DB cho thấy nạp dimension→lookup→fact bên trong BEGIN/COMMIT TRANSACTION, có XACT_ABORT và ROLLBACK ở CATCH. Script SELECT-only này không fault-inject lỗi/không gọi loader; phép thử rollback đã được thực hiện bằng runner riêng ở mục 6. Bộ 22 test cũ có test rollback SQLite và cleanup rollback cho live SQL; hai điều đó vẫn không được đổi tên thành bằng chứng fault-injection native.

Tái lập đọc ở thư mục mới, không ghi đè evidence đã có:

```powershell
.\.venv\Scripts\python scripts/native_ssas_trang/verify_etl_mart.py --output results/native_build_20261120/relational_acceptance/replay01
```

Run đầu đã lưu kết quả 37 PASS nhưng in console gặp encoding cp949 sau khi ghi artifact; giữ nguyên ở thư mục cha. Run `final/` sửa console ASCII và thêm hai kiểm PK/schema FK, đủ 39 PASS/exit0; đây là run được dẫn trong các checklist.

## 6. Rollback fault-injection native đã đạt

[Runner](../scripts/native_ssas_trang/verify_loader_rollback.py) có guard đúng DB thử, yêu cầu `--execute` rõ ràng, không ALTER procedure hoặc tạo trigger. [Run chốt](../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/verification.json) từ `2026-11-20T14:25:31.551400Z` đến `14:25:39.760161Z` đạt **12/12 kiểm tra**; [README chi tiết](../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/README.md) và [5 test safeguards PASS](../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/unit_tests.xml) đi kèm.

Probe khai SourceCount 2 nhưng chỉ đặt một dòng staging trong outer transaction chưa commit; đổi Sales/State của khóa có sẵn để lỗi được chạm sau UPDATE dimension và fact. [Trước EXEC](../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/probe_before_execute.json) có `@@TRANCOUNT=1`; [receipt native](../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/native_error_receipt.json) nhận lỗi 50006 của `dw.usp_LoadCoffee`, dòng 74, CATCH trả `@@TRANCOUNT=0`, `XACT_STATE()=0`. ODBC 266 được lưu nguyên văn và chỉ chấp nhận khi đi cùng receipt 50006 đúng và mọi readback đạt.

Snapshot trước/sau của **11 bảng / 47.315 dòng**, toàn bộ cột, có hash logical giống nhau; không còn probe audit/staging/reject/landing/fact lineage/State marker. Loader definition, nguồn gốc, 11 số đo và tám receipt SSIS không đổi. Hash này là giá trị logical, không so database page vật lý. Đây là phép thử T-SQL trên DB biệt lập có rollback, không phải ca SSIS thứ 9 hay thay đổi nguồn thật; không có commit business rows. Các lần chuẩn bị FAIL_STOP và diagnostic cũ được giữ riêng, không đổi nhãn thành PASS.

## 7. Cách mở để trình bày và kiểm tra cuối

1. Đọc [final_summary.json](../results/native_build_20261120/final_summary.json) và [verification nguồn cuối](../results/native_build_20261120/ssas/integrated_ssis_source/verification.json), xác nhận cube đọc DB SSIS biệt lập. Kho SSIS đã có 4.248 fact nên phần trình bày CSV dùng manifest/receipt/audit và ảnh thành công, không F5 lại suite đòi kho ban đầu rỗng. DB native 19/11 giữ dữ liệu/benchmark/forecast cũ, không còn là nguồn cuối của cube này.
2. Khi project SSAS đang đóng, chạy cấu hình local dưới đây trước khi mở sau clone. Script chỉ ghi `.dwproj.user` cho Development và không deploy/process; file này được ignore. Sau đó mở `ssas/CoffeeCubeTrang/CoffeeCube.dwproj`, chọn Development rồi **Build** để tạo lại `bin/CoffeeCube.deploymenttargets`. File hiện tại đã được đọc lại đúng `localhost\TRANGTRETRAU` / `CoffeeCube_Trang_20261120` sau Build cuối. Receipt recheck13:59–14:03Z còn ghi target bin cũ trước bước này, được giữ nguyên theo lịch sử.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/native_ssas_trang/Configure-Designer.ps1
```

3. Mở cube Browser, dùng query WHERE 01/2012 để xem slice Market, drill Central→State và dice Coffee/Central+East. Trình bày pivot bằng hai MDX và bảng 6 ô ADOMD đã đối chiếu; giải thích riêng hạn chế Query Designer UI. Deploy/process vẫn là bước server riêng có guard, không dùng target generic hoặc cube cũ `MySalesCube`.
4. Mở solution SSIS Acceptance để xem Control/Data Flow; đối chiếu tám ca với receipt đã lưu. Dùng [phân tích relational](../results/native_build_20261120/relational_acceptance/final/analysis.md) và [biên bản rollback](../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/README.md) để giải thích kiểm toàn vẹn và lỗi có rollback. Rerun runner rollback là phép thử ghi tạm được guard, không phải SELECT chỉ để mở xem báo cáo.

**Kiểm tra tích hợp cuối đã có kết quả:** [JUnit](../results/native_build_20261120/final_pytest.xml) ghi **141 tests / 0 failures / 0 errors / 0 skipped** với biến môi trường trỏ đúng DB thử; warning cache WinError5 không phải test fail và không sửa ACL. Frontend `node --test tests/test_presenter_frontend.js` đạt **10/10** theo direct tool output, được ghi trong final_summary. [CLI demo](../results/native_build_20261120/final_demo.log) trên reference DB biệt lập trả exit 0, 4.248 accepted/0 rejected/Sales819811; [CLI forecast](../results/native_build_20261120/final_forecast.log) trả exit 0, chọn MA3 bằng validation. Không dùng các kiểm tra này để tạo phiên UX người thật.

File mới/phép chạy phục vụ đợt này gồm [Configure-Designer.ps1](../scripts/native_ssas_trang/Configure-Designer.ps1), [verify_etl_mart.py](../scripts/native_ssas_trang/verify_etl_mart.py), [verify_loader_rollback.py](../scripts/native_ssas_trang/verify_loader_rollback.py), [recheck_readonly.py](../scripts/native_ssas_trang/recheck_readonly.py), [integrate_ssis_source.ps1](../scripts/native_ssas_trang/integrate_ssis_source.ps1), [verify_integrated_source.py](../scripts/native_ssas_trang/verify_integrated_source.py), hai query MDX pivot và [tests safeguards rollback](../tests/test_loader_rollback_probe.py). Các log SQL/MDX, Build, Browser AX/ảnh, JUnit và manifest nằm trong `results/native_build_20261120/`, không đưa toàn bộ output/installer/database lên Git.

**Ví dụ xem thực tế tháng 11/2013:** Browser đang để `Date Key=20131101`, với [ảnh sau tích hợp](../results/native_build_20261120/ui/ssas_integrated_browser_actual_201311.png) và [SQL đối chứng](../results/native_build_20261120/ssas/integrated_ssis_source/browser_actual_201311.json). Sales thực tế là Central **10.885**, East **7.438**, South **4.480**, West **11.300**, theo đơn vị nguồn và không đổi thang. `Sales` là actual; `Budget Sales` là ngân sách, còn `Gap=Sales−Budget Sales` là chênh kế hoạch, **không phải sai số mô hình dự báo**. Khi đánh giá mô hình, so dự đoán với Sales thực tế cùng Market và tháng; lấy `prediction−actual` cho sai lệch có dấu, hoặc trị tuyệt đối cho sai số tuyệt đối.

## 8. Đồng bộ tài liệu theo bằng chứng

Các tài liệu liên quan đã được đồng bộ theo native receipt, SELECT, Build và UI thực chạy. TN05 giới hạn ở CTE nêu trên; rollback có bằng chứng riêng; UX người thật và giới hạn IDE vẫn được ghi rõ.

| File hiện tại | Mốc đã đồng bộ theo bằng chứng |
|---|---|
| [ch04](chapters/ch04_chi.md) | Đánh dấu riêng mục đã có batch/reject/incremental/correction từ native CSV; mục SCD dẫn run thực nhưng ghi dữ liệu mô phỏng; link ảnh và log thật |
| [ch05](chapters/ch05_chi.md) | Liên kết project biệt lập, process receipt, 17 ca MDX–SQL, ảnh DSV/Dimension Usage và SELECT-only TN05/mart riêng; không suy TN05 từ cube |
| [BASE_STATUS](BASE_STATUS.md) | Thêm mốc 20/11, giữ phần 13/11 là lịch sử; SSAS 17/17, SSIS 8/8 và SCD có kết quả riêng; UX người thật vẫn riêng |
| [REPORT_MAP](REPORT_MAP.md) | Bổ sung đường dẫn minh chứng TN03/04/06, không thay tiêu chí nghiệm thu bằng tên project |
| [ssis/README](../ssis/README.md) | Câu mở đầu “chưa có .dtproj/.dtsx” đã là mốc base; trỏ project mới, mô tả raw landing/SQL validator và phạm vi variable binding thực tế |
| [ssas/README](../ssas/README.md) | Câu mở đầu “chưa có .dwproj/cube đã deploy” đã cũ; đổi hướng dẫn Inventory LastNonEmpty sang chính sách **LastChild/kỳ cuối được chọn**, tránh fallback sai hợp đồng |
| [CoffeeETLTrang README](../ssis/CoffeeETLTrang/README.md) và [Acceptance README](../ssis/CoffeeETLTrangAcceptance/README.md) | Bổ sung extension/designer Build và CSV 8/8 PASS. Giữ lỗi DTExec/crash là lịch sử, không xóa dấu vết |
| [CoffeeCubeTrang README](../ssas/CoffeeCubeTrang/README.md) | Processed 17/17, ảnh Browser/DSV cuối, Build 0 lỗi / 8 cảnh báo, pivot native 6/6 và cấu hình local sau clone |
| [TRANG_NATIVE_HANDOFF](TRANG_NATIVE_HANDOFF.md), [reproduction_handoff](trang/reproduction_handoff.md), [chương7](trang/chapter07_deployment.md), [README](../README.md) | Link mốc native 20/11 này; giữ rõ database/phiên bản nguồn và phần thích nghi riêng, không gán bản chạy biệt lập thành bàn giao chính thức trên máy Chi |

## 9. Giới hạn bàn giao

- Các link trong `results/` đã kiểm tồn tại cục bộ, nhưng thư mục này bị Git ignore theo quy ước. Người nhận clone repo sẽ cần bộ evidence được chọn/bàn giao riêng hoặc tái lập; không sửa ignore để đưa toàn bộ output/installer lên Git.
- CSV tám ca có receipt/verifier PASS; chưa có xác nhận reboot sau cài extension. VS đóng/crash sau thành công khi đổi viewport cần log riêng. Không biến một run PASS thành cam kết IDE ổn định hoặc chạy lại trên kho không còn rỗng.
- SSAS có 17 ca runtime và Browser slice/drill/dice; Query Designer vẫn chặn axis swap. Pivot 6/6 native ADOMD không biến thành pivot UI PASS. Build cuối vẫn có 8 cảnh báo provider/attribute best practices.
- Không gộp SQL regression, SCD synthetic, benchmark, UX người thật và native CSV thành một kết quả PASS chung. TN05 CTE là fixture có nhãn; rollback 12/12 là T-SQL probe riêng. Không thay nguồn thật bằng dữ liệu sinh, không viết đè Word gốc hoặc project Chi. Không commit/push/merge vào main trong đợt này.

