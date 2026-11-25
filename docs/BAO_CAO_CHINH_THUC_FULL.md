# BÁO CÁO CHÍNH THỨC
## ĐỀ TÀI: XÂY DỰNG KHO DỮ LIỆU VÀ HỆ THỐNG PHÂN TÍCH ĐA CHIỀU ĐỂ ĐÁNH GIÁ CHÊNH LỆCH DOANH SỐ SO VỚI KẾ HOẠCH CỦA CHUỖI CÀ PHÊ COFFEE CHAINS

---

# LỜI NÓI ĐẦU

Cuối quý, người quản lý một chuỗi cà phê cần biết doanh số đã đạt kế hoạch hay chưa. Con số tổng giúp trả lời nhanh câu hỏi ấy, nhưng quyết định tiếp theo thường cụ thể hơn. Người phụ trách thị trường cần biết tháng nào hụt kế hoạch. Người phụ trách sản phẩm cần biết nhóm cà phê hay nhóm trà đóng góp bao nhiêu vào mức hụt. Hai người nhìn cùng một hoạt động kinh doanh ở hai mức chi tiết khác nhau. Muốn các báo cáo thống nhất, cả hai phải dùng cùng kỳ, cùng phạm vi địa bàn và cùng cách tính.

Dữ liệu Coffee Chains cho thấy rõ tình huống này. Trong quý III năm 2013, thị trường South ghi nhận doanh số thực tế 13.554 so với kế hoạch 13.180, vượt 374 đơn vị. Tuy nhiên, khi mở riêng tháng 8, doanh số thực tế là 4.601 so với kế hoạch 4.610, hụt 9 đơn vị. Một quý vượt kế hoạch và một tháng hụt kế hoạch hoàn toàn có thể cùng xuất hiện. Điều cần giải thích là các sản phẩm đã đóng góp theo những hướng nào để tạo nên kết quả của tháng đó.

Đề tài “Xây dựng kho dữ liệu và hệ thống phân tích đa chiều để đánh giá chênh lệch doanh số so với kế hoạch của chuỗi cà phê Coffee Chains” xuất phát từ nhu cầu trên. Kho tổ chức dữ liệu theo thời gian, địa bàn và sản phẩm. Người sử dụng có thể chọn một thị trường, xem kết quả quý rồi mở từng tháng và từng nhóm sản phẩm. Ở mỗi bước, doanh số thực tế và kế hoạch được đặt cạnh nhau để người đọc tự kiểm lại mức chênh lệch.

Phạm vi nghiên cứu gồm 24 tháng từ tháng 1/2012 đến tháng 12/2013. Tệp nguồn ghi số liệu ở mức một sản phẩm tại một mã vùng trong một tháng. Mức chi tiết này phù hợp để so sánh các thị trường và phân tích danh mục sản phẩm. Muốn giải thích sâu hơn một biến động do giá bán, lượng khách hay chương trình khuyến mãi, cần bổ sung dữ liệu về các yếu tố đó.

Báo cáo bắt đầu từ một bản ghi cụ thể để xác định kho có thể trả lời những câu hỏi nào. Trên cơ sở đó, các bước thiết kế, nạp và kiểm chứng dữ liệu phục vụ cùng một mục đích là giúp người đọc đi từ kết quả kinh doanh trên giao diện về các số liệu đã tạo ra kết quả ấy.

Với cách tổ chức đó, người quản lý có thể chỉ ra phần chênh lệch cần tìm hiểu tiếp, còn người kiểm tra báo cáo có thể lặp lại phép tính trên cùng kỳ, cùng thị trường và cùng nhóm sản phẩm.

---

# CHƯƠNG 1. KHẢO SÁT DỮ LIỆU COFFEE CHAINS VÀ THIẾT KẾ MÔ HÌNH KHO

## 1.1. Nguồn dữ liệu và ý nghĩa của một bản ghi

Coffee.csv là tệp dữ liệu kinh doanh định kỳ được sử dụng trong bài thực nghiệm. Tệp thuộc bộ Coffee Chains Dataset công bố trên Kaggle. Mỗi dòng có hai phần. Phần thứ nhất xác định sản phẩm, địa bàn và thời gian. Phần thứ hai ghi doanh số, kế hoạch cùng các số đo kinh doanh của đúng đối tượng và kỳ đó [1].

*Hình 1.1. Các cột mô tả và số đo trong tệp Coffee.csv*

**Đọc dòng đầu tiên**

Dòng đầu ghi sản phẩm Amaretto, mã vùng 719, bang Colorado và thị trường Central. Trường Date có giá trị 40909. Khi chuyển số ngày theo mốc Excel 30/12/1899, giá trị tương ứng với ngày 01/01/2012. Ngày đầu tháng được dùng làm nhãn cho cả kỳ tháng 1. Hai cột Sales và Budget Sales lần lượt là 219 và 220. Do đó Amaretto tại mã vùng này hụt 1 đơn vị so với kế hoạch tháng.

**Bảng 1.1. Thông tin nghiệp vụ đọc được từ một dòng nguồn**

| Câu hỏi | Trường cần đọc | Giá trị ở dòng đầu |
| --- | --- | --- |
| Kỳ nào? | Date | Tháng 01/2012 |
| Địa bàn nào? | Area Code, State, Market | 719, Colorado, Central |
| Sản phẩm nào? | Product, Product Type | Amaretto, nhóm Coffee |
| Kết quả thế nào? | Sales, Budget Sales | 219 thực tế, 220 kế hoạch |

Area Code nhận diện một địa bàn. Tệp không có mã cửa hàng hoặc mã hóa đơn để đi sâu tới một điểm bán hay một lần thanh toán. Đơn vị tiền tệ cũng chưa được nêu trong nguồn, nên các giá trị trong báo cáo được giữ theo đơn vị gốc.

## 1.2. Khám phá dữ liệu kinh doanh

Bước khảo sát đầu tiên là đếm số giá trị khác nhau của từng trường. Kết quả cho biết có thể so sánh bao nhiêu kỳ, thị trường và sản phẩm. Trong 20 cột của tệp, chín cột mô tả đối tượng quan sát và 11 cột còn lại ghi các số đo. Có 4.248 dòng trải đều trong 24 tháng, mỗi tháng 177 dòng.

**Bảng 1.2. Phạm vi quan sát của bản dữ liệu nghiên cứu**

| Góc nhìn | Quy mô | Ý nghĩa khi phân tích |
| --- | --- | --- |
| Thời gian | 24 tháng, 2012–2013 | Có thể tổng hợp theo tháng, quý và năm |
| Địa bàn | 4 thị trường, 20 bang, 156 mã vùng | Có thể mở từ thị trường xuống bang rồi mã vùng |
| Sản phẩm | 2 dòng, 4 nhóm, 13 sản phẩm | Có thể so kết quả theo nhóm hoặc tên sản phẩm |
| Số đo | 11 trường | Có cả kết quả thực tế và kế hoạch cùng kỳ |

**So sánh doanh số giữa hai năm**

**Bảng 1.3. Doanh số thực tế và kế hoạch theo năm**

| Kỳ | Số dòng | Thực tế | Kế hoạch | Chênh lệch |
| --- | ---: | ---: | ---: | ---: |
| 2012 | 2.124 | 401.159 | 373.080 | +28.079 |
| 2013 | 2.124 | 418.652 | 373.080 | +45.572 |
| Cả hai năm | 4.248 | 819.811 | 746.160 | +73.651 |

Tổng kế hoạch của hai năm bằng nhau. Doanh số năm 2013 cao hơn năm 2012 là 17.493 đơn vị, nên phần vượt kế hoạch cũng tăng đúng 17.493. Tuy nhiên, các tổng năm chưa chỉ ra thị trường nào có doanh số cao hoặc nơi nào có tháng hụt. Cần giữ các thuộc tính địa bàn và sản phẩm khi đưa dữ liệu vào kho để có thể mở kết quả theo các góc nhìn này.

**Hai cách đếm phục vụ hai mục đích**

Mỗi năm có 2.124 dòng, nhưng con số này chỉ cho biết số quan sát kinh doanh ở mức chi tiết của nguồn. Để so hiệu quả theo thời gian, cần cộng doanh số của các quan sát thuộc từng kỳ. Chẳng hạn, doanh số toàn chuỗi tăng khoảng 4,36% từ năm 2012 sang năm 2013 dù số dòng và tổng kế hoạch của hai năm bằng nhau.

### 1.2.1. So sánh thực tế với kế hoạch theo thị trường

Để so sánh bốn thị trường, lấy toàn bộ giai đoạn 2012–2013, chia các dòng theo Market rồi cộng riêng Sales và Budget Sales trong mỗi nhóm. Hai thanh của mỗi thị trường trong hình dưới có cùng đơn vị, cùng kỳ và cùng phạm vi sản phẩm. Khoảng cách giữa hai đầu thanh thể hiện độ chênh giữa doanh số và kế hoạch.

*Hình 1.2. Doanh số thực tế và kế hoạch của bốn thị trường, 2012–2013*

**Đọc độ lớn và tỷ lệ**

West có doanh số lớn nhất, đạt 272.264 so với kế hoạch 239.700. Phần vượt là 32.564. South cũng vượt kế hoạch trên toàn kỳ, nhưng chỉ vượt 5.726. Hai số này trả lời câu hỏi về mức đóng góp tuyệt đối của từng thị trường vào chênh lệch toàn chuỗi.

Để hỏi toàn chuỗi đạt bao nhiêu phần trăm kế hoạch, lấy 819.811 chia 746.160 rồi nhân 100, được 109,87%. Mỗi thị trường có kế hoạch khác nhau nên tỷ lệ toàn chuỗi phải được tính từ hai tổng. Lấy trung bình đơn giản bốn tỷ lệ sẽ gán trọng số bằng nhau cho các thị trường có quy mô khác nhau [2].

Khi nạp xong, có thể nhóm dữ liệu trong kho theo Market và so với bảng Excel dưới đây để khoanh vùng sai lệch.

*Hình 1.3. Bảng tổng hợp Excel dùng để đối chiếu độc lập theo Market*

Đọc hàng Grand Total ở cuối bảng Excel và so hai cột Sum of Sales, Sum of Budget Sales với hai tổng dùng để tính tỷ lệ trên.

### 1.2.2. Kiểm tra chất lượng trước khi thiết kế kho

Khảo sát dữ liệu còn phải xác định giá trị nào cần lưu nguyên và trường hợp nào làm một dòng mất ý nghĩa. Một dòng có lợi nhuận âm vẫn xác định được kỳ, địa bàn và sản phẩm. Ngược lại, khi thiếu tên sản phẩm, hệ thống không thể biết cần gán doanh số cho sản phẩm nào.

**Bảng 1.4. Các dấu hiệu chất lượng trên 4.248 bản ghi nguồn**

| Phép kiểm | Số dòng | Cách xử lý |
| --- | ---: | --- |
| Thiếu khóa, sai kiểu hoặc trùng mức chi tiết | 0 | Kiểm lại khi nhận lô mới |
| Profit nhỏ hơn 0 | 528 | Lưu nguyên giá trị âm |
| Inventory nhỏ hơn 0 | 88 | Giữ nguyên và ghi nhận giới hạn diễn giải |
| Sales khác COGS + Margin | 2.088 | Giữ Sales như nguồn cung cấp |
| Profit khác Margin − Total Expenses | 2.105 | Giữ Profit như nguồn cung cấp |

*Hình 1.4. Các bộ đếm cảnh báo trong kết quả khảo sát bằng Python*

Ví dụ, tự tính lại Profit từ Margin và Total Expenses sẽ làm thay đổi lợi nhuận nguồn ở 2.105 dòng. Quyết định thiết kế là giữ đủ các số đo gốc để người đọc có thể đối chiếu, đồng thời công bố kết quả kiểm chất lượng. Một dòng có thể thỏa nhiều điều kiện cảnh báo nên không cộng các bộ đếm thành số dòng lỗi duy nhất.

**Từ cảnh báo đến quy tắc nạp**

Trong hình, `negative_profit` đếm các dòng có Profit âm. Biến `sales_not_cogs_plus_margin` đếm các dòng có Sales khác tổng COGS và Margin. Hai con số trả lời hai câu hỏi độc lập. Khi nhận dữ liệu kỳ mới, ghi lại từng bộ đếm cho phép nhận thấy một thay đổi về chất lượng mà tổng doanh số có thể che khuất. Quy trình nạp ở Chương 2 sẽ thử riêng trường hợp thiếu khóa và sai kiểu số.

## 1.3. Nhu cầu phân tích và lựa chọn hệ thống OLAP

Tại quầy, khi khách thanh toán, ứng dụng cần ghi nhận một giao dịch, cập nhật trạng thái và cho phép tra lại hóa đơn. Đó là dạng công việc của hệ thống xử lý giao dịch trực tuyến OLTP. Cuối quý, người phụ trách thị trường lại cần đọc lịch sử nhiều tháng, chọn một nhóm sản phẩm và tính mức thực hiện kế hoạch. Đó là nhu cầu xử lý phân tích trực tuyến OLAP [3].

**Bảng 1.5. OLTP và OLAP nhìn từ hoạt động của một chuỗi cà phê**

| Tiêu chí | OLTP tại điểm bán | OLAP trong đề tài |
| --- | --- | --- |
| Câu hỏi | Hóa đơn vừa tạo đã thanh toán chưa? | South hụt kế hoạch ở tháng nào? |
| Đối tượng thao tác | Một giao dịch cụ thể | Nhiều dòng trong một phạm vi phân tích |
| Tác vụ thường gặp | Thêm đơn, ghi thanh toán, sửa trạng thái | Lọc, tổng hợp, so sánh và mở chi tiết |
| Dữ liệu cần có | Mã đơn, thời điểm bán, mặt hàng | Kỳ tháng, địa bàn, sản phẩm và số đo |

