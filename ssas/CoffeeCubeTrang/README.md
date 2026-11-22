# Project SSAS biệt lập của Trang — 20/11/2026

Đây là bản thích nghi riêng từ project Chi tại commit `59d2559`, không sửa project
nguồn trong `.work/review_chi/`. Không tác động database cube có sẵn `MySalesCube`.

- SSAS Multidimensional: `localhost\TRANGTRETRAU`.
- Database SSAS mới: `CoffeeCube_Trang_20261120`, cube `[Coffee Performance]`.
- Data Source cuối: SQL Server `.`, database **`CoffeeDW_Trang_SSIS_TN03_20261120` vừa được SSIS nạp**, provider `MSOLEDBSQL`.
- Windows identity đọc nguồn khi process: `NT Service\MSOLAP$TRANGTRETRAU`
  (`ImpersonateServiceAccount`). Cần login/user phù hợp và quyền SELECT bốn bảng
  `dw.DimDate`, `dw.DimLocation`, `dw.DimProduct`, `dw.FactSalesPerformance`.
  Quyền cuối trên DB SSIS chỉ có CONNECT và SELECT đúng 4 bảng, không role DB/server rộng;
  xem [permissions_after.json](../../results/native_build_20261120/ssas/integrated_ssis_source/permissions_after.json).
  Nguồn `CoffeeDW_Trang_20261119` và log `source_read_permissions.txt` thuộc giai đoạn đầu,
  được giữ nguyên theo lịch sử, không còn là Data Source cuối của cube này.

## Các file đưa vào SSMS

1. `CreateCoffeeCubeTrang.xmla`: chỉ CREATE database/cube mới, **không process**.
2. `ProcessFull.xmla`: bước ProcessFull riêng cho đúng database mới.
3. `queries.mdx`: tám truy vấn của Chi, Query 7 sửa `NONEMPTY(...)` bên trong ORDER.
4. `acceptance_cases.mdx`: 17 ca nghiệm thu kèm kết quả SQL độc lập trong evidence.

Chỉ người điều khiển phiên SSMS thực hiện CREATE/Process sau khi kiểm tra target.
`prepare_project.py` và `prepare_cases.py` không gửi lệnh ghi lên SSAS/SQL Server.

## Inventory bán cộng

Mười số đo dòng chảy và Inventory đều là physical measures; Inventory dùng
`AggregateFunction=LastChild` theo chiều thời gian. Không thay giá trị tháng cuối
bằng tháng gần nhất trước đó có dữ liệu. Quarter composite key gồm năm+quý; DateKey
`YYYYMMDD` được sắp theo thứ tự thời gian. Đây là LastChild, không phải LastNonEmpty.

ProcessFull và MDX runtime đã được kiểm tra trực tiếp. Các filter Year 2012/2013,
Quarter 2013Q2, range 02–05/2013, hai tháng không liên tiếp 01+08/2013, WHERE multi-select,
lọc Colombian 08+11/2013 và ca tháng cuối thiếu actual đều trả đúng tháng cuối tập chọn.
Ca cuối chứng minh không fallback về Inventory 1091 của tháng trước. Budget=0 trả tỷ lệ NULL;
slice nhiều Market/kỳ xác nhận tỷ lệ tính từ tổng tử / tổng mẫu.

