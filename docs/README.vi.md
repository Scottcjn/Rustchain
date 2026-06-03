# Tài Liệu RustChain

> **RustChain** là một blockchain Proof-of-Antiquity thưởng cho phần cứng cổ điển với hệ số nhân khai thác cao hơn. Mạng sử dụng 6 kiểm tra vân tay phần cứng để ngăn máy ảo và giả lập nhận thưởng.

## Liên Kết Nhanh

| Tài liệu | Mô tả |
|----------|------|
| [Hướng Dẫn Thiết Lập Miner](sprint/miner-setup-guide.vi.md) | Thiết lập miner trên máy của bạn từng bước |
| [Bắt Đầu Nhanh](QUICKSTART.md) | Thiết lập nhanh ví, chạy miner, xác thực và nhận RTC |
| [Hướng Dẫn CLI](CLI.md) | Tham khảo dòng lệnh — miner, ví, node, attest |
| [Thiết Lập Ví](WALLET_SETUP.md) | Tạo và quản lý ví RTC |
| [Câu Hỏi Thường Gặp](FAQ.md) | Các câu hỏi và câu trả lời về khai thác |
| [Sách Trắng](WHITEPAPER.md) | Sách trắng kỹ thuật RustChain và thiết kế giao thức |
| [Hướng Dẫn Cho Nhà Phát Triển](DEV_GUIDE.md) | Chạy node, API và phát triển |
| [Đóng Góp](CONTRIBUTING.md) | Hướng dẫn đóng góp cho kho lưu trữ |
| [API](api-reference.md) | Tài liệu tham khảo API |

## Kiến Trúc

Tài liệu kỹ thuật chuyên sâu được tổ chức trong thư mục `docs/`:

### Giao Thức & Thiết Kế

| Tài liệu | Mô tả |
|----------|------|
| [Tổng Quan Giao Thức](protocol-overview.md) | Tổng quan kiến trúc RustChain |
| [Giao Thức](PROTOCOL.md) | Chi tiết giao thức cốt lõi |
| [Giao Thức v1.1](PROTOCOL_v1.1.md) | Cập nhật giao thức và sửa đổi |

### Khai Thác & Phần Cứng

| Tài liệu | Mô tả |
|----------|------|
| [Khai Thác Cổ Điển Được Giải Thích](VINTAGE_MINING_EXPLAINED.md) | Cách hoạt động của khai thác cổ điển |
| [Thiết Lập Khai Thác Console](CONSOLE_MINING_SETUP.md) | Thiết lập khai thác không đầu |
| [Vân Tay GPU](GPU_FINGERPRINTING.md) | Cách GPU được xác định và gắn dấu vân tay |
| [Điểm Chuẩn Tác Động CPU](CPU_IMPACT_BENCHMARK.md) | Điểm chuẩn RustChain trên phần cứng cổ điển |

### Ví & Tài Khoản

| Tài liệu | Mô tả |
|----------|------|
| [Hướng Dẫn Người Dùng Ví](WALLET_USER_GUIDE.md) | Hướng dẫn toàn diện về tính năng ví |
| [Hướng Dẫn Ví Đa Chữ Ký](MULTISIG_WALLET_GUIDE.md) | Thiết lập ví đa chữ ký |
| [Tương Thích CLI Ví 39](WALLET_CLI_COMPATIBILITY_39.md) | Thay đổi tương thích CLI ví |

### Node & Mạng

| Tài liệu | Mô tả |
|----------|------|
| [Hướng Dẫn Devnet](DEVNET.md) | Thiết lập và chạy node devnet |
| [Giao Thức Node P2P](NODE_P2P_PROTOCOL.md) | Giao thức truyền thông node |
| [Nguồn Cấp WebSocket](WEBSOCKET_FEED.md) | Nguồn cấp dữ liệu thời gian thực |
| [Vòi Testnet](TESTNET_FAUCET.md) | Nhận RTC testnet |

### Kinh Tế & Phần Thưởng

| Tài liệu | Mô tả |
|----------|------|
| [Kinh Tế Token](token-economics.md) | Mô hình kinh tế và phân phối token |
| [Kinh Tế Token v1](tokenomics_v1.md) | Thông số kỹ thuật kinh tế token ban đầu |

### Tích Hợp BoTTube

| Tài liệu | Mô tả |
|----------|------|
| [Nhúng BoTTube](BOTTUBE_EMBED.md) | Nhập nội dung BoTTube |
| [Tích Hợp BoTTube](BOTTUBE_INTEGRATION.md) | Tích hợp nâng cao |
| [Hệ Thống Tâm Trạng BoTTube](BOTTUBE_MOOD_SYSTEM.md) | Hệ thống tâm trạng và phát hiện |
| [Nguồn Cấp BoTTube](BOTTUBE_FEED.md) | Tích hợp nguồn cấp nội dung |

## Bắt Đầu

1. **Thiết lập miner của bạn** — làm theo [Hướng Dẫn Thiết Lập Miner](sprint/miner-setup-guide.vi.md)
2. **Tạo ví** — xem [Thiết Lập Ví](WALLET_SETUP.md)
3. **Bắt đầu khai thác** — chạy `python3 rustchain_linux_miner.py --wallet YOUR_WALLET_NAME_RTC`
4. **Nhận phần thưởng** — xác thực mỗi epoch và yêu cầu phần thưởng qua [Hướng Dẫn Yêu Cầu](CLAIMS_GUIDE.md)

## Hỗ Trợ

- **Discord:** Tham gia cộng đồng RustChain (liên kết trong README gốc của repo)
- **Báo cáo lỗi:** Mở issue trên GitHub với đầu ra `--dry-run --show-payload`
- **Bounty:** Xem [rustchain-bounties](https://github.com/Scottcjn/rustchain-bounties) để kiếm RTC