**Hệ thống Coffee Chains phục vụ OLAP**

Một người đọc có thể cố định thị trường South, xem tổng quý rồi mở ba tháng. Sau khi chọn tháng 8, người đọc có thể chia kết quả theo nhóm sản phẩm. Kho cần giữ các cấp thời gian, các thuộc tính phân nhóm và những số đo có thể cộng lại. Khả năng chuyển giữa các cấp phân tích giải thích vì sao dữ liệu được tổ chức thành một mô hình đa chiều.

Nguồn đầu vào đã tổng hợp theo tháng. Kho có thể trả lời tháng nào hụt và sản phẩm nào đóng góp vào phần hụt, còn việc truy một hóa đơn đòi hỏi dữ liệu tác nghiệp chi tiết hơn. Quy trình ghi dữ liệu định kỳ vào kho phục vụ việc cập nhật lịch sử cho các câu hỏi phân tích này.

**Một thao tác OLAP có thể tự kiểm**

Ở South, quý III/2013 gồm tháng 7 vượt 16, tháng 8 hụt 9 và tháng 9 vượt 367. Tách quý thành ba tháng là thao tác khoan sâu drill-down. Cộng lại theo quý là thao tác tổng hợp lên cấp cao hơn roll-up. Người đọc có thể kiểm kết quả ngay bằng phép tính `16 − 9 + 367 = 374`. Điều kiện South phải được giữ trong cả hai chiều thao tác.

## 1.4. Phương pháp thiết kế kho và lý do chọn Kimball

Có hai điểm xuất phát thường gặp khi thiết kế kho. Theo cách tiếp cận của Inmon, doanh nghiệp xây dựng một kho tích hợp ở cấp tổ chức rồi cung cấp dữ liệu cho các nhu cầu chuyên biệt [4]. Theo Kimball, người thiết kế bắt đầu từ một quy trình nghiệp vụ, xác định mức chi tiết và xây dựng mô hình chiều cho quy trình đó. Những quy trình triển khai về sau có thể dùng chung các chiều đã thống nhất.

Coffee Chains có một nguồn chính và một câu hỏi trọng tâm về việc thực hiện kế hoạch. Doanh số, mức kế hoạch, địa bàn, kỳ và sản phẩm đều hiện diện trên cùng dòng. Vì vậy, đề tài chọn phương pháp Kimball để chuyển trực tiếp từ câu hỏi nghiệp vụ sang cấu trúc có thể triển khai và kiểm chứng.

**Bảng 1.6. Bốn quyết định thiết kế theo phương pháp Kimball**

| Bước | Lựa chọn trong đề tài | Căn cứ từ dữ liệu |
| --- | --- | --- |
| 1. Chọn quy trình | Theo dõi kết quả kinh doanh định kỳ | Có thực tế và kế hoạch cùng kỳ |
| 2. Chốt mức chi tiết | Tháng × mã vùng × sản phẩm | Bộ ba phân biệt được các dòng |
| 3. Xác định chiều | Thời gian, địa bàn, sản phẩm | Đây là những thuộc tính dùng lọc và nhóm |
| 4. Xác định số đo | 11 giá trị thực tế, kế hoạch và vận hành | Các giá trị gắn với cùng bộ ba |

Thứ tự của bốn quyết định có ý nghĩa. Nếu chọn lưu ở cấp thị trường–tháng ngay từ đầu, hệ thống vẫn trả được tổng tháng nhưng mất các dòng sản phẩm cần để giải thích mức hụt. Chốt mức chi tiết trước giúp phát hiện mất mát đó ngay trong thiết kế [5].

**Khi mở rộng thêm một quy trình**

Giả sử sau này có nguồn dữ liệu về khuyến mãi theo cửa hàng và ngày. Bước đầu tiên vẫn là xác định một dòng khuyến mãi đại diện cho điều gì. Chỉ khi thống nhất được ý nghĩa của thời gian, sản phẩm và địa bàn mới có thể so chương trình khuyến mãi với doanh số tháng. Chính việc định nghĩa các chiều dùng chung giúp mô hình hiện tại có điểm tựa để mở rộng.

## 1.5. Xác định quy trình nghiệp vụ và mức chi tiết

Quy trình được chọn là theo dõi kết quả kinh doanh từng kỳ. Khi kỳ tháng kết thúc, nguồn ghi nhận kết quả của mỗi sản phẩm có quan sát tại từng mã vùng. Mức chi tiết, thường gọi là grain, phát biểu ý nghĩa của đúng một dòng sự kiện. Trong kho Coffee Chains, một dòng biểu diễn một sản phẩm tại một mã vùng trong một tháng.

**Kiểm mức chi tiết trên dữ liệu thật**

Có thể kiểm phát biểu này bằng cách nhóm theo ba trường Date, Area Code và Product rồi đếm số dòng của từng nhóm. Bản nguồn có 4.248 nhóm trên 4.248 dòng. Mỗi nhóm có đúng một dòng. Kết quả kết hợp với ý nghĩa nghiệp vụ của ba trường là căn cứ để chọn chúng làm khóa nghiệp vụ của quan sát.

**Bảng 1.7. Cách hiểu một dòng thay đổi khi đổi trường nhóm**

| Trường dùng để nhóm | Số nhóm | Câu hỏi trả lời được |
| --- | ---: | --- |
| Tháng × mã vùng × sản phẩm | 4.248 | Một sản phẩm tại địa bàn đó đạt bao nhiêu trong tháng? |
| Tháng × thị trường × sản phẩm | 1.008 | Một sản phẩm đạt bao nhiêu khi cộng các địa bàn thuộc thị trường? |
| Tháng × thị trường | 96 | Cả thị trường đạt bao nhiêu trong tháng? |

**Ý nghĩa khi nhận lại một tệp**

Nếu một dòng mới cùng tháng, mã vùng và sản phẩm đã có trong kho, cần so các số đo để biết đó là bản gửi lại hay một điều chỉnh. Nếu sản phẩm giống nhau nhưng thuộc mã vùng khác, hai dòng đại diện cho hai quan sát khác nhau và đều phải được giữ.

Các mức tổng hợp trong bảng phục vụ các câu hỏi khác nhau. Giữ mức chi tiết gốc cho phép tạo lại hai mức phía dưới. Theo chiều ngược lại, chỉ biết tổng doanh số của South trong một tháng thì chưa thể tách lại phần của Colombian nếu thông tin sản phẩm đã bị bỏ đi.

Ở tháng 8/2013, lọc South cho 28 dòng ở mức nguồn. Khi nhóm theo tên sản phẩm, còn bảy sản phẩm có số liệu. Cả hai mức đều cho Sales bằng 4.601. Ví dụ này cho thấy số dòng thay đổi theo góc nhìn, trong khi tổng doanh số của phạm vi đang chọn vẫn phải bằng nhau.

## 1.6. Xác định bảng sự kiện, bảng chiều và mô hình sao

### 1.6.1. Bảng sự kiện và cách lưu số đo

Bảng `FactSalesPerformance` lưu các giá trị ở mức chi tiết vừa xác định. Mỗi dòng có ba khóa chiều để trả lời “khi nào”, “ở đâu” và “sản phẩm nào”. Những cột còn lại ghi các giá trị kinh doanh và thông tin truy vết lần nạp. Tách vai trò của từng nhóm cột giúp tránh nhầm một mã định danh với một đại lượng có thể cộng.

**Bảng 1.8. Các thành phần của FactSalesPerformance**

| Nhóm cột | Tên cột trong kho | Vai trò |
| --- | --- | --- |
| Khóa chiều | DateKey, LocationKey, ProductKey | Cùng tạo khóa chính của dòng sự kiện |
| Kết quả kinh doanh | Sales, COGS, Margin, Profit | Lưu kết quả theo nguồn |
| Kế hoạch | BudgetSales, BudgetCOGS, BudgetMargin, BudgetProfit | Lưu mức kế hoạch tương ứng |
| Vận hành | Marketing, Inventory, TotalExpenses | Lưu chi phí tiếp thị, tồn kho và tổng chi phí |
| Truy vết | BatchID, SourceRow | Xác định lô nạp và dòng nguồn |

**Vì sao tồn kho được xử lý riêng?**

Sales của tháng 7 và tháng 8 có thể cộng để tính doanh số hai tháng. Với Inventory, cùng một lượng hàng có thể còn tồn tại qua cả hai kỳ. Cộng hai số dư sẽ làm một phần hàng tồn được tính hai lần. Kho chọn số dư ở kỳ cuối trong phạm vi đang xét rồi mới cộng theo địa bàn và sản phẩm của kỳ đó. Nếu kỳ cuối thiếu số liệu, kết quả cần thể hiện trạng thái thiếu [2].

Tương tự, mức hoàn thành kế hoạch được tính khi truy vấn từ tổng Sales chia tổng BudgetSales. Khi mẫu số bằng 0, tỷ lệ được để thiếu. Quy tắc này cho phép thay đổi cấp tổng hợp mà vẫn giữ đúng ý nghĩa của chỉ tiêu.

**Đối chiếu ngược về tệp nguồn**

Với dòng Amaretto ở đầu tệp, ô Sales trong fact giữ giá trị 219. Khóa thời gian dẫn tới tháng 01/2012, khóa địa bàn dẫn tới mã 719 và khóa sản phẩm dẫn tới Amaretto. BatchID và SourceRow cung cấp đường kiểm tra ngược khi một giá trị trên báo cáo cần được xác minh với lô dữ liệu gốc.

### 1.6.2. Ba bảng chiều và quan hệ trong mô hình sao

`DimDate` chứa kỳ tháng cùng thuộc tính năm và quý. `DimLocation` nối mỗi mã vùng với bang, thị trường và quy mô thị trường. `DimProduct` nối tên sản phẩm với dòng, nhóm và loại sản phẩm. Trong hình dưới, `FactSalesPerformance` nằm ở giữa. Ba đường nối đi từ khóa của mỗi chiều tới khóa tương ứng trong bảng sự kiện.

*Hình 1.5. Mô hình sao đã triển khai trên SQL Server*

Ví dụ, để tính Sales của nhóm Coffee tại South trong tháng 8/2013, chọn kỳ ở `DimDate`, các mã vùng thuộc South ở `DimLocation` và các sản phẩm thuộc Coffee ở `DimProduct`. Các dòng sự kiện thỏa cả ba điều kiện đóng góp vào tổng doanh số 1.567 và kế hoạch 1.940. Phần hụt của riêng nhóm Coffee là 373 đơn vị.

Mỗi dòng sự kiện phải tìm được đúng một dòng ở mỗi chiều. Điều kiện này nối kết thiết kế với bước triển khai tiếp theo. Khi nạp kho, cần kiểm khóa ngoại, tính duy nhất của bộ ba và đối chiếu tổng số đo sau khi nối bảng. Chương 2 dùng chính các điều kiện đó để kiểm chứng quy trình tích hợp.

Trên hình, có thể lần theo đường nối từ `ProductKey` của bảng sự kiện tới `DimProduct` để đọc tên sản phẩm và nhóm Coffee. Cùng cách đó, `LocationKey` cho biết mã vùng thuộc thị trường nào.

---

# CHƯƠNG 2. TÍCH HỢP DỮ LIỆU VÀ KIỂM CHỨNG KẾT QUẢ PHÂN TÍCH ĐA CHIỀU

## 2.1. Từ tệp doanh số đến hai cách đọc cùng một kết quả

Trong tháng 08/2013, thị trường South bán được 4.601 so với kế hoạch 4.610. Trước khi kết luận thị trường hụt 9, cần trả lời ba câu hỏi. Dữ liệu tháng này đã nạp đủ chưa? Việc nối sản phẩm với địa bàn có làm lặp doanh số không? Khi chọn cùng tháng và thị trường trên khối phân tích, số liệu có khớp với SQL không?

*Hình 2.1. Sơ đồ tích hợp từ nguồn đến mart SQL và khối SSAS. Nhánh bên phải lưu dấu vết của lần nạp và dòng bị loại.*

Mô hình sao ở Chương 1 là điểm chung của hai đường đọc. Các khung nhìn SQL gom dữ liệu theo cấp mà báo cáo cần. Khối SSAS đọc các bảng của mô hình sao và cho phép chọn thời gian, thị trường, sản phẩm bằng truy vấn đa chiều MDX.

Nhánh nhật ký giúp phân biệt hai tình huống có thể cho cùng một tổng thấp. Nếu một dòng bị loại vì thiếu tên sản phẩm, người nạp dữ liệu phải xem lý do loại và tìm dòng trong tệp. Nếu mọi dòng đều hợp lệ mà Sales vẫn thấp hơn BudgetSales, người phân tích mới đi sâu theo địa bàn hoặc mặt hàng.

Chương này đi theo thứ tự ấy. Trước hết, kiểm tra các khóa và số gốc trên SQL Server. Tiếp theo, chạy gói SSIS với dữ liệu mới, dữ liệu gửi lại và dữ liệu sai. Cuối cùng, so từng kết quả tổng hợp của mart và cube với số đối chứng ở cùng phạm vi.

### 2.1.1. Kiểm tra mô hình vật lý trước khi nạp định kỳ

Bảng `FactSalesPerformance` ghi một dòng cho mỗi tổ hợp tháng, mã vùng và sản phẩm. Trong SQL Server, tổ hợp này được biểu diễn bằng `DateKey`, `LocationKey` và `ProductKey`. Một dòng fact chỉ có ý nghĩa khi cả ba khóa đều tìm được bản ghi tương ứng trong bảng chiều.

*Hình 2.2. Kết quả truy vấn SQL Server trong thực nghiệm thiết kế kho. Các lưới đầu thể hiện tổng số dòng, số đo và số phần tử của ba chiều.*

