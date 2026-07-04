# Bộ xác thực RustChain cho Classic Mac OS (System 7.5 - 9.1)

Mục này chứa mã nguồn bộ xác thực (validator) tương thích với hệ điều hành Classic Mac OS của Apple chạy trên các bộ xử lý Motorola 68k và PowerPC.

## Tính năng
- Sử dụng Macintosh Toolbox API truyền thống (`Types.h`, `Files.h`, `OSUtils.h`).
- Đọc ngày giờ hệ thống bằng hàm `GetDateTime` và `SecondsToDate`.
- Thu thập giá trị xung nhịp hệ thống thông qua `TickCount` để sinh entropy làm cơ sở cho thuật toán Proof-of-Antiquity (PoA).
- Ghi tệp kết quả `proof_of.json` ra phân vùng đĩa HFS hiện hành.

## Cách biên dịch

### Sử dụng THINK C (dành cho máy 68k)
1. Tạo một project mới trong THINK C.
2. Thêm file `miner.c` vào project.
3. Thêm các thư viện tiêu chuẩn `MacTraps` và `ANSI`.
4. Chọn **Build Application** để xuất tệp thực thi.

### Sử dụng CodeWarrior (dành cho PowerPC / 68k)
1. Tạo một dự án MacOS C mới.
2. Liên kết mã nguồn `miner.c` cùng các thư viện hệ thống cần thiết.
3. Tiến hành compile để tạo tệp thực thi Classic Mac.

## Cách chạy ứng dụng
Sau khi build, bạn có thể chạy tệp thực thi trực tiếp trên máy Classic Macintosh thật hoặc trên các trình giả lập như Basilisk II hay SheepShaver. Chương trình sẽ tự động trích xuất thông tin hệ thống và ghi file kết quả xác thực ra đĩa.
