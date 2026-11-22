# Giải thích đồ thị và trả lời câu hỏi về dự báo

Cập nhật **19/11/2026**. Kết luận hiện tại: **MA3 vẫn là phương pháp chính theo MAE validation; hiển thị đẹp hơn giúp đọc đúng kết quả, không làm số đo tốt lên. Không cần sinh doanh số giả để hoàn thiện phần này.**

## 1. Vì sao hình cũ chỉ có ba điểm test mỗi thị trường

Nguồn có 24 tháng. Protocol chính dành 15 tháng đầu khởi tạo, sáu tháng 04–09/2013 chọn phương pháp và ba tháng 10–12/2013 báo cáo test. Vì vậy chỉ có ba lỗi test/Market là giới hạn thật của thiết kế, không phải lỗi đồ thị. Bốn ô giúp đọc khác biệt giữa các Market nhưng hình ba điểm dễ thiếu bối cảnh.

Hình thay thế chỉ vẽ **actual và MA3 chính thức trong cả chín kỳ 04–12/2013**, tô nền riêng validation và test. Có 36 điểm MA3 trên bốn Market: 24 validation + 12 test. Chúng không trở thành 36 điểm test khi đưa lên cùng hình. Bảng và dot plot riêng vẫn giữ đủ 12 lỗi test, kể cả ca lệch lớn.

- [Hình chính chín origin](../../results/trang_forecast_review/figures/01_ma3_nine_origins.png).
- [Dot plot 12 lỗi test](../../results/trang_forecast_review/figures/02_twelve_test_errors.png).
- [Bảng actual–forecast 12 ô](../../results/trang_forecast_review/figures/03_test_audit_table.png), [CSV số gốc](../../results/trang_forecast_review/ma3_test_audit.csv).
- [Hình cũ với đủ ba phương pháp](../../experiments/baseline/results/04_test/figures/01_actual_forecast.png) giữ ở phụ lục, không ghi đè hoặc xóa.

Lời trả lời ngắn: “Em chỉ có ba tháng test mỗi thị trường nên em công bố đúng cỡ mẫu. Hình chính mở thêm sáu tháng validation để dễ đọc diễn biến; hai pha được tô nền và ghi nhãn riêng. Em không tăng cỡ mẫu test bằng cách đổi cách vẽ.”

## 2. Chọn khoảng kỳ khác gì dự báo nhiều bước và khoảng dự báo

| Khái niệm | Trong bài Coffee | Ý nghĩa khi người xem thao tác |
| --- | --- | --- |
| Khoảng kỳ hiển thị | Ví dụ 04–12/2013 hoặc 10–12/2013 | Chọn những dòng kết quả đã có để đối chiếu; không fit lại hoặc thay lịch chọn mô hình |
| Forecast horizon | Bản chính **h=1 tháng** | Mỗi dự báo sử dụng actual đến hết tháng trước target |
| Origin cố định dự báo nhiều bước | Ví dụ đứng tại 09/2013 dự báo cả 10,11,12/2013 | Đây sẽ là h=1,2,3 từ cùng origin; chưa phải phép thử mà bảng hiện tại chứng minh |
| Prediction interval | Ví dụ một khoảng giá trị có mức coverage được kiểm chứng | Biểu diễn bất định của giá trị tương lai, không phải khoảng tháng trên bộ lọc |

