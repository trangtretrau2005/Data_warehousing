# Chương 4 — Quy trình ETL và kiểm soát chất lượng

Người phụ trách: **Chi**. Cần phân biệt chạy logic tham chiếu bằng Python với bằng chứng chạy package SSIS tại máy.

- [x] Đăng ký batch gồm tên file, SHA-256, thời điểm, trạng thái và số dòng; raw staging giữ chuỗi gốc và số dòng nguồn.
- [x] Parse ngày Excel, mã địa bàn và tiền; đẩy dòng lỗi sang audit kèm nguyên nhân/giá trị gốc, không thay lỗi bằng 0.
- [x] Nạp dimension trước fact, lookup khóa nhiều–một, transaction và UNIQUE bảo vệ grain.
- [x] Triển khai nạp mới, chạy lại cùng nội dung, sửa số cùng khóa; ghi RowsRead/Accepted/Rejected/Inserted/Updated.
- [x] Kiểm tra `read = accepted + rejected`, tổng số đo tập hợp lệ, khóa mồ côi và tổng trước/sau join.
- [x] TN03: tải đầy đủ, phát lại nguyên file, bản sao có Sales=`abc`; lưu audit và reject, giữ nguyên CSV gốc.
- [x] Kiểm tra tải tăng dần: 23 tháng đầu → thêm 12/2013 → phát lại 12/2013; kết quả cuối 4.248 dòng, Sales 819.811.
- [x] TN04: SCD Type 1 sửa nhãn; Type 2 đóng/mở phiên bản trong cùng transaction; lookup trước và đúng biên hiệu lực.
- [x] Kiểm tra không chồng khoảng, một dòng hiện hành và nạp lại sự kiện không tăng phiên bản; minh họa giới hạn Type 3.
- [ ] Tạo và chạy package SSIS thật; chụp Control Flow/Data Flow, mã batch, số dòng và đường lỗi. *(Đã tạo và thực thi thành công package `ssis/CoffeeETL/LoadCoffee.dtsx` và `SCD_TN04.dtsx` bằng `DTExec.exe` 64-bit v16.0.1000.6 trên SQL Server 2022 `Chi-Chie`, thu đủ BatchID/audit/reject tại `results/TN03/chi_2026-11-15/`; chỉ còn mở `CoffeeETL.dtproj` trong Visual Studio SSDT để chụp ảnh màn hình Designer chèn vào Word).*

Ca dữ liệu lỗi nhỏ của báo cáo: lấy tám dòng đầu, sửa Sales dòng đầu thành `abc`, Product dòng thứ hai thành rỗng; kỳ vọng sáu dòng hợp lệ với Sales 1.139. Khi chạy trên kho đã có dữ liệu, một dòng bị loại ở batch mới vẫn có thể có bản hợp lệ từ batch trước; phải nêu trạng thái kho để diễn giải số tổng.

Điều kiện bàn giao: log batch và reject truy ngược được tới file/dòng; các ca tải tăng dần, phát lại, sửa số có đáp án; SSIS chỉ đánh dấu đạt sau khi có log và ảnh chạy thật.

---

## 4.1 Kiến trúc luồng ETL: Staging – Dimension – Fact – Audit

Quy trình tích hợp dữ liệu của **CoffeeDW** được thiết kế theo kiến trúc bốn lớp nhằm tách biệt hoàn toàn việc tiếp nhận dữ liệu thô với việc kiểm định chất lượng và công bố số liệu phục vụ phân tích:

1. **Đăng ký Batch và Truy vết nguồn (`audit.LoadBatch`):**
   - Mỗi lần thực thi tạo một mã định danh `BatchID` (`uniqueidentifier` trên SQL Server / UUID hex trên SQLite), ghi nhận tên tệp (`SourceFile`), mã băm `SHA-256` (`SourceChecksum = 929bdcc7fd8f6bf21607618e7474df0683af6412b32b8c5af39a40e89b62ffce` đối với bản chuẩn `Coffee.csv`), thời điểm bắt đầu UTC (`StartedAt`), tổng số dòng đọc (`SourceCount`) và trạng thái khởi tạo `STAGED`.
   - Việc đăng ký `audit.LoadBatch` được commit trước khi gọi giao dịch nạp kho (`dw.usp_LoadCoffee`), kết hợp với `OnError` Event Handler trong package SSIS (`EST_OnError_LogFailedBatch`) và khối `try/except` trong `src/coffee_dw/sqlserver.py`. Nhờ đó, nếu giao dịch nạp kho gặp lỗi và `ROLLBACK`, bản ghi batch vẫn được giữ lại với trạng thái `FAILED` để phục vụ điều tra.

