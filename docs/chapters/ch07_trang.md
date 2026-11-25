# Chương 7 — Triển khai và đánh giá hệ thống

Người phụ trách: **Trang**. Chương này tích hợp ứng dụng và thu bằng chứng thực nghiệm trên môi trường triển khai.

- [x] Dashboard gồm tổng quan KPI, drill-down State/Product, Marketing/chi phí, tồn kho kỳ chọn, dự báo và kết quả thực nghiệm. Có backend SQLite/SQL Server; trang kết quả đọc artifact đã tính sẵn.
- [x] Bộ lọc kỳ/Market đi cùng biểu đồ, KPI và CSV xuất; xếp Market/Product theo Gap có dấu tăng dần, quy định thứ tự khi đồng hạng. Lịch đánh giá forecast và bảng thực nghiệm có phạm vi riêng được ghi rõ.
- [x] TN11 kỹ thuật: đổi West→East→West ở 01/2012; West Sales/Budget/Gap = 10.453/9.460/+993, East = 6.780/6.180/+600. Đã thao tác browser trên mart SQL Server, tải CSV và đối chiếu nguồn.
- [x] Giao diện báo không có bản ghi khi lọc rỗng; lỗi kết nối nguồn có thông báo riêng, không biến thành KPI bằng 0. Ca rỗng kiểm trên browser; ca nguồn lỗi/warehouse rỗng kiểm riêng bằng AppTest, không lộ nội dung connection.
- [x] TN07: chuẩn bị bench riêng, đối chiếu số dòng/tổng và EXCEPT hai chiều trước khi đo; dữ liệu nhân bản chỉ dùng thử tải. Sáu bảng × 2.124.000 dòng, kiểm đa tập trước/sau.
- [x] TN08: indexed view so GROUP BY, kiểm tra SET options/SCHEMABINDING/COUNT_BIG, plan thực đọc bảng hoặc view, đo cả duy trì và dung lượng. Có phép đo INSERT statement rồi rollback, không gọi throughput commit.
- [x] TN09: bảng thường/partition RANGE RIGHT, cùng dữ liệu/chỉ mục; lọc một tháng và toàn khoảng, ghi partition thực truy cập. Actual plan xác nhận 1 và 24 partition; toàn kỳ không cải thiện.
- [x] TN10: đối chứng độc lập có/không nonclustered index; thử lát cắt hẹp/rộng, selectivity, seek/scan/lookup. Đã thấy Seek/Scan; covering NCI không có Lookup, không tạo/tuyên bố operator giả.
- [x] Mỗi cặp: ba warm-up, 15 lượt đo mỗi phương án xen kẽ, IO/TIME/actual plan, raw runs, median/p95 cùng quy ước. TN08–10 có 216 lượt kể cả warm-up, 180 lượt chính.
- [x] TN13 mở rộng: lattice tám cuboid MRP/MR/MP/RP/M/R/P/tổng, ngân sách lưu trữ, greedy tính lại lợi ích biên; so mô hình chi phí và đo SQL. Chọn 167/300 group-row; 216 lượt replay, MP fallback base; chưa đo refresh HRU.
- [ ] Nghiệm thu người dùng: cùng người thử Excel và Streamlit, đổi thứ tự, ba tác vụ tương đương; ghi ẩn danh, đúng/sai, giây, trợ giúp.
- [x] Lưu phiên bản môi trường, thông số, log, `.sqlplan`, ảnh và kết luận có giới hạn; không điền thời gian hay phản hồi người dùng chưa đo. Tổng native TN08–10/HRU có 432 actual plan + 432 Messages và manifest 926 artifact.
- [x] Diễn tập source snapshot sạch với venv mới và có kịch bản bảo vệ bốn phút. CLI demo/forecast, 113 pytest và 10 frontend test đạt; không copy DB/output cũ. Đây là snapshot mã đang làm, chưa phải checkout từ commit Git đã bàn giao; audio/model không tái tải trong venv mới.
- [ ] Chốt commit/PR vào dev và kiểm lại bản checkout từ commit đã chốt; người trình bày tự diễn tập thời lượng bốn phút. Không cập nhật main khi chưa được Trang chấp thuận.

