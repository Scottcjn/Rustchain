# Hướng Dẫn Thiết Lập Miner RustChain

Thiết lập miner RustChain trên phần cứng của bạn và bắt đầu kiếm RTC thông qua
xác thực **Proof-of-Antiquity**. Phần cứng càng cũ càng có hệ số nhân cao hơn —
PowerPC G4 đạt 2.5× trong khi x86_64 hiện đại chỉ đạt 1.0×.

**Node mặc định:**
- `https://rustchain.org`

Node công cộng được phục vụ qua HTTPS. Các script miner hiện tại mặc định dùng
`https://rustchain.org`; chỉ ghi đè URL node khi bạn cố tình kiểm tra một
bản triển khai khác.

---

## Hệ Số Nhân Cổ Điển (Tham Khảo Nhanh)

| Phần cứng | Hệ số nhân |
|-----------|-----------|
| PowerPC G4 (trước 2003) | 2.5× |
| PowerPC G5 (2003–2006) | 2.0× |
| Apple Silicon (M1/M2) | 1.2× |
| x86_64 hiện đại (sau 2015) | 1.0× |
| ARM64 Linux (vd. Pi 4) | 1.3× |
| POWER8 (IBM) | 1.8× |

---

## Kiểm Tra Nhanh Trước Khai Thác

Nếu bạn chưa sẵn sàng bắt đầu vòng lặp khai thác, hãy chạy thử nghiệm khô (dry-run) trước. Đây là
cách kiểm tra tương thích an toàn nhất vì nó hiển thị thông tin phát hiện phần cứng, trạng thái
vân tay (fingerprint), và tình trạng node mà không đăng ký hay khai thác thực tế.

Điểm vào dry-run hiện tại là script miner Linux:

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
python3 -m venv .venv
source .venv/bin/activate
pip install requests
python3 rustchain_linux_miner.py --dry-run --show-payload
```

Đầu ra dự kiến ở mức cao:

```text
[FINGERPRINT] Running 6 hardware fingerprint checks...
OVERALL RESULT: ALL CHECKS PASSED
[DRY-RUN] RustChain Linux Miner preflight
[DRY-RUN] No mining or network state will be modified
[DRY-RUN] Node URL: https://rustchain.org
[DRY-RUN] CPU: Apple M3
[DRY-RUN] Cores: 8
[DRY-RUN] Memory(GB): 16
[DRY-RUN] Fingerprint pass status: True
[DRY-RUN] Health probe: HTTP 200
[DRY-RUN] Node version: 2.2.1-rip200
[DRY-RUN] Next real steps would be: attest -> enroll -> mine loop
```

CPU, số lõi, bộ nhớ và kết quả vân tay thay đổi tùy theo máy. Kiểm tra vân tay
thất bại vẫn hữu ích: hãy bao gồm toàn bộ đầu ra dry-run khi mở
issue hoặc yêu cầu bounty báo cáo phần cứng.

---

## Thiết Lập Theo Nền Tảng

### macOS (Apple Silicon & Intel)

#### Yêu Cầu

- macOS 10.15 Catalina trở lên
- Xcode Command Line Tools
- Python 3.8+

```bash
# Cài đặt Xcode CLI tools (bỏ qua nếu đã cài)
xcode-select --install

# Kiểm tra phiên bản Python
python3 --version   # phải từ 3.8+
```

Nếu Python cũ hơn 3.8, hãy cài đặt qua Homebrew:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.11
```

#### Cài Đặt & Cấu Hình

```bash
# 1. Clone kho lưu trữ
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/macos

# 2. Tạo môi trường ảo
python3 -m venv .venv
source .venv/bin/activate

# 3. Cài đặt thư viện phụ thuộc
pip install requests
```

#### Chạy

```bash
source .venv/bin/activate
python3 rustchain_mac_miner_v2.5.py \
    --miner-id your_wallet_nameRTC \
    --node https://rustchain.org
```

> **Apple Silicon:** Hồ sơ vân tay `arm64` được áp dụng tự động.
> Hệ số nhân của bạn là 1.2×. Không cần thêm bước nào.
>
> **Lưu ý dry-run:** Trong bản checkout hiện tại, macOS miner entrypoint chấp nhận
> `--miner-id`, `--wallet`, và `--node`, nhưng không chấp nhận `--dry-run`. Hãy dùng
> dry-run Linux ở trên nếu bạn chỉ cần báo cáo tương thích không khai thác.

