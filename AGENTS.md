# Hướng dẫn làm việc trong Coffee DW

Repo phục vụ bài tập lớn môn Kho dữ liệu trên Coffee Chains. Có hai phần: thực nghiệm kiến thức trong `learning/`, `sql/`, `ssis/`, `ssas/`; dashboard và AI trong `apps/dashboard/` và `src/coffee_dw/forecast.py`. Logic dữ liệu dùng chung nằm ở `src/coffee_dw/`.

## Đọc trước khi sửa

1. `README.md` và `docs/START_HERE.md`: thiết lập và việc đầu tiên theo vai trò.
2. `docs/architecture.md`: grain, schema, mapping và hợp đồng consumer.
3. `docs/REPORT_MAP.md` và `docs/BASE_STATUS.md`: yêu cầu báo cáo, TN01–TN13, phần đã chạy và phần còn chờ.
4. Checklist chương liên quan trong `docs/chapters/`, rồi đọc code/tests hiện có trước khi đề xuất thay đổi.

Khi cần chi tiết yêu cầu gốc, đọc hai tài liệu Word trong `docs/`. Mặc định dùng tiếng Việt cho giải thích và tài liệu nhóm; tên code/cột giữ thống nhất với hợp đồng hiện tại. Tái sử dụng base, bổ sung theo checklist và phạm vi người giao việc.

## Phân công và nơi sửa

| Thành viên | Chương | Phạm vi chính |
| --- | --- | --- |
| Thanh | 1–3 | Lý thuyết, hồ sơ nguồn, `source.py`, DDL, mô hình sao và mapping |
| Chi | 4–5 | `warehouse.py`, ETL/audit, SCD, mart, `ssis/`, `ssas/` và OLAP |
| Trang | 6–7 | `forecast.py`, dashboard, benchmark, tích hợp và nghiệm thu |

Phân công xác định người chủ trì, không chặn sửa consumer cần thiết. Nếu đổi schema/tên cột/quy tắc KPI, cập nhật code liên quan, tests và tài liệu trong cùng thay đổi; nêu rõ phần cần bàn giao cho người khác.

## Những hợp đồng phải giữ

- `data/raw/Coffee.csv` bất biến. Tạo bản sao biệt lập cho dữ liệu lỗi, sửa số, SCD mô phỏng hay nhân tải.
- Grain fact: tháng × mã vùng × sản phẩm. AreaCode là chuỗi; số dòng không phải số đơn hàng. Date Excel có origin `1899-12-30`.
- Giữ đủ 11 số đo nguồn, Profit/Inventory âm và các chênh đẳng thức kế toán. Thiếu khóa/sai kiểu/trùng grain đi vào reject; không đổi lỗi thành số0.
- Tỷ lệ ngân sách = SUM(Sales)/SUM(BudgetSales) trong cùng filter; mẫu0 trả thiếu. Inventory chỉ gộp trong một kỳ theo chính sách kỳ cuối, không SUM xuyên thời gian.
- SQLite là bản tham chiếu. SQL Server, SSIS, SSAS, benchmark và UX cần bằng chứng thực chạy riêng. `ssas/queries.mdx` là mẫu cần khớp tên metadata của project native.
- Forecast chính: 15 kỳ khởi tạo, 6 kỳ validation, 3 kỳ test; chọn bằng validation, fit feature/scaler chỉ trên quá khứ. TN12 West trong sổ tay là protocol khác.

## Kiểm tra và bàn giao

Tại root sau khi setup:

```powershell
.\.venv\Scripts\python -m coffee_dw.cli demo
.\.venv\Scripts\python -m coffee_dw.cli forecast
.\.venv\Scripts\python -m pytest
```

Chạy kiểm tra phù hợp với phần thay đổi. Khi sửa logic nguồn/ETL/forecast phải kiểm tra grain, số dòng, tổng hoặc split bị ảnh hưởng. Trên snapshot gốc: 4248 dòng, 24 tháng, Sales819811, BudgetSales746160, Profit259543. Thay đổi tài liệu nhỏ chỉ cần kiểm tra nội dung và link liên quan.

Sau mỗi đầu việc, ghi file đã sửa, cách tái lập, kết quả kiểm tra, giới hạn và bước tiếp theo. Cập nhật checklist chương theo bằng chứng thực có. Không ghi hoàn tất SSIS/SSAS/benchmark/UX khi chưa có log, plan, ảnh hoặc phiên thử tương ứng.

## Git và tài sản sinh ra

- Mặc định tính năng mới dùng nhánh theo thành viên, mở PR vào `main`; thực hiện yêu cầu Git cụ thể của người dùng nếu có. Không force push hoặc bỏ thay đổi của người khác.
- Trước commit xem `git status`, diff và danh sách staged. Không commit `.env`, credential, `.venv`, cache hay database cục bộ.
- `results/` được ignore theo mặc định; chỉ thêm thủ công minh chứng nhỏ đã kiểm tra theo `results/README.md`. Không sửa ignore để đưa toàn bộ output lên Git.
- Dùng file Markdown riêng từng chương khi viết song song. Tránh ghi đè Word hoặc project designer đang được thành viên khác sửa.