Điều kiện bàn giao: người khác chạy được theo README; SQL Server/SSIS/SSAS, benchmark và thử người dùng chỉ ghi đạt khi có minh chứng tương ứng. Nếu thời gian sát độ phân giải đồng hồ, kết luận chưa đủ bằng chứng về tốc độ dù plan cho thấy cơ chế hoạt động.

## Linear Lab trong server tích hợp — 23/11/2026

Trang `http://127.0.0.1:8504/linear.html` dùng cùng server/backend chỉ-đọc với Cube 3D và Query Studio, không tạo thêm cổng dashboard. API `GET /api/linear` tổng hợp Marketing/Sales từ mart, kiểm tra đủ 96 ô rồi trả phương trình, điểm train/test và metric cho bốn Market. Giao diện có scatter plot, đường hồi quy, thanh what-if −30% đến +50%, bảng so sánh và cảnh báo không phải dự báo/nhân quả. Xem [protocol và kết quả](../trang/linear_marketing.md).

## Hoàn thiện và bằng chứng ngày 19/11/2026

- [Báo cáo chương 6–7, kết luận RQ, protocol/phiếu UX và kịch bản 4 phút](../trang/README.md) đã có bản Markdown cùng HTML in được. Không sửa hai Word gốc.
- [Native serving](../../results/trang_completion/native_serving/verification.json): đối soát từng dòng, đủ 11 số đo và 96 ô; tổng Sales819811/Budget746160/Profit259543. Publish/replay 112 forecast không trùng, 4 actual tương lai NULL. Database biệt lập `CoffeeDW_Trang_20261119`, không thay bằng chứng SSIS/SSAS của Chi.
- [Nghiệm thu browser](../../results/trang_completion/browser/acceptance.json): 12 ca kỹ thuật, screenshot/AX và CSV thật đã tải; export West01/2012 gồm56 dòng,12 sản phẩm, Sales10453; Inventory khi chọn01–02/2012 chỉ lấy02/2012=38751. Demo có công thức MA3, gate actual, play/pause và tiến độ âm thanh. Chưa đánh giá chủ quan độ tự nhiên của giọng.
- [Bàn giao native và cách tái lập](../TRANG_NATIVE_HANDOFF.md): SQL Server Express15.0.2210.4, MAXDOP1/memory grant1% ở query cho cả A/B, máy dùng chung. Reads/time/CPU/storage và kết quả không cải thiện được giữ; 0ms không diễn giải thành speedup vô hạn.
- UI/AppTest là bằng chứng kỹ thuật. [Bộ UX](../trang/ux_protocol.md) đã chuẩn bị đủ đề A/B, đáp án từ nguồn, CSV Excel, phiếu trống và bộ tổng hợp; **0 người/0 lượt**, không đánh dấu nghiệm thu người dùng.
- Luồng Git vẫn là `trang` → PR `dev`; working tree còn các file mới và chưa commit. Không cập nhật `main`.
- [Tái lập snapshot sạch](../../results/trang_completion/clean_snapshot/verification.json):131 file nguồn, venv mới không system-site-packages, extras dev/explore/sqlserver cài mới và pip check sạch. CLI tạo lại kho/forecast từ nguồn. Giới hạn voice và committed checkout ghi trong manifest; [script prepare/verify](../../scripts/verify_trang_snapshot.py) tái lập được.

## Phản hồi prototype — 16/11/2026

Trang phản hồi ba điểm: tương phản/cỡ chữ khó đọc, lời đọc nhanh và dính chữ, nội dung còn rời rạc. Bản sửa trong `apps/forecast_demo/` dùng Times New Roman, nền sáng navy–trắng, thêm bối cảnh kinh doanh và điều cần kiểm tra để nối báo cáo. Piper được điều chỉnh tốc độ, viết số thành chữ và nghỉ giữa câu/đoạn; vẫn cần người nghe đánh giá chất giọng. Cách chạy và bằng chứng kiểm tra tự động ở [README demo](../../apps/forecast_demo/README.md). Công cụ trình duyệt báo host chưa khả dụng, chưa nghiệm thu nhìn/nghe hoặc đánh dấu TN11/UX hoàn tất từ lượt sửa này.

