# Coffee Query Studio: bộ tạo truy vấn và Gemini Text-to-SQL

## Mục tiêu

Chức năng trả lời các câu hỏi tổng hợp linh hoạt mà người demo không phải gõ SQL:

- Tính **tổng**, **trung bình**, `COUNT`, `MIN/MAX`, tỷ lệ và xếp hạng top-N.
- Nhóm theo tháng, Market, State, nhóm sản phẩm hoặc sản phẩm.
- Lọc theo năm, tháng, nhiều Market và nhiều sản phẩm.
- Xem câu SQL thật và tham số đã dùng để có thể giải thích, đối soát.

Đây là truy vấn mô tả trên dữ liệu kho, không phải mô hình dự báo hoặc mô hình học máy.

## Hai chức năng độc lập

### Bộ chọn truy vấn

Đây là chức năng chính và ổn định khi demo. Giao diện gửi một đặc tả JSON, ví dụ:

```json
{
  "aggregate": "SUM",
  "measures": ["Sales", "BudgetSales", "Gap"],
  "groupBy": ["Market"],
  "year": 2013,
  "month": null,
  "markets": [],
  "products": []
}
```

Server không nhận câu SQL từ browser. Nó chỉ ghép identifier có trong allowlist và bind mọi giá trị lọc bằng dấu `?`.

### Gemini API

Gemini là chức năng Text-to-SQL, không phải engine chạy dữ liệu. Model trả một kế hoạch JSON gồm `status`, `sql` và `explanation`. Backend không chạy chuỗi đó ngay mà dùng SQLGlot parse theo dialect T-SQL/SQLite, canonicalize lại AST rồi kiểm tra:

- Đúng một `SELECT` hoặc `WITH … SELECT`, không có dấu phân tách/comment.
- Đọc đúng một lần từ `mart.vw_Detail` trên SQL Server hoặc `vw_Detail` trên SQLite.
- Chỉ dùng cột và hàm phân tích trong allowlist; không system variable/table-valued function.
- Không DDL, DML, `INTO`, self-join hoặc nguồn thứ hai.
- Tối đa 201 dòng được đọc để phát hiện truncation; giao diện hiển thị 200 dòng.
- Inventory chỉ được phép khi lọc đúng một `MonthStart`.

Câu hỏi có năm rõ ràng được kiểm trước khi gọi Gemini. Ví dụ `2015` trả HTTP 400 vì snapshot chỉ có `2012–2013`; hệ thống không được phép xóa điều kiện rồi trả tổng toàn kho. Nếu SQL của model không qua AST validator, hệ thống thử model fallback kế tiếp.

Gemini không bắt buộc. `GET /api/ai/status` dùng API `models.list`, rồi giao danh sách đó với allowlist text model có quota của dự án. Agent, Pro quota 0, TTS, image, embedding, Live API, Computer Use và Robotics không được dùng. Khi key chưa cấu hình hoặc mọi model đều hết quota, bộ chọn truy vấn không bị ảnh hưởng.

Thứ tự fallback ưu tiên hạn mức cao hơn:

1. `gemini-3.5-flash-lite` — 15 RPM, 500 RPD.
2. `gemini-3.1-flash-lite` — 15 RPM, 500 RPD.
3. `gemini-2.5-flash-lite` — 10 RPM, 20 RPD.
4. Các Flash text còn lại có 5 RPM, 20 RPD: `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3-flash`, `gemini-2.5-flash`, `gemini-4-hydrogen`.

Một model chỉ xuất hiện nếu `models.list` của key thật trả model đó và `supportedGenerationMethods` chứa `generateContent`. Khi model đầu trả `429 RESOURCE_EXHAUSTED`, `503` hoặc lỗi model tạm thời, server thử model sau. Lỗi `401/403` dừng ngay vì đổi model không thể sửa key hoặc quyền sai.

Kiểm tra thực ngày 22/11/2026 với key local trả **9 model text** sau khi loại 5 biến thể image/TTS. Các câu hỏi SUM, AVG, top-5, COUNT, tỷ lệ đạt ngân sách và filter Market/năm đều chạy đúng. Một số lượt tự chuyển từ model đầu sang model thứ hai vì SQL đầu không qua validator hoặc model tạm lỗi, xác nhận fallback hoạt động ngoài test mô phỏng.

## Phép tính và cách giải thích

### SUM

`SUM` cộng các ô fact trong cùng filter và nhóm phân tích. Với `Gap`:

```sql
SUM(Sales) - SUM(BudgetSales)
```

Điều này giữ đúng hợp đồng `Gap = Sales − BudgetSales` trên cùng phạm vi.

### AVG

