# Biên bản thực nghiệm TN05 — Data Mart và Drill-Across không gây Fan-out

- **Mã TN, chương, người thực hiện, ngày:** TN05, Chương 5, Chi (`chiche2k5`), 2026-11-15 (UTC+07:00)
- **Câu hỏi và giả thuyết:**
  - Các view tầng mart (`mart.vw_Detail`, `mart.vw_MarketPeriod`, `mart.vw_MarketProductPeriod`) có bảo toàn chính xác từng ô (cell-by-cell) so với phép tổng hợp trực tiếp từ `Coffee.csv` không?
  - Khi kết hợp hai quy trình/fact có độ hạt khác nhau (ví dụ `Actual` chi tiết và `Budget` hoặc `ForecastSales` ở mức `MonthStart × Market`), vì sao phải tổng hợp độc lập mỗi phía về cùng grain chung trước khi `FULL OUTER JOIN`?
  - Điều gì xảy ra nếu nối trực tiếp bảng tổng hợp `MonthStart × Market` vào bảng chi tiết `vw_Detail` trước khi `SUM` (lỗi fan-out)?
- **Phiên bản code (commit), file/checksum, engine và cấu hình máy:**
  - Base commit: `0775041` (nhánh `chi`)
  - Nguồn gốc: `data/raw/Coffee.csv` (`SHA-256: 929bdcc7fd8f6bf21607618e7474df0683af6412b32b8c5af39a40e89b62ffce`)
  - Engine tham chiếu: Python 3.13 / SQLite + pandas (`learning/experiments/mart_olap.py`)
  - Engine native: `Microsoft SQL Server 2022 (RTM) - 16.0.1000.6 (X64)` trên `Chi-Chie (localhost)`, chạy `sql/sqlserver/02_marts.sql`, `10_drill_across.sql`, `11_tn05_budget_demo.sql`.
- **Dữ liệu thật / dữ liệu mô phỏng, số dòng:**
  - Dữ liệu thật: 4.248 dòng trên `dw.FactSalesPerformance` → 96 nhóm `MonthStart × Market` (`vw_MarketPeriod`) và 1.008 nhóm `MonthStart × Market × ProductName` (`vw_MarketProductPeriod`), cùng 112 dòng dự báo trong `ml.ForecastSales`.
  - Dữ liệu mô phỏng trong bảng tạm `#Actual` và `#Budget` (`11_tn05_budget_demo.sql`): xóa dòng `Budget` của `West` kỳ `2012-01-01` (ca thiếu ngân sách) và chèn dòng kế hoạch tương lai `West` kỳ `2014-01-01` với `BudgetSales = 1000` (ca chỉ có kế hoạch, chưa có thực tế).
- **Phương án A/B, tham số giữ cố định:**
  - **Phương án đúng (Pre-aggregated Drill-Across):** Tổng hợp độc lập `#Actual` và `#Budget` (hoặc `ChosenForecast`) theo `(MonthStart, Market)`, sau đó `FULL OUTER JOIN` 1–1 trên khóa ghép và gắn cờ `MissingActual` / `MissingBudget`.
  - **Phương án sai (Fan-out Join):** Nối `mart.vw_Detail` (mức `MonthStart × AreaCode × Product`) với `#Budget` (mức `MonthStart × Market`) rồi tính `SUM(BudgetSales)`.
- **Đáp án đối chứng và cách kiểm tra:**
  - Đối soát từng ô trên 96 nhóm `vw_MarketPeriod` và 1.008 nhóm `vw_MarketProductPeriod`: sai lệch tuyệt đối lớn nhất (`max_abs_diff`) của `Sales`, `BudgetSales`, `Profit`, `Gap`, `BudgetAchievement` đều bằng `0.0`.
  - Drill-across chuẩn trên 96 nhóm: `Groups = 96`, `SUM(Sales) = 819.811`, `SUM(BudgetSales) = 746.160`.
  - Lỗi fan-out khi nối `#Budget` vào `mart.vw_Detail`: tổng `IncorrectRepeatedBudget` bị nhân vọt lên `36.035.260` (gấp ~48,3 lần tổng thật `746.160`); riêng lát cắt `West` tháng `01/2012` có 56 dòng chi tiết nên ngân sách `9.460` bị cộng lặp 56 lần thành `529.760`.
  - Khi xóa budget `West 2012-01-01` và thêm budget `West 2014-01-01 = 1000`: phép `FULL OUTER JOIN` giữ nguyên cả hai dòng với `(2012-01-01, West, Sales=10453.0, BudgetSales=NULL, Gap=NULL, MissingActual=0, MissingBudget=1)` và `(2014-01-01, West, Sales=NULL, BudgetSales=1000.0, Gap=NULL, MissingActual=1, MissingBudget=0)`.
- **Lệnh chạy:**
  ```powershell
  .\.venv\Scripts\python learning/experiments/mart_olap.py
  sqlcmd -S localhost -E -b -W -s " | " -i sql/sqlserver/11_tn05_budget_demo.sql
  sqlcmd -S localhost -E -b -W -s " | " -i sql/sqlserver/10_drill_across.sql
  ```
- **Kết quả thô, đơn vị, ảnh và execution plan:**
  - Lưu tại [`tn05_summary.json`](tn05_summary.json), [`sqlserver_tn05_budget_demo.txt`](sqlserver_tn05_budget_demo.txt) và [`sqlserver_10_drill_across.txt`](sqlserver_10_drill_across.txt).
- **Nhận xét, giới hạn và quyết định:**
  - Không bao giờ thay thế `NULL` của nhóm thiếu ở một phía bằng `0` vì thiếu ngân sách hoặc chưa phát sinh thực tế mang ý nghĩa "chưa có dữ liệu" chứ không phải bằng 0.
  - Hợp đồng mart (`mart.vw_Detail`, `mart.vw_MarketPeriod`, `mart.vw_MarketProductPeriod`) đã khớp 100% giữa SQLite và SQL Server 2022, sẵn sàng bàn giao cho Trang tích hợp dashboard và dự báo.

Trạng thái: **ĐÃ CHẠY VÀ ĐỐI SOÁT KHỚP 100% (SQLite + SQL Server 2022).**