## Tái lập chuẩn bị và đối soát đọc

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/native_ssas_trang/inspect_environment.ps1
.\.venv\Scripts\python scripts/native_ssas_trang/prepare_project.py
.\.venv\Scripts\python scripts/native_ssas_trang/prepare_cases.py
# Sau khi CREATE/ProcessFull trong SSMS hoặc guarded AMO runner:
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/native_ssas_trang/read_cases.ps1
.\.venv\Scripts\python scripts/native_ssas_trang/compare_cases.py
```

Phần receipt đầu đợt sau đây thuộc nguồn cũ; mốc tích hợp nguồn cuối được ghi riêng ngay dưới. Read-only AMO inspection dùng client SSMS22 phiên bản 19.113.3 để nhận SQL2025
Standard Developer. WinPowerShell5 cần dependency resolver cho thư viện Identity.
Native XMLA CREATE và ProcessFull đã thành công trên instance Multidimensional;
đích `CoffeeCube_Trang_20261120` ở trạng thái `Processed`, còn `MySalesCube` cũ vẫn
`Processed`. `final_environment.json` xác nhận Inventory=LastChild và cả ba dimension
đặt Duplicate/NotFound/NullKey thành ReportAndStop. Đối chiếu **17/17 ca** MDX với
SQL Server relational nguồn đạt; kết quả/queries ở `results/native_build_20261120/ssas/`
(`deploy_process.json`, `final_environment.json`, `comparison.json`, `mdx_actual/`,
`sql_expected/`, permissions log và attempt logs).

**Tích hợp nguồn cuối ngày 20/11/2026:** [migration.json](../../results/native_build_20261120/ssas/integrated_ssis_source/migration.json)
ghi AlterDataSourceOnly và ProcessFull thành công; lần process cuối `2026-11-20T14:58:07.690Z`
(21:58:07, giờ Bangkok). Data Source thực, DSV và local `.ds` đều trỏ DB SSIS nêu ở đầu file.
[Verification cuối](../../results/native_build_20261120/ssas/integrated_ssis_source/verification.json)
đạt 4.248 business rows/all thuộc tính/11 số đo, 96 ô tháng–Market, [17/17 MDX–SQL](../../results/native_build_20261120/ssas/integrated_ssis_source/comparison.json)
và [pivot 6/6 ô](../../results/native_build_20261120/ssas/integrated_ssis_source/pivot_acceptance/verification.json)
trên **chính DB mới**, Inventory LastChild và ba dimension ReportAndStop vẫn giữ nguyên.
Không create/drop database/cube khác; raw và `MySalesCube` không đổi. Các receipt
`final_acceptance.json`/`final_environment.json` phía trước là mốc nguồn cũ, không bị ghi đè.

Runner CREATE/Process guard target mới và log từng thông báo XMLA:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/native_ssas_trang/deploy_process.ps1 -Mode ProcessExisting
```

Không rerun `CreateAndProcess` trên database đã tồn tại; runner từ chối target không trống.
Project Visual Studio được mở/chuẩn hóa riêng; không dùng generator lên thư mục live.

AMO deployment/process và ADOMD read-only acceptance đã chạy thật. Ảnh DSV,
Dimension Usage, Browser có bộ lọc và Build được lưu riêng từ phiên UI.
Bảng/query output là evidence số học độc lập, không thay ảnh giao diện.

