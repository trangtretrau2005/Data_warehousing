# Bước tiếp theo — từ nghiên cứu đến thuyết trình

Đưa quyết định của [vòng thử siêu tham số](../tuning/README.md) vào [demo đang có](../../apps/forecast_demo/README.md). Không huấn luyện thêm mô hình: nối dữ liệu đã kiểm chứng → cách tính → sai số → lời nói đúng bộ lọc.

```powershell
.\.venv\Scripts\python experiments/briefing/run.py --voice
```

Nếu chưa có kho/tuning, chạy `python -m coffee_dw.cli demo` và `python experiments/tuning/run.py` trước. Cần extra `voice,explore` như các bước trước; lần đầu chưa có model giọng dùng thêm `--download-voice`. Bỏ `--voice` để xuất đầy đủ bảng/hình/phụ đề nhưng không có WAV mới.

## Ba bước thực hiện

| Bước | Công việc | Kết quả đã lưu |
| --- | --- | --- |
| 1. Đối soát | Kiểm tra checksum artifact tuning, nguồn và từng ô kho–nghiên cứu | `01_reconciliation/monthly_reconciliation.csv`: 96 ô; hình bảng tổng hợp |
| 2. Dựng bài báo cáo | 48 case có lịch validation trước target; 16 case MA3 có ba tháng đầu vào, công thức trực tiếp và ba đoạn lời mới | `02_story/`: checks, inputs, validation, steps, 16 JSON/Markdown và 16 hình báo cáo |
| 3. Tích hợp demo | Lưu bảng xếp hạng bảy cấu hình; mặc định MA3; phát ba phần liên tục; mở actual có chủ đích; tải báo cáo theo filter | `03_research/`, `bundle_snapshot.json`, preview HTML và bundle đang phục vụ tại `results/forecast_demo/` |

Mỗi bộ hình có PNG300dpi/PDF/SVG, font Times New Roman. Hình báo cáo sinh từ số liệu, không phải ảnh nghiệm thu giao diện. Không dùng MAE/RMSE test của các tháng tương lai để thuyết minh như thông tin đã biết tại origin. Bảng `retrospective_test_metrics.csv` là đánh giá sau kỳ, tách khỏi lời đọc origin.

## Mở kết quả

- [Báo cáo toàn bộ](results/report.html), [phân tích từng bước](results/analysis.md).
- [Preview độc lập West–01/2014](results/preview_west_201401.html): chứa Plotly và audio đã nhúng nếu chạy có `--voice`; mở trực tiếp bằng trình duyệt.
- [Hình West–01/2014](results/02_story/figures/west_201401_moving_average_3.png), [hồ sơ và lời đọc](results/02_story/cases/west_201401_moving_average_3.md).
- [Toàn bộ lời theo từng bước](results/02_story/steps.csv), [kiểm tra 48 case](results/02_story/case_checks.csv).
- [Manifest](results/manifest.json), [chỉ mục âm thanh](results/audio_index.json).

Các link sinh sau khi chạy. Cache WAV được giữ theo hash nội dung tại `results/forecast_demo/audio/` để không nhân bản hàng trăm MB; `audio_index.json` ghi đường dẫn, thời lượng và checksum từng tham chiếu. Preview HTML đã nhúng ba WAV của case mặc định nên tự mở được. Bundle đang phục vụ trước lần tích hợp đầu tiên được lưu tại `00_previous_bundle.json` nếu tồn tại.

Chạy ứng dụng:

```powershell
.\.venv\Scripts\python -m streamlit run apps/forecast_demo/app.py --server.port 8502
```

Mặc định West–01/2014–MA3. Bấm nghe để xem biểu đồ chuyển phần. Chọn 10/2013 và mở actual để kiểm chứng một kỳ có kết quả thật. Khi đổi phương pháp, đối chứng được ghi nhãn rõ; Ridge giữ waterfall cộng tính, MA3 dùng ba cột và đường trung bình.

## Kiểm tra và giới hạn

```powershell
.\.venv\Scripts\python -m pytest
node --test tests/test_presenter_frontend.js
```

Kiểm tra chống dữ liệu tương lai, checksum nghiên cứu, sai khác kho–nguồn, công thức MA3, gói hỏng, bộ lọc West→East→West, xuất hồ sơ và thao tác component trong Node VM. Chưa thay bằng chứng UX, native SQL Server/SSIS/SSAS hoặc đánh giá chủ quan giọng nói.

Lượt chạy đã kiểm tra: **61 test Python, 10 test JavaScript đạt**. Đã xuất **99 artifact** (chưa tính manifest), gồm 7 CSV, 16 hồ sơ JSON/Markdown, 18 bộ hình PNG/PDF/SVG, bundle snapshot, báo cáo và preview. Đủ 144 tham chiếu âm thanh/121 WAV riêng; WAV mono16bit có tín hiệu, mỗi đoạn khoảng22–34giây. AppTest trên bundle/audio thật mặc định West–01/2014–MA3 không có exception/warning. Xem log JUnit và `qa_v3.json` tại `results/forecast_demo/`.

Sau khi chạy có thể kiểm tra lại checksum/link/hình/WAV và AppTest bằng `python experiments/briefing/verify.py`; kết quả QA lưu tại `results/forecast_demo/qa_v3.json` để không tự thay checksum artifact trong manifest.

Công cụ browser host chưa khả dụng trong lượt tích hợp này. Trạng thái đó được ghi trong manifest; không đánh dấu đã nghe/nhìn qua browser thật. Bước sau là Trang chạy thử giọng/bố cục và lưu phiên nghiệm thu, rồi đối soát mart native của Chi khi bàn giao. Không tạo thêm doanh số giả, không sửa nguồn, không commit/push hoặc thay `main` từ script này. `results/` vẫn được ignore theo quy tắc nhóm.