Trên bản nguồn chuẩn, phép nối fact với cả ba chiều trả về 4.248 dòng và tổng Sales 819.811, bằng trước khi nối. Đây là hai kiểm tra bổ trợ nhau. Số dòng phát hiện việc mất hoặc lặp bản ghi, còn tổng Sales kiểm tra tác động của phép nối lên chỉ tiêu báo cáo.

*Hình 2.3. Thử chèn DateKey không tồn tại. SQL Server trả lỗi khóa ngoại 547. Hai cột cuối ghi 4.248 dòng trước và sau khi hoàn tác.*

Phép thử thứ hai chủ động đưa một khóa tháng sai vào trong giao dịch thử. SQL Server chặn phép chèn ngay tại kho. Kết quả này giải thích vì sao gói nạp phải tìm được khóa chiều trước khi ghi một dòng doanh số vào fact.

Các lưới kiểm tra cũng ghi nhận 24 kỳ, 156 mã vùng và 13 sản phẩm. Ba con số này cung cấp mốc kiểm lại sau mỗi lần nạp toàn bộ nguồn chuẩn.

### 2.1.2. Tổ chức luồng nạp bằng SSIS

Một lần nhận tệp được gán một mã lô `BatchID`. Gói `LoadCoffee.dtsx` gốc có hai tác vụ nối tiếp. Tác vụ đầu đăng ký lô và đưa dữ liệu vào vùng trung gian. Tác vụ sau gọi thủ tục `dw.usp_LoadCoffee` để nạp kho. Mã lô đi cùng dữ liệu, cho phép lần từ kết quả về tệp đã gửi.

*Hình 2.4. Hai tác vụ trong Control Flow của gói LoadCoffee.dtsx gốc. Mũi tên xác định thứ tự gọi các tác vụ.*

*Hình 2.5. Bản tích hợp tách bước nhận CSV thành Data Flow. Bên trái là thứ tự bốn tác vụ. Bên phải là đường đi của một dòng từ tệp đến bảng tiếp nhận.*

Ở bản tích hợp, Data Flow đọc 20 cột dạng văn bản, gắn `BatchID` rồi ghi vào SQL Server qua kết nối OLE DB. Bước kiểm tra bằng T-SQL tiếp đó mới chuyển ngày Excel sang ngày đầu tháng, kiểm tra kiểu số và khóa nghiệp vụ. Sau khi nhận diện dòng hợp lệ, thủ tục cập nhật bảng chiều, tra khóa rồi thêm mới hoặc cập nhật fact trong một giao dịch [6].

### 2.1.3. Nạp mới, phát lại và sửa số trong cùng một tháng

TN03 chạy gói SSIS bằng DTExec trên SQL Server 2022. Đầu tiên, kho nhận 23 tháng lịch sử. Tháng 12/2013 được tách riêng để thử ba tình huống thường gặp khi nhận báo cáo định kỳ. Bảng ghi tác động lên fact sau mỗi lần nạp.

**Bảng 2.1. Bảy lần chạy của gói SSIS gốc trong TN03**

| Lô đầu vào | Đọc | Thêm | Sửa | Dòng fact | Tổng Sales |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1. Lịch sử 23 tháng | 4.071 | 4.071 | 0 | 4.071 | 784.231 |
| 2. Thêm tháng 12 | 177 | 177 | 0 | 4.248 | 819.811 |
| 3. Phát lại tháng 12 | 177 | 0 | 0 | 4.248 | 819.811 |
| 4. Sửa Sales (+10) | 177 | 0 | 1 | 4.248 | 819.821 |
| 5. Lô có hai lỗi | 8 | 0 | 0 | 4.248 | 819.821 |
| 6. Nạp đủ sau khi đặt lại kho thử | 4.248 | 4.248 | 0 | 4.248 | 819.811 |
| 7. Phát lại tệp đủ | 4.248 | 0 | 0 | 4.248 | 819.811 |

*Hình 2.6. Lưới kết quả audit.LoadBatch trong SQL Server Management Studio. Mỗi dòng mang một mã lô và tên tệp riêng.*

Tháng 12 đóng góp 35.580 doanh số. Khi gửi lại đúng tệp ở lần 3, cả 177 dòng giữ nguyên. Ở lần 4, bản sao thử tăng Sales của một dòng thêm 10. Kho cập nhật đúng một dòng, giữ nguyên 176 dòng còn lại. Vì vậy tổng tăng 10 trong khi số dòng đứng yên. Lần 6 bắt đầu lại từ kho thử đã đặt lại để kiểm tra độc lập phép nạp toàn bộ.

*Hình 2.7. Bảng đếm trong hồ sơ TN03. Hai cột sai lệch của nhật ký đều bằng 0 từ lần nạp lịch sử đến lần phát lại toàn bộ tệp.*

Cả bảy lần thực thi đều có mã kết thúc 0 của DTExec. Các bộ đếm trong nhật ký cho biết gói đã xử lý dữ liệu như thế nào ở từng lần.

### 2.1.4. Xử lý dòng lỗi và kiểm tra nhật ký nạp

Để kiểm tra cách xử lý dữ liệu hỏng, TN03 lấy bản sao tám dòng đầu của tệp. Một dòng bị thay doanh số bằng chuỗi “abc”, một dòng bị xóa tên sản phẩm. Gói vẫn phải ghi nhận đủ tám dòng đầu vào, đồng thời chỉ cho các dòng hợp lệ đi tiếp.

*Hình 2.8. Trích kết quả TN03. Nhật ký lưu số dòng nguồn, lý do từ chối và giá trị ban đầu để có thể tìm lại lỗi trong tệp.*

**Bảng 2.2. Cách đọc kết quả lô thử tám dòng**

| Dòng nguồn | Điều kiện quan sát | Kết quả xử lý |
| --- | --- | --- |
| Dòng 2 | Sales chứa “abc” | Loại dòng vì sai kiểu số. Giữ giá trị gốc trong nhật ký. |
| Dòng 3 | Tên sản phẩm bị bỏ trống | Loại dòng vì thiếu khóa dùng để tìm sản phẩm. |
| Sáu dòng còn lại | Đủ khóa, đọc được số đo | Chấp nhận cả sáu. Tổng Sales của sáu dòng là 1.139. |

Hai phép đối chiếu áp dụng cho từng lô. Số dòng đọc phải bằng số chấp nhận cộng số bị loại. Số chấp nhận phải bằng số thêm mới, số cập nhật và số giữ nguyên cộng lại. Cả bảy lần chạy đều có chênh lệch bằng 0 ở hai phép kiểm.

Lô lỗi chạy trên kho đã có dữ liệu. Sáu dòng hợp lệ đã tồn tại và giữ nguyên. Hai dòng bị loại ở lần gửi mới cũng không xóa các dòng hợp lệ đã nạp trước đó. Vì vậy tổng Sales của lô hợp lệ là 1.139, còn tổng của cả kho sau lần 5 vẫn là 819.821.

**Khi nào phải hủy cả lần nạp?**

Dòng “abc” đã có lý do loại cụ thể, nên sáu dòng hợp lệ vẫn được xử lý. Một tình huống khác là các bộ đếm trong giao dịch mâu thuẫn nhau. Trong bài thử hoàn tác riêng ở SQL Server, lần nạp khai hai dòng nhưng staging chỉ chứa một. Thủ tục báo lỗi 50006 và hủy giao dịch. Đối chiếu sau lỗi cho thấy dữ liệu của 11 bảng giống trước khi thử.

Phép thử này kiểm tra tình huống đã bắt đầu cập nhật nhưng chưa hoàn tất lô. Nhờ hoàn tác, lần đọc báo cáo kế tiếp vẫn thấy trạng thái nhất quán của kho.

### 2.1.5. Quản lý thay đổi thuộc tính chiều

Một lỗi chính tả và một lần chuyển nhóm sản phẩm cần hai cách xử lý khác nhau. Thực nghiệm TN04 chạy gói `SCD_TN04.dtsx` trên các bảng thử biệt lập với mã sản phẩm P01 và mã địa bàn A01. Các thay đổi dưới đây được tạo cho phép thử.

**Bảng 2.3. Ba cách xử lý thuộc tính thay đổi chậm SCD**

| Cách lưu | Thao tác với P01 | Kết quả khi tra cứu |
| --- | --- | --- |
| Loại 1 | Sửa tên Amareto thành Amaretto trên bản ghi hiện tại. | Vẫn một khóa sản phẩm. Báo cáo dùng tên đã sửa. |
| Loại 2 | Chuyển Coffee sang Specialty từ 01/01/2013. Đóng bản cũ và mở bản mới. | Tra tháng 12/2012 trả khóa 1. Đúng ngày 01/01/2013 trả khóa 2. |
| Loại 3 | Lưu nhóm hiện tại và nhóm liền trước. Đổi hai lần tới Premium. | Còn Premium và Specialty. Hai cột này không truy lại được Coffee. |

*Hình 2.9. Bảng phiên bản trong hồ sơ TN04. Hai khoảng hiệu lực của cùng một mã tiếp giáp ở ngày đổi nhóm.*

*Hình 2.10. Tra cứu trước và đúng ngày đổi nhóm trong TN04. Sản phẩm P01 và địa bàn A01 đều chuyển sang khóa mới tại biên.*

*Hình 2.11. Trích ca P01 của TN04. Sau hai lần đổi, cặp thuộc tính hiện tại và liền trước chỉ còn Premium và Specialty.*

Điều kiện tra cứu lấy ngày bắt đầu và loại ngày kết thúc của phiên bản. Phát lại sự kiện P01 vẫn cho hai phiên bản, một bản hiện hành và không có khoảng chồng nhau. Trong kho phục vụ báo cáo, các chiều địa bàn và sản phẩm dùng loại 1. Tệp nguồn chỉ cung cấp tên sản phẩm và không ghi sự kiện chuyển nhóm để dựng lịch sử như P01.

## 2.2. Xây dựng lớp phân tích phục vụ quyết định

Từ cùng một bảng sự kiện, người quản lý cần hai cách nhìn. Để biết thị trường nào hụt kế hoạch, cần tổng theo thị trường và tháng. Để tìm mặt hàng đóng góp vào phần hụt, cần giữ thêm tên sản phẩm. Các view trong schema mart tạo sẵn những mức tổng hợp này cho truy vấn.

**Bảng 2.4. Chọn view theo câu hỏi của người đọc**

| Khung nhìn | Một dòng biểu diễn | Câu hỏi có thể trả lời |
| --- | --- | --- |
| vw_Detail | Một tháng × mã vùng × sản phẩm | Doanh số và kế hoạch ở một mã vùng, một mặt hàng là bao nhiêu? |
| vw_MarketPeriod | Một tháng × thị trường | Tháng nào thị trường hụt hoặc vượt kế hoạch? |
| vw_MarketProductPeriod | Một tháng × thị trường × sản phẩm | Trong tháng đã chọn, mặt hàng nào đóng góp bao nhiêu vào chênh lệch? |

*Hình 2.12. Trích kết quả SQL của kho gốc. Lưới theo thị trường và lưới chi tiết theo bang minh họa hai mức tổng hợp trong tháng 01/2012.*

Trong 24 tháng, view theo thị trường có 96 nhóm, còn view theo thị trường và sản phẩm có 1.008 nhóm quan sát được. TN05 đối chiếu từng nhóm với phép tổng hợp trực tiếp từ nguồn. Sai lệch tuyệt đối lớn nhất bằng 0 cho Sales, BudgetSales, Profit và Gap ở cả hai view.

Khi gộp nhiều nhóm, chênh lệch bằng tổng Sales trừ tổng BudgetSales. Tỷ lệ đạt kế hoạch bằng tổng Sales chia tổng BudgetSales trong cùng bộ lọc. Nếu tổng kế hoạch bằng 0, tỷ lệ để trống. Cách tính này giữ đúng trọng số của từng nhóm khi chuyển lên cấp thị trường.

Central tháng 01/2012 đạt 10.346 trên kế hoạch 9.970, tương đương 103,77%. Tổng chênh lệch của các bang phải bằng +376.

### 2.2.1. Ghép doanh số với kế hoạch ở cùng mức chi tiết

Ở West tháng 01/2012, có 56 dòng chi tiết và một tổng kế hoạch của thị trường là 9.460. Nếu gắn tổng 9.460 vào từng dòng chi tiết rồi cộng lại, kế hoạch bị lặp 56 lần. Doanh số thực tế vẫn đúng, nên chỉ kiểm tra riêng cột Sales sẽ bỏ sót lỗi.

*Hình 2.13. Đối chiếu hai cách nối trong TN05. Ô ngân sách West tháng 01/2012 tăng từ 9.460 lên 529.760 khi tổng tháng bị lặp trên 56 dòng.*

Cách ghép đúng drill-across là tổng hợp riêng doanh số và kế hoạch về cùng khóa tháng × thị trường, rồi mới nối hai phía. Trong phép thử này, hai phía được dựng từ dữ liệu gốc để kiểm tra cách nối. Trên đủ 96 nhóm, tổng đúng là 819.811 doanh số và 746.160 kế hoạch.

**Bảng 2.5. Hai tình huống thiếu dữ liệu trong bảng thử TN05**

| Tình huống tạo thử | Doanh số | Kế hoạch | Kết quả cần giữ |
| --- | ---: | ---: | --- |
| Xóa kế hoạch West 01/2012 | 10.453 | Trống | Giữ dòng và đánh dấu thiếu kế hoạch. |
| Thêm riêng kế hoạch West 01/2014 | Trống | 1.000 | Giữ dòng và đánh dấu thiếu thực tế. |

