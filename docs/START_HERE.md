# Bắt đầu làm việc với Coffee DW

Đây là code base của nhóm, đã có luồng Python/SQLite chạy được và hướng dẫn triển khai SQL Server/SSIS/SSAS. Mỗi thành viên đọc phần được giao, chạy bản demo, sau đó hoàn thiện code và báo cáo trên base hiện có. Checklist là việc cần nghiệm thu; code mẫu không đồng nghĩa mọi thực nghiệm đã hoàn thành.

## Lần đầu nhận repo

```powershell
git clone --branch main https://github.com/trangtretrau2005/Data_warehousing.git
cd Data_warehousing
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
.\.venv\Scripts\python -m coffee_dw.cli demo
.\.venv\Scripts\python -m coffee_dw.cli forecast
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m streamlit run apps/dashboard/app.py
```

Nếu đã clone, dùng `git pull --ff-only origin main` khi đang ở `main` và không có thay đổi chưa lưu. Mở cả thư mục repo trong IDE để agent thấy code và tài liệu. Không cần SQL Server cho lần chạy demo đầu tiên. Khi chuyển sang công cụ native, dùng cấu hình riêng trên máy và giữ credential trong `.env`.

Đọc theo thứ tự: [README](../README.md) → [hướng dẫn agent](../AGENTS.md) → [kiến trúc](architecture.md) → [ánh xạ báo cáo](REPORT_MAP.md) → [trạng thái base](BASE_STATUS.md) → checklist chương của mình. Cách phối hợp và PR ở [TEAM_WORKFLOW](TEAM_WORKFLOW.md).

## Thanh bắt đầu từ đâu

Tạo nhánh `thanh/ch01-03-schema`. Đọc `docs/chapters/ch01_thanh.md`, `ch02_thanh.md`, `ch03_thanh.md`, `source.py` và SQL00–01.

Việc đầu tiên: chạy profile, đối chiếu độc lập số nguồn/Pivot, xác nhận grain tháng–mã vùng–sản phẩm, lập mapping đủ20 cột và chốt DDL. Bàn giao cho Chi/Trang các khóa, kiểu số, quan hệ chiều, định nghĩa KPI và đáp án kiểm tra; ghi chỗ chưa rõ như đơn vị tiền/Inventory.

Prompt có thể gửi nguyên văn cho agent:

```text
Tôi là Thanh, phụ trách chương 1, 2, 3 của repo Coffee DW này.
Hãy đọc AGENTS.md, README.md, docs/START_HERE.md, docs/architecture.md,
docs/REPORT_MAP.md, docs/BASE_STATUS.md và ba checklist ch01_thanh,
ch02_thanh, ch03_thanh trong docs/chapters; sau đó đọc code liên quan.
Giải thích ngắn luồng dữ liệu và phần tôi phải bàn giao cho Chi/Trang.
Bắt đầu bằng kiểm chứng TN01: profile và đối soát độc lập nguồn, grain,
ngày Excel, tổng số đo, các phụ thuộc chiều; rồi rà mapping/DDL cho TN02.
Tận dụng code base hiện có, giữ nguyên Coffee.csv và hợp đồng consumer.
Làm trên nhánh thanh/ch01-03-schema; bổ sung nội dung và code còn thiếu,
kiểm tra phù hợp, cập nhật checklist và ghi minh chứng thực chạy.
Chỉ rõ điều gì đã kiểm chứng bằng Python, điều gì còn cần SQL Server.
```

## Chi bắt đầu từ đâu

Tạo nhánh `chi/ch04-05-etl-olap`. Đọc `docs/chapters/ch04_chi.md`, `ch05_chi.md`, `warehouse.py`, `learning/experiments`, SQL02–04 và hướng dẫn `ssis/`, `ssas/`.

Việc đầu tiên: chạy demo, incremental và SCD để hiểu audit/reject/idempotence trước. Tiếp theo dựng môi trường SQL Server, chạy SQL00–04 để đối soát, tạo package SSIS, rồi cube SSAS. Kiểm tra cùng bộ lọc giữa nguồn–SQL–cube và bàn giao mart đã chốt cho Trang.

```text
Tôi là Chi, phụ trách chương 4 và 5 của repo Coffee DW này.
Hãy đọc AGENTS.md, README.md, docs/START_HERE.md, docs/architecture.md,
docs/REPORT_MAP.md, docs/BASE_STATUS.md và checklist ch04_chi/ch05_chi;
sau đó đọc warehouse.py, learning/experiments, SQL02–04, ssis/ và ssas/.
Giải thích luồng staging–dimension–fact–mart, audit và xử lý lỗi.
Bắt đầu bằng TN03/TN04: chạy demo, thử tăng dần, phát lại, sửa số, dòng lỗi
và SCD; đối soát kết quả, rồi triển khai SQL Server/SSIS trước SSAS/OLAP.
Tái sử dụng base và giữ hợp đồng khóa/cột với Thanh/Trang. Làm trên nhánh
chi/ch04-05-etl-olap, cập nhật tests/checklist và lưu minh chứng thật.
queries.mdx còn là mẫu; phải khớp metadata của cube đã tạo trước khi chạy.
Không coi kết quả SQLite là bằng chứng triển khai SSIS/SSAS.
```

## Trang tiếp tục phần nào

Nhánh `trang/ch06-07-app-ai`; checklist `ch06_trang.md`, `ch07_trang.md`. Chạy forecast/dashboard, chốt KPI với Chi, tích hợp mart SQL Server khi sẵn sàng; thu benchmark TN07–10, tác vụ người dùng TN11 và kết quả dự báo TN12. HRU/TN13 là mở rộng đã có code mô hình chi phí, còn cần đo engine thật.

## Mỗi lần bàn giao

Gửi PR kèm: chương/TN đã làm; file chính; lệnh chạy; số đối soát; minh chứng; phần còn chờ. Người nhận cần biết có phải chạy ETL, process cube hoặc chạy forecast lại không. Chỉ đánh dấu đạt sau khi có bằng chứng theo checklist. Nếu schema thay đổi, cập nhật cả consumer và báo cho người phụ trách phần đó trong nội dung PR.
