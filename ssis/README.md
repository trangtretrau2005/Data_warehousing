# SSIS Chương 4

Chi tạo project Integration Services native tại đây, ví dụ `ssis/CoffeeETL/`. Base cung cấp schema/procedure và bản Python tham chiếu; chưa có `.dtproj`/`.dtsx` đã deploy. Dùng Visual Studio/SSDT có phần mở rộng SSIS phù hợp SQL Server của nhóm.

1. Chạy SQL00–03, tạo connection manager SQL Server và Flat File UTF-8. File path, server và DB là project parameter; dùng parameter nhạy cảm cho credential, không commit mật khẩu.
2. Control Flow: tạo BatchID, lưu checksum/tên nguồn/StartedAt vào `audit.LoadBatch`; đảm bảo SourceCount bằng số bản ghi đọc.
3. Data Flow: đọc 20 cột ở dạng chuỗi, thêm số bản ghi, chuyển Excel Date từ 1899-12-30 thành đầu tháng, giữ mã vùng là chuỗi và chuyển 11 số đo sang DECIMAL(19,4). Đối chiếu quy tắc với `source.py`.
4. Conditional Split/Error Output: thiếu khóa/sai kiểu/trùng grain/thuộc tính cha mâu thuẫn ghi RejectReason và raw payload. Giữ số Profit/Inventory âm và sai đẳng thức kế toán như cảnh báo. Không chuyển lỗi thành số0.
5. Nạp `stg.CoffeeRaw` gồm cả dòng hợp lệ và dòng bị loại. Execute SQL Task gọi `dw.usp_LoadCoffee @BatchID`; procedure transaction hóa lookup/upsert/audit. Nếu dùng lookup/insert fact trực tiếp bằng SSIS, áp cùng unique keys, chính sách Type1 và đối soát.
6. Chạy lần đầu, phát lại, sửa Sales cùng grain, thêm tháng12/2013, và ca8 dòng có2 lỗi. Lưu batch counts, source/valid totals và ảnh Control/Data Flow. Cập nhật checklist ch04 sau khi có bằng chứng.
7. SCD2 làm trong bảng/batch TN04 biệt lập với mã P01 ổn định, ValidFrom≤date<ValidTo; đóng/mở phiên bản cùng transaction, một current, không overlap và replay không tạo version mới. So Type1/Type3. Không dùng tên sản phẩm làm mã ổn định cho thay đổi tên thật.

Tên bảng và mapping ở [architecture](../docs/architecture.md); đáp án thử ở [learning](../learning/README.md). File demo lỗi nằm riêng, không sửa `data/raw/Coffee.csv`. Lưu log failed batch ngoài transaction để lỗi rollback cũng truy vết được. Đối soát tổng theo batch hợp lệ, không chỉ tổng toàn kho khi đang tải tăng dần.
