# TN11 — Protocol nghiệm thu người dùng Excel và Streamlit

Phiên bản ngày **19/11/2026**. Trạng thái: **đã chuẩn bị protocol và đáp án; chưa có phiên người thử**. Tác vụ agent/AppTest thực hiện được lưu riêng, không nhập vào dữ liệu UX.

## 1. Mục đích và điều kiện bắt đầu

Đo khả năng trả lời đúng và thời gian tìm câu trả lời trên cùng snapshot Coffee bằng Excel PivotTable và Streamlit. Chỉ kết luận trong phạm vi người tham gia thực tế. Ghi số người và mức quen Excel/web; không tự gán họ là chuyên gia/quản lý nếu không có thông tin đó.

Người điều phối chuẩn bị trước:

```powershell
.\.venv\Scripts\python scripts/prepare_trang_acceptance.py
.\.venv\Scripts\python -m coffee_dw.cli demo
.\.venv\Scripts\python -m streamlit run apps/dashboard/app.py --server.port 8501
```

Đầu ra ở `results/trang_acceptance/`: `excel_input.csv` chứa nguồn đã chuẩn hóa, `monthly_market.csv`, `answer_key.json`, `expected_products_A/B.csv`, `ux_trials.csv` và manifest checksum. Người điều phối giữ riêng đáp án, không đưa cho người thử. Script không xóa phiếu đã ghi khi chạy lại.

Import `excel_input.csv` bằng **Data → From Text/CSV** với UTF-8, giữ AreaCode dạng Text và MonthStart dạng ngày, không mở rồi lưu đè CSV gốc. Lưu workbook thử riêng. Tạo PivotTable có thể đổi Rows Market/State/ProductName, Values **Sum of Sales**, **Sum of BudgetSales**, **Sum of Profit**; Gap ở bảng trả lời bằng tổng Sales trừ tổng BudgetSales. Nếu có tỷ lệ, chia hai tổng, không lấy trung bình tỷ lệ dòng. Cho hai công cụ cùng mức chuẩn bị: mở sẵn tệp/trang và hướng dẫn cách dùng bộ lọc cơ bản, chưa đặt sẵn đáp án.

Trước đo, người điều phối đối soát West 01/2012 = Sales 10.453, BudgetSales 9.460, Gap +993 trên cả hai công cụ; kiểm tra CSV nhập Excel không đổi kiểu/số. Khóa checksum snapshot cho toàn phiên. Không tiếp tục đo khi hai công cụ đang dùng dữ liệu khác nhau hoặc báo lỗi.

## 2. Phân nhóm và giảm học thuộc

Mỗi người làm ba tác vụ trên mỗi công cụ, tổng sáu lượt. Phân tuần tự theo nhóm bốn để cân bằng công cụ, thứ tự và bộ đề:

| Nhóm | Khối đầu, order=1 | Khối sau, order=2 |
| --- | --- | --- |
| G1 | Excel — bộ A | Streamlit — bộ B |
| G2 | Streamlit — bộ A | Excel — bộ B |
| G3 | Excel — bộ B | Streamlit — bộ A |
| G4 | Streamlit — bộ B | Excel — bộ A |

Nếu số người không chia hết cho bốn, ghi phân bố thực và nêu mất cân bằng. Dùng mã P01, P02…; không ghi tên, số điện thoại, tài khoản. Ghi mức quen công cụ trong `notes` bằng nhãn người tham gia tự mô tả. Cho hướng dẫn chung và một tác vụ làm quen không trùng đề đo trước mỗi công cụ; ghi thời lượng làm quen. Không tiết lộ đúng/sai hoặc đáp án giữa hai khối.

## 3. Phiếu đề cho người tham gia

Không đưa phần đáp án của người điều phối cho người tham gia.

| Task | Bộ A | Bộ B | Câu trả lời cần ghi |
| --- | --- | --- | --- |
| T1 | Trong toàn năm 2012, Market nào có tổng Sales lớn nhất? | Trong toàn năm 2013, Market nào có tổng Sales lớn nhất? | Tên Market và tổng Sales |
| T2 | Chọn 01/2012, Central, mở danh sách State. | Chọn 01/2013, East, mở danh sách State. | Tổng Sales/BudgetSales/Gap của Market; State có Gap thấp nhất và Gap của State đó; xác nhận tổng State bằng tổng Market |
| T3 | Trong 08/2013, tìm Market có Gap thấp nhất, rồi tìm Product có Gap thấp nhất trong Market đó và xuất bảng sản phẩm. | Trong 08/2012, tìm Market có Gap thấp nhất, rồi tìm Product có Gap thấp nhất trong Market đó và xuất bảng sản phẩm. | Market, Gap Market, Product, Gap Product; nộp CSV đúng kỳ/Market |

