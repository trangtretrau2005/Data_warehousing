# SSIS Chương 4

Chi chủ trì project Integration Services native tại đây. Base ban đầu cung cấp schema/procedure và bản Python tham chiếu; hướng dẫn dưới đây giữ các quy tắc triển khai chung. Dùng Visual Studio/SSDT có phần mở rộng SSIS phù hợp SQL Server của nhóm.

**Đã thực chạy 20/11/2026 trên máy Trang:** bản thích nghi riêng [CoffeeETLTrang](CoffeeETLTrang/README.md) và [CoffeeETLTrangAcceptance](CoffeeETLTrangAcceptance/README.md) Build trong Visual Studio 0 lỗi / 0 cảnh báo. Suite tám ca CSV qua SSDT F5 có đủ tám receipt, [verifier PASS/exit0](../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/verification.json); kho thử `CoffeeDW_Trang_SSIS_TN03_20261120` cuối 4248/Sales819811/Budget746160/Profit259543. SCD package có run riêng PASS. Xem [biên bản](../docs/TRANG_NATIVE_BUILD_20261120.md) để phân biệt lỗi DTExec trước đây, crash IDE sau thành công và giới hạn ảnh viewport; không tự ghi bản trên máy Chi đã chạy.

Data Flow hiện chạy Flat File UTF-8→Derived BatchID→OLE DB raw landing; validator T-SQL chuyển raw landing sang `stg.CoffeeRaw`, giữ reject/raw payload rồi gọi loader. Đây là phương án triển khai thực tế cho các yêu cầu dưới đây, không mô tả ép kiểu/reject đều nằm trong component Data Flow. Tham số của project này là standalone package variables có expression binding, không phải `Project.params` đã bind; xem README riêng trước khi đổi nguồn/DB.

[Rollback native riêng](../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/verification.json) đã đạt 12/12: loader phát lỗi 50006 sau UPDATE rồi rollback outer transaction; 11 bảng / 47.315 dòng giữ hash logical và không residue. Đây là T-SQL probe có guard/không commit business rows, không phải ca CSV thứ 9. [Tổng hợp kiểm tra cuối](../results/native_build_20261120/final_summary.json) giữ kết quả SSIS/SSAS/pytest/CLI và giới hạn IDE tách riêng.

[Cube cuối đã đọc chính DB này](../results/native_build_20261120/ssas/integrated_ssis_source/verification.json), ProcessFull lúc 14:58:07Z và chạy lại 17 ca MDX/pivot 6 ô trên SQL mới đều đạt; đó là minh chứng consumer SSAS sau nạp SSIS. Nguồn native 19/11 và receipt trước tích hợp vẫn được giữ riêng.

1. Chạy SQL00–03, tạo connection manager SQL Server và Flat File UTF-8. File path, server và DB là project parameter; dùng parameter nhạy cảm cho credential, không commit mật khẩu.
2. Control Flow: tạo BatchID, lưu checksum/tên nguồn/StartedAt vào `audit.LoadBatch`; đảm bảo SourceCount bằng số bản ghi đọc.
3. Data Flow: đọc 20 cột ở dạng chuỗi, thêm số bản ghi, chuyển Excel Date từ 1899-12-30 thành đầu tháng, giữ mã vùng là chuỗi và chuyển 11 số đo sang DECIMAL(19,4). Đối chiếu quy tắc với `source.py`.
4. Conditional Split/Error Output: thiếu khóa/sai kiểu/trùng grain/thuộc tính cha mâu thuẫn ghi RejectReason và raw payload. Giữ số Profit/Inventory âm và sai đẳng thức kế toán như cảnh báo. Không chuyển lỗi thành số0.
5. Nạp `stg.CoffeeRaw` gồm cả dòng hợp lệ và dòng bị loại. Execute SQL Task gọi `dw.usp_LoadCoffee @BatchID`; procedure transaction hóa lookup/upsert/audit. Nếu dùng lookup/insert fact trực tiếp bằng SSIS, áp cùng unique keys, chính sách Type1 và đối soát.
6. Chạy lần đầu, phát lại, sửa Sales cùng grain, thêm tháng12/2013, và ca8 dòng có2 lỗi. Lưu batch counts, source/valid totals và ảnh Control/Data Flow. Cập nhật checklist ch04 sau khi có bằng chứng.
7. SCD2 làm trong bảng/batch TN04 biệt lập với mã P01 ổn định, ValidFrom≤date<ValidTo; đóng/mở phiên bản cùng transaction, một current, không overlap và replay không tạo version mới. So Type1/Type3. Không dùng tên sản phẩm làm mã ổn định cho thay đổi tên thật.

Tên bảng và mapping ở [architecture](../docs/architecture.md); đáp án thử ở [learning](../learning/README.md). File demo lỗi nằm riêng, không sửa `data/raw/Coffee.csv`. Lưu log failed batch ngoài transaction để lỗi rollback cũng truy vết được. Đối soát tổng theo batch hợp lệ, không chỉ tổng toàn kho khi đang tải tăng dần.