`AVG` là trung bình trên các ô fact có grain **tháng × AreaCode × sản phẩm** trong phạm vi đã chọn. Ví dụ `AVG(Marketing)` theo Market là chi phí Marketing trung bình của một ô fact, không phải chi phí trung bình trên một đơn hàng; dữ liệu nguồn không có grain đơn hàng.

Với Gap, biểu thức là `AVG(Sales - BudgetSales)`. Không diễn giải AVG này thành tỷ lệ đạt ngân sách. Tỷ lệ đạt ngân sách phải tính bằng `SUM(Sales) / NULLIF(SUM(BudgetSales), 0)`: bộ chọn thủ công chưa có measure tỷ lệ, nhưng Gemini Text-to-SQL hỗ trợ công thức này và AST validator kiểm tra các cột/hàm.

### Vì sao không có Inventory?

Inventory là số thời điểm. Hợp đồng kho yêu cầu chỉ lấy trong một kỳ theo chính sách kỳ cuối, không `SUM` xuyên nhiều tháng. Bộ chọn thủ công loại Inventory hoàn toàn; Text-to-SQL chỉ cho phép cột này khi câu SELECT lọc đúng một `MonthStart`.

## Miền được phép

| Loại | Bộ chọn thủ công | Gemini Text-to-SQL |
| --- | --- | --- |
| Phép tính | `SUM`, `AVG` | `SUM`, `AVG`, `COUNT`, `MIN/MAX`, tỷ lệ, `CASE`, `HAVING`, top-N, window ranking an toàn |
| Chỉ tiêu | 11 measure trừ Inventory | Các measure hợp đồng; Inventory cần đúng một tháng |
| Chiều | `MonthStart`, `Market`, `State`, `ProductType`, `ProductName` | Các thuộc tính của `vw_Detail` |
| Bộ lọc | năm/tháng, Market, ProductName | Điều kiện SELECT trên giá trị/cột hợp lệ |

Bộ chọn có giới hạn bốn chỉ tiêu và ba chiều. Text-to-SQL rộng hơn nhưng không có nghĩa “mọi SQL trên server”: chỉ SELECT phân tích từ một view mart. Giới hạn 200 dòng hiển thị tránh làm trang demo bị treo.

## Dấu `?` trong SQL thủ công

Bộ chọn thủ công dùng parameter binding. Ví dụ lọc năm 2013:

```text
WHERE MonthStart >= ? AND MonthStart < ?
?1 = "2013-01-01" · ?2 = "2014-01-01"
```

Dấu `?` không phải thiếu ngày; giá trị được truyền riêng để tránh ghép chuỗi. Giao diện hiển thị từng binding theo số thứ tự. SQL của Gemini được parse/canonicalize từ AST và hiện literal trong câu SELECT đã kiểm tra.

### Vì sao server dùng 201 dòng nhưng giao diện không còn hiện `TOP 201`?

Giới hạn nghiệp vụ của giao diện là 200 dòng. Server thực thi với giới hạn **201** để phân biệt “có đúng 200 dòng” với “còn ít nhất một dòng chưa hiển thị”: dòng thứ 201 chỉ là tín hiệu `truncated`, không được đưa vào bảng. Đây là hàng rào kỹ thuật, không phải điều kiện do người dùng hỏi. Vì vậy giao diện hiện `sql` nghiệp vụ đã canonicalize mà không chèn giới hạn này; câu thực thi có guard nằm trong `executionSql` để test và audit. Nếu Gemini chủ động tạo `TOP 5` cho câu top-5 thì `TOP 5` vẫn được giữ vì đó là logic nghiệp vụ.

## Mở kết quả trên Data Cube 3D

Mỗi phản hồi truy vấn có thêm `cubeContext` gồm `year`, `month`, `market`, `product`, `measure` và `mode`. Nút **Mở trên Data Cube 3D** biến ngữ cảnh này thành URL hash; cube kiểm tra lại từng giá trị với metadata mart trước khi áp dụng.

- Có đúng tháng → mở chế độ cắt lát ở tháng đó.
- Chỉ có năm → mở toàn bộ các tháng trong năm; không có năm → mở toàn bộ thời gian của snapshot.
- Chỉ có một Market hoặc sản phẩm rõ ràng → giữ đúng giá trị đó; nếu không rõ thì để “tất cả”.
- Với top-N tối đa 10 sản phẩm, cube mang theo toàn bộ `ProductName` trả về, làm nổi bật tất cả sản phẩm và tính KPI cùng tháng trên đúng nhóm đó.
- Với đúng một số đo theo `Market`, ví dụ `COUNT(*) AS RecordCount GROUP BY Market`, cube chuyển sang chế độ roll-up: bốn dòng kết quả thành đúng bốn khối. Nó không mở lại lưới tháng × sản phẩm và không đổi `RecordCount` thành Sales.
- Giá trị ngoài metadata bị bỏ qua; không được dùng link để đưa cột hoặc miền dữ liệu lạ vào ứng dụng.