Nếu dùng kết quả nối sai để đánh giá West, một tháng thực tế vượt kế hoạch 993 sẽ bị đọc thành hụt hơn nửa triệu đơn vị nguồn. Do đó, kiểm tra mức chi tiết của hai phía phải đi trước việc diễn giải dấu của chênh lệch.

Phép nối ngoài đầy đủ `FULL OUTER JOIN` giữ cả nhóm chỉ xuất hiện ở một phía. Cột chênh lệch để trống ở cả hai dòng thử vì thiếu một vế của phép trừ. Riêng tháng 01/2014 là dữ liệu dựng trong bảng tạm, ngoài thời gian của Coffee.csv.

**Bảng 2.6. Tác động của phép nối lên hai chỉ tiêu tại West tháng 01/2012**

| Chỉ tiêu | Nối sau khi gom | Nối vào 56 dòng |
| --- | ---: | ---: |
| Doanh số thực tế | 10.453 | 10.453 |
| Kế hoạch doanh số | 9.460 | 529.760 |
| Chênh lệch tính ra | +993 | −519.307 |

### 2.2.2. Tổ chức khối phân tích trong SSAS

Để trả lời cùng câu hỏi bằng thao tác đa chiều, dự án xây khối `Coffee Performance` trên SQL Server Analysis Services. Trong Data Source View, bảng sự kiện liên kết với ba bảng chiều. Cấu trúc này cho phép lần ngược một số đo đang xem về các bảng SQL cung cấp dữ liệu.

*Hình 2.14. Hai thẻ thiết kế trong dự án SSAS gốc. Bên trái, DSV thể hiện quan hệ giữa các bảng. Bên phải, Cube Structure cho thấy nhóm số đo và danh sách ba chiều.*

*Hình 2.15. Dimension Usage của bản tích hợp. Ba hàng chỉ ra khóa nối từng chiều với nhóm số đo ở mức chi tiết của fact.*

Trên thẻ Dimension Usage, mối quan hệ Regular biểu diễn liên kết trực tiếp giữa một chiều và bảng fact của nhóm số đo [7]. Khi người đọc chọn Central, khối dùng liên kết địa bàn để tìm phần doanh số tương ứng. Chọn thêm tháng sẽ thu hẹp trên chiều thời gian của cùng nhóm số đo.

Trong thiết kế, `DateKey` xác định kỳ, `LocationKey` xác định địa bàn và `ProductKey` xác định sản phẩm. Sau khi triển khai trên môi trường tích hợp, Process Full đọc lại dữ liệu từ kho SQL đã nạp bằng SSIS. Hồ sơ ngày 20/11/2026 ghi trạng thái Processed. Đây là bước chuyển từ thiết kế trong công cụ sang một khối có thể truy vấn.

### 2.2.3. Đọc khối theo tháng, thị trường và sản phẩm

Một lát cắt slice cố định một giá trị của chiều. Chọn tháng 01/2012 giúp nhìn bốn thị trường trong cùng kỳ. Từ đó, người đọc có thể khoan sâu drill-down từ thị trường Central đến các bang, rồi gộp trở lại roll-up để kiểm tra tổng.

*Hình 2.16. Kết quả Cube Browser khi mở Central đến cấp bang trong tháng 01/2012. Mỗi hàng giữ cùng tháng và hiển thị riêng một bang.*

Sáu bang của Central có tổng Sales 10.346 và tổng kế hoạch 9.970, tương ứng vượt 376. Trong tổng dương này, Illinois có Sales 2.538 và kế hoạch 2.580, tức hụt 42. Việc khoan sâu cho thấy thị trường có thể vượt kế hoạch dù một bang bên trong vẫn hụt.

*Hình 2.17. Kết quả chọn đồng thời tháng 01/2012, nhóm Coffee và hai thị trường Central, East trên Cube Browser của bản tích hợp.*

Phép lọc đồng thời nhiều chiều dice thu hẹp câu hỏi vào cùng nhóm hàng. Riêng Coffee ở Central có Sales 2.663 so với kế hoạch 2.680, tức hụt 17. Ở East, cùng nhóm có Sales 2.105 so với kế hoạch 1.960, tức vượt 145. Hai kết quả chỉ so sánh được khi giữ nguyên tháng và nhóm sản phẩm.

**Gộp từ bang lên thị trường**

Sáu bang của Central lần lượt đóng góp `+88, −42, +219, +49, +1` và `+61` vào chênh lệch tháng 01/2012. Cộng sáu giá trị được `+376`, đúng bằng `10.346 − 9.970` của Central. Theo chiều ngược lại, khoan từ `+376` xuống các bang cho thấy Illinois hụt 42 dù cả thị trường vượt kế hoạch.

### 2.2.4. Đổi trục hiển thị và đọc tồn kho cuối kỳ

Người dùng có thể đặt thị trường theo hàng hoặc theo cột để dễ so sánh. Phép đổi trục pivot phải đưa từng giá trị sang đúng vị trí tương ứng. Để kiểm tra, thực nghiệm chạy hai truy vấn MDX đổi vị trí trục qua ADOMD, rồi đối chiếu sáu giá trị với SQL trên cùng bộ lọc Coffee tháng 01/2012.

**Bảng 2.7. Giá trị sau khi chuyển hai thị trường sang cột**

| Chỉ tiêu | Central | East |
| --- | ---: | ---: |
| Doanh số Sales | 2.663 | 2.105 |
| Kế hoạch BudgetSales | 2.680 | 1.960 |
| Lợi nhuận Profit | 724 | 924 |

Cả 6/6 ô khớp khi đổi trục. Chẳng hạn, doanh số 2.105 ban đầu nằm ở hàng East, cột Sales, sau đó chuyển sang hàng Sales, cột East. Kết quả này được xác nhận ở mức truy vấn MDX. Giao diện Query Designer đã gặp giới hạn khi đổi trục trực tiếp.

**Vì sao tồn kho cả năm được đọc ở tháng cuối?**

Doanh số là lượng phát sinh trong kỳ nên có thể cộng qua các tháng. Tồn kho là số tại một thời điểm. Nếu cộng tồn tháng 11 với tháng 12, phần hàng còn lại qua hai tháng có thể bị tính hai lần. Cube dùng quy tắc kỳ cuối `LastChild` cho Inventory theo chiều thời gian.

**Bảng 2.8. Tồn kho cuối năm 2013 theo tháng cuối kỳ 12/2013**

| Central | East | South | West | Toàn chuỗi |
| ---: | ---: | ---: | ---: | ---: |
| 45.252 | 31.529 | 11.444 | 58.933 | 147.158 |

*Hình 2.18. Phần kiểm tra tồn kho trong kết quả SQL của TN06. Lưới đối chứng đặt cùng ngày 01/12/2013 cho cả bốn thị trường.*

Có thể cộng bốn thị trường vì tất cả cùng mô tả tháng 12/2013. Khi bộ lọc chọn một tập kỳ, hệ thống lấy kỳ cuối trong tập đó. Nếu lát cắt chi tiết thiếu dữ liệu ở kỳ cuối, kết quả để trống để người đọc nhận ra giới hạn của dữ liệu.

## 2.3. Kiểm chứng từ nguồn đến câu trả lời quản trị

Các phép kiểm đi từ cấu trúc đến kết quả sử dụng. Một tổng toàn chuỗi có thể vẫn đúng dù một bản ghi bị xếp nhầm thị trường. Vì vậy, ngoài tổng nguồn, thực nghiệm còn so những lát cắt hẹp, ngày biên và trường hợp thiếu dữ liệu.

**Bảng 2.9. Bằng chứng theo tầng và phạm vi được xác nhận**

| Tầng kiểm tra | Cách kiểm tra | Kết quả đã ghi nhận |
| --- | --- | --- |
| Nguồn và kho SQL | Nối fact với ba chiều rồi kiểm lại khóa, số dòng và số đo. | 4.248 dòng sau nối. Bộ kiểm tra SQL tích hợp xác nhận bảo toàn cả 11 tổng. |
| SSIS và nhật ký | Nạp mới, phát lại, sửa số, gửi lô lỗi trong TN03. | Bảy lô gốc cân bằng số dòng. Gói tích hợp có bộ tám ca chạy riêng. |
| Mart SQL | So các nhóm tháng – thị trường và tháng – thị trường – sản phẩm với nguồn. | Sai lệch lớn nhất bằng 0 ở các tổng Sales, BudgetSales, Profit và Gap đã thử. |
| Cube SSAS | Sau Process Full ngày 20/11, đối soát lại MDX với SQL ngày 22/11/2026. | 17/17 ca đạt theo tiêu chí đã đặt, gồm lọc nhiều chiều, tỷ lệ và tồn cuối kỳ. |

**Trở lại câu hỏi ở South tháng 08/2013**

SQL và cube cùng trả về 4.601 doanh số, 4.610 kế hoạch và chênh lệch −9. Ở cấp sản phẩm, cả bảy dòng khớp về Sales, BudgetSales, Profit và Gap. Hai sản phẩm Colombian và Decaf Irish Cream lần lượt hụt 268 và 105. Năm sản phẩm còn lại cộng lại vượt 364. Kết quả chung là `−268 − 105 + 364 = −9`.

*Hình 2.19. Bảy sản phẩm của South tháng 08/2013 trong lưới kết quả SQL gốc. Cột Gap giữ cả giá trị âm và dương khi cộng về tổng tháng.*

Như vậy, người quản lý có thể đọc một con số nhỏ ở cấp thị trường và lần về các khoản bù trừ lớn hơn ở cấp sản phẩm. Chương 3 sử dụng chính lát cắt đã đối chứng này để thử cách dẫn người dùng từ câu hỏi về một quý đến tháng và mặt hàng cần xem.

---

# CHƯƠNG 3. THỬ NGHIỆM CÁC PHƯƠNG PHÁP KHAI THÁC KHO DỮ LIỆU

## 3.1. Từ khối phân tích đến câu hỏi của người quản lý

Biết South vượt kế hoạch 374 trong quý III/2013 mới trả lời được câu hỏi “kết quả chung thế nào?”. Người quản lý còn cần biết tháng nào hụt, sản phẩm nào đóng góp vào phần hụt và con số trên màn hình có thể kiểm lại ở đâu. Thực nghiệm bắt đầu từ ba nhu cầu đó, trước khi xét đến khả năng dự báo doanh số.

**Bảng 3.1. Bốn câu hỏi và cách đánh giá câu trả lời**

| Câu hỏi cần trả lời | Phương pháp thử | Bằng chứng cần có |
| --- | --- | --- |
| Phần hụt nằm ở đâu? | Khoan từ quý xuống tháng, nhóm và sản phẩm. | Tổng Sales và kế hoạch ở các nhánh con bằng số của nhánh cha. |
| Có thể tự đặt câu hỏi khác không? | Bộ chọn sinh SQL và truy vấn bằng tiếng Việt. | Đúng năm, đúng nhóm, đúng phép tính. Kết quả khớp truy vấn đối chứng. |
| Sales tháng tới có thể đạt bao nhiêu? | So dự báo kỳ trước, trung bình trượt và hồi quy Ridge. | Sai số trên những tháng đến sau thời điểm lập dự báo. |
| Marketing có giải thích được Sales không? | Hồi quy riêng từng thị trường. | So ước lượng với doanh số thực của sáu tháng giữ lại. |

Khối SSAS ở Chương 2 cung cấp số đối chứng cho các lát cắt. Ứng dụng web đọc mart SQL của cùng kho, nhận bảng theo tháng và dựng góc nhìn tương tác. Vì vậy, hai giao diện có thể cùng hiển thị South tháng 08/2013 dù đường lấy dữ liệu khác nhau.

Điểm chung của các phép thử là xác định trước đơn vị phân tích. Một dòng tháng × vùng × sản phẩm dùng để đếm ô dữ liệu. Một dòng tháng × thị trường dùng để thử dự báo. Việc phân biệt hai đơn vị này quyết định cả cách đọc kết quả lẫn cỡ mẫu thực sự của mô hình.

**Mốc đối chứng chung**

Cùng là tháng 08/2013, nhưng South ở cấp thị trường có chênh lệch −9, còn Colombian ở riêng South có chênh lệch −268. Khi đối chiếu giữa hai màn hình, cần ghi cả thị trường, tháng, sản phẩm và phép tính. Chỉ một điều kiện bị bỏ sót cũng đủ làm cho hai số đúng trong hai phạm vi trở thành một phép so sai.

## 3.2. Thử nghiệm khoan sâu và kiểm tra cộng ngược

Ứng dụng lấy tổng doanh số và kế hoạch từ mart tháng × thị trường × sản phẩm. Khi người dùng chọn thị trường và quý, chương trình giữ những dòng thuộc phạm vi đó rồi gom theo tháng. Với tháng được chọn, nó tra nhóm của từng sản phẩm và gom lại lần nữa. Lần cuối chỉ còn các sản phẩm của nhóm đang xem.

**Bảng 3.2. Kết quả ở ba tháng của South trong quý III/2013**

| Kỳ phân tích | Sales | Kế hoạch | Chênh lệch |
| --- | ---: | ---: | ---: |
| Tháng 07/2013 | 4.406 | 4.390 | +16 |
| Tháng 08/2013 | 4.601 | 4.610 | −9 |
| Tháng 09/2013 | 4.547 | 4.180 | +367 |
| Cả quý III/2013 | 13.554 | 13.180 | +374 |

**Phép thử cho toàn bộ 32 trường hợp**

Bốn thị trường và tám quý tạo thành 32 tổ hợp. Ở từng tổ hợp, cộng từ mart sản phẩm lên quý rồi so riêng Sales và BudgetSales với tổng từ mart thị trường. Lần đối chiếu trên dữ liệu ứng dụng trả về đủ 32 tổ hợp. Chênh lệch tuyệt đối lớn nhất của từng chỉ tiêu bằng 0. Vì Gap bằng hiệu hai tổng nên Gap cấp quý cũng khớp.

