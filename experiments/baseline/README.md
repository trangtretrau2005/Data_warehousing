# Thử nghiệm cơ sở — ba phương pháp dự báo

Đây là bước sau [EDA của Trang](../../explore/README.md). Tái lập các cấu hình đã có trong base, lưu đầy đủ kết quả và lời phân tích. Chưa chạy dò tham số, Random Forest hoặc reconciliation. Đọc trực tiếp Coffee.csv qua bộ chuẩn hóa chung; chạy được khi chưa có kho của Chi.

## Chạy

Tại root, dùng môi trường đã chuẩn bị cho EDA:

```powershell
.\.venv\Scripts\python experiments/baseline/run.py
```

Nếu máy chưa có môi trường và thư viện vẽ:

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev,explore]"
```

Đọc [báo cáo HTML](results/report.html), [phân tích tiếng Việt](results/analysis.md), [gợi ý thuyết trình](results/presentation.md) và [hình tóm tắt một trang](results/06_summary/figures/01_study_summary.png). Các link kết quả có sau khi chạy.

## Sáu bước và minh chứng

| Bước | Bảng / tệp cần xem | Hình nên dùng |
| --- | --- | --- |
| 1 Chốt nguồn | `01_input/source_profile.csv`, `input_checks.csv`, `monthly_market.csv` | `01_input/figures/01_data_flow` |
| 2 Chốt cách thử | `02_protocol/protocol.json`, `model_specifications.csv`, `split_manifest.csv`, `first_origin_training.csv`, `first_origin_scaler.csv` | `02_protocol/figures/01_rolling_origin`, `02_method_specifications` |
| 3 Chọn bằng validation | `03_validation/predictions.csv`, `metrics.csv`, `leaderboard.csv`, `selection.json` | `03_validation/figures/01_validation_mae`, `02_validation_by_market` |
| 4 Kiểm tra và phân tích lỗi | `04_test/metrics.csv`, `selected_metrics.csv`, `prediction_errors.csv`, `largest_selected_errors.csv`, `improvement_vs_naive.csv` | Đường thực tế–dự báo, metric test, heatmap lỗi, bias, mức cải thiện |
| 5 Dự báo kỳ tiếp | `05_future/next_month.csv`, `selected_state.json` | `05_future/figures/01_next_month` |
| 6 Tổng hợp để báo cáo | `06_summary/presentation_summary.csv`, `execution_events.csv`, `presentation.md` | `06_summary/figures/01_study_summary` |

Mỗi bộ hình có **PNG 300 dpi, PDF và SVG**. Giữ Times New Roman, màu phương pháp thống nhất; thang Y riêng ở biểu đồ đường có ghi rõ. CSV giữ số chưa làm tròn. `manifest.json` lưu checksum nguồn trước/sau, lựa chọn, phiên bản và hash từng artifact. Toàn bộ `results/` được ignore; mã và README giữ trên nhánh `trang`, chưa commit/push.

## Cấu hình cố định

- **Naive:** tháng tới bằng tháng trước.
- **MA3:** trung bình ba tháng gần nhất.
- **Ridge:** StandardScaler + Ridge(alpha=1), lag1/lag2/lag3.

Ridge được fit lại trên lịch sử khả dụng của từng origin. Scaler và hệ số từng lần fit nằm ở `ridge_fit_audit.csv` của validation/test. Hai phương pháp quy tắc cập nhật theo lịch sử nhưng không học hệ số; không tạo biểu đồ loss/epoch giả cho chúng.

Lịch giữ nguyên: 15 tháng đầu 01/2012–03/2013; validation 04–09/2013; test 10–12/2013. Có 72 dự báo validation (24/phương pháp), 36 test (12/phương pháp). Chọn chung bằng pooled validation MAE, bằng điểm theo thứ tự METHODS đã khai báo. Các chỉ số khác dùng mô tả bổ sung.

`selection.json` được ghi trước khi hàm tính test được gọi. `execution_events.csv` cho thấy thứ tự đó; checksum lựa chọn không đổi qua test. Tuy nhiên test tham chiếu đã được biết trong repo và các lượt trước, nên đây **không phải thử nghiệm mù mới**. Kết quả của cả ba đối chứng test được trình bày sau khi đã chốt lựa chọn, không dùng để đổi lựa chọn.

## Cách đọc kết quả

- MAE/RMSE thấp hơn là tốt hơn. MAPE bỏ actual bằng 0; `MAPE_N` ghi số trường hợp được tính.
- `Error`/`Bias` = Prediction − Actual: dương dự báo cao, âm dự báo thấp.
- `MAE_ImprovementPct`/`RMSE_ImprovementPct` dương là giảm sai số so với Naive, âm là kém hơn. Không chỉ báo kết quả có lợi.
- Test chỉ ba tháng/Market; luôn đọc N, từng tháng và từng Market. Không gọi `100%−MAPE` là accuracy hoặc gán khoảng 95% khi chưa hiệu chuẩn.
- Actual 01/2014 để trống; đây là dự báo lịch sử ngoài nguồn, không phải dự báo hiện tại. Trạng thái MA3 lưu JSON, không cần file `.pth`.
- Thời gian `FitPredictSeconds` chỉ chẩn đoán cục bộ; không phải benchmark SQL hay phép so hiệu năng đã kiểm soát.
- Không ghi kho hoặc tự thay gói dashboard. Khi Chi bàn giao mart, đối chiếu 96 ô nguồn–kho trước khi đổi đầu vào nghiên cứu.

## Mã và kiểm tra

- `src/coffee_dw/baseline_study.py`: protocol, điều phối validation → lưu lựa chọn → test, bảng gốc và manifest.
- `src/coffee_dw/baseline_plots.py`: hình báo cáo.
- `src/coffee_dw/baseline_report.py`: nhận xét, HTML và kịch bản trình bày.
- Tái sử dụng `monthly_sales`, `predict_next`, `fit_ridge_model` và metric của `forecast.py`, không xây thuật toán khác rồi gán cùng tên.

```powershell
.\.venv\Scripts\python -m pytest tests/test_baseline_study.py
```

Kiểm tra khớp từng dự báo với reference, chống dùng actual tương lai, scaler chỉ từ lịch sử, chặn chọn bằng test, tệp lựa chọn có trước test, MAPE actual0, tháng thiếu và trạng thái dự báo tương lai.

## Kết quả lần chạy đã kiểm tra

- **27 bảng CSV, 12 bộ hình** (mỗi bộ PNG/PDF/SVG), báo cáo HTML, phân tích, gợi ý thuyết trình và manifest. Đã kiểm tra 70 tệp artifact, checksum từng tệp, link HTML và độ phân giải PNG 300 dpi; đã xem bộ hình và kiểm tra lại hình so metric test sau chỉnh bố cục.
- **45 test Python đạt**, gồm 7 test cho nghiên cứu cơ sở. Raw Coffee.csv không đổi; output kho và dashboard không bị ghi bởi lệnh nghiên cứu.
- Chọn MA3: MAE validation **223,28**, giảm **13,74%** so Naive; tốt nhất theo MAE ở 3/4 Market validation.
- Test MA3: MAE **225,22**, RMSE **265,41**, MAPE **2,40%**, N=12. MAE kém Naive **1,57%**, RMSE tốt hơn **6,97%**. Ridge có MAE test thấp nhất **213,33**, nhưng không đổi lựa chọn dựa vào test.
- Sai số MA3 lớn nhất tại West 11/2013: actual **11.300**, forecast **11.777,33**, lệch **477,33**. Bước sau nên dùng bộ này làm mốc cho thử tham số có kiểm soát; chưa dò tham số trong lượt này.
