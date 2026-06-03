# RustChain Miner cho Linux (vi-VN)

Hướng dẫn này bản địa hóa luồng cài đặt miner Linux cho người dùng tiếng Việt. Các thuật ngữ `RTC`, `attestation`, `antiquity` và `fingerprint` được giữ nguyên vì chúng xuất hiện trong protocol, log và API của RustChain.

## Kiểm tra trước khi tin cậy

Trước khi mining, hãy chạy các lệnh kiểm tra. Chúng cho bạn thấy dữ liệu nào sẽ được gửi tới node và cho phép xem payload trước khi bắt đầu một phiên mining.

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --show-payload --wallet YOUR_WALLET_ID
python3 miners/linux/rustchain_linux_miner.py --test-only --wallet YOUR_WALLET_ID
```

Không dịch hoặc thay đổi các flag ở trên. `--dry-run`, `--show-payload` và `--test-only` là các lệnh literal.

## Miner làm gì

Miner Linux phát hiện máy cục bộ, thu thập các tín hiệu phần cứng trung thực và gửi một `attestation` tới node RustChain. Các tín hiệu này tạo thành một `fingerprint` phần cứng dùng để đánh giá `antiquity` của máy và áp dụng multiplier phù hợp.

Miner không nên tự tạo kiến trúc CPU, tuổi đời phần cứng, số core, serial, hostname hoặc bất kỳ tín hiệu nào khác. Nếu một tín hiệu không có sẵn, hành vi đúng là khai báo rằng tín hiệu đó vắng mặt hoặc hạ mức kiểm tra.

## Cài đặt phụ thuộc

```bash
python3 --version
python3 -m pip install requests
```

Trên Debian/Ubuntu, nếu `python3` hoặc `pip` chưa được cài đặt:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip
```

## Chạy miner

```bash
python3 miners/linux/rustchain_linux_miner.py --wallet YOUR_WALLET_ID
```

Hãy dùng một wallet hoặc định danh mà bạn có thể nhận ra sau này. Payout bounty có thể dùng `github:ten-nguoi-dung`, nhưng mining thông thường dùng giá trị truyền vào `--wallet`.

## Đồng ý lần chạy đầu tiên

Trong lần chạy tương tác đầu tiên, người dùng phải xác nhận rõ ràng rằng họ hiểu:

- miner sẽ gửi dữ liệu `fingerprint` và `attestation` tới node RustChain;
- các lệnh kiểm tra nên được chạy trước khi mining;
- phần thưởng bằng `RTC` không được đảm bảo;
- máy phải tự khai báo trung thực, không spoof phần cứng.

Token xác nhận đồng ý là `CO` (viết không dấu để dễ nhập trong terminal). Đây là dạng không dấu của "Có".

## Tham chiếu chéo

Để đọc giải thích ngắn về protocol và các thuật ngữ được giữ nguyên, xem:

- [RUSTCHAIN_EXPLAINED.md](../../docs/vi-VN/RUSTCHAIN_EXPLAINED.md)

## Bảng thuật ngữ

| Thuật ngữ | Cách giữ nguyên | Ghi chú |
|---|---|---|
| `RTC` | `RTC` | Token gốc của RustChain. |
| `attestation` | `attestation` | Bằng chứng gửi tới node về máy. |
| `antiquity` | `antiquity` | Thuật ngữ riêng của RustChain về tuổi đời/độ hiếm tương đối dùng trong multiplier. |
| `fingerprint` | `fingerprint` | Tập hợp tín hiệu phần cứng. |
