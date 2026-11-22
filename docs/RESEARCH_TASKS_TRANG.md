# Các task nghiên cứu và đầu ra báo cáo của Trang

Ngày chốt bản nhiệm vụ: 15/11/2026. Trạng thái: kế hoạch, chưa tạo số đo mới trong lượt này. Phạm vi chương6 là nghiên cứu dự báo; chương7 là triển khai, kiểm chứng hệ thống và sử dụng. Làm trên `trang`, PR vào `dev`; không cập nhật `main` khi Trang chưa xác nhận OK.

Đây là nghiên cứu thực nghiệm ứng dụng và tái lập trên một snapshot lịch sử. Mục tiêu là trả lời câu hỏi bằng đối chứng và bằng chứng truy vết được, không bắt buộc tạo thuật toán mới hoặc chứng minh ML luôn thắng baseline. Code tham chiếu và một số kết quả đã có trong repo; lần nghiên cứu mới phải ghi rõ phần tái lập và phần mở rộng.

## 1 Câu hỏi nghiên cứu và quy tắc chung

| Mã | Câu hỏi | Bằng chứng trả lời |
| --- | --- | --- |
| RQ1 | Ridge có cải thiện dự báo Sales tháng tới so với tháng trước và trung bình ba tháng không | MAE validation để lựa chọn, kết quả test và sai số từng Market |
| RQ2 | Thay feature hoặc phương pháp đơn giản bổ sung có giúp không | Thực nghiệm mở rộng có kiểm soát trên cùng origin; ghi số cấu hình đã thử |
| RQ3 | Dự báo có thể tích hợp và sử dụng đúng trên kho/dashboard không | Đối soát từng ô, phiên bản dự báo, kiểm tra filter/export và tác vụ người dùng |
| RQ4 | Tổ chức truy vấn nào phù hợp workload dashboard | Đối chứng SQL Server, số đọc trang, median/p95, dung lượng và chi phí duy trì |

Mỗi task có ít nhất một bảng hoặc hình có giá trị giải thích. Task thiết kế có thể xuất bảng phương pháp hoặc sơ đồ thay vì ép có một biểu đồ số liệu. Các giá trị chưa chạy phải để trạng thái chưa đo, không điền số minh họa vào bảng kết quả thật.

## 2 Danh sách task nghiên cứu

