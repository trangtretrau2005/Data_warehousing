# Thử siêu tham số — bước sau thí nghiệm cơ sở

Thử đầy đủ **7 cấu hình** đã chốt, giữ nguyên nguồn, lịch 15/6/3 và chọn bằng MAE validation. Kết quả ở đây là mở rộng thăm dò vì các tháng test đã được xem trong [bước cơ sở](../baseline/README.md). Không thay gói dữ liệu dashboard hoặc ghi kho.

```powershell
.\.venv\Scripts\python experiments/tuning/run.py
```

Môi trường như EDA/baseline: `python -m pip install -e ".[dev,explore]"` nếu chưa setup. Script chạy trực tiếp nguồn qua bộ chuẩn hóa dùng chung, chưa cần code/kho của Chi. Không sinh thêm doanh số giả.

| Nhóm | Siêu tham số thử | Tham số học |
| --- | --- | --- |
| Naive | Không có | Không học hệ số, dùng tháng trước |
| Trung bình trượt | `window=2,3,6` | Không học hệ số, trung bình các tháng gần nhất |
| Ridge | `alpha=0.1,1,10`; giữ lag1/2/3 | Ba hệ số, intercept; mean/scale của scaler |

Ridge dùng `StandardScaler + Ridge(solver="svd", fit_intercept=True)`, fit riêng quá khứ mỗi origin. Solver cố định để tái lập, không được dò. Có kiểm tra tương đương cấu hình alpha=1 với base ở sai số số học. Không có loss/epoch giả cho các phương pháp này.

## Mở kết quả

- [Báo cáo HTML](results/report.html): bảng số liệu, nhận xét và toàn bộ hình.
- [Phân tích Markdown](results/analysis.md), [quyết định](results/02_validation/decision.md), [gợi ý thuyết trình](results/presentation.md).
- [Một trang tóm tắt](results/06_summary/figures/01_summary.png): chèn báo cáo hoặc slide.
- [Danh sách cấu hình](results/01_protocol/configurations.csv), [xếp hạng validation](results/02_validation/leaderboard.csv), [toàn bộ metric](results/04_comparison/all_configurations.csv).
- [Chỉ mục mô hình](results/05_models/model_index.csv), [gói cấu hình chọn](results/05_models/selected_bundle.json), [hệ số cuối](results/05_models/final_coefficients_readable.csv).
- [Manifest](results/manifest.json): checksum nguồn/mã/artifact, phiên bản thư viện, số dự báo/lần fit.

Các link kết quả có sau khi chạy. Mỗi hình xuất PNG 300 dpi, PDF và SVG, cùng Times New Roman và palette của EDA. CSV giữ số chưa làm tròn.

## Cấu trúc đầu ra

| Thư mục | Kết quả |
| --- | --- |
| `01_protocol/` | Nguồn, kiểm tra, 7 cấu hình, protocol lưu trước đánh giá, mẫu học/scaler đầu |
| `02_validation/` | 168 dự báo, metric, xếp hạng, thông số 72 lần fit Ridge, lựa chọn đã lưu, độ nhạy |
| `03_test/` | 84 dự báo, metric, thông số 36 lần fit Ridge, sai số từng trường hợp |
| `04_comparison/` | So Naive và cấu hình chọn ở bước cơ sở; báo cả kết quả không cải thiện |
| `05_models/` | 12 pipeline Ridge fit cuối, 28 trạng thái JSON, 28 dự báo tương lai (4 được chọn), hệ số cuối |
| `06_summary/` | Tóm tắt, nhật ký thứ tự chạy và hình một trang |

Các pipeline cuối dùng 24 tháng lịch sử, còn 21 mẫu đủ lag mỗi Market. Tổng 120 lần fit Ridge; origin trung gian lưu hệ số/scaler trong CSV, chỉ 12 pipeline cuối lưu nhị phân. Naive/MA lưu quy tắc và lịch sử trong JSON, không cần `.pth`. Nạp lại pipeline vừa xuất để kiểm tra dự báo; phiên bản thư viện ghi trong manifest.

Kiểm tra độ nhạy bằng cách bỏ từng tháng khỏi **bảng chấm** validation, không fit lại hoặc dùng nó để đổi lựa chọn. Không gọi đó là sáu kiểm định độc lập. Các giá trị MAE fit là sai số trong mẫu học Ridge, không dùng lựa chọn hoặc xem là kết quả ngoài mẫu.

## Kiểm tra và giới hạn

```powershell
.\.venv\Scripts\python -m pytest tests/test_tuning_study.py
```

Kiểm tra đối chiếu base, chống rò rỉ actual tương lai, scaler/hệ số đúng quá khứ, chọn chỉ bằng validation, tệp lựa chọn có trước test, xuất/nạp lại mọi pipeline cuối, kỳ thiếu và độ nhạy. Không có random split.

Test chỉ ba tháng/Market và đã được biết. Không tuyên bố kiểm định mù mới, khoảng dự báo 95% hoặc `100%-MAPE` là accuracy. Actual 01/2014 giữ thiếu; Sales là đơn vị nguồn, không phải số đơn hàng và chưa xác định đơn vị tiền.

`results/` được ignore cục bộ, không thay quy tắc đưa output lên Git. Mã và hướng dẫn có thể đưa lên nhánh `trang` theo quy trình nhóm. Chưa nghiệm thu mart của Chi, TN12 West protocol riêng, native SQL/SSIS/SSAS, benchmark hoặc UX từ bộ này.

## Kết quả đã chạy và kiểm tra

- **MA3 vẫn được chọn**: MAE validation223,28, giảm13,74% so Naive, nhưng cải thiện0% so phương pháp chọn ở bước cơ sở. MA6 đạt231,31; Ridge tốt nhất nhóm là alpha10 với275,22.
- MA3 test: MAE225,22, RMSE265,41, MAPE2,40%, N=12; MAE kém Naive1,57%, RMSE tốt hơn6,97%. MA6 có MAE test thấp nhất152,00; không đổi lựa chọn theo test.
- **31 CSV, 14 bộ hình (42 tệp PNG/PDF/SVG), 12 pipeline Ridge, 28 trạng thái cấu hình**, báo cáo/nhận xét/lời thuyết trình và manifest. Đã kiểm tra checksum 122 artifact, link HTML/Markdown, PNG300dpi và nguồn bất biến; đã xem toàn bộ hình và chỉnh hai chú giải.
- **53 test Python đạt**, gồm 8 test mới cho vòng tuning. Chạy lại bằng lệnh trong README; các số này thuộc snapshot nguồn gốc đã ghi checksum, không suy ra mọi dữ liệu khác cũng chọn MA3.
