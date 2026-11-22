# Chương 6 — Dự báo doanh số theo thị trường

Người phụ trách: **Trang**. Mục tiêu là dự báo Sales tháng kế tiếp ở mức Market, có baseline và kỳ kiểm tra riêng.

**Trạng thái mới ngày19/11/2026:** toàn bộ mục dự báo Python trong checklist đã có bằng chứng, gồm TN12 West riêng. [Bản chương6 để ghép báo cáo](../trang/chapter06_forecasting.md) và [native serving](../../results/trang_completion/native_serving/verification.json) đối soát4248 dòng/11 số đo/96 ô, phát hành112 forecast không trùng. Kết quả native là môi trường biệt lập của Trang, không thay nghiệm thu SSIS/SSAS hoặc bàn giao chính thức của Chi. Các đoạn ngày16/11 bên dưới là nhật ký lịch sử.

- [x] Tổng hợp một giá trị Market–tháng, kiểm tra đủ lịch liên tục; kỳ thiếu giữ là thiếu nếu chưa có bằng chứng bằng 0. Đã kiểm tra trên nguồn CSV bằng EDA; đối soát mart của Chi còn chờ bàn giao.
- [x] Theo lịch chính của báo cáo: 15 tháng đầu khởi tạo, 04–09/2013 chọn phương pháp, 10–12/2013 kiểm tra. Đã tái lập trên nguồn CSV tại `experiments/baseline/`.
- [x] So kỳ trước, trung bình ba kỳ và Ridge(alpha=1) với ba lag; fit scaler và Ridge riêng trên quá khứ ở từng mốc. Có audit thông số từng origin.
- [x] Dự báo một bước bằng cửa sổ mở rộng; mọi feature phải có sẵn trước tháng mục tiêu. Có origin schedule và test thay actual tương lai.
- [x] Chọn theo MAE trên 24 dự báo validation của bốn thị trường; lưu lựa chọn trước pha tính 12 dự báo test trong lượt tái lập. Test tham chiếu đã biết trước, không gọi đây là thử nghiệm mù mới.
- [x] Lưu origin/target/Market/actual/prediction/method/split, MAE/RMSE theo nhóm và toàn bộ; MAPE chỉ khi actual khác 0.
- [x] Cập nhật phương pháp chọn trên lịch sử khả dụng để dự báo tháng 01/2014; ghi TrainEnd, kỳ phát hành và phiên bản. MA3 dùng quy tắc trung bình, không có bước học hệ số; Actual tương lai giữ thiếu.
- [x] TN12 bổ sung: tái lập ví dụ West, sáu kỳ 07–12/2013, feature lag1/lag2/mean3; ghi rõ đây là phép thử khác lịch chính. Đã chạy ngày 19/11/2026, khớp đoạn Python sổ tay; [mã, bảng/hình và kiểm tra](../../experiments/tn12_west/README.md).
- [x] Vẽ actual/baseline/phương pháp chọn, nêu số kỳ đánh giá và giới hạn 24 tháng dữ liệu. Có hình PNG/PDF/SVG và nhận xét cả mặt chưa cải thiện.

Tài liệu gốc chọn trung bình ba kỳ theo MAE validation, dù Ridge có MAE thấp hơn trên test. Không đổi phương pháp phục vụ sau khi xem test rồi gọi đó là đánh giá độc lập. Các số tham chiếu chỉ so được khi giữ nguyên split, feature, chuẩn hóa và cách tổng hợp sai số.

Điều kiện bàn giao: dự báo có phiên bản và mốc phát hành; không nối forecast vào fact chi tiết gây nhân dòng; chưa có actual 01/2014 để chấm sai số.

## Prototype thuyết minh — cập nhật 16/11/2026

> Cập nhật sau phản hồi19/11: [review11 cấu hình](../../experiments/forecast_review/README.md) đã thêm SES/mùa vụ nhưng không vượt MA3 trên validation, không đổi gói phục vụ. [Bộ hình đối chiếu mới](../../results/trang_forecast_review/report.html) làm rõ36 điểm MA3 gồm24 validation/12test và từng lỗi có dấu; [FAQ bảo vệ](../trang/forecast_questions.md) giải thích horizon, actual, khoảng bất định và dữ liệu synthetic. Dashboard AI có khoảng target riêng, chọn tháng và hiển thị Prediction/Actual/Error/APE; CSV theo đúng khoảng đang xem. Đây là cải thiện khả năng đọc và thăm dò có công bố, không tăng số kỳ test hoặc sửa dữ liệu cho khớp đường dự báo.