2. **Tiếp nhận nguyên trạng và Phân luồng kiểm tra tại Staging (`stg.CoffeeRaw` & `audit.RejectedRow`):**
   - Toàn bộ 20 cột của CSV được đọc ở dạng văn bản UTF-8 (`CodePage = 65001`), đánh số thứ tự dòng vật lý `SourceRow` bắt đầu từ `2` (dòng `1` là tiêu đề cột) và đóng gói toàn bộ bản ghi gốc vào chuỗi JSON (`RawJson` / `RawPayload`).
   - Quy tắc chuẩn hóa và kiểm tra chất lượng (đồng nhất giữa `src/coffee_dw/source.py` và `ssis/CoffeeETL/LoadCoffee.dtsx`):
     - **Chiều thời gian:** Cột `Date` được chuyển từ số sê-ri ngày Excel với mốc gốc `1899-12-30` (`DATEADD(day, TRY_CONVERT(int, [Date]), CONVERT(date, '1899-12-30'))`), kiểm tra bắt buộc là ngày đầu tháng (`DAY(MonthStart) = 1`) và tạo `DateKey = YYYYMMDD`.
     - **Chiều địa lý và sản phẩm:** Giữ `AreaCode` dạng chuỗi (`nvarchar(20)`), kiểm tra không rỗng đối với đủ 8 thuộc tính mô tả (`AreaCode, State, Market, MarketSize, ProductName, ProductLine, ProductType, Type`).
     - **11 chỉ tiêu số đo:** Chuyển đổi chính xác sang `DECIMAL(19,4)` trên SQL Server (hoặc số nguyên nhân `10.000` trên SQLite) cho `Sales, BudgetSales, Profit, BudgetProfit, COGS, BudgetCOGS, Margin, BudgetMargin, Marketing, Inventory, TotalExpenses`. **Tuyệt đối không thay thế chuỗi lỗi kiểu số bằng `0`**.
     - **Kiểm tra tính nhất quán lô (Batch-level consistency):** Các dòng hợp lệ về cú pháp tiếp tục được kiểm tra trùng khóa hạt ứng viên `(DateKey, AreaCode, ProductName)` và mâu thuẫn thuộc tính phụ thuộc hàm (`AreaCode -> State, Market, MarketSize`; `ProductName -> ProductLine, ProductType, Type`). Nếu vi phạm, toàn bộ các dòng liên quan bị gắn `RejectReason`.
     - **Bảo toàn dị thường nghiệp vụ:** Các dòng có `Profit < 0` (528 dòng), `Inventory < 0` (88 dòng), `Sales <> COGS + Margin` (2.088 dòng) hoặc `Profit <> Margin - TotalExpenses` (2.105 dòng) là đặc trưng của dữ liệu nguồn, được giữ nguyên giá trị và theo dõi qua truy vấn cảnh báo đối soát (`04_checks.sql`).

3. **Nạp chiều và Fact trong Giao dịch nguyên tử (`dw.usp_LoadCoffee`):**
   - Thủ tục `dw.usp_LoadCoffee` mở `TRANSACTION` kèm khóa ứng dụng độc quyền `sys.sp_getapplock` (`Resource = N'CoffeeDW.Load'`) để ngăn hai tiến trình ETL ghi tranh chấp.
   - Các dòng có `RejectReason IS NOT NULL` được chuyển sang `audit.RejectedRow(BatchID, SourceRow, Reason, RawJson)`.
   - Chiều thời gian `dw.DimDate` được chèn mới nếu chưa tồn tại (`WHERE NOT EXISTS`). Hai chiều `dw.DimLocation` và `dw.DimProduct` được cập nhật theo chính sách **SCD Type 1** rồi chèn các khóa nghiệp vụ mới để sinh khóa thay thế (`LocationKey`, `ProductKey`).
   - Bảng sự kiện `dw.FactSalesPerformance` được bảo vệ bởi khóa chính ghép `PK_FactSalesPerformance (DateKey, LocationKey, ProductKey)`:
     - Nếu bộ ba khóa đã tồn tại và có ít nhất một trong 11 số đo thay đổi (kiểm tra bằng toán tử tập hợp `EXCEPT`), hệ thống thực hiện `UPDATE` số đo kèm `BatchID` mới và tăng `@updated`.
     - Nếu bộ ba khóa chưa tồn tại, hệ thống thực hiện `INSERT` và tăng `@inserted`.
     - Nếu bộ ba khóa đã tồn tại và cả 11 số đo giữ nguyên, bản ghi được tính vào `UnchangedCount = @accepted - @inserted - @updated`.

