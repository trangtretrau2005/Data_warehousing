# Demo dự báo có giải thích và người thuyết minh

Demo nối kết quả nghiên cứu với bài thuyết trình theo bộ lọc. Chọn4 Market,4 kỳ mục tiêu10/2013–01/2014 và3 phương pháp có trong base. Có48 trường hợp được tính từ kho tham chiếu; mặc định West–01/2014–MA3 đã chọn bằng validation. Nhân vật An là minh họa SVG, giọng nói là TTS Piper tiếng Việt. Không dùng LLM để tự nghĩ nguyên nhân.

Từ root:

```powershell
.\.venv\Scripts\python -m coffee_dw.cli demo
.\.venv\Scripts\python -m pip install -e ".[voice,explore]"
.\.venv\Scripts\python experiments/tuning/run.py
.\.venv\Scripts\python experiments/briefing/run.py --voice --download-voice
.\.venv\Scripts\python -m streamlit run apps/forecast_demo/app.py --server.port 8502
```

Mở `http://localhost:8502`. Lần đầu tải model giọng Việt công khai khoảng63MB và tạo WAV; lần sau dùng cache. Chỉ cần `--download-voice` khi chưa có model. Chuẩn bị không có âm thanh bằng `python experiments/briefing/run.py`; giao diện vẫn có đầy đủ nội dung và biểu đồ. Script cũ `scripts/prepare_forecast_demo.py` vẫn tạo demo cơ sở ba phương pháp; dùng script briefing để có bằng chứng bảy cấu hình và luồng giải thích mới.

Nếu sau khi cập nhật code gặp `ImportError: cannot import name 'report_fingerprint'`, kiểm tra bằng `.\.venv\Scripts\python -c "from coffee_dw.demo import report_fingerprint; print('OK')"`. Khi import mới thành công nhưng trang vẫn báo lỗi, dừng tiến trình Streamlit cũ bằng Ctrl+C tại terminal đang chạy và chạy lại lệnh Streamlit ở trên. Tải lại trang chỉ chạy lại script trong cùng tiến trình; không bảo đảm làm mới module Python đang được giữ trong bộ nhớ. Không cần tạo lại dữ liệu hoặc cài lại thư viện cho trường hợp này.

## Thử những gì

1. Mặc định West,01/2014,MA3: bấm **Bắt đầu thuyết minh**. Ba đoạn chuyển theo sự kiện kết thúc âm thanh, không theo thời gian chờ giả định.
2. Chuyển **Căn cứ tính toán**: ba cột là Sales ba tháng gần nhất, đường ngang là trung bình, công thức hiển thị ngay dưới biểu đồ. Với Ridge đối chứng, giữ waterfall mức nền + đóng góp = dự báo.
3. Phần **Kiểm chứng & theo dõi** so thực tế–dự báo của sáu kỳ validation tại cùng Market, kèm MAE. Không dùng số thực tế tháng đích trong lời đọc.
4. Bảng nghiên cứu bên dưới hiện bảy cấu hình và lựa chọn theo MAE validation toàn chuỗi. Đối chứng được ghi nhãn khi chọn; không đổi phương pháp theo test.
5. Chọn10/2013 và bấm mở actual để đối chiếu kỳ có kết quả. Chọn01/2014 thì actual chưa có, nút mở bị khóa; không thay bằng0 hoặc chấm sai số tương lai.
6. Tải báo cáo Markdown và bảng validation đúng bộ lọc. [Kết quả bước tích hợp](../../experiments/briefing/README.md) có 16 hồ sơ MA3 và hình PNG/PDF/SVG để đưa vào báo cáo.

Phần giải thích nói mô hình sử dụng ba tháng trước thế nào so với mức nền từ train; không kết luận do khuyến mãi, thời tiết, giá bán hay hành vi khách hàng. Các lag có tương quan nên đóng góp phụ thuộc mô hình và mức tham chiếu.

## Bản sửa theo phản hồi ngày 16/11/2026

Lượt tích hợp sau tuning: MA3 làm mặc định, ba tháng/công thức thay waterfall cho MA3; sáu kỳ actual–forecast validation thay phần chất lượng rời rạc; hiển thị bảy cấu hình và tải báo cáo đúng filter. Có16 hồ sơ MA3,18 bộ hình và preview độc lập tại [bước briefing](../../experiments/briefing/README.md). Đã đối soát96 ô kho–nghiên cứu, 61 test Python/10 test JavaScript đạt; bundle thật chạy AppTest không có exception/warning. Có144 tham chiếu âm thanh/121 WAV, kiểm tra định dạng/tín hiệu. Browser host chưa khả dụng nên chưa kết luận đã nghiệm thu nhìn/nghe.

