# Tái lập và bàn giao phần Trang

Ngày lập hồ sơ: **19/11/2026**. Thực hiện từ root repo trên nhánh `trang`. Giữ `main` nguyên trạng. Đọc [AGENTS](../../AGENTS.md), [kiến trúc](../architecture.md), [chương6](../chapters/ch06_trang.md) và [chương7](../chapters/ch07_trang.md) trước khi thay đổi.

## 1. Kiểm tra trước khi chạy

```powershell
git status --short
git branch --show-current
git log -1 --format="%h %s"
```

Không chuyển nhánh hoặc dọn file khi có thay đổi chưa phân loại. Không in `.env` hoặc connection string vào log bàn giao. Ghi Python/package versions, checksum nguồn và commit vào manifest phù hợp. Trạng thái working tree dirty cần công bố vì chỉ commit hash chưa đủ tái tạo bản đang chạy.

## 2. Cài môi trường và chạy bản tham chiếu

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
.\.venv\Scripts\python -m pip install -e ".[dev,explore]"
.\.venv\Scripts\python -m coffee_dw.cli demo
.\.venv\Scripts\python -m coffee_dw.cli forecast
.\.venv\Scripts\python -m pytest
```

Kỳ vọng snapshot gốc: 4.248 dòng, 24 tháng, Sales819811/BudgetSales746160/Profit259543; không coi giá trị kỳ vọng là kết quả chạy cho đến khi có log. `demo` có thể bỏ qua snapshot đã nạp, nên lần xác nhận độc lập dùng đường dẫn DB mới theo tùy chọn CLI; không xóa kho của người khác.

## 3. Tái lập nghiên cứu và gói thuyết trình

```powershell
.\.venv\Scripts\python explore/run.py
.\.venv\Scripts\python experiments/baseline/run.py
.\.venv\Scripts\python experiments/tuning/run.py
.\.venv\Scripts\python experiments/briefing/run.py
.\.venv\Scripts\python experiments/briefing/verify.py
.\.venv\Scripts\python experiments/forecast_review/run.py
.\.venv\Scripts\python scripts/render_forecast_review.py
.\.venv\Scripts\python scripts/build_trang_report.py
```

Baseline/tuning đọc snapshot nguồn qua logic chuẩn hóa chung. Briefing cần kho đã nạp và kết quả tuning; nó kiểm checksum cùng 96 ô trước xuất gói. Bước chạy briefing không có `--voice` không tạo WAV mới; tránh dùng lần đó để kết luận đã nghiệm thu audio. Muốn có giọng đọc:

```powershell
.\.venv\Scripts\python -m pip install -e ".[voice]"
.\.venv\Scripts\python experiments/briefing/run.py --voice --download-voice
node --test tests/test_presenter_frontend.js
```

Chỉ lần đầu thiếu model cần `--download-voice` (khoảng63MB theo README demo). TTS là thành phần bên thứ ba; giữ model card/ghi nhận nguồn. Hình/case report nằm trong `experiments/*/results/`, bundle/audio phục vụ nằm trong `results/forecast_demo/`. Không commit toàn bộ các đầu ra này.

Chạy protocol TN12 West riêng bằng:

```powershell
.\.venv\Scripts\python experiments/tn12_west/run.py
.\.venv\Scripts\python -m pytest -p no:cacheprovider tests/test_tn12_west.py
```

Đối chiếu [hướng dẫn TN12](../../experiments/tn12_west/README.md). TN12 chọn Naive trên sáu kỳ West, không thay MA3 của protocol 15/6/3 chính.

## 4. Mở hai ứng dụng

Chạy trong hai terminal riêng:

```powershell
.\.venv\Scripts\python -m streamlit run apps/dashboard/app.py --server.port 8501
```

```powershell
.\.venv\Scripts\python -m streamlit run apps/forecast_demo/app.py --server.port 8502
```

Hoặc dùng launcher Windows để bật cả hai ứng dụng và mở trình duyệt:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_trang_demo.ps1 -Backend sqlite
```

Để dashboard đọc mart SQL Server thử đã nạp và đã publish forecast:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_trang_demo.ps1 -Backend sqlserver -NativeDatabase CoffeeDW_Trang_20261119
```

Launcher đặt `COFFEE_DW_BACKEND` cho tiến trình con. Nếu chưa có biến `COFFEE_DW_SQLSERVER_CONNECTION`, nó dùng ODBC18/Windows auth vào instance local `.` và database chỉ định, không ghi credential hoặc sửa `.env`. Nếu biến kết nối đã tồn tại thì giữ cấu hình đó; cần xác nhận đúng database trước khi chạy. `-NoBrowser` chỉ bật server. Launcher không thay tiến trình đã chiếm cổng; muốn đổi backend phải dừng đúng server của dự án rồi chạy lại và kiểm tra nhãn nguồn trên dashboard. Demo thuyết minh dùng bundle đã chuẩn bị và cơ chế kiểm fingerprint riêng, không tự chuyển mọi tài sản nghiên cứu sang SQL chỉ vì đổi backend dashboard.

Kiểm tra health chỉ xác nhận server còn hoạt động. Phiên nghiệm thu UI phải kiểm bộ lọc, số, bảng, CSV, biểu đồ, ca rỗng/lỗi và audio tương ứng. Chụp ảnh có bộ lọc và kết quả trong cùng khung, tránh chỉ chụp KPI không rõ phạm vi. Nếu import cũ còn bị giữ trong tiến trình Streamlit, dừng đúng tiến trình của ứng dụng rồi chạy lại, không tắt mọi Python trên máy.

## 5. Chuẩn bị và tổng hợp UX

```powershell
.\.venv\Scripts\python scripts/prepare_trang_acceptance.py
.\.venv\Scripts\python -m pytest tests/test_acceptance.py
.\.venv\Scripts\python scripts/prepare_trang_acceptance.py --trials results/trang_acceptance/ux_trials.csv
```

Lượt chuẩn bị 19/11/2026 xác nhận 4.248 dòng, nguồn không thay đổi và tạo **0** trial người dùng. Tám kiểm tra riêng của module nghiệm thu đạt. Trước khi có người thử, đầu ra tổng hợp phải là `not_measured`, không có tỷ lệ đúng hoặc median được tạo giả. Cách tổ chức phiên và chấm ở [protocol UX](ux_protocol.md).

## 6. Hợp đồng bàn giao native với Chi

Ngày 19/11/2026 đã chạy [verify_native_serving.py](../../scripts/verify_native_serving.py) trên database biệt lập `CoffeeDW_Trang_20261119`: 4.248 dòng/11 số đo/96 ô khớp tham chiếu, phát hành và phát lại 112 dòng forecast không trùng, bốn actual tương lai NULL. Xem [kết quả](../../results/trang_completion/native_serving/verification.json). Để tái lập, đặt `COFFEE_DW_SQLSERVER_CONNECTION` trong cấu hình cục bộ trỏ đúng database đã tạo bằng schema nhóm, không in giá trị kết nối ra log; script chỉ công bố forecast, không nạp fact nghiệp vụ:

```powershell
.\.venv\Scripts\python scripts/verify_native_serving.py --help
```

Đối soát này không thay nghiệm thu SSIS/SSAS hoặc bàn giao chính thức từ Chi. Khi đổi database/batch, chạy đối soát lại theo hợp đồng dưới đây.

Benchmark TN07–TN10 đã chạy native với2.124.000 dòng/bảng và180 lượt chính; đọc [bàn giao native](../TRANG_NATIVE_HANDOFF.md) để tái lập vào database thử mới. Không chạy lại ghi đè output đã công bố. Bộ nguyên trạng có summary, raw, actual plans, IO/TIME, storage, checksum và EXCEPT hai chiều; không chỉ sao bảng median vào báo cáo mà bỏ giới hạn môi trường.

TN13 cũng đã replay sáu cặp trên SQL Server với180 lượt chính; kết quả ở `results/native_trang/20261119/hru/`. Chỉ tái lập sau khi chuẩn bị base bench và dùng database/output mới nếu materialization đã tồn tại. Bảng tổng hợp HRU không tự refresh; ngân sách300 group-row là giả định, không phải300 byte hoặc mức dung lượng đo. Lệnh và giới hạn ở cùng tài liệu bàn giao native.

| Đầu vào Chi bàn giao | Trang cần xác nhận |
| --- | --- |
| Instance/database, driver, quyền đọc mart; credential giữ ngoài Git | Kết nối được bằng cấu hình an toàn, không ghi password vào log |
| `mart.vw_Detail`, `vw_MarketPeriod`, `vw_MarketProductPeriod` theo kiến trúc | Tên cột, kiểu, khóa duy nhất; tổng và từng ô 96 Market–tháng khớp SQLite/nguồn |
| Batch/checksum/audit nguồn, đường đi reject | Chạy forecast trên đúng snapshot và phát hiện kết quả cũ |
| Đích forecast theo hợp đồng | Giữ grain phát hành, chọn phiên bản rõ; join actual ở Market–tháng không fan-out |
| Log/plan và cấu hình SQL Server phục vụ benchmark | Đối chứng độc lập, raw runs và actual plan; không nhận số thời gian chưa đo |
| Project/log SSIS và cube/MDX do Chi chủ trì | Đối soát consumer, không tự tuyên bố đã deploy/process nếu chưa có bằng chứng |

Các truy vấn từ bộ lọc phải truyền tham số; tài khoản ứng dụng chỉ đọc phần phục vụ. Công bố forecast chạy qua bước phát hành riêng được cấp quyền thích hợp, không để thao tác xem trang ghi vào fact.

## 7. Diễn tập checkout sạch

Ngày19/11/2026 đã chạy thành công **clean working-source snapshot với venv mới** bằng `python scripts/verify_trang_snapshot.py prepare` rồi `python scripts/verify_trang_snapshot.py verify`:131 file nguồn được kiểm kê SHA256, không mang theo .git/.env/DB/output/model/audio; cài mới extras dev/explore/sqlserver, pip check sạch; CLI demo/forecast tạo lại4248 dòng và112 forecast. Trong môi trường mới,113 pytest và10 frontend test đạt. [Verification và log](../../results/trang_completion/clean_snapshot/verification.json) ghi rõ không phải committed Git checkout và không tái tải voice/model. Đây là bằng chứng dựng từ source sạch; bước checkout từ commit đã chốt còn thực hiện khi bàn giao Git.

Chỉ thực hiện sau khi bộ mã cần bàn giao đã được đưa vào commit/PR hoặc snapshot biệt lập có kiểm kê, vì file untracked không xuất hiện trong checkout từ Git. Không đánh dấu đã tái lập sạch chỉ vì `.venv` hiện tại chạy được.

Trong thư mục biệt lập: lấy nhánh/commit đã chốt, tạo venv mới, cài đúng extras, chạy các lệnh ở mục2–5, kiểm checksum và output, mở UI và ghi log. Có thể dùng nguồn CSV trong repo; không sao chép database hoặc cache hiện có để gọi đó là dựng lại từ đầu. Ghi rõ node/TTS/model có được cài mới hay dùng cache; nếu chỉ chạy không audio, công bố giới hạn đó.

## 8. Chốt Git và nghiệm thu

Rà diff từng file, chạy test phù hợp và kiểm link. Chỉ stage code/docs/tests cùng minh chứng nhỏ đã kiểm theo `results/README.md`; không stage `.env`, `.venv`, cache, DB, model/audio hoặc toàn bộ output. Xem `git diff --cached` và danh sách staged trước commit. Push nhánh `trang`, PR base `dev`; không merge/đẩy `main` khi chưa có chấp thuận rõ ràng mới của Trang.

Phiếu bàn giao cuối ghi: file sửa, lệnh tái lập, log kiểm tra, phần đã chạy, phần còn chờ và người nhận. Ghi riêng trạng thái **nghiên cứu**, **UI**, **SQL Server**, **UX** và **checkout sạch** để không dùng một kiểm tra thay cho toàn bộ.
