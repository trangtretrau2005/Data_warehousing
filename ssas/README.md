# SSAS Chương 5 (`ssas/CoffeeCube/`)

Project Analysis Services **Multidimensional** đã được tạo và kiểm tra cấu trúc bằng `Microsoft.AnalysisServices (AMO)` tại `ssas/CoffeeCube/`:

- `CoffeeCube.dwproj` & `CoffeeCube.database`: Project và định nghĩa database SSAS Multidimensional.
- `CoffeeDW.ds`: Data Source kết nối tới `CoffeeDW` trên SQL Server (`localhost`).
- `CoffeeDW.dsv`: Data Source View gồm `dw.FactSalesPerformance`, `dw.DimDate`, `dw.DimLocation`, `dw.DimProduct` cùng đầy đủ khóa chính (PK) và quan hệ khóa ngoại (FK).
- `Dim Date.dim`: Khóa chính `Date Key` (`YYYYMMDD`); phân cấp `Calendar` (`Year -> Quarter -> Month`) với `Quarter` dùng khóa ghép `(Year, Quarter)` và `Month` dùng `DateKey` (`NameColumn = MonthStart`) để không gộp nhầm tháng/quý giữa các năm.
- `Dim Location.dim`: Khóa chính `Location Key`; quan hệ thuộc tính `Location Key -> Area Code -> State -> Market` và `Location Key -> Market Size`; phân cấp `Geography` (`Market -> State -> Area Code`).
- `Dim Product.dim`: Khóa chính `Product Key`; quan hệ thuộc tính `Product Key -> Product Name -> Product Type -> Product Line` và `Product Name -> Type`; phân cấp `Product Hierarchy` (`Product Line -> Product Type -> Product Name`).
- `Coffee Performance.cube`:
  - Measure group `Fact Sales Performance` nối `Regular` tới 3 chiều ở grain lá (`DateKey`, `LocationKey`, `ProductKey`).
  - 10 số đo dòng chảy (`Sales`, `Budget Sales`, `Profit`, `Budget Profit`, `COGS`, `Budget COGS`, `Margin`, `Budget Margin`, `Marketing`, `Total Expenses`) dùng hàm gộp `Sum`.
  - Số đo tồn kho (`Inventory`) được áp quy tắc bán cộng (semi-additive) qua `SCOPE` trong `MdxScript` để lấy giá trị của tháng cuối cùng trong tập đang chọn (`TAIL(EXISTING [Dim Date].[Date Key].[Date Key].Members, 1).Item(0)`), không cộng dồn qua nhiều tháng.
  - Ba calculated measures trong `MdxScript`:
    - `[Measures].[Gap] = [Measures].[Sales] - [Measures].[Budget Sales]`
    - `[Measures].[Budget Achievement] = IIF(IsEmpty([Measures].[Budget Sales]) OR [Measures].[Budget Sales] = 0, NULL, [Measures].[Sales] / [Measures].[Budget Sales])`
    - `[Measures].[Profit Margin] = IIF(IsEmpty([Measures].[Sales]) OR [Measures].[Sales] = 0, NULL, [Measures].[Profit] / [Measures].[Sales])`
- `DeployCoffeeCube.xmla`: Script XMLA Create đầy đủ để triển khai trực tiếp trên SSMS Analysis Services.
- [`ssas/queries.mdx`](queries.mdx): Bộ 8 truy vấn MDX đã đồng bộ tên định danh (`[Coffee Performance]`, `[Dim Date].[Calendar]`, `[Dim Location].[Geography]`, `[Dim Product].[Product Hierarchy]`) để kiểm tra toàn chuỗi, Slice, Drill-down, Roll-up, Dice, Pivot, xếp hạng Gap South `08/2013` và Inventory kỳ cuối.

## Bản nghiệm thu biệt lập của Trang