| Task | Việc phải làm và mục đích | Bảng đầu ra | Hình đầu ra | Điều kiện hoàn thành |
| --- | --- | --- | --- | --- |
| R01 Bài toán và nghiên cứu liên quan | Chốt người dùng, target Sales/Market, horizon một tháng, giả thuyết và cách dùng; tổng hợp nguồn phương pháp | R01_questions.csv và R01_related_work.csv: câu hỏi, đối chứng, bằng chứng, tài liệu, cách áp dụng/giới hạn | R01_study_design: sơ đồ nguồn→kho→dự báo→đánh giá→dashboard | Target, phạm vi, giả thuyết và tiêu chí chốt trước khi so kết quả |
| R02 Kiểm toán dữ liệu đầu vào | Xác nhận snapshot và mart bàn giao từ Thanh/Chi; kiểm tra kiểu, thiếu, trùng, phụ thuộc, kỳ và tổng | R02_dataset_profile.csv, R02_quality_checks.csv | R02_month_coverage: ma trận kỳ–Market; ô thiếu khác0 | Truy được checksum/batch; source4248 dòng, mart96 ô trên snapshot gốc; số tiền khớp |
| R03 Tiền xử lý và tổng hợp | Giải mã ngày, giữ mã vùng chuỗi, chuẩn tên/kiểu, xử lý reject theo base, GROUP BY Market–tháng | R03_preprocessing_audit.csv, R03_monthly_sales.csv, R03_source_mart_reconciliation.csv | R03_preprocessing_flow: số dòng tại các bước, nhánh reject và mức tổng hợp | Không sửa raw, không tự sửa số kế toán; join/tổng hợp có đối soát và không mất grain |
| R04 Khám phá dữ liệu | Mô tả quy mô, mức dao động và thay đổi theo thời gian; phân biệt quan sát và giả thuyết | R04_descriptive_statistics.csv theo Market; R04_monthly_change.csv | R04_sales_history: bốn ô cùng trục thời gian; R04_sales_heatmap | EDA dùng thiết kế chỉ trên lịch sử ban đầu; ghi N và không suy mùa vụ chắc chắn từ hai năm |
| R05 Thiết kế kiểm định | Khóa ngày train/validation/test, lịch expanding origin, tiêu chí và cách xử lý bằng điểm | R05_split_manifest.csv, R05_origin_schedule.csv | R05_temporal_split: timeline; R05_rolling_origin: lịch train→target | Không random split; cùng target cho mọi phương pháp; khóa lựa chọn trước test |
| R06 Tạo đặc trưng và chuẩn hóa | Định nghĩa lag1/2/3, kiểm tra thời điểm feature được biết; fit scaler trên train từng origin | R06_feature_dictionary.csv, R06_supervised_preview.csv, R06_feature_row_counts.csv; thông số scaler của một origin minh họa | R06_feature_availability: sơ đồ lag→target; scatter lag–Sales là tùy chọn | Không lấy actual tháng đích, không fit scaler toàn bộ; số mẫu và các dòng chưa đủ lag được giải thích |
| R07 Tái lập phương pháp chuẩn | Chạy naive_last, MA3, Ridge alpha1 với lag123 trên một protocol cố định | R07_model_specification.csv, R07_reference_predictions.csv, R07_execution_audit.csv | R07_validation_forecasts: actual và ba phương pháp trong validation | Đủ dự báo, provenance, tests chống rò rỉ; baseline không bị thay đổi để hợp kết quả |
| R08 Mở rộng có kiểm soát, tùy chọn | Chọn tối đa1–2 mở rộng hoặc một trục ablation; chốt cấu hình trước xem test | R08_experiment_matrix.csv, R08_validation_metrics.csv | R08_ablation hoặc R08_validation_comparison | Cùng target và dữ liệu được biết; chỉ đổi yếu tố đã công bố, ghi toàn bộ cấu hình và cả kết quả kém |
| R09 Lựa chọn phương pháp | Xếp hạng bằng pooled validation MAE, xem thêm từng Market và baseline | R09_validation_leaderboard.csv, R09_selected_method.csv | R09_validation_mae: biểu đồ có nhãn và N; R09_market_validation_errors | Ghi nhận lựa chọn/feature/tham số trước đánh giá test, không đổi tiêu chí theo kết quả |
| R10 Đánh giá test và phân tích lỗi | Chấm phương pháp đã chọn, so baseline cùng kỳ, phân tích hướng lệch và các ca khó | R10_test_metrics.csv, R10_prediction_errors.csv, R10_largest_errors.csv | R10_actual_forecast: bốn Market, phân biệt validation/test; R10_test_error_heatmap | Báo MAE/RMSE/MAPE, N, từng Market; không retune rồi gọi cùng test là độc lập |
| R11 Dự báo kỳ tiếp theo và diễn giải sử dụng | Tái fit/cập nhật theo phương pháp đã khóa trên lịch sử khả dụng, tạo bốn dự báo01/2014 | R11_next_month.csv, R11_forecast_provenance.csv | R11_next_month_forecast: so với actual gần nhất, phân biệt điểm dự báo | Actual01/2014 để thiếu; có origin/trainend/version, không coi là dự báo hiện tại hay quyết định nhập hàng |
| R12 Tổng hợp kết luận nghiên cứu | Trả lời từng RQ, nêu kết quả âm, giới hạn, khả năng áp dụng và hướng tiếp | R12_findings_matrix.csv, R12_validity_limits.csv; research_conclusion.md | R12_evidence_summary hoặc dùng lại hình kết quả chủ đạo, không cần hình mới chỉ để đủ số | Mỗi kết luận dẫn tới bảng/hình/run cụ thể; không khẳng định nhân quả hay hiệu quả triển khai chưa đo |

R08 là mở rộng, không phải điều kiện bắt buộc để hoàn thành ba phương pháp của báo cáo. RQ2 chỉ được kết luận khi thực hiện R08; nếu không, ghi rõ ngoài phạm vi đã chạy.

