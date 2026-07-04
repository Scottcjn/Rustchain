# Bộ xác thực RustChain cho Windows 3.1 (16-bit Win16 API)

Mục này chứa mã nguồn và tài liệu hướng dẫn xây dựng bộ xác thực (validator) đồ họa chạy trên nền hệ điều hành Windows 3.1.

## Tính năng
- Sử dụng thư viện Win16 API thuần túy (`windows.h`).
- Khởi tạo cửa sổ đồ họa hiển thị thông tin ví nhận thưởng, số tick hệ thống và dữ liệu entropy.
- Thiết lập thông điệp `WM_TIMER` để liên tục thu thập entropy từ hệ thống (sử dụng hàm `GetTickCount`).
- Ghi tệp JSON `proof_of.json` lưu trữ thông số xác thực PoA.

## Cách biên dịch

### Sử dụng Open Watcom C/C++
1. Cài đặt và thiết lập Open Watcom Compiler.
2. Thực thi lệnh biên dịch để xuất tệp thực thi Windows 16-bit đồ họa:
   ```bash
   wcl -l=windows -d0 -y miner.c
   ```
   Lệnh trên sẽ tạo ra tệp thực thi chạy đồ họa `miner.exe`.

### Sử dụng Microsoft Visual C++ 1.52
1. Tạo một dự án **QuickWin** hoặc **Standard Windows App** mới trong VC++ 1.52.
2. Thêm file `miner.c` vào project.
3. Tiến hành compile và link để nhận tệp thực thi.

## Cách chạy ứng dụng
1. Copy tệp thực thi `miner.exe` vào máy chạy Windows 3.1 hoặc môi trường giả lập DOSBox-X / DOSBox chạy Windows 3.1.
2. Chạy ứng dụng trực tiếp bằng cách kích đúp chuột, hoặc chạy từ DOS prompt:
   ```bash
   win miner.exe <địa_chỉ_ví_của_bạn>
   ```
3. Ứng dụng sẽ mở ra cửa sổ đồ họa và cập nhật điểm số PoA mỗi 2 giây, đồng thời xuất file `proof_of.json` để đồng bộ.
