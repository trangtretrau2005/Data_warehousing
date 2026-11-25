# Kết luận nghiên cứu và giới hạn bằng chứng

Ngày đối chiếu: **19/11/2026**. Nguồn các số dưới đây là bảng kết quả đã lưu; không phải số minh họa. [Bản CSV](research_findings.csv) dùng ghép bảng kết luận vào báo cáo.

| Câu hỏi | Kết luận được hỗ trợ | Bằng chứng | Chưa được kết luận |
| --- | --- | --- | --- |
| RQ1: Ridge tốt hơn Naive/MA3 không? | Trên validation 04–09/2013, MA3 tốt nhất: MAE 223,28 so Naive 258,83 và Ridge alpha1 292,93. MA3 được phục vụ. Trên test MA3 MAE kém Naive 1,57%, RMSE tốt hơn 6,97%. | [Bảng mọi cấu hình](../../experiments/tuning/results/04_comparison/all_configurations.csv), [quyết định](../../experiments/tuning/results/02_validation/decision.md) | Không khẳng định ML luôn tốt hơn baseline hoặc MA3 thắng mọi metric. |
| RQ2: Thử tham số có cải thiện không? | Bảy cấu hình không cải thiện lựa chọn validation so cơ sở: MA3 vẫn đứng đầu, cải thiện 0%. Ridge alpha10 tốt nhất nhóm Ridge, validation MAE 275,22. | [Leaderboard](../../experiments/tuning/results/02_validation/leaderboard.csv), [ma trận cấu hình](../../experiments/tuning/results/01_protocol/configurations.csv) | MA6 có test MAE 152,00 nhưng chưa đủ lý do đổi lựa chọn. Test đã xem, kết quả mở rộng mang tính thăm dò. |
| RQ3: Tích hợp có giữ đúng dữ liệu và cách dùng không? | Đã đối soát 96 ô nghiên cứu–SQLite và chuẩn bị 48 case demo. Ngày 19/11 đã đối soát native biệt lập 4.248 dòng/11 số đo/96 ô; publish/replay 112 forecast không trùng, bốn actual tương lai NULL. Đạt 12/12 ca agent kiểm trên browser, có CSV tải thật và ảnh. | [Native verification](../../results/trang_completion/native_serving/verification.json), [browser acceptance](../../results/trang_completion/browser/acceptance.json), [case checks](../../experiments/briefing/results/02_story/case_checks.csv) | Chưa suy ra SSIS/SSAS của Chi đã nghiệm thu, hiệu quả UX hoặc giọng đọc tự nhiên với người thật; người tham gia UX = 0. |
| RQ4: Cấu trúc truy vấn nào phù hợp? | Trên 2.124.000 dòng, indexed view giảm median đọc 898→3 ms nhưng tăng INSERT 10→29 ms; partition một tháng 107→27 ms, toàn kỳ 728→739 ms; NCI lát hẹp có seek 6 reads. HRU dùng 167/300 group-row phục vụ năm truy vấn nhỏ, MP fallback base không cải thiện. | [Summary 180 lượt chính](../../results/native_trang/20261119/benchmark_summary.csv), [HRU SQL](../../results/native_trang/20261119/hru/benchmark_summary.csv), [actual plans](../../results/native_trang/20261119/plans/), [môi trường](../../results/native_trang/20261119/environment.json) | Máy chung/Express, query MAXDOP 1 và memory grant 1%; 0 ms là sát độ phân giải; workload/budget HRU giả định, chưa đo refresh; không suy tốc độ sản xuất hoặc UX. |

## Giới hạn cần giữ trong bản báo cáo cuối

- Chỉ 24 tháng mỗi Market; test chính có 12 dự báo, ba mỗi Market. Các điểm thời gian có phụ thuộc, không xem như 12 quan sát độc lập để khẳng định mạnh.
- Test tham chiếu đã biết trước; mọi thử tham số bổ sung phải công bố là thăm dò và cần kỳ mới để đánh giá độc lập.
- Nguồn không có giá, thời tiết, khuyến mãi hay lịch phát hành ngân sách tương lai. Giải thích feature không phải giải thích nguyên nhân doanh số.
- Chỉ có dự báo điểm; MAE không phải khoảng dự báo đảm bảo, MAPE không đổi thành accuracy.
- Dự báo 01/2014 là kỳ ngoài snapshot lịch sử, không phải dự báo tại thời điểm hiện tại. Actual của kỳ đó chưa có trong CSV.
- Đối soát SQLite và AppTest không thay cho SQL Server/SSIS/SSAS, actual plan hoặc phiên người dùng Excel/web. Ghi riêng tình trạng từng tầng.

## Đóng góp có thể trình bày

Đóng góp của phần Trang là quy trình tái lập dự báo theo thời gian có baseline, thử tham số có kiểm soát, audit từng origin và phương án phục vụ kết quả có giải thích. Giá trị nằm ở tính đúng và khả năng truy vết từ dữ liệu kho đến quyết định chọn phương pháp. Không cần tuyên bố thuật toán mới hoặc kết quả vượt mọi đối chứng để mô tả đóng góp này.