---

## 4.2 Kiểm soát bất biến kế toán dòng và Đối soát sau nạp

Trước khi `COMMIT TRANSACTION`, `dw.usp_LoadCoffee` và `warehouse.py` cưỡng bức hai điều kiện đối soát tự động:

1. **Bất biến số lượng bản ghi:**
   $$\text{SourceCount} = \text{AcceptedCount} + \text{RejectedCount}$$
   $$\text{AcceptedCount} = \text{InsertedCount} + \text{UpdatedCount} + \text{UnchangedCount}$$
   Nếu chênh lệch khác `0`, giao dịch lập tức `THROW 50006` và `ROLLBACK`.
2. **Đối soát bảo toàn số đo theo từng hạt (`EXCEPT` hai chiều):**
   Toàn bộ tập dòng hợp lệ trong batch (`#mapped`) được đối chiếu 1–1 với `dw.FactSalesPerformance` trên khóa `(DateKey, LocationKey, ProductKey)` và cả 11 cột số đo. Nếu bất kỳ chỉ tiêu nào sai khác sau khi nạp, thủ tục `THROW 50005` và hủy giao dịch.

Kết quả chạy kiểm tra `sql/sqlserver/04_checks.sql` trên SQL Server 2022 (`Chi-Chie`, database `CoffeeDW`) sau khi nạp bản chuẩn `Coffee.csv`:

| Chỉ tiêu kiểm tra trên `CoffeeDW` | Kết quả thực chạy SQL Server 2022 | Đáp án tham chiếu nguồn | Chênh lệch |
| --- | ---: | ---: | ---: |
| Số dòng `dw.FactSalesPerformance` | 4.248 | 4.248 | 0 |
| Số kỳ `dw.DimDate` (`FirstMonth` – `LastMonth`) | 24 (`2012-01-01` – `2013-12-01`) | 24 (`2012-01-01` – `2013-12-01`) | 0 |
| Số địa bàn `dw.DimLocation` / Sản phẩm `dw.DimProduct` | 156 / 13 | 156 / 13 | 0 |
| Tổng `Sales` | 819.811,0000 | 819.811 | 0 |
| Tổng `BudgetSales` | 746.160,0000 | 746.160 | 0 |
| Tổng `Profit` | 259.543,0000 | 259.543 | 0 |
| Cảnh báo `NegativeProfit` / `NegativeInventory` | 528 / 88 | 528 / 88 | 0 |
| Cảnh báo `SalesMismatch` / `ProfitMismatch` | 2.088 / 2.105 | 2.088 / 2.105 | 0 |

---

## 4.3 Thực nghiệm quản lý thay đổi thuộc tính chiều — SCD Type 1, Type 2, Type 3 (TN04)

### 4.3.1 Thiết kế thực nghiệm
Trong tệp `Coffee.csv`, mỗi tên sản phẩm (`Product`) cố định ở một `Product Type` duy nhất trong suốt 24 tháng và chưa có cột mã sản phẩm độc lập. Để kiểm chứng đầy đủ cơ chế quản lý lịch sử chiều mà không làm bẩn dữ liệu phục vụ báo cáo, thực nghiệm **TN04** được cô lập trong script Python `learning/experiments/scd.py`, script T-SQL `sql/sqlserver/12_tn04_scd_demo.sql` và package SSIS `ssis/CoffeeETL/SCD_TN04.dtsx` trên hai kịch bản:
- **Kịch bản 1 (Báo cáo mục 4.3 — Sản phẩm `P01`):**
  - *Ca A (SCD Type 1):* Khởi tạo `P01` với tên bị gõ sai `'Amareto'`, sau đó cập nhật thành `'Amaretto'`.
  - *Ca B (SCD Type 2):* Khởi tạo `P01` thuộc nhóm `'Coffee'` hiệu lực `[2012-01-01, 9999-12-31)`, `IsCurrent = 1`. Tại mốc biên `T = 2013-01-01`, sản phẩm chuyển sang nhóm `'Specialty'`. Trong cùng một giao dịch, phiên bản cũ được đóng (`ValidTo = '2013-01-01', IsCurrent = 0`) và phiên bản mới được mở (`ValidFrom = '2013-01-01', ValidTo = '9999-12-31', IsCurrent = 1`). Phát lại sự kiện đổi nhóm lần thứ hai để kiểm tra tính lũy đẳng (idempotence).
  - *Ca C (SCD Type 3):* Khởi tạo `P01` ở nhóm `'Coffee'`, sau đó đổi liên tiếp sang `'Specialty'` rồi `'Premium'`.
