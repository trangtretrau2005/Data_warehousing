# Chẩn đoán VS/SSIS sau cài extension — chưa restart

Đọc thực tế trên máy ngày20/11/2026, không sửa registry/quyền, không dừng dịch vụ/process và không gọi DebugHost.

## Cập nhật sau suite thành công và crash lúc20:45

Suite `63d2403b-e12f-495d-a3ce-69efce27f1a6` đã thực thi bằng một lần F5 hợp lệ trong SSDT từ **20:41:12.439462 đến20:41:44.562889 (+07)**. Native parent ghi PASS với đủ tám receipt con; verifier chỉ đọc đối chiếu raw payload/SourceRow, parser chung và11 số đo của cả tám batch đều PASS. Kho cuối giữ4248 fact, Sales819811, BudgetSales746160, Profit259543. Xem [verification.json](../../../results/native_build_20261120/ssis/acceptance_runs/63d2403b-e12f-495d-a3ce-69efce27f1a6/verification.json).

Sau đó, root quan sát VS mất khi đã mở Data Flow thành công và đang đổi viewport/kéo kích thước. **Event1000 lúc20:45:43.640129 (+07)** xác nhận process `devenv.exe` PID `0x81C0` (=33216), version18.13.12412.241 bị exception `0xc0000409`, faulting module **unknown**. WER1001 lúc20:45:59 và20:46:05 ghi BEX64/StackHash_6501, ReportID `778ee947-aace-4061-b724-d965c9b163d2`. Log không xác định thao tác UI hay DLL nào là nguyên nhân. Crash này xảy ra sau receipt hoàn thành khoảng4phút; không phải bằng chứng tám tình huống ETL thất bại.

Bản thu chỉ đọc mới nằm tại [post_2045_20261120T2100](../../../results/native_build_20261120/ssis/readonly_diagnostics/post_2045_20261120T2100/): `events_after_2045.json`, `application_events.json`, `environment.json` và `processes.json`. Thời điểm thu chính xác được lưu trong `environment.json`. Snapshot process có VS mới PID39868 đang Responding và hai DtsDebugHost11652/11988 còn sống; không có Event1000/1001 mới cho DtsDebugHost trong phạm vi truy vấn sau20:45. Không dừng hoặc khởi chạy lại process nào khi chẩn đoán.

Kết luận hiện tại: **native acceptance PASS8/8; IDE Insiders vẫn có lỗi ổn định riêng chưa xác định nguyên nhân**. Yêu cầu reboot của MSI là có thật nhưng chưa chứng minh là nguyên nhân crash. Giữ run/receipt đã hoàn tất, không F5 lại vào DB đã có fact. Khi người dùng sẵn sàng bảo trì môi trường, lưu công việc rồi hoàn tất reboot installer yêu cầu và thử lại riêng thao tác Designer; chưa thể cam kết reboot sẽ sửa lỗi. Không tắt bảo vệ, đổi license, sửa ACL hay gọi trực tiếp DebugHost.

## Hygiene project và kiểm tra sau bàn giao

Ba `.gitignore` riêng trong `ssis/CoffeeETLTrang`, `ssis/CoffeeETLTrangAcceptance`, `ssas/CoffeeCubeTrang` chỉ bỏ output cục bộ `/bin/`, `/obj/`, `/Backup/`, `*.ispac`, `/__pycache__/`. Project ETL gốc còn bỏ đúng hai bản `CoffeeETLTrang 1.database`/`2.database` do phiên thử Designer tạo; descriptor được project tham chiếu vẫn là `CoffeeETLTrang.database`. Không xóa file hay sửa `.user`, `.dtproj`, `.dwproj`; `.dtsx`, schema, manifest, native source và project descriptor vẫn hiện trong Git để review.

`results/native_build_20261120/ssis/status.json` đã đổi từ snapshot trước chạy thành `PASS_SSDT_EIGHT_CASES`, ghi đủ8verifier PASS, raw landing21425dòng và fact4248dòng. Ba lỗi CLI cũ0xC000F427 vẫn được giữ ở `csv_dataflow_attempts`; bản status cũ nguyên byte và SHA256 được lưu trong thư mục chẩn đoán mới. Chúng là lịch sử standalone DTExec trước F5 thành công, không bị sửa thành một lần CLI thành công.

