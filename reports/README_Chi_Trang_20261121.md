# Bàn giao báo cáo Chi và Trang ngày 21 tháng 11 năm 2026

## Tài liệu

`Bao_cao_Chi_Trang_Coffee_DW_20261121.docx` là bản báo cáo Word cho chương 4–7. Nội dung theo phần Chi chủ trì ETL và OLAP, cùng phần Trang chủ trì dự báo, dashboard, benchmark và nghiệm thu. Báo cáo dùng Times New Roman 13, khổ A4 và lề theo báo cáo nhóm hiện có. Số trang được kiểm bằng Microsoft Word trên máy này; mục lục, số chương, chú thích hình/bảng và số trang là trường Word thật.

Bản chốt: **25 trang, 16 hình và 23 bảng**, gồm phần mở đầu, mục lục, chương 4–7, kết luận với câu hỏi bảo vệ và phụ lục nguồn.

Ảnh gốc trong `results/` được giữ nguyên. Thư mục `assets_chi_trang_20261121/` chứa ảnh cắt phóng to, sơ đồ nhóm tự vẽ và biểu đồ tái lập từ số liệu đã lưu; các manifest ghi nguồn, phép cắt, kích thước và checksum. Báo cáo có một biểu đồ Word chỉnh sửa được kèm workbook nhúng và ba công thức Word native.

## Đọc và giải thích

- Chương 4: hợp đồng nguồn, SSIS, nạp tăng dần, phát lại, sửa số, reject, rollback và SCD mô phỏng.
- Chương 5: mart, lỗi nhân bản khi nối, SSAS đọc trực tiếp mô hình sao, KPI và các thao tác OLAP.
- Chương 6: split 15–6–3, chọn phương pháp bằng validation, so dự báo với actual, ví dụ 11/2013, kỳ 01/2014 chưa có actual, giới hạn dữ liệu và TN12 West riêng.
- Chương 7: tích hợp, benchmark native, HRU, nghiệm thu kỹ thuật và giới hạn triển khai.
- Kết luận có bảng câu hỏi và cách giải thích khi bảo vệ; phụ lục giải nghĩa mã minh chứng M1–M7 và dẫn tài liệu gốc T1–T5.

Không diễn giải 4.248 dòng thành đơn hàng; không cộng Inventory xuyên thời gian; không lấy BudgetSales làm dự báo. MA3 được giữ theo validation dù Ridge có MAE test thấp hơn. Dữ liệu nhân 500 lần chỉ phục vụ benchmark, không được tính là lịch sử dự báo mới. UX người thật vẫn là 0 người/0 lượt; SSAS Build có 8 cảnh báo được công bố. Các số liệu này phản ánh minh chứng đã lưu ngày 19–20/11/2026, không phải một đợt chạy mới trong lúc viết báo cáo.

## Tái lập bản Word từ đầu vào đã lưu

Thực hiện ở root repo, dùng Python từ workspace dependency runtime của Codex đã được xác nhận trong phiên làm việc. Không dùng Python hệ thống hoặc thay package của dự án để dựng tài liệu.

```powershell
$artifactPython = 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1119-907-0_26.1119.907.0_x64__3k8sg7r9htsxt/dependencies/python/python.exe'
& $artifactPython '.work/report_20261121/build_report.py'
& $artifactPython '.work/report_20261121/render_word.py' 'reports/Bao_cao_Chi_Trang_Coffee_DW_20261121.docx' --output '.work/report_20261121/render_delivery' --dpi 140
& $artifactPython '.work/report_20261121/final_checks.py'
```

Đầu vào gồm hai bản thảo `chi_content.md`, `trang_content.md`, các JSON facts trong `.work/report_20261121/`, tài sản trong `reports/assets_chi_trang_20261121/` và minh chứng `results/`. Trình render mở một phiên Microsoft Word riêng, gắn outline native, cập nhật trường và mục lục, xuất PDF rồi rasterize bằng Poppler để soát trang. Không thay đổi tài liệu Word khác đang mở.

Trình render chuẩn của skill đã được thử nhưng máy không có `soffice.exe`; log nằm ở `.work/report_20261121/canonical_renderer.log`. Bản bàn giao được kiểm bằng Word native trên chính máy dùng mở tài liệu. PDF/PNG render là tài sản QA nội bộ.

## Kiểm tra và giới hạn bàn giao

Kết quả cấu trúc, SHA-256 của DOCX và hash nguồn nằm ở `.work/report_20261121/final_checks.json`; đối chiếu số liệu độc lập nằm ở `.work/report_20261121/fact_audit.json`. Biên bản soát toàn bộ trang nằm ở `.work/report_20261121/visual_qa.json`.

Lần làm này chỉ tạo báo cáo và tài sản hình liên quan, không chỉnh logic nguồn, ETL hay forecast; không nạp lại database, không chạy benchmark ghi dữ liệu, không commit/push/merge và không thay đổi `main`. Không chạy lại toàn bộ test phần mềm vì không đổi mã ứng dụng; báo cáo ghi rõ mốc test có bằng chứng trong snapshot.

Khi ghép với chương 1–3 hoặc thay nội dung, cần cập nhật toàn bộ trường trong Word và kiểm lại phân trang. Muốn công bố UX người thật, kiểm định dự báo trên kỳ mới hoặc nghiệm thu bản Git cố định phải bổ sung đúng phiên thực nghiệm tương ứng trước khi đổi kết luận trong báo cáo.
