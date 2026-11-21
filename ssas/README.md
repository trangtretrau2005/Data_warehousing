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
