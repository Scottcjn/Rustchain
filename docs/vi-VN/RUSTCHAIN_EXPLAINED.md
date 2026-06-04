# Giải thích RustChain (vi-VN)

RustChain là một mạng Proof-of-Antiquity thưởng cho các máy thật, đặc biệt là phần cứng cũ, khi chúng chứng minh rằng vẫn đang hoạt động. Ý tưởng cốt lõi rất đơn giản: phần cứng được giữ lại có giá trị, và mạng cần phân biệt được máy thật với VM, container hoặc khai báo bị tạo dựng.

## Cách quá trình kiểm tra hoạt động

Miner thu thập các tín hiệu cục bộ và gửi một `attestation` tới node RustChain. `attestation` này bao gồm một `fingerprint` phần cứng. Node dùng các dữ liệu đó để ước tính `antiquity` của máy và tính multiplier phần thưởng.

Quá trình này phải trung thực:

- không tự tạo kiến trúc CPU;
- không ép máy thành một dòng CPU mà nó không có;
- không sửa payload để máy trông có vẻ cũ hơn;
- không dịch flag dòng lệnh hoặc tên endpoint.

## Kiểm tra trước khi mining

Hãy dùng các lệnh dưới đây trước khi để bất kỳ miner nào chạy liên tục:

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

Các lệnh này giúp xem lại máy được phát hiện, payload `attestation` và kết nối tới node. Chúng phải được giữ chính xác như trên trong tài liệu đã bản địa hóa.

## Người dùng đồng ý với điều gì

Khi xác nhận lần chạy đầu tiên, người dùng tuyên bố rằng họ hiểu:

1. miner có thể gửi dữ liệu `fingerprint` và `attestation`;
2. phần cứng phải được báo cáo trung thực;
3. phần thưởng bằng `RTC` phụ thuộc vào việc mạng chấp nhận và không được đảm bảo;
4. spoofing, giả lập không khai báo hoặc payload bị tạo dựng có thể làm giảm phần thưởng hoặc bị từ chối.

Màn hình đồng ý tiếng Việt phải yêu cầu một input khẳng định rõ ràng, ví dụ `CO` (dạng không dấu của "Có" để dễ nhập trong terminal). Chỉ bấm Enter không được bắt đầu mining.

## Bảng thuật ngữ được giữ nguyên

| Thuật ngữ | Ý nghĩa vận hành |
|---|---|
| `RTC` | Token RustChain dùng cho phần thưởng và bounty. |
| `attestation` | Khai báo có thể kiểm chứng của máy gửi tới node. |
| `antiquity` | Thuật ngữ riêng của RustChain về tuổi đời, độ hiếm và mức độ bảo tồn của phần cứng. |
| `fingerprint` | Tập hợp tín hiệu phần cứng dùng để kiểm tra. |

## Hướng dẫn miner Linux

Hướng dẫn miner Linux đã bản địa hóa nằm tại:

- [miners/linux/README.vi-VN.md](../../miners/linux/README.vi-VN.md)
