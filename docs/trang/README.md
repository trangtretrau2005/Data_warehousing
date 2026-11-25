# Hồ sơ bàn giao phần Trang — chương 6 và 7

Cập nhật ngày **19/11/2026**. Đây là bộ nội dung Markdown để ghép báo cáo nhóm; không ghi đè hai tài liệu Word gốc. Các mục có số đo dẫn đến tệp kết quả thực, các mục chờ giữ nguyên trạng thái chờ. Số hình/bảng trong bản Word cuối do nhóm chốt khi ghép.

| Tệp | Mục đích |
| --- | --- |
| [Chương 6](chapter06_forecasting.md) | Bài toán, dữ liệu, protocol, mô hình, kết quả, phân tích lỗi và giới hạn |
| [Chương 7](chapter07_deployment.md) | Kiến trúc phục vụ, quy tắc KPI, nghiệm thu, benchmark và giới hạn triển khai |
| [Kết luận theo câu hỏi nghiên cứu](research_findings.md) | Trả lời RQ1–RQ4 và chỉ rõ bằng chứng hỗ trợ |
| [Protocol và phiếu UX](ux_protocol.md) | Tác vụ Excel/web, đổi thứ tự, cách chấm và ghi số đo thật |
| [Kịch bản bảo vệ 4 phút](defense_4_minutes.md) | Thứ tự thao tác, lời nói và phương án khi demo gặp lỗi |
| [Tái lập và bàn giao](reproduction_handoff.md) | Các lệnh, hợp đồng đầu vào/đầu ra và bước chốt Git |
| [Nhật ký thực hiện](worklog_20261119.md) | File, lệnh, kết quả kiểm tra và giới hạn của bộ báo cáo/nghiệm thu |
| [Câu hỏi về dự báo và dữ liệu sinh thêm](forecast_questions.md) | Actual/sai lệch từng tháng, khoảng xem so với horizon, chất lượng mô hình và cách trả lời bảo vệ |
| [Linear Regression Marketing–Sales](linear_marketing.md) | Dữ liệu, split thời gian, metric, kết quả bốn Market, giao diện what-if và quyết định chưa gộp forecast |

## Mở tài sản đã có

- [EDA](../../explore/README.md), [thực nghiệm cơ sở](../../experiments/baseline/README.md), [thử bảy cấu hình](../../experiments/tuning/README.md), [tích hợp thuyết trình](../../experiments/briefing/README.md).
- Kết quả cục bộ sau khi chạy: [bảng xếp hạng validation](../../experiments/tuning/results/02_validation/leaderboard.csv), [bảng so sánh toàn bộ](../../experiments/tuning/results/04_comparison/all_configurations.csv), [sai số test theo thị trường](../../experiments/baseline/results/04_test/selected_metrics.csv), [đối soát SQLite–nghiên cứu](../../experiments/briefing/results/01_reconciliation/monthly_reconciliation.csv).
- Bộ UX sinh bằng `python scripts/prepare_trang_acceptance.py`: [đáp án cho người điều phối](../../results/trang_acceptance/answer_key.json), [đầu vào Excel](../../results/trang_acceptance/excel_input.csv), [phiếu trống](../../results/trang_acceptance/ux_trials.csv), [manifest](../../results/trang_acceptance/manifest.json).

Các liên kết vào thư mục `results/` chỉ có sau khi tái lập; chúng được ignore theo chính sách repo. Người nhận cần chạy lệnh trước khi mở các liên kết kết quả. Không đưa toàn bộ output, âm thanh, model hay database vào Git.

Tạo bản HTML in được, gồm hai chương, sáu hình kết quả và kết luận nghiên cứu:

```powershell
.\.venv\Scripts\python scripts/build_trang_report.py
```

Mở [báo cáo HTML](../../results/trang_completion/report_trang.html), dùng nút in nếu cần. Nội dung lấy từ Markdown, không thay tài liệu Word gốc. Bản này không được gọi là DOCX đã render/nghiệm thu.

Sau lượt rà dự báo, hình chính chương6 dùng [bộ đối chiếu rõ actual/sai lệch](../../results/trang_forecast_review/report.html). Nếu dựng lại từ đầu, chạy `python experiments/forecast_review/run.py` rồi `python scripts/render_forecast_review.py` trước builder báo cáo. Đợt mở rộng11 cấu hình không thay MA3; xem [protocol và kết quả](../../experiments/forecast_review/README.md).

## Ranh giới nghiệm thu

Nghiên cứu dự báo, đối soát SQLite, kiểm thử tự động, kiểm tra UI bằng agent và thử người dùng là các loại bằng chứng khác nhau. Chỉ một phiên có người tham gia thực mới được điền vào phiếu UX. Nội dung benchmark chưa có raw runs/actual plans phải ghi **chưa đo**, không dùng thời gian Python hoặc SQLite thay số SQL Server. Trạng thái theo từng tiêu chí được quản lý tại [checklist chương 6](../chapters/ch06_trang.md) và [chương 7](../chapters/ch07_trang.md).