- **Kịch bản 2 (Sổ tay TN04 — Địa bàn `A01`):**
  - Sửa nhãn `'Wset'` → `'West'` (Type 1); đổi phân hạng `'Minor'` → `'Major'` tại biên `2012-07-01` (Type 2) và đổi tiếp sang `'Pilot'` trên bảng Type 3.

### 4.3.2 Kết quả thực chạy trên SQLite và SQL Server 2022 (`Chi-Chie`)

**Bảng 4.1. Kết quả các phiên bản SCD Type 2 của `P01` sau khi chạy và phát lại sự kiện (`sql/sqlserver/12_tn04_scd_demo.sql`):**

| `ProductKey` | `Code` | `ProductName` | `ProductType` | `ValidFrom` | `ValidTo` | `IsCurrent` |
| ---: | --- | --- | --- | --- | --- | ---: |
| 1 | `P01` | Amaretto | Coffee | `2012-01-01` | `2013-01-01` | 0 |
| 2 | `P01` | Amaretto | Specialty | `2013-01-01` | `9999-12-31` | 1 |

**Bảng 4.2. Kết quả tra cứu khóa theo mốc thời gian nghiệp vụ với điều kiện nửa mở `ValidFrom <= OrderMonth AND OrderMonth < ValidTo`:**

| Bộ thử | Ngày nghiệp vụ | Khóa tra được (`ProductKey` / `SK`) | Phân loại hiển thị | Giải thích tại mốc biên |
| --- | --- | ---: | --- | --- |
| `P01` | `2012-12-01` | 1 | `Coffee` | Trước ngày hiệu lực `2013-01-01`: bảo toàn lịch sử nhóm cũ |
| `P01` | `2013-01-01` | 2 | `Specialty` | Đúng tại biên `T = 2013-01-01`: cận phải mở `< ValidTo` loại phiên bản 1, khớp duy nhất phiên bản 2 |
| `P01` | `2013-02-01` | 2 | `Specialty` | Sau biên hiệu lực: tiếp tục nhận phiên bản hiện hành 2 |
| `A01` | `2012-06-01` | 1 | `Minor` | Trước biên `2012-07-01`: nhận phân hạng `Minor` |
| `A01` | `2012-07-01` | 2 | `Major` | Đúng tại biên `2012-07-01`: nhận phân hạng mới `Major` |

- **Kiểm tra các điều kiện nghiệm thu SCD trên SQL Server 2022:**
  - `TotalVersionsAfterReplay = 2` (phát lại cùng sự kiện đổi nhóm không sinh thêm phiên bản thứ 3).
  - `CurrentVersionCount = 1` (ràng buộc `CREATE UNIQUE INDEX UX_Type2_OneCurrent ON #Type2(Code) WHERE IsCurrent = 1` bảo đảm mỗi mã chỉ có đúng 1 dòng hiện hành).
  - `OverlappingIntervals = 0` (không có hai khoảng hiệu lực nào chồng lấn).
  - **Giới hạn Type 3:** Sau hai lần đổi (`Coffee` → `Specialty` → `Premium` với `P01`, hoặc `Minor` → `Major` → `Pilot` với `A01`), dòng Type 3 chỉ còn giữ `(CurrentType = 'Premium', PreviousType = 'Specialty')` và làm mất hoàn toàn lịch sử ban đầu `'Coffee'`. Do đó Type 2 là lựa chọn bắt buộc khi cần tái lập báo cáo lịch sử tại bất kỳ kỳ giao dịch nào.

---

## 4.4 Thực nghiệm tải ban đầu, tải tăng dần, phát lại, sửa số và xử lý dòng lỗi (TN03)

Thực nghiệm **TN03** được thực thi đầy đủ trên cả bản tham chiếu SQLite (`learning/experiments/incremental.py`) và package SSIS native `ssis/CoffeeETL/LoadCoffee.dtsx` qua công cụ `DTExec.exe (Version 16.0.1000.6 for 64-bit)` nạp vào SQL Server 2022 (`Chi-Chie`, database `CoffeeDW`).

### 4.4.1 Kết quả 7 lượt chạy SSIS `LoadCoffee.dtsx` trên SQL Server 2022