Kiểm tra metadata native và generator chỉ đọc: **7tests PASS**, log/JUnit tại `post_2045_20261120T2100/hygiene_tests.log` và `hygiene_tests.xml`. Test descriptor chấp nhận đúng vòng save SSDT thực tế: Manifest vẫn phải có ID hợp lệ, đủ package và ConfigurationSQLServer2022; các bản sao outer ProjectGuid/Packages là tùy chọn. Archive SDK nếu có vẫn phải chứa package byte-khớp và target160, các metadata còn lại phải khớp Manifest sau khi chuẩn hóa riêng TargetServerVersion dư thừa. `.ispac` là output ignore nên test archive sẽ ghi skip rõ lý do nếu chưa được build trên một clone mới; kiểm tra source descriptor vẫn chạy riêng.

## Điều đã thấy

- Application Error1000 lúc19:14:22 ghi `devenv.exe 18.13.12412.241`, exception `0xc0000409`, **Faulting module unknown**. WER1001 gọi sự kiện BEX64/StackHash_6501. Các log này không chỉ ra một DLL SSIS cụ thể là thủ phạm.
- Burn log ghi `SSDTISSingleton160` hoàn tất16:44:54 với `restart: Required`; apply tổng thể thành công nhưng `restarting: No`. LastBoot vẫn17/11/2026, nên chưa có reboot sau cài.
- Log MSI thật trong `%TEMP%/SsdtisSetup/…_9_SSDTISSingleton160.log` dòng693 ghi **`instapi160.dll` bị giữ đang dùng**. Dòng805 là lịch reboot để **xóa rollback backup `C:\Config.Msi\1042510c.rbf`**.
- File trên đĩa hiện tại `instapi160.dll` và `sqlboot.dll` đã là **2022.160.6009.0**, không còn bản1220 theo log cũ. Không tìm được từ registry đọc hiện tại bằng chứng một pipeline DLL SSIS cụ thể còn chờ thay thế.
- Không đọc được file chi tiết WER do Access Denied. Chưa có dump/stack xác định call gây fail-fast. Không thay ACL để đọc.

Vì vậy: **có yêu cầu restart thật, nhưng chưa đủ bằng chứng nói pending replacement gây crash hoặc restart chắc chắn sửa được**. Lỗi project thiếu Manifest đã được sửa riêng và Designer đã mở được; trạng thái đó cũng không bảo đảm debug runtime ổn định.

## Các bước không reboot có thể thử, do root/người dùng thực hiện

1. Lưu công việc, đóng Visual Studio bình thường rồi mở một process VS mới với đúng solution. Process mới có thể nạp DLL trên đĩa mới; đây là khả năng, không phải kết quả đã chứng minh.
2. Mở đúng `CoffeeETLTrangAcceptance.slnx`, chọn parent `00_AcceptAll` làm startup. Build trước, chưa F5; giữ ActivityLog/Output để tách lỗi load/build khỏi lỗi debug.
3. Nếu cần build không chạy bằng CLI, dùng **đường dẫn solution rõ ràng** và chỉ `/Build`, không `/Run`. Root cần phối hợp để không mở/reuse UI đang có công việc:

```powershell
& 'C:/Program Files/Microsoft Visual Studio/18/Insiders/Common7/IDE/devenv.com' '<root>/ssis/CoffeeETLTrangAcceptance/CoffeeETLTrangAcceptance.slnx' /Build Development /Out '<root>/results/native_build_20261120/ssis/acceptance_build.log'
```

Lệnh này chỉ được đề xuất, chưa chạy trong lượt chuẩn bị. Nếu VS18 không chấp nhận tên configuration, chọn configuration thực hiện trong Configuration Manager rồi giữ log, không sửa dữ liệu để che lỗi.

4. Nếu debug vẫn crash trước package entry, giữ event/log mới và hoàn tất yêu cầu reboot của installer lúc người dùng đã sẵn sàng. Không lặp F5 vô hạn, không tắt kiểm tra license/CFG hay gọi trực tiếp `DtsDebugHost.exe` như một workaround.

Script `Collect-ReadOnly.ps1` thu lại các bằng chứng trên vào `results/native_build_20261120/ssis/readonly_diagnostics/`; chỉ ghi file báo cáo, không thay hệ thống. No-reboot không có nghĩa có thể bảo đảm hoàn tất một cài đặt mà MSI đã yêu cầu restart.
