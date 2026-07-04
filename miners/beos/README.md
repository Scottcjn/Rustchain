# Bộ xác thực RustChain cho BeOS / Haiku OS (C++ Native API)

Mục này chứa mã nguồn và hướng dẫn biên dịch bộ xác thực (validator) đồ họa native chạy trên BeOS hoặc hệ điều hành kế cận Haiku OS.

## Tính năng
- Sử dụng thư viện C++ native Kits của BeOS/Haiku (`Application Kit` và `Interface Kit`).
- Hiển thị giao diện đồ họa thông qua cấu trúc lớp kế thừa `BApplication`, `BWindow` và `BView`.
- Sử dụng hàm thời gian kernel `system_time()` để lấy xung nhịp hệ thống cực kỳ chính xác dưới dạng microsecond phục vụ sinh entropy.
- Cập nhật thời gian thực giao diện qua lớp truyền tin `BMessageRunner` mỗi 2 giây.
- Ghi tệp JSON `proof_of.json` ra phân vùng BFS hiện tại.

## Hướng dẫn biên dịch

Trên máy chạy Haiku OS, mở ứng dụng **Terminal** và chạy lệnh biên dịch bằng `g++` như sau:
```bash
g++ -o Miner miner.cpp -lbe
```
Trình biên dịch sẽ liên kết với thư viện `libbe` hệ thống và tạo ra tệp thực thi đồ họa `Miner`.

## Cách chạy ứng dụng
Chạy tệp thực thi trực tiếp từ Tracker (kích đúp chuột vào file `Miner`) hoặc khởi chạy từ dòng lệnh:
```bash
./Miner
```
Ứng dụng sẽ mở giao diện đồ họa và bắt đầu quá trình tính toán và tạo entropy liên tục, đồng thời tự động cập nhật file `proof_of.json` trong thư mục hiện hành.
