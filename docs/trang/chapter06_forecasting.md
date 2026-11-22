# Chương 6. Dự báo doanh số theo thị trường

## 6.1 Mục tiêu và phạm vi sử dụng

Nghiên cứu dự báo Sales tháng kế tiếp cho từng Market, phục vụ việc rà soát kế hoạch doanh số. Câu hỏi chính là phương pháp Ridge có cải thiện so với lấy doanh số tháng trước và trung bình ba tháng hay không. Một kết quả không vượt baseline vẫn có giá trị: hệ thống cần phục vụ phương pháp có bằng chứng phù hợp thay vì mặc định chọn mô hình phức tạp.

Đầu ra là một dự báo điểm cho mỗi thị trường và tháng mục tiêu, kèm tháng phát hành, lịch sử dùng để tính, phương pháp, phiên bản và sai số đã đánh giá. Nguồn không chứa hóa đơn, số ly, giá bán, định mức nguyên liệu, tồn an toàn hoặc lịch nhân sự. Vì vậy kết quả chưa trực tiếp quyết định đơn nhập hàng hay lịch làm việc. Đơn vị Sales giữ nguyên theo nguồn, không tự gán VND hoặc USD.

## 6.2 Dữ liệu và đối soát đầu vào

Snapshot `Coffee.csv` có 4.248 dòng ở grain tháng × mã vùng × sản phẩm; đây không phải 4.248 đơn hàng. Tổng hợp theo Market–tháng thu được 96 ô, gồm bốn thị trường và 24 tháng liên tục từ 01/2012 đến 12/2013. Tổng nguồn đối soát là Sales 819.811, BudgetSales 746.160 và Profit 259.543. Mã vùng được giữ dạng chuỗi; ngày Excel dùng origin `1899-12-30`; 11 số đo nguồn, số âm và chênh đẳng thức kế toán được giữ nguyên.

Các ô thiếu phải được điều tra, không tự thay bằng 0. Tập thiết kế EDA chỉ dùng 15 tháng đầu; đồ thị toàn bộ 24 tháng được gắn nhãn mô tả hồi cứu. Snapshot nguồn được truy vết bằng SHA256 `929bdcc7fd8f6bf21607618e7474df0683af6412b32b8c5af39a40e89b62ffce`. Bộ briefing đã đối soát từng ô nghiên cứu với kho SQLite. Ngày 19/11/2026, phép tích hợp native trên database biệt lập `CoffeeDW_Trang_20261119` đối soát tiếp 4.248 dòng, đủ 11 số đo và 96 ô Market–tháng với bản tham chiếu; [verification.json](../../results/trang_completion/native_serving/verification.json) ghi trạng thái `passed`. Đây là bằng chứng mart/consumer SQL Server trong môi trường thử của Trang, chưa phải nghiệm thu package SSIS hoặc cube do Chi triển khai.

Bằng chứng: [EDA và hình](../../explore/README.md), [hồ sơ nguồn](../../experiments/baseline/results/01_input/source_profile.csv), [96 ô đầu vào](../../experiments/baseline/results/01_input/monthly_market.csv), [đối soát kho–nghiên cứu](../../experiments/briefing/results/01_reconciliation/monthly_reconciliation.csv).

## 6.3 Thiết kế đánh giá theo thời gian

| Vai trò | Khoảng thời gian | Số tháng | Số dự báo mỗi phương pháp |
| --- | --- | ---: | ---: |
| Lịch sử khởi tạo | 01/2012–03/2013 | 15 | Không chấm như ngoài mẫu |
| Validation để chọn phương pháp | 04/2013–09/2013 | 6 | 24 trên bốn Market |
| Test báo cáo sau lựa chọn | 10/2013–12/2013 | 3 | 12 trên bốn Market |
| Kỳ ngoài nguồn | 01/2014 | 1 | 4, actual chưa có |

Mỗi mốc dự báo một bước trước bằng cửa sổ lịch sử mở rộng. Ví dụ, dự báo 10/2013 dùng actual đến hết 09/2013; dự báo 11/2013 được dùng actual 10/2013 vì tháng đó đã kết thúc ở origin mới. Không dùng actual của tháng mục tiêu trong feature hoặc chuẩn hóa. Phương pháp được chọn bằng MAE validation gộp bốn thị trường và giữ nguyên khi đánh giá test.