*Hình 3.1. Chênh lệch theo nhóm trong tháng 08 tại South. Mỗi thanh có chung mốc 0. Hai phần vượt cộng lại là 364.*

**Vì sao phải giữ dấu khi khoan sâu?**

Ở South, cộng `16 − 9 + 367` được `+374`. Nếu chỉ xếp theo độ lớn tuyệt đối, tháng 09 đứng đầu, nhưng đó là tháng vượt kế hoạch. Khi mục đích là tìm nhánh hụt, giao diện gợi ý nhánh có Gap nhỏ nhất và cho người dùng chủ động chọn nhánh khác. Kết quả xác định phần đóng góp số học của mỗi nhánh. Dữ liệu hiện có chưa ghi sự kiện giá hoặc khuyến mãi để suy ra nguyên nhân thị trường.

Cách thử này còn phát hiện việc gán nhầm kỳ. Chẳng hạn, chuyển +367 của tháng 09 sang tháng 08 có thể vẫn giữ tổng quý +374. Do đó ca South kiểm thêm từng tháng và hai sản phẩm trong Coffee, bên cạnh phép so ở cấp quý.

## 3.3. Tạo truy vấn bằng lựa chọn có cấu trúc

Một cây khoan sâu trả lời tốt câu hỏi đã biết trước. Khi cần xem Marketing trung bình theo thị trường, người dùng cần đổi cả phép tính lẫn chỉ tiêu. Bộ tạo truy vấn nhận các lựa chọn trên biểu mẫu rồi chuyển thành lệnh SELECT. Người dùng có thể đọc SQL và các giá trị lọc bên dưới bảng trả về.

**Bảng 3.3. Từ lựa chọn trên màn hình đến phép tính trong SQL**

| Lựa chọn | Ví dụ | Ý nghĩa trên dữ liệu |
| --- | --- | --- |
| Phép tính và chỉ tiêu | SUM Sales, SUM BudgetSales | Cộng doanh số và kế hoạch của các dòng thỏa điều kiện. |
| Chiều nhóm | Market | Mỗi thị trường có một dòng kết quả. |
| Kỳ và thị trường | Năm 2013, tất cả Market | Lấy từ 01/01/2013 đến trước 01/01/2014. |
| Phép tính thay thế | AVG Marketing theo Market | Mẫu số là số ô fact có Marketing trong mỗi nhóm. |

Trên toàn bộ 24 tháng, trung bình Marketing của một ô lần lượt là 29,32 ở Central, 33,16 ở East, 24,65 ở South và 35,01 ở West. Nếu câu hỏi là ngân sách Marketing cho cả tháng, phải đổi sang tổng và chỉ rõ tháng. Cùng một cột nguồn có thể cho hai câu trả lời đúng về số học nhưng khác ý nghĩa.

**Cách kiểm tra bộ lọc năm**

Trong truy vấn do biểu mẫu tạo, hai dấu hỏi ở điều kiện ngày nhận hai giá trị riêng khi chạy. Ngày đầu năm được lấy, ngày đầu năm kế tiếp bị loại. Cách viết này bao phủ tháng 12 và tránh phải đoán ngày cuối của từng tháng. Tên cột và phép tính lấy từ danh sách cho phép của máy chủ.

Bộ chọn hỗ trợ SUM và AVG, tối đa bốn chỉ tiêu và ba chiều. Các yêu cầu đếm, tìm cực trị, xếp hạng hoặc tính một tỷ lệ từ hai tổng được đưa sang phép thử Text-to-SQL ở mục tiếp theo.

**Đối chứng một phép tính tỷ lệ**

Khi cần tỷ lệ đạt kế hoạch của cả Market, biểu thức là tổng Sales chia tổng BudgetSales trong cùng phạm vi. Với West năm 2013, hai tổng là 139.029 và 119.850, tương ứng khoảng 116,00%. Lấy trung bình các tỷ lệ ở mức dòng có thể cho một số khác vì mỗi dòng có mức kế hoạch khác nhau.

## 3.4. Từ thử nghiệm Ollama đến Gemini Text-to-SQL

Câu hỏi “Đếm số ô dữ liệu theo Market năm 2012” đòi hỏi hệ thống giữ đúng năm, dùng COUNT và nhóm theo Market. Mô hình ngôn ngữ đảm nhận việc diễn đạt ba yêu cầu đó thành SQL. Việc tính số lượng thuộc về SQL Server, nơi chứa dữ liệu đã đối soát.

**Bảng 3.4. Các phương án đã xem xét cho câu hỏi tiếng Việt**

| Phương án | Cách sử dụng | Căn cứ lựa chọn |
| --- | --- | --- |
| Ollama cục bộ | Chạy dịch vụ và mô hình trên máy trình diễn. | Đã thử hướng chạy cục bộ. Hồ sơ hiện có chưa lưu log đủ để kết luận lỗi cụ thể, tốc độ hoặc tỷ lệ trả lời đúng. |
| Gemini qua API | Gửi câu hỏi, mô tả cột và quy tắc tính. Nhận đề xuất SELECT có cấu trúc. | Có truy vấn đã chạy, mã mô hình trả lời và bảng SQL dùng để đối chiếu. Chọn cho nhánh hỏi tự nhiên. |
| Biểu mẫu có sẵn | Người dùng tự xác định phép tính, chỉ tiêu và chiều. | Giữ làm cách truy vấn chính khi cần kiểm soát bộ lọc hoặc khi dịch vụ AI không sẵn sàng. |

**Cấu hình phép thử Gemini**

Máy chủ yêu cầu phản hồi JSON với trạng thái, câu SQL và phần giải thích. Cấu hình sinh SELECT đặt temperature bằng 0, tối đa 1.600 token đầu ra và thời gian chờ 40 giây cho một lần gọi. Danh sách mô hình được lấy từ API, lọc theo khả năng sinh văn bản và thứ tự ưu tiên của dự án [8].

Ở lần kiểm tra phục vụ báo cáo, hệ thống báo có chín mô hình phù hợp. Đây là số lựa chọn tại thời điểm kiểm tra. Căn cứ để chấp nhận một câu trả lời vẫn là điều kiện lọc và bảng kết quả. Temperature thấp hoặc số lượng mô hình dự phòng không tự xác nhận mô hình đã hiểu đúng câu hỏi.

**Cấu hình lần gọi Gemini**

Máy chủ yêu cầu phản hồi dạng JSON theo lược đồ đã định, đặt temperature bằng 0, tối đa 1.600 token đầu ra và thời gian chờ 40 giây cho một lần sinh SQL. Dữ liệu gửi đi gồm câu hỏi và thông tin cần để viết truy vấn. Bảng kết quả được tính ở SQL Server sau khi câu lệnh qua bộ kiểm tra [8].

### 3.4.1. Vòng lặp đổi mô hình và điểm dừng

Cùng một câu hỏi có thể gặp hai trở ngại độc lập. Dịch vụ có thể tạm hết hạn mức, hoặc mô hình có thể trả câu SELECT sai quy tắc. Máy chủ thử lần lượt các mô hình đủ điều kiện và lưu lý do của lần thất bại. Khi nhận được kết quả hợp lệ, vòng lặp dừng ngay.

*Hình 3.2. Luồng tự động của một câu hỏi. Mũi tên quay lại chỉ lần chuyển sang ứng viên kế tiếp trong danh sách.*

Bộ kiểm tra đọc cấu trúc cú pháp AST của câu SQL, kiểm nguồn, tên cột và hàm. Kết nối dành cho truy vấn đọc mart. Với yêu cầu đếm, một SELECT hợp lệ vẫn có thể đếm nhầm đối tượng. Do đó, ngoài kiểm tra cấu trúc, người đọc phải so câu hỏi với WHERE, GROUP BY và tên phép tính.

Lỗi quyền hoặc xác thực dừng yêu cầu. Khi đã thử hết danh sách, giao diện báo lỗi và người dùng vẫn có thể chuyển sang bộ chọn. Khi một câu hỏi nêu năm ngoài phạm vi, máy chủ trả thông báo ngay trước bước gọi mô hình.

**Hai tình huống dễ nhầm trong lúc trình diễn**

Ca kiểm thử mô phỏng HTTP 429 xác nhận máy chủ chuyển sang mô hình kế tiếp. Nếu câu hỏi yêu cầu năm 2015 trong khi kho chỉ có 2012–2013, đổi mô hình sẽ không bổ sung được kỳ còn thiếu. Trong tình huống thứ hai, trả thông báo ngay giúp tránh lỗi bỏ điều kiện năm rồi vô tình trả tổng hai năm.

### 3.4.2. Đánh giá câu trả lời trên những câu hỏi có đáp án

Mỗi ca thử có một đáp án kiểm tra độc lập. Với câu hỏi ngoài phạm vi, hành vi đúng là thông báo phạm vi. Với câu hỏi hợp lệ, kiểm cả số dòng lẫn giá trị. Ví dụ, bốn con số của năm 2012 chỉ có ý nghĩa khi SQL vẫn giữ điều kiện năm 2012.

**Bảng 3.5. Kết quả kiểm tra truy vấn theo mục đích câu hỏi**

| Câu hỏi thử | Điều cần kiểm | Kết quả quan sát |
| --- | --- | --- |
| Tổng Profit năm 2013 | Lọc đúng năm trước khi SUM. | Hồ sơ chạy trên mart ghi 153.717. Tổng hai năm là 259.543. |
| Top 5 sản phẩm theo Sales năm 2013 | Nhóm theo sản phẩm, xếp tổng Sales giảm dần rồi lấy 5. | Hồ sơ thử ghi Colombian dẫn đầu với 65.487. |
| Đếm số ô theo Market năm 2012 | COUNT trên fact, bốn nhóm thị trường. | Lần chạy phục vụ báo cáo trả East 444, South 336, West 672, Central 672. |
| Tổng lợi nhuận năm 2015 | Phát hiện năm ngoài dữ liệu 2012–2013. | Giao diện trả thông báo ngoài phạm vi trước khi gọi AI. |

*Hình 3.3. Trạng thái thực tế của dịch vụ và thứ tự ứng viên trên giao diện trong lần kiểm tra.*

Riêng câu đếm được chạy lại từ giao diện. Mô hình `gemini-3.5-flash-lite` trả lời ở lần đầu. Cộng bốn nhóm được 2.124, khớp số dòng nguồn của năm 2012. Điều này chứng minh đúng ca lọc và đếm đã thử. Những câu diễn đạt theo cách khác vẫn cần đối chứng riêng.

Tỷ lệ đạt ca cần mẫu số là một bộ câu hỏi cố định. Các ca trên được chọn để minh họa những phép tính và lỗi cụ thể, chưa tạo thành bộ đánh giá đại diện cho mọi câu hỏi tiếng Việt. Vì vậy kết quả được công bố theo từng ca, cùng số đối chiếu hoặc thông báo thực tế.

## 3.5. Thiết kế phép thử dự báo doanh số tháng kế tiếp

Với câu hỏi dự báo, kết quả chưa có ở thời điểm trả lời. Dữ liệu được tổng hợp thành 96 quan sát, gồm 24 tháng cho mỗi thị trường. Mỗi lần thử chọn một tháng đích và chỉ dùng các tháng đã kết thúc trước đó. Một mô hình có thể làm tốt ở một giai đoạn nhưng phản ứng chậm khi mức doanh số đổi.

**Bảng 3.6. Ba giai đoạn của thử nghiệm dự báo một bước**

| Giai đoạn | Khoảng thời gian | Vai trò của số liệu |
| --- | --- | --- |
| Khởi tạo | 01/2012–03/2013, 15 tháng | Tạo các biến trễ và học hệ số ban đầu. |
| Chọn phương pháp | 04–09/2013, 6 tháng | 24 dự báo trên bốn thị trường. Chọn MAE thấp nhất. |
| Đánh giá cuối | 10–12/2013, 3 tháng | 12 dự báo. Giữ nguyên lựa chọn trước khi đọc kết quả. |

*Hình 3.4. Mỗi hàng là một lượt dự báo. Phần bên trái tháng đích là lịch sử đã biết ở lượt đó.*

**Ba họ phương pháp**

Naive lấy số kỳ trước. Trung bình trượt thử cửa sổ 2, 3 và 6 tháng. Ridge dùng Sales trễ 1, 2 và 3 tháng; các mức $\alpha$ là 0,1, 1 và 10. Tại mỗi mốc, bộ chuẩn hóa và Ridge chỉ được học từ dữ liệu đã có của thị trường đó.

Dự báo tháng 10 dùng lịch sử đến tháng 09. Khi chuyển sang dự báo tháng 11, doanh số thực của tháng 10 đã biết và có thể đưa vào lịch sử. Tháng đích luôn nằm sau mốc tính. Việc mở rộng lịch sử ở mỗi lượt khác với lập một lần cả ba dự báo từ cuối tháng 09 [9].

### 3.5.1. Kết quả lựa chọn và sai số ngoài mẫu

MAE là trung bình độ lớn của sai số, cùng đơn vị với Sales. Sai số âm và dương đều góp phần vào MAE nên không triệt tiêu nhau. RMSE lấy căn của trung bình bình phương sai số và nhạy hơn với lần dự báo lệch nhiều. Phương pháp được chọn theo MAE trên 24 dự báo ở giai đoạn lựa chọn.

**Bảng 3.7. Bảy cấu hình trên cùng các mốc thời gian**

| Cấu hình | MAE lựa chọn trên 24 dự báo | MAE kiểm tra trên 12 dự báo |
| --- | ---: | ---: |
| Trung bình 3 tháng MA3 | 223,28 | 225,22 |
| Trung bình 6 tháng | 231,31 | 152,00 |
| Trung bình 2 tháng | 244,15 | 213,42 |
| Sales kỳ trước | 258,83 | 221,75 |
| Ridge, $\alpha = 10$ | 275,22 | 200,59 |
| Ridge, $\alpha = 1$ | 292,93 | 213,33 |
| Ridge, $\alpha = 0,1$ | 298,87 | 215,95 |