- Giao diện nền sáng xanh navy–trắng, chữ Times New Roman 18–21px, tiêu đề 27–43px; khóa màu chữ/ô chọn/KPI để không bị theme tối của Streamlit làm trắng chữ.
- Báo cáo có nhận định chung ở đầu và nền kinh doanh luôn hiển thị: doanh số, ngân sách, Profit, tỷ suất, sáu tháng Sales/Budget và top 5 sản phẩm tháng đã biết. Chỉ dùng dữ liệu trước kỳ dự báo; không lấy ngân sách hay Profit tương lai để diễn giải.
- Kết luận so độ lớn biến động với MAE lịch sử và nêu việc cần rà soát. Đây là quy tắc gợi ý thận trọng, không phải xác suất tin cậy hoặc khuyến nghị mua hàng/nhân sự tự động. Nguồn chưa có dữ liệu đơn hàng/định mức nguyên liệu để tính những quyết định đó.
- Lời đọc nối bối cảnh → kết quả dự kiến → cơ chế → sai số → điều kiện hành động. Số và ngày tháng được viết thành chữ tiếng Việt trước khi tổng hợp. Piper dùng length_scale 1,18 thay 0,94; nghỉ 0,42 giây sau câu và thêm 0,40 giây cuối đoạn. Người nghe có thể chọn tốc độ 0,9×/1×/1,1×.
- Cache audio đổi phiên bản để không phát lại giọng cũ. Công cụ tạo bundle chỉ công bố gói sau khi hoàn tất âm thanh; JSON thay thế nguyên tử để tránh đọc tệp đang ghi. TTS vẫn là cùng giọng Piper; thay đổi ngắt nghỉ không đồng nghĩa đã có cảm xúc như người thật.

Công cụ trình duyệt ở lượt sửa này trả `The browser access host is unavailable`. AppTest/Node VM và kiểm tra WAV chỉ xác nhận logic, số liệu và cấu trúc âm thanh; chưa thay cho nghiệm thu nhìn/nghe bằng trình duyệt thật.

Kết quả kiểm tra bản 02: **33 test Python, 8 test JavaScript đạt**; AppTest với bundle âm thanh thật chạy không có exception/cảnh báo. Đủ 144 tham chiếu âm thanh cho 48 trường hợp, cache thành 123 WAV; mỗi đoạn khoảng 22–34 giây. Mặc định West–10/2013–Ridge có ba đoạn khoảng 31/33/30 giây ở tốc độ 1×. Kiểm tra tệp WAV có tín hiệu và đúng định dạng; chưa đánh giá chủ quan độ tự nhiên. Số đối soát cục bộ lưu trong `results/forecast_demo/qa_v2.json` (được ignore).

Fingerprint mới kiểm tra cả BudgetSales, Profit và ProductName dùng trong báo cáo, bên cạnh chuỗi Sales dự báo; thay ngân sách mà giữ nguyên Sales cũng yêu cầu tạo lại gói. Tỷ lệ ngân sách dùng SUM(Sales)/SUM(BudgetSales) cùng kỳ/thị trường, không lấy trung bình tỷ lệ dòng.

## Dữ liệu mới gồm gì

| Tệp trong results/forecast_demo | Nguồn tạo |
| --- | --- |
| bundle.json | Snapshot kho, forecast, giải thích, metadata và lời thuyết minh |
| case_summary.csv |48 dự báo và actual có sẵn, mức nền, sai lệch tái dựng |
| contributions.csv |144 đóng góp theo feature, giá trị lag và tham chiếu |
| validation_metrics.csv | Ba phương pháp trên24 dự báo validation toàn chuỗi |
| narration.csv |144 đoạn lời theo mẫu, mỗi đoạn bám số liệu của một case |
| audio/*.wav | Piper tổng hợp từ các đoạn lời, cache theo hash nội dung |

Không sinh thêm doanh số hoặc sản phẩm giả, không sửa Coffee.csv.48 case chỉ là kết quả dẫn xuất từ96 ô Market–tháng của nguồn. Dataset/giọng đọc sinh ra bị ignore; model tải về ở data/models/piper cũng bị ignore. Mã và trọng số giọng Piper là thành phần bên thứ ba, ghi nguồn trong bundle và MODEL_CARD.txt; không nhận là mô hình tự huấn luyện của nhóm.

App kiểm tra fingerprint của dữ liệu tháng trong kho với bundle. Nếu ETL làm thay đổi dữ liệu thì phải chạy lại prepare; không phát lời cũ trên biểu đồ mới. Pipeline demo chưa tự publish forecast sang SQL Server, không thay bằng chứng native hoặc UX.

## Kiểm tra

```powershell
.\.venv\Scripts\python -m pytest
node --test tests/test_presenter_frontend.js
```

Tests kiểm tra48 case, tính cộng được, không dùng dữ liệu tương lai, thiếu tháng, lịch sử hằng, bundle lỗi và trạng thái giao diện. Kiểm tra nghe/nhìn trình duyệt là phần QA bổ sung. Không có bảo đảm tuyệt đối không lỗi; trình duyệt chặn phát âm thanh thì bấm phát lại và vẫn có phụ đề.

Lượt chuẩn bị ngày15/11/2026:26 kiểm tra Python và6 kiểm tra logic component JavaScript đã đạt;48 case có144 tham chiếu audio, tương ứng120 WAV khác nhau nhờ cache. Đã kiểm tra file WAV có thời lượng và tín hiệu khác0. Kiểm tra JavaScript chạy trong Node VM, không thay cho kiểm tra trực quan trong trình duyệt; công cụ UI chưa có quyền truy cập Chrome ở lượt này.

Trên Windows có đường dẫn dự án tiếng Việt, espeak-ng cần tài nguyên phonemizer ở đường dẫn ASCII. Helper sao chép riêng tài nguyên đóng gói của Piper vào user TEMP khi cần; model và kết quả vẫn nằm trong dự án.

Nguồn: [Piper](https://github.com/OHF-Voice/piper1-gpl), [giọng vais1000](https://huggingface.co/rhasspy/piper-voices/tree/main/vi/vi_VN/vais1000/medium), [Piper Python API](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md).

Piper engine có license GPL-3.0; model card của giọng vais1000 ghi dataset VAIS1000, license CC BY4.0. Trọng số và model card được tải về riêng để giữ nguồn/ghi nhận thành phần bên thứ ba.
