# Chương 7. Triển khai và đánh giá hệ thống

## 7.1 Phạm vi triển khai

Hệ thống có hai giao diện: dashboard phân tích tại `apps/dashboard/app.py` và demo giải thích dự báo tại `apps/forecast_demo/app.py`. Dashboard phục vụ KPI, xu hướng, đi sâu State/Product, tồn kho/chi phí, xuất CSV và dự báo. Demo bổ sung công thức, kiểm chứng lịch sử và lời thuyết minh cho từng bộ lọc. Python/SQLite là bản tham chiếu dùng phát triển và đối soát. Ngày 19/11/2026 đã kiểm chứng mart/consumer SQL Server trên database biệt lập `CoffeeDW_Trang_20261119`; không dùng database này để tuyên bố Chi đã nghiệm thu SSIS/SSAS.

Luồng nguồn bất biến → chuẩn hóa/kiểm tra → staging–dimension–fact → mart → dashboard/dự báo giữ nguyên grain và các hợp đồng tại [kiến trúc](../architecture.md). Nghiên cứu được chạy ngoài luồng đọc trang, sau đó công bố tệp kết quả và phiên bản. Nhờ vậy thao tác xem không làm fit lại mô hình hoặc tự thay đổi quyết định chọn.

## 7.2 Quy tắc hiển thị và lọc

Sales, BudgetSales, Profit và các chi phí được tổng theo cùng kỳ và Market. Gap = SUM(Sales) − SUM(BudgetSales); tỷ lệ đạt ngân sách = SUM(Sales)/SUM(BudgetSales), mẫu bằng 0 giữ thiếu. Xếp nhóm theo Gap có dấu tăng dần, sau đó tên để ổn định khi bằng điểm; không xếp bằng trị tuyệt đối rồi gọi là hụt lớn nhất.

Khi đi sâu từ Market xuống State/Product, giữ nguyên khoảng tháng và thị trường đang xét. CSV xuất phải phản ánh đúng phần đang xem. Inventory là snapshot: lấy kỳ cuối trong khoảng đang chọn, rồi cộng theo địa bàn/sản phẩm trong kỳ đó; không cộng tồn kho xuyên 24 tháng. Số âm được giữ để đối soát. Nguồn chưa mô tả đơn vị tiền/tồn kho nên giao diện không tự gán đơn vị.

Trang AI có lịch đánh giá riêng: lọc Market áp dụng vào dự báo, còn khoảng tháng phân tích không làm dịch lịch train/validation/test đã công bố. Actual 01/2014 thiếu được hiển thị là chưa có, không biến thành 0. Nội dung chi tiết phải nhất quán với [README dashboard](../../apps/dashboard/README.md) và [README demo](../../apps/forecast_demo/README.md).

## 7.3 Kiểm chứng số liệu và ứng dụng — TN11

Các ca đối soát cố định để phát hiện số cũ hoặc lẫn bộ lọc:

| Ca | Sales | BudgetSales | Gap | Điều cần kiểm tra |
| --- | ---: | ---: | ---: | --- |
| West, 01/2012 | 10.453 | 9.460 | +993 | Lọc một kỳ và một thị trường |
| East, 01/2012 | 6.780 | 6.180 | +600 | Đổi thị trường, số phải đổi theo |
| Quay về West, 01/2012 | 10.453 | 9.460 | +993 | Không giữ kết quả East |
| South, 08/2013 | 4.601 | 4.610 | −9 | Đi sâu sản phẩm; Colombian Gap −268 |

Bản tham chiếu đã có AppTest cho luồng bộ lọc và các trang. Bộ briefing kiểm tra 48 case và đối soát 96 ô nghiên cứu–SQLite; hồ sơ QA lưu 61 test Python và 10 test JavaScript ở lượt tích hợp trước. Đây là kết quả tự động đã lưu, không tự thay cho nghiệm thu trên trình duyệt hoặc người dùng thật. Kết quả chạy mới và bằng chứng UI ở lượt hoàn thiện được ghi tại [checklist chương 7](../chapters/ch07_trang.md).

