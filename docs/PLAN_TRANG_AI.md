# Kế hoạch thực hiện dự báo và ứng dụng cho phần việc của Trang

Ngày lập: 15/11/2026. Phạm vi: chương 6 và phần tích hợp AI/dashboard của chương 7. Đây là kế hoạch; chưa chạy thêm mô hình hoặc tạo số đo mới trong lượt lập kế hoạch này. Làm trên nhánh `trang`, tích hợp vào `dev`; giữ nguyên `main` đến khi Trang xác nhận OK.

Danh sách task nghiên cứu, bảng/hình bắt buộc và tiêu chí hoàn thành được chi tiết hóa trong [RESEARCH_TASKS_TRANG](RESEARCH_TASKS_TRANG.md).

## 1 Mục tiêu thực tế

Xây một quy trình dự báo Sales tháng kế tiếp cho từng Market từ dữ liệu kho đã đối soát. Người dùng chính là quản lý kinh doanh: xem mức doanh số dự kiến, nhận diện thị trường cần rà soát kế hoạch và theo dõi dự báo trước đây đã lệch bao nhiêu.

| Câu hỏi quản lý | Đầu ra hệ thống | Cách sử dụng |
| --- | --- | --- |
| Tháng tới mỗi thị trường có thể đạt mức Sales nào | Một dự báo/Market/kỳ phát hành, có tên phương pháp | Tham khảo khi lập và rà soát kế hoạch doanh số |
| Dự báo có đáng dùng hơn lấy doanh số tháng trước không | Sai số ngoài mẫu của phương pháp và baseline trên cùng kỳ | Quyết định có đưa ML vào phục vụ hay giữ cách đơn giản |
| Thị trường/kỳ nào dự báo thường lệch nhiều | Bảng sai số từng Market–tháng, chiều lệch và biểu đồ | Ưu tiên rà soát dữ liệu và giả định kế hoạch |
| Dự báo hiện tại khác kế hoạch đã phê duyệt bao nhiêu | Chênh forecast–budget nếu có budget được biết tại lúc phát hành | Gợi ý điểm cần xem xét, chưa kết luận nguyên nhân |

Ví dụ minh họa, không phải kết quả Coffee: nếu dự báo là 10000 đơn vị Sales và kế hoạch đã phê duyệt là 11000 thì hệ thống hiển thị chênh -1000 để quản lý rà soát. Không tự kết luận phải tăng Marketing hay nhập thêm một lượng hàng cụ thể.

Nguồn không có số ly, giá bán, hóa đơn, định mức nguyên liệu, tồn an toàn, thời gian cung ứng hay giờ công. Vì vậy dự báo doanh số chưa trực tiếp tạo được đơn nhập hàng SKU hoặc lịch nhân viên. Muốn tiến tới các quyết định đó cần bổ sung dữ liệu nghiệp vụ và hàm chi phí. Nguồn cũng chưa công bố đơn vị tiền tệ.

## 2 Quy mô và giới hạn cần chốt trước

- 4248 dòng chi tiết nguồn tổng hợp thành 96 ô Market–tháng: 4 Market × 24 tháng, 01/2012–12/2013.
- Mỗi mô hình riêng theo Market chỉ có 24 điểm thời gian. Ở mốc huấn luyện đầu với 15 tháng và ba lag, Ridge có 12 mẫu huấn luyện/Market.
- Đây là mô phỏng dự báo lịch sử. Dự báo kỳ 01/2014 không phải dự báo cho thời điểm hiện tại, chưa có actual trong file để chấm sai số.
- Dữ liệu nhân tải trong `bench` không làm tăng lịch sử quan sát để học ML. Không dùng nó để huấn luyện hoặc làm tăng cỡ mẫu công bố.
- Kết quả tham chiếu đã có trong báo cáo và tests. Thực nghiệm này tái lập một protocol cố định; không mô tả như kiểm định mù hoàn toàn. Nếu tiếp tục chọn phương án dựa trên test đã xem thì kết quả đó là thăm dò; cần kỳ mới để đánh giá độc lập.

## 3 Bước 1 Chốt dữ liệu đầu vào và yêu cầu

Đọc mart từ kho qua logic dùng chung, GROUP BY Market và MonthStart, SUM(Sales). Bước đầu dùng SQLite để phát triển; khi Chi bàn giao SQL Server, đối soát từng ô giữa hai backend trước khi đổi nguồn phục vụ.

Kiểm tra 4 Market, 24 đầu tháng liên tiếp mỗi Market, 96 khóa duy nhất, không thiếu kỳ, không có số không hữu hạn. Đối chiếu tổng Sales819811 trên snapshot gốc; truy vết được về checksum và batch nguồn. Thiếu tháng phải rà soát, không tự điền0.

