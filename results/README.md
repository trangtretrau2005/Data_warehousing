# Quy ước lưu kết quả

`results/` chứa output sinh khi thực chạy và chứng cứ báo cáo. Mặc định Git ignore các kết quả lớn/riêng từng máy; chỉ `README`, `templates` và `examples` được theo dõi. Kho SQLite nằm ở `data/warehouse` và cũng bị ignore.

| Vùng | Nội dung |
| --- | --- |
| TN01 | profile.json từ nguồn thực |
| TN03 | load.json và incremental.json; ca lỗi/sửa số ghi rõ mô phỏng |
| TN04 | scd.json cho bản thử P01 |
| TN07–10 | benchmark_runs.csv, summary, SQL, Messages, .sqlplan và ảnh A/B |
| TN11 | Ảnh bộ lọc, export, ux_trials.csv với người thử ẩn danh |
| TN13 | hru.json; tách mô hình chi phí với số đo SQL |
| forecast | metrics.csv, predictions.csv, next_month.csv, summary.json |

Mỗi lần đo quan trọng tạo thư mục con như `TN08/trang_2026-11-13/`, kèm phiếu từ `templates/experiment.md`. Ghi commit, checksum, tham số, số dòng, máy và phiên bản engine. UTC dùng cho audit kỹ thuật; ngày/người thực hiện ghi theo giờ của nhóm.

Khi cần đưa một bộ bằng chứng nhỏ lên Git, kiểm tra không có mật khẩu/thông tin kết nối rồi thêm đúng tệp:

```powershell
git add -f results/TN08/trang_2026-11-13/experiment.md
git add -f results/TN08/trang_2026-11-13/benchmark_runs.csv
git diff --cached --stat
```

Không thêm toàn bộ `results` bằng `-f`. Log/plan dài nên lưu như phụ lục có chọn lọc; đặt link trong phiếu. Tệp ví dụ trong `examples` phải ghi rõ là minh họa. Không điền sẵn số benchmark, phản hồi người thử hoặc ảnh SSIS/SSAS khi chưa chạy.