Ngày 19/11/2026 đã thực hiện tiếp **12/12 ca nghiệm thu bằng agent trên trình duyệt**, dashboard đọc backend SQL Server biệt lập. Hồ sơ có JSON, ảnh giao diện, cây accessibility và ba CSV thực tải từ trình duyệt. Các kết quả chính:

| Nhóm kiểm tra trực tiếp | Kết quả quan sát |
| --- | --- |
| West → East → West, 01/2012 | Khớp đủ ba KPI trong bảng đối soát, quay lại West không lẫn số East |
| Drill-down và CSV West 01/2012 | Bảng sản phẩm 12 dòng, Colombian Gap −276 đứng đầu; CSV chi tiết 56 dòng, Sales 10.453, đúng kỳ và Market |
| Không chọn Market | Có thông báo không có dữ liệu, không hiển thị KPI giả bằng 0 |
| Inventory West 01–02/2012 | Dùng đúng snapshot 02/2012, Inventory 38.751 |
| Dự báo native | MA3, West 01/2014 = 11.593, actual thiếu; tải CSV dự báo chín dòng lịch sử thuộc bộ lọc |
| Demo giải thích và actual | Công thức `(11.596 + 11.300 + 11.883) / 3 = 11.593`; nút actual 01/2014 khóa, chủ động mở 10/2013 trả 11.596 |
| Âm thanh và thực nghiệm | Play làm elapsed/progress tăng, Pause dừng; trang thực nghiệm đọc kết quả tuning, TN12 và benchmark đã tạo sẵn |

Bằng chứng: [12 ca và giới hạn](../../results/trang_completion/browser/acceptance.json), [ảnh West](../../results/trang_completion/browser/dashboard_west_replay.png), [ảnh East](../../results/trang_completion/browser/dashboard_east_201201.png), [CSV sản phẩm tải thật](../../results/trang_completion/browser/downloaded_products.csv), [CSV chi tiết](../../results/trang_completion/browser/downloaded_detail.csv), [ảnh Inventory](../../results/trang_completion/browser/inventory_feb.png), [ảnh dự báo native](../../results/trang_completion/browser/native_forecast.png). Kiểm tra điều khiển audio xác nhận hoạt động kỹ thuật; độ tự nhiên giọng nói **chưa được người nghe đánh giá**. Số người tham gia UX vẫn bằng 0. Lỗi kết nối, kho hỏng/rỗng được kiểm riêng bằng AppTest, không được gộp thành ca mất kết nối thực trên trình duyệt.

Phép kiểm chứng native ngày 19/11/2026 đối soát 4.248 dòng ở grain gốc, đủ 11 số đo, các thuộc tính chiều và 96 ô Market–tháng. Tổng native khớp Sales 819.811, BudgetSales 746.160 và Profit 259.543. Luồng phát hành và phát lại forecast giữ 112 dòng không trùng khóa, bốn actual tương lai NULL, phương pháp chính vẫn MA3; sai số làm tròn khi lưu DECIMAL tối đa theo ngưỡng 0,00005. Bằng chứng và CSV gốc ở [verification.json](../../results/trang_completion/native_serving/verification.json) và [monthly_reconciliation.csv](../../results/trang_completion/native_serving/monthly_reconciliation.csv). Phạm vi kết luận là serving/integration trên database thử biệt lập.

Ca rỗng phải cho biết không có bản ghi trong phạm vi. Mất hoặc hỏng nguồn phải báo lỗi truy cập/thiết lập, không hiển thị KPI 0. Với slider chỉ liệt kê tháng có trong kho, người dùng không thể chọn khoảng ngoài nguồn; ca ngoài miền thời gian được kiểm tra bằng cách lọc dữ liệu ở tầng truy vấn/test hoặc dùng snapshot thử biệt lập. Không sửa CSV gốc để tạo ca lỗi.

Chất lượng giọng thuyết minh phải phân biệt kiểm tra WAV có tín hiệu, thao tác phát/đổi đoạn, và đánh giá tự nhiên bởi người nghe. Hai kiểm tra đầu có thể tự động hóa hoặc kiểm tra UI; nhận xét chủ quan về chất giọng cần phiên người nghe thực.

## 7.4 Thiết kế benchmark native — TN07–TN10