Tệp lựa chọn được lưu trước pha tính test trong lần tái lập. Tuy nhiên, kết quả test tham chiếu đã được biết trước từ base; vòng mở rộng bảy cấu hình được công bố là thăm dò trên test đã biết, không phải kiểm định mù mới. Chưa có giai đoạn dữ liệu mới để đánh giá độc lập lựa chọn sau thăm dò.

Bằng chứng: [split](../../experiments/baseline/results/02_protocol/split_manifest.csv), [lịch origin](../../experiments/baseline/results/03_validation/origin_schedule.csv), [hình rolling origin](../../experiments/baseline/results/02_protocol/figures/01_rolling_origin.png), [nhật ký thứ tự thử tham số](../../experiments/tuning/results/06_summary/execution_events.csv).

## 6.4 Phương pháp và đặc trưng

Naive dùng Sales tháng liền trước. MA3 tính `Prediction(t) = [Sales(t−1) + Sales(t−2) + Sales(t−3)] / 3`, không học hệ số. Ridge chuẩn dùng ba lag `lag1/lag2/lag3`, StandardScaler và Ridge alpha=1; scaler và hệ số được fit riêng trên quá khứ của từng Market tại từng origin. Với 15 tháng khởi tạo, Ridge có 12 mẫu đủ ba lag cho mỗi Market.

Vòng mở rộng giữ nguyên ngày split và lag123, thử bảy cấu hình: Naive; MA window=2,3,6; Ridge alpha=0,1; 1; 10. Solver SVD được cố định để tái lập, không được dò. Mọi cấu hình đều được lưu, kể cả cấu hình kém hơn. Không tạo loss/epoch cho phương pháp không có lịch huấn luyện theo epoch.

Bộ thử tham số có 168 dự báo validation, 84 dự báo test và 120 lần fit Ridge tính cả 12 pipeline cuối. Naive/MA lưu trạng thái quy tắc; Ridge lưu cả preprocessing và mô hình, có kiểm tra nạp lại. Các bảng feature và audit nằm trong [protocol](../../experiments/tuning/results/01_protocol/) và [audit validation](../../experiments/tuning/results/02_validation/).

## 6.5 Tiêu chí đánh giá và lựa chọn

MAE là trung bình sai số tuyệt đối, dùng làm tiêu chí chọn; RMSE nhạy hơn với sai số lớn. MAPE chỉ tính ở actual khác 0 và công bố số mẫu tương ứng. Sai số có dấu trong bộ kết quả là Prediction − Actual. Tất cả số tính/xếp hạng dùng độ chính xác đầy đủ; bảng dưới làm tròn hai chữ số.

| Cấu hình | MAE validation, N=24 | MAE test, N=12 | Được chọn |
| --- | ---: | ---: | --- |
| MA3 | 223,28 | 225,22 | Có |
| MA6 | 231,31 | 152,00 | Không |
| MA2 | 244,15 | 213,42 | Không |
| Naive | 258,83 | 221,75 | Không |
| Ridge alpha=10 | 275,22 | 200,59 | Không |
| Ridge alpha=1 | 292,93 | 213,33 | Không |
| Ridge alpha=0,1 | 298,87 | 215,95 | Không |

MA3 có MAE validation thấp nhất, giảm 13,74% so với Naive. Vòng thử tham số không cải thiện MAE validation so với MA3 đã chọn ở bước cơ sở: mức cải thiện là 0%. Ridge alpha=10 tốt nhất trong nhóm Ridge nhưng chưa vượt MA3 trên tiêu chí lựa chọn. MA6 có MAE test thấp nhất trong bảng hồi cứu, song không đổi phương pháp phục vụ sau khi xem test.

MA3 trên test đạt RMSE 265,41 và MAPE 2,40%. So Naive cùng 12 điểm test, MAE của MA3 kém 1,57%, trong khi RMSE tốt hơn 6,97%. Do vậy không kết luận MA3 thắng mọi chỉ số, và càng không kết luận ML luôn tốt hơn phương pháp đơn giản.

Bằng chứng: [leaderboard](../../experiments/tuning/results/02_validation/leaderboard.csv), [mọi cấu hình và metric](../../experiments/tuning/results/04_comparison/all_configurations.csv), [quyết định trước test](../../experiments/tuning/results/02_validation/decision.md).