Khám phá biểu đồ doanh số và biến động trên phần lịch sử dùng thiết kế. Tránh nhìn kỳ test để chọn feature hoặc thay giả thuyết; biểu đồ toàn bộ giai đoạn có thể dùng ở phần báo cáo sau khi đã khóa cấu hình.

Đầu ra dự kiến: `monthly_sales.csv`, `data_quality.json`, biểu đồ bốn chuỗi và một biên bản chốt target, horizon, thời điểm dữ liệu được biết. Các tệp này là đầu ra cần bổ sung khi thực hiện, chưa có sẵn đầy đủ trong base.

## 4 Bước 2 Khóa lịch kiểm định và quy tắc so sánh

| Vai trò | Khoảng thời gian | Số tháng | Số dự báo mỗi phương pháp |
| --- | --- | ---: | ---: |
| Lịch sử khởi tạo | 01/2012–03/2013 | 15 | Dùng để fit lần đầu |
| Validation chọn phương pháp | 04/2013–09/2013 | 6 | 24 trên bốn Market |
| Test đánh giá sau lựa chọn | 10/2013–12/2013 | 3 | 12 trên bốn Market |
| Kỳ ngoài nguồn | 01/2014 | 1 | 4 dự báo, chưa có actual |

Đánh giá theo cửa sổ lịch sử mở rộng, dự báo một tháng trước. Ví dụ: dùng đến03/2013 dự báo04; đến04 dự báo05. Trong test, dự báo10 dùng dữ liệu đến09; dự báo11 được dùng actual10 vì tại mốc đó tháng10 đã kết thúc. Phương pháp, feature policy và tham số đã chọn phải giữ nguyên khi đi qua test.

Không random split. Mọi mô hình dùng cùng các kỳ mục tiêu và cùng phạm vi Market. Nếu thử mô hình gộp Market, tách đồng bộ theo tháng: không đưa actual của bất kỳ Market nào ở tháng đích vào train.

Khóa ngày split cụ thể trong cấu hình thử nghiệm của snapshot này. Hàm hiện tại lấy chín tháng cuối khi lịch sử thay đổi; cần kiểm soát để bổ sung dữ liệu không tự dịch protocol đang tái lập.

## 5 Bước 3 Tái lập ba phương pháp bắt buộc

| Phương pháp | Quy tắc | Mục đích |
| --- | --- | --- |
| `naive_last` | Dùng Sales tháng gần nhất | Mốc đối chứng quản lý dễ hiểu |
| `moving_average_3` | Trung bình ba tháng gần nhất | Kiểm tra lợi ích làm trơn biến động |
| `ridge` | Học Sales từ lag1/lag2/lag3; StandardScaler + Ridge(alpha=1) | Kiểm tra ML có cải thiện so với quy tắc đơn giản |

Code tham chiếu đã có ở `src/coffee_dw/forecast.py`. Trước khi thêm mô hình, tái lập đúng các phương pháp này và kiểm tra tính đúng. Với ba phương pháp: 108 prediction đánh giá = 3 × (24 validation + 12 test), cùng bốn dự báo kỳ tiếp theo của phương pháp được chọn.

Feature chuẩn là Sales ba tháng trước. Fit scaler riêng trên tập train của từng origin. Không dùng Sales, Profit, COGS, Inventory hoặc Marketing thực hiện của tháng đích. Budget tháng đích chỉ dùng trong thí nghiệm khác nếu chứng minh đã được phát hành và biết tại origin; CSV hiện chưa cung cấp lịch phát hành đó.

Giữ tests tái lập baseline hiện có. Bổ sung tests cho tính nhất quán kỳ phát hành, thay đổi dữ liệu tương lai không thay dự báo quá khứ và tính duy nhất khi lưu kết quả.

## 6 Bước 4 Mở rộng có kiểm soát

Chỉ thực hiện sau khi pipeline tham chiếu ổn định. Hoàn thành phạm vi bắt buộc trước; lựa chọn thêm tối đa một hoặc hai phương pháp cho một đợt thí nghiệm đã công bố.

| Mở rộng | Câu hỏi thử | Điều kiện và giới hạn |
| --- | --- | --- |
| Seasonal naive12 | Cùng tháng năm trước có tốt hơn tháng liền trước không | Có đủ lịch sử lag12; chỉ hai năm nên chưa khẳng định mùa vụ ổn định |
| Simple exponential smoothing | Ưu tiên quan sát gần có tốt hơn trung bình ba tháng không | Fit chỉ trên lịch sử; ghi rõ cách ước lượng hệ số; cần thêm dependency khi triển khai |
| Mô hình cây nông gộp bốn Market | Chia sẻ thông tin giữa Market có giúp không | Hướng thăm dò sau; feature trễ và Market, split theo tháng, cấu hình nhỏ và seed cố định |