---

### Linux — x86_64

#### Yêu Cầu

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git

# Fedora / RHEL / CentOS
sudo dnf install -y python3 python3-pip git

# Arch
sudo pacman -S python python-pip git
```

Kiểm tra Python >= 3.8:

```bash
python3 --version
```

#### Cài Đặt & Cấu Hình

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
python3 -m venv .venv && source .venv/bin/activate
pip install requests
```

Chạy dry-run trước:

```bash
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC --dry-run --show-payload
```

Chỉ bắt đầu khai thác sau khi đầu ra dry-run trông đúng:

```bash
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC
```

#### Chạy Dưới Dạng Dịch Vụ systemd

```bash
sudo tee /etc/systemd/system/rustchain-miner.service > /dev/null <<EOF
[Unit]
Description=RustChain Miner
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PWD
ExecStart=$PWD/.venv/bin/python3 rustchain_linux_miner.py \
    --wallet your_wallet_nameRTC
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now rustchain-miner
sudo journalctl -u rustchain-miner -f
```

---

### Linux — ARM64 (Máy chủ ARM 64-bit, cloud instances)

Cài đặt giống hệt Linux x86_64 ở trên. Hồ sơ vân tay `arm64_linux`
được tải tự động. Không cần thêm gói nào.

Xác nhận hồ sơ đúng được phát hiện khi khởi động:

```
[INFO] Hardware profile: arm64_linux (multiplier=1.3x)
```

---

### Windows (WSL — Windows Subsystem for Linux)

#### Yêu Cầu

1. Cài đặt WSL2 từ PowerShell (Quản trị viên):

```powershell
wsl --install
# Khởi động lại khi được nhắc, sau đó mở Ubuntu từ Start menu
```

2. Trong WSL Ubuntu:

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
```

#### Cài Đặt & Cấu Hình

Các bước trong WSL giống hệt Linux x86_64:

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
python3 -m venv .venv && source .venv/bin/activate
pip install requests
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC --dry-run --show-payload
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC
```

> **Lưu ý:** Vân tay phần cứng WSL được phân loại là `modern_x86` (hệ số nhân
> 1.0×). Windows chạy trực tiếp trên bare-metal chưa được hỗ trợ; WSL là
> phương pháp khuyến nghị.

---

### IBM POWER8

Máy POWER8 (vd. Talos II, Blackbird, máy chủ OpenPOWER) đạt hệ số nhân cổ điển
1.8×.

#### Yêu Cầu

```bash
# Fedora / CentOS Stream (ppc64le)
sudo dnf install -y python3 python3-pip git

# Ubuntu ppc64el
sudo apt install -y python3 python3-pip python3-venv git
```

Kiểm tra: `python3 --version` (phải >= 3.8)

#### Cài Đặt & Cấu Hình

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
python3 -m venv .venv && source .venv/bin/activate
pip install requests
```

Chạy:

```bash
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC --dry-run --show-payload
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC
```

Khi khởi động bạn sẽ thấy:

```
[INFO] Hardware profile: ppc64le / POWER8 (multiplier=1.8x)
```

> **SMT:** POWER8 có 8 luồng trên mỗi lõi. Vân tay sử dụng đường cơ sở
> một luồng để so sánh công bằng. Không cần điều chỉnh SMT.

---

### Raspberry Pi (Pi 3B+, Pi 4, Pi 5)

Raspberry Pi chạy ARM Linux và đạt hệ số nhân 1.3×.

#### Yêu Cầu (Raspberry Pi OS / DietPi / Ubuntu ARM)

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
```

Pi 3B+ đi kèm Python 3.7 mặc định trên các bản image cũ. Nâng cấp nếu cần:

```bash
sudo apt install -y python3.9 python3.9-venv
python3.9 -m venv venv
```

