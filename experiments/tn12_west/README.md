# TN12 West — ví dụ riêng trong sổ tay

Tái lập mục **TN12** của `docs/Huong_dan_Coffee_Chains_Kaggle.docx` trên nguồn bất biến
`data/raw/Coffee.csv`. Thực nghiệm này độc lập với lịch chính của chương 6 và không
thay mô hình đang phục vụ dashboard/demo.

## Chạy từng bước

Tại root, dùng môi trường đã cài theo README dự án:

```powershell
.\.venv\Scripts\python experiments/tn12_west/run.py
.\.venv\Scripts\python -m pytest -p no:cacheprovider tests/test_tn12_west.py
```

Nếu thiếu thư viện vẽ, cài extra `.[explore]` theo hướng dẫn root.
Script hỗ trợ `--source` và `--output`; nguồn phải có đúng 24 tháng West
01/2012–12/2013, grain duy nhất và Sales hữu hạn. Thiếu tháng báo lỗi, không điền 0.

1. Đọc nguồn bằng `source.read_source`; dừng nếu có reject; tổng hợp Market–tháng bằng hàm chung.
2. Lấy West, kiểm tra 24 kỳ liên tục; tính lag1, lag2 và mean3 từ ba tháng **trước** target.
3. Dự báo một bước cho 07–12/2013. Mỗi origin fit StandardScaler và Ridge(alpha=1)
   trên các feature/target thuộc lịch sử đã biết. So với tháng trước và MA3 trên cùng target.
4. Tính MAE/RMSE/MAPE và chọn MAE nhỏ nhất; bằng điểm theo thứ tự Naive → MA3 → Ridge.
5. Dùng phương pháp chọn với lịch sử đến 12/2013 để dự báo West 01/2014; actual giữ thiếu.
6. Xuất bảng, hình PNG 300 dpi/PDF/SVG, phân tích, HTML và manifest checksum.

## Kết quả đã tái lập ngày 19/11/2026

| Phương pháp | N | MAE | RMSE |
| --- | ---: | ---: | ---: |
| Tháng trước | 6 | **309,00** | **357,86** |
| Trung bình ba tháng | 6 | 396,72 | 423,88 |
| Ridge lag1/lag2/mean3, alpha=1 | 6 | 320,18 | 379,00 |

Kết quả khớp ví dụ gốc. Chọn **tháng trước**; West 01/2014 = **11.883** đơn vị Sales
nguồn, chưa có actual để đo sai số. Không có căn cứ thay baseline bằng Ridge trong
ví dụ này. Origin đầu dùng 18 tháng/15 mẫu fit; origin cuối dùng 23 tháng/20 mẫu fit.

**Giới hạn:** sáu kỳ vừa dùng so sánh vừa dùng chọn, không có test độc lập. Đây là tái lập
ví dụ đã biết trong sổ tay, không phải kiểm định mù mới. Chỉ một thị trường và sáu lỗi,
không suy rộng tới hiệu quả kinh doanh hay các Market khác.

Protocol chính vẫn chọn **MA3** trên validation 04–09/2013 gộp bốn Market rồi đánh giá
test 10–12/2013, Ridge lag123. MAE của hai protocol không so trực tiếp. Module TN12
không gọi hàm ghi kho và không thay `ForecastSales`, bundle demo hoặc kết quả chính.

## Đầu ra để đưa vào báo cáo

Sau khi chạy, mở [báo cáo](results/report.html) hoặc [phân tích](results/analysis.md).

| Tệp | Nội dung |
| --- | --- |
| `protocol.json` | Mốc, feature, alpha, tiêu chí và giới hạn |
| `west_monthly.csv`, `features.csv` | Chuỗi 24 tháng, feature với ba tháng đầu thiếu lag |
| `six_origin_comparison.csv` | Sáu dòng actual và ba phương pháp |
| `predictions.csv`, `metrics.csv` | 18 dự báo với origin/version/error và chỉ số chưa làm tròn |
| `origins.csv` | HistoryN/FitN, feature tại origin, mốc fit đầu/cuối |
| `fit_audit.csv` | Mean/scale/hệ số của 3 feature × 6 origin |
| `future.csv` | Một dự báo 01/2014, actual trống, version TN12 riêng |
| `figures/TN12_eval.*` | Bảng sáu kỳ và chỉ số — đúng hình sổ tay yêu cầu |
| `figures/TN12_chart.*` | Actual và phương pháp chọn; điểm tương lai riêng |
| `manifest.json` | SHA256 nguồn trước/sau, Git, mã, phiên bản và hash artifact |

Đầu ra `results/` được ignore theo quy ước dự án. Không sửa ignore để đưa cả output lên Git.

## Kiểm tra đã thực hiện

- **8 test đạt:** khớp từng dự báo với đoạn Python gốc độc lập; thay actual tháng đích/tương lai
  không đổi dự báo đã phát hành; scaler chỉ dùng 15–20 mẫu quá khứ; chặn tháng thiếu,
  trùng grain, số không hữu hạn và ngày không phải đầu tháng; checksum nguồn và hash output;
  actual tương lai thiếu, version tách riêng.
- Đã chạy script, đọc các chỉ số và xem trực tiếp hai PNG; sửa vị trí chú giải để không chồng chú thích nguồn.
- Đây là bằng chứng Python/CSV, không thay đối soát mart SQL Server của Chi hoặc nghiệm thu UX.