Đề xuất đợt mở rộng đầu là seasonal naive12 hoặc exponential smoothing. LSTM/Transformer và tìm kiếm tham số diện rộng chưa nằm trong kế hoạch tối thiểu: với lượng lịch sử hiện có, khó đưa ra kết luận có sức thuyết phục về khả năng tổng quát hóa. Đây là lựa chọn phạm vi của dự án, không phải khẳng định các mô hình đó luôn kém.

Mỗi thay đổi feature, tham số hoặc cách gộp thị trường phải có tên protocol và run riêng. Không trộn bảng chương6 với ví dụ TN12 West sáu kỳ, lag1/lag2/mean3 trong sổ tay.

## 7 Bước 5 Đánh giá và chốt cách phục vụ

Chọn một phương pháp chung bằng MAE validation gộp bốn thị trường theo báo cáo. Nếu bằng điểm, ưu tiên cách đơn giản hơn theo thứ tự đã chốt. Sau đó báo test của phương pháp đã chọn; có thể giữ bảng test các đối chứng để giải thích, nhưng không đổi lựa chọn sau khi nhìn test.

- MAE là độ lệch tuyệt đối trung bình theo đơn vị Sales nguồn. MAE200 không có nghĩa mọi tháng đều lệch trong ±200.
- RMSE giúp nhìn độ nhạy với các lỗi lớn.
- MAPE là số đo tham khảo khi actual khác0; nêu cách xử lý actual0, không gọi 100%-MAPE là độ chính xác của hệ thống.
- Báo riêng từng Market và từng tháng để quy mô Market lớn không che Market nhỏ. Ghi thêm hướng lệch dự báo cao/thấp hơn actual.
- Cải thiện so baseline = (MAE baseline − MAE phương pháp)/MAE baseline ×100%, nếu MAE baseline dương. Tính trên cùng kỳ và cùng phạm vi.

Kết luận phải trả lời phương pháp nào được chọn, hơn/kém cách lấy tháng trước bao nhiêu, thị trường nào còn yếu và có đủ lý do phục vụ hay chỉ tiếp tục thử. ML không thắng baseline vẫn là kết quả hợp lệ: giữ baseline phù hợp và giải thích bằng số liệu.

Code hiện chỉ tạo point forecast. Trước mắt hiển thị sai số lịch sử và số kỳ đánh giá; không tự thêm dải95% hoặc dùng MAE làm khoảng tin cậy. Nếu bổ sung prediction interval phải có phương pháp, dữ liệu hiệu chuẩn và kiểm tra coverage riêng; sáu kỳ validation mỗi Market là rất ít.

Đầu ra: bảng so sánh, bảng sai số từng kỳ, biểu đồ actual/baseline/phương pháp được chọn và `decision.md` ghi lý do lựa chọn, giới hạn, phạm vi sử dụng.

## 8 Bước 6 Lưu kết quả có thể tái lập

Base hiện có bốn tệp trong `results/forecast/` và bảng SQLite ForecastSales. Khi chạy lặp nhiều cấu hình cần thêm thư mục theo run để tránh ghi đè, cùng audit nguồn và cấu hình.

```text
results/experiments/forecast/<run_id>/
  config.json             Target, horizon, ngày split, feature, mô hình, tham số
  manifest.json           Commit, checksum, batch, phiên bản package, seed, thời điểm
  monthly_sales.csv       96 ô đầu vào của snapshot gốc
  data_quality.json       Các kiểm tra và đối soát
  predictions.csv         Market, origin, target, actual, prediction, model, split
  metrics.csv             MAE/RMSE/MAPE, N theo split và Market
  next_month.csv          Bốn dự báo kỳ01/2014, actual rỗng
  summary.json            Phương pháp được chọn và thông tin protocol
  error_analysis.csv      Sai số từng kỳ, hướng lệch
  decision.md             Kết luận sử dụng và giới hạn
  figures/                Biểu đồ dùng cho báo cáo
```

Đây là cấu trúc dự kiến cần bổ sung, không phải mô tả toàn bộ chức năng hiện có. `results/forecast/` có thể tiếp tục là bản phục vụ dashboard sau khi chọn và công bố một run. Không tự động ghi đè bản phục vụ với mọi mô hình đang thử.

ForecastSales cần giữ Market, IssueMonth, ForecastMonth, TrainEnd, ModelName, ModelVersion, Prediction và Actual. Bổ sung truy vết run/checksum bằng audit phù hợp; ModelVersion cố định hiện tại chưa đủ phân biệt mọi lần sửa dữ liệu. Nếu đổi schema, phối hợp Chi và cập nhật consumer/tests cùng thay đổi.