R07–R09 chỉ dùng các đầu ra validation để thiết kế/lựa chọn. Hàm tham chiếu hiện tính cả validation và test trong một lần gọi; khi triển khai quy trình nghiên cứu cần tách hoặc kiểm soát bước công bố kết quả để chỉ mở phần test ở R10, sau khi đã lưu quyết định chọn. Giữ nguyên các tests tái lập tham chiếu; kết quả test đã được biết trước vẫn phải được thừa nhận như giới hạn ở R05.

## 3 Đặc tả kỹ các task dữ liệu trước mô hình

### R02 Bảng hồ sơ và kiểm tra

Dataset profile cần các cột: DatasetLevel, Scope, Rows, Columns, Markets, MonthsPerMarket, FirstMonth, LastMonth, SourceChecksum, BatchID. Phân biệt nguồn chi tiết và mart dự báo.

Tái sử dụng profile/mapping/ETL do Thanh và Chi phụ trách. Phần của Trang xác nhận hợp đồng đầu vào cho nghiên cứu và xuất bằng chứng phù hợp, không xây lại một pipeline xử lý nguồn khác với kho dùng chung.

Quality checks cần CheckID, DatasetLevel, Scope, Rule, ObservedValue, Status, Action, Notes. Có đủ kiểm tra ô thiếu, trùng grain, đầu tháng, liên tục kỳ, giá trị không hữu hạn, số âm và chênh giả thuyết kế toán. Thiếu dữ liệu và vi phạm nghiệp vụ không được trộn thành một loại lỗi.

Ma trận coverage tô ô có/thiếu dữ liệu; không dùng màu doanh số0 để biểu diễn thiếu. Nếu toàn bộ kỳ đều đủ, hình vẫn có ích để xác nhận phạm vi, nhưng không vẽ biểu đồ cột các lỗi đều0 chỉ để làm đẹp.

### R03 Bảng tiền xử lý và đối soát

Bảng tiền xử lý cần: Step, InputLevel, OutputLevel, RowsBefore, RowsAfter, ChangedRows, RejectedRows, Rule, Reason, EvidencePath. Mọi số đếm được lấy từ lần chạy thực; đổi số dòng do tổng hợp không phải mất dữ liệu.

Các mốc dưới đây là kỳ vọng từ snapshot gốc, chưa phải số đo mới của lượt lập task:

| Mức dữ liệu | Số dòng kỳ vọng | Cách diễn giải |
| --- | ---: | --- |
| Nguồn chi tiết hợp lệ | 4248 | Tháng × mã vùng × sản phẩm |
| Mart dự báo | 96 | 24 tháng ×4 Market |
| Bảng supervised có đủ lag123 trên toàn lịch sử | 84 | Mỗi Market chưa có lag ở ba kỳ đầu; không phải12 dòng lỗi nguồn |
| Mẫu fit Ridge tại origin đầu | 48 tổng,12 mỗi Market | 15 tháng đầu trừ ba kỳ tạo lag |

Giữ bảng monthly_sales đủ96 ô; không thay nó bằng bảng supervised84 dòng. Bảng feature minh họa có thể chứa các split với nhãn rõ, nhưng chỉ fit theo các mốc và phạm vi được cho phép.

Bảng đối soát cần MonthStart, Market, SourceSales, MartSales, Delta, Status; kiểm tra từng ô thay vì chỉ so tổng toàn chuỗi. Tiền xử lý không tự xóa Profit/Inventory âm, ép Sales=COGS+Margin hoặc tự điền kỳ thiếu bằng0.

### R04 Bảng thống kê và EDA

Bảng thống kê nên có Market, Scope, N, Min, Q1, Median, Mean, Q3, Max, Std, CV, FirstMonth, LastMonth. Bảng biến động có MonthStart, Market, Sales, PreviousMonthSales, AbsoluteChange, RelativeChange; mẫu0 để thiếu theo quy ước.

Đối với EDA dẫn tới lựa chọn feature/phương pháp, Scope là train_design, 01/2012–03/2013, N15 mỗi Market. Khi đã khóa thiết kế, có thể đưa hình mô tả toàn bộ24 tháng vào báo cáo với nhãn full_history_descriptive; không dùng nó để tuyên bố thiết kế hoàn toàn không tiếp xúc test.

