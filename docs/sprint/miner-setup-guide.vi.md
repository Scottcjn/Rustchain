     1|# Hướng Dẫn Thiết Lập Miner RustChain
     2|
     3|Thiết lập miner RustChain trên phần cứng của bạn và bắt đầu kiếm RTC thông qua
     4|xác thực **Proof-of-Antiquity**. Phần cứng càng cũ càng có hệ số nhân cao hơn —
     5|PowerPC G4 đạt 2.5× trong khi x86_64 hiện đại chỉ đạt 1.0×.
     6|
     7|**Node mặc định:**
     8|- `https://rustchain.org`
     9|
    10|Node công cộng được phục vụ qua HTTPS. Các script miner hiện tại mặc định dùng
    11|`https://rustchain.org`; chỉ ghi đè URL node khi bạn cố tình kiểm tra một
    12|bản triển khai khác.
    13|
    14|---
    15|
    16|## Hệ Số Nhân Cổ Điển (Tham Khảo Nhanh)
    17|
    18|| Phần cứng | Hệ số nhân |
    19||-----------|-----------|
    20|| PowerPC G4 (trước 2003) | 2.5× |
    21|| PowerPC G5 (2003–2006) | 2.0× |
    22|| Apple Silicon (M1/M2) | 1.2× |
    23|| x86_64 hiện đại (sau 2015) | 1.0× |
    24|| ARM64 Linux (vd. Pi 4) | 1.3× |
    25|| POWER8 (IBM) | 1.8× |
    26|
    27|---
    28|
    29|## Kiểm Tra Nhanh Trước Khai Thác
    30|
    31|Nếu bạn chưa sẵn sàng bắt đầu vòng lặp khai thác, hãy chạy thử nghiệm khô (dry-run) trước. Đây là
    32|cách kiểm tra tương thích an toàn nhất vì nó hiển thị thông tin phát hiện phần cứng, trạng thái
    33|vân tay (fingerprint), và tình trạng node mà không đăng ký hay khai thác thực tế.
    34|
    35|Điểm vào dry-run hiện tại là script miner Linux:
    36|
    37|```bash
    38|git clone https://github.com/Scottcjn/Rustchain.git
    39|cd Rustchain/miners/linux
    40|python3 -m venv .venv
    41|source .venv/bin/activate
    42|pip install requests
    43|python3 rustchain_linux_miner.py --dry-run --show-payload
    44|```
    45|
    46|Đầu ra dự kiến ở mức cao:
    47|
    48|```text
    49|[FINGERPRINT] Running 6 hardware fingerprint checks...
    50|OVERALL RESULT: ALL CHECKS PASSED
    51|[DRY-RUN] RustChain Linux Miner preflight
    52|[DRY-RUN] No mining or network state will be modified
    53|[DRY-RUN] Node URL: https://rustchain.org
    54|[DRY-RUN] CPU: Apple M3
    55|[DRY-RUN] Cores: 8
    56|[DRY-RUN] Memory(GB): 16
    57|[DRY-RUN] Fingerprint pass status: True
    58|[DRY-RUN] Health probe: HTTP 200
    59|[DRY-RUN] Node version: 2.2.1-rip200
    60|[DRY-RUN] Next real steps would be: attest -> enroll -> mine loop
    61|```
    62|
    63|CPU, số lõi, bộ nhớ và kết quả vân tay thay đổi tùy theo máy. Kiểm tra vân tay
    64|thất bại vẫn hữu ích: hãy bao gồm toàn bộ đầu ra dry-run khi mở
    65|issue hoặc yêu cầu bounty báo cáo phần cứng.
    66|
    67|---
    68|
    69|## Thiết Lập Theo Nền Tảng
    70|
    71|### macOS (Apple Silicon & Intel)
    72|
    73|#### Yêu Cầu
    74|
    75|- macOS 10.15 Catalina trở lên
    76|- Xcode Command Line Tools
    77|- Python 3.8+
    78|
    79|```bash
    80|# Cài đặt Xcode CLI tools (bỏ qua nếu đã cài)
    81|xcode-select --install
    82|
    83|# Kiểm tra phiên bản Python
    84|python3 --version   # phải từ 3.8+
    85|```
    86|
    87|Nếu Python cũ hơn 3.8, hãy cài đặt qua Homebrew:
    88|
    89|```bash
    90|/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    91|brew install python@3.11
    92|```
    93|
    94|#### Cài Đặt & Cấu Hình
    95|
    96|```bash
    97|# 1. Clone kho lưu trữ
    98|git clone https://github.com/Scottcjn/Rustchain.git
    99|cd Rustchain/miners/macos
   100|
   101|# 2. Tạo môi trường ảo
   102|python3 -m venv .venv
   103|source .venv/bin/activate
   104|
   105|# 3. Cài đặt thư viện phụ thuộc
   106|pip install requests
   107|```
   108|
   109|#### Chạy
   110|
   111|```bash
   112|source .venv/bin/activate
   113|python3 rustchain_mac_miner_v2.5.py \
   114|    --miner-id your_wallet_nameRTC \
   115|    --node https://rustchain.org
   116|```
   117|
   118|> **Apple Silicon:** Hồ sơ vân tay `arm64` được áp dụng tự động.
   119|> Hệ số nhân của bạn là 1.2×. Không cần thêm bước nào.
   120|>
   121|> **Lưu ý dry-run:** Trong bản checkout hiện tại, macOS miner entrypoint chấp nhận
   122|> `--miner-id`, `--wallet`, và `--node`, nhưng không chấp nhận `--dry-run`. Hãy dùng
   123|> dry-run Linux ở trên nếu bạn chỉ cần báo cáo tương thích không khai thác.
   124|
   125|---
   126|
   127|### Linux — x86_64
   128|
   129|#### Yêu Cầu
   130|
   131|```bash
   132|# Ubuntu / Debian
   133|sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
   134|
   135|# Fedora / RHEL / CentOS
   136|sudo dnf install -y python3 python3-pip git
   137|
   138|# Arch
   139|sudo pacman -S python python-pip git
   140|```
   141|
   142|Kiểm tra Python >= 3.8:
   143|
   144|```bash
   145|python3 --version
   146|```
   147|
   148|#### Cài Đặt & Cấu Hình
   149|
   150|```bash
   151|git clone https://github.com/Scottcjn/Rustchain.git
   152|cd Rustchain/miners/linux
   153|python3 -m venv .venv && source .venv/bin/activate
   154|pip install requests
   155|```
   156|
   157|Chạy dry-run trước:
   158|
   159|```bash
   160|python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC --dry-run --show-payload
   161|```
   162|
   163|Chỉ bắt đầu khai thác sau khi đầu ra dry-run trông đúng:
   164|
   165|```bash
   166|python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC
   167|```
   168|
   169|#### Chạy Dưới Dạng Dịch Vụ systemd
   170|
   171|```bash
   172|sudo tee /etc/systemd/system/rustchain-miner.service > /dev/null <<EOF
   173|[Unit]
   174|Description=RustChain Miner
   175|After=network.target
   176|
   177|[Service]
   178|Type=simple
   179|User=$USER
   180|WorkingDirectory=$PWD
   181|ExecStart=$PWD/.venv/bin/python3 rustchain_linux_miner.py \
   182|    --wallet your_wallet_nameRTC
   183|Restart=on-failure
   184|RestartSec=60
   185|
   186|[Install]
   187|WantedBy=multi-user.target
   188|EOF
   189|
   190|sudo systemctl daemon-reload
   191|sudo systemctl enable --now rustchain-miner
   192|sudo journalctl -u rustchain-miner -f
   193|```
   194|
   195|---
   196|
   197|### Linux — ARM64 (Máy chủ ARM 64-bit, cloud instances)
   198|
   199|Cài đặt giống hệt Linux x86_64 ở trên. Hồ sơ vân tay `arm64_linux`
   200|được tải tự động. Không cần thêm gói nào.
   201|
   202|Xác nhận hồ sơ đúng được phát hiện khi khởi động:
   203|
   204|```
   205|[INFO] Hardware profile: arm64_linux (multiplier=1.3x)
   206|```
   207|
   208|---
   209|
   210|### Windows (WSL — Windows Subsystem for Linux)
   211|
   212|#### Yêu Cầu
   213|
   214|1. Cài đặt WSL2 từ PowerShell (Quản trị viên):
   215|
   216|```powershell
   217|wsl --install
   218|# Khởi động lại khi được nhắc, sau đó mở Ubuntu từ Start menu
   219|```
   220|
   221|2. Trong WSL Ubuntu:
   222|
   223|```bash
   224|sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
   225|```
   226|
   227|#### Cài Đặt & Cấu Hình
   228|
   229|Các bước trong WSL giống hệt Linux x86_64:
   230|
   231|```bash
   232|git clone https://github.com/Scottcjn/Rustchain.git
   233|cd Rustchain/miners/linux
   234|python3 -m venv .venv && source .venv/bin/activate
   235|pip install requests
   236|python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC --dry-run --show-payload
   237|python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC
   238|```
   239|
   240|> **Lưu ý:** Vân tay phần cứng WSL được phân loại là `modern_x86` (hệ số nhân
   241|> 1.0×). Windows chạy trực tiếp trên bare-metal chưa được hỗ trợ; WSL là
   242|> phương pháp khuyến nghị.
   243|
   244|---
   245|
   246|### IBM POWER8
   247|
   248|Máy POWER8 (vd. Talos II, Blackbird, máy chủ OpenPOWER) đạt hệ số nhân cổ điển
   249|1.8×.
   250|
   251|#### Yêu Cầu
   252|
   253|```bash
   254|# Fedora / CentOS Stream (ppc64le)
   255|sudo dnf install -y python3 python3-pip git
   256|
   257|# Ubuntu ppc64el
   258|sudo apt install -y python3 python3-pip python3-venv git
   259|```
   260|
   261|Kiểm tra: `python3 --version` (phải >= 3.8)
   262|
   263|#### Cài Đặt & Cấu Hình
   264|
   265|```bash
   266|git clone https://github.com/Scottcjn/Rustchain.git
   267|cd Rustchain/miners/linux
   268|python3 -m venv .venv && source .venv/bin/activate
   269|pip install requests
   270|```
   271|
   272|Chạy:
   273|
   274|```bash
   275|python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC --dry-run --show-payload
   276|python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC
   277|```
   278|
   279|Khi khởi động bạn sẽ thấy:
   280|
   281|```
   282|[INFO] Hardware profile: ppc64le / POWER8 (multiplier=1.8x)
   283|```
   284|
   285|> **SMT:** POWER8 có 8 luồng trên mỗi lõi. Vân tay sử dụng đường cơ sở
   286|> một luồng để so sánh công bằng. Không cần điều chỉnh SMT.
   287|
   288|---
   289|
   290|### Raspberry Pi (Pi 3B+, Pi 4, Pi 5)
   291|
   292|Raspberry Pi chạy ARM Linux và đạt hệ số nhân 1.3×.
   293|
   294|#### Yêu Cầu (Raspberry Pi OS / DietPi / Ubuntu ARM)
   295|
   296|```bash
   297|sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
   298|```
   299|
   300|Pi 3B+ đi kèm Python 3.7 mặc định trên các bản image cũ. Nâng cấp nếu cần:
   301|
   302|```bash
   303|sudo apt install -y python3.9 python3.9-venv
   304|python3.9 -m venv venv
   305|```
   306|
   307|#### Cài Đặt & Cấu Hình
   308|
   309|```bash
   310|git clone https://github.com/Scottcjn/Rustchain.git
   311|cd Rustchain/miners/linux
   312|python3 -m venv .venv && source .venv/bin/activate
   313|pip install requests
   314|```
   315|
   316|Chạy:
   317|
   318|```bash
   319|python3 rustchain_linux_miner.py --wallet mypiRTC --dry-run --show-payload
   320|python3 rustchain_linux_miner.py --wallet mypiRTC
   321|```
   322|
   323|> **Pi Zero / Pi 2:** Các thiết bị này có CPU ARMv6/ARMv7. Sử dụng `python3.9` trở lên.
   324|> Linux miner hiện tại lấy hồ sơ phần cứng từ các thăm dò hệ thống cục bộ,
   325|> vì vậy không có cờ `--arch` thủ công trong CLI.
   326|
   327|---
   328|
   329|## Đầu Ra Xác Thực Thành Công
   330|
   331|Khi mọi thứ hoạt động chính xác, bạn sẽ thấy đầu ra như sau:
   332|
   333|```text
   334|======================================================================
   335|RustChain Local Linux Miner
   336|RIP-PoA Hardware Fingerprint + Serial Binding v2.0
   337|======================================================================
   338|Node: https://rustchain.org
   339|Wallet: your_wallet_nameRTC
   340|
   341|[FINGERPRINT] Running 6 hardware fingerprint checks...
   342|[1/6] Clock-Skew & Oscillator Drift...
   343|  Result: PASS
   344|[2/6] Cache Timing Fingerprint...
   345|  Result: PASS
   346|[3/6] SIMD Unit Identity...
   347|  Result: PASS
   348|[4/6] Thermal Drift Entropy...
   349|  Result: PASS
   350|[5/6] Instruction Path Jitter...
   351|  Result: PASS
   352|[6/6] Anti-Emulation Checks...
   353|  Result: PASS
   354|
   355|OVERALL RESULT: ALL CHECKS PASSED
   356|[FINGERPRINT] All checks PASSED - eligible for full rewards
   357|[DRY-RUN] RustChain Linux Miner preflight
   358|[DRY-RUN] No mining or network state will be modified
   359|[DRY-RUN] Health probe: HTTP 200
   360|[DRY-RUN] Node version: 2.2.1-rip200
   361|```
   362|
   363|---
   364|
   365|## Các Vấn Đề Thường Gặp & Cách Khắc Phục
   366|
   367|### Lỗi `VM_DETECTED`
   368|
   369|```json
   370|{"error": "VM_DETECTED", "failed_checks": ["thermal_entropy", "clock_skew"]}
   371|```
   372|
   373|**Nguyên nhân:** Bạn đang chạy bên trong máy ảo (VirtualBox, VMware, WSL 1,
   374|Docker, v.v.).
   375|**Khắc phục:** Chạy trên bare-metal. WSL2 vượt qua được trên kernel Windows hiện đại (>= 19041).
   376|WSL1 thì không.
   377|
   378|---
   379|
   380|### `ModuleNotFoundError: No module named 'nacl'`
   381|
   382|```
   383|ModuleNotFoundError: No module named 'nacl'
   384|```
   385|
   386|**Khắc phục:**
   387|
   388|Các entrypoint miner Linux và macOS hiện tại chỉ yêu cầu `requests` cho
   389|đường dẫn miner cơ bản. Nếu bạn đang chạy script xác thực cũ có import
   390|`nacl`, hãy cài đặt PyNaCl trong cùng môi trường ảo:
   391|
   392|```bash
   393|pip install PyNaCl
   394|```
   395|
   396|---
   397|
   398|### `Connection refused` / `Failed to connect`
   399|
   400|```
   401|ConnectionRefusedError: [Errno 111] Connection refused
   402|```
   403|
   404|**Nguyên nhân:** Sai NODE_URL hoặc node đang offline.
   405|**Khắc phục:**
   406|
   407|```bash
   408|# Kiểm tra kết nối
   409|curl -fsS https://rustchain.org/health
   410|```
   411|
   412|Nếu bạn cố tình kiểm tra node riêng, hãy truyền nó bằng `--node`.
   413|
   414|---
   415|
   416|### Lỗi `HARDWARE_ALREADY_BOUND`
   417|
   418|```json
   419|{"error": "HARDWARE_ALREADY_BOUND", "existing_miner": "other_walletRTC"}
   420|```
   421|
   422|**Nguyên nhân:** Vân tay phần cứng của bạn đã được đăng ký trước đó với một
   423|`miner_id` khác.
   424|**Khắc phục:** Sử dụng cùng `MINER_ID` như đăng ký ban đầu, hoặc liên hệ
   425|cộng đồng Discord để yêu cầu rebind.
   426|
   427|---
   428|
   429|### Phát hiện Python 3.7 trở xuống
   430|
   431|```
   432|RuntimeError: Python 3.8+ required
   433|```
   434|
   435|**Khắc phục:** Cài đặt Python 3.9+ qua trình quản lý gói hoặc pyenv:
   436|
   437|```bash
   438|# pyenv (đa nền tảng)
   439|curl https://pyenv.run | bash
   440|pyenv install 3.11.8
   441|pyenv global 3.11.8
   442|```
   443|
   444|---
   445|
   446|### Xác thực thành công nhưng không có thưởng khi kết thúc epoch
   447|
   448|**Nguyên nhân:** Miner được đăng ký sau hạn đăng ký của epoch.
   449|**Khắc phục:** Xác thực phải diễn ra trước slot 140 của epoch (144 slot mỗi
   450|epoch). Theo dõi endpoint `/epoch` và đảm bảo bạn xác thực sớm trong epoch.
   451|
   452|```bash
   453|curl -fsS https://rustchain.org/epoch | python3 -m json.tool
   454|```
   455|
   456|Nếu `slot` > 140, hãy đợi epoch tiếp theo trước khi mong đợi phần thưởng.
   457|
   458|---
   459|
   460|*Hướng dẫn dành cho RustChain v2.2.1-rip200 · Node mặc định: https://rustchain.org*
   461|