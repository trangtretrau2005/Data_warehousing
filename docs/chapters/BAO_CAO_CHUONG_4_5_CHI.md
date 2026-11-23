# BÁO CÁO PHẦN CHI — CHƯƠNG 4 VÀ CHƯƠNG 5 (ĐỊNH DẠNG CHUẨN GOOGLE DOC NHÓM)

> **Hướng dẫn dán vào Google Doc:**
> - Toàn bộ nội dung dưới đây được biên soạn theo đúng quy chuẩn định dạng, văn phong học thuật và hệ thống đánh số mục (`4.1` → `4.1.1` → `a)`), bảng biểu (`Bảng 4.x`, `Bảng 5.x`) và hình ảnh (`Hình 4.x`, `Hình 5.x`) nối tiếp trực tiếp sau **Chương 3** của Thanh trên Google Doc nhóm.
> - Tại mỗi vị trí **[Chèn Hình X.Y: ...]** bên dưới, bạn chèn file ảnh tương ứng đã có sẵn trong thư mục `results/TN03/chi_2026-11-15/`, `results/TN04/chi_2026-11-15/`, `results/TN05/chi_2026-11-15/`, `results/TN06/chi_2026-11-15/` (hoặc ảnh bổ sung từ `results/native_build_20261120/ui/`).

---

# CHƯƠNG 4. QUY TRÌNH ETL VÀ KIỂM SOÁT CHẤT LƯỢNG DỮ LIỆU

## 4.1. Kiến trúc và luồng tích hợp dữ liệu ETL

### 4.1.1. Tổng quan luồng ETL Staging – Dimension – Fact – Audit

Sau khi hoàn thiện thiết kế mô hình Star Schema và các ràng buộc toàn vẹn ở Chương 3, hệ thống CoffeeDW cần một quy trình ETL (Extract – Transform – Load) có khả năng tiếp nhận dữ liệu từ tệp nguồn `Coffee.csv`, kiểm định chất lượng dữ liệu ở mức dòng và mức lô, cập nhật các bảng chiều và nạp bảng sự kiện một cách an toàn.

Quy trình ETL của hệ thống CoffeeDW được thiết kế theo kiến trúc bốn lớp tách biệt nhằm bảo đảm dữ liệu thô luôn được lưu vết trước khi biến đổi, đồng thời ngăn chặn tuyệt đối việc dữ liệu lỗi làm sai lệch các chỉ tiêu tài chính trong kho:

1. **Lớp đăng ký lô nạp và kiểm toán (`audit.LoadBatch`, `audit.RejectedRow`):** Ghi nhận thông tin định danh của từng lần chạy ETL (mã `BatchID`, tên tệp nguồn, mã băm `SHA-256`, thời gian bắt đầu/kết thúc, trạng thái thực thi và các bộ đếm đối soát dòng) cùng danh sách chi tiết từng bản ghi bị từ chối.
2. **Lớp tiếp nhận tạm thời (`stg.CoffeeRaw`):** Tiếp nhận toàn bộ dữ liệu thô từ tệp CSV kèm số thứ tự dòng vật lý (`SourceRow`), bản sao nguyên trạng dạng JSON (`RawJson`), các cột đã chuẩn hóa kiểu dữ liệu và lý do loại bỏ (`RejectReason`) nếu dòng dữ liệu vi phạm quy tắc chất lượng.
3. **Lớp bảng chiều (`dw.DimDate`, `dw.DimLocation`, `dw.DimProduct`):** Lưu trữ các thực thể phân tích duy nhất, sinh khóa thay thế (`Surrogate Key`) và quản lý sự thay đổi thuộc tính theo thời gian (Slowly Changing Dimensions – SCD).
4. **Lớp bảng sự kiện (`dw.FactSalesPerformance`):** Lưu trữ 11 chỉ tiêu kinh doanh ở đúng độ hạt `Tháng × Mã vùng × Sản phẩm` thông qua bộ ba khóa ngoại `(DateKey, LocationKey, ProductKey)` kèm thông tin truy vết ngược về lô nạp (`BatchID`, `SourceRow`).

| Thành phần trong luồng ETL | Đối tượng SQL Server / SSIS / Python | Vai trò chính trong quy trình |
| --- | --- | --- |
| Đăng ký và kiểm toán lô nạp | `audit.LoadBatch` | Quản lý vòng đời batch (`STAGED`, `COMPLETED`, `FAILED`), lưu `SHA-256` và đối soát số dòng |
| Lưu trữ bản ghi lỗi | `audit.RejectedRow` | Cô lập dòng sai kiểu, thiếu khóa hoặc trùng độ hạt kèm `SourceRow`, `Reason` và `RawJson` |
| Vùng đệm tiếp nhận | `stg.CoffeeRaw` | Lưu dữ liệu thô kèm kết quả ép kiểu và cờ kiểm tra hợp lệ trước khi nạp vào kho |
| Thủ tục nạp kho nguyên tử | `dw.usp_LoadCoffee` | Thực thi giao dịch nạp Dimension, tra cứu khóa, `INSERT`/`UPDATE` Fact và kiểm tra bất biến |
| Gói tích hợp SSIS native | `ssis/CoffeeETL/LoadCoffee.dtsx` (`CoffeeETLTrang`) | Tự động hóa luồng đọc CSV, ghi staging, gọi `dw.usp_LoadCoffee` và bắt lỗi qua `OnError` |
| Bản tham chiếu kiểm thử | `src/coffee_dw/warehouse.py` | Thực thi quy trình ETL tương đương trên SQLite để kiểm thử tự động và đối soát chéo |

*Bảng 4.1. Các thành phần kiến trúc trong quy trình ETL của hệ thống CoffeeDW*

### 4.1.2. Cơ chế đăng ký Batch, Checksum SHA-256 và truy vết lỗi ngoài giao dịch

Một yêu cầu cốt lõi của hệ thống kho dữ liệu là mọi lần chạy ETL — dù thành công hay thất bại — đều phải để lại dấu vết kiểm toán đầy đủ. Để đạt được mục tiêu này, quy trình đăng ký lô nạp được tách thành một bước độc lập trước khi mở giao dịch nạp kho:

* **Khởi tạo mã định danh và mã băm nguồn:** Ngay khi bắt đầu một lượt chạy, hệ thống sinh mã `BatchID` (`UNIQUEIDENTIFIER` trên SQL Server) và tính mã băm `SHA-256` của tệp đầu vào (đối với tệp chuẩn `Coffee.csv`, giá trị `SourceChecksum` luôn là `929bdcc7fd8f6bf21607618e7474df0683af6412b32b8c5af39a40e89b62ffce`).
* **Ghi nhận trạng thái `STAGED` ngoài giao dịch chính:** Bản ghi `audit.LoadBatch` và dữ liệu trong `stg.CoffeeRaw` được lưu với trạng thái `STAGED` trước khi gọi thủ tục `dw.usp_LoadCoffee`.
* **Bảo toàn nhật ký khi giao dịch nạp kho Rollback:** Trong trường hợp thủ tục `dw.usp_LoadCoffee` phát hiện vi phạm đối soát hoặc gặp lỗi hệ thống, giao dịch nạp bảng Dimension và Fact sẽ được hoàn tác (`ROLLBACK TRANSACTION`) để bảo vệ tính nguyên vẹn của kho dữ liệu. Ngay sau đó, khối xử lý ngoại lệ (`CATCH` / sự kiện `OnError` trong SSIS `EST_OnError_LogFailedBatch` / khối `except` trong `src/coffee_dw/sqlserver.py`) sẽ cập nhật trạng thái của `audit.LoadBatch` thành `FAILED` kèm thông điệp lỗi trong `Notes` mà không làm mất bản ghi kiểm toán của lần chạy đó.

---

## 4.2. Quy tắc chuẩn hóa, kiểm soát chất lượng và nạp kho dữ liệu

### 4.2.1. Chuẩn hóa dữ liệu tại lớp Staging

Tại bước tiếp nhận tệp CSV vào `stg.CoffeeRaw`, hệ thống đọc toàn bộ 20 cột ở định dạng chuỗi Unicode (`UTF-8`, `CodePage = 65001`), gán chỉ số dòng vật lý `SourceRow` bắt đầu từ `2` (do dòng `1` là dòng tiêu đề cột) và áp dụng bộ quy tắc chuẩn hóa thống nhất:

* **Chuyển đổi thời gian từ số sê-ri Excel:** Trường `Date` trong nguồn lưu số ngày tính từ mốc gốc `1899-12-30` của Microsoft Excel. Hệ thống chuyển đổi giá trị này sang kiểu ngày chuẩn thông qua biểu thức `DATEADD(day, TRY_CONVERT(int, [Date]), CONVERT(date, '1899-12-30'))`, kiểm tra ngày kết quả bắt buộc là ngày đầu tháng (`DAY(MonthStart) = 1`) và sinh khóa thời gian `DateKey` dạng số nguyên `YYYYMMDD` (ví dụ: `40909` → `2012-01-01` → `DateKey = 20120101`).
* **Chuẩn hóa mã vùng và thuộc tính mô tả:** Trường `Area Code` được cắt khoảng trắng hai đầu (`LTRIM/RTRIM`) và giữ nguyên ở kiểu chuỗi `NVARCHAR(20)` để không làm mất chữ số `0` ở đầu nếu mở rộng vùng địa lý. Các thuộc tính phân loại địa lý (`State`, `Market`, `MarketSize`) và sản phẩm (`ProductName`, `ProductLine`, `ProductType`, `Type`) được cắt khoảng trắng thừa và kiểm tra khác rỗng.
* **Chuyển đổi chính xác 11 chỉ tiêu số đo:** Toàn bộ 11 cột chỉ tiêu kinh doanh (`Sales`, `BudgetSales`, `Profit`, `BudgetProfit`, `COGS`, `BudgetCOGS`, `Margin`, `BudgetMargin`, `Marketing`, `Inventory`, `TotalExpenses`) được chuyển đổi sang kiểu số thập phân cố định `DECIMAL(19,4)` bằng hàm chuyển đổi an toàn `TRY_CONVERT(decimal(19,4), ...)`. Hệ thống tuyệt đối không tự động thay thế các chuỗi lỗi kiểu số (như `'abc'`) bằng giá trị `0`, bởi việc gán `0` sẽ làm sai lệch số trung bình và che giấu lỗi dữ liệu nguồn.

### 4.2.2. Phân luồng bản ghi lỗi và bảo toàn dị thường nghiệp vụ

Hệ thống phân biệt rõ ràng giữa **lỗi kỹ thuật/cấu trúc** (phải loại bỏ khỏi bảng Fact và đưa vào `audit.RejectedRow`) với **dị thường nghiệp vụ có thật trong nguồn** (phải bảo toàn nguyên giá trị để phân tích và đối soát):

| Nhóm kiểm tra | Điều kiện phát hiện trên dòng / lô dữ liệu | Quyết định xử lý trong ETL | Nơi lưu vết / đối soát |
| --- | --- | --- | --- |
| Lỗi định dạng ngày | `Date` rỗng, không phải số nguyên hoặc không rơi vào ngày mùng 1 đầu tháng | Từ chối nạp (`Reject`), ghi lý do `Date: invalid value` | `audit.RejectedRow` |
| Thiếu thuộc tính chiều | Một trong các cột `AreaCode`, `State`, `Market`, `MarketSize`, `ProductName`, `ProductLine`, `ProductType`, `Type` bị rỗng | Từ chối nạp (`Reject`), ghi rõ tên cột thiếu (`<Column>: required`) | `audit.RejectedRow` |
| Lỗi kiểu dữ liệu số đo | Bất kỳ cột nào trong 11 số đo không thể chuyển sang `DECIMAL(19,4)` (ví dụ `Sales = 'abc'`) | Từ chối nạp (`Reject`), ghi rõ `<Measure>: invalid numeric value`, không thay bằng `0` | `audit.RejectedRow` |
| Trùng khóa độ hạt trong lô | Hai dòng hợp lệ trong cùng batch có cùng bộ ba `(DateKey, AreaCode, ProductName)` | Từ chối các dòng trùng (`Duplicate grain key in batch: Date + Area Code + Product`) | `audit.RejectedRow` |
| Mâu thuẫn phụ thuộc hàm | Cùng `AreaCode` nhưng khác `(State, Market, MarketSize)` hoặc cùng `ProductName` nhưng khác `(ProductLine, ProductType, Type)` trong batch | Từ chối nạp (`Inconsistent location/product attributes within batch`) | `audit.RejectedRow` |
| Lợi nhuận hoặc tồn kho âm | `Profit < 0` (`528` dòng) hoặc `Inventory < 0` (`88` dòng) | Chấp nhận nạp (`Accept`), giữ nguyên số âm theo đúng thực tế hạch toán nguồn | `dw.FactSalesPerformance` & `04_checks.sql` |
| Chênh lệch đẳng thức kế toán | `Sales <> COGS + Margin` (`2.088` dòng) hoặc `Profit <> Margin - TotalExpenses` (`2.105` dòng) | Chấp nhận nạp (`Accept`), không tự ý sửa lại số đo nguồn, gắn cờ theo dõi đối soát | `dw.FactSalesPerformance` & `04_checks.sql` |

*Bảng 4.2. Quy tắc phân luồng bản ghi lỗi và xử lý dị thường nghiệp vụ trong CoffeeDW*

### 4.2.3. Thủ tục nạp chiều, bảng sự kiện và kiểm soát bất biến kế toán dòng

Khi dữ liệu đã nằm trong `stg.CoffeeRaw`, thủ tục `dw.usp_LoadCoffee` thực thi việc nạp kho trong một giao dịch nguyên tử (`BEGIN TRANSACTION` kèm `SET XACT_ABORT ON`) và khóa ứng dụng độc quyền `sys.sp_getapplock` (`Resource = N'CoffeeDW.Load'`) nhằm ngăn chặn hai tiến trình chạy chồng lấn:

1. **Tách dòng lỗi sang bảng kiểm toán:** Toàn bộ các bản ghi trong `stg.CoffeeRaw` có `RejectReason IS NOT NULL` được chèn vào bảng `audit.RejectedRow(BatchID, SourceRow, Reason, RawJson)` để lưu giữ bằng chứng phục vụ tra cứu ngược về đúng dòng tệp CSV.
2. **Cập nhật và bổ sung các bảng Dimension:**
   * Với `dw.DimDate`: Chèn các kỳ `DateKey` mới từ tập bản ghi hợp lệ (`WHERE NOT EXISTS`), tự động tính các cột `Year`, `Quarter`, `Month`.
   * Với `dw.DimLocation` và `dw.DimProduct`: Thực hiện cập nhật thuộc tính mô tả nếu có sự thay đổi trên cùng khóa tự nhiên (`AreaCode` hoặc `ProductName`), sau đó chèn các khóa tự nhiên mới chưa có trong chiều để hệ thống tự sinh khóa thay thế `LocationKey` và `ProductKey`.
3. **Ánh xạ khóa thay thế và nạp bảng Fact theo cơ chế Lũy đẳng (Idempotent Upsert):**
   * Tập bản ghi hợp lệ được nối (`INNER JOIN`) với ba bảng chiều để thu được bộ khóa `(DateKey, LocationKey, ProductKey)` lưu vào bảng tạm `#mapped`.
   * Đối với các khóa đã tồn tại trong `dw.FactSalesPerformance`, thủ tục chỉ thực hiện `UPDATE` khi phát hiện ít nhất một trong 11 chỉ tiêu số đo thay đổi (sử dụng phép so sánh tập hợp `WHERE EXISTS (SELECT ... EXCEPT SELECT ...)`). Số dòng thực sự thay đổi giá trị được ghi nhận vào biến `@updated`.
   * Đối với các khóa chưa tồn tại trong `dw.FactSalesPerformance`, thủ tục thực hiện `INSERT` và ghi nhận số dòng vào biến `@inserted`.
   * Các bản ghi hợp lệ đã có sẵn trong kho với số đo hoàn toàn giống hệt sẽ không bị ghi đè thừa và được tính vào chỉ số `UnchangedCount = @accepted - @inserted - @updated`.
4. **Cưỡng bức bất biến kế toán dòng và bảo toàn số đo trước khi Commit:**
   * Hệ thống kiểm tra hai đẳng thức bảo toàn dòng cho mọi batch:
     $$\text{SourceCount} = \text{AcceptedCount} + \text{RejectedCount}$$
     $$\text{AcceptedCount} = \text{InsertedCount} + \text{UpdatedCount} + \text{UnchangedCount}$$
   * Đồng thời, thủ tục đối chiếu hai chiều bằng toán tử `EXCEPT` giữa bảng tạm `#mapped` và bảng `dw.FactSalesPerformance` trên toàn bộ khóa và 11 cột số đo. Nếu phát hiện bất kỳ dòng hợp lệ nào bị lệch số đo sau nạp (mã lỗi `50005`) hoặc tổng số dòng không khớp đẳng thức kế toán (mã lỗi `50006`), giao dịch lập tức bị hủy bỏ (`ROLLBACK TRANSACTION`).

---

## 4.3. Quản lý thay đổi thuộc tính chiều theo thời gian – SCD

### 4.3.1. Cơ sở áp dụng SCD Type 1, Type 2 và Type 3 trong CoffeeDW

Trong quá trình vận hành kho dữ liệu, các thuộc tính mô tả của sản phẩm hoặc địa bàn kinh doanh có thể thay đổi theo thời gian (ví dụ: đính chính lỗi chính tả tên sản phẩm/thị trường, hoặc tái phân loại một sản phẩm từ nhóm thông thường sang nhóm đặc sản từ một kỳ nhất định). Ralph Kimball định nghĩa ba kỹ thuật cơ bản để xử lý các thay đổi này (Slowly Changing Dimensions – SCD):

| Kỹ thuật SCD | Cơ chế cập nhật trên bảng Dimension | Ưu điểm và phạm vi áp dụng | Hạn chế cần lưu ý |
| --- | --- | --- | --- |
| **SCD Type 1** (Ghi đè) | Cập nhật trực tiếp giá trị mới đè lên giá trị cũ trên cùng dòng (`LocationKey` / `ProductKey` giữ nguyên) | Cấu trúc đơn giản, phù hợp khi sửa lỗi nhập liệu, chuẩn hóa chính tả mà không cần giữ lịch sử sai | Làm mất hoàn toàn trạng thái phân loại cũ trước thời điểm cập nhật |
| **SCD Type 2** (Tạo dòng phiên bản mới) | Giữ nguyên dòng cũ, đóng khoảng hiệu lực (`ValidTo = T`, `IsCurrent = 0`) và chèn dòng mới với khóa thay thế mới (`ValidFrom = T`, `ValidTo = 9999-12-31`, `IsCurrent = 1`) | Bảo toàn toàn bộ lịch sử phân loại theo thời gian; gán đúng sự kiện lịch sử vào phiên bản chiều tại kỳ phát sinh | Kích thước bảng chiều tăng theo số lần thay đổi; cần điều kiện tra cứu theo khoảng hiệu lực |
| **SCD Type 3** (Thêm cột giá trị cũ) | Giữ một dòng duy nhất cho mỗi mã nghiệp vụ, lưu trạng thái mới ở `CurrentType` và đẩy trạng thái liền trước sang `PreviousType` | Cho phép xem nhanh trạng thái hiện tại và trạng thái ngay trước đó trên cùng một dòng | Chỉ nhớ được tối đa 1 lần đổi gần nhất; mất lịch sử gốc nếu thuộc tính thay đổi từ 2 lần trở lên |

*Bảng 4.3. So sánh ba kỹ thuật quản lý thay đổi thuộc tính chiều SCD Type 1, Type 2 và Type 3*

Trong bộ dữ liệu gốc `Coffee.csv`, mỗi tên sản phẩm (`ProductName`) và mã vùng (`AreaCode`) giữ nguyên thuộc tính phân loại trong suốt 24 tháng. Do đó, luồng nạp chuẩn (`dw.usp_LoadCoffee`) áp dụng chính sách **SCD Type 1** để đồng bộ nhãn mô tả nếu có bản đính chính, trong khi cơ chế **SCD Type 2** và **SCD Type 3** được thiết kế và kiểm chứng trên môi trường mô phỏng biệt lập (Thực nghiệm TN04) để sẵn sàng mở rộng khi doanh nghiệp phát sinh nghiệp vụ tái phân nhóm sản phẩm hoặc thị trường.

### 4.3.2. Thiết kế cơ chế đóng – mở phiên bản và tra cứu theo mốc hiệu lực

Đối với **SCD Type 2**, mỗi phiên bản của một thực thể chiều được quản lý bởi bộ thuộc tính thời gian hiệu lực nửa mở `[ValidFrom, ValidTo)` và cờ `IsCurrent`:

* **Quy ước khoảng nửa mở `[ValidFrom, ValidTo)`:** Một phiên bản có hiệu lực tại ngày giao dịch `OrderMonth` khi và chỉ khi thỏa mãn điều kiện:
  $$\text{ValidFrom} \le \text{OrderMonth} < \text{ValidTo}$$
  Việc sử dụng dấu nhỏ hơn nghiêm ngặt (`< ValidTo`) ở cận phải kết hợp với việc đặt `ValidTo` của phiên bản cũ đúng bằng `ValidFrom` của phiên bản mới (`T`) giúp loại bỏ hoàn toàn khoảng trống hoặc sự chồng lấn tại ngày biên chuyển giao `T`.
* **Giao dịch đóng cũ – mở mới và tính lũy đẳng:** Khi nhận một sự kiện thay đổi thuộc tính tại mốc `T`, hệ thống kiểm tra phiên bản hiện hành (`IsCurrent = 1`). Nếu giá trị thuộc tính mới trùng với giá trị đang hiện hành (trường hợp phát lại sự kiện), hệ thống bỏ qua để không sinh thêm phiên bản trùng lặp. Nếu giá trị thực sự thay đổi, hệ thống đóng dòng hiện hành (`ValidTo = T`, `IsCurrent = 0`) và chèn dòng phiên bản mới (`ValidFrom = T`, `ValidTo = '9999-12-31'`, `IsCurrent = 1`) trong cùng một giao dịch, đồng thời bảo vệ bằng chỉ mục duy nhất có điều kiện `WHERE IsCurrent = 1`.

---

## 4.4. Thực nghiệm TN03 – Kiểm chứng quy trình ETL, tải tăng dần, phát lại, sửa số và cô lập dòng lỗi

### 4.4.1. Mục tiêu và phương pháp thực hiện

Thực nghiệm TN03 được xây dựng nhằm kiểm chứng toàn diện tính đúng đắn, tính lũy đẳng (idempotence) và khả năng cô lập lỗi của quy trình ETL trên cả hai môi trường: bản tham chiếu Python/SQLite (`learning/experiments/incremental.py`) và hệ quản trị SQL Server 2022 kết hợp gói SSIS native (`ssis/CoffeeETL/LoadCoffee.dtsx` thực thi qua `DTExec.exe` 64-bit v16.0.1000.6 trên máy Chi `Chi-Chie`, cùng bộ kiểm chứng mở rộng 8 ca chạy trực tiếp trong Visual Studio SSDT `ssis/CoffeeETLTrangAcceptance` trên máy Trang).

Nhóm thiết kế 7 kịch bản kiểm thử liên tiếp (và mở rộng thành 8 kịch bản kèm kiểm thử tiêm lỗi Rollback trên môi trường tích hợp), trong đó tệp nguồn `data/raw/Coffee.csv` (`SHA-256: 929bdcc7fd8f6bf21607618e7474df0683af6412b32b8c5af39a40e89b62ffce`) được giữ nguyên bất biến; mọi tệp tách kỳ, sửa số hoặc gài lỗi đều được sinh ra dưới dạng bản sao biệt lập:

1. **Lượt 1 – Nạp lịch sử 23 tháng đầu (`01/2012 – 11/2013`):** Tách `4.071` dòng thuộc 23 tháng đầu tiên vào tệp `history_23m.csv` và nạp vào kho trống.
2. **Lượt 2 – Tải tăng dần kỳ mới (`12/2013`):** Nạp tệp `new_201312.csv` chứa `177` dòng của tháng `12/2013`.
3. **Lượt 3 – Phát lại cùng kỳ (`12/2013`):** Chạy lại chính tệp `new_201312.csv` lần thứ hai để kiểm tra hệ thống không nhân đôi bản ghi hay cộng dồn doanh số.
4. **Lượt 4 – Sửa số đo trên cùng độ hạt (`+10 Sales`):** Tạo bản sao `correction_plus10.csv` của kỳ `12/2013`, tăng giá trị `Sales` của dòng đầu tiên (`Date = 2013-12-01`, `AreaCode = 303`, `Product = Amaretto`) thêm `+10` đơn vị để kiểm tra cơ chế `UPDATE` đúng 1 dòng thay đổi và giữ nguyên `176` dòng còn lại.
5. **Lượt 5 – Nạp lô dữ liệu hỗn hợp có chứa dòng lỗi (`invalid_8rows.csv`):** Trích 8 dòng đầu của tệp nguồn, sửa dòng dữ liệu đầu tiên (`SourceRow = 2`) thành `Sales = 'abc'` và sửa dòng thứ hai (`SourceRow = 3`) thành `Product = ''` (rỗng). Kỳ vọng hệ thống loại đúng 2 dòng lỗi vào `audit.RejectedRow` và chấp nhận 6 dòng hợp lệ có tổng `Sales = 1.139`.
6. **Lượt 6 – Nạp chuẩn toàn bộ tệp nguồn (`Coffee.csv`):** Làm sạch kho về trạng thái chuẩn và nạp toàn bộ `4.248` dòng từ tệp `Coffee.csv` gốc.
7. **Lượt 7 – Phát lại toàn bộ tệp nguồn (`Coffee.csv`):** Chạy lại nguyên tệp `Coffee.csv` (`4.248` dòng) trên kho đã đầy đủ dữ liệu để xác nhận `Inserted = 0`, `Updated = 0`, `Unchanged = 4.248`.

**[Chèn Hình 4.1: Ảnh chụp giao diện gói SSIS `LoadCoffee.dtsx` và cấu hình luồng thực thi trong Visual Studio (`results/TN03/chi_2026-11-15/TN03_ssis_vs.jpg`)]**
*Hình 4.1. Giao diện thiết kế gói SSIS `LoadCoffee.dtsx` trong Visual Studio*

**[Chèn Hình 4.2: Sơ đồ luồng Control Flow / Data Flow và kiến trúc kiểm soát ETL của Thực nghiệm TN03 (`results/TN03/chi_2026-11-15/TN03_flow.png`)]**
*Hình 4.2. Sơ đồ luồng xử lý ETL và cơ chế phân luồng bản ghi hợp lệ – bản ghi lỗi trong TN03*

### 4.4.2. Kết quả thực nghiệm trên Python/SQLite và SSIS/SQL Server

Sau khi thực thi chuỗi 7 lượt nạp qua package SSIS `LoadCoffee.dtsx` trên SQL Server 2022 (`CoffeeDW`), bảng kiểm toán `audit.LoadBatch` và bảng sự kiện `dw.FactSalesPerformance` ghi nhận kết quả khớp tuyệt đối với đáp án đối soát trên bản tham chiếu Python/SQLite:

| Lượt chạy | Mã lô (`BatchID` trên SQL Server) | Tệp đầu vào | Dòng đọc (`Source`) | Hợp lệ (`Accepted`) | Bị loại (`Rejected`) | Chèn mới (`Inserted`) | Cập nhật (`Updated`) | Giữ nguyên (`Unchanged`) | Tổng dòng Fact | Tổng `Sales` trên Fact |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1. 23 kỳ đầu (`01/2012–11/2013`) | `A56DAA5A-2B66-47E0-BD54-AB4D26DFA88D` | `history_23m.csv` | 4.071 | 4.071 | 0 | 4.071 | 0 | 0 | 4.071 | 784.231,0000 |
| 2. Thêm kỳ `12/2013` | `4EED60E8-74C2-4CEE-B50B-DDBEDBF95258` | `new_201312.csv` | 177 | 177 | 0 | 177 | 0 | 0 | 4.248 | 819.811,0000 |
| 3. Phát lại kỳ `12/2013` | `11F7FFFF-DC0B-4B6E-A25B-25DC9272564E` | `new_201312.csv` | 177 | 177 | 0 | 0 | 0 | 177 | 4.248 | 819.811,0000 |
| 4. Sửa số `+10` cùng grain | `E412F96D-88CF-42CD-9765-7C16440716D1` | `correction_plus10.csv` | 177 | 177 | 0 | 0 | 1 | 176 | 4.248 | 819.821,0000 |
| 5. Ca 8 dòng có 2 dòng lỗi | `FDC68A75-53CA-4EA4-BA3F-571D144DD1FA` | `invalid_8rows.csv` | 8 | 6 | 2 | 0 | 0 | 6 | 4.248 | 819.821,0000 *(6 dòng batch = 1.139)* |
| 6. Nạp chuẩn toàn bộ nguồn | `325E810B-B722-4BC3-A11D-8A6CAD5F8B50` | `Coffee.csv` | 4.248 | 4.248 | 0 | 4.248 | 0 | 0 | 4.248 | 819.811,0000 |
| 7. Phát lại toàn bộ nguồn | `7907ADCB-A79D-4797-A8B9-853EF6517E71` | `Coffee.csv` | 4.248 | 4.248 | 0 | 0 | 0 | 4.248 | 4.248 | 819.811,0000 |

*Bảng 4.4. Kết quả kiểm toán `audit.LoadBatch` và đối soát `dw.FactSalesPerformance` qua 7 lượt chạy SSIS trên SQL Server 2022*

**[Chèn Hình 4.3: Kết quả truy vấn bảng `audit.LoadBatch` và `audit.RejectedRow` trên SQL Server Management Studio (`results/TN03/chi_2026-11-15/TN03_ssms_audit.jpg`)]**
*Hình 4.3. Kết quả truy vấn nhật ký `audit.LoadBatch` và `audit.RejectedRow` trên SSMS*

**[Chèn Hình 4.4: Bảng tổng hợp kết quả kiểm toán các lượt chạy Batch trong TN03 (`results/TN03/chi_2026-11-15/TN03_audit.png`)]**
*Hình 4.4. Đối soát các bộ đếm `SourceCount`, `AcceptedCount`, `RejectedCount`, `InsertedCount`, `UpdatedCount` và `UnchangedCount`*

Đối với Lượt chạy 5 (`BatchID = FDC68A75-53CA-4EA4-BA3F-571D144DD1FA`, tệp `invalid_8rows.csv`), truy vấn bảng `audit.RejectedRow` cho thấy hai bản ghi lỗi đã bị cô lập chính xác kèm số dòng vật lý và chuỗi JSON nguyên gốc:

| Mã lô (`BatchID`) | Dòng nguồn (`SourceRow`) | Lý do từ chối (`Reason`) | Dữ liệu gốc được lưu vết (`RawJson`) |
| --- | ---: | --- | --- |
| `FDC68A75-53CA-4EA4-BA3F-571D144DD1FA` | 2 | `Sales: invalid numeric value` | `{"Area Code":"719","Date":"40909","Market":"Central","Product":"Amaretto",...,"Sales":"abc","Total Expenses":"36"}` |
| `FDC68A75-53CA-4EA4-BA3F-571D144DD1FA` | 3 | `ProductName: required` | `{"Area Code":"970","Date":"40909","Market":"Central","Product":"",...,"Sales":"190","Total Expenses":"39"}` |

*Bảng 4.5. Chi tiết hai bản ghi bị từ chối trong `audit.RejectedRow` ở kịch bản dữ liệu lỗi 8 dòng*

**[Chèn Hình 4.5: Minh chứng truy vết bản ghi bị từ chối trong `audit.RejectedRow` (`results/TN03/chi_2026-11-15/TN03_reject.png`)]**
*Hình 4.5. Kết quả cô lập dòng lỗi `Sales = 'abc'` và thiếu `ProductName` trong bảng `audit.RejectedRow`*

Khi chạy kịch bản `invalid_8rows.csv` vào một kho trống (như trong kịch bản kiểm thử độc lập trên SQLite và Ca 7 của bộ nghiệm thu SSDT `CoffeeETLTrangAcceptance`), bảng Fact thu được đúng `6` dòng hợp lệ với tổng `Sales = 1.139`, `BudgetSales = 1.180`, `Profit = 398`. Khi chạy kịch bản này dưới dạng một lô bổ sung trên kho đã có sẵn dữ liệu lịch sử (Lượt 5 ở Bảng 4.4), 2 dòng lỗi của lô mới bị chặn không cho ghi vào kho, trong khi bản ghi hợp lệ của cùng độ hạt đã nạp từ lô lịch sử trước đó vẫn được giữ an toàn trên `dw.FactSalesPerformance`.

Bên cạnh đó, để kiểm chứng khả năng bảo vệ nguyên tử khi xảy ra sự cố giữa chừng, nhóm đã thực hiện thêm phép thử tiêm lỗi (`Fault-injection Rollback Probe`): cố tình tạo sự lệch số dòng giữa khai báo `audit.LoadBatch` (`SourceCount = 2`) và số dòng thực nạp trong `stg.CoffeeRaw` (`1` dòng có sửa `Sales` và `State`) để kích hoạt lỗi kiểm soát bất biến `50006` ngay sau bước `UPDATE` trong `dw.usp_LoadCoffee`. Kết quả thực nghiệm xác nhận giao dịch bị hủy hoàn toàn (`@@TRANCOUNT = 0`, `XACT_STATE() = 0`), toàn bộ 11 bảng trong cơ sở dữ liệu (`47.315` dòng dữ liệu và nhật ký) giữ nguyên mã băm logic như trước khi gọi thủ tục, không để lại bất kỳ dữ liệu rác hay bản cập nhật dở dang nào.

| Chỉ tiêu kiểm tra sau nạp chuẩn (`04_checks.sql`) | Kết quả trên SQL Server 2022 (`CoffeeDW`) | Giá trị đối soát chuẩn từ nguồn | Chênh lệch |
| --- | ---: | ---: | ---: |
| Tổng số dòng `dw.FactSalesPerformance` | 4.248 | 4.248 | 0 |
| Số dòng `dw.DimDate` / `dw.DimLocation` / `dw.DimProduct` | 24 / 156 / 13 | 24 / 156 / 13 | 0 |
| Tổng `Sales` / `BudgetSales` / `Profit` | 819.811,0000 / 746.160,0000 / 259.543,0000 | 819.811 / 746.160 / 259.543 | 0 |
| Tổng `COGS` / `BudgetCOGS` | 358.672,0000 / 317.800,0000 | 358.672 / 317.800 | 0 |
| Tổng `Margin` / `BudgetMargin` | 443.479,0000 / 428.360,0000 | 443.479 / 428.360 | 0 |
| Tổng `Marketing` / `TotalExpenses` / `Inventory` | 132.533,0000 / 230.088,0000 / 3.182.971,0000 | 132.533 / 230.088 / 3.182.971 | 0 |
| Số bản ghi `NegativeProfit` / `NegativeInventory` | 528 / 88 | 528 / 88 | 0 |
| Số bản ghi `SalesMismatch` / `ProfitMismatch` | 2.088 / 2.105 | 2.088 / 2.105 | 0 |

*Bảng 4.6. Kết quả đối soát toàn bộ 11 chỉ tiêu số đo và cảnh báo chất lượng sau khi nạp chuẩn bằng `04_checks.sql`*

### 4.4.3. Nhận xét kết quả

Thực nghiệm TN03 chứng minh quy trình ETL đã đáp ứng đầy đủ các yêu cầu kỹ thuật của kho dữ liệu:
* Mọi lượt chạy đều thỏa mãn bất biến kế toán dòng `SourceCount = AcceptedCount + RejectedCount` và `AcceptedCount = InsertedCount + UpdatedCount + UnchangedCount` (`SourceDelta = 0`, `AcceptedDelta = 0`).
* Việc tải tăng dần (23 tháng + 1 tháng) cho kết quả cuối cùng (`4.248` dòng, `Sales = 819.811`) trùng khớp tuyệt đối với việc nạp một lần toàn bộ tệp nguồn.
* Việc phát lại cùng một tệp dữ liệu nhiều lần không làm tăng số bản ghi và không làm thay đổi tổng số đo; việc sửa số trên cùng khóa độ hạt chỉ cập nhật đúng bản ghi có thay đổi.
* Các dòng lỗi kiểu dữ liệu hoặc thiếu thuộc tính khóa bị chặn hoàn toàn khỏi bảng Fact và truy vết được chính xác tới từng dòng nguồn qua `audit.RejectedRow`.

---

## 4.5. Thực nghiệm TN04 – Kiểm chứng SCD Type 1, Type 2 và Type 3

### 4.5.1. Mục tiêu và phương pháp thực hiện

Thực nghiệm TN04 được thực hiện nhằm kiểm chứng cách kho dữ liệu xử lý sự thay đổi thuộc tính chiều theo cả ba phương pháp SCD Type 1, Type 2 và Type 3, đồng thời kiểm tra việc tra cứu khóa thay thế (`Surrogate Key Lookup`) cho các giao dịch phát sinh trước, đúng tại ngày biên và sau ngày hiệu lực.

Để không làm xáo trộn dữ liệu lịch sử của 13 sản phẩm và 156 mã vùng trong kho chính, thực nghiệm được thiết kế biệt lập trong script Python `learning/experiments/scd.py`, kịch bản T-SQL `sql/sqlserver/12_tn04_scd_demo.sql` và gói SSIS `ssis/CoffeeETL/SCD_TN04.dtsx` với hai thực thể thử nghiệm:
* **Thực thể sản phẩm `P01`:**
  * *SCD Type 1:* Khởi tạo sản phẩm `P01` với tên bị gõ sai chính tả `'Amareto'`, sau đó thực hiện cập nhật đính chính thành `'Amaretto'`.
  * *SCD Type 2:* Khởi tạo `P01` thuộc nhóm `ProductType = 'Coffee'` với khoảng hiệu lực `[2012-01-01, 9999-12-31)`, `IsCurrent = 1`. Tại mốc ngày biên `T = 2013-01-01`, sản phẩm được tái phân loại sang nhóm `'Specialty'`. Hệ thống thực hiện đóng phiên bản cũ và mở phiên bản mới, sau đó phát lại chính sự kiện đổi nhóm này lần thứ hai để kiểm tra tính lũy đẳng.
  * *SCD Type 3:* Khởi tạo `P01` ở nhóm `'Coffee'`, sau đó đổi lần 1 sang `'Specialty'` và đổi tiếp lần 2 sang `'Premium'`.
* **Thực thể địa bàn `A01`:** Kiểm chứng tương tự cho chiều địa lý với thao tác sửa lỗi chính tả thị trường `'Wset'` → `'West'` (Type 1), nâng hạng quy mô thị trường `'Minor'` → `'Major'` tại ngày biên `2012-07-01` (Type 2) và đổi tiếp sang `'Pilot'` (Type 3).

### 4.5.2. Kết quả thực nghiệm

Sau khi thực thi `sql/sqlserver/12_tn04_scd_demo.sql` và gói SSIS `SCD_TN04.dtsx` trên SQL Server 2022 (`Chi-Chie`), kết quả các phiên bản chiều và phép tra cứu theo ngày nghiệp vụ được ghi nhận như sau:

| Khóa thay thế (`ProductKey`) | Mã nghiệp vụ (`Code`) | Tên sản phẩm (`ProductName` – Type 1) | Nhóm sản phẩm (`ProductType` – Type 2) | Ngày bắt đầu (`ValidFrom`) | Ngày kết thúc (`ValidTo`) | Cờ hiện hành (`IsCurrent`) |
| ---: | --- | --- | --- | --- | --- | ---: |
| 1 | `P01` | Amaretto | Coffee | `2012-01-01` | `2013-01-01` | 0 |
| 2 | `P01` | Amaretto | Specialty | `2013-01-01` | `9999-12-31` | 1 |

*Bảng 4.7. Các phiên bản SCD Type 2 của sản phẩm `P01` sau khi cập nhật và phát lại sự kiện thay đổi*

**[Chèn Hình 4.6: Kết quả các dòng phiên bản SCD Type 1 và Type 2 trên SQL Server (`results/TN04/chi_2026-11-15/TN04_versions.png`)]**
*Hình 4.6. Kết quả bảng phiên bản SCD Type 2 của `P01` và `A01` sau khi đóng phiên bản cũ và mở phiên bản mới*

Khi áp dụng điều kiện kết nối nửa mở `d.ValidFrom <= f.OrderMonth AND f.OrderMonth < d.ValidTo` để gán khóa chiều cho các sự kiện bán hàng phát sinh ở các kỳ khác nhau, hệ thống trả về kết quả chính xác tại mọi mốc thời gian:

| Mã thực thể | Ngày giao dịch (`OrderMonth`) | Khóa tra cứu được (`Surrogate Key`) | Giá trị thuộc tính được gán | Giải thích hành vi tại mốc thời gian |
| --- | --- | ---: | --- | --- |
| `P01` | `2012-12-01` | 1 | `Coffee` | Trước ngày biên `2013-01-01`: giao dịch lịch sử năm 2012 giữ đúng nhóm cũ `Coffee` |
| `P01` | `2013-01-01` | 2 | `Specialty` | Đúng tại ngày biên `2013-01-01`: cận phải mở `< ValidTo` loại dòng 1, khớp duy nhất dòng 2 |
| `P01` | `2013-02-01` | 2 | `Specialty` | Sau ngày biên: giao dịch tiếp tục nhận phiên bản hiện hành `ProductKey = 2` |
| `A01` | `2012-06-01` | 1 | `Minor` | Trước ngày biên `2012-07-01`: giao dịch tháng 06/2012 giữ phân hạng cũ `Minor` |
| `A01` | `2012-07-01` | 2 | `Major` | Đúng tại ngày biên `2012-07-01`: giao dịch tháng 07/2012 nhận phân hạng mới `Major` |

*Bảng 4.8. Kết quả tra cứu khóa SCD Type 2 theo ngày giao dịch trước, đúng và sau mốc biên hiệu lực*

**[Chèn Hình 4.7: Kết quả tra cứu khóa SCD Type 2 tại các mốc trước, đúng và sau ngày biên (`results/TN04/chi_2026-11-15/TN04_lookup.png`)]**
*Hình 4.7. Minh chứng kết quả tra cứu khóa chiều SCD Type 2 theo điều kiện khoảng nửa mở `[ValidFrom, ValidTo)`*

Đối với **SCD Type 3**, sau hai lần thay đổi liên tiếp, trạng thái lưu trữ trên bảng chiều được ghi nhận ở Bảng 4.9:

| Mã thực thể (`Code`) | Chuỗi sự kiện thay đổi thực tế | Giá trị hiện tại (`CurrentValue`) | Giá trị liền trước (`PreviousValue`) | Giá trị lịch sử bị mất |
| --- | --- | --- | --- | --- |
| `P01` | `Coffee` → `Specialty` → `Premium` | `Premium` | `Specialty` | Mất giá trị gốc `Coffee` |
| `A01` | `Minor` → `Major` → `Pilot` | `Pilot` | `Major` | Mất giá trị gốc `Minor` |

*Bảng 4.9. Kết quả kiểm chứng giới hạn lưu trữ lịch sử của SCD Type 3 sau hai lần thay đổi*

**[Chèn Hình 4.8: Minh chứng giới hạn của SCD Type 3 và các kiểm tra ràng buộc SCD (`results/TN04/chi_2026-11-15/TN04_type3.png`)]**
*Hình 4.8. Kết quả kiểm tra tính lũy đẳng, không chồng khoảng của SCD Type 2 và giới hạn mất lịch sử của SCD Type 3*

### 4.5.3. Nhận xét kết quả

Thực nghiệm TN04 khẳng định:
* **SCD Type 1** sửa lỗi chính tả (`'Amareto'` → `'Amaretto'`, `'Wset'` → `'West'`) ngay trên các dòng hiện có mà không làm phát sinh khóa thay thế mới.
* **SCD Type 2** với quy ước khoảng nửa mở `[ValidFrom, ValidTo)` bảo đảm tính duy nhất của phiên bản tại đúng ngày biên chuyển giao (`OverlappingIntervals = 0`, `CurrentVersionCount = 1`) và hoàn toàn lũy đẳng khi phát lại sự kiện (`TotalVersionsAfterReplay = 2`).
* **SCD Type 3** chỉ lưu được trạng thái hiện tại và một trạng thái liền trước, làm mất giá trị ban đầu khi thực thể thay đổi từ lần thứ hai trở đi; do đó SCD Type 2 là giải pháp bắt buộc khi kho dữ liệu cần bảo toàn lịch sử phân tích xuyên thời gian.

---
---

# CHƯƠNG 5. PHÂN TÍCH ĐA CHIỀU VÀ KẾT QUẢ KINH DOANH

## 5.1. Xây dựng lớp Data Mart và hệ thống chỉ tiêu phân tích

### 5.1.1. Thiết kế các View phục vụ phân tích tại lớp Data Mart

Để cung cấp một giao diện dữ liệu thống nhất, an toàn và hiệu năng cao cho các công cụ khai thác phía sau (bao gồm khối OLAP SSAS Multidimensional, ứng dụng Dashboard phân tích và mô-đun dự báo doanh số ở Chương 6–7), hệ thống CoffeeDW xây dựng lớp **Data Mart** (`sql/sqlserver/02_marts.sql`) gồm ba View chuẩn hóa:

| Tên View trong Data Mart | Độ hạt (Grain) của dữ liệu trả về | Số dòng trên bộ nguồn chuẩn | Mục đích sử dụng chính |
| --- | --- | ---: | --- |
| `mart.vw_Detail` | `MonthStart × AreaCode × ProductName` | 4.248 | Kết nối sẵn `FactSalesPerformance` với `DimDate`, `DimLocation`, `DimProduct`; phục vụ truy sâu chi tiết theo bang, mã vùng, sản phẩm và xuất CSV |
| `mart.vw_MarketPeriod` | `MonthStart × Market` | 96 (`24 tháng × 4 thị trường`) | Tổng hợp sẵn các chỉ tiêu theo tháng và thị trường; phục vụ thẻ KPI tổng quan, biểu đồ xu hướng và làm chuỗi đầu vào chuẩn cho bài toán dự báo |
| `mart.vw_MarketProductPeriod` | `MonthStart × Market × ProductName` | 1.008 | Tổng hợp doanh số, ngân sách, lợi nhuận và chênh lệch `Gap` theo từng thị trường và sản phẩm trong tháng; phục vụ phân tích đóng góp sản phẩm |

*Bảng 5.1. Danh mục các View công bố tại lớp Data Mart của hệ thống CoffeeDW*

### 5.1.2. Quy tắc tổng hợp KPI, tỷ lệ hoàn thành và tồn kho bán cộng

Một sai lầm phổ biến trong các hệ thống báo cáo là tính trung bình cộng của các tỷ lệ phần trăm ở dòng chi tiết hoặc cộng dồn chỉ tiêu tồn kho qua nhiều kỳ. Để đảm bảo tính chính xác về mặt toán học và nghiệp vụ kế toán, lớp Data Mart và khối OLAP của CoffeeDW áp dụng thống nhất các quy tắc tổng hợp sau:

1. **Các chỉ tiêu cộng được hoàn toàn (Fully Additive Measures):** Gồm 10 chỉ tiêu dòng chảy trong kỳ là `Sales`, `BudgetSales`, `Profit`, `BudgetProfit`, `COGS`, `BudgetCOGS`, `Margin`, `BudgetMargin`, `Marketing` và `TotalExpenses`. Các chỉ tiêu này được phép cộng (`SUM`) tự do theo mọi chiều Thời gian, Địa lý và Sản phẩm.
2. **Chênh lệch thực hiện so với ngân sách (`Gap`):**
   $$\text{Gap} = \sum \text{Sales} - \sum \text{BudgetSales}$$
   Khi xếp hạng để tìm khu vực hoặc sản phẩm hụt ngân sách nặng nhất, hệ thống bắt buộc sắp xếp theo giá trị **`Gap` có dấu tăng dần** (giá trị âm lớn nhất đứng đầu, ví dụ `-268` đứng trước `-105`), tuyệt đối không sắp xếp theo giá trị tuyệt đối `|Gap|`.
3. **Tỷ lệ hoàn thành ngân sách (`BudgetAchievement`) và Biên lợi nhuận (`ProfitMargin`) — Chỉ tiêu không cộng được (Non-Additive):**
   $$\text{BudgetAchievement} = \frac{\sum \text{Sales}}{\text{NULLIF}(\sum \text{BudgetSales}, 0)}, \quad \text{ProfitMargin} = \frac{\sum \text{Profit}}{\text{NULLIF}(\sum \text{Sales}, 0)}$$
   Các tỷ lệ này luôn được tính bằng **tổng tử số chia cho tổng mẫu số** trên cùng tập bản ghi sau khi lọc. Nếu tổng mẫu số bằng `0` hoặc `NULL`, biểu thức trả về `NULL` (thiếu dữ liệu) chứ không ép về `0%`.
4. **Tồn kho (`Inventory`) — Chỉ tiêu bán cộng (Semi-Additive):**
   `Inventory` là chỉ tiêu phản ánh trạng thái tồn kho tại một thời điểm (snapshot cuối kỳ). Do đó, `Inventory` chỉ được phép cộng (`SUM`) theo chiều Địa lý (`Location`) và Sản phẩm (`Product`) trong **cùng một kỳ tháng**, nhưng tuyệt đối không được cộng dồn xuyên qua nhiều tháng. Khi người dùng chọn một khoảng thời gian nhiều tháng (hoặc xem cấp Quý/Năm trên Cube), hệ thống lấy tổng tồn kho tại **kỳ tháng cuối cùng** có trong khoảng thời gian đang xét (`Closing Period` / `LastChild`).

### 5.1.3. Đối soát liên quy trình Drill-Across và phòng tránh lỗi nhân bản Fan-out

Khi doanh nghiệp cần đối chiếu hai quy trình nghiệp vụ khác nhau (ví dụ: doanh số thực tế chi tiết từ bảng sự kiện `FactSalesPerformance` ở độ hạt `Tháng × Mã vùng × Sản phẩm` với kế hoạch ngân sách hoặc dự báo doanh số ở độ hạt `Tháng × Thị trường` trong bảng `ml.ForecastSales`), việc thực hiện phép nối trực tiếp (`JOIN`) giữa bảng chi tiết và bảng tổng hợp trước khi gom nhóm (`SUM`) sẽ gây ra lỗi **nhân bản số liệu (Fan-out Trap)**.

Cụ thể, vì một thị trường trong một tháng có nhiều dòng chi tiết `(AreaCode × ProductName)` (như thị trường `West` tháng `01/2012` có `56` dòng chi tiết), nếu nối trực tiếp bảng ngân sách cấp thị trường vào bảng chi tiết rồi mới `SUM(BudgetSales)`, con số ngân sách của thị trường đó sẽ bị cộng lặp lại `56` lần.

Để loại bỏ hoàn toàn lỗi Fan-out, hệ thống áp dụng mẫu truy vấn **Drill-Across chuẩn** (`sql/sqlserver/10_drill_across.sql` và `11_tn05_budget_demo.sql`):
* **Bước 1 (Tiền tổng hợp độc lập):** Tổng hợp riêng từng bảng sự kiện về đúng độ hạt chung là `MonthStart × Market` thông qua các biểu thức bảng chung (CTE `ActualByMarketMonth` và `BudgetByMarketMonth` / `ForecastByMarketMonth`).
* **Bước 2 (Kết nối toàn phần `FULL OUTER JOIN`):** Nối hai tập kết quả đã có cùng độ hạt `MonthStart × Market` bằng `FULL OUTER JOIN`, sử dụng `COALESCE(a.MonthStart, b.MonthStart)` và `COALESCE(a.Market, b.Market)` cùng hai cờ trạng thái `MissingActual` và `MissingBudget` để bảo toàn cả những kỳ chỉ có thực tế (thiếu ngân sách) lẫn những kỳ tương lai chỉ có kế hoạch/dự báo (chưa phát sinh doanh số thực tế).

---

## 5.2. Thiết kế khối đa chiều Data Cube trên SSAS Multidimensional

### 5.2.1. Cấu trúc Data Source View và các chiều phân cấp

Dự án phân tích đa chiều native được xây dựng bằng Microsoft SQL Server Analysis Services (SSAS Multidimensional) tại thư mục `ssas/CoffeeCube/CoffeeCube.dwproj` (cùng bản triển khai tích hợp `ssas/CoffeeCubeTrang/CoffeeCube.dwproj`).

Trên lớp `CoffeeDW.dsv` (Data Source View), lược đồ hình sao của kho dữ liệu `CoffeeDW` được ánh xạ gồm bảng sự kiện `dw.FactSalesPerformance` ở trung tâm nối với ba bảng chiều `dw.DimDate`, `dw.DimLocation` và `dw.DimProduct` qua các khóa chính – khóa ngoại tương ứng.

**[Chèn Hình 5.1: Lược đồ Data Source View `CoffeeDW.dsv` trong Visual Studio SSDT (`results/TN06/chi_2026-11-15/TN06_dsv_vs.jpg`)]**
*Hình 5.1. Lược đồ hình sao trong `CoffeeDW.dsv` trên Visual Studio SSDT với 0 lỗi và 0 cảnh báo*

Ba chiều phân tích (`Dimensions`) được thiết kế với hệ thống phân cấp (`User Hierarchies`) và quan hệ thuộc tính (`Attribute Relationships`) chặt chẽ:

| Chiều (`Dimension`) | Tên cây phân cấp (`Hierarchy`) | Các cấp độ từ tổng quát đến chi tiết (`Levels`) | Thiết kế khóa thuộc tính (`KeyColumns`) và quan hệ thuộc tính (`Attribute Relationships`) |
| --- | --- | --- | --- |
| `Dim Date` | `Calendar` | `Year` → `Quarter` → `Month` | `Date Key` (`YYYYMMDD`, hiển thị `MonthStart`) → `Month` (khóa `DateKey`) → `Quarter` (khóa ghép `Year, Quarter`) → `Year` (`RelationshipType = Rigid`). Khóa ghép giúp tách biệt quý/tháng của năm 2012 với năm 2013 |
| `Dim Location` | `Geography` | `Market` → `State` → `Area Code` | `Location Key` → `Area Code` → `State` → `Market`; thuộc tính độc lập `Market Size` nối từ `Location Key`. Phản ánh đúng phụ thuộc hàm `AreaCode → State → Market` |
| `Dim Product` | `Product Hierarchy` | `Product Line` → `Product Type` → `Product Name` | `Product Key` → `Product Name` → `Product Type` → `Product Line`; thuộc tính `Type` (`Regular` / `Decaf`) là thuộc tính phân tích độc lập gắn với `Product Name` |

*Bảng 5.2. Cấu trúc phân cấp và quan hệ thuộc tính của ba chiều trong khối `Coffee Performance`*

### 5.2.2. Thiết kế Measure Group, Dimension Usage và MDX Script

Khối đa chiều `Coffee Performance.cube` được cấu hình với một Measure Group trung tâm là `Fact Sales Performance`:

**[Chèn Hình 5.2: Cấu trúc Cube Structure của `Coffee Performance.cube` trong Visual Studio SSDT (`results/TN06/chi_2026-11-15/TN06_cube_structure_vs.jpg`)]**
*Hình 5.2. Giao diện thiết kế Cube Structure với các Measures và Dimensions trong Visual Studio SSDT*

**[Chèn Hình 5.3: Ma trận Dimension Usage thiết lập quan hệ Regular giữa ba chiều và Measure Group (`results/TN06/chi_2026-11-15/TN06_usage.png`)]**
*Hình 5.3. Cấu hình Dimension Usage với liên kết Regular tại các khóa hạt lá `Date Key`, `Location Key` và `Product Key`*

* **Liên kết Dimension Usage:** Cả ba chiều `Dim Date`, `Dim Location` và `Dim Product` đều liên kết với Measure Group `Fact Sales Performance` theo kiểu quan hệ **Regular** thông qua đúng khóa hạt lá (`DateKey`, `LocationKey`, `ProductKey`).
* **Cấu hình hàm tổng hợp và MDX Script (`Calculations`):**
  * 10 chỉ tiêu cộng được (`Sales`, `Budget Sales`, `Profit`, `Budget Profit`, `COGS`, `Budget COGS`, `Margin`, `Budget Margin`, `Marketing`, `Total Expenses`) sử dụng `AggregateFunction = Sum`.
  * Chỉ tiêu bán cộng `Inventory` được định nghĩa quy tắc lấy kỳ cuối thông qua lệnh `SCOPE` trong `MdxScript` (hoặc hàm bán cộng `LastChild` trên chiều thời gian): khi truy vấn ở cấp `Year`, `Quarter` hoặc `[All]`, giá trị `[Measures].[Inventory]` tự động lấy theo thành viên tháng cuối cùng hiện hữu trong ngữ cảnh lọc (`TAIL(EXISTING [Dim Date].[Date Key].[Date Key].Members, 1).Item(0)`).
  * Ba chỉ tiêu tính toán (`Calculated Measures`) được định nghĩa trực tiếp trong `MdxScript` của Cube:
    * `[Measures].[Gap] = [Measures].[Sales] - [Measures].[Budget Sales]`
    * `[Measures].[Budget Achievement] = IIF(IsEmpty([Measures].[Budget Sales]) OR [Measures].[Budget Sales] = 0, NULL, [Measures].[Sales] / [Measures].[Budget Sales])`
    * `[Measures].[Profit Margin] = IIF(IsEmpty([Measures].[Sales]) OR [Measures].[Sales] = 0, NULL, [Measures].[Profit] / [Measures].[Sales])`

### 5.2.3. Mô hình khối lập phương 3D Data Cube và các phép toán OLAP

Khi dữ liệu từ mô hình Star Schema được xử lý (`ProcessFull`) vào khối `Coffee Performance`, không gian phân tích của CoffeeDW có thể được hình dung như một **khối lập phương 3 chiều (3D Data Cube)** với ba trục tọa độ vuông góc: trục Thời gian (`Dim Date`: 24 tháng), trục Địa lý (`Dim Location`: 4 thị trường → 20 bang → 156 mã vùng) và trục Sản phẩm (`Dim Product`: 2 dòng → 4 nhóm → 13 sản phẩm).

**[Chèn Hình 5.4: Mô hình trực quan khối lập phương 3D Data Cube của hệ thống CoffeeDW (`results/TN06/chi_2026-11-15/TN06_datacube_3d.png`)]**
*Hình 5.4. Biểu diễn trực quan khối lập phương 3D Data Cube và các lát cắt doanh số theo Thời gian × Thị trường × Nhóm sản phẩm*

Trên không gian khối lập phương này, người phân tích thực hiện 5 phép toán OLAP kinh điển để trả lời các câu hỏi quản trị:
1. **Slice (Cắt một lát phẳng):** Cố định một giá trị trên một chiều (ví dụ: cố định chiều Thời gian tại tháng `01/2012` hoặc tháng `11/2013`) để quan sát bảng 2 chiều còn lại (`Market × Product` hoặc `Market × Measures`).
2. **Drill-down (Truy sâu xuống cấp chi tiết):** Đi từ cấp tổng hợp cao xuống cấp chi tiết hơn theo cây phân cấp (ví dụ: từ `Market = Central` mở xuống 6 `State` trực thuộc, hoặc từ `Market = South` mở xuống 7 `Product Name`).
3. **Roll-up (Cuộn tổng hợp lên cấp cao):** Cộng gộp các thành phần con lên cấp cha (ví dụ: cộng 6 bang của `Central` về tổng `Central`, hoặc gộp các tháng lên Quý và Năm) đồng thời tính lại các tỷ lệ phần trăm từ tổng tử và tổng mẫu.
4. **Dice (Cắt khối con đa điều kiện):** Lọc đồng thời trên nhiều chiều để trích xuất một khối con (sub-cube), chẳng hạn cố định `Month = 01/2012`, chọn tập thị trường `{Central, East}` và nhóm sản phẩm `Product Type = Coffee`.
5. **Pivot (Xoay trục phân tích):** Hoán đổi vị trí giữa các chiều trên trục hàng (`ROWS`) và trục cột (`COLUMNS`) của báo cáo (ví dụ: đưa `Product Name` lên hàng và `Market` lên cột) mà vẫn giữ nguyên tổng đại số của lát cắt.

---

## 5.3. Phân tích kết quả kinh doanh chuỗi cà phê từ kho dữ liệu

### 5.3.1. Phân tích tổng quan hiệu quả kinh doanh theo thị trường

Tổng hợp toàn bộ 24 tháng hoạt động (`01/2012 – 12/2013`, gồm `4.248` bản ghi sự kiện) từ lớp Data Mart (`mart.vw_MarketPeriod`) và khối OLAP `Coffee Performance` cho kết quả bức tranh kinh doanh tổng thể của chuỗi theo 4 thị trường như sau:

| Thị trường (`Market`) | Số dòng Fact | Doanh số thực tế (`Sales`) | Ngân sách (`BudgetSales`) | Chênh lệch (`Gap`) | Lợi nhuận (`Profit`) | Tỷ lệ đạt ngân sách (`BudgetAchievement`) | Biên lợi nhuận (`ProfitMargin`) | Tồn kho kỳ cuối `12/2013` (`Inventory`) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Central** | 1.344 | 265.045 | 250.360 | +14.685 | 93.852 | 105,87% | 35,41% | 45.252 |
| **East** | 888 | 178.576 | 157.900 | +20.676 | 59.217 | 113,09% | 33,16% | 31.529 |
| **South** | 672 | 103.926 | 98.200 | +5.726 | 32.478 | 105,83% | 31,25% | 11.444 |
| **West** | 1.344 | 272.264 | 239.700 | +32.564 | 73.996 | 113,59% | 27,18% | 58.933 |
| **Toàn chuỗi** | **4.248** | **819.811** | **746.160** | **+73.651** | **259.543** | **109,87%** | **31,66%** | **147.158** |

*Bảng 5.3. Tổng hợp kết quả kinh doanh toàn chuỗi theo thị trường giai đoạn 2012–2013*

Từ Bảng 5.3 có thể rút ra các nhận định quản trị quan trọng:
* **Về quy mô doanh số và hoàn thành kế hoạch:** Toàn chuỗi đạt doanh số `819.811`, vượt ngân sách `+73.651` (tương ứng tỷ lệ hoàn thành `109,87%`). Thị trường **West** dẫn đầu về doanh số (`272.264`, chiếm `33,21%` toàn chuỗi) và có mức vượt ngân sách cao nhất (`+32.564`, đạt `113,59%`).
* **Về hiệu quả sinh lời:** Mặc dù đứng thứ hai về doanh số (`265.045`), thị trường **Central** lại dẫn đầu toàn chuỗi về lợi nhuận tuyệt đối (`93.852`) với biên lợi nhuận trên doanh thu đạt tới `35,41%`, cao hơn đáng kể so với `West` (`27,18%`). Ngược lại, `West` có quy mô doanh thu và tồn kho cuối kỳ lớn nhất (`58.933`) nhưng biên lợi nhuận thấp nhất, cho thấy chi phí giá vốn và chi phí vận hành/tiếp thị tại `West` đang chiếm tỷ trọng lớn.
* **Về rủi ro tiềm ẩn dưới mức tổng hợp:** Khi nhìn ở cấp tổng hợp 24 tháng, cả 4 thị trường đều có `Gap > 0`. Tuy nhiên, khi phân rã theo từng tháng trên `mart.vw_MarketPeriod`, hệ thống phát hiện những kỳ bị hụt ngân sách cục bộ, điển hình là thị trường **South kỳ tháng 08/2013** (`Sales = 4.601`, `BudgetSales = 4.610`, `Gap = -9`).

### 5.3.2. Phân tích lát cắt theo bang và nhóm sản phẩm

Khi thực hiện lát cắt tại kỳ khởi đầu **`01/2012` (`DateKey = 20120101`)** và truy sâu từ cấp `Market` xuống cấp `State` cho hai thị trường lớn nhất là `Central` và `West`, kết quả phân bổ theo từng bang như sau:

| Thị trường (`Market`) | Bang (`State`) | Doanh số (`Sales`) | Ngân sách (`BudgetSales`) | Lợi nhuận (`Profit`) | Chênh lệch (`Gap`) | Tỷ lệ đạt ngân sách (`BudgetAchievement`) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| **Central** | Colorado | 1.958 | 1.870 | 585 | +88 | 104,71% |
| **Central** | Illinois | 2.538 | 2.580 | 912 | −42 | 98,37% |
| **Central** | Iowa | 2.029 | 1.810 | 653 | +219 | 112,10% |
| **Central** | Missouri | 1.009 | 960 | 125 | +49 | 105,10% |
| **Central** | Ohio | 1.471 | 1.470 | 384 | +1 | 100,07% |
| **Central** | Wisconsin | 1.341 | 1.280 | 297 | +61 | 104,77% |
| **Tổng Roll-up Central** | **6 bang** | **10.346** | **9.970** | **2.956** | **+376** | **103,77%** |
| **West** | California | 3.602 | 3.450 | 1.034 | +152 | 104,41% |
| **West** | Nevada | 2.117 | 1.680 | 236 | +437 | 126,01% |
| **West** | Oregon | 1.741 | 1.590 | 444 | +151 | 109,50% |
| **West** | Utah | 1.388 | 1.320 | 237 | +68 | 105,15% |
| **West** | Washington | 1.605 | 1.420 | 405 | +185 | 113,03% |
| **Tổng Roll-up West** | **5 bang** | **10.453** | **9.460** | **2.356** | **+993** | **110,50%** |

*Bảng 5.4. Kết quả Drill-down từ `Market` xuống `State` và Roll-up ngược lại tại kỳ tháng `01/2012`*

Bảng 5.4 cho thấy phép truy sâu giúp phát hiện sự phân hóa ngay trong một thị trường đang vượt kế hoạch: tại `Central` tháng `01/2012` (`Gap = +376`), bang `Illinois` có doanh số lớn nhất (`2.538`) nhưng thực chất lại đang hụt ngân sách (`Gap = -42`, chỉ đạt `98,37%`), trong khi mức vượt kế hoạch của toàn vùng được kéo lên chủ yếu bởi bang `Iowa` (`Gap = +219`, đạt `112,10%`).

### 5.3.3. Truy sâu phát hiện điểm hụt ngân sách tại thị trường South kỳ 08/2013

Để làm rõ nguyên nhân thị trường **South** bị hụt ngân sách tại kỳ **`08/2013`** (`Sales = 4.601`, `BudgetSales = 4.610`, `Gap = -9`), nhóm thực hiện truy sâu xuống cấp sản phẩm (`mart.vw_MarketProductPeriod` / MDX Query 7) và sắp xếp theo `Gap` có dấu tăng dần:

| Thứ hạng hụt | Sản phẩm (`ProductName`) | Nhóm (`ProductType`) | Doanh số (`Sales`) | Ngân sách (`BudgetSales`) | Chênh lệch (`Gap`) | Lợi nhuận (`Profit`) | Tỷ lệ đạt (`BudgetAchievement`) | Đánh giá đóng góp |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | **Colombian** | Coffee | 1.102 | 1.370 | **−268** | 542 | 80,44% | Hụt ngân sách nghiêm trọng nhất cần ưu tiên xử lý |
| 2 | **Decaf Irish Cream** | Coffee | 465 | 570 | **−105** | 105 | 81,58% | Hụt ngân sách lớn thứ hai (tổng 2 món hụt `−373`) |
| 3 | Chamomile | Herbal Tea | 482 | 460 | +22 | 164 | 104,78% | Vượt nhẹ ngân sách |
| 4 | Lemon | Herbal Tea | 646 | 620 | +26 | 133 | 104,19% | Vượt nhẹ ngân sách |
| 5 | Caffe Latte | Espresso | 573 | 480 | +93 | 161 | 119,38% | Tăng trưởng tốt, bù đắp thiếu hụt |
| 6 | Decaf Espresso | Espresso | 719 | 610 | +109 | 341 | 117,87% | Tăng trưởng tốt, bù đắp thiếu hụt |
| 7 | Caffe Mocha | Espresso | 614 | 500 | +114 | 258 | 122,80% | Vượt ngân sách cao nhất trong kỳ |
| **—** | **Tổng South 08/2013** | **7 sản phẩm** | **4.601** | **4.610** | **−9** | **1.704** | **99,80%** | **5 món vượt (`+364`) bù gần hết 2 món hụt (`−373`)** |

*Bảng 5.5. Phân tích đóng góp chênh lệch ngân sách theo sản phẩm tại thị trường `South` kỳ `08/2013`*

Kết quả ở Bảng 5.5 minh chứng rõ giá trị của kho dữ liệu đa chiều: nếu nhà quản lý chỉ nhìn con số tổng `Gap = -9` ở cấp thị trường `South`, họ có thể đánh giá sai rằng mọi sản phẩm đều bám sát kế hoạch (`99,80%`). Tuy nhiên, khi drill-down xuống cấp sản phẩm, hai mặt hàng dòng `Coffee` là **Colombian** (`Gap = -268`) và **Decaf Irish Cream** (`Gap = -105`) thực tế bị hụt tới **`-373`** đơn vị doanh số, nhưng đã bị che lấp bởi mức vượt kế hoạch `+364` của 5 sản phẩm dòng `Espresso` và `Herbal Tea`.

---

## 5.4. Thực nghiệm TN05 – Kiểm chứng Data Mart và Drill-Across không gây Fan-out

### 5.4.1. Mục tiêu và phương pháp thực hiện

Thực nghiệm TN05 được thực hiện nhằm đạt ba mục tiêu:
1. Kiểm chứng độ chính xác từng ô (cell-by-cell) của ba View tại tầng Data Mart (`mart.vw_Detail`, `mart.vw_MarketPeriod`, `mart.vw_MarketProductPeriod`) so với dữ liệu nguồn `Coffee.csv`.
2. Định lượng sai số phóng đại ngân sách khi cố tình nối trực tiếp bảng tổng hợp cấp `MonthStart × Market` vào bảng chi tiết trước khi `SUM` (lỗi Fan-out).
3. Kiểm chứng mẫu truy vấn **Drill-Across** sử dụng tiền tổng hợp độc lập kết hợp `FULL OUTER JOIN` trên kịch bản có nhóm thiếu ngân sách và nhóm tương lai chỉ có kế hoạch (`learning/experiments/mart_olap.py`, `sql/sqlserver/10_drill_across.sql` và `sql/sqlserver/11_tn05_budget_demo.sql`).

Trong kịch bản thử nghiệm nhóm thiếu (`11_tn05_budget_demo.sql`), nhóm khởi tạo bảng `#Actual` (`96` nhóm `MonthStart × Market` từ nguồn) và bảng `#Budget` (`96` nhóm), sau đó:
* Xóa dòng ngân sách của thị trường `West` kỳ `2012-01-01` khỏi `#Budget` (mô phỏng trường hợp có doanh số thực tế nhưng thiếu kế hoạch ngân sách).
* Chèn thêm một dòng kế hoạch tương lai cho thị trường `West` kỳ `2014-01-01` với `BudgetSales = 1.000` vào `#Budget` (mô phỏng trường hợp kỳ kế hoạch tương lai chưa có doanh số thực tế).

### 5.4.2. Kết quả thực nghiệm

Thứ nhất, phép đối soát từng ô trên toàn bộ `96` nhóm của `mart.vw_MarketPeriod`, `1.008` nhóm của `mart.vw_MarketProductPeriod` và `4.248` dòng của `mart.vw_Detail` giữa SQL Server 2022 (`CoffeeDW`), SQLite và kết quả tính trực tiếp từ `Coffee.csv` đều cho độ lệch tuyệt đối lớn nhất (`max_abs_diff`) bằng **`0,0000`** trên mọi cột số đo và KPI.

Thứ hai, kết quả so sánh giữa phép nối sai (Anti-pattern Fan-out) và phép nối đúng (Drill-Across sau tiền tổng hợp) trên SQL Server 2022 được tổng hợp trong Bảng 5.6:

| Phương pháp kết nối Actual và Budget | Phạm vi kiểm tra | Số dòng chi tiết bị nhân bản | Tổng `Sales` thu được | Tổng `BudgetSales` thu được | Hệ số phóng đại `BudgetSales` | Đánh giá tính đúng đắn |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| **Nối sai (Fan-out):** Nối trực tiếp `#Budget` (`MonthStart × Market`) vào `mart.vw_Detail` rồi mới `SUM` | Riêng `West` kỳ `01/2012` | 56 dòng | 10.453,0000 | **529.760,0000** | Gấp **56,00 lần** số đúng (`9.460`) | **Sai** – Ngân sách thị trường bị cộng lặp theo số dòng chi tiết |
| **Nối sai (Fan-out):** Nối trực tiếp `#Budget` vào `mart.vw_Detail` trên toàn bộ 24 tháng | Toàn chuỗi 24 tháng | 4.248 dòng | 819.811,0000 | **36.035.260,0000** | Gấp **48,29 lần** số đúng (`746.160`) | **Sai** – Báo cáo ngân sách bị thổi phồng nghiêm trọng |
| **Nối đúng (Drill-Across):** Tiền tổng hợp độc lập từng bảng về `MonthStart × Market` rồi `FULL OUTER JOIN` | Riêng `West` kỳ `01/2012` | 1 nhóm | 10.453,0000 | **9.460,0000** | **1,00 lần** (Chính xác) | **Đúng** – Bảo toàn tuyệt đối cả `Sales` và `BudgetSales` |
| **Nối đúng (Drill-Across):** Tiền tổng hợp độc lập trên toàn bộ 24 tháng | Toàn chuỗi 24 tháng | 96 nhóm | 819.811,0000 | **746.160,0000** | **1,00 lần** (Chính xác) | **Đúng** – Khớp 100% với tổng nguồn |

*Bảng 5.6. Đối chiếu định lượng giữa phép nối gây lỗi Fan-out và phép nối Drill-Across chuẩn trong TN05*

Thứ ba, khi chạy truy vấn Drill-Across có `FULL OUTER JOIN` trên tập dữ liệu thử nghiệm có kỳ thiếu ngân sách và kỳ tương lai chỉ có kế hoạch, hệ thống trả về đúng `97` nhóm (`95` nhóm khớp đủ hai phía, `1` nhóm thiếu Budget và `1` nhóm thiếu Actual):

| Kỳ tháng (`MonthStart`) | Thị trường (`Market`) | Doanh số thực tế (`Sales`) | Ngân sách (`BudgetSales`) | Chênh lệch (`Gap`) | Cờ `MissingActual` | Cờ `MissingBudget` | Ý nghĩa đối soát |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `2012-01-01` | `West` | 10.453,0000 | `NULL` | `NULL` | 0 | 1 | Giữ nguyên doanh số thực tế `10.453`; không biến ngân sách thiếu thành `0` |
| `2014-01-01` | `West` | `NULL` | 1.000,0000 | `NULL` | 1 | 0 | Giữ nguyên kế hoạch kỳ tương lai `1.000` dù chưa có doanh số thực tế |

*Bảng 5.7. Kết quả bảo toàn nhóm thiếu bằng `FULL OUTER JOIN` và cờ trạng thái trong TN05*

**[Chèn Hình 5.5: Kết quả thực nghiệm TN05 đối soát Drill-Across, cờ thiếu và minh họa lỗi Fan-out trên SQL Server (`results/TN05/chi_2026-11-15/TN05_join.png`)]**
*Hình 5.5. Kết quả thực thi kịch bản TN05 kiểm chứng `FULL OUTER JOIN` và lỗi nhân bản ngân sách Fan-out*