MA3 đứng đầu ở giai đoạn lựa chọn. Đến ba tháng cuối, MAE của MA3 là 225,22, nhỉnh hơn mức 221,75 của cách lấy kỳ trước. Trung bình sáu tháng đạt 152,00 ở cột kiểm tra. Nếu sau khi xem cột này mới chọn sáu tháng, ta đã dùng chính dữ liệu kiểm tra để ra quyết định.

**Bảng 3.8. MAE của MA3 trên từng thị trường ở giai đoạn kiểm tra**

| Thị trường | Số tháng đánh giá | MAE theo đơn vị Sales |
| --- | --- | --- |
| Central / East | 3 cho mỗi thị trường | 259,78 / 205,33 |
| South / West | 3 cho mỗi thị trường | 58,11 / 377,67 |

**Một sai số cụ thể ở West**

Dự báo cho tháng 11/2013 là 11.777,33 trong khi doanh số thực tế là 11.300. Dự báo cao hơn 477,33. Trên đủ 12 dự báo kiểm tra, MA3 đạt RMSE 265,41 và MAPE 2,40%. Mỗi thị trường chỉ có ba tháng kiểm tra. MA3 được giữ làm mốc nghiên cứu cho dữ liệu tương lai, với giới hạn này ghi cùng kết quả.

Bảy cấu hình được so sánh trong vòng thử mở rộng trên cùng lịch chia. Kết quả bộ kiểm tra đã được biết từ lần thử cơ sở, vì vậy vòng mở rộng là đánh giá thăm dò. Muốn kiểm định lựa chọn trên dữ liệu hoàn toàn mới cần thêm kỳ thực tế sau tháng 12/2013.

## 3.6. Hồi quy giữa Marketing và Sales của cùng tháng

Nếu một thị trường chi nhiều hơn cho Marketing, doanh số cùng tháng thường thay đổi theo hướng nào? Mỗi thị trường được học một đường thẳng riêng, với $x$ là tổng Marketing và $y$ là tổng Sales trong cùng tháng. Phương trình ước lượng có dạng $\hat{y} = a + b \times x$. Hệ số $b$ cho biết độ dốc của đường đã học.

**Bảng 3.9. Thiết kế thử nghiệm hồi quy đơn biến**

| Thành phần | Cấu hình |
| --- | --- |
| Tập học | 18 tháng từ 01/2012 đến 06/2013 cho mỗi thị trường. Ước lượng hệ số chặn $a$ và hệ số góc $b$ trên tập này. |
| Tập kiểm tra | Sáu tháng từ 07/2013 đến 12/2013. Giữ nguyên hệ số rồi thay Marketing từng tháng để ước lượng Sales. |
| Mốc so sánh MAE | Dùng một số cố định là Sales trung bình của 18 tháng học, rồi tính sai số trên sáu tháng kiểm tra. |
| Tương quan | Pearson $r$ tính trên đủ 24 tháng để mô tả chiều và mức độ liên hệ tuyến tính quan sát được. |
| Đánh giá ngoài mẫu | MAE, RMSE và $R^2$ tính trên sáu tháng kiểm tra riêng của mỗi thị trường. |

Dự báo tháng tới ở mục 3.5 chỉ dùng doanh số quá khứ. Phép hồi quy ở đây cần biết Marketing của chính tháng được ước lượng. Ví dụ hệ số của West là 3,2312, nghĩa là trên đường thẳng đã học, hai mức Marketing cách nhau một đơn vị đi cùng hai mức Sales ước lượng cách nhau khoảng 3,23 đơn vị.

Mô hình chỉ có một biến giải thích. Số liệu quan sát không cô lập tác động của giá, mùa vụ hay phối hợp sản phẩm. Vì vậy hệ số có thể dùng để mô tả dữ liệu, còn việc quyết định tăng chi tiếp thị cần một thiết kế đánh giá khác.

**Thay một giá trị vào đường hồi quy**

Tại West, phương trình dùng hệ số chặn khoảng 4.925,21 và hệ số góc 3,23124. Tháng 12/2013 có Marketing bằng 1.982. Phương trình ước lượng Sales là 11.329,53, trong khi số thực là 11.883, chênh 553,47. Đây là một trong sáu sai số dùng để đánh giá West. Hệ số được giữ nguyên khi tính tất cả sáu tháng.

### 3.6.1. Diễn giải $R^2$ âm và quyết định về mô hình

**Bảng 3.10. Kết quả theo thị trường trên sáu tháng kiểm tra**

| Thị trường | Pearson $r^1$ | Hệ số $b$ | MAE | RMSE | $R^2$ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Central | 0,5623 | 4,9310 | 325,45 | 386,01 | −2,8745 |
| East | 0,7234 | 4,8075 | 274,75 | 295,67 | −2,0051 |
| South | 0,6205 | 3,4321 | 187,37 | 215,30 | −9,7109 |
| West | 0,7206 | 3,2312 | 333,87 | 397,89 | −1,5295 |

$^1$ Pearson $r$ mô tả toàn bộ 24 tháng. Hệ số $b$ học từ 18 tháng đầu. Ba cột sai số và độ phù hợp được tính trên sáu tháng cuối. Các cột này trả lời những câu hỏi khác nhau.

$R^2$ so tổng bình phương sai số của đường hồi quy với tổng bình phương độ lệch của Sales quanh trung bình tập kiểm tra. $R^2$ bằng 0 khi hai tổng bằng nhau. $R^2$ âm nghĩa là đường đã học lệch nhiều hơn mốc hằng bằng trung bình của sáu tháng kiểm tra. Trung bình này chỉ biết sau khi kỳ kiểm tra kết thúc [10].

**Bảng 3.11. Vì sao MAE có thể cải thiện trong khi $R^2$ vẫn âm?**

| Ví dụ West | Giá trị đối chiếu | Cách đọc |
| --- | --- | --- |
| MAE hồi quy và MAE mốc học | 333,87 so với 536,00 | Đường hồi quy giảm độ lệch tuyệt đối so với hằng số lấy từ 18 tháng đầu. |
| $R^2$ trên tập kiểm tra | −1,5295 | Theo sai số bình phương, đường hồi quy kém hơn hằng số trung bình của sáu tháng cuối. |

$R^2$ của West đạt khoảng 0,513 trên 18 tháng học nhưng giảm xuống −1,530 trên sáu tháng cuối. Rõ ràng đường thẳng có thể mô tả một phần biến thiên trong giai đoạn dùng để khớp hệ số mà vẫn cho ước lượng kém khi chuyển sang giai đoạn sau.

Cả bốn $R^2$ ngoài mẫu đều âm. Vì vậy, hồi quy Marketing–Sales được lưu như một thực nghiệm và không được chọn cho quy trình hỗ trợ quyết định ở Chương 4. Dữ liệu sinh thêm cũng không cung cấp thêm tháng thực để kiểm tra khả năng khái quát hóa [10].

## 3.7. Lựa chọn chức năng cho phiên bản trình diễn

Đánh giá một câu trả lời về quá khứ và đánh giá một dự báo cần hai tiêu chuẩn khác nhau. Với dữ liệu đã có, người dùng có thể kiểm lại con số đến từng nhánh. Với tháng chưa quan sát, chỉ có thể ước lượng sai số qua những lần kiểm tra ngoài mẫu.

**Bảng 3.12. Quyết định sau thực nghiệm**

| Phương pháp | Kết quả làm căn cứ | Vai trò trong báo cáo |
| --- | --- | --- |
| Khoan sâu theo quý | 32 tổ hợp thị trường – quý khớp hai tổng. Ca South cộng ngược được đến từng sản phẩm. | Chức năng chính để giải thích chênh lệch thực tế. |
| Bộ chọn sinh SQL | SQL, tham số và số liệu hiện cùng nhau. Người dùng kiểm được phạm vi. | Chức năng chính để đối chứng hoặc đặt câu hỏi tổng hợp khác. |
| Gemini Text-to-SQL | Có câu đếm, xếp hạng và tỷ lệ đã thử. Việc hiểu đúng cần kiểm từng câu. | Nhánh thử nghiệm có thể mở khi demo. Luôn kèm bảng và SQL. |
| Cube 3D trên web | Có lát cắt theo tháng và chế độ gom một số đo theo thị trường. | Trực quan bổ trợ đang phát triển. Đọc số chính thức ở bảng truy vấn. |
| Dự báo một bước | MA3 đạt MAE 225,22 trên 12 dự báo cuối. Số tháng kiểm tra còn ít. | Giữ kết quả nghiên cứu để so sánh khi có thêm kỳ thực tế. |
| Hồi quy Marketing | $R^2$ kiểm tra âm ở cả bốn thị trường. | Kết thúc ở phần thực nghiệm. |

**Cách xử lý khi các chỉ tiêu cho kết luận khác nhau**

Ở truy vấn mô tả, khớp tổng toàn chuỗi vẫn chưa đủ nếu bốn Market bị phân bổ sai. Từng nhóm phải khớp với cùng phạm vi nguồn. Ở bài toán dự báo, phương pháp có MAE thấp nhất trên ba tháng cuối chưa chắc là phương pháp sẽ chọn được trước khi thấy ba tháng ấy. Hai ví dụ này giải thích vì sao mỗi hàng trong bảng có một tiêu chí lựa chọn riêng.

Phần triển khai bắt đầu từ quý của một thị trường, dừng ở một sản phẩm cụ thể rồi cho phép kiểm kết quả bằng SQL. Bộ lọc và số đối chứng của từng bước được giữ lại để người đọc có thể thực hiện lại chuỗi thao tác.

---

# CHƯƠNG 4. TRIỂN KHAI HỆ THỐNG VÀ KIỂM CHỨNG TRÊN GIAO DIỆN

## 4.1. Tổ chức các thành phần khi vận hành

Điểm bắt đầu của phiên trình diễn là trang “Giải thích chênh lệch”. Người dùng chọn một thị trường và quý, đọc kết quả, rồi đi sâu đến sản phẩm. Khi cần đặt một câu hỏi khác, họ mở Query Studio để xem cả kết quả lẫn SQL. Hai thao tác này cùng đọc mart SQL Server đã được đối soát với cube ở Chương 2.

*Hình 4.1. Luồng dữ liệu và các điểm truy cập. Nhánh SSAS dùng để đối chứng. Giao diện truy vấn đọc mart qua máy chủ ứng dụng.*

Một máy chủ web cục bộ phục vụ các trang phân tích tại cổng 8504. Trang chênh lệch dùng đường dẫn `/quarter.html`, Query Studio dùng `/query.html`, còn Cube 3D ở đường dẫn gốc. Các đường dẫn này thể hiện những thao tác khác nhau trên cùng nguồn SQL Server.

Dashboard KPI và xuất CSV đã được kiểm tra riêng dưới dạng ứng dụng Streamlit. Phần sau ghi rõ khi nào ảnh thuộc dashboard này. URL cổng 8503 từng dùng cho bản SQLite tham chiếu. Phiên trình diễn SQL Server trong chương dùng cổng 8504.

Người xem có thể dừng sau khi đi hết một nhánh khoan sâu và giải thích được phép cộng. Nếu cần tự kiểm tra một con số khác trong phần hỏi đáp, Query Studio giữ một lối tra cứu độc lập với nhánh 3D.

### 4.1.1. Chuẩn bị nguồn dữ liệu và xác nhận đúng môi trường

Trước khi đọc KPI, cần xác nhận ứng dụng đang kết nối đến bản kho nào. Hai bản có thể cùng hiển thị trang web nhưng đọc dữ liệu khác nhau. Việc mở được giao diện chỉ xác nhận máy chủ web đã trả trang, chưa đủ để biết mart trả đúng số liệu.

**Bảng 4.1. Các điểm kiểm tra trước khi mở phiên trình diễn**

| Điểm kiểm tra | Cách thực hiện | Dấu hiệu cần thấy |
| --- | --- | --- |
| Nguồn của ứng dụng | Chạy máy chủ Cube Explorer với backend sqlserver, chọn database đã được SSIS nạp và cổng 8504. | Cấu hình truy vấn báo SQL Server. API dữ liệu cung cấp danh sách tháng, thị trường và nhóm sản phẩm. |
| Khoảng dữ liệu | Đối chiếu tháng đầu, tháng cuối, bốn thị trường và các tổng nguồn. | Từ 01/2012 đến 12/2013. Sales 819.811, kế hoạch 746.160, Profit 259.543. |
| Mart và cube | Kiểm tra hồ sơ Process Full, nguồn của cube và phép so MDX với SQL. | Bản tích hợp đã xử lý cube từ cùng kho. Hồ sơ đối soát cuối có 17/17 ca đạt. |
| Nhánh Gemini | Mở trạng thái dịch vụ từ Query Studio trước lúc đặt câu hỏi. | Hiện danh sách mô hình khả dụng theo tài khoản ở thời điểm kiểm tra. |

**Một phép thử nhanh sau khi mở trang**

Chọn South, quý III/2013. Nếu Sales là 13.554, kế hoạch là 13.180 và dòng tóm tắt ghi vượt 374, phép trừ đang dùng đúng bộ lọc quý này. Tiếp tục bấm tháng 08 để kiểm tra việc giữ bộ lọc đến cấp chi tiết. Chuỗi thao tác này kiểm tra cả đường đọc dữ liệu lẫn cách giao diện gom nhóm.