| Lượt chạy | `BatchID` (SQL Server `audit.LoadBatch`) | Tệp đầu vào | Dòng đọc (`Source`) | Hợp lệ (`Accepted`) | Bị loại (`Rejected`) | Chèn mới (`Inserted`) | Cập nhật (`Updated`) | Giữ nguyên (`Unchanged`) | Tổng dòng Fact | Tổng `Sales` trên Fact |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1. 23 kỳ đầu (`01/2012–11/2013`) | `A56DAA5A-2B66-47E0-BD54-AB4D26DFA88D` | `history_23m.csv` | 4.071 | 4.071 | 0 | 4.071 | 0 | 0 | 4.071 | 784.231,0000 |
| 2. Thêm kỳ `12/2013` | `4EED60E8-74C2-4CEE-B50B-DDBEDBF95258` | `new_201312.csv` | 177 | 177 | 0 | 177 | 0 | 0 | 4.248 | 819.811,0000 |
| 3. Phát lại kỳ `12/2013` | `11F7FFFF-DC0B-4B6E-A25B-25DC9272564E` | `new_201312.csv` | 177 | 177 | 0 | 0 | 0 | 177 | 4.248 | 819.811,0000 |
| 4. Sửa số `+10` cùng grain | `E412F96D-88CF-42CD-9765-7C16440716D1` | `correction_plus10.csv` | 177 | 177 | 0 | 0 | 1 | 176 | 4.248 | 819.821,0000 |
| 5. Ca 8 dòng có 2 dòng lỗi | `FDC68A75-53CA-4EA4-BA3F-571D144DD1FA` | `invalid_8rows.csv` | 8 | 6 | 2 | 0 | 0 | 6 | 4.248 | 819.821,0000 *(Batch valid = 1.139,0000)* |
| 6. Nạp chuẩn toàn bộ nguồn | `325E810B-B722-4BC3-A11D-8A6CAD5F8B50` | `Coffee.csv` | 4.248 | 4.248 | 0 | 4.248 | 0 | 0 | 4.248 | 819.811,0000 |
| 7. Phát lại toàn bộ nguồn | `7907ADCB-A79D-4797-A8B9-853EF6517E71` | `Coffee.csv` | 4.248 | 4.248 | 0 | 0 | 0 | 4.248 | 4.248 | 819.811,0000 |

### 4.4.2 Truy vết chi tiết dòng bị loại trong `audit.RejectedRow`

Trong Lượt chạy 5 (`BatchID = FDC68A75-53CA-4EA4-BA3F-571D144DD1FA`, tệp `invalid_8rows.csv`), 2 dòng lỗi bị cô lập chính xác vào `audit.RejectedRow` mà không làm hỏng 6 dòng hợp lệ (`SUM(Sales)` của 6 dòng hợp lệ trong batch = `1.139`):

| `BatchID` | `SourceRow` | `Reason` | Trích xuất `RawJson` gốc |
| --- | ---: | --- | --- |
| `FDC68A75-53CA-4EA4-BA3F-571D144DD1FA` | 2 | `Sales: invalid numeric value` | `{"Area Code":"719","Date":"40909","Market":"Central",...,"Product":"Amaretto",...,"Sales":"abc","Total Expenses":"36"}` |
| `FDC68A75-53CA-4EA4-BA3F-571D144DD1FA` | 3 | `ProductName: required` | `{"Area Code":"970","Date":"40909","Market":"Central",...,"Product":"",...,"Sales":"190","Total Expenses":"39"}` |

- **Diễn giải trạng thái kho khi nạp batch lỗi:**
  - Khi chạy `invalid_8rows.csv` vào một kho trống (như trong `learning/experiments/incremental.py` và `tests/test_pipeline.py`), kho sau nạp có đúng `6` dòng và `SUM(Sales) = 1.139`.
  - Khi chạy `invalid_8rows.csv` trên kho đã nạp sẵn dữ liệu lịch sử (Lượt 5 trên SQL Server), 2 dòng bị loại ở batch mới chỉ bị chặn không cho ghi đè vào fact, trong khi bản ghi hợp lệ của cùng grain từ batch trước vẫn được bảo toàn trên `dw.FactSalesPerformance`. Do đó, việc đối soát chất lượng batch tăng dần luôn phải kiểm tra đồng thời `audit.LoadBatch` (`SourceDelta = 0`, `AcceptedDelta = 0`) và tổng số đo của các dòng hợp lệ thuộc chính `BatchID` đó (`1.139,0000`).