Biểu đồ chính là bốn chuỗi doanh số theo Market, dùng cùng mốc thời gian và ghi rõ khi thang y khác nhau. Heatmap dùng giá trị thật có đơn vị; nếu chuẩn hóa theo Market để so hình dạng thì phải ghi rõ và không trình bày như doanh số gốc. Outlier là điểm cần kiểm tra, không mặc nhiên là lỗi để xóa.

### R05 Bảng chia tập và origin

Split chuẩn là15 kỳ01/2012–03/2013,6 kỳ validation04–09/2013,3 kỳ test10–12/2013. Mỗi phương pháp có24 dự báo validation và12 test trên4 Market.

Origin schedule cần Market, IssueMonth, ForecastMonth, Split, HistoryStart, TrainEnd, HistoryN, EffectiveFitN, FeatureSet. Với baseline không có bước fit hệ số, EffectiveFitN có thể để không áp dụng và ghi HistoryN. Trong test được dùng actual của kỳ test trước đã kết thúc tại origin tiếp theo; phương pháp/tham số phải giữ nguyên.

Kết quả tham chiếu trong báo cáo/tests đã được biết. Đây là tái lập protocol có thứ tự thời gian; không gọi test là một kiểm định mù mới. Nếu sau khi xem test còn thay mô hình dựa vào nó, công bố là mở rộng thăm dò và cần kỳ mới để đánh giá độc lập.

### R06 Bảng đặc trưng

Feature dictionary cần Feature, Formula, RequiredHistory, AvailableAtOrigin, Transformation, FitScope, MissingRule. Preview cần Market, TargetMonth, lag1, lag2, lag3, TargetSales, Split; hiển thị một số dòng liên tiếp để người đọc kiểm tra quan hệ tháng.

Giữ code chuẩn với lag123 và StandardScaler fit trên train. Không dùng các số thực hiện tháng đích hoặc Budget tương lai khi không biết lịch phát hành. Nếu thêm rolling mean, phải shift trước rolling.

Nếu R08 so lag1 với lag123 để tách tác động feature, dùng cùng origin và cùng tập target fit hợp lệ theo lag lớn nhất; nếu số mẫu fit khác nhau, phải công bố đó là một thay đổi khác cùng xảy ra. Không vẽ training loss theo epoch cho Ridge/naive/MA3 nếu thực tế phương pháp không có lịch epoch như vậy.

## 4 Task triển khai và kiểm chứng chương 7

| Task | Nội dung | Bảng và hình báo cáo bắt buộc | Điều kiện hoàn thành |
| --- | --- | --- | --- |
| V01 Truy vết và tái lập, làm song song từ R02 | RunID, commit, checksum, config, package versions, output paths; lưu ForecastSales đúng grain | V01_run_manifest.csv, V01_artifact_inventory.csv; sơ đồ actual và forecast được tổng hợp/nối đúng grain | Chạy lại được, không ghi đè lịch sử nghiên cứu, không nhân dòng khi join; đổi schema phải phối hợp Chi |
| V02 Dashboard và nghiệm thu sử dụng | Đưa dữ liệu/dự báo đã công bố vào Streamlit; kiểm tra KPI/filter/drill-down/export; thử tác vụ Excel/web | V02_reconciliation_cases.csv, V02_ux_trials.csv; ảnh giao diện thực chạy, biểu đồ thời gian và tỷ lệ đúng với N thật | App khớp SQL/nguồn; UX có người thử thật, thứ tự được ghi, không coi test tự động là người dùng thử |
| V03 Hiệu năng SQL Server | TN07–TN10: cùng dữ liệu/tham số, EXCEPT hai chiều,3 warm-up và15 lượt đo mỗi cấu hình; indexed view/partition/index | V03_raw_runs.csv, V03_benchmark_summary.csv; median/p95 và reads tách đơn vị, ảnh actual plans | Có engine/máy/plan/IO/TIME thật; ghi dung lượng/chi phí ghi; thời gian0 không suy ra speedup vô hạn |
| V04 HRU, tùy chọn | TN13: cuboid/workload/ngân sách và lựa chọn view theo lợi ích biên | V04_hru_rounds.csv; lattice và tiến trình lợi ích/ngân sách | Tách mô hình chi phí theo row khỏi số byte/thời gian SQL đo thật |

