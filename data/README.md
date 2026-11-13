# Dữ liệu dự án

`raw/Coffee.csv` là nguồn dùng chung được theo dõi trên Git. Giữ nguyên file để cả ba thành viên đối soát cùng snapshot. Nguồn được mô tả trong hai tài liệu Word ở `docs/`; nhóm cần bổ sung URL nguồn Kaggle, tác giả và điều kiện sử dụng trước khi công bố sản phẩm.

Snapshot tại thời điểm dựng base: 4248 bản ghi, 20 cột; SHA256 `929bdcc7fd8f6bf21607618e7474df0683af6412b32b8c5af39a40e89b62ffce`. Đây là dữ liệu tháng 2012–2013. AreaCode là mã phân loại, chưa có mã cửa hàng/hóa đơn/khách hàng; đơn vị tiền tệ và Inventory chưa được nguồn CSV công bố.

`warehouse/` và `processed/` là vùng sinh cục bộ, được ignore. Tạo lại warehouse bằng `python -m coffee_dw.cli demo`. Dữ liệu lỗi, sửa số hay nhân tải chỉ dùng trong bài thử riêng; không ghi vào raw. Nếu cập nhật snapshot thật, ghi checksum mới, nguồn, khác biệt schema/kỳ và chạy lại toàn bộ đối soát/dự báo.
