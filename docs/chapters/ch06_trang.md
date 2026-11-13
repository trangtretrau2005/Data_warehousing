# Chương 6 — Dự báo doanh số theo thị trường

Người phụ trách: **Trang**. Mục tiêu là dự báo Sales tháng kế tiếp ở mức Market, có baseline và kỳ kiểm tra riêng.

- [ ] Tổng hợp một giá trị Market–tháng, kiểm tra đủ lịch liên tục; kỳ thiếu giữ là thiếu nếu chưa có bằng chứng bằng 0.
- [ ] Theo lịch chính của báo cáo: 15 tháng đầu khởi tạo, 04–09/2013 chọn phương pháp, 10–12/2013 kiểm tra.
- [ ] So kỳ trước, trung bình ba kỳ và Ridge(alpha=1) với ba lag; fit scaler và Ridge riêng trên quá khứ ở từng mốc.
- [ ] Dự báo một bước bằng cửa sổ mở rộng; mọi feature phải có sẵn trước tháng mục tiêu.
- [ ] Chọn theo MAE trên 24 dự báo validation của bốn thị trường; khóa lựa chọn trước khi xem 12 dự báo test.
- [ ] Lưu origin/target/Market/actual/prediction/method/split, MAE/RMSE theo nhóm và toàn bộ; MAPE chỉ khi actual khác 0.
- [ ] Huấn luyện lại trên lịch sử khả dụng để dự báo tháng 01/2014; ghi TrainEnd, kỳ phát hành và phiên bản phương pháp.
- [ ] TN12 bổ sung: tái lập ví dụ West, sáu kỳ 07–12/2013, feature lag1/lag2/mean3; ghi rõ đây là phép thử khác lịch chính.
- [ ] Vẽ actual/baseline/phương pháp chọn, nêu số kỳ đánh giá và giới hạn 24 tháng dữ liệu.

Tài liệu gốc chọn trung bình ba kỳ theo MAE validation, dù Ridge có MAE thấp hơn trên test. Không đổi phương pháp phục vụ sau khi xem test rồi gọi đó là đánh giá độc lập. Các số tham chiếu chỉ so được khi giữ nguyên split, feature, chuẩn hóa và cách tổng hợp sai số.

Điều kiện bàn giao: dự báo có phiên bản và mốc phát hành; không nối forecast vào fact chi tiết gây nhân dòng; chưa có actual 01/2014 để chấm sai số.