Độ tốt mô hình, thời gian truy vấn và thời gian người dùng hoàn thành tác vụ là ba khía cạnh riêng. Không dùng một số đo thay cho cả ba. V02 pilot ít người chỉ cho kết luận trong phạm vi nhóm thử; trình bày cả lượt thử và giới hạn, không tạo người dùng mô phỏng làm chứng cứ UX.

## 5 Chuẩn hình và bảng để đưa vào báo cáo

Mỗi task hoàn thành cần có code/lệnh tái lập, dữ liệu bảng gốc, hình/bảng đã trình bày, metadata và một đoạn nhận xét. Đoạn nhận xét trả lời hình/bảng cho thấy gì, căn cứ nào hỗ trợ, ảnh hưởng đến bước sau và giới hạn nào còn tồn tại. Task thiết kế dùng bảng cấu hình/sơ đồ có nhãn; task có số liệu phải xuất cả giá trị gốc.

| Thành phần | Quy ước |
| --- | --- |
| Hình tĩnh | PNG300dpi và PDF vector khi phù hợp; chữ đọc được ở kích thước chèn cuối, khoảng10–12pt; khổ ngang khoảng15–17cm hoặc theo mẫu Word |
| Bảng | CSV giữ độ chính xác, không chèn ký hiệu tiền chưa biết; bản trình bày HTML/Markdown hoặc bảng Word chỉnh được; không dùng screenshot terminal làm bảng khoa học |
| Thống nhất hình thức | Một palette xuyên suốt; cùng Market giữ cùng màu; phân biệt phương pháp/split bằng nét hoặc ký hiệu ngoài màu; không dùng hiệu ứng3D |
| Nhãn | Tên biến, đơn vị nguồn, phạm vi Market/thời gian, split, số mẫu N, chú giải và nguồn; ghi rõ khi dùng chuẩn hóa hoặc thang y khác nhau |
| Số làm tròn | Bảng trình bày thường2 chữ số cho metrics, quy định riêng cho tỷ lệ; tính/xếp hạng bằng số chưa làm tròn, không làm tròn đầu vào trước tính |
| Diễn giải sai số | Phân biệt sai số có dấu và tuyệt đối; MAPE cần quy ước actual0; MAE không phải khoảng dự báo95%; không gọi100%-MAPE là accuracy |
| Chọn kết quả | Lưu mọi cấu hình đã thử, không chỉ kết quả thắng; chốt theo validation trước test; kết quả kém hoặc không cải thiện vẫn được báo cáo |
| Kết quả nhỏ | Test chỉ12 dự báo,3 mỗi Market, có phụ thuộc thời gian; luôn ghi N và tránh kết luận mạnh từ hình hộp hoặc p-value không phù hợp |
| Báo cáo chính/phụ lục | Chọn hình/bảng trả lời RQ cho nội dung chính; bảng từng origin, dữ liệu dài và log đặt phụ lục. Mã Rxx/Vxx là mã làm việc, số hình/bảng Word chốt khi ghép |

Nên dùng công cụ vẽ tĩnh như Matplotlib cho hình xuất báo cáo; Plotly dùng cho tương tác dashboard. Không cần xuất lại mọi biểu đồ web thành ảnh trong báo cáo nếu không hỗ trợ kết luận. Việc xuất DOCX/PDF hoàn chỉnh sẽ có bước kiểm tra render riêng khi nhóm ghép báo cáo.

## 6 Tổ chức tệp dự kiến và nhật ký tiến độ

```text
results/research_trang/<run_id>/
  manifest.json
  protocol.json
  tables/       R02_dataset_profile.csv, R03_preprocessing_audit.csv, ...
  figures/      R04_sales_history.png, R04_sales_history.pdf, ...
  notes/        R01.md, R02.md, ..., R12.md
  models/       Chỉ khi cần lưu pipeline/model cuối có đủ metadata
  decision.md
```

Đây là cấu trúc dự kiến; base chưa có bộ xuất đầy đủ các artifact này. `results/` vẫn được ignore. Chỉ thêm minh chứng nhỏ có chọn lọc theo `results/README.md`; không đẩy toàn bộ output hoặc thay đổi ignore hàng loạt. Có thể tiếp tục công bố bản đã chọn vào `results/forecast/` cho dashboard, đồng thời giữ bản nghiên cứu theo run.