## Luồng báo cáo có kiểm chứng — sau vòng thử tham số

[Bước tích hợp](../../experiments/briefing/README.md) cập nhật demo với MA3 mặc định; ba phần dự kiến → công thức ba tháng → sáu kỳ kiểm chứng, bảng7 cấu hình và tải Markdown/CSV theo bộ lọc. Actual chỉ hiện khi chủ động mở;01/2014 giữ thiếu. Đã đối soát96 ô với kho SQLite, có16 hồ sơ MA3/18 bộ hình,61 test Python và10 test JavaScript đạt; AppTest bundle/audio thật và West→East→West không có exception/warning. Dịch vụ8502 phản hồi health OK; đây chưa phải bằng chứng nhìn/nghe trong browser. Host CUA chưa khả dụng, nên TN11/UX/native vẫn để chờ phiên nghiệm thu thật. Log/checksum tại `experiments/briefing/results/manifest.json` và `results/forecast_demo/qa_v3.json`.

## Giao diện phân tích riêng — Coffee Atlas, 21/11/2026

[Coffee Atlas / Cube Explorer](../../apps/cube_explorer/README.md) ban đầu là ứng dụng riêng ở cổng8503; bản tích hợp SQL Server hiện chạy ở cổng8504, không sửa dashboard hoặc prototype forecast cổng8501/8502. Phạm vi chính là phân tích Sales/Budget/Profit theo tháng–Market–sản phẩm; Query Studio và Linear Lab là các chức năng bổ sung trong cùng server. Khối 3D là lớp biểu diễn các mart quan hệ, không gọi là một engine SSAS mới.

- [x] Đọc trực tiếp `mart.vw_MarketPeriod`, `mart.vw_MarketProductPeriod`, `dw.DimProduct` và drill State qua `mart.vw_Detail`. Chạy SELECT chỉ-đọc trên DB SSIS biệt lập `CoffeeDW_Trang_SSIS_TN03_20261120`; 96/1.008 ô, tổng819811/746160/259543 khớp nguồn.
- [x] Có code khối 3D xoay/cắt lát/tách lớp/đổi trục; chọn tháng–Market–nhóm/sản phẩm và export cùng phạm vi. Kiểm tra controller với dữ liệu API SQL Server thực đạt10/10 và hình học Three.js thật đạt4/4; kiểm backend đạt13/13. Các phép kiểm logic/hình học chưa xác nhận hình hiển thị thực.
- [x] Có câu chuyện South08/2013: Sales4601/Budget4610/Gap−9; Colombian−268 và phân rã xuống State giữ tổng. Màn “Từ kho đến ứng dụng” nối ETL → hình sao → mart → bộ lọc hiện tại.
- [ ] Kiểm tra hình, xoay/chạm khối và bố cục responsive trong browser thực. Công cụ browser đã dừng vì không xác minh được URL cửa sổ đang mở; không thay bước này bằng Node VM hoặc ảnh minh họa.
- [ ] Thử với người tham gia và đánh giá mức dễ hiểu; không suy tính hữu ích hoặc thời gian tác vụ từ các test tự động. Hướng dẫn, giới hạn và cách tái lập ở README ứng dụng riêng.

**Bản làm mới cùng ngày:** Coffee Atlas chuyển sang ba tab **Khối dữ liệu 3D / Phân tích chi tiết / Kho & ứng dụng**, tăng cỡ chữ, tương phản, bo góc và giữ bộ lọc giữa các tab. Tab chi tiết có bốn KPI, bảng sản phẩm, drill State và CSV cùng phạm vi; bộ lọc trên khung hẹp thu gọn. Node20/20 đạt, gồm kiểm tra tab/bộ lọc mới. Phiên browser thực đã xem1440/527/390px, không tràn ngang, không lỗi console; South/Colombian08/2013 khớp1102/1370/−268/80,4% và bốn State. [Ảnh giao diện](../../results/cube_explorer/design_desktop_20261121.jpg), [biên bản](../../results/cube_explorer/design_verification_20261121.json) là mốc kiểm hình hiển thị mới, bổ sung cho giới hạn browser của lần dựng đầu; không thay nghiệm thu UX người thật.