Benchmark dùng bản sao riêng trong `bench`; dữ liệu nhân tải không được đưa vào kho phục vụ hoặc dùng tăng cỡ mẫu dự báo. Trước khi đo phải đối soát số dòng, tổng và EXCEPT hai chiều giữa hai phương án. Mọi khác biệt ngoài yếu tố đang thử phải được kiểm soát hoặc công bố.

| Thực nghiệm | Đối chứng | Bằng chứng cần thu |
| --- | --- | --- |
| TN07 | Tập dữ liệu và workload chuẩn | Cấu hình máy/engine, hệ số nhân, số dòng/tổng, EXCEPT hai chiều |
| TN08 | GROUP BY và indexed view | SET options, SCHEMABINDING, COUNT_BIG, actual plan, reads, CPU/elapsed, bytes và chi phí ghi |
| TN09 | Bảng thường và partition RANGE RIGHT | Cùng dữ liệu/index, lọc một tháng/toàn khoảng, actual partitions được truy cập |
| TN10 | Có/không nonclustered index | Lát cắt hẹp/rộng, selectivity, seek/scan/lookup và plan |

Mỗi cặp có ba lượt warm-up và 15 lượt đo mỗi phương án theo thứ tự xen kẽ. Lưu raw runs để tính lại median và p95 theo cùng quy ước; tách logical reads, CPU và elapsed vì đơn vị và ý nghĩa khác nhau. Thu actual plan và IO/TIME từ SQL Server thật. Nếu thời gian chạm độ phân giải đồng hồ, không kết luận speedup vô hạn hoặc khẳng định tốc độ chỉ từ plan.

### Kết quả native ngày 19 tháng 11 năm 2026

Đã đo trên SQL Server Express 15.0.2210.4, instance local, database biệt lập `CoffeeDW_Trang_20261119`. Mỗi bảng bench có 2.124.000 dòng từ 500 bản sao nguồn, tổng Sales 409.905.500; EXCEPT hai chiều bằng 0 cho sáu bảng. Tập chạy có 216 bản ghi: 36 warm-up và 180 lượt chính, tương ứng sáu cặp × 15 lượt/phương án. Sau đo ghi có rollback, số dòng và tổng được đối soát lại.

| Phép thử A → B | Median ms A | Median ms B | p95 ms A / B | Median logical reads A / B |
| --- | ---: | ---: | ---: | ---: |
| TN08 đọc GROUP BY → indexed view | 898 | 3 | 4.585,40 / 5,50 | 11.367 / 9 |
| TN08 chèn 4.248 dòng không view → có view | 10 | 29 | 11,90 / 43,50 | 4.354 / 17.031 |
| TN09 một tháng bảng thường → partition | 107 | 27 | 127,80 / 29,00 | 11.367 / 474 |
| TN09 toàn kỳ bảng thường → partition | 728 | 739 | 835,60 / 909,10 | 11.367 / 11.376 |
| TN10 lát hẹp không NCI → có NCI | 96 | 0 | 124,30 / 0 | 11.367 / 6 |
| TN10 lát rộng không NCI → có NCI | 346 | 300 | 368,00 / 389,60 | 11.367 / 8.958 |

Thời gian bảng là elapsed của statement trên server lấy từ actual plan; thời gian client gồm truyền kết quả/plan được lưu riêng trong CSV. Phép chèn 4.248 dòng được rollback và chỉ so chi phí INSERT statement, không coi là throughput giao dịch đã commit. Indexed view đọc được chỉ định `NOEXPAND`, phương án A dùng `EXPAND VIEWS`; kết luận thể hiện lợi ích khi sử dụng materialization rõ ràng trong workload này, không khẳng định optimizer luôn tự chọn view.

Actual plan xác nhận đọc `vSalesAgg`/`CX_vSalesAgg` ở TN08B và cập nhật `vWriteAgg` khi ghi. TN09B truy cập 1/24 partition khi lọc một tháng và 24/24 khi đọc toàn kỳ; cùng PRIMARY nên không kết luận về phân bố đĩa. TN10B là Index Seek ở lát hẹp và Index Scan ở lát rộng. Lát hẹp khớp 500/2.124.000 dòng (khoảng 0,02354%). Bộ index bao phủ nên không tạo Lookup chỉ để minh họa.