Không bắt buộc lưu file pickle/joblib cho mọi lượt fit; baseline có thể tái tính, Ridge có thể tái fit từ snapshot/config. Nếu lưu model cuối phải đi kèm đủ preprocessing, feature order và metadata nguồn.

## 9 Bước 7 Đưa kết quả lên dashboard

Giao diện giúp người quản lý đọc một dự báo đúng phiên bản: chọn Market và kỳ phát hành, nhìn kỳ mục tiêu, số dự báo, actual gần nhất, tên phương pháp, kết quả sai số đã đánh giá và dữ liệu chốt đến kỳ nào. Biểu đồ actual/baseline/phương pháp được chọn và CSV xuất giữ cùng phạm vi.

Gắn nhãn rõ dữ liệu lịch sử2012–2013, tách kỳ chưa có actual, không biến missing thành0. Nếu so với kế hoạch, phải có budget đúng kỳ và nguồn công bố; chưa có thì để thiếu và giải thích. Cảnh báo khi kết quả forecast không còn khớp snapshot kho hiện tại là một đầu việc cần bổ sung.

Trang dự báo chỉ đọc kết quả đã công bố. Việc huấn luyện/nạp lại chạy riêng theo quy trình. Khi actual tháng mới tới, đối chiếu forecast đã phát hành, cập nhật sai số và mới phát hành dự báo tháng sau; không ghi đè quá khứ rồi chấm như dự báo cũ.

Nghiệm thu: đổi Market không lẫn số, xuất CSV khớp bộ lọc, một target/Market/phương pháp/phiên bản không nhân dòng, actual phải được gộp lên Market–tháng trước khi ghép forecast. Đây là điểm nối trực tiếp giữa môn kho dữ liệu và ứng dụng ML.

## 10 Bước 8 Hoàn thiện phần triển khai chương 7

Sau khi logic AI ổn định, tích hợp nguồn SQL Server do Chi bàn giao và đối soát với SQLite. Thu benchmark indexed view/partition/index theo TN07–TN10 trên engine thật; đo UX theo TN11 bằng người thử thực tế. Thời gian model fit, thời gian truy vấn SQL và thời gian người dùng tìm câu trả lời là ba số đo khác nhau.

Các đầu việc này có thể chuẩn bị song song với AI nhưng có nghiệm thu riêng; điểm MAE thấp không thay cho bằng chứng đúng số của kho, plan SQL hay phiên thử dashboard. Hoàn thành bắt buộc trước khi ưu tiên TN13 và các mô hình bổ sung khác.

## 11 Thứ tự thực hiện và tiêu chí hoàn thành

| Mốc | Làm gì | Điều kiện để sang mốc tiếp |
| --- | --- | --- |
| A | Chốt câu hỏi quản lý, snapshot và protocol | Có dataset96 ô, kiểm tra nguồn, ngày split và feature policy |
| B | Bổ sung audit run, tái lập ba phương pháp chuẩn | Tính đúng, không rò rỉ, không ghi đè kết quả, đủ prediction |
| C | Thử mở rộng giới hạn nếu cần | Cấu hình công bố trước, cùng target và tiêu chí |
| D | Khóa lựa chọn, đánh giá và phân tích lỗi | Bảng validation/test, từng Market, decision.md, giới hạn rõ |
| E | Lưu kho và dashboard | Đúng phiên bản, đúng filter, không fan-out, export khớp |
| F | Native integration, UX và báo cáo | Có minh chứng thật, tái lập được, PR vào dev |

Việc nên bắt đầu sau khi chốt kế hoạch là mốcA: kiểm chứng đầu vào và viết protocol/config; chưa cần thêm thuật toán ngay. Nhóm có thể làm riêng mốcA–B trong lúc chờ SSIS/SSAS, dùng hợp đồng mart hiện tại.

## Tài liệu đối chiếu

- `docs/chapters/ch06_trang.md`, `ch07_trang.md`, `docs/architecture.md` và `docs/REPORT_MAP.md`: yêu cầu cụ thể của repo.
- [Forecasting Principles and Practice mục phương pháp đơn giản và rolling origin](https://otexts.com/fpp3/toolbox.html): nền tảng baseline và kiểm định theo thời gian.
- [scikit-learn Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html): preprocessing và tránh rò rỉ dữ liệu.
- [statsmodels SimpleExpSmoothing](https://www.statsmodels.org/stable/generated/statsmodels.tsa.holtwinters.SimpleExpSmoothing.html): tài liệu cho hướng mở rộng exponential smoothing.