Trong bản chính, dự báo 10/2013 dùng đến 09/2013; dự báo 11/2013 dùng đến 10/2013; dự báo 12/2013 dùng đến 11/2013. Cả ba đều h=1 từ các origin khác nhau. Không được trình bày đường ba tháng đó như dự báo h=3 phát hành một lần vào 09/2013. FPP3 mô tả rolling origin với tập học chỉ chứa quan sát xảy ra trước target và phân biệt đánh giá một bước với nhiều bước. [FPP3, chương 5, mục 5.10](https://otexts.com/fpp3/toolbox.html).

Khi chọn một khoảng trên giao diện, metric tính từ phần đang xem phải gắn nhãn “phạm vi hiển thị”, có split và N tương ứng. Không dùng metric của khoảng dễ hơn để thay MAE validation chính 223,28 hoặc test chính 225,22. Kỳ trước 04/2013 chỉ có actual trong protocol này; thiếu prediction không được hiển thị thành 0.

Lời trả lời ngắn: “Bộ lọc đổi khoảng em muốn nhìn. Độ xa dự báo vẫn một tháng ở từng origin. Nếu cô yêu cầu đứng ở một origin dự báo ba tháng liên tục, em phải đánh giá thêm h=1,2,3 riêng, không dùng kết quả rolling một bước để thay thế.”

## 3. West tháng 11 năm 2013 actual là bao nhiêu

Actual **West 11/2013 = 11.300**, được tổng hợp từ Sales nguồn của đúng tháng và Market. MA3 phát hành sau 10/2013 dùng ba actual đã biết:

`(Sales 08/2013 + Sales 09/2013 + Sales 10/2013) / 3`

`= (12.039 + 11.697 + 11.596) / 3 = 11.777,333333…`

Với quy ước của repo `Error = Prediction − Actual`, sai số là **+477,333333…**, tức dự báo cao. APE = `477,333333… / 11.300 × 100% = 4,22418879…%`. Không nhầm số actual của Market khác trong cùng tháng:

| Market, 11/2013 | Actual | MA3 | MA3 − Actual | APE |
| --- | ---: | ---: | ---: | ---: |
| Central | 10.885 | 11.345,00 | +460,00 | 4,226% |
| East | 7.438 | 7.630,67 | +192,67 | 2,590% |
| South | 4.480 | 4.568,00 | +88,00 | 1,964% |
| West | 11.300 | 11.777,33 | +477,33 | 4,224% |

Dấu chấm trong bảng là phân cách hàng nghìn, dấu phẩy là phần thập phân. CSV lưu số chưa làm tròn. Bốn số actual này là từng Market, không phải tổng toàn bộ thị trường.

Bằng chứng: [CSV đối chiếu 11/2013](../../results/trang_forecast_review/november_all_markets.csv), [hình West riêng](../../results/trang_forecast_review/figures/04_west_november_case.png), [kiểm tra tính lại từ nguồn](../../results/trang_forecast_review/checks.json). FPP3 dùng quy ước error ngược dấu (actual − forecast); MAE/RMSE/APE không đổi, còn chiều bias cần đọc đúng nhãn. [FPP3, mục 5.8](https://otexts.com/fpp3/toolbox.html).

Lời trả lời ngắn: “Actual West là 11.300. Tại origin hết tháng 10 em chưa được dùng số tháng 11 nên MA3 lấy ba tháng trước ra 11.777,33. Khi actual xuất hiện, em ghi nhận dự báo cao 477,33, tương đương APE 4,224%; em giữ ca này để phân tích lỗi.”

## 4. Actual đã biết rồi vì sao không cho mô hình khớp hơn

Đây là backtest: chương trình biết snapshot đầy đủ để chấm lỗi nhưng mỗi origin chỉ được dùng quá khứ. Renderer kiểm lại từng actual với nguồn và tính lại cả 36 giá trị MA3 từ đúng ba tháng trước. Không lấy actual tháng đích để sửa đường dự báo.

MA3 lấy trung bình nên không được thiết kế để đi qua mọi điểm actual; ở West 11/2013, cả ba tháng đầu vào đều cao hơn actual tháng đích nên dự báo cũng cao hơn. Nguồn chưa có bằng chứng để kết luận do khuyến mãi, thời tiết, giá bán hay hành vi khách hàng. Kiểm tra lỗi ngoài mẫu phải dùng dự báo chưa fit vào chính dữ liệu cần chấm. [FPP3, mục 5.8](https://otexts.com/fpp3/toolbox.html).

Không làm trơn actual, xóa tháng khó hoặc đổi trục để che sai số. Hình đường dùng thang Y riêng và ghi rõ; hình cột West bắt đầu từ 0. Sai số có dấu và APE được công bố để người xem nhìn đúng cả mức lệch tuyệt đối lẫn tương đối.

## 5. Có nên vẽ dải 95 phần trăm cho thuyết phục

Chưa có phương pháp khoảng dự báo được hiệu chuẩn trong bản hiện tại. MAE 223,28 là thống kê lỗi validation gộp, không phải một khoảng ±223,28 có coverage 95%. Renderer vì thế không vẽ dải đó.

Một prediction interval cần phân phối hoặc phương pháp lượng hóa bất định với giả định phù hợp và đánh giá coverage; nó không được suy ra chỉ bằng việc gắn nhãn 95% lên MAE. [FPP3, mục 5.5](https://otexts.com/fpp3/toolbox.html).

Lời trả lời ngắn: “Bản này là point forecast; em công bố sai số lịch sử và N. Em chưa hiệu chuẩn interval nên không gắn nhãn 95%. Muốn thêm, em cần một phương pháp riêng và kiểm tra coverage thay vì dùng MAE làm khoảng chắc chắn.”

## 6. Đã thử thêm phương pháp có tiềm năng chưa

Sau bảy cấu hình cũ, vòng review thêm Seasonal Naive 12 và SES alpha 0,2/0,5/0,8, tổng **11 cấu hình**, giữ nguyên nguồn, target, split 15/6/3 và tiêu chí MAE validation. Kết quả mới được lưu riêng tại `experiments/forecast_review/results/`, không công bố thay mô hình phục vụ.

| Cấu hình cần chú ý | MAE validation, N=24 | MAE test, N=12 | Cách diễn giải |
| --- | ---: | ---: | --- |
| MA3 chính thức | 223,28 | 225,22 | Vẫn thấp nhất trên tiêu chí chọn |
| SES alpha 0,5 | 230,40 | 204,88 | Tốt nhất trong bốn cấu hình mới nhưng validation kém MA3 3,19% |
| Seasonal Naive 12 | 233,96 | 537,08 | Kết quả test kém; chưa có bằng chứng mùa vụ ổn định từ hai năm |
| SES alpha 0,8 | 246,88 | 218,43 | Chưa vượt MA3 ở validation |
| SES alpha 0,2 | 256,74 | 161,11 | Test đẹp hơn nhưng không được chọn bằng test |

Không cấu hình mới nào cải thiện validation so MA3; mức cải thiện của lựa chọn vẫn **0%**. SES alpha0,5 có test tốt hơn 9,03% theo MAE, song test đã biết và nó thua tiêu chí lựa chọn; không tự đổi bản chính để lấy con số đẹp. Phép bỏ từng tháng khỏi bảng chấm validation cho MA3 đứng đầu 4/6 lần, Seasonal Naive 12 đứng đầu 2/6; đây là phân tích độ nhạy khi chấm, **không fit lại, không phải sáu kiểm định mới và không đổi lựa chọn**.

Bằng chứng: [README review](../../experiments/forecast_review/README.md), [leaderboard](../../experiments/forecast_review/results/validation_leaderboard.csv), [summary](../../experiments/forecast_review/results/summary.json), [hình 11 cấu hình](../../results/trang_forecast_review/figures/05_exploratory_validation.png). Tất cả test đã được biết trước; vòng review là thăm dò, cần kỳ actual mới để xác nhận tiềm năng.

Lời trả lời ngắn: “Em đã thử thêm bốn cấu hình có lý do, công bố đủ cả thắng lẫn thua. MA3 vẫn đứng đầu validation. SES0,5 là phương án mới gần nhất nên đáng theo dõi khi có kỳ mới; em không chọn SES0,2 chỉ vì test hiện tại đẹp.”

## 7. Có cần gen data để kết quả đẹp hoặc mô hình tốt hơn

**Không thêm doanh số sinh ra vào Coffee.csv hoặc gọi chúng là actual mới.** Sao 4.248 dòng thành 2.124.000 dòng benchmark chỉ tăng tải SQL, không tạo thêm tháng quan sát. Dự báo theo Market vẫn chỉ có 24 tháng thật; sinh thêm mốc thời gian theo một quy tắc tự chọn sẽ kiểm tra quy tắc sinh đó, chưa chứng minh dự báo doanh số thật tốt hơn.

Nếu cần dữ liệu tổng hợp cho kiểm thử ca rỗng/lỗi, thử tải hoặc một nghiên cứu mô phỏng riêng thì có thể tạo bản biệt lập, gắn nhãn synthetic, lưu seed và quy tắc; không trộn vào bảng accuracy thực. Nếu thử bagging/augmentation phải có protocol riêng và vẫn chấm trên actual thật giữ riêng; đó là thí nghiệm chưa được thực hiện ở đây. Vòng review này ghi **0 synthetic observations** và checksum nguồn trước/sau bằng nhau.

Muốn cải thiện bằng chứng dự báo thực tế, cần thêm tháng actual có xuất xứ hoặc dữ liệu doanh nghiệp tương thích, khóa cách dùng trước khi đánh giá và giữ kỳ tương lai chưa dùng để xác nhận. Chỉ đổi hình, đổi mô hình sau khi biết test hoặc sinh dữ liệu dễ dự đoán không giải quyết được giới hạn 24 tháng thật.

## 8. Nếu cô hỏi điểm mạnh của bài ở đâu khi MA3 thắng Ridge

“Bài của em kiểm tra một giả thuyết ứng dụng trên kho dữ liệu, không đặt điều kiện ML phải thắng. Em có kiểm grain/tổng, đối soát SQLite–SQL Server, thử mô hình trên cùng target theo thời gian, tránh dùng tương lai, giữ nguyên quyết định theo validation, lưu phiên bản và đưa kết quả lên dashboard. Giá trị chính là một luồng đúng và có thể kiểm tra; kết quả âm về Ridge vẫn được công bố. Em giới hạn kết luận vì test chỉ 12 điểm và đã được biết.”

Mô hình riêng theo Market chỉ có **24 điểm thời gian**, không phải 4.248 mẫu thời gian: 4.248 là số dòng tổng hợp ở grain tháng × mã vùng × sản phẩm, sau gộp chỉ còn96 ô của bốn Market. Origin đầu với15 tháng và ba lag chỉ có12 mẫu học Ridge/Market. Ba kỳ test/Market rất ít để khẳng định mô hình phức tạp sẽ tổng quát tốt hơn. Review11 cấu hình vẫn không vượt MA3 ở validation là kết quả phải giữ nguyên.

Hướng nghiên cứu có tiềm năng nhưng **chưa chạy trong phạm vi này** là mô hình panel/pooling dùng lịch sử trễ thật ở State/Product để chia sẻ thông tin giữa các nhóm, cùng việc thu thêm tháng actual có xuất xứ. Cần khóa target, thiết kế split theo tháng cho mọi nhóm và fit feature/scaler trong quá khứ, không dùng actual tháng đích của nhóm khác; nếu tổng hợp nhiều cấp phải kiểm tổng và grain. Thêm nhóm không làm số tháng độc lập tự tăng, nên vẫn cần kỳ tương lai mới xác nhận hiệu quả. Đây là đề xuất thử, không phải kết quả cải thiện đã đo.

Không gọi MAPE 2,40% thành “accuracy 97,60%”. Không kết luận mô hình giảm chi phí doanh nghiệp khi chưa có phép đo quyết định hoặc người dùng thật. Dự báo 01/2014 là mô phỏng sau snapshot 2012–2013, chưa có actual trong nguồn và không phải dự báo cho thời điểm hiện tại.

## 9. Vì sao TN12 West lại ra phương pháp hoặc dự báo khác

TN12 riêng theo sổ tay dùng West, sáu kỳ 07–12/2013 và feature lag1/lag2/mean3; nó chọn Naive và dự báo West01/2014=11.883. Protocol chính dùng bốn Market, validation04–09/2013, test10–12/2013, Ridge lag123; chọn MA3 và West01/2014=11.593. Khác tập chấm và feature nên không ghép metric hoặc chọn số đẹp giữa hai protocol. [Hướng dẫn TN12](../../experiments/tn12_west/README.md).

## 10. Tái lập hình và kiểm tra dữ liệu

```powershell
.\.venv\Scripts\python scripts/render_forecast_review.py
```

Nếu chưa có baseline/review artifacts, chạy các runner tương ứng theo README trước. Script vẽ không fit hoặc publish mô hình; nguồn đầu vào được kiểm SHA256 và mọi điểm MA3 được tính lại từ raw. Đầu ra ở `results/trang_forecast_review/`: năm bộ PNG300dpi/PDF/SVG, ba CSV số gốc, HTML, checks và manifest. Không ghi đè hình cũ trong baseline/tuning hoặc sửa bundle phục vụ. Khi không có kết quả review11 cấu hình, script chỉ xuất bốn bộ hình chính và ghi rõ trong manifest.

Nguồn phương pháp đã đọc: Hyndman, R.J. và Athanasopoulos, G., **Forecasting Principles and Practice**, chương5, mục5.5,5.8,5.10. [Trang chính thức OTexts](https://otexts.com/fpp3/toolbox.html). Các số Coffee trong tài liệu này lấy từ CSV/manifest của repo, không phải ví dụ số của sách.