Cube của Chi có đích `CoffeeCube` và đọc `CoffeeDW`. Cube của Trang có đích `CoffeeCube_Trang_20261120` và đọc kho nghiệm thu SSIS riêng. Chi xử lý Inventory bằng MDX `SCOPE` ở Year, Quarter và All. Trang khai báo `LastChild` trực tiếp trên measure. Khi so sánh hai cube, cần đối chiếu thêm tập tháng không liên tiếp và kỳ cuối thiếu dòng. Coffee Datacube 3D đọc mart quan hệ qua backend SQLite hoặc SQL Server.

**Đã thực chạy 20/11/2026 trên máy Trang:** project thích nghi riêng [CoffeeCubeTrang](CoffeeCubeTrang/README.md), database `CoffeeCube_Trang_20261120` trên `localhost\TRANGTRETRAU`, đã ProcessFull/Processed. **Nguồn cuối là `CoffeeDW_Trang_SSIS_TN03_20261120` vừa được SSIS nạp**: [verification](../results/native_build_20261120/ssas/integrated_ssis_source/verification.json), [17/17 ca MDX khớp SQL mới](../results/native_build_20261120/ssas/integrated_ssis_source/comparison.json), [pivot native 6/6](../results/native_build_20261120/ssas/integrated_ssis_source/pivot_acceptance/verification.json). Nguồn `CoffeeDW_Trang_20261119` và receipt đầu đợt được giữ là lịch sử; `MySalesCube` không đổi. [Biên bản native](../docs/TRANG_NATIVE_BUILD_20261120.md) có DSV đủ 4 bảng, Dimension Usage và ảnh Browser slice/drill/dice. [Build sau tích hợp lúc 22:17](../results/native_build_20261120/ui/ssas_integrated_build.txt) **0 lỗi / 8 cảnh báo**, không phải 0 cảnh báo. Query Designer chặn đổi trục khác Measures trên axis đầu; ADOMD ExecuteCellSet chạy được query đổi trục, không gọi đó là pivot UI PASS.

Sau clone, đóng project rồi chạy `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/native_ssas_trang/Configure-Designer.ps1` trước khi mở `.dwproj`; script chỉ cấu hình `.dwproj.user` local đúng target biệt lập, không deploy/process. Build trong Visual Studio để tái tạo `bin/CoffeeCube.deploymenttargets`, kiểm đúng instance/database trước thao tác server. Xem README project cho parity hai nguồn, 177 SourceRow tháng 12/2013 khác do lineage file/batch và quyền tối thiểu CONNECT+SELECT bốn bảng trên nguồn SSIS. Data Source cuối đã được ProcessFull lúc 14:58:07Z; không dùng parity thay cho receipt migration thật.


## Kiểm tra đối chứng SQL và triển khai Cube

1. Chạy bộ kiểm tra đối chứng đa chiều trên SQL Server:
   ```powershell
   sqlcmd -S localhost -E -b -W -s " | " -i sql/sqlserver/13_tn06_olap_checks.sql
   .\.venv\Scripts\python learning/experiments/mart_olap.py
   ```
2. Trên máy đã cài dịch vụ `SQL Server Analysis Services (MSOLAP)` ở chế độ **Multidimensional**:
   - Mở `ssas/CoffeeCube/CoffeeCube.dwproj` trong Visual Studio (hoặc mở `ssas/CoffeeCube/DeployCoffeeCube.xmla` trong SSMS kết nối Analysis Services) → chạy **Deploy** và **Process Full**.
   - Chạy [`ssas/queries.mdx`](queries.mdx) trên SSMS MDX Query và mở **Cube Browser** để chụp ảnh `TN06_usage.png` và `TN06_browser.png`.
   - Biên bản đối soát chi tiết: [`results/TN05/chi_2026-11-15/experiment.md`](../results/TN05/chi_2026-11-15/experiment.md) và [`results/TN06/chi_2026-11-15/experiment.md`](../results/TN06/chi_2026-11-15/experiment.md).