Dung lượng reserved của indexed view đọc là 200 KB, used 72 KB; NCI của `IdxB` là 71.688 KB reserved, 71.664 KB used, ngoài heap nền 90.952 KB reserved. Phép đo cho thấy lợi ích đọc đi kèm chi phí lưu trữ và duy trì: indexed view giảm reads nhưng phép chèn có view tăng từ 10 lên 29 ms trong snapshot này. Partition chỉ giúp lát lọc phù hợp: toàn kỳ không cải thiện median. NCI lát rộng giảm median elapsed nhưng p95 cao hơn A, nên không diễn giải thành thắng nhất quán mọi lượt.

Máy dùng chung và Express có áp lực bộ nhớ. Các truy vấn A/B đều dùng `MAXDOP 1, MAX_GRANT_PERCENT=1` ở phạm vi query; không thay server setting hoặc flush cache toàn máy. p95 GROUP BY rất cao so median cho thấy biến thiên nền. Giá trị 0 ms của seek là giới hạn độ phân giải millisecond, không phải thời gian thực bằng 0 hoặc speedup vô hạn; median client của B là 3,16 ms. Không suy kết quả này thành tốc độ sản xuất hoặc UX.

Bằng chứng: [summary](../../results/native_trang/20261119/benchmark_summary.csv), [raw 216 lượt](../../results/native_trang/20261119/benchmark_runs.csv), [môi trường](../../results/native_trang/20261119/environment.json), [actual plans và IO/TIME](../../results/native_trang/20261119/plans/), [storage](../../results/native_trang/20261119/storage.csv), [bàn giao và lệnh tái lập](../TRANG_NATIVE_HANDOFF.md). Các script nền ở `sql/sqlserver/05_bench_setup.sql` đến `09_benchmark_protocol.sql`; runner thực ở `scripts/run_native_benchmarks.py`.

### TN13 mở rộng HRU và kiểm chứng SQL

Đã chạy mở rộng trên tám cuboid MRP/MR/MP/RP/M/R/P/tổng, trong đó M là tháng, R là Market và P là Product. Cardinality SQL lần lượt là MRP 1.008, MR 96, MP 312, RP 42, M 24, R 4, P 13 và tổng 1. Với workload và ngân sách **giả định 300 group-row**, greedy chọn ALL → R → M → MR → RP, dùng 167 group-row và còn 133. Lợi ích biên được tính lại sau mỗi lượt; mô hình dùng base 4.248 dòng nguồn, khác tập bench 2.124.000 dòng dùng đo hiệu năng.

| Truy vấn | Nguồn B được chọn | Median ms A / B | Median reads A / B |
| --- | --- | ---: | ---: |
| MR | MR | 719 / 0 | 11.367 / 1 |
| RP | RP | 693 / 0 | 11.367 / 1 |
| M | M | 552 / 0 | 11.367 / 1 |
| R | R | 915 / 0 | 11.367 / 1 |
| Tổng | ALL | 325 / 0 | 11.367 / 1 |
| MP | BASE, không có ancestor đã chọn | 596 / 631 | 11.367 / 11.367 |

Replay gồm 216 actual plans/IO-TIME, trong đó 180 lượt chính, sáu cặp đều khớp checksum kết quả. Phương án B chỉ dùng các materialization đã chọn có thể trả lời truy vấn; MP cần 312 group-row, không vừa ngân sách 300 và không có ancestor đã chọn nên quay về base, không có lợi ích đo được. Các giá trị 0 ms là sát độ phân giải; median client ở các truy vấn nhỏ khoảng 1–2 ms, không báo speedup vô hạn.

Các cuboid là **bảng tổng hợp thường riêng trong bench**, không phải indexed view tự duy trì. Tạo đủ tám candidate để khảo sát cardinality/storage không có nghĩa B được dùng mọi candidate. Trọng số và ngân sách group-row là giả định; cardinality, byte, reads và thời gian SQL là số đo riêng. Chưa đo refresh/maintenance HRU; không lấy phép đo indexed view TN08 gán cho cơ chế này.

