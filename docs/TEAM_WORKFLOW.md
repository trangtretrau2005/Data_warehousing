# Phân công và phối hợp nhóm

Nhóm cùng làm trong repository `Data_warehousing`. Mỗi phần có một người chịu trách nhiệm cuối cùng; người khác có thể hỗ trợ qua nhánh và Pull Request.

| Thành viên | Nhánh | Phạm vi báo cáo | Phạm vi code chính | Điểm cần bàn giao |
| --- | --- | --- | --- | --- |
| Thanh | `thanh` | Chương 1, 2, 3 | Source profiling, mapping, DDL, sơ đồ, lý thuyết | Grain/khóa/kiểu/11 số đo và bộ đối soát cho Chi, Trang |
| Chi | `chi` | Chương 4, 5 | ETL, audit/reject, SSIS, SCD, mart, SSAS/MDX | Hợp đồng view và dữ liệu đã đối soát cho dashboard/dự báo |
| Trang | `trang` | Chương 6, 7 | Forecast, dashboard, benchmark, tích hợp và nghiệm thu | App chạy được, sai số/plan/log/UX, hướng dẫn tái lập |

Phần phân công tên không thay GitHub username. Khi biết tài khoản của Thanh và Chi, Trang thêm họ làm collaborator trên GitHub nếu cần quyền push nhánh. Mỗi thành viên bắt đầu theo [START_HERE](START_HERE.md), trong đó có prompt dành cho agent.

## Thứ tự phối hợp

1. **Thanh chốt hợp đồng dữ liệu:** profile nguồn, grain, mapping, DDL và một nhóm đối soát. Các thay đổi schema sau mốc này phải cập nhật cả người tiêu thụ.
2. **Chi hoàn thiện luồng kho:** chạy ETL với đầy đủ ca nạp, tạo mart và cube. Trong lúc chờ SQL Server/SSIS/SSAS, cả nhóm dùng SQLite để phát triển logic.
3. **Trang tích hợp ứng dụng:** đọc hợp đồng mart, triển khai forecast với split cố định, dùng cùng filter/KPI ở web và file xuất.
4. **Cả nhóm nghiệm thu:** nguồn→kho→cube→web khớp số; lưu đầy đủ TN trước khi đưa kết luận vào báo cáo.

Không cần đợi xong chương trước để viết phần độc lập: Thanh có thể viết lý thuyết, Chi dựng package với schema đã chốt, Trang làm giao diện và forecast trên bản SQLite.

## Nhánh và Pull Request

Luồng tích hợp là `thanh` / `chi` / `trang` → `dev` → `main`. Các nhánh cá nhân đã có sẵn trên GitHub. `dev` là nơi merge code của nhóm và chạy thử toàn luồng. `main` được giữ nguyên cho tới khi Trang xác nhận bản tích hợp OK và yêu cầu cập nhật.

```powershell
git fetch origin
git switch thanh
git pull --ff-only origin thanh
# Làm phần việc, chạy lệnh kiểm tra phù hợp, chọn rõ file cần commit.
git add docs/chapters/ch01_thanh.md
git commit -m "docs: clarify business questions and data grain"
git push origin thanh
```

Sau đó mở Pull Request trên GitHub với **base `dev`, compare `thanh`**. Chi/Trang dùng compare `chi`/`trang`. Trước khi merge vào `dev`, một thành viên đọc thay đổi, kiểm tra tên cột/KPI và cách tái lập. Chạy lại toàn luồng tích hợp trên `dev` sau khi merge.

Khi cần lấy thay đổi tích hợp mới về nhánh cá nhân, bảo đảm đã lưu công việc rồi chạy `git fetch origin`, chuyển đúng nhánh và `git merge origin/dev`; xử lý conflict và kiểm tra lại nếu có. Không force push các nhánh chung. Chỉ mở/merge bản phát hành từ `dev` sang `main` sau khi Trang chấp thuận rõ ràng.

## Tránh đụng cùng file

- Mỗi chương có file Markdown riêng trong `docs/chapters/`; ghép vào bản Word sau khi nội dung ổn định. Git khó merge `.docx` và package designer; báo trong nhóm trước khi sửa cùng một file Word/SSIS/SSAS.
- Thanh chủ trì DDL; Chi chủ trì ETL/mart. Nếu đổi tên cột/khóa, PR phải kèm cập nhật source mapping, mart, cube, forecast và app bị ảnh hưởng.
- Cùng một TN có thể nhiều người chạy; đặt output vào thư mục con theo người/ngày hoặc ghi rõ người/commit trong phiếu. Không ghi đè số đo cũ khi chưa giữ cấu hình gốc.
- Giữ `data/raw/Coffee.csv` nguyên trạng. Dữ liệu lỗi và bản nhân tải nằm trong vùng thử, không nối vào kho phục vụ dashboard/ML.
- File `.env`, mật khẩu, `.venv`, database cục bộ và cache không commit. Chỉ thêm thủ công các output minh chứng nhỏ cần đưa vào báo cáo; xem [quy ước kết quả](../results/README.md).

## Một Pull Request hoàn thành khi

- [ ] Nêu rõ vấn đề, hành vi sau sửa và chương/TN liên quan.
- [ ] Chạy được từ hướng dẫn và không phụ thuộc đường dẫn tuyệt đối trên máy người viết.
- [ ] Các khóa, số dòng, tổng và KPI được đối soát ở phạm vi thay đổi.
- [ ] Cập nhật checklist chương và minh chứng thật; ghi phần còn chờ công cụ native.
- [ ] Người khác biết cần chạy lại ETL/process cube/forecast nếu dữ liệu hoặc schema đổi.

Xem thêm [CONTRIBUTING](../CONTRIBUTING.md) và [hợp đồng kiến trúc](architecture.md).
