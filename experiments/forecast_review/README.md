# Mở rộng thăm dò: seasonal naive12 và SES

Đợt mở rộng nhỏ sau vòng bảy cấu hình: giữ nguyên nguồn thật và protocol chính,
chỉ thêm **hai family/bốn cấu hình**. Không sinh doanh số giả, không thay MA3 đang
phục vụ, không tự công bố kết quả này vào kho hoặc demo.

## Chạy từng bước

Tại root, dùng môi trường đã cài project `.[dev,explore]`:

```powershell
.\.venv\Scripts\python experiments/forecast_review/run.py
.\.venv\Scripts\python -m pytest -p no:cacheprovider tests/test_forecast_review.py
```

1. Lưu `protocol.json` và danh sách cấu hình **trước** khi tính sai số.
2. Đọc Coffee.csv bằng logic chung; xác minh đủ96 ô Market–tháng, 24tháng/Market, không tự điền tháng thiếu.
3. Giữ lịch15/6/3: lịch sử01/2012–03/2013, validation04–09/2013, test10–12/2013.
4. Tính lại bảy cấu hình hiện có bằng đúng code tuning; thêm seasonal naive12 và SES alpha0.2/0.5/0.8.
5. Xếp hạng11 cấu hình bằng MAE gộp24 dự báo validation/cấu hình; lưu `selection.json` trước lời gọi pha test.
6. Chấm test đã biết để mô tả, không chọn lại. Xuất dự báo01/2014 với actual thiếu, bảng/nhận xét/checksum.

Mọi dự báo một bước chỉ dùng dữ liệu trước target; scaler/Ridge của nhóm cũ vẫn fit riêng quá khứ.
Các alpha SES là fixed grid, không tối ưu theo test. Không huấn luyện LSTM hoặc dò hàng loạt cấu hình.

## Hai quy tắc mới

- **Seasonal naive12:** dự báo tháng`t` bằng Sales tháng`t−12`. Ví dụ dự báo04/2013 dùng04/2012,
  không dùng05/2012 hoặc actual04/2013. Cần đủ12 tháng lịch sử liên tục.
- **SES:** mức ban đầu bằng quan sát Sales đầu tiên; lần lượt cập nhật
  `level = alpha × observed_sales + (1−alpha) × previous_level` trên các tháng đã biết.
  Dự báo một bước là mức cuối tại origin. Không tối ưu mức ban đầu, không có training epoch hoặc scaler.

## Kết quả lần chạy 19/11/2026

| Cấu hình | MAE validation, N=24 | MAE test đã biết, N=12 |
| --- | ---: | ---: |
| **MA3 — chọn bằng validation** | **223,28** | **225,22** |
| SES alpha0.5 | 230,40 | 204,88 |
| MA6 — đối chứng đã có | 231,31 | 152,00 |
| Seasonal naive12 | 233,96 | 537,08 |
| SES alpha0.8 | 246,88 | 218,43 |
| SES alpha0.2 | 256,74 | 161,11 |

Toàn bộ11 cấu hình nằm ở `validation_leaderboard.csv`, không chỉ những dòng chọn ở bảng trên.
**Không có cấu hình mới nào vượt MA3 trên validation.** SES alpha0.5 gần nhất nhưng MAE vẫn cao hơn
khoảng3,19%. SES alpha0.2 có test tốt hơn nhưng không được chọn lại dựa trên test.
Seasonal naive12 test rất kém; kết quả này không ủng hộ việc mặc định dùng cùng tháng năm trước.

MA3 test giữ nguyên MAE225,22/RMSE265,41/MAPE2,40%, N12. Đây là sai số Sales theo đơn vị nguồn;
không chuyển MAPE thành “accuracy”, không xem MAE là khoảng dự báo95% hoặc số đơn hàng.

Kiểm tra bỏ từng tháng khỏi **bảng chấm** validation: MA3 thắng4/6 lượt, seasonal12 thắng2/6.
Đây chỉ là độ nhạy của thứ hạng khi có ít kỳ; không fit lại, không dùng để thay lựa chọn.

## Minh chứng

Kết quả ở `experiments/forecast_review/results/`, được ignore cục bộ:

| Tệp | Nội dung |
| --- | --- |
| `protocol.json`, `configurations.csv` | Grid, split, công thức và tiêu chí đã lưu trước chấm |
| `source_profile.csv`, `input_checks.csv`, `monthly_market.csv` | Hồ sơ/checksum, kiểm tra và96 ô gốc |
| `validation_predictions.csv`, `validation_metrics.csv`, `validation_leaderboard.csv` | 264 dự báo validation,55 dòng metric và thứ hạng11 cấu hình |
| `selection.json` | Quyết định chọn chỉ bằng validation, lưu trước test |
| `test_predictions.csv`, `test_metrics.csv` | 132 dự báo test đã biết và metric |
| `all_predictions.csv`, `all_metrics.csv` | 396 dự báo với error/selected và110 dòng metric theo Market/ALL,split |
| `origins.csv` | Origin/TrainEnd, lịch sử, trạng thái SES hoặc tháng tham chiếu seasonal |
| `baseline_ridge_parameters.csv` | Scaler/hệ số của các đối chứng Ridge được tái lập |
| `improvement_vs_ma3.csv` | Chênh MAE/RMSE và % cải thiện so MA3 trong đúng nhóm/pha |
| `validation_sensitivity.csv` | Sáu lượt bỏ một tháng khỏi bảng chấm, N20/lượt |
| `future.csv` | 44 dự báo01/2014; bốn dòng Selected; mọi actual trống |
| `execution_events.csv` | Thứ tự protocol → selection → test |
| `summary.json`, `analysis.md`, `manifest.json` | Kết luận, giới hạn, phiên bản, source/code/artifact hashes |

## Kiểm tra và giới hạn

**8 test đạt:** seasonal dùng đúng t−12; SES khớp phép tính tay, xử lý0/âm/hữu hạn và alpha lỗi;
bảy cấu hình cũ khớp từng prediction; không đọc actual tháng đích/tương lai;
thay toàn bộ actual test không đổi validation selection/forecast test đầu;
chặn chọn bằng test hoặc leaderboard thiếu; protocol và selection có trước từng pha;
future actual thiếu, checksum đủ; tháng thiếu không đổi thành dữ liệu giả.

Test và một phần kết quả validation đã được xem trong repo trước đợt này. Đây là **thăm dò**,
không phải kiểm định mù mới hoặc bằng chứng triển khai hiệu quả hơn. Giữ mô hình phục vụ MA3.
Muốn xác nhận cải thiện cần quan sát thật mới chưa xem, cùng grain/định nghĩa và khóa lựa chọn
trước khi mở actual. Không dùng dữ liệu tổng hợp giả làm thêm tháng độc lập để giảm metric.
Chỉ hai năm lịch sử chưa đủ khẳng định mùa vụ ổn định. Không có biến giá/khuyến mãi với
thời điểm được biết để kết luận nguyên nhân hoặc tính tác động kinh doanh.