**Đối chiếu hồ sơ UI 20/11/2026:** đã có [DSV đủ 4 bảng (mốc 21:34)](../../results/native_build_20261120/ui/ssas_dsv_final.png),
[Dimension Usage](../../results/native_build_20261120/ui/ssas_dimension_usage.png) và
[Cube Structure](../../results/native_build_20261120/ui/ssas_cube_structure.png).
[Build ban đầu](../../results/native_build_20261120/ui/ssas_build_initial.txt) là 0 lỗi / 11 cảnh báo;
[Build sau tích hợp lúc 22:17](../../results/native_build_20261120/ui/ssas_integrated_build.txt) là **0 lỗi / 8 cảnh báo**,
có [ảnh](../../results/native_build_20261120/ui/ssas_integrated_build.png). Vẫn có cảnh báo provider,
visible attribute hierarchies, Geography/Product types và rigid relationships; không công bố 0 cảnh báo.
Metadata runtime dùng ReportAndStop và Inventory LastChild. Browser đã chạy
[slice 01/2012](../../results/native_build_20261120/ui/ssas_integrated_browser_slice_201201.png),
[drill sáu State Central](../../results/native_build_20261120/ui/ssas_integrated_browser_central_states.png),
[dice Coffee Central+East](../../results/native_build_20261120/ui/ssas_integrated_browser_dice_coffee.png);
file `.txt` cùng tên giữ query/filter và số hiển thị. Query Designer chặn axis đầu khác Measures
([ảnh giới hạn pivot](../../results/native_build_20261120/ui/ssas_browser_pivot_designer_limit.png)).
Hai MDX gốc/đổi trục đã chạy lại trên nguồn SSIS bằng ADOMD ExecuteCellSet, [6/6 ô khớp SQL và transpose](../../results/native_build_20261120/ssas/integrated_ssis_source/pivot_acceptance/verification.json); đây là pivot native PASS, không phải pivot UI PASS. [17 ca đối soát cuối](../../results/native_build_20261120/ssas/integrated_ssis_source/comparison.json) dùng SQL expected mới từ DB SSIS. `final_acceptance.json` và 17 file trước chuyển nguồn giữ là bộ lịch sử, không thay receipt nguồn cuối.
[Bàn giao tổng hợp](../../docs/TRANG_NATIVE_BUILD_20261120.md)
tách SSAS 17/17, SSIS CSV 8/8 và SCD PASS khỏi UX người thật. TN05/mart có
[39 kiểm SQL chỉ đọc riêng](../../results/native_build_20261120/relational_acceptance/final/summary.json)
trên DB ETL; các ca thiếu nhóm là fixture CTE có nhãn, không suy từ cube hoặc deploy mart mới.

Các ảnh Browser chính vừa dẫn được thu sau ProcessFull nguồn SSIS. Ảnh DSV 21:34/Dimension Usage là mốc cấu trúc trước chuyển nguồn; migration xác nhận bốn bảng/quan hệ không đổi, nên không gắn ảnh đó thành ảnh mới sau rewire. Bộ ảnh Browser 21:18–21:26 và Build 21:07 giữ trong lịch sử của [biên bản](../../docs/TRANG_NATIVE_BUILD_20261120.md); Build 22:17 và ảnh Browser có prefix `ssas_integrated_` là mốc trình bày cuối.

## Mở project sau clone và đích triển khai

Đóng project Visual Studio trước khi chạy cấu hình local:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/native_ssas_trang/Configure-Designer.ps1
```

Script chỉ tạo/cập nhật `CoffeeCube.dwproj.user` cho Development, giữ file local được ignore,
target `localhost\TRANGTRETRAU` / `CoffeeCube_Trang_20261120`; không kết nối server/deploy/process
và không sửa `.dwproj` chung. [Receipt cấu hình](../../results/native_build_20261120/ssas/designer_configuration/verification.json)
giữ bằng chứng. Sau đó mở `CoffeeCube.dwproj`, chọn Development và **Build** để tái tạo
`bin/CoffeeCube.deploymenttargets`; file hiện tại đã được đọc lại đúng target sau Build cuối.
Không dùng target generic `localhost/CoffeeCube` từ output build cũ. Deploy/process vẫn là thao tác
riêng có guard cho database biệt lập, không chạy vào `MySalesCube` hoặc database đang có công việc khác.

[Read-only recheck trước chuyển nguồn](../../results/native_build_20261120/ssas/readonly_recheck/verification.json) ghi 4.248 business keys,
11 số đo và 96 ô tháng–Market giống giữa nguồn cube cũ `CoffeeDW_Trang_20261119` và DB SSIS mới.
177 SourceRow tháng 12/2013 khác vì lineage theo file/batch, đã ghi riêng; không phải khác số đo.
Receipt recheck được thu trước Build cuối nên còn ghi built target cũ; Build 21:07 đã tái tạo
`bin/CoffeeCube.deploymenttargets` đúng đích nêu trên. Việc đổi Data Source sau đó được
xác nhận riêng bằng migration và verification cuối ở trên, không suy từ parity.
