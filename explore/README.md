# Explore data — phần của Trang

**Làm được ngay khi chưa có code của Chi.** Bộ EDA đọc `data/raw/Coffee.csv` qua `src/coffee_dw/source.py`, không gọi kho SQLite, SQL Server, SSIS hoặc SSAS. Mã nguồn CSV giữ nguyên; đây là kiểm tra và mô tả đầu vào cho nghiên cứu, chưa chứng minh kho/ETL của Chi đã hoàn tất.

## Chạy

Tại root repo, dùng môi trường đã có:

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev,explore]"
.\.venv\Scripts\python explore/run.py
```

Nếu Matplotlib đã có thì chạy trực tiếp lệnh thứ hai. Có thể chọn một **bản sao** CSV để kiểm tra bằng `--source <path>`; mặc định scope và protocol dành cho snapshot Coffee 01/2012–12/2013 của repo.

## Mở gì trước?

1. [results/report.html](results/report.html): báo cáo HTML mở cục bộ bằng trình duyệt, chứa nhận xét, bảng và toàn bộ hình; không cần chạy server.
2. [results/analysis.md](results/analysis.md): phân tích tiếng Việt, kết luận có giới hạn và ý nghĩa cho bước thử mô hình.
3. [results/train_design/figures](results/train_design/figures): hình dùng cho khám phá phục vụ thiết kế mô hình.
4. [results/full_history_descriptive/figures](results/full_history_descriptive/figures): hình toàn kỳ cho phần mô tả tổng quan của báo cáo.
5. [results/manifest.json](results/manifest.json): số liệu nguồn, checksum, phạm vi, phiên bản thư viện và danh sách tệp.

Các link `results/` có sau khi chạy; output được ignore và chưa commit/push. Không sửa ignore để đẩy toàn bộ hình lên Git; khi nhóm cần công bố minh chứng, chọn đúng vài tệp nhỏ đã kiểm tra.

## Cấu trúc đầu ra

```text
explore/
  run.py                         Lệnh chạy EDA
  results/                       Sinh cục bộ, không đưa toàn bộ lên Git
    report.html                  Báo cáo có hình, bảng, nhận xét
    analysis.md                  Phân tích và giới hạn bằng tiếng Việt
    manifest.json                Dấu vết tái lập và checksum
    tables/                      Hồ sơ 20 cột, chất lượng, reject, anomaly, audit
    figures/                     Coverage, quy trình tiền xử lý, lịch chia tập
    train_design/
      tables/                    Các bảng từ 15 tháng đầu
      figures/                   8 bộ hình PNG/PDF/SVG
    full_history_descriptive/
      tables/                    Các bảng mô tả đủ 24 tháng
      figures/                   8 bộ hình PNG/PDF/SVG