| Nhóm | Trạng thái ban đầu | Thứ tự |
| --- | --- | --- |
| R01–R06 | Chưa thực hiện theo bộ artifact nghiên cứu này | Chốt bài toán, dữ liệu, EDA, split và feature trước khi mở rộng mô hình |
| R07, R09–R12 | Có code/kết quả tham chiếu, chưa có đầy đủ bộ hình/bảng theo task | Tái lập thành run có minh chứng, chốt lựa chọn rồi đánh giá |
| R08 | Tùy chọn, chưa làm | Chọn phạm vi sau khi pipeline tham chiếu ổn định |
| V01 | Base có audit dữ liệu, còn cần audit từng research run | Chuẩn bị cùng R02, hoàn thiện khi lưu forecast |
| V02–V03 | Có base/hướng dẫn, còn cần nghiệm thu native/người thử | Làm sau hoặc song song khi dữ liệu/instance sẵn sàng |
| V04 | Có mô hình chi phí tham chiếu, chưa đủ số đo SQL | Ưu tiên sau nội dung bắt buộc |

Không đánh dấu checklist chương hoàn tất chỉ vì đã viết kế hoạch. Bước bắt đầu hợp lý là R01–R03 cùng V01; sau đó R04–R06, rồi mới chạy đợt mô hình có kiểm soát. Tài liệu này chi tiết hóa [kế hoạch ứng dụng AI](PLAN_TRANG_AI.md), không thay các yêu cầu gốc trong hai checklist chương.

## 7 Nguồn phương pháp

Cập nhật thực hiện 16/11/2026: EDA nguồn R02–R04 và bảng lag minh họa R06 đã có bộ xuất tại [explore](../explore/README.md): 40 CSV, 19 bộ hình PNG/PDF/SVG, phân tích và manifest; 38 test Python đạt. Phần bàn giao/đối soát mart của Chi trong R02–R03 vẫn chờ. R05 có hình lịch chia tập, chưa công bố quyết định chọn mô hình mới; R06 chưa fit scaler. Không đánh dấu R07–R10 training/tuning mới từ EDA này.

Mốc tiếp theo sau EDA: [thực nghiệm cơ sở](../experiments/baseline/README.md) đã tái lập R05–R07, R09–R11 trên nguồn CSV: protocol, feature, scaler audit từng origin, validation → tệp lựa chọn → test, phân tích lỗi và dự báo 01/2014. Đây là tái lập cấu hình có sẵn, không phải R08 dò tham số hoặc test mù mới. R02–R03 đối soát kho của Chi và các tác vụ native/UX vẫn chưa nghiệm thu từ bộ này.

R08 mở rộng sau cơ sở: [thử siêu tham số](../experiments/tuning/README.md) đã chạy đủ 7 cấu hình (Naive; MA2/3/6; Ridge alpha0.1/1/10, lag123 cố định), 168 prediction validation/84 test, 120 lần fit Ridge tính cả 12 lần cuối. Có 31 CSV, 14 bộ hình PNG/PDF/SVG, thông số từng origin, 12 pipeline Ridge cuối, 28 trạng thái, báo cáo/nhận xét/lời thuyết trình và manifest; 53 test Python đạt. MA3 tiếp tục được chọn bằng MAE validation223,28, không cải thiện so baseline đã chọn. MA6 có MAE test152,00 nhưng không được chọn bằng test. Test đã biết từ trước nên công bố đây là mở rộng thăm dò. Bước sau là tích hợp kết quả/giải thích/thuyết trình; chưa nghiệm thu R02–R03 mart, native hoặc UX từ lần này.

- [Forecasting Principles and Practice](https://otexts.com/fpp3/toolbox.html): workflow dự báo, baseline, đánh giá điểm và rolling origin.
- [scikit-learn Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html): fit preprocessing trên train và tránh rò rỉ dữ liệu.
- Yêu cầu repo: `docs/architecture.md`, `docs/REPORT_MAP.md`, `docs/chapters/ch06_trang.md`, `docs/chapters/ch07_trang.md`.
