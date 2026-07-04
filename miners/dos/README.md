# Bộ xác thực RustChain cho MS-DOS (16-bit Real Mode)

Mục này chứa mã nguồn bộ xác thực (validator) chạy trực tiếp trong chế độ thực 16-bit của MS-DOS / FreeDOS.

## Tính năng
- Đọc ngày của BIOS trực tiếp từ bộ nhớ vật lý `0xF000:0xFFF5`.
- Đăng ký ngắt `INT 1Ah` của BIOS để truy xuất số tick thời gian của hệ thống phục vụ tạo entropy.
- Tạo vòng lặp trễ để tính toán entropy ngẫu nhiên thực tế trên phần cứng cũ.
- Xuất kết quả xác thực ra tệp tin định dạng JSON `proof_of.json` tương thích với mạng RustChain.

## Hướng dẫn biên dịch

### Sử dụng Open Watcom
1. Tải và cấu hình Open Watcom C/C++ Compiler.
2. Chạy lệnh sau để biên dịch:
   ```bash
   wcl -0 -y -d0 miner.c
   ```
   Lệnh trên sẽ tạo ra tệp thực thi `miner.exe`.

### Sử dụng Borland C++ 3.1
Chạy lệnh biên dịch:
```bash
bcc -mt -lt miner.c
```

## Cách chạy ứng dụng
Chạy tệp thực thi trong DOSBox hoặc máy DOS thực tế:
```bash
miner.exe <địa_chỉ_ví_của_bạn>
```
Ứng dụng sẽ thực thi, in thông tin ngày BIOS cùng giá trị entropy ra màn hình, và xuất tệp `proof_of.json` ra thư mục hiện hành.