```

Mỗi scope có chuỗi tháng, thống kê phân vị/mean/std/CV, biến động tháng, bảng lag, tương quan, cờ IQR, tổng hợp Market/State/Product/State×Product, đối soát tổng hợp và bảng nhận xét. `InventoryLastMonth` trong bảng tổng hợp chỉ lấy kỳ cuối của scope, không cộng xuyên thời gian. `BudgetAchievement` và `ProfitRatio` là tỷ lệ dạng 0–1; CSV giữ độ chính xác, không thêm ký hiệu tiền.

## Những hình nên chọn cho báo cáo

| Hình | Giải thích gì? |
| --- | --- |
| `figures/02_preprocessing_flow` | Từ 4.248 dòng nguồn → 96 ô tháng–Market → 60 ô thiết kế → 48 dòng đủ lag |
| `train_design/figures/01_sales_history` | Doanh số biến động ra sao trên lịch sử dùng thiết kế |
| `train_design/figures/02_sales_heatmap` | Các tháng cao/thấp theo từng Market |
| `train_design/figures/05_monthly_distribution` | Khác biệt quy mô và phân bố Sales tháng |
| `train_design/figures/06_lag_correlations` | Liên hệ mô tả giữa doanh số và 1–3 tháng trước, có số mẫu N |
| `full_history_descriptive/figures/03_market_budget` | Kết quả kinh doanh toàn kỳ so với ngân sách |
| `full_history_descriptive/figures/04_product_ranking` | Sản phẩm nào có doanh số lớn hoặc hụt ngân sách lợi nhuận |

Mỗi hình có PNG 300 dpi để chèn Word/slide, PDF và SVG vector để phóng to. Dùng Times New Roman nếu máy có font; fallback DejaVu Serif trên máy khác. Giữ cùng màu cho cùng Market. Đọc nhãn đơn vị: một số hình hiển thị nghìn đơn vị; biểu đồ đường dùng thang Y riêng và ghi rõ trong hình.

## Tránh nhầm phần khám phá với kết quả mô hình

- `train_design`: 01/2012–03/2013, 15 tháng mỗi Market; có 12 dòng đủ lag123 mỗi Market.
- `full_history_descriptive`: 24 tháng, chỉ mô tả toàn bộ snapshot, không dùng để tuyên bố thiết kế chưa tiếp xúc test. Repo đã có kết quả test tham chiếu.
- Chưa fit scaler, training, tuning, chọn mô hình hay tự tạo thêm doanh số.
- Tương quan không chứng minh nguyên nhân. Số đo thực hiện cùng tháng chưa phải feature biết trước để dự báo tháng đó.
- Profit/Inventory âm, cờ IQR và chênh kế toán được giữ lại để rà soát; không tự xóa, thay bằng 0 hoặc suy ra số lần hết hàng.
- 4.248 dòng là quan sát tổng hợp, không phải hóa đơn; nguồn chưa có số ly/đơn giá hay đơn vị tiền tệ được xác nhận.

## Khi Chi bàn giao

Dùng `results/full_history_descriptive/tables/monthly_market.csv` làm đáp án đối soát nguồn. So từng khóa `MonthStart × Market`, cả Sales, BudgetSales, Profit và snapshot Inventory cùng tháng. Kiểm tra nguồn gốc batch, tên cột và chính sách reject; nếu dữ liệu kho thay đổi hợp lệ phải ghi nguyên nhân và chạy lại EDA. `aggregation_reconciliation.csv` hiện chỉ xác nhận tổng hợp EDA bảo toàn số nguồn; cột `ComparedWithWarehouse=False` nói rõ chưa kiểm tra kho của Chi.

Mã tính nằm ở `src/coffee_dw/exploration.py`; mã vẽ ở `src/coffee_dw/exploration_plots.py`.

## Kiểm tra

```powershell
.\.venv\Scripts\python -m pytest tests/test_exploration.py
```

Kiểm tra các mốc nguồn/grain, 60/96 ô tháng–Market, 48/84 dòng đủ lag, tổng hợp Inventory đúng kỳ, tỷ lệ có trọng số, thiếu tháng không biến thành 0, tách reject và dữ liệu tương lai không làm đổi thống kê thiết kế.

## Lần chạy đã kiểm tra — 16/11/2026

- Nguồn gốc: 4.248 dòng hợp lệ, 0 reject, 24 tháng, 4 Market; Sales 819.811, BudgetSales 746.160, Profit 259.543. Checksum nguồn trước/sau giống nhau.
- Sinh **40 bảng CSV và 19 bộ hình**, mỗi bộ có PNG/PDF/SVG, kèm `report.html`, `analysis.md` và `manifest.json`.
- **38 test Python đạt**, trong đó 5 test mới cho EDA. Đã kiểm tra 99 tệp trong manifest, checksum từng tệp, link nội bộ của HTML và độ phân giải 300 dpi của 19 PNG.
- Đã xem bộ hình tổng hợp và kiểm tra riêng các hình heatmap/lag: chữ Times New Roman, ghi rõ đơn vị và N, ô ngoài scope giữ xám. Đây là QA hình tĩnh, chưa phải thử nghiệm UX hoặc xác nhận kho của Chi.
- Bước tiếp theo: đọc nhận xét trên `train_design`, chốt đầu vào/tham số trước khi chạy mô hình; nhận mart từ Chi rồi đối soát từng ô. Chưa có training/tuning mới trong đầu việc này.
