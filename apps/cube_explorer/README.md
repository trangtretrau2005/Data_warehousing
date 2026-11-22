# Coffee Datacube — giao diện riêng của Trang

Ứng dụng khám phá Sales so với Budget theo **tháng × Market × sản phẩm**, dùng trực tiếp mart theo hợp đồng chương 4–5 của Chi. Giao diện này nằm riêng ở cổng **8503**; không thay dashboard cũ ở cổng 8501, không gọi mô hình AI hoặc dự báo và không ghi kho dữ liệu.

Mục tiêu của màn trình diễn: từ một khối số liệu, chọn lát cắt tháng/thị trường, xem sản phẩm đang hụt hay vượt kế hoạch, rồi phân rã một sản phẩm xuống State. Kết quả là xác định nơi cần kiểm tra tiếp; chênh lệch số liệu không tự chứng minh nguyên nhân kinh doanh.

## Mở thử

Tại root repo, dùng venv đã setup:

```powershell
.\.venv\Scripts\python.exe apps/cube_explorer/server.py
```

Mở [http://127.0.0.1:8503](http://127.0.0.1:8503). Mặc định đọc kho SQLite có sẵn tại `data/warehouse/coffee_dw.sqlite`. Nếu chưa có kho, chạy `python -m coffee_dw.cli demo` theo README root trước khi mở ứng dụng. Server không tự tạo database rỗng hoặc tự nạp nguồn khi một đường dẫn sai.

Để xem dữ liệu **SQL Server thật** trên database SSIS đã đối soát trên máy Trang:

```powershell
.\.venv\Scripts\python.exe apps/cube_explorer/server.py --backend sqlserver --database CoffeeDW_Trang_SSIS_TN03_20261120
```

Lệnh trên dùng instance local `.` và Windows authentication qua ODBC Driver 18. Không ghi connection string vào file hoặc log. Đối với cấu hình riêng khác, dùng `COFFEE_DW_SQLSERVER_CONNECTION` theo `.env.example`, rồi chạy với `--backend sqlserver` và **bỏ `--database`** để không nhầm hai cấu hình. Quyền tài khoản nên giới hạn ở SELECT mart/dimension phục vụ; runner yêu cầu kết nối ODBC read-only và chỉ thực thi SELECT cố định có parameter binding.

Đổi cổng bằng `--port 8504`; đổi kho tham chiếu có sẵn bằng `--db đường_dẫn.sqlite`. Server chỉ bind loopback (`127.0.0.1` hoặc `localhost`). Không chạy hai tiến trình trên cùng cổng; dừng server cũ bằng Ctrl+C trong terminal trước khi đổi backend. Backend được cố định lúc khởi động, không có chuyển nguồn ngầm.

## Liên hệ với phần Chi

| Thành phần của kho | Giao diện sử dụng như thế nào |
| --- | --- |
| `mart.vw_MarketPeriod` | KPI Sales/Budget/Profit/Gap và tỷ lệ trên tổng cùng lát cắt; 96 ô ở snapshot gốc |
| `mart.vw_MarketProductPeriod` | Các ô tháng–Market–sản phẩm; 1.008 ô ở snapshot gốc; roll-up theo nhóm sản phẩm để nhìn khối dễ hơn |
| `dw.DimProduct` | Đọc tên và ProductType cho phân cấp nhóm → sản phẩm |
| `mart.vw_Detail` | Truy vấn chỉ-đọc có tham số để drill từ ô sản phẩm xuống State |
| Quy tắc ETL/grain | Từ chối mart trùng khóa, thiếu số đo, Gap sai hoặc hai mart không đối soát theo từng ô |

Bản SQLite dùng các view và dimension tương đương, không có tiền tố schema. Ứng dụng không đọc CSV trực tiếp để giả làm kết nối kho. Database SQL Server trên máy Trang là môi trường thích nghi biệt lập từ hợp đồng/tài sản Chi, không chứng minh đã bàn giao hoặc chạy trên máy Chi.

Khối 3D là cách trực quan hóa kết quả **mart relational**, không phải kết nối trực tiếp SSAS/MDX. SSAS có bằng chứng thực chạy riêng trong `docs/TRANG_NATIVE_BUILD_20261120.md`. Không gọi giao diện 3D này là một engine OLAP mới hoặc bằng chứng hiệu năng cube.

## Một ca demo dễ giải thích

Chọn **08/2013 → South**: Sales **4.601**, Budget **4.610**, Gap **−9**. Khi phân rã theo sản phẩm, **Colombian −268**, **Decaf Irish Cream −105**, **Chamomile +22**. Các phần âm/dương bù trừ nhau; một vài sản phẩm riêng lẻ không đại diện tổng Market. Chọn Colombian để xem những State đang đóng góp vào Gap −268; tổng drill-down phải khớp ô sản phẩm đã chọn.

Một ô không có bản ghi không bị đổi thành số 0. `BudgetAchievement = SUM(Sales) / SUM(BudgetSales)`; budget bằng 0 trả thiếu. Nguồn chưa công bố loại tiền nên chỉ giữ đơn vị Sales nguồn. Không dùng số dòng như số đơn hàng và không cộng Inventory qua thời gian; ứng dụng này tập trung vào bốn số Sales/BudgetSales/Profit/Gap.

## Cấu trúc và kiểm tra

- `server.py`: HTTP local, API chỉ-đọc và phục vụ các tài nguyên giao diện trong allowlist.
- `data.py`: đọc hai mart, dimension sản phẩm và drill-down; đối soát grain, số đo, tỷ lệ và tổng từng ô.
- `index.html`, `styles.css`, `app.js`: giao diện tương tác riêng.
- `vendor/`: thư viện giao diện được lưu cục bộ theo phiên bản và giấy phép kèm theo.

Các API dùng JSON số hữu hạn, ngày `YYYY-MM-DD`, tỷ lệ thiếu là `null`:

- `GET /api/data`: `{meta, marketPeriod, productPeriod}`; snapshot đã kiểm nhất quán khi khởi động.
- `GET /api/drill?month=2013-08-01&market=South&product=Colombian`: `{rows,month,market,product,reconciliation}`; từ chối nếu kết quả đã đổi và không khớp snapshot.
- `GET /api/health`: trạng thái server và backend.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cube_explorer.py -q
```

Đợt kiểm tra 21/11/2026: **13/13 test backend đạt**, gồm snapshot gốc, không ghi SQLite, không tự tạo file kho thiếu, khóa/grain, số không hữu hạn, tổng hai mart, mẫu budget 0, drill có tham số, snapshot drift, JSON/API và bảo vệ đường dẫn static. Chạy thêm `-p no:cacheprovider` để không ghi cache trong workspace.

Controller giao diện có **10/10 kiểm tra Node VM đạt**, dùng API SQL Server thực: tổng hợp nhóm, ca South, drill State, export đúng filter, giữ số âm, chọn ô→bộ lọc, đổi trục không đổi tổng, đổi năm, ô thiếu và mẫu ngân sách 0. Chạy khi server SQL Server cổng 8503 đang mở:

```powershell
node --test tests/test_cube_explorer_frontend.js
```

File Node có thêm **4/4 ca hình học**, dùng Three.js thật và `CubeScene.prototype`: các ô ngoài cùng vẫn chọn được sau cắt/tách/đổi trục; ma trận/màu/bounds của1.008 ô hữu hạn; không chọn ô ẩn đang co lại; nhãn năm không trùng và hover cũ được xóa. Tổng Node **14/14 đạt**.

Các kiểm tra controller dùng DOM/scene giả; ca hình học dùng Three.js thật nhưng không khởi tạo renderer WebGL. Ở lần dựng đầu, công cụ browser bị dừng tại bước xác minh URL nên chưa có xác nhận hình hiển thị. Mốc cải thiện giao diện bên dưới đã kiểm lại bằng browser thực; vẫn không gọi các kiểm tra tự động hoặc phiên agent này là UX người thật.

## Những thao tác để xem thử

1. **Toàn khối**: ba trục tháng, Market và nhóm sản phẩm; kéo để xoay, cuộn để thu phóng, hoặc dùng phím mũi tên khi canvas có focus.
2. **Cắt lát**: giữ một tháng. **Tách lớp**: tách các tháng để dễ nhận diện. **Đổi trục**: đổi vị trí trục tháng/sản phẩm; số liệu vẫn giữ nguyên.
3. Bấm khối hoặc chọn bằng bộ lọc để cập nhật KPI, thẻ Market và sản phẩm; chuyển **Nhóm / Sản phẩm** để roll-up/drill-down.
4. Bấm **Vì sao South hụt 9?**, rồi Colombian để xem Gap −268 và phân rã State. Đây là phân rã số học, không kết luận nguyên nhân kinh doanh.
5. **Từ kho đến ứng dụng** nối ETL → hình sao → mart → thao tác hiện tại. Nút CSV xuất đúng tháng, Market và sản phẩm đang chọn.

Các khối có kích thước theo lưới phân loại; **màu**, không phải thể tích khối, biểu diễn số đo. Các ô không có bản ghi được giữ thiếu: ví dụ năm 2013 có 180 nhóm tháng–Market–ProductType, không tự bù thành 192 tổ hợp đầy đủ. Dữ liệu thư viện Three.js 0.170.0 lưu local cùng giấy phép MIT, app không cần CDN trong lúc chạy.

## Giao diện dễ đọc hơn — cập nhật 21/11/2026

Giao diện chia ba tab và giữ cùng bộ lọc giữa các tab:

- **Khối dữ liệu 3D**: xoay/cắt lát/tách lớp/đổi trục, xem kết quả và chọn ô. Ở khung hẹp, bộ lọc thu gọn để dành chỗ cho khối; bấm “Bộ lọc phân tích” để mở.
- **Phân tích chi tiết**: chọn tháng, Market, mức nhóm/sản phẩm; xem bốn thẻ KPI, so sánh Market và bảng sản phẩm có số Sales/Budget/Gap. Bấm một dòng để phân rã State; CSV dùng đúng phạm vi đang chọn.
- **Kho & ứng dụng**: xem luồng ETL → hình sao → mart và số liệu theo bộ lọc hiện tại.

Các tab hỗ trợ phím mũi tên, Home và End. Phần dữ liệu, công thức và quyền chỉ-đọc không đổi. Các kiểm tra controller bổ sung xác nhận tab chỉ hiện nội dung tương ứng, giữ lựa chọn và đồng bộ KPI/drill/CSV; kết quả kiểm tra hình hiển thị được lưu riêng theo phiên browser, không gọi là UX người thật.

**Kiểm tra bản làm mới:** 20/20 kiểm tra Node đạt, gồm 6 ca tab/bộ lọc mới. Browser thực đã được xem ở khung rộng1440px, khung hẹp527px và điện thoại390px; không thấy tràn ngang hoặc lỗi console. Chữ thân15px, nhãn13px, tiêu đề tab16px trên desktop; các vùng số liệu và khối 3D có màu riêng. Ca South/Colombian08/2013 trên tab phân tích cho Sales1102/Budget1370/Gap−268/80,4%, bốn State giữ tổng. Ảnh [bản desktop](../../results/cube_explorer/design_desktop_20261121.jpg) và [biên bản kiểm](../../results/cube_explorer/design_verification_20261121.json) lưu cục bộ; `results/` vẫn ignore. Viewport thử nghiệm đã reset về khung ban đầu sau kiểm tra. Chưa có phiên người tham gia hoặc bằng chứng tiết kiệm thời gian tác vụ.

Đọc SQL Server chỉ-đọc trong cùng đợt trên cả `CoffeeDW_Trang_SSIS_TN03_20261120` và `CoffeeDW_Trang_20261119`: **96/1.008 ô, 13 ánh xạ sản phẩm**, tổng Sales **819.811**, BudgetSales **746.160**, Profit **259.543**; drill Colombian/South/08-2013 cộng đúng **−268**. Đây là kiểm tra dữ liệu/backend, không thay cho phiên UX với người tham gia hoặc chứng minh ứng dụng giúp quyết định nhanh hơn.

Khởi động lại server để đọc một snapshot mart mới nếu ETL vừa thay dữ liệu. Ảnh/nhật ký kiểm tra giao diện có thể lưu chọn lọc trong `results/` theo quy ước của repo; không sửa ignore hoặc đưa database/credential lên Git.
