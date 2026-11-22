# Chương 4 — Quy trình ETL và kiểm soát chất lượng

Người phụ trách: **Chi**. Cần phân biệt chạy logic tham chiếu bằng Python với bằng chứng chạy package SSIS tại máy.

> **Bổ sung native 20/11/2026 trên máy Trang:** bản thích nghi biệt lập đã chạy tám ca CSV trong SSDT, đủ tám receipt và verifier PASS, kho cuối 4248/Sales819811/Budget746160/Profit259543. [Biên bản và bảng từng ca](../TRANG_NATIVE_BUILD_20261120.md), [verification.json](../../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/verification.json), [ảnh thành công](../../results/native_build_20261120/ui/ssis_acceptance_success.png). Các dấu đạt dưới đây giới hạn ở protocol này; không khẳng định bản trên máy Chi đã tự chạy.

- [x] Đăng ký batch gồm tên file, SHA-256, thời điểm, trạng thái và số dòng; raw staging giữ chuỗi gốc và số dòng nguồn.
- [x] Parse ngày Excel, mã địa bàn và tiền; đẩy dòng lỗi sang audit kèm nguyên nhân/giá trị gốc, không thay lỗi bằng 0.
- [x] Nạp dimension trước fact, lookup khóa nhiều–một, transaction và UNIQUE bảo vệ grain.
- [x] Triển khai nạp mới, chạy lại cùng nội dung, sửa số cùng khóa; ghi RowsRead/Accepted/Rejected/Inserted/Updated.
- [x] Kiểm tra `read = accepted + rejected`, tổng số đo tập hợp lệ, khóa mồ côi và tổng trước/sau join.
- [x] TN03: tải đầy đủ, phát lại nguyên file, bản sao có Sales=`abc`; lưu audit và reject, giữ nguyên CSV gốc.
- [x] Kiểm tra tải tăng dần: 23 tháng đầu → thêm 12/2013 → phát lại 12/2013; kết quả cuối 4.248 dòng, Sales 819.811.
- [x] TN04: SCD Type 1 sửa nhãn; Type 2 đóng/mở phiên bản trong cùng transaction; lookup trước và đúng biên hiệu lực.
- [x] Kiểm tra không chồng khoảng, một dòng hiện hành và nạp lại sự kiện không tăng phiên bản; minh họa giới hạn Type 3.
- [x] Tạo và chạy package SSIS thật; chụp Control Flow/Data Flow, mã batch, số dòng và đường lỗi.

SCD có [manifest/log thực chạy riêng](../../results/native_build_20261120/ssis/scd/6f3301d7-87ff-44c5-a578-76666329f290/manifest.json), Execute SQL package exit 0/assertions PASS; P01/A01 là dữ liệu mô phỏng, không phải sự kiện đổi nhãn thật từ Coffee.csv. Data Flow CSV là Flat File→Derived BatchID→OLE DB raw landing; ép kiểu/reject nằm trong validator T-SQL rồi loader. Ảnh [Data Flow sau chạy](../../results/native_build_20261120/ui/ssis_data_flow_executed_viewport.png) là ảnh viewport với bộ đếm giao diện; không dùng ảnh để chốt tổng. Số dòng đầy đủ đã đối chiếu bằng landing/audit/verifier.

**Đối soát SQL chỉ đọc ngày 20/11/2026:** [39 phép kiểm PASS](../../results/native_build_20261120/relational_acceptance/final/summary.json), [phân tích và giới hạn](../../results/native_build_20261120/relational_acceptance/final/analysis.md), bằng [script có guard exact DB](../../scripts/native_ssas_trang/verify_etl_mart.py). PK fact đúng ba khóa; bốn FK được enabled/trusted; UNIQUE các khóa dimension hoạt động; không có orphan hoặc duplicate grain. JOIN ba chiều giữ 4.248 dòng và cả 11 tổng; tám batch giữ số dòng/11 tổng từ staging hợp lệ qua lookup, khớp nguồn từng batch. Định nghĩa loader trên DB cho thấy dimension→mapping→fact nằm trong BEGIN/COMMIT TRANSACTION, có XACT_ABORT và nhánh ROLLBACK. Phép SELECT-only này không tự chứng minh lỗi rollback; bằng chứng fault-injection native được thu riêng ngay dưới đây.

**Rollback native đã thực thử ngày 20/11/2026:** [verification 12/12 PASS](../../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/verification.json), [biên bản/giới hạn](../../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/README.md) và [runner có guard](../../scripts/native_ssas_trang/verify_loader_rollback.py). Probe trong outer transaction không commit cố ý khai 2 dòng nhưng staging 1 dòng, đổi Sales/State của khóa có sẵn, chạm guard cuối của loader sau các UPDATE: error50006 tại dòng 74. Trước EXEC `@@TRANCOUNT=1`; receipt trong CATCH xác nhận `@@TRANCOUNT=0`, `XACT_STATE()=0`. Sau đó 11 bảng/47.315 dòng có hash logical toàn bộ cột giống trước, không còn probe/residue;11 số đo, raw và tám receipt SSIS giữ nguyên. [5 test safeguards PASS](../../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/unit_tests.xml) hỗ trợ runner, không thay kết quả native. Đây là thử T-SQL trên DB biệt lập, không phải ca SSIS thứ 9 hoặc sự kiện nguồn thật; không ALTER loader, không commit business rows. ODBC 266 chỉ được chấp nhận kèm đúng receipt 50006 và toàn bộ readback đạt, không nuốt lỗi khác. Hash so giá trị logical, không phải page vật lý; không dùng test SQLite để thay bằng chứng này.

Ca dữ liệu lỗi nhỏ của báo cáo: lấy tám dòng đầu, sửa Sales dòng đầu thành `abc`, Product dòng thứ hai thành rỗng; kỳ vọng sáu dòng hợp lệ với Sales 1.139. Khi chạy trên kho đã có dữ liệu, một dòng bị loại ở batch mới vẫn có thể có bản hợp lệ từ batch trước; phải nêu trạng thái kho để diễn giải số tổng.

Điều kiện bàn giao: log batch và reject truy ngược được tới file/dòng; các ca tải tăng dần, phát lại, sửa số có đáp án; SSIS chỉ đánh dấu đạt sau khi có log và ảnh chạy thật.