Khi dịch vụ Gemini gián đoạn, người dùng có thể tiếp tục tra cứu từ biểu mẫu và kiểm lại số liệu ở mart. Hai nhánh dùng chung kho dữ liệu nhưng chỉ nhánh ngôn ngữ tự nhiên phụ thuộc vào dịch vụ bên ngoài.

**Dấu hiệu của một lần đọc thiếu phạm vi**

Nếu truy vấn đang hỏi riêng năm 2013 mà lại trả đúng tổng Profit 259.543, phải mở phần SQL để kiểm năm. Tổng này thuộc trọn hai năm. Câu đối chứng Profit năm 2013 là 153.717. Kiểm được hai phạm vi giúp tránh nhầm một kết quả toàn kho với một kết quả năm.

## 4.2. Luồng gọi chức năng khoan sâu theo quý

Khi mở trang, trình duyệt gọi `GET /api/data` để nhận dữ liệu theo thị trường – tháng và sản phẩm – thị trường – tháng. Phần mô tả dữ liệu đi kèm cho biết mỗi sản phẩm thuộc nhóm nào. Sau lần nhận đó, mỗi lần chọn nhánh sẽ tính lại phần chi tiết ngay trên tập dữ liệu đang xem.

*Hình 4.2. Luồng gọi dữ liệu và xử lý lựa chọn trên trang chênh lệch. Các bước sau lần tải dữ liệu đầu diễn ra trong trình duyệt.*

Khi đổi thị trường hoặc quý, chương trình bỏ đường chọn cũ và tính lại từ cấp quý. Khi chỉ đổi tháng, quý và thị trường vẫn giữ nguyên. Các nhóm và sản phẩm ở hai cột sau được lấy từ đúng tháng mới. Đây là điều kiện để một con số cấp sản phẩm luôn có đủ ngữ cảnh.

Tháng được xếp theo thời gian. Trong tháng đã chọn, nhóm và sản phẩm được xếp theo chênh lệch tăng dần. Nhánh gợi ý ban đầu là nhánh có chênh lệch thấp nhất. Người dùng vẫn có thể bấm một nhánh vượt kế hoạch để xem phần nào đã bù vào khoản hụt.

**Bảng 4.2. Khi bấm một nhánh, các bộ lọc thay đổi thế nào?**

| Thao tác | Phạm vi giữ lại | Phần được tính lại |
| --- | --- | --- |
| Đổi quý của South | Giữ thị trường South. | Tất cả tháng, nhóm và sản phẩm trong quý mới. |
| Bấm nhóm Coffee | Giữ South và tháng đã chọn. | Các sản phẩm thuộc Coffee trong đúng kỳ. |
| Bấm một sản phẩm | Giữ tháng và nhóm hiện tại. | Thẻ chi tiết và đường dẫn mở lát cắt. |

### 4.2.1. Phiên trình diễn từ South đến từng sản phẩm

*Hình 4.3. Bộ lọc của phiên chạy trên SQL Server. Thị trường South và quý III/2013 xác định phạm vi cho các số phía dưới.*

*Hình 4.4. Màn hình trả tổng quý và chỉ ra tháng hụt. Doanh số 13.554 trừ kế hoạch 13.180 bằng +374.*

*Hình 4.5. Ba cột trên giao diện thật. Đọc lần lượt tháng 08/2013, nhóm Coffee và sản phẩm Colombian.*

Ở cột tháng, nhánh 08/2013 có Gap −9. Ngay bên phải, Coffee hụt 373 trong khi Herbal Tea và Espresso vượt lần lượt 48 và 316. Vì `−373 + 48 + 316 = −9`, khoản hụt lớn của Coffee chỉ còn thể hiện thành mức hụt nhỏ khi nhìn toàn thị trường.

*Hình 4.6. Sau khi bấm Decaf Irish Cream, thẻ chi tiết đổi sang Sales 465, kế hoạch 570 và chênh lệch −105.*

Hai sản phẩm của Coffee là Colombian với −268 và Decaf Irish Cream với −105. Bấm qua lại giữa hai sản phẩm cho phép kiểm rằng tháng, thị trường và nhóm vẫn giữ nguyên. Tổng hai khoản hụt bằng −373, đúng bằng nhãn của nhóm ở cột giữa.

Độ dài thanh chỉ dùng để so các mục trong cùng một cột. Muốn so hai cấp khác nhau, cần đọc số cạnh tên nhánh và cộng các giá trị có dấu.

## 4.3. Chạy truy vấn theo lựa chọn và đọc câu SQL

Trong Query Studio, chọn phép SUM, hai chỉ tiêu Sales và BudgetSales, nhóm theo Market và lọc năm 2013. Câu hỏi lúc này là thị trường nào có doanh số thực tế vượt kế hoạch bao nhiêu trong cả năm. Ứng dụng trả bảng theo thị trường để người dùng so hai cột.

*Hình 4.7. Trích biểu mẫu chọn phép tính, chỉ tiêu và góc nhìn trong phiên chạy. Phạm vi năm được kiểm lại ở tham số SQL.*

*Hình 4.8. Bảng bốn thị trường sau khi chạy bộ chọn trên mart. Mỗi dòng gộp đủ các ô thuộc cùng thị trường trong năm.*

*Hình 4.9. SQL và hai giá trị gắn với điều kiện ngày. Khoảng thời gian là từ đầu năm 2013 đến trước đầu năm 2014.*

Ví dụ West ghi nhận 139.029 doanh số so với kế hoạch 119.850, tức vượt 19.179. Con số này thuộc cả năm và toàn thị trường West. Nếu đổi năm hoặc chọn một sản phẩm, phải chạy lại truy vấn rồi đọc bộ tham số mới trước khi so với kết quả cũ.

Với cùng bộ lọc, Central vượt 10.185, East vượt 12.228 và South vượt 3.980. Tổng hợp các kết quả cho thấy cả bốn thị trường đều vượt kế hoạch trong năm 2013, dù vẫn có tháng và sản phẩm riêng lẻ bị hụt.

### 4.3.1. Hỏi bằng Gemini và kiểm tra câu trả lời

Một câu hỏi đếm được chạy ngay trên giao diện để kiểm tra trọn đường đi từ tiếng Việt tới bảng kết quả. Người dùng nhập “Đếm số ô dữ liệu theo Market năm 2012”. Hệ thống ghi nhận mô hình trả lời `gemini-3.5-flash-lite` và không có lần chuyển mô hình trong lượt này.

*Hình 4.10. Ô nhập câu hỏi tiếng Việt. Từ “đếm” và cụm “theo Market năm 2012” xác định ba yêu cầu cho SQL.*

*Hình 4.11. Bốn dòng do SQL Server trả về sau khi Gemini đề xuất truy vấn. Thứ tự dòng không ảnh hưởng phép đếm.*

*Hình 4.12. SQL thực tế của ca thử. COUNT(*) đếm dòng, WHERE giữ năm 2012 và GROUP BY Market chia thành bốn nhóm.*

East 444, South 336, West 672 và Central 672 cộng thành 2.124 dòng. Mỗi Market đều khớp số đếm độc lập từ các dòng nguồn năm 2012. Phải kiểm tra trực tiếp việc lọc năm vì một tổng trông hợp lý vẫn có thể được tạo từ phạm vi sai.

*Hình 4.13. Khi thay câu hỏi bằng tổng lợi nhuận năm 2015, giao diện báo chỉ có dữ liệu 2012 và 2013.*

## 4.4. Mở ngữ cảnh phân tích trên Data Cube 3D

Cube 3D trên web là tính năng trực quan đang phát triển. Tại trang khoan sâu, liên kết mang theo tháng, thị trường và tên sản phẩm đã chọn. Nhờ đó, người xem có thể mở đúng lát cắt mà không phải đặt lại ba bộ lọc bằng tay.

*Hình 4.14. Trích giao diện Cube 3D sau khi mở đường dẫn mang ngữ cảnh South, tháng 08/2013 và sản phẩm đang chọn.*

**Bảng 4.3. Cần đọc gì khi chuyển kết quả sang cube?**

| Trường hợp | Biểu diễn dự kiến | Số dùng để đối chứng |
| --- | --- | --- |
| Một sản phẩm trong một tháng | Nhấn mạnh lát cắt và sản phẩm được chọn. | Với Colombian ở South 08/2013, Sales 1.102 và kế hoạch 1.370. |
| Đếm một chỉ tiêu theo Market | Gom theo Market. Mỗi nhóm kết quả ứng với một khối. | Bốn Market của năm 2012 cộng lại thành 2.124 ô nguồn. |
| Xếp hạng nhiều sản phẩm của cả năm | Làm nổi các sản phẩm thuộc danh sách trả về. Thanh tháng cho biết kỳ đang xem. | Thứ hạng và tổng cả năm đọc ở bảng truy vấn. KPI của lát tháng có phạm vi hẹp hơn. |

Đường dẫn từ ca South mang tháng 08/2013, thị trường South và tên Colombian. Trên màn hình, ba bộ lọc cùng phản ánh đúng lựa chọn, còn thẻ KPI hiện 1.102, 1.370 và −268. Đây là cách nhận biết người dùng đã chuyển đến đúng sản phẩm trước khi xoay khối hoặc đổi tháng.

### 4.4.1. Đọc đúng bốn nhóm kết quả trong không gian ba chiều

Với câu đếm theo Market năm 2012, SQL chỉ có bốn dòng. Ứng dụng mang tên chỉ tiêu và từng cặp thị trường – giá trị sang chế độ gom nhóm. Nhờ đó, một khối đại diện cho một Market dù mỗi Market có dữ liệu ở nhiều tháng và nhiều sản phẩm.

*Hình 4.15. Chế độ gom theo thị trường sau câu đếm. Nhãn RecordCount xác định số đo của các khối.*

Bảng SQL luôn đi cùng câu hỏi ban đầu. Nếu hình đang thể hiện tháng trong khi bảng tổng hợp cả năm, người xem phải so lại tiêu đề kỳ trước khi đọc số. Một lát cắt đúng của cube chỉ trả lời trong các chiều và phép tổng hợp mà giao diện hỗ trợ.

**Bảng 4.4. Đối chiếu khi đọc màn hình 3D của câu đếm**

| Thông tin trên khối | Giá trị cần đọc | Đối chứng từ bảng SQL |
| --- | --- | --- |
| Số thị trường | 4 | Bốn nhãn East, South, West, Central. |
| Tổng RecordCount | 2.124 | 444 + 336 + 672 + 672. |
| Giá trị lớn nhất | 672 | West và Central cùng đạt 672. |

Một câu COUNT đếm số ô ở mức tháng, mã vùng và sản phẩm. Vì thế nhãn RecordCount trên hình rất quan trọng. Nếu đọc tổng 2.124 thành doanh số, ý nghĩa đã thay đổi dù con số trên hình hoàn toàn khớp bảng.

Giới hạn nội bộ 201 dòng của máy chủ gồm tối đa 200 dòng hiển thị và một dòng để phát hiện còn kết quả. Câu đếm chỉ có bốn nhóm nên giới hạn này không đổi số khối hoặc giá trị của từng nhóm.

## 4.5. Kiểm tra đổi bộ lọc trên dashboard KPI

Dashboard KPI phục vụ việc xem một kỳ, đi sâu vào bang hoặc sản phẩm và xuất dữ liệu chi tiết. Trong phiên nghiệm thu trình duyệt trên SQL Server, kịch bản West → East → West kiểm tra một lỗi thường khó phát hiện qua ảnh tĩnh: giao diện đã đổi tên thị trường nhưng số liệu vẫn còn ở bộ lọc trước.

*Hình 4.16. Ảnh nghiệm thu West tháng 01/2012. Các thẻ KPI ghi Sales 10.453, kế hoạch 9.460 và chênh lệch +993.*

*Hình 4.17. Cùng kỳ, sau khi chọn East, ba thẻ đổi thành 6.780, 6.180 và +600.*

**Bảng 4.5. Số đối chứng qua ba thao tác lọc liên tiếp**

| Trạng thái | Sales | Kế hoạch | Gap |
| --- | ---: | ---: | ---: |
| Chọn West | 10.453 | 9.460 | +993 |
| Chuyển sang East | 6.780 | 6.180 | +600 |
| Quay lại West | 10.453 | 9.460 | +993 |

Việc quay lại được West với đúng ba số cũ xác nhận trạng thái của East không rò sang lần chọn sau trong ca thử này. Đây là kết quả kiểm tra kỹ thuật trên trình duyệt. Thời gian và mức dễ sử dụng đối với người quản lý cần một phiên đánh giá có người tham gia.

West và East cùng đạt trên 100% kế hoạch trong tháng này. Tuy nhiên, +993 của West và +600 của East là chênh lệch theo đơn vị Sales. Tỷ lệ tương ứng phải lấy doanh số từng thị trường chia cho kế hoạch riêng của thị trường đó.

### 4.5.1. Đối chiếu tệp CSV tải xuống với phần đang xem

Người quản lý có thể mang kết quả từ dashboard sang Excel để kiểm tiếp. Phép nghiệm thu giữ nguyên West và tháng 01/2012 rồi tải hai loại bảng. Bảng sản phẩm gom các địa bàn theo sản phẩm, còn bảng chi tiết giữ từng mã vùng. Vì khác mức chi tiết, hai bảng có số dòng khác nhau.

*Hình 4.18. Giao diện bảng sản phẩm và chức năng xuất ở phiên nghiệm thu West. Bộ lọc thị trường và kỳ vẫn được giữ sau khi đi sâu.*

**Bảng 4.6. Đối chiếu kết quả xuất với bộ lọc West tháng 01/2012**