#### Cài Đặt & Cấu Hình

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
python3 -m venv .venv && source .venv/bin/activate
pip install requests
```

Chạy:

```bash
python3 rustchain_linux_miner.py --wallet mypiRTC --dry-run --show-payload
python3 rustchain_linux_miner.py --wallet mypiRTC
```

> **Pi Zero / Pi 2:** Các thiết bị này có CPU ARMv6/ARMv7. Sử dụng `python3.9` trở lên.
> Linux miner hiện tại lấy hồ sơ phần cứng từ các thăm dò hệ thống cục bộ,
> vì vậy không có cờ `--arch` thủ công trong CLI.

---

## Đầu Ra Xác Thực Thành Công

Khi mọi thứ hoạt động chính xác, bạn sẽ thấy đầu ra như sau:

```text
======================================================================
RustChain Local Linux Miner
RIP-PoA Hardware Fingerprint + Serial Binding v2.0
======================================================================
Node: https://rustchain.org
Wallet: your_wallet_nameRTC

[FINGERPRINT] Running 6 hardware fingerprint checks...
[1/6] Clock-Skew & Oscillator Drift...
  Result: PASS
[2/6] Cache Timing Fingerprint...
  Result: PASS
[3/6] SIMD Unit Identity...
  Result: PASS
[4/6] Thermal Drift Entropy...
  Result: PASS
[5/6] Instruction Path Jitter...
  Result: PASS
[6/6] Anti-Emulation Checks...
  Result: PASS

OVERALL RESULT: ALL CHECKS PASSED
[FINGERPRINT] All checks PASSED - eligible for full rewards
[DRY-RUN] RustChain Linux Miner preflight
[DRY-RUN] No mining or network state will be modified
[DRY-RUN] Health probe: HTTP 200
[DRY-RUN] Node version: 2.2.1-rip200
```

---

## Các Vấn Đề Thường Gặp & Cách Khắc Phục

### Lỗi `VM_DETECTED`

```json
{"error": "VM_DETECTED", "failed_checks": ["thermal_entropy", "clock_skew"]}
```

**Nguyên nhân:** Bạn đang chạy bên trong máy ảo (VirtualBox, VMware, WSL 1,
Docker, v.v.).  
**Khắc phục:** Chạy trên bare-metal. WSL2 vượt qua được trên kernel Windows hiện đại (>= 19041).
WSL1 thì không.

---

### `ModuleNotFoundError: No module named 'nacl'`

```
ModuleNotFoundError: No module named 'nacl'
```

**Khắc phục:**

Các entrypoint miner Linux và macOS hiện tại chỉ yêu cầu `requests` cho
đường dẫn miner cơ bản. Nếu bạn đang chạy script xác thực cũ có import
`nacl`, hãy cài đặt PyNaCl trong cùng môi trường ảo:

```bash
pip install PyNaCl
```

---

### `Connection refused` / `Failed to connect`

```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Nguyên nhân:** Sai NODE_URL hoặc node đang offline.  
**Khắc phục:**

```bash
# Kiểm tra kết nối
curl -fsS https://rustchain.org/health
```

Nếu bạn cố tình kiểm tra node riêng, hãy truyền nó bằng `--node`.

---

### Lỗi `HARDWARE_ALREADY_BOUND`

```json
{"error": "HARDWARE_ALREADY_BOUND", "existing_miner": "other_walletRTC"}
```

**Nguyên nhân:** Vân tay phần cứng của bạn đã được đăng ký trước đó với một
`miner_id` khác.  
**Khắc phục:** Sử dụng cùng `MINER_ID` như đăng ký ban đầu, hoặc liên hệ
cộng đồng Discord để yêu cầu rebind.

---

### Phát hiện Python 3.7 trở xuống

```
RuntimeError: Python 3.8+ required
```

**Khắc phục:** Cài đặt Python 3.9+ qua trình quản lý gói hoặc pyenv:

```bash
# pyenv (đa nền tảng)
curl https://pyenv.run | bash
pyenv install 3.11.8
pyenv global 3.11.8
```

---

### Xác thực thành công nhưng không có thưởng khi kết thúc epoch

**Nguyên nhân:** Miner được đăng ký sau hạn đăng ký của epoch.  
**Khắc phục:** Xác thực phải diễn ra trước slot 140 của epoch (144 slot mỗi
epoch). Theo dõi endpoint `/epoch` và đảm bảo bạn xác thực sớm trong epoch.

```bash
curl -fsS https://rustchain.org/epoch | python3 -m json.tool
```

Nếu `slot` > 140, hãy đợi epoch tiếp theo trước khi mong đợi phần thưởng.

---

*Hướng dẫn dành cho RustChain v2.2.1-rip200 · Node mặc định: https://rustchain.org*