`apps/forecast_demo/` bổ sung bối cảnh ngân sách, Profit và cơ cấu sản phẩm tại thời điểm phát hành, giải thích cộng tính và nhận định có điều kiện dựa trên MAE lịch sử. Không sinh thêm doanh số để huấn luyện. Đã có kiểm tra 48 trường hợp, đối soát KPI và không đọc dữ liệu tương lai; xem cách tái lập và giới hạn tại [README demo](../../apps/forecast_demo/README.md). Đây là prototype, chưa thay cho hoàn thiện nghiên cứu/TN12 hoặc lựa chọn mô hình mới.

## EDA nguồn — 16/11/2026

Chạy `python explore/run.py`, xem [explore/README](../../explore/README.md). Đã có bảng hồ sơ/chất lượng/tiền xử lý và thống kê, hình PNG/PDF/SVG, phân tích tiếng Việt. Tách `train_design` 15 tháng đầu và `full_history_descriptive` toàn kỳ. Dữ liệu nguồn được giữ nguyên; EDA chạy độc lập với kho/ETL của Chi. Chưa đánh dấu R02/R03 bàn giao kho hoặc R07–R10 huấn luyện/lựa chọn mới hoàn tất từ bước này.

## Tái lập thực nghiệm cơ sở — sau EDA

Chạy `python experiments/baseline/run.py`; xem [hướng dẫn và kết quả](../../experiments/baseline/README.md). Đã có ba phương pháp cố định, 72 prediction validation, 36 prediction test, bốn dự báo tương lai, lựa chọn MA3 lưu trước pha test, bảng/hình cho sáu bước và gợi ý thuyết trình. MAE validation 223,28; MAE test 225,22. So Naive, MAE test kém 1,57% nhưng RMSE tốt hơn 6,97%; không tuyên bố thắng mọi metric. Chưa có tuning mới, TN12 protocol West riêng, bàn giao mart của Chi hoặc kiểm định mù mới.

## R08 — thử siêu tham số sau bước cơ sở

- [x] Thử đủ lưới đã chốt: Naive; MA window=2/3/6; Ridge alpha=0.1/1/10, giữ lag1/2/3. [Mã chạy và hướng dẫn](../../experiments/tuning/README.md).
- [x] Lưu protocol/cấu hình trước chấm, 168 dự báo validation, 84 test; 72/36 lần fit Ridge tương ứng, hệ số và scaler từng origin; chọn bằng MAE validation và ghi lựa chọn trước pha test.
- [x] Fit cuối 12 pipeline Ridge trên lịch sử 24 tháng, 21 mẫu học/Market; xuất/nạp lại kiểm tra pipeline, 28 trạng thái JSON cho mọi cấu hình, gói chọn và bốn dự báo được chọn cho 01/2014. Actual tương lai giữ thiếu.
- [x] Có 31 bảng CSV, 14 bộ hình PNG300dpi/PDF/SVG, báo cáo HTML/Markdown, lời thuyết trình và manifest; 53 kiểm tra Python đạt, gồm 8 kiểm tra mới cho tuning. Kiểm tra checksum 122 artifact, link và độ phân giải; đã xem hình và chỉnh chú giải MA/Ridge.

MA3 vẫn đứng đầu validation (223,28), cải thiện **0%** so cấu hình chọn ở bước cơ sở; MA6 là đối chứng gần nhất (231,31). Ridge alpha=10 tốt nhất nhóm Ridge (275,22), chưa vượt MA3. MA6 có MAE test thấp nhất (152,00), nhưng không đổi lựa chọn theo test. MA3 test vẫn MAE225,22/RMSE265,41/MAPE2,40%, N=12. Đây là mở rộng thăm dò sau khi test đã được xem, không phải đánh giá mù mới hoặc TN12 West riêng. Bàn giao mart của Chi/native/UX vẫn chờ; chưa thay gói dashboard từ bộ nghiên cứu này.

## Tích hợp kết quả vào thuyết trình — sau R08

[Bước briefing](../../experiments/briefing/README.md) đã đối soát96 ô giữa nghiên cứu và kho SQLite, gắn bằng chứng7 cấu hình vào48 case demo, tạo16 hồ sơ MA3 với công thức trung bình trực tiếp và6 kỳ validation có trước target. Đã lưu99 artifact gồm18 bộ hình PNG/PDF/SVG,7 CSV,hồ sơ/lời đọc,preview và snapshot;144 tham chiếu âm thanh/121 WAV. Đây là phục vụ kết quả đã chốt, không huấn luyện/chọn mô hình mới. MAE trên giao diện gắn nhãn validation; không dùng test tương lai trong lời đọc origin. Chưa nghiệm thu mart native của Chi hoặc TN12 West riêng.
