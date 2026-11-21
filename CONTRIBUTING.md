# Đóng góp vào Coffee DW

Phân công: **Thanh chương 1–3**, **Chi chương 4–5**, **Trang chương 6–7**. Chi tiết phạm vi và cách bàn giao ở [TEAM_WORKFLOW](docs/TEAM_WORKFLOW.md).

## Thiết lập và kiểm tra

Python tối thiểu 3.11; nên dùng 3.12 để cả nhóm thống nhất. Chạy tại thư mục gốc:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m coffee_dw.cli demo
.\.venv\Scripts\python -m coffee_dw.cli forecast
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m streamlit run apps/dashboard/app.py
```

Nếu dùng Python 3.11, thay `-3.12` bằng `-3.11`. Không cần bật PowerShell activation để chạy các lệnh này. Luồng SQL Server còn cần ODBC Driver và cấu hình riêng theo README, `ssis/README.md`, `ssas/README.md`; cài extra bằng `pip install -e ".[dev,sqlserver]"` trong cùng môi trường.

## Quy tắc sửa code và dữ liệu

- Làm trên `thanh`, `chi` hoặc `trang`; commit nhỏ có mục đích; mở PR với base `dev` để một người khác review và tích hợp chạy thử.
- Giữ nguyên `main`. Chỉ cập nhật `main` từ bản `dev` đã kiểm tra sau khi Trang xác nhận OK rõ ràng; không push trực tiếp hoặc tự merge vào `main`.
- Đồng bộ nhánh cá nhân từ `origin/dev` trước khi tích hợp việc mới nếu cần. Giải quyết conflict trên nhánh cá nhân và chạy lại kiểm tra bị ảnh hưởng.
- Giữ raw bất biến; không thay số lỗi bằng 0, không xóa Profit/Inventory âm theo mặc định.
- Khi đổi schema, cập nhật consumer và tài liệu trong cùng PR; ba phần cùng dùng một định nghĩa grain/KPI.
- Thêm kiểm tra khi thay đổi logic có ảnh hưởng grain, tổng, ETL hoặc chia thời gian dự báo. Chỉnh tài liệu/định dạng nhỏ chỉ cần kiểm tra phù hợp.
- Với SQL, ghi thứ tự chạy, database/schema và batch `GO` khi cần. Chỉ chạy dữ liệu nhân bản trong `bench`.
- Không commit thông tin đăng nhập, `.env`, file venv, database phát sinh hoặc cache. Kiểm tra `git diff --cached` trước commit.
- Kết quả thí nghiệm phải có input/config/người/commit/output. Không điền số tốc độ, ảnh cube hay phản hồi UX khi chưa chạy.

## Nội dung PR

```text
Vấn đề và hành vi sau thay đổi:
Chương/TN và file liên quan:
Cách chạy lại:
Kiểm tra và minh chứng:
Phần còn chờ SQL Server/SSIS/SSAS/người thử (nếu có):
```

Nếu làm thay đổi số trong báo cáo, ghi rõ phiên bản dữ liệu và công thức/split. Đặc biệt, TN12 thăm dò West và protocol chính 15/6/3 của chương 6 là hai thực nghiệm khác nhau.