### Mở rộng thăm dò sau phản hồi về chất lượng dự báo

Đã tái lập bảy cấu hình cũ và thêm hai họ đơn giản: seasonal naive12 và SES với alpha cố định0,2/0,5/0,8, tổng11 cấu hình. Protocol được lưu trước chấm và quyết định chọn lưu trước pha test trong lượt này. Tuy vậy cả validation và test cũ đều đã được biết; đây là mở rộng thăm dò, không phải kiểm định mù mới. Không thay nguồn hoặc gói forecast đang phục vụ.

| Cấu hình | MAE validation, N=24 | MAE test đã biết, N=12 |
| --- | ---: | ---: |
| MA3 chính thức | 223,28 | 225,22 |
| SES alpha0,5 | 230,40 | 204,88 |
| Seasonal naive12 | 233,96 | 537,08 |
| SES alpha0,8 | 246,88 | 218,43 |
| SES alpha0,2 | 256,74 | 161,11 |

Không có cấu hình mới vượt MA3 trên tiêu chí validation. SES0,5 kém MA3 khoảng3,19% ở validation; dù có test MAE thấp hơn9,03%, không đổi lựa chọn theo test đã biết. Seasonal naive12 không ổn định trên test. Phân tích bỏ từng tháng khỏi bảng chấm validation cho MA3 thắng4/6 lượt và seasonal12 thắng2/6; đây là độ nhạy của bảng chấm, không phải sáu kiểm định độc lập. Bằng chứng: [review11 cấu hình](../../experiments/forecast_review/README.md), [leaderboard](../../experiments/forecast_review/results/validation_leaderboard.csv), [summary/provenance](../../experiments/forecast_review/results/summary.json).

Nguồn chỉ có24 điểm thời gian/Market. Không sinh thêm doanh số để làm tăng cỡ mẫu thực hay dựng actual tương lai. Có thể nghiên cứu mô phỏng riêng cho stress test hoặc phương pháp bootstrap có protocol đánh giá riêng; bộ này có0 quan sát synthetic. Hướng tiếp theo là bổ sung lịch sử thực và thử mô hình dùng chung thông tin giữa các chuỗi từ dữ liệu thật, với origin/split đồng bộ. Chưa coi các hướng đó là kết quả đã chạy. [FAQ bảo vệ](forecast_questions.md) giải thích khoảng tháng xem, horizon một bước và khoảng bất định.

## 6.6 Phân tích lỗi theo thị trường

Hình chính dùng hai đường **thực tế và MA3 đã chọn** trên04–12/2013: sáu kỳ validation để lựa chọn và ba kỳ test để báo cáo, nền tách rõ. Việc mở rộng khoảng nhìn không tạo thêm test hoặc một dự báo chín tháng từ cùng origin; từng điểm vẫn chỉ dùng quá khứ trước tháng đích. [Bộ hình đối chiếu mới](../../results/trang_forecast_review/report.html) có bảng12 lỗi test, độ lệch có dấu theo%, và hồ sơ West11/2013. [Hình cũ so cả ba phương pháp](../../experiments/baseline/results/04_test/figures/01_actual_forecast.png) giữ nguyên làm phụ lục đối chứng.

| Market | N test | MAE | RMSE | MAPE (%) |
| --- | ---: | ---: | ---: | ---: |
| Central | 3 | 259,78 | 296,03 | 2,35 |
| East | 3 | 205,33 | 205,67 | 2,71 |
| South | 3 | 58,11 | 61,98 | 1,28 |
| West | 3 | 377,67 | 384,69 | 3,27 |

West có sai số tuyệt đối lớn nhất trong bốn thị trường ở test này. Ca West–11/2013 dự báo 11.777,33 so actual 11.300, lệch +477,33; ở 12/2013, MA3 lại dự báo thấp hơn actual 352. Điều này phù hợp với việc trung bình ba tháng phản ứng chậm trước thay đổi, nhưng chưa đủ để suy ra nguyên nhân kinh doanh. Nguồn không cung cấp bằng chứng về thời tiết, giá hoặc khuyến mãi để quy kết nguyên nhân.

