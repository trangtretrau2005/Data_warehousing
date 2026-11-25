# Chọn ba trường hợp cần kiểm tra sau khi chốt tháng

**Kết quả chính.** Với cùng 33 lượt kiểm tra, xếp theo số hụt hiện tại bao phủ 7.565 đơn vị hụt của kỳ sau. Isolation Forest bao phủ 3.849. Cả hai đều chọn đúng 33/33 lượt còn hụt. Chỉ số phân biệt hai cách trong bài toán này là **số hụt kỳ sau được bao phủ**. [Mở màn hình thử nghiệm](http://127.0.0.1:8504/triage.html).

## 1. Câu hỏi quản lý và đơn vị phân tích

Sau khi chốt sổ tháng t, quản lý biết Sales, BudgetSales và Profit thực tế của tháng đó. Giả định nhóm chỉ đủ thời gian kiểm tra ba cặp Market–Product. Câu hỏi là phương pháp chọn ba cặp nào giúp tập trung vào những khoản hụt còn xuất hiện ở tháng t+1. Số 3 là ngân sách kiểm tra giả định do nhóm đặt trước cho cả hai phương pháp. Một cặp có thể được chọn nhiều tháng liên tiếp. Các số tiền dùng đơn vị của nguồn.

## 2. Nguồn, grain và đối soát

Nguồn gốc là [Coffee.csv](../../data/raw/Coffee.csv). Snapshot có 4.248 dòng ở grain tháng × mã vùng × sản phẩm, 24 tháng liên tiếp từ 01/2012 đến 12/2013, bốn thị trường và 13 sản phẩm. Tổng Sales 819.811, BudgetSales 746.160, Profit 259.543. Gom theo tháng × Market × Product cho 42 cặp thực sự xuất hiện mỗi tháng, tức 1.008 ô.

Runner đọc SQLite bằng kết nối read-only, nhóm dữ liệu từ vw_Detail. Để kiểm độc lập, runner đọc CSV gốc, đổi ngày Excel với origin 1899-12-30, nhóm lại và đối chiếu Sales, BudgetSales, Profit trên từng khóa của toàn bộ 1.008 ô. Dashboard trình bày bản kết quả lịch sử đã xuất từ lần chạy này. Khi đổi snapshot phải chạy lại runner. [Mã thực nghiệm](run.py) · [Hợp đồng kho](../../docs/architecture.md).

## 3. Hai cách lập danh sách và nguồn tham khảo

**Quy tắc theo tiền hụt.** Với từng cặp i, đặt L(i,t) = max(BudgetSales(i,t) − Sales(i,t), 0). Đầu tiên cộng theo đúng grain, sau đó mới lấy phần dương. Chọn ba cặp có L lớn nhất. Ví dụ South–Colombian tháng 8 có Sales 1.102, BudgetSales 1.370, do đó L = 268. Một sản phẩm vượt kế hoạch có L = 0. Cộng các L đo tổng phần hụt của những sản phẩm hụt, còn Gap ròng của Market có tính cả phần vượt bù lại.

Công thức cụ thể và ngưỡng ba lượt là **baseline quản lý do nhóm định nghĩa** dựa trên KPI Gap của dự án. Cơ sở phương pháp là ưu tiên hạng mục theo quy mô tác động. ASQ mô tả phân tích Pareto với các hạng mục được xếp giảm dần theo tần suất hoặc chi phí. ASQ cung cấp nguyên tắc sắp thứ tự, còn số 3 và phép kiểm kỳ kế tiếp là thiết kế của thí nghiệm này. [ASQ – Pareto Chart](https://asq.org/quality-resources/pareto).

**Isolation Forest.** Fit chung các cặp Market–Product có đủ feature trong các tháng trước. Ba đầu vào đều tính riêng theo cặp:

| Feature | Công thức | Ý nghĩa |
| --- | --- | --- |
| Tỷ lệ hụt có dấu | (BudgetSales − Sales) / BudgetSales | Cùng một mức tiền hụt có thể lớn hoặc nhỏ so với kế hoạch của sản phẩm |
| Biến động Sales | Sales tháng t / trung bình Sales ba tháng liền trước − 1 | Độ lệch so với doanh số gần đây |
| Biến động biên lợi nhuận | Profit(t)/Sales(t) − tổng Profit ba tháng trước / tổng Sales ba tháng trước | Chênh giữa hai tỷ suất, nhân 100 để đọc theo điểm phần trăm |

Mẫu số 0 được coi là thiếu. Chỉ dùng hàng đủ ba feature. Rừng dùng 100 cây theo mặc định, random_state=42, max_samples=auto. Điểm trên màn hình bằng −score_samples để điểm cao ứng với quan sát dễ bị cô lập hơn. Thuật toán có thể chấm cao cho biến động ở cả hai chiều. Hai cách cùng chọn từ nhóm đang hụt và đủ feature. Khi bằng điểm, xếp Market rồi ProductName theo thứ tự chữ. [Tài liệu Isolation Forest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html).

## 4. Các giai đoạn thực nghiệm

1. **Chuẩn bị lịch sử.** Dùng 2012 làm năm khởi tạo. Ba tháng đầu cung cấp lịch sử trượt. Tại mỗi tháng, ba tháng đối chiếu đều kết thúc trước tháng đó.
2. **Đóng vai người ra quyết định.** Lần đầu chốt tháng 01/2013, fit mô hình bằng các hàng đủ feature đến hết 12/2012. Ở lượt sau, mở rộng lịch sử thêm một tháng và fit lại. Dùng số thực tế tháng vừa chốt để tính feature và chọn ba cặp.
3. **Ghi hai danh sách độc lập.** Cùng tháng, tập ứng viên và số lượt kiểm tra. Mô hình sắp theo điểm bất thường. Baseline sắp theo L(i,t). Mỗi danh sách có ba dòng. Có thể trùng cặp giữa hai cách.
4. **Mở kỳ kế tiếp.** Với đúng khóa Market–Product đã chọn, tra Sales và BudgetSales thật của tháng t+1 rồi tính L(i,t+1). Các cột của kỳ sau chỉ dùng để chấm. Có 11 lượt chọn từ 01 đến 11/2013, kiểm bằng thực tế 02 đến 12/2013. Tháng 12 cuối nguồn thiếu kỳ kế tiếp để đánh giá.
5. **Cộng gộp.** Thu 104 ứng viên-tháng và 33 lượt chọn mỗi cách. Đây là backtest thăm dò theo thứ tự thời gian trên một snapshot. Không tinh chỉnh hyperparameter theo điểm kết quả. Protocol này độc lập với split dự báo doanh số ở TN12.

## 5. Metric và mẫu số

- **Precision@3.** Nhãn proxy y(i,t+1) = 1 nếu L(i,t+1) > 0. Mỗi tháng lấy số cặp được chọn có y=1 chia 3. Điểm chung bằng tổng số lượt còn hụt chia 33 vì mỗi tháng có đúng ba lượt. Nó đo độ dai dẳng của việc hụt ngân sách. Nguồn thiếu nhãn sự cố vận hành đã điều tra.
- **Bao phủ số hụt kỳ sau.** Tử số là tổng L(i,t+1) của những cặp đã chọn. Mẫu số là tổng L(i,t+1) của **toàn bộ ứng viên đủ điều kiện tại tháng t**, cộng qua 11 lượt. Các cặp khác mới bắt đầu hụt ở kỳ sau nằm ngoài phạm vi. Kết quả toàn kỳ là tỷ số của hai tổng nên các tháng có số hụt lớn đóng góp nhiều hơn.
- **Số hụt trên một lượt kiểm tra.** Lấy tử số trên chia 33. Chỉ số diễn đạt quy mô tiền cần xem xét bằng đơn vị nguồn. Để kết luận về khoản tiết kiệm cần thêm thử nghiệm can thiệp và chi phí xử lý.

| Cách chọn | Precision@3 | Bao phủ kỳ sau | Hụt kỳ sau trên một lượt |
| --- | ---: | ---: | ---: |
| Isolation Forest | 33/33 = 100% | 3.849/12.829 = 30,0% | 116,64 |
| Theo tiền hụt | 33/33 = 100% | 7.565/12.829 = 59,0% | 229,24 |

Trong toàn bộ ứng viên, 98/104 (94,2%) vẫn hụt kỳ sau. Do tỷ lệ nền cao, 100% ở cả hai cách là một tiêu chí ít phân biệt. Chênh lệch bao phủ tính từ số gốc là khoảng 29,0 điểm phần trăm. Hai danh sách có thể trùng nên không cộng hai tỷ lệ.

## 6. Kết quả theo tháng

| Tháng chốt | Hàng fit | Ứng viên | Còn hụt kỳ sau | Hụt kỳ sau của cả nhóm | AI bao phủ | Baseline bao phủ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2013-01 | 378 | 7 | 7 | 798 | 225 | 432 |
| 2013-02 | 420 | 8 | 8 | 793 | 182 | 445 |
| 2013-03 | 462 | 8 | 8 | 805 | 207 | 456 |
| 2013-04 | 504 | 8 | 8 | 1296 | 368 | 752 |
| 2013-05 | 546 | 13 | 13 | 1496 | 609 | 812 |
| 2013-06 | 588 | 13 | 13 | 1524 | 540 | 832 |
| 2013-07 | 630 | 13 | 13 | 1541 | 590 | 877 |
| 2013-08 | 672 | 13 | 7 | 803 | 274 | 500 |
| 2013-09 | 714 | 7 | 7 | 2225 | 506 | 1354 |
| 2013-10 | 756 | 7 | 7 | 735 | 161 | 541 |
| 2013-11 | 798 | 7 | 7 | 813 | 187 | 564 |

## 7. Đối chiếu thực tế tháng 8 sang tháng 9

| Cách chọn | Market | Sản phẩm | Sales T8 | Ngân sách T8 | Hụt T8 | Sales T9 | Ngân sách T9 | Hụt T9 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AI | West | Amaretto | 283 | 340 | 57 | 395 | 450 | 55 |
| AI | South | Colombian | 1102 | 1370 | 268 | 1006 | 1160 | 154 |
| AI | South | Decaf Irish Cream | 465 | 570 | 105 | 475 | 540 | 65 |
| Theo tiền hụt | West | Colombian | 1406 | 1750 | 344 | 1383 | 1600 | 217 |
| Theo tiền hụt | South | Colombian | 1102 | 1370 | 268 | 1006 | 1160 | 154 |
| Theo tiền hụt | Central | Caffe Mocha | 1575 | 1840 | 265 | 1541 | 1670 | 129 |

Cả hai chọn South–Colombian, kỳ sau hụt 154. Hai lựa chọn riêng của AI đóng góp 55 + 65 = 120. Hai lựa chọn riêng của baseline đóng góp 217 + 129 = 346. Phần chênh đúng 226, tạo ra tổng 274 so với 500. AI học độ hiếm tương đối của các tỷ lệ và biến động. Baseline dùng số hụt tuyệt đối, cùng đơn vị với mục tiêu bao phủ. Kết quả phù hợp với sự khác biệt mục tiêu này. Để giải thích nguyên nhân kinh doanh của một khoản hụt cần thêm dữ liệu về giá, nhu cầu hoặc khuyến mãi.

## 8. Giới hạn, tái lập và trình bày

Một bộ dữ liệu, 11 tháng chấm và các cặp lặp qua nhiều tháng giới hạn khả năng khái quát. Phần hụt ngân sách có thể do cách lập kế hoạch. Thử nghiệm chỉ hỗ trợ chọn danh sách kiểm tra. Để đánh giá phát hiện sự cố thật, cần người nghiệp vụ gán nhãn sau điều tra và đối chiếu Precision@3 với nhãn đó.

Từ thư mục gốc sau khi setup và nạp kho SQLite:

```powershell
.\.venv\Scripts\python -m coffee_dw.cli demo
.\.venv\Scripts\python experiments/triage/run.py
```

Phiên bản scikit-learn 1.7.1. SHA-256 của Coffee.csv: `929bdcc7fd8f6bf21607618e7474df0683af6412b32b8c5af39a40e89b62ffce`. Runner xuất [toàn bộ ứng viên](../../results/triage_pilot/candidates.csv), [66 lượt chọn của hai cách](../../results/triage_pilot/alerts.csv) và [snapshot cho màn hình](../../apps/cube_explorer/triage.json). Hai CSV được tái tạo cục bộ theo quy ước results/.

Khi bảo vệ, mở tháng 08/2013, chọn một phương pháp và đọc ba tên trước khi mở tháng 09. Đổi phương pháp để xem danh sách khác nhau ở đâu. Cuối cùng mở kết quả 11 lượt để tránh suy rộng từ một ví dụ.