Khi Gap Market dương, người thử cần nói vượt ngân sách dù đó là mức Gap thấp nhất; không gọi mọi trường hợp là hụt. Đồng hạng xếp tên Market/State/ProductName tăng dần sau Gap. Hai bộ đề tương đương về thao tác, không đồng nhất độ khó: T2 có số State khác nhau, T3 có một Market Gap âm và một Market Gap dương. Cần công bố giới hạn này khi so thời gian. Hai năm đều có thể trả cùng tên Market/Product nhưng các giá trị cần cung cấp khác nhau.

## 4. Đồng hồ, trợ giúp và cách chấm

1. Reset về trang/tệp ban đầu trước từng khối; đưa đề từng tác vụ. Người tham gia đọc đề xong và báo sẵn sàng thì bắt đầu bấm giờ.
2. Dừng khi người tham gia chốt đủ câu trả lời và tệp xuất nếu có. Nếu sau 300 giây vẫn chưa xong, dừng tác vụ, ghi thời gian thực đã trôi, `correct=0`, `notes=timeout`; không điền thời gian 0 hoặc loại khỏi mẫu.
3. Mỗi lần người điều phối hướng dẫn thao tác sau khi bắt đầu đều tăng `help_count` một lần và ghi nội dung ngắn. Không đọc đáp án. Nếu lỗi hệ thống làm gián đoạn, ghi `notes=system_error...`; giữ bản ghi, tách khỏi phân tích chính bằng bản sao dữ liệu có lý do loại, không xóa dấu vết.
4. Chấm `correct=1` chỉ khi **đủ mọi phần** tác vụ. Sales/Budget/Gap nguồn là số nguyên, chấm đúng số; cho phép định dạng phân cách hàng nghìn khác nhau. T2 phải giữ đúng kỳ và tổng State khớp Market. T3 phải có CSV, khóa `(Market, ProductName)` và các tổng dùng chung Sales/BudgetSales/Profit/Gap khớp `expected_products_A/B.csv`; không yêu cầu byte hoặc thứ tự cột giống nhau.
5. Ghi nguyên câu trả lời vào `answer`, không sửa thành đáp án chuẩn. Người điều phối có thể chấm sau hai khối để tránh gợi ý. Ghi lý do sai vào `notes`.

Ví dụ cấu trúc phiếu (đây là định nghĩa cột, **không phải lượt thử**):

| Cột | Quy ước |
| --- | --- |
| participant_id | Mã ẩn danh P01… |
| tool | `Excel` hoặc `Streamlit` |
| task, set | `T1`/`T2`/`T3`, `A`/`B` |
| order | 1 hoặc 2, là thứ tự khối công cụ |
| answer | Câu trả lời thực được chốt; với timeout ghi phần đã trả lời/“chưa có đáp án” |
| correct | 1 đúng đủ; 0 còn thiếu/sai/hết giờ |
| seconds | Số giây thực, lớn hơn 0 |
| help_count | Số nguyên không âm |
| notes | Lỗi, trợ giúp, file CSV nộp, kinh nghiệm tự báo, khác biệt quy trình |

CSV mẫu chỉ có header tại [ux_trials_template.csv](ux_trials_template.csv). Mỗi phiên nên dùng bản sao riêng, không ghi vào tệp kết quả đã công bố của phiên khác.

## 5. Tổng hợp và công bố

```powershell
.\.venv\Scripts\python scripts/prepare_trang_acceptance.py --trials results/trang_acceptance/ux_trials.csv
```

Lệnh kiểm tra các trường bắt buộc, số đo hữu hạn, đúng/sai 0/1, thứ tự 1/2, mã đề hợp lệ, trùng lượt và tính nhất quán hai khối. Đầu ra `ux_summary.csv` báo số đúng/tổng lượt, tỷ lệ đúng, median giây **các lượt đúng** và tổng trợ giúp theo công cụ; `ux_audit.json` nêu số người/lượt và người chưa đủ sáu tác vụ. Không có lượt thì trả `not_measured`, không tạo biểu đồ hay metric giả.

Khi có dữ liệu, báo riêng từng lượt trong phụ lục và so cặp trong cùng người. Cần xem phân bố thứ tự, bộ đề và mức quen công cụ trước khi diễn giải. Với pilot ít người, chỉ viết “trong nhóm thử N người, …”; không suy ra web tốt hơn cho mọi người dùng hoặc đánh đồng thời gian UX với thời gian truy vấn SQL. Nếu tách bản ghi lỗi hệ thống, công bố cả số bản ghi và quy tắc loại; script không tự loại giúp người điều phối.

## 6. Các ca nghiệm thu kỹ thuật riêng

Các ca West→East→West, CSV/drill-down, Inventory kỳ cuối, không chọn Market, kho thiếu/hỏng, forecast thiếu/cũ và phát audio được kiểm tra trong hồ sơ kỹ thuật. Không bấm giờ agent rồi đưa vào phiếu người thử. Bằng chứng kỹ thuật hỗ trợ tính đúng ứng dụng; nó không đo mức dễ dùng của con người.