Mỗi Market chỉ có ba điểm test nên thứ hạng và MAPE có thể thay đổi khi có kỳ mới. Không diễn giải MAE thành biên sai số đảm bảo hoặc khoảng dự báo 95%; không dùng `100% − MAPE` làm “độ chính xác”. Bằng chứng: [metric theo Market](../../experiments/baseline/results/04_test/selected_metrics.csv), [các ca sai số lớn](../../experiments/baseline/results/04_test/largest_selected_errors.csv), [hình actual–forecast](../../experiments/baseline/results/04_test/figures/01_actual_forecast.png).

## 6.7 Phát hành dự báo và giải thích trên ứng dụng

Sau đánh giá, cập nhật MA3 bằng lịch sử đến 12/2013 để phát hành dự báo 01/2014. Các giá trị sau là mô phỏng ngoài nguồn lịch sử, không phải dự báo cho ngày thực hiện báo cáo 19/11/2026.

| Market | Forecast 01/2014 | Actual 01/2014 |
| --- | ---: | --- |
| Central | 11.174,33 | Chưa có |
| East | 7.585,33 | Chưa có |
| South | 4.537,33 | Chưa có |
| West | 11.593,00 | Chưa có |

Ví dụ West: `(11.596 + 11.300 + 11.883) / 3 = 11.593`. Demo hiển thị ba tháng đầu vào và công thức trực tiếp, kèm sáu kỳ validation đã biết trước origin để người xem đánh giá giới hạn. Phần thuyết minh nối bối cảnh kinh doanh, dự báo, cơ chế, sai số và điều kiện rà soát. Không dùng test tương lai trong lời đọc như dữ kiện đã biết tại origin. Đối chứng Ridge dùng phân rã mức nền và đóng góp feature, không gọi đó là quan hệ nhân quả.

Forecast giữ grain Market × ForecastMonth × IssueMonth × ModelName × ModelVersion. Actual phải tổng hợp lên Market–tháng trước khi ghép; không nối mọi phiên bản forecast vào fact chi tiết rồi SUM. Trang AI đọc kết quả đã phát hành, không huấn luyện khi mở trang.

Bằng chứng: [bốn dự báo kỳ tới](../../experiments/baseline/results/05_future/next_month.csv), [hồ sơ West](../../experiments/briefing/results/02_story/cases/west_201401_moving_average_3.md), [hình giải thích West](../../experiments/briefing/results/02_story/figures/west_201401_moving_average_3.png), [hướng dẫn demo](../../apps/forecast_demo/README.md).

## 6.8 Phép thử TN12 West và kết luận

Ví dụ TN12 của sổ tay sử dụng West, sáu kỳ 07–12/2013 và feature lag1/lag2/mean3. Ngày 19/11/2026 đã tái lập riêng với scaler và Ridge alpha1 chỉ fit quá khứ ở mỗi origin. Kết quả:

| Phương pháp TN12 West | N | MAE | RMSE |
| --- | ---: | ---: | ---: |
| Tháng trước | 6 | 309,00 | 357,86 |
| Trung bình ba tháng | 6 | 396,72 | 423,88 |
| Ridge lag1/lag2/mean3 | 6 | 320,18 | 379,00 |

Theo MAE, ví dụ này chọn tháng trước và dự báo West 01/2014 là 11.883; actual chưa có. Sáu kỳ vừa so sánh vừa chọn nên không có test độc lập. Origin đầu có 18 tháng lịch sử/15 mẫu fit; origin cuối 23 tháng/20 mẫu fit. Tám test kiểm tra đã đạt, gồm đối chiếu đoạn Python gốc, fit quá khứ, chống actual tương lai và các ca đầu vào lỗi. Đây là protocol riêng; không nhập metric hoặc dự báo của nó vào bản phục vụ MA3 của chương6. Bằng chứng: [TN12 README](../../experiments/tn12_west/README.md), [metric](../../experiments/tn12_west/results/metrics.csv), [bảng sáu origin](../../experiments/tn12_west/results/six_origin_comparison.csv).

Kết luận trên snapshot hiện có là phục vụ MA3 theo tiêu chí validation đã chốt. Kết quả đủ để minh họa luồng kho dữ liệu → dự báo → ứng dụng có truy vết, nhưng lịch sử 24 tháng, test nhỏ và test đã biết giới hạn khả năng tổng quát hóa. Bước tiếp theo là theo dõi dự báo đã phát hành khi có actual mới, nhận bàn giao SSIS/SSAS từ Chi và thu bằng chứng sử dụng bằng người tham gia thực.
