# Giải thích chênh lệch theo quý

## Bài toán

Một con số tổng của quý có thể che mất các tháng và sản phẩm đang hụt kế hoạch. Chức năng này trả lời câu hỏi: **Kết quả của một Market trong quý được tạo bởi những phần hụt và phần vượt nào?**

Người dùng chọn `Market` và `Quý`, sau đó đi qua bốn cấp:

```text
Quý → Tháng → Nhóm sản phẩm → Sản phẩm → ô trên cube 3D
```

Ứng dụng dùng dữ liệu đã tổng hợp trong `mart.vw_MarketProductPeriod`. Nó không huấn luyện mô hình và không suy đoán nguyên nhân kinh doanh. Kết quả là phép phân rã có thể cộng ngược để kiểm tra.

## Công thức

Tại mỗi cấp, ứng dụng tính:

```text
Sales      = SUM(Sales của các ô con)
BudgetSales = SUM(BudgetSales của các ô con)
Gap         = Sales − BudgetSales
```

- `Gap < 0` nghĩa là doanh số thực tế thấp hơn kế hoạch.
- `Gap > 0` nghĩa là doanh số thực tế vượt kế hoạch.
- Các Gap âm và dương có thể bù trừ khi cộng lên cấp cha.

Mỗi biểu đồ dùng chung mốc 0. Độ dài thanh chỉ so sánh các nhánh trong cùng cấp vì từng cấp có thang đo riêng.

## Ca trình diễn mặc định

Chọn `South · Q3/2013`:

| Cấp | Thành phần | Sales | BudgetSales | Gap |
| --- | --- | ---: | ---: | ---: |
| Quý | South Q3/2013 | 13.554 | 13.180 | +374 |
| Tháng | 07/2013 | — | — | +16 |
| Tháng | 08/2013 | 4.601 | 4.610 | −9 |
| Tháng | 09/2013 | — | — | +367 |
| Nhóm trong 08/2013 | Coffee | — | — | −373 |
| Nhóm trong 08/2013 | Herbal Tea | — | — | +48 |
| Nhóm trong 08/2013 | Espresso | — | — | +316 |
| Sản phẩm trong Coffee | Colombian | 1.102 | 1.370 | −268 |
| Sản phẩm trong Coffee | Decaf Irish Cream | 465 | 570 | −105 |

Hai phép đối soát quan trọng:

```text
16 − 9 + 367 = 374
−373 + 48 + 316 = −9
−268 − 105 = −373
```

Vì vậy, South vượt kế hoạch 374 trong cả quý nhưng vẫn có một nhánh cần chú ý: tháng 08/2013, nhóm Coffee, đặc biệt là Colombian.

## Cách trình bày trong khoảng một phút

1. Chọn `South` và `Quý 3/2013`.
2. Đọc kết quả quý: Sales 13.554, kế hoạch 13.180, vượt 374.
3. Chọn tháng 08/2013 vì đây là tháng duy nhất hụt kế hoạch, ở mức 9.
4. Chọn nhóm Coffee. Nhóm này hụt 373, còn Herbal Tea và Espresso bù lại tổng cộng 364.
5. Chọn Colombian. Sản phẩm này hụt 268 vì `1.102 − 1.370 = −268`.
6. Bấm **Mở ô này trên cube 3D** để xác nhận cùng tháng, Market và Product trên giao diện đa chiều.

Câu kết luận phù hợp là: **Dashboard xác định nơi đóng góp lớn nhất vào chênh lệch; muốn kết luận nguyên nhân cần thêm dữ liệu nghiệp vụ.**

## Kiểm tra kỹ thuật

- Kiểm tra 32 tổ hợp gồm bốn Market × tám quý.
- Mỗi quý có đúng ba nhánh tháng.
- Tổng Sales, BudgetSales và Gap của mart sản phẩm khớp mart Market tại từng Market–quý.
- Ca South Q3/2013 được khóa bằng các tổng và phép cộng ở trên.
- Nút mở cube đã được kiểm tra để chọn đúng `2013-08-01 · South · Colombian` ở chế độ lát cắt sản phẩm.
- Giao diện đã được kiểm tra ở 1.440 px và 390 px, không tràn ngang.

Chạy kiểm tra dữ liệu bằng:

```powershell
.\.venv\Scripts\python -m pytest -p no:cacheprovider -q tests/test_cube_explorer.py
```

Chạy ứng dụng SQL Server bằng:

```powershell
.\.venv\Scripts\python.exe apps/cube_explorer/server.py `
  --backend sqlserver `
  --database CoffeeDW_Trang_SSIS_TN03_20261120 `
  --port 8504
```

Sau đó mở [phần trình diễn chính](http://127.0.0.1:8504/quarter.html).