### 5.4.3. Nhận xét kết quả

Thực nghiệm TN05 chứng minh rằng khi làm việc với các bảng sự kiện hoặc bảng kế hoạch/dự báo có độ hạt khác nhau, việc tiền tổng hợp độc lập từng nguồn về cùng độ hạt chung trước khi thực hiện `FULL OUTER JOIN` là điều kiện bắt buộc để tránh sai số nhân bản gấp hàng chục lần, đồng thời bảo toàn đầy đủ các kỳ dữ liệu bất đối xứng ở biên thời gian.

---

## 5.5. Thực nghiệm TN06 – Triển khai Data Cube, truy vấn MDX và đối soát OLAP đa chiều

### 5.5.1. Mục tiêu và phương pháp thực hiện

Thực nghiệm TN06 được thực hiện nhằm triển khai khối đa chiều `Coffee Performance` từ dự án `ssas/CoffeeCube/CoffeeCube.dwproj`, thực thi bộ 9 truy vấn MDX trong `ssas/queries.mdx` (bao phủ các phép toán Slice, Drill-down, Roll-up, Dice, Pivot, xếp hạng `Gap` có dấu tại `South 08/2013` và kiểm tra tồn kho bán cộng `Inventory`) và đối chiếu chéo từng con số với tập truy vấn SQL chuẩn `sql/sqlserver/13_tn06_olap_checks.sql` cũng như tệp nguồn `Coffee.csv`.

Bên cạnh việc kiểm chứng trên máy Chi (`Chi-Chie`) và bản tham chiếu Python, trong đợt tích hợp nhánh `dev` ngày `20/11/2026`, khối SSAS native (`CoffeeCube_Trang_20261120` trên instance `localhost\TRANGTRETRAU`, SSAS Server v17.0.25.218) cũng đã được `ProcessFull` trực tiếp trên chính cơ sở dữ liệu vừa nạp qua SSIS (`CoffeeDW_Trang_SSIS_TN03_20261120`) và vượt qua toàn bộ `17/17` ca đối soát MDX – SQL tự động cùng `6/6` ô kiểm tra xoay trục Pivot qua giao thức ADOMD.

**[Chèn Hình 5.6: Bộ truy vấn MDX chuẩn trong `ssas/queries.mdx` phục vụ kiểm thử khối `Coffee Performance` (`results/TN06/chi_2026-11-15/TN06_mdx_query.png`)]**
*Hình 5.6. Nội dung các truy vấn MDX thực hiện Slice, Drill-down, Roll-up, Dice, Pivot và xử lý tồn kho bán cộng*

### 5.5.2. Kết quả thực nghiệm

Thứ nhất, kết quả phép **cắt khối con (Dice)** và **xoay trục (Pivot)** tại kỳ `01/2012` (`DateKey = 20120101`), lọc hai thị trường `{Central, East}` và nhóm sản phẩm `Product Type = Coffee` (MDX Query 5 & Query 6 / SQL Check 4 & Check 5):

* **Trước khi Pivot (nhóm theo `Market`):** Thị trường `Central` đạt `Sales = 2.663` (`BudgetSales = 2.650`, `Profit = 860`, `Gap = +13`); thị trường `East` đạt `Sales = 2.105` (`BudgetSales = 1.990`, `Profit = 788`, `Gap = +115`). Tổng doanh số của khối con là **`4.768`** (`BudgetSales = 4.640`, `Profit = 1.648`, `Gap = +128`).
* **Sau khi Pivot (đưa `Product Name` lên trục hàng và `Market` lên trục cột):**

| Sản phẩm thuộc nhóm `Coffee` (`ProductName`) | Thị trường `Central` (`Sales`) | Thị trường `East` (`Sales`) | Tổng theo sản phẩm (`Row Total`) |
| --- | ---: | ---: | ---: |
| Amaretto | 524 | 93 | 617 |
| Colombian | 1.117 | 1.812 | 2.929 |
| Decaf Irish Cream | 1.022 | 200 | 1.222 |
| **Tổng theo thị trường (`Column Total`)** | **2.663** | **2.105** | **4.768** |

*Bảng 5.8. Ma trận kết quả sau phép xoay trục Pivot cho khối con `Coffee` tại `Central` và `East` kỳ `01/2012`*

Phép xoay trục giữ nguyên tổng từng cột (`2.663` và `2.105`), tổng từng hàng (`617 + 2.929 + 1.222`) và tổng toàn lát cắt bằng **`4.768`**, khớp `100%` giữa truy vấn MDX và truy vấn SQL `PIVOT`.

**[Chèn Hình 5.7: Giao diện Cube Browser thực hiện các phép lọc Slice, Drill-down và Dice trên khối `Coffee Performance` (`results/TN06/chi_2026-11-15/TN06_browser.png`)]**
*Hình 5.7. Kết quả duyệt khối đa chiều trên SSAS Cube Browser với các bộ lọc thời gian, thị trường và nhóm sản phẩm*

**[Chèn Hình 5.8: Kết quả chạy bộ truy vấn SQL đối chứng `13_tn06_olap_checks.sql` trên SQL Server 2022 (`results/TN06/chi_2026-11-15/TN06_sql.png`)]**
*Hình 5.8. Kết quả thực thi bộ truy vấn SQL đối chứng `13_tn06_olap_checks.sql` trên SQL Server 2022*

Thứ hai, bảng tổng hợp đối soát chéo toàn bộ các kịch bản trong TN06 giữa dữ liệu nguồn (`Coffee.csv`), truy vấn SQL Server (`13_tn06_olap_checks.sql`) và truy vấn MDX trên khối SSAS (`ssas/queries.mdx`) được trình bày tại Bảng 5.9:

| Kịch bản kiểm thử OLAP (TN06) | Bộ lọc áp dụng (`Time / Location / Product`) | Kết quả từ nguồn `Coffee.csv` | Kết quả từ SQL Server (`CoffeeDW`) | Kết quả từ SSAS Cube (`queries.mdx`) | Độ lệch |
| --- | --- | --- | --- | --- | ---: |
| **1. Tổng toàn khối (All Periods)** | `24 tháng`, `4 Market`, `13 Product` | `Sales = 819.811`, `Budget = 746.160`, `Profit = 259.543`, `Gap = +73.651` | `Sales = 819.811`, `Budget = 746.160`, `Profit = 259.543`, `Gap = +73.651` | `Sales = 819.811`, `Budget = 746.160`, `Profit = 259.543`, `Gap = +73.651` | 0 |
| **2. Slice kỳ `11/2013`** | `DateKey = 20131101` (`4 Market`) | `Central = 10.966`, `East = 7.302`, `South = 4.467`, `West = 11.300` (Tổng `34.035`) | `Central = 10.966`, `East = 7.302`, `South = 4.467`, `West = 11.300` (Tổng `34.035`) | `Central = 10.966`, `East = 7.302`, `South = 4.467`, `West = 11.300` (Tổng `34.035`) | 0 |
| **3. Slice & Roll-up `Central 01/2012`** | `DateKey = 20120101`, `Market = Central` (gộp 6 bang) | `Sales = 10.346`, `Budget = 9.970`, `Profit = 2.956`, `Ach = 103,77%` | `Sales = 10.346`, `Budget = 9.970`, `Profit = 2.956`, `Ach = 103,77%` | `Sales = 10.346`, `Budget = 9.970`, `Profit = 2.956`, `Ach = 103,77%` | 0 |
| **4. Slice & Roll-up `West 01/2012`** | `DateKey = 20120101`, `Market = West` (gộp 5 bang) | `Sales = 10.453`, `Budget = 9.460`, `Profit = 2.356`, `Ach = 110,50%` | `Sales = 10.453`, `Budget = 9.460`, `Profit = 2.356`, `Ach = 110,50%` | `Sales = 10.453`, `Budget = 9.460`, `Profit = 2.356`, `Ach = 110,50%` | 0 |
| **5. Dice & Pivot nhóm `Coffee`** | `DateKey = 20120101`, `{Central, East}`, `ProductType = Coffee` | `Central = 2.663`, `East = 2.105`, Tổng = `4.768` (`Budget = 4.640`) | `Central = 2.663`, `East = 2.105`, Tổng = `4.768` (`Budget = 4.640`) | `Central = 2.663`, `East = 2.105`, Tổng = `4.768` (`Budget = 4.640`) | 0 |
| **6. Drill-down `South 08/2013`** | `DateKey = 20130801`, `Market = South` (7 sản phẩm) | `Sales = 4.601`, `Budget = 4.610`, `Gap = -9`; `Colombian = -268`, `Decaf Irish Cream = -105` | `Sales = 4.601`, `Budget = 4.610`, `Gap = -9`; `Colombian = -268`, `Decaf Irish Cream = -105` | `Sales = 4.601`, `Budget = 4.610`, `Gap = -9`; `Colombian = -268`, `Decaf Irish Cream = -105` | 0 |
| **7. Tồn kho bán cộng (`Inventory`)** | Kỳ cuối `2013-12-01` (không cộng dồn 24 tháng `3.182.971`) | `Central = 45.252`, `East = 31.529`, `South = 11.444`, `West = 58.933` (Tổng `147.158`) | `Central = 45.252`, `East = 31.529`, `South = 11.444`, `West = 58.933` (Tổng `147.158`) | `Central = 45.252`, `East = 31.529`, `South = 11.444`, `West = 58.933` (Tổng `147.158`) | 0 |

*Bảng 5.9. Bảng đối soát toàn diện kết quả phân tích đa chiều giữa Tệp nguồn – SQL Server – SSAS Cube*

### 5.5.3. Nhận xét kết quả

Thực nghiệm TN06 xác nhận khối đa chiều `Coffee Performance` trên SSAS Multidimensional và lớp Data Mart trên SQL Server đã được thiết kế đồng bộ, chính xác về mặt ngữ nghĩa dữ liệu:
* Thiết kế khóa ghép `(Year, Quarter)` và khóa tháng `DateKey` (`YYYYMMDD`) trong chiều `Dim Date` đã ngăn chặn triệt để lỗi gộp nhầm các tháng cùng tên của hai năm khác nhau.
* Các phép biến đổi không gian đa chiều (`Slice`, `Drill-down`, `Roll-up`, `Dice`, `Pivot`) bảo toàn tuyệt đối tổng số đo, đồng thời tính lại chính xác các chỉ tiêu tỷ lệ (`BudgetAchievement`, `ProfitMargin`) và chỉ tiêu bán cộng (`Inventory` theo kỳ cuối).
* Toàn bộ hệ thống View tại lớp Data Mart (`mart.vw_Detail`, `mart.vw_MarketPeriod`, `mart.vw_MarketProductPeriod`) đã được kiểm chứng khớp 100% với nguồn và Cube, tạo nền tảng dữ liệu tin cậy để bàn giao cho mô-đun dự báo chuỗi thời gian (Chương 6) và hệ thống Dashboard phục vụ người dùng cuối (Chương 7).