Bằng chứng: [protocol](../../results/native_trang/20261119/hru/protocol.json), [các vòng greedy](../../results/native_trang/20261119/hru/hru_rounds.csv), [mapping workload](../../results/native_trang/20261119/hru/workload_mapping.csv), [summary SQL](../../results/native_trang/20261119/hru/benchmark_summary.csv), [báo cáo HRU](../../results/native_trang/20261119/hru/report.html).

## 7.5 Nghiệm thu sử dụng Excel và Streamlit

Giả thuyết ứng dụng là người dùng trả lời câu hỏi quản trị đúng với ít thời gian tra cứu hơn. Thiết kế trong cùng người dùng: mỗi người làm ba loại nhiệm vụ trên Excel PivotTable và Streamlit với cùng snapshot, KPI và đơn vị. Bộ A/B thay kỳ hoặc thị trường giữa hai công cụ để giảm nhớ đáp án, đồng thời đổi công cụ làm trước giữa người tham gia.

Ba loại tác vụ gồm tìm Market có Sales lớn nhất, đi sâu State và kiểm tra tổng, tìm Market có Gap thấp nhất rồi sản phẩm đóng góp và xuất CSV. Người điều phối dùng đáp án tính từ nguồn, ghi mã ẩn danh, thứ tự, câu trả lời, đúng/sai, số giây và số lần trợ giúp. Bắt đầu bấm giờ sau khi đọc đề xong; dừng khi chốt đáp án. Tỷ lệ đúng tính trên mọi lượt; median giây chỉ tính các lượt đúng. Báo cả người/lượt chưa hoàn thành.

Bộ tác vụ, phiếu trống, đáp án và lệnh tổng hợp được chuẩn bị tại [protocol UX](ux_protocol.md). **Chưa có phiên người tham gia thì không có kết luận hiệu quả UX.** Không đưa tác vụ do agent thực hiện vào dữ liệu người thử. A/B không đồng nhất hoàn toàn về số nhóm và độ khó; đây là giới hạn cần báo ngay cả khi đã đổi thứ tự.

## 7.6 Bàn giao và tái lập

Ngày19/11/2026 đã diễn tập trên snapshot131 file nguồn có kiểm kê và môi trường Python ảo tạo mới, không dùng system-site-packages hoặc sao chép database/kết quả cũ. Cài mới extras dev/explore/sqlserver và kiểm `pip check` sạch; CLI demo/forecast tái tạo đúng4248 dòng/112 forecast;113 pytest và10 frontend test đạt. [Hồ sơ tái lập sạch](../../results/trang_completion/clean_snapshot/verification.json) lưu inventory, constraints, install log và test log. Đây là clean working-source snapshot của thay đổi cục bộ, chưa phải checkout từ commit Git đã bàn giao; voice/model/audio không được tái tải trong lần này.

Người nhận chạy lại từ mã nguồn, ghi phiên bản môi trường và checksum, sau đó kiểm tra số gốc, dự báo, giao diện và các tệp xuất. [Hướng dẫn tái lập](reproduction_handoff.md) tách lệnh bắt buộc, tùy chọn audio và phần native cần môi trường riêng. Khởi chạy trên workspace có sẵn không được gọi là đã chạy từ checkout sạch; chỉ đánh dấu điều kiện đó khi tạo môi trường biệt lập và lưu log tương ứng.

Phép tích hợp native của Trang đã chứng minh hợp đồng mart/forecast trên database thử. Khi chuyển sang bản bàn giao chính thức của Chi, vẫn cần xác nhận mart, quyền đọc consumer, batch và checksum tương ứng; SSIS/SSAS cần bằng chứng do người phụ trách chạy. Git dùng nhánh `trang`, PR vào `dev`; không đưa credential, môi trường ảo, DB hoặc output lớn lên Git. `main` giữ nguyên đến khi có chấp thuận rõ ràng mới của Trang.

## 7.7 Kết luận triển khai

Ứng dụng tham chiếu đã nối được nghiên cứu dự báo với dữ liệu và cách giải thích có truy vết. Tính đúng số liệu, độ tốt dự báo, hiệu năng SQL và khả năng sử dụng là bốn mục đánh giá độc lập. Chương này chỉ kết luận trong phạm vi bằng chứng hiện có; mục còn chờ native hoặc người tham gia được liệt kê rõ để tránh mô tả prototype như hệ thống đã nghiệm thu toàn bộ.
