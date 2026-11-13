# SSAS Chương 5

Chi tạo project Analysis Services **Multidimensional** tại `ssas/CoffeeCube/`. Base có đặc tả và MDX khởi đầu; chưa có `.dwproj`/cube đã deploy. SQL Server Database Engine và SSAS là hai dịch vụ khác nhau; ghi rõ tên instance/phiên bản khi thu minh chứng.

1. Tạo Data Source tới CoffeeDW và Data Source View gồm dw.FactSalesPerformance, DimDate, DimLocation, DimProduct. Kiểm tra PK/FK và cardinality.
2. Tạo DimDate: key DateKey; hierarchy Year→Quarter→Month. Quarter key gồm Year+Quarter, Month key DateKey; không dùng riêng số tháng qua nhiều năm.
3. Tạo DimLocation key LocationKey; Market→State→AreaCode. Xác nhận AreaCode chỉ có một State và State chỉ có một Market trong nguồn. Nếu không đúng, dùng composite attribute key trước khi process.
4. Tạo DimProduct key ProductKey; ProductLine→ProductType→ProductName, Type như thuộc tính riêng. Xác nhận phụ thuộc của từng cấp.
5. Tạo cube `Coffee Performance`, measure group FactSalesPerformance; regular relationships tới ba chiều ở grain lá. Sales/BudgetSales/Profit/COGS/Marketing… dùng SUM. Gap=Sales−BudgetSales; Achievement=Sales/BudgetSales với IIF mẫu0 trả NULL. Inventory không SUM qua tháng: cấu hình LastNonEmpty nếu edition hỗ trợ, hoặc measure riêng truy vấn kỳ cuối. Không dùng SUM đa kỳ.
6. Deploy và Process Full. Lưu DSV, Dimension Usage, attribute relationships và process log. Không suy ra cube đã cập nhật chỉ vì ETL chạy xong.
7. Browser: slice01/2012/Central, drill tới State; tổng10346 và Budget9970. Dice Coffee/Central+East cùng tháng cho2663+2105=4768. Roll-up/pivot phải giữ tổng với cùng filter.
8. Đối chiếu `04_checks.sql` và `queries.mdx`, thay unique names theo metadata thực tế của project. Lưu query thực chạy, ảnh và chênh từng ô; cập nhật ch05.

Nếu thêm ForecastSales vào cube, tổng hợp actual lên Market–Month và chọn đúng ModelName/IssueMonth/ModelVersion trước khi drill-across. Forecast không có grain sản phẩm; tránh phân bổ giả xuống từng sản phẩm.
