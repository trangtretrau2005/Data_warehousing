# Trạng thái bộ khung ngày 13 tháng 11 năm 2026

> **Cập nhật riêng phần Trang ngày 19/11/2026:** đã tái lập TN12 West, chạy benchmark SQL Server TN07–TN10 và HRU/TN13 thật, tích hợp native serving và thao tác browser. Xem [hồ sơ mới](trang/README.md), [checklist chương7](chapters/ch07_trang.md) và [bàn giao native](TRANG_NATIVE_HANDOFF.md). Các mục dưới đây giữ mốc lịch sử 13/11; không còn là toàn bộ trạng thái hiện tại. UX người thật và bàn giao SSIS/SSAS của Chi vẫn riêng.

> **Bổ sung native 20/11/2026:** bản thích nghi riêng trên máy Trang đã có SSIS CSV **8/8 ca PASS** qua SSDT F5 và verifier exit 0, SCD Execute SQL package PASS riêng, cùng SSAS `CoffeeCube_Trang_20261120` trên `localhost\TRANGTRETRAU` **Processed/17 ca MDX–SQL đạt**. Kho SSIS thử cuối 4248 dòng, Sales 819811/Budget746160/Profit259543. [Biên bản và link evidence](TRANG_NATIVE_BUILD_20261120.md) phân biệt database, receipt, lỗi cũ và ảnh UI. [SQL chỉ đọc 39 PASS](../results/native_build_20261120/relational_acceptance/final/summary.json) bổ sung khóa/FK/JOIN/11 tổng, ba mart và TN05 bằng CTE có nhãn; không tạo stored mart mới hoặc hai nguồn actual/budget thật. Extension 2.2 đã cài nhưng chưa reboot; IDE có crash sau thành công lúc đổi viewport nên chưa khẳng định ổn định. Các bảng 13/11 bên dưới vẫn là lịch sử; UX người thật, native fault-injection rollback và bàn giao trên máy Chi vẫn riêng.

> **Chốt kiểm tra ngày 20/11/2026:** [rollback native 12/12 PASS](../results/native_build_20261120/relational_acceptance/rollback/20261120T142531Z_7f80dd10/verification.json) giữ nguyên hash logical của 11 bảng / 47.315 dòng; Browser đã có slice/drill/dice và pivot native ADOMD 6/6 ô, còn Query Designer UI chặn đổi trục. Build SSAS cuối **0 lỗi / 8 cảnh báo**. [Final summary](../results/native_build_20261120/final_summary.json) và [JUnit](../results/native_build_20261120/final_pytest.xml) ghi **141 tests / 0 fail / 0 error / 0 skip**, frontend 10/10, CLI demo/forecast exit 0. Chương 4–5 đã chốt các mục có bằng chứng trong phạm vi biệt lập; UX người thật và độ ổn định IDE sau reboot vẫn riêng. Tên đích local sau clone cần Configure-Designer rồi Build theo README SSAS, không deploy tự động.

Base đã có code chạy cục bộ cho profile nguồn, ETL staging–star–mart, audit/reject, nạp lại, sửa số, dashboard và dự báo theo protocol báo cáo. Script thực nghiệm có SCD1/2/3, nạp tăng dần và lựa chọn view HRU. Cấu trúc, checklist và code được chia theo Thanh1–3, Chi4–5, Trang6–7.

> **Nguồn cube cuối đã tích hợp:** [verification](../results/native_build_20261120/ssas/integrated_ssis_source/verification.json) xác nhận cube đọc chính `CoffeeDW_Trang_SSIS_TN03_20261120` do SSIS nạp, ProcessFull lúc `2026-11-20T14:58:07.690Z`, chạy lại 17/17 ca MDX và pivot 6/6 ô so SQL mới đều đạt. CONNECT+SELECT đúng bốn bảng nguồn, raw/`MySalesCube` giữ nguyên. Các receipt dùng nguồn 19/11 được giữ là lịch sử; không suy tích hợp chỉ từ parity hai DB.

## Đã chạy trên bản tham chiếu

- Profile: 4248 dòng hợp lệ, 24 tháng, 4 thị trường, 156 mã vùng, 13 sản phẩm; giữ đủ các cảnh báo số nguồn.
- ETL: tổng Sales819811, BudgetSales746160, Profit259543; phát lại không nhân bản; sửa cùng grain cập nhật số đo.
- Tải tăng dần: 23 kỳ4071 dòng/Sales784231; thêm kỳ mới thành4248/819811; lỗi mô phỏng6 hợp lệ/2 loại/Sales1139.
- SCD: Type2 lookup trước/đúng biên ra key1/key2, replay giữ2 phiên bản, không chồng khoảng; Type3 chỉ giữ một bước trước.
- Forecast: chọn moving_average_3 trên24 prediction validation, MAE223.28; test12 prediction MAE225.22; tương lai01/2014 chưa có actual.
- Dashboard AppTest: thiếu kho có hướng dẫn; bộ lọc01/2012 West→East→West trả đúng KPI; các trang, trạng thái rỗng và AI đọc kết quả tạo sẵn chạy được.

Đây là kết quả thực thi Python/SQLite và kiểm tra giao diện bằng Streamlit AppTest. Chưa phải kết quả người dùng thực hiện tác vụ hay bằng chứng xử lý trên SQL Server.

## Phần nhóm tiếp tục

| Hạng mục | Bộ khung đã có | Cần thực hiện |
| --- | --- | --- |
| SQL Server | DDL, ETL proc, cầu nối ODBC, mart, đối soát | Cấu hình instance/driver, chạy script và kiểm tra trên engine thật |
| SSIS | Quy tắc, mapping và hướng dẫn Control/Data Flow | Tạo/chạy project native, capture batch và đường lỗi |
| SSAS | Đặc tả dimension/hierarchy/measure và MDX mẫu | Tạo/deploy/process cube, đối chiếu Browser/MDX/SQL |
| Benchmark | Bản sao500 lần, indexed view/partition/index, protocol và mẫu raw runs | Thu plans, IO/TIME, dung lượng, chi phí ghi;15 lượt mỗi cấu hình |
| Dashboard SQL Server | Hợp đồng mart trùng tên/cột | Kết nối chỉ đọc mart và lưu forecast về ml.ForecastSales khi tích hợp native |
| UX | Tác vụ, đáp án và mẫu ẩn danh | Mời người thử Excel/web, đổi thứ tự và ghi số đo thật |
| Báo cáo | Bảy checklist và ánh xạ đủ bước/TN | Viết nội dung, chèn ảnh thật, kết luận sau khi đo |

Nhánh tích hợp/chạy thử là `dev`; các nhánh làm việc là `thanh`, `chi`, `trang`. `main` được giữ nguyên tại bản base cho tới khi Trang xác nhận bản tích hợp OK và yêu cầu cập nhật. Remote `origin` là repository GitHub của nhóm. Xem commit cụ thể bằng `git log` và GitHub; các thành viên bắt đầu theo [START_HERE](START_HERE.md) trên `dev` hoặc nhánh cá nhân. Các file Word nguồn và CSV gốc được giữ nguyên.