| Đầu ra | Mức chi tiết | Kết quả kiểm |
| --- | --- | --- |
| Bảng sản phẩm | Một sản phẩm trong thị trường và kỳ đang chọn | 12 sản phẩm. Colombian có Gap −276, là sản phẩm hụt nhiều nhất trong ca này. |
| CSV chi tiết | Tháng × mã vùng × sản phẩm | 56 dòng, một thị trường West, một tháng. Tổng Sales 10.453 và BudgetSales 9.460. |
| Thẻ thị trường | Tổng của tất cả dòng chi tiết cùng bộ lọc | Sales 10.453 − BudgetSales 9.460 = +993, bằng tổng đọc lại từ CSV. |

Không thể dùng 12 sản phẩm để kết luận chỉ có 12 dòng dữ liệu gốc. Một sản phẩm có thể được báo cáo ở nhiều mã vùng. Tệp chi tiết giữ các khóa đó nên có thể kiểm tra phép cộng từ dưới lên; tệp theo sản phẩm thuận tiện khi cần biết mặt hàng nào đóng góp vào kết quả.

## 4.6. Hiệu năng truy vấn trên bản sao thử tải

Giao diện đúng số liệu vẫn có thể phản hồi chậm khi phải tổng hợp nhiều dòng. Để đo riêng phần SQL, thử nghiệm nhân tải 500 lần trong bộ bảng biệt lập, tạo 2.124.000 dòng mỗi bảng. Các phương án được đối chiếu kết quả hai chiều trước khi so thời gian. Dữ liệu nhân tải chỉ phục vụ phép đo tốc độ.

**Bảng 4.7. Thời gian trung vị và số lần đọc trang logic trên SQL Server**

| Phép thử A → B | A (ms) | B (ms) | Reads A | Reads B |
| --- | ---: | ---: | ---: | ---: |
| Gom trực tiếp → dùng indexed view | 898 | 3 | 11.367 | 9 |
| Chèn dữ liệu khi chưa có → có indexed view | 10 | 29 | 4.354 | 17.031 |
| Một tháng, bảng thường → phân vùng | 107 | 27 | 11.367 | 474 |
| Toàn kỳ, bảng thường → phân vùng | 728 | 739 | 11.367 | 11.376 |
| Lát lọc hẹp, chưa có → có chỉ mục phụ | 96 | 0 | 11.367 | 6 |
| Lát lọc rộng, chưa có → có chỉ mục phụ | 346 | 300 | 11.367 | 8.958 |

Mỗi cặp có ba lượt làm nóng và 15 lượt đo cho từng phương án. Thời gian trong bảng thuộc câu lệnh trên máy chủ. Giá trị 0 ms ở lát lọc hẹp nằm sát độ phân giải phép đo. Thời gian mở cả trang web còn bao gồm đọc dữ liệu, truyền kết quả và vẽ giao diện.

Indexed view giảm số lần đọc khi phải gom lặp lại, nhưng phép chèn chịu chi phí duy trì kết quả đã tổng hợp. Phân vùng đem lại lợi ích rõ ở truy vấn một tháng vì chỉ đọc một trong 24 phân vùng; khi lấy toàn kỳ, cả 24 phân vùng đều được truy cập. Vì vậy lựa chọn tối ưu phụ thuộc vào bộ lọc của câu hỏi cụ thể.

Ca lọc hẹp chỉ khớp 500 trong số 2.124.000 dòng. Kế hoạch thực thi ghi nhận Index Seek ở ca này và Index Scan ở ca lọc rộng. Hai hình thức truy cập giúp giải thích vì sao cùng một chỉ mục phụ lại giảm số lần đọc rất khác nhau.

## 4.7. Kết quả nghiệm thu và phạm vi sử dụng

**Bảng 4.8. Những kết quả có thể kiểm tra lại khi trình diễn**

| Thao tác | Điểm đối chiếu | Bằng chứng và phạm vi |
| --- | --- | --- |
| Chọn quý rồi khoan sâu | South quý III vượt 374, tháng 08 hụt 9, nhóm Coffee hụt 373. | Mart sản phẩm khớp mart thị trường ở 32 quý – thị trường. Ảnh và số đo riêng cho nhánh South. |
| Chạy biểu mẫu | Lọc đúng năm, nhóm đúng Market và khớp tổng. | Bảng kết quả và SQL có hai tham số ngày, cùng xuất hiện trong phiên chạy. |
| Hỏi bằng tiếng Việt | Giữ năm 2012, trả bốn thị trường. Từ chối năm 2015. | Ảnh câu hỏi, SQL, kết quả và thông báo ngoài phạm vi. Gemini vẫn là chức năng thử nghiệm. |
| Xem khối 3D | Bảo toàn ngữ cảnh tháng, thị trường và sản phẩm. | Ảnh chụp một lát cắt. Các truy vấn phức tạp cần đọc lại bảng SQL. |
| Đổi bộ lọc và xuất CSV | KPI West khớp 56 dòng chi tiết, tổng Sales là 10.453. | Hồ sơ thử qua trình duyệt, kèm ảnh và tệp CSV đã tải. |

Bộ nghiệm thu dashboard trước đó ghi nhận 12/12 ca kỹ thuật qua trình duyệt tự động trên môi trường SQL Server thử. Các ca này xác nhận hành vi phần mềm trong điều kiện đã ghi nhận. Chưa có lượt UX với người dùng thật để kết luận dashboard giúp tiết kiệm bao nhiêu thời gian so với Excel.

**Trình tự kiểm tra khi đọc báo cáo**

Trước hết xác định kỳ và thị trường trên ảnh, sau đó cộng lại các nhánh con hoặc kiểm mệnh đề WHERE trong SQL. Với bản xuất CSV, so số dòng, tổng Sales và tổng kế hoạch ngay trên tệp đã tải. Trình tự này giúp khoanh vùng một sai lệch ở khâu lọc, tổng hợp hay xuất tệp.

Kết quả trọng tâm là một câu trả lời có thể lần ngược về dữ liệu. Ở quý III/2013, South vượt kế hoạch 374, nhưng riêng tháng 08, hai sản phẩm Coffee hụt tổng cộng 373. Các nhóm còn lại bù 364 nên thị trường chỉ còn hụt 9. Một báo cáo chỉ dừng ở tổng quý sẽ bỏ qua phần chênh lệch này.

---

# KẾT LUẬN

Báo cáo đã xây dựng và kiểm chứng trọn vẹn một hệ thống kho dữ liệu và phân tích đa chiều trên bộ dữ liệu kinh doanh chuỗi cà phê Coffee Chains giai đoạn 2012–2013, đi xuyên suốt từ một bản ghi nguồn cụ thể đến câu trả lời quản trị trên giao diện trực quan. Những kết quả đạt được của đề tài có thể tổng kết trên bốn khía cạnh chính:

1. **Xác lập mô hình dữ liệu chuẩn xác và bảo toàn ngữ nghĩa nguồn:**
   Từ 4.248 bản ghi của tệp `Coffee.csv`, đề tài đã xác định đúng mức chi tiết hạt nhân là một sản phẩm tại một mã vùng trong một tháng, triển khai thành công mô hình hình sao trên SQL Server gồm bảng sự kiện `dw.FactSalesPerformance` và ba bảng chiều `dw.DimDate`, `dw.DimLocation`, `dw.DimProduct`. Quy trình thiết kế giữ nguyên toàn bộ 11 chỉ tiêu số đo nguồn, các giá trị âm có ý nghĩa hạch toán và phân biệt rõ quy tắc tổng hợp giữa số đo cộng được hoàn toàn như doanh số, ngân sách, lợi nhuận với số đo tỷ lệ và số đo tồn kho bán cộng theo kỳ cuối.

2. **Đảm bảo tính toàn vẹn, khả năng truy vết và đối soát đa chiều qua SSIS, Data Mart và SSAS:**
   Quy trình nạp dữ liệu bằng gói SSIS cùng thủ tục `dw.usp_LoadCoffee` đã vượt qua các kịch bản nạp lịch sử 23 tháng, bổ sung tháng mới, phát lại tệp, điều chỉnh số đo, cô lập dòng lỗi vào nhật ký `audit.RejectedRow` và hoàn tác toàn bộ giao dịch khi xảy ra mâu thuẫn bộ đếm. Ở tầng khai thác, phép tổng hợp độc lập trước khi nối `FULL OUTER JOIN` đã loại bỏ triệt để lỗi nhân bản kế hoạch Fan-out. Khối phân tích đa chiều `Coffee Performance` trên SSAS sau khi xử lý từ chính kho dữ liệu do SSIS nạp đã đạt 17/17 ca đối soát MDX – SQL và 6/6 ô xoay trục Pivot. Nhờ đó, hệ thống giải thích tường minh hiện tượng bù trừ tại thị trường South quý III/2013: toàn quý vượt kế hoạch `+374`, riêng tháng 08/2013 hụt `−9`, nhưng bên trong nhóm Coffee thực chất hụt tới `−373` do hai mặt hàng Colombian hụt `−268` và Decaf Irish Cream hụt `−105`, được bù đắp bởi mức vượt `+364` từ nhóm Herbal Tea và Espresso.

3. **Đánh giá khách quan các phương pháp khai thác nâng cao và dự báo:**
   Việc thử nghiệm nhiều phương pháp khai thác trên cùng nền tảng kho dữ liệu giúp phân định rõ phạm vi áp dụng của từng công cụ. Chức năng khoan sâu theo quý và bộ chọn truy vấn có cấu trúc đóng vai trò trụ cột vì bảo đảm tính chính xác số học trên cả 32 tổ hợp thị trường – quý. Nhánh hỏi đáp tiếng Việt qua Gemini Text-to-SQL hỗ trợ sinh câu lệnh `SELECT` có kiểm tra cú pháp và phạm vi năm, luôn đi kèm câu lệnh SQL và bảng kết quả để người đọc tự đối chứng. Đối với bài toán dự báo một bước trên 96 quan sát thị trường – tháng theo cửa sổ thời gian mở rộng, phương pháp trung bình trượt 3 tháng MA3 đạt sai số lựa chọn thấp nhất với `MAE = 223,28` và sai số kiểm tra `MAE = 225,22`, vượt các cấu hình hồi quy Ridge phức tạp hơn. Ngược lại, mô hình hồi quy đơn biến giữa chi phí Marketing và Sales cùng tháng đều cho hệ số xác định $R^2$ ngoài mẫu âm ở cả bốn thị trường, qua đó được giữ lại làm kết quả thực nghiệm thay vì đưa vào quy trình ra quyết định.

4. **Giới hạn của đề tài và hướng phát triển tiếp theo:**
   Nguồn dữ liệu hiện tại mới bao phủ 24 tháng, chưa ghi nhận đơn vị tiền tệ, giá bán, số lượng hóa đơn hay các chương trình khuyến mãi tại từng điểm bán, đồng thời số tháng kiểm tra độc lập cho bài toán dự báo còn ít. Bên cạnh đó, việc nghiệm thu giao diện mới dừng ở các ca kiểm thử kỹ thuật tự động trên trình duyệt và các phép đo hiệu năng SQL trên tập dữ liệu nhân tải 2.124.000 dòng, chưa thực hiện phiên đo lường trải nghiệm với người dùng quản lý thực tế. Trong giai đoạn tiếp theo, hệ thống có thể được mở rộng bằng cách tích hợp thêm chiều khuyến mãi hoặc dữ liệu giao dịch cấp cửa hàng dựa trên các chiều dùng chung đã thiết kế, tiếp tục cập nhật các kỳ thực tế sau tháng 12/2013 để tái kiểm định mô hình dự báo, đồng thời tổ chức đánh giá người dùng thực tế để hoàn thiện trải nghiệm khai thác báo cáo.

---

# TÀI LIỆU THAM KHẢO (REFERENCES)

[1] Kaggle, *Coffee Chains Dataset (`Coffee.csv`)*. Truy cập tại: https://www.kaggle.com/datasets

[2] Kimball Group, *Additive, Semi-Additive, and Non-Additive Facts*. Truy cập tại: https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/additive-semi-additive-non-additive-facts/

[3] Microsoft Learn, *Online Analytical Processing (OLAP)*. Truy cập tại: https://learn.microsoft.com/en-us/azure/architecture/data-guide/relational-data/online-analytical-processing

[4] W. H. Inmon, *Building the Data Warehouse*, 4th ed. Indianapolis, IN, USA: Wiley Publishing, 2005. Truy cập tại: https://www.wiley.com/en-us/Building+the+Data+Warehouse%2C+4th+Edition-p-9780764599446

[5] R. Kimball and M. Ross, *The Data Warehouse Toolkit: The Definitive Guide to Dimensional Modeling*, 3rd ed. Indianapolis, IN, USA: John Wiley & Sons, 2013 (Four-Step Dimensional Design Process). Truy cập tại: https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/four-step-dimensional-design-process/

[6] Microsoft Learn, *Control Flow in SQL Server Integration Services (SSIS)*. Truy cập tại: https://learn.microsoft.com/en-us/sql/integration-services/control-flow/control-flow

[7] Microsoft Learn, *Dimension Relationships in SQL Server Analysis Services (SSAS Multidimensional)*. Truy cập tại: https://learn.microsoft.com/en-us/analysis-services/multidimensional-models/dimension-relationships

[8] Google AI for Developers, *Gemini API Documentation: Gemini Models and Supported Generation Methods*. Truy cập tại: https://ai.google.dev/gemini-api/docs/models/gemini

[9] R. J. Hyndman and G. Athanasopoulos, *Forecasting: Principles and Practice*, 3rd ed., Section 5.10: "Evaluating forecast accuracy / Time series cross-validation". Melbourne, Australia: OTexts, 2021. Truy cập tại: https://otexts.com/fpp3/tscv.html

[10] Scikit-learn Developers, *Scikit-learn User Guide: `r2_score` — Coefficient of Determination ($R^2$) and Common Pitfalls in Machine Learning*. Truy cập tại: https://scikit-learn.org/stable/modules/model_evaluation.html#r2-score
