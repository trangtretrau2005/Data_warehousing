# Chương 4 — Quy trình ETL và kiểm soát chất lượng

Người phụ trách: **Chi**. Cần phân biệt chạy logic tham chiếu bằng Python với bằng chứng chạy package SSIS tại máy.

- [ ] Đăng ký batch gồm tên file, SHA-256, thời điểm, trạng thái và số dòng; raw staging giữ chuỗi gốc và số dòng nguồn.
- [ ] Parse ngày Excel, mã địa bàn và tiền; đẩy dòng lỗi sang audit kèm nguyên nhân/giá trị gốc, không thay lỗi bằng 0.
- [ ] Nạp dimension trước fact, lookup khóa nhiều–một, transaction và UNIQUE bảo vệ grain.
- [ ] Triển khai nạp mới, chạy lại cùng nội dung, sửa số cùng khóa; ghi RowsRead/Accepted/Rejected/Inserted/Updated.
- [ ] Kiểm tra `read = accepted + rejected`, tổng số đo tập hợp lệ, khóa mồ côi và tổng trước/sau join.
- [ ] TN03: tải đầy đủ, phát lại nguyên file, bản sao có Sales=`abc`; lưu audit và reject, giữ nguyên CSV gốc.
- [ ] Kiểm tra tải tăng dần: 23 tháng đầu → thêm 12/2013 → phát lại 12/2013; kết quả cuối 4.248 dòng, Sales 819.811.
- [ ] TN04: SCD Type 1 sửa nhãn; Type 2 đóng/mở phiên bản trong cùng transaction; lookup trước và đúng biên hiệu lực.
- [ ] Kiểm tra không chồng khoảng, một dòng hiện hành và nạp lại sự kiện không tăng phiên bản; minh họa giới hạn Type 3.
- [ ] Tạo và chạy package SSIS thật; chụp Control Flow/Data Flow, mã batch, số dòng và đường lỗi.

Ca dữ liệu lỗi nhỏ của báo cáo: lấy tám dòng đầu, sửa Sales dòng đầu thành `abc`, Product dòng thứ hai thành rỗng; kỳ vọng sáu dòng hợp lệ với Sales 1.139. Khi chạy trên kho đã có dữ liệu, một dòng bị loại ở batch mới vẫn có thể có bản hợp lệ từ batch trước; phải nêu trạng thái kho để diễn giải số tổng.

Điều kiện bàn giao: log batch và reject truy ngược được tới file/dòng; các ca tải tăng dần, phát lại, sửa số có đáp án; SSIS chỉ đánh dấu đạt sau khi có log và ảnh chạy thật.
