# Thử nghiệm Linear Regression giữa Marketing và Sales

## 1. Câu hỏi và phạm vi

Thử nghiệm trả lời câu hỏi: **trong từng Market, tổng Marketing của một tháng liên hệ tuyến tính với tổng Sales cùng tháng như thế nào?** Đây là bài toán hồi quy giải thích và thử kịch bản, không phải dự báo Sales tháng kế tiếp và không chứng minh Marketing gây ra Sales.

Mô hình được giữ tách khỏi forecast hiện có vì hai chức năng dùng thông tin khác nhau:

| Chức năng | Câu hỏi | Feature có sẵn khi nào? | Vai trò |
| --- | --- | --- | --- |
| Forecast hiện có | Sales tháng tới sẽ khoảng bao nhiêu? | Sales của các tháng trước | Dự báo một bước theo thời gian |
| Linear Lab | Marketing và Sales cùng tháng đi với nhau ra sao? | Marketing của chính tháng cần ước lượng | Giải thích liên hệ và thử what-if |

Không sinh thêm dữ liệu để làm đẹp metric. Dữ liệu synthetic không tạo thêm bằng chứng thực về quan hệ Marketing–Sales và có thể làm kết quả trông tốt giả tạo.

## 2. Dữ liệu và phép chia thời gian

- Nguồn chạy trên giao diện: `mart.vw_Detail`, chỉ đọc qua backend hiện tại.
- Grain sau tổng hợp: **MonthStart × Market**.
- Chỉ tiêu: `SUM(Marketing)` là feature `x`; `SUM(Sales)` là target `y`.
- Snapshot: 24 tháng từ 01/2012 đến 12/2013 × 4 Market = **96 quan sát**, mỗi Market có 24 quan sát.
- Train: 18 tháng, 01/2012–06/2013.
- Test: 6 tháng cuối, 07/2013–12/2013.
- Không xáo trộn ngẫu nhiên, không nội suy tháng thiếu và không đổi thiếu thành số 0.

Mỗi Market học một phương trình độc lập trên train:

```text
Sales = intercept + coefficient × Marketing
```

Sau đó phương trình đã học được giữ nguyên để dự đoán sáu điểm test. Actual test chỉ dùng để tính metric, không tham gia fit hệ số.

## 3. Cách đọc metric

| Metric | Cách đọc trong thử nghiệm |
| --- | --- |
| Pearson `r` | Mức đồng biến tuyến tính trên 24 tháng; gần 1 là cùng tăng rõ hơn. Đây chỉ là tương quan mô tả. |
| MAE test | Trung bình trị tuyệt đối `|Actual − Prediction|` trên 6 tháng test, cùng đơn vị Sales nguồn. Càng thấp càng tốt. |
| RMSE test | Căn trung bình bình phương sai số; phạt các lỗi lớn mạnh hơn MAE. Càng thấp càng tốt. |
| R² test | So Linear với dự đoán hằng theo trung bình actual của chính tập test. `R² < 0` nghĩa là đường Linear tổng quát hóa kém hơn mốc hằng này trên test. |
| Baseline MAE | MAE khi luôn dự đoán bằng Sales trung bình của 18 tháng train; baseline này không đọc actual test để tạo dự đoán. |

R² và baseline MAE dùng hai mốc so sánh khác nhau nên không được suy ra trực tiếp từ nhau. Giao diện hiển thị cả hai để tránh kết luận dựa trên một metric.

## 4. Kết quả snapshot gốc

| Market | Pearson r | Hệ số | MAE test | RMSE test | MAE baseline train-mean | R² test |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Central | 0,5623 | 4,9310 | 325,45 | 386,01 | 361,00 | −2,8745 |
| East | 0,7234 | 4,8075 | 274,75 | 295,67 | 314,22 | −2,0051 |
| South | 0,6205 | 3,4321 | 187,37 | 215,30 | 263,22 | −9,7109 |
| West | 0,7206 | 3,2312 | 333,87 | 397,89 | 536,00 | −1,5295 |

Ví dụ West có hệ số `3,2312`: trên 18 tháng train, Marketing tăng một đơn vị **đi cùng** Sales tăng khoảng 3,23 đơn vị theo đường đã fit. Không được diễn đạt thành “chi thêm một đơn vị Marketing chắc chắn làm Sales tăng 3,23”, vì dữ liệu quan sát không cô lập mùa vụ, giá, sản phẩm hoặc yếu tố thị trường.

Tương quan toàn kỳ ở mức vừa đến khá (`0,5623–0,7234`), nhưng R² test âm ở cả bốn Market. Marketing cùng tháng có tín hiệu mô tả nhưng một đường thẳng đơn biến không theo kịp mức Sales trong sáu tháng cuối. Vì vậy kết quả **không đạt điều kiện thay forecast hiện có**.

## 5. Chức năng trên giao diện

Mở [Linear Lab](http://127.0.0.1:8504/linear.html) trong cùng server với Cube 3D và Query Studio. Trang cung cấp:

1. Chọn một trong bốn Market.
2. Xem 18 điểm train, 6 điểm test và đường chỉ fit từ train.
3. Xem Pearson r, MAE, RMSE và R² test cùng diễn giải ngắn.
4. Điều chỉnh Marketing từ −30% đến +50% quanh tháng tham chiếu mới nhất; Sales giả định được tính trên đường hồi quy.
5. So sánh bốn Market và hiện cảnh báo khi R² test âm.

Thanh kịch bản chỉ là phép tính “nếu đi theo đường đã học và các yếu tố khác không đổi”. Nó không tối ưu ngân sách, không bảo đảm doanh thu và không ghi dữ liệu trở lại kho.

## 6. Quyết định tích hợp

**Giữ Linear Lab và forecast Sales thành hai tab/chức năng tách biệt. Chưa gộp hai model.** Forecast cũ vẫn trả lời bài toán một tháng tới bằng dữ liệu quá khứ. Linear Lab bổ sung một phần dễ giải thích về quan hệ Marketing–Sales và trung thực cho thấy giới hạn khi đem sang kỳ mới.

Bước thử tiếp theo hợp lý là hồi quy theo thời gian có `Sales lag 1/2/3`, Marketing kế hoạch biết trước và biến tháng/mùa vụ, sau đó so với Naive/MA3 trên đúng validation/test. Chỉ tích hợp vào forecast nếu mô hình mới thắng baseline trên validation và giữ kết quả hợp lý trên test; không chọn vì hình đẹp hoặc vì đã xem test.

## 7. Tái lập và kiểm tra

```powershell
.\.venv\Scripts\python.exe apps/cube_explorer/server.py --backend sqlserver --database CoffeeDW_Trang_SSIS_TN03_20261120 --port 8504
.\.venv\Scripts\python.exe -m pytest tests/test_linear_marketing.py tests/test_cube_explorer.py -q -p no:cacheprovider
node --check apps/cube_explorer/linear.js
```

Code mô hình ở `src/coffee_dw/linear_marketing.py`; API chỉ đọc là `GET /api/linear`; giao diện nằm trong `apps/cube_explorer/linear.html`, `linear.css`, `linear.js`. Kiểm thử khóa mốc thời gian, số quan sát, metric West, việc actual test không làm đổi phương trình đã fit và quy tắc từ chối khi thiếu một Market–tháng.
