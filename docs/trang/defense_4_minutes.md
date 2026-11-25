# Kịch bản bảo vệ phần Trang trong bốn phút

Đây là kịch bản để diễn tập, **không phải bằng chứng đã có buổi bảo vệ**. Chỉ dùng câu về benchmark/UX khi đã có kết quả thật được duyệt. Người trình bày có thể rút ngắn lời đọc theo tốc độ nói của mình, ưu tiên thao tác và kết luận.

## Chuẩn bị trước khi bấm giờ

Mở dashboard cổng 8501, demo cổng 8502; chuẩn bị thêm [hình tóm tắt nghiên cứu](../../experiments/tuning/results/06_summary/figures/01_summary.png) và [hồ sơ West](../../experiments/briefing/results/02_story/cases/west_201401_moving_average_3.md). Đặt dashboard ở 01/2012–West; demo West–01/2014–MA3. Thử âm lượng trước, không phát toàn bộ ba đoạn audio trong khung bốn phút. Dùng phụ đề/lời nói trực tiếp nếu audio bị chặn.

| Thời gian | Thao tác | Nội dung nói |
| --- | --- | --- |
| 0:00–0:30 | Mở sơ đồ/giới thiệu dữ liệu | “Phần của em nối kho dữ liệu với phân tích và dự báo Sales theo tháng ở bốn thị trường. Nguồn có 4.248 dòng tổng hợp, không phải số đơn hàng; sau tổng hợp có 96 ô Market–tháng trong hai năm. Mọi số trên ứng dụng giữ nguyên đơn vị nguồn.” |
| 0:30–1:10 | Dashboard 01/2012: West → East → West | “KPI theo cùng bộ lọc. West có Sales 10.453, Budget 9.460, Gap +993; East có 6.780, 6.180, +600; quay lại West giữ đúng số. Tỷ lệ là chia hai tổng. Khi đi sâu State/Product và xuất CSV, kỳ và thị trường được giữ nguyên.” |
| 1:10–1:55 | Mở hình protocol và bảng validation | “Dự báo một tháng trước: 15 tháng khởi tạo, sáu tháng validation chọn phương pháp, ba tháng test báo cáo. Ridge fit scaler và hệ số chỉ trên quá khứ ở mỗi mốc. Em so ba phương pháp chuẩn và mở rộng thành bảy cấu hình. MA3 được chọn với MAE validation 223,28; Ridge alpha10 là tốt nhất nhóm Ridge nhưng chưa vượt MA3.” |
| 1:55–2:25 | Mở bảng test/hình tóm tắt | “Trên test, MA3 có MAE 225,22; MAE kém Naive 1,57% nhưng RMSE tốt hơn 6,97%. Vì vậy em không kết luận mô hình thắng mọi mặt. MA6 thấp nhất trên bảng test hồi cứu, nhưng không đổi lựa chọn theo test. Vòng mở rộng là thăm dò vì test đã được biết.” |
| 2:25–3:20 | Demo West–01/2014–MA3 → căn cứ tính toán → kiểm chứng | “Dự báo West là 11.593, bằng trung bình 11.596, 11.300 và 11.883 của ba tháng gần nhất. Hệ thống cho xem công thức và sáu kỳ validation để đọc sai số lịch sử, rồi tải báo cáo đúng bộ lọc. Đây là dự báo 01/2014 ngoài nguồn lịch sử, chưa có actual, không phải dự báo cho năm 2026. Thuyết minh bám dữ liệu, không tự suy nguyên nhân thời tiết hoặc khuyến mãi.” |
| 3:20–4:00 | Mở trang trạng thái bằng chứng | “Đã đối soát cả SQLite và mart SQL Server thử: 4.248 dòng, 11 số đo, 96 ô khớp; phát lại forecast không nhân dòng. Hiệu năng SQL, khả năng sử dụng và độ tốt dự báo là các đánh giá riêng. Chỉ số benchmark hoặc UX được báo khi có plan, log hay phiên người thật. Giới hạn chính là chỉ 24 tháng, test nhỏ và chưa có actual mới. Hiện em ưu tiên MA3 đơn giản, có truy vết, tiếp tục theo dõi khi có dữ liệu mới.” |

Nếu đã có kết quả native/UX thật, thay 15–20 giây cuối bằng **một** kết quả chính, kèm số mẫu và giới hạn. Không đọc toàn bộ bảng benchmark. Nếu một phần chưa đo, nói đúng trạng thái đang chờ và mở tài liệu bàn giao khi được hỏi.

## Câu hỏi thường gặp

**Vì sao dùng MA3 thay vì Ridge?** Vì tiêu chí chọn đã chốt là MAE validation; MA3 thấp nhất. Độ phức tạp không phải tiêu chí thắng.

**MA6 test tốt hơn, sao không chọn?** Chọn lại bằng test sẽ dùng tập đánh giá để ra quyết định. Có thể đề xuất MA6 cho thử nghiệm tiếp theo, cần kỳ mới kiểm tra.

**Có rò rỉ trong test khi dùng actual tháng trước thuộc test không?** Không, nếu actual đó đã xảy ra tại origin mới. Điều cần giữ là không dùng actual của chính tháng đích hoặc tương lai, và không đổi phương pháp theo lỗi test.

**Dự báo này có ra số lượng nguyên liệu không?** Chưa, Sales chưa có đơn vị tiền công bố và nguồn thiếu số ly, định mức, tồn an toàn, lead time. Cần dữ liệu và mục tiêu quyết định riêng.

**Có chứng minh web nhanh hơn Excel chưa?** Chỉ trả lời có nếu đã chạy protocol UX với người thật. AppTest hoặc thao tác agent không phải phiên người dùng.

**Số liệu nào do Trang thực hiện, phần nào của nhóm?** Trang phụ trách dự báo, ứng dụng, tích hợp/đối soát consumer và đánh giá. Kho/ETL/SSIS/SSAS có người chủ trì riêng; không nhận bằng chứng native chưa được bàn giao.