Cube biểu diễn lát cắt tương thích gần nhất, không thay bảng kết quả của một truy vấn bất kỳ. Ví dụ, top-5 vẫn phải đọc đủ năm dòng trong bảng; cube làm nổi cả năm dải sản phẩm trên năm đang hỏi. KPI bên phải là tổng của năm sản phẩm tại **tháng đang trỏ trên thanh thời gian**, không phải tổng năm của bảng xếp hạng. Riêng roll-up một số đo theo Market, KPI chính là tổng của các khối kết quả và từng khối giữ nguyên giá trị từng dòng SQL.

## Ca đối soát trên SQL Server

Nguồn chạy: `CoffeeDW_Trang_SSIS_TN03_20261120`, view `mart.vw_Detail`.

**SUM Sales, BudgetSales và Gap năm 2013 theo Market:**

| Market | Sales | BudgetSales | Gap |
| --- | ---: | ---: | ---: |
| Central | 135.365 | 125.180 | 10.185 |
| East | 91.178 | 78.950 | 12.228 |
| South | 53.080 | 49.100 | 3.980 |
| West | 139.029 | 119.850 | 19.179 |

Ở cả bốn dòng, `Gap = Sales − BudgetSales`.

**AVG Marketing trên toàn bộ 24 tháng theo Market:** Central `29,32`; East `33,16`; South `24,65`; West `35,01`. Đây là trung bình ô fact, không phải tổng Marketing.

**Text-to-SQL thực:** Profit năm 2013 `153.717`; top-1 Sales là Colombian `65.487`; COUNT fact cell năm 2013 theo Market trả bốn dòng; tỷ lệ đạt ngân sách theo Market dùng tỷ lệ hai tổng. Câu hỏi năm 2015 trả lỗi phạm vi thay vì trả tổng `259.543` của toàn bộ 24 tháng.

## Cách chạy

```powershell
.\.venv\Scripts\python.exe apps/cube_explorer/server.py --backend sqlserver --database CoffeeDW_Trang_SSIS_TN03_20261120 --port 8504
```

Mở `http://127.0.0.1:8504/query.html`.

Muốn dùng Gemini, tạo file `.env` local từ `.env.example` và đặt key mới:

```dotenv
GEMINI_API_KEY=your_new_key_here
```

Không ghi key thật vào source, tài liệu, log hoặc Git. Restart server sau khi đổi `.env`. Câu hỏi, schema view và quy tắc KPI được gửi tới Google Gemini API; dữ liệu kết quả SQL không được gửi. SQL trả về chỉ chạy sau khi qua AST validator local.

## Kịch bản thuyết trình ngắn

1. Mở tab **Tạo truy vấn bằng lựa chọn** và chọn preset “Sales & Budget theo Market”.
2. Nói: “Em không gõ SQL tự do. Các tên cột đến từ allowlist, còn năm và Market đi qua parameter binding.”
3. Chạy truy vấn, chỉ vào bốn dòng và mở phần SQL để đối chiếu `SUM`, `GROUP BY`, dấu `?`.
4. Đổi sang `AVG Marketing theo Market`, giải thích AVG tính trên fact cell chứ không phải đơn hàng.
5. Mở tab Gemini, thử top-5 hoặc tỷ lệ: “Gemini viết SELECT nhưng không có quyền chạy trực tiếp. Parser chỉ cho đọc mart; nếu model viết sai, hệ thống từ chối hoặc fallback.”
6. Thử hỏi năm 2015 để chứng minh ứng dụng báo không có dữ liệu, không tự bỏ filter.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cube_explorer.py -q -p no:cacheprovider
node --check apps/cube_explorer/query.js
```

Test bao phủ bộ chọn SUM/AVG/Gap và parameter binding; ngữ cảnh link năm/lát cắt sang cube; top-N giữ đủ danh sách sản phẩm và làm nổi toàn bộ nhóm trong Three.js; Gemini model filtering/fallback; chặn năm ngoài snapshot trước khi gọi AI; AST chặn DDL, nhiều statement, system table/function, cột lạ, self-join, nguồn động và Inventory sai kỳ; fallback khi model đầu viết SQL không hợp lệ; và chạy SELECT hợp lệ trên kho tham chiếu. Kiểm tra visual bằng browser cần được chạy lại nếu môi trường không cấp quyền mở localhost.
