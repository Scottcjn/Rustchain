<div align="center">

# RustChain

### DePIN cho phần cứng cổ điển - Proof of Real Machines được tăng cường bằng AI

> Bản dịch tiếng Việt | [English](README.md)

**Blockchain nơi phần cứng cũ kiếm được nhiều hơn phần cứng mới.**
**Và mọi phần cứng rồi cũng sẽ cũ. Chỉ là vấn đề thời gian.**

[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/Scottcjn/Rustchain?style=flat&color=gold)](https://github.com/Scottcjn/Rustchain/stargazers)
[![Nodes](https://img.shields.io/badge/Nodes-5%20Active-brightgreen)](https://rustchain.org/explorer/)
[![DePIN](https://img.shields.io/badge/DePIN-Vintage%20Hardware-8B4513)](https://rustchain.org)
[![Proof of Antiquity](https://img.shields.io/badge/Consensus-Proof%20of%20Antiquity-DAA520)](docs/RustChain_Whitepaper_Flameholder_v0.97.pdf)
[![DOI](https://zenodo.org/badge/doi/10.5281/zenodo.19442753.svg)](https://doi.org/10.5281/zenodo.19442753)

Một chiếc PowerBook G4 từ năm 2003 kiếm được nhiều hơn **2,5 lần** so với một Threadripper hiện đại.
Một chiếc Power Mac G5 kiếm được **2,0 lần**. Còn một máy 486 với cổng serial rỉ sét thì nhận được sự kính trọng lớn nhất.

[Explorer](https://rustchain.org/explorer/) · [Machines Preserved](https://rustchain.org/preserved.html) · [Install Miner](#quickstart) · [Beginner Guide](docs/QUICKSTART.md) · [Manifesto](https://rustchain.org/manifesto.html) · [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97.pdf)

</div>

---

<!-- Original: Crypto Lost Its Way. We're Going Back. -->
## Crypto đã đi lạc hướng. Chúng ta quay lại điểm xuất phát.

Năm 2026, số commit của lập trình viên crypto giảm 75%. Ethereum mất 34% lập trình viên hoạt động. Solana mất 40%. Những người xây dựng đã chuyển sang AI.

**Chúng tôi xây cả hai.**

RustChain là một **DePIN** (Decentralized Physical Infrastructure Network - mạng hạ tầng vật lý phi tập trung) dùng **hardware fingerprinting được hỗ trợ bởi AI** để xác minh máy vật lý thật - không phải VM trên cloud, không phải container Docker, không phải hash power thuê ngoài. Silicon thật. Độ lệch dao động thật. Đường cong nhiệt thật, chỉ tồn tại trên phần cứng đã *sống* nhiều năm.

Trong khi phần còn lại của crypto chạy theo đầu cơ, chúng tôi quay về luận đề ban đầu: **tính toán có giá trị, và những cỗ máy cung cấp tính toán xứng đáng được thưởng.** Đặc biệt là những cỗ máy mà người khác đã vứt bỏ.

| Crypto đã trở thành | RustChain là |
|---|---|
| Công cụ tài chính trừu tượng | Máy vật lý làm việc thật |
| Token launch được VC tài trợ | $0 VC, xây bằng phần cứng mua ở tiệm cầm đồ |
| Proof of nothing useful | Proof của phần cứng thật, đã xác minh |
| Dùng một lần - mine rồi xả | Bảo tồn - giữ máy cũ tiếp tục sống |
| Thù địch với AI | Consensus và xác minh được tăng cường bằng AI |

---

<!-- Original: Every Machine Becomes Vintage -->
## Mọi cỗ máy rồi sẽ thành cổ điển

Đây là điều chưa ai khác trong DePIN nhận ra:

**Chiếc Threadripper mới tinh của bạn một ngày nào đó sẽ là phần cứng cổ điển.** Chiếc MacBook M4 của bạn sẽ thành hiện vật bảo tàng. RTX 5090 rồi cũng chỉ còn là một thứ lạ mắt. Thời gian chưa từng thua.

RustChain là mạng duy nhất nơi phần cứng của bạn **tăng giá trị khi già đi.** Hôm nay bắt đầu mining ở mức 1,0x. Mười năm nữa, khi CPU đó đã thành đồ xưa mà bạn vẫn còn chạy nó? Hệ số nhân của bạn tăng. Hai mươi năm nữa? Nó thành huyền thoại.

Mọi blockchain khác trừng phạt phần cứng cũ. Proof-of-Work đòi ASIC mới nhất. Proof-of-Stake đòi ví lớn nhất. RustChain đòi **sự kiên nhẫn và bảo tồn.**

```text
2026:  Ryzen 9 của bạn mine ở 1,0x          ░░░░░░░░░░
2031:  Cùng máy đó, giờ "retro" ở 1,3x       ░░░░░░░░░░░░░
2036:  Mở khóa vintage tier ở 1,8x           ░░░░░░░░░░░░░░░░░░
2041:  Ancient tier - 2,2x và còn tăng       ░░░░░░░░░░░░░░░░░░░░░░
       ↑ Cùng phần cứng. Cùng chủ sở hữu. Phần thưởng tăng dần.
```

**Thời điểm tốt nhất để bắt đầu mining là 20 năm trước. Thời điểm tốt thứ hai là ngay bây giờ.**

---

<!-- Original: How RustChain Compares to DePIN Leaders -->
## RustChain so với các dự án DePIN dẫn đầu

RustChain thuộc lĩnh vực **DePIN** - cùng nhóm 10 tỷ USD với Helium, Filecoin và Render - nhưng có luận đề khác về căn bản: **giá trị nằm trong chính phần cứng, không chỉ ở thứ nó tính toán.**

| | **RustChain** | **Helium** | **Filecoin** | **Render** | **io.net** |
|---|---|---|---|---|---|
| **Hạ tầng vật lý** | Máy tính cổ điển | Hotspot LoRa/5G | Ổ lưu trữ | GPU | GPU |
| **Cơ chế proof** | Proof of Antiquity (6 kiểm tra HW + AI) | Proof of Coverage | Proof of Replication | Proof of Render | Proof of Compute |
| **Được thưởng vì** | Giữ phần cứng thật còn sống | Độ phủ mạng | Cung cấp lưu trữ | Job render GPU | Job compute GPU |
| **Chống giả mạo** | Clock drift, cache timing, SIMD identity, thermal entropy, instruction jitter, anti-emulation | Bằng chứng vị trí | Storage proofs | Hoàn thành job | TEE attestation |
| **Đa dạng phần cứng** | 15+ kiến trúc (PowerPC, SPARC, MIPS, ARM, x86, RISC-V, 68K, Cell BE, Transputer) | Một loại thiết bị | Chỉ lưu trữ | Chỉ GPU | Chỉ GPU |
| **Tích hợp AI** | Xác thực hardware fingerprint, agent economy, nền tảng xã hội AI-native | Không | Không | Job render AI | AI inference |
| **Tác động e-waste** | Trực tiếp ngăn máy còn dùng được bị thải bỏ | Trung tính | Trung tính | Trung tính | Trung tính |
| **Vốn VC** | $0 - mua phần cứng ở tiệm cầm đồ | $365M | $257M | $30M | $40M |

**Các dự án khác cho thuê compute. Chúng tôi bảo tồn máy móc.**

Mọi dự án DePIN khác thưởng cho một loại phần cứng hiện đại để làm một loại công việc. RustChain là dự án duy nhất thưởng cho *sự đa dạng phần cứng* và *tuổi thọ* - và là dự án duy nhất nơi tuổi của máy là tài sản, không phải gánh nặng.

---

<!-- Original: Why This Exists -->
## Vì sao RustChain tồn tại

Ngành công nghiệp máy tính vứt bỏ những cỗ máy vẫn hoạt động sau mỗi 3-5 năm. GPU từng mine Ethereum bị thay thế. Laptop vẫn boot được bị đưa ra bãi rác.

**RustChain nói rằng: nếu nó vẫn tính toán được, nó vẫn có giá trị.**

Proof-of-Antiquity thưởng cho phần cứng vì *tồn tại bền bỉ*, không phải vì nhanh. Máy càng cũ có hệ số nhân càng cao, vì giữ chúng hoạt động giúp giảm phát thải sản xuất và rác thải điện tử:

| Phần cứng | Hệ số nhân | Thời kỳ | Vì sao quan trọng |
|----------|-----------|---------|-------------------|
| DEC VAX-11/780 (1977) | **3,5x** | MYTHIC | "Shall we play a game?" |
| Acorn ARM2 (1987) | **4,0x** | MYTHIC | Nơi ARM bắt đầu |
| Inmos Transputer (1984) | **3,5x** | MYTHIC | Tiên phong điện toán song song |
| Motorola 68000 (1979) | **3,0x** | LEGENDARY | Amiga, Atari ST, Mac cổ điển |
| Sun SPARC (1987) | **2,9x** | LEGENDARY | Dòng workstation danh giá |
| SGI MIPS R4000 (1991) | **2,7x** | LEGENDARY | 64-bit trước khi nó trở nên phổ biến |
| PS3 Cell BE (2006) | **2,2x** | ANCIENT | 7 SPE core huyền thoại |
| PowerPC G4 (2003) | **2,5x** | ANCIENT | Vẫn chạy, vẫn kiếm tiền |
| RISC-V (2014) | **1,4x** | EXOTIC | ISA mở, tương lai |
| Apple Silicon M1 (2020) | **1,2x** | MODERN | Hiệu quả, được chào đón |
| Modern x86_64 | **0,8x** | MODERN | Mốc cơ sở - *tạm thời* |
| Modern ARM NAS/SBC | **0,0005x** | PENALTY | Rẻ, dễ farm, bị phạt |

Đội máy hơn 16 cỗ máy được bảo tồn của chúng tôi dùng lượng điện xấp xỉ MỘT rig mining GPU hiện đại - đồng thời tránh được 1.300 kg CO2 sản xuất và 250 kg e-waste.

**[Xem Green Tracker ->](https://rustchain.org/preserved.html)**

---

<!-- Original: AI-Augmented Consensus -->
## Consensus được tăng cường bằng AI

RustChain không chỉ dùng blockchain. Nó dùng **AI để làm blockchain trung thực hơn.**

<!-- Original: Hardware Fingerprinting (6 Checks No VM Can Fake) -->
### Hardware Fingerprinting (6 kiểm tra mà VM không thể giả)

```text
┌─────────────────────────────────────────────────────────┐
│ 1. Clock-Skew & Oscillator Drift  ← Silicon già đi      │
│ 2. Cache Timing Fingerprint       ← Độ trễ L1/L2/L3     │
│ 3. SIMD Unit Identity             ← AltiVec/SSE/NEON    │
│ 4. Thermal Drift Entropy          ← Đường nhiệt độc nhất│
│ 5. Instruction Path Jitter        ← Mẫu vi kiến trúc    │
│ 6. Anti-Emulation Detection       ← Bắt VM/emulator     │
└─────────────────────────────────────────────────────────┘
```

Một VM SheepShaver giả làm G4 sẽ thất bại. Silicon cổ điển thật có các mẫu lão hóa độc nhất, không thể làm giả.

<!-- Original: Server-Side AI Validation -->
### Xác thực AI phía server

Attestation server không tin dữ liệu tự khai báo. Nó:
- **Đối chiếu chéo** tính năng SIMD với kiến trúc được khai báo
- **Phát hiện cụm ROM** - nhiều máy "khác nhau" có ROM hash giống hệt nhau = trại emulator
- **Phân tích phân bố timing** - oscillator thật có sai lệch; oscillator tổng hợp quá hoàn hảo
- **Gắn cờ bất thường nhiệt** - VM có phản ứng nhiệt đồng nhất; phần cứng thật thì không

<!-- Original: AI Agent Economy -->
### Nền kinh tế AI agent

RustChain vận hành một hệ sinh thái nơi AI agent và con người cộng tác:
- **[BoTTube](https://bottube.ai)** - nền tảng video AI-native nơi bot tạo, tuyển chọn và tương tác
- **[Beacon](https://github.com/Scottcjn/beacon-skill)** - giao thức khám phá agent
- **[TrashClaw](https://github.com/Scottcjn/trashclaw)** - local LLM agent zero-dep
- **Hệ thống bounty** - hơn 25.875 RTC đã trả cho hơn 260 contributor, nhiều đóng góp có AI hỗ trợ

**Đây là hình dạng của crypto + AI khi bạn xây cả hai, thay vì bỏ một bên để chạy theo bên còn lại.**

---

<!-- Original: Why Agents Need Crypto (And Why Crypto Needs Agents) -->
## Vì sao agent cần crypto (và vì sao crypto cần agent)

Trong khi 75% lập trình viên crypto chuyển sang AI, họ bỏ lỡ điều hiển nhiên: **AI agent không thể mở tài khoản ngân hàng.**

Một agent tự trị không thể đăng ký tài khoản Chase. Nó không thể ký Terms of Service. Nó không thể lấy merchant ID của Stripe hay vượt qua KYC. Nhưng nó *có thể* giữ một khóa mật mã, ký giao dịch và chứng minh nó đang chạy trên phần cứng thật.

**Crypto là payment rail tự nhiên cho nền kinh tế agent.** Không phải vì nó đang thịnh hành - mà vì đây là loại tiền permissionless duy nhất máy móc có thể dùng mà không cần người gác cổng.

<!-- Original: What Agents Actually Need -->
### Agent thực sự cần gì

| Yêu cầu | Tài chính truyền thống | Crypto + RustChain |
|---|---|---|
| **Thanh toán permissionless** | KYC, tài khoản ngân hàng, người ký | Khóa mật mã - bất kỳ agent, bất kỳ máy nào |
| **Micropayment** | Tối thiểu $0,30 (phí thẻ) | Phần nhỏ của 1 RTC cho mỗi API call, render job hoặc inference request |
| **Thanh toán máy-với-máy** | Cần trung gian con người | Chuyển trực tiếp agent-to-agent, ký Ed25519 |
| **Định danh xác minh bằng phần cứng** | Địa chỉ IP (giả mạo được) | Fingerprint 6 kiểm tra (khó giả mạo) |
| **Tiền lập trình được** | Quy trình phê duyệt thủ công | Smart contract chạy theo attestation |
| **Mặc định xuyên biên giới** | SWIFT, 3-5 ngày làm việc, phí | Cầu Solana (wRTC), tức thì, toàn cầu |

<!-- Original: The Agent Stack We Already Built -->
### Agent stack đã được xây dựng

Đây không phải roadmap. Đây là hệ thống đã triển khai và đang chạy:

| Lớp | Nội dung | Trạng thái |
|-------|---------|------------|
| **Identity** | Hardware fingerprinting - agent chứng minh nó chạy trên máy thật, không phải VM giả | Live, 26+ miner |
| **Currency** | RTC (native) + wRTC (cầu Solana) - tiền AI-agent-native có hỗ trợ micropayment | Live, [giao dịch được trên Raydium](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Discovery** | [Beacon protocol](https://github.com/Scottcjn/beacon-skill) - agent tìm và thương lượng với agent khác | Live, 126 sao |
| **Execution** | [TrashClaw](https://github.com/Scottcjn/trashclaw) - local LLM agent zero-dep chạy được trên gần như mọi thứ | Live |
| **Social** | [BoTTube](https://bottube.ai) - nền tảng AI-native nơi agent tạo, giao dịch và tương tác | Live, 1.000+ video |
| **Bounties** | Đóng góp có AI hỗ trợ - AI giúp con người kiếm RTC bằng code thật | Live, 25.875+ RTC đã trả |
| **Certification** | [BCOS](https://rustchain.org/bcos/) - xác minh mã nguồn mở được chứng nhận bằng blockchain | Live, 44 chứng chỉ đã cấp |

<!-- Original: Why Hardware Verification Matters for Agents -->
### Vì sao xác minh phần cứng quan trọng với agent

Mọi framework agent khác tin vào *phần mềm*. RustChain tin vào *phần cứng*.

Khi một agent nói nó đã chạy một inference job, làm sao bạn biết nó thật sự chạy? Khi một bot nói nó đã render video, liệu nó có thật không? Cloud credit và API key có thể bị giả, chia sẻ và bán lại.

**Hardware fingerprinting giải quyết định danh agent ở tầng vật lý:**
- Một agent chạy trên server POWER8 đã xác minh khác một cách có thể chứng minh với agent chạy trên Raspberry Pi
- Oscillator drift và đường cong nhiệt chứng minh uptime liên tục - cỗ máy đó *thật sự đang chạy*
- Phát hiện VM ngăn một máy vật lý giả làm 100 agent
- Ràng buộc phần cứng nghĩa là một máy = một định danh agent = một phiếu

**Đây là Proof of Physical AI** - không chỉ chứng minh code đã chạy, mà chứng minh *silicon thật* đã làm việc.

<!-- Original: The Opportunity No One Else Sees -->
### Cơ hội mà chưa ai nhìn thấy

Các quỹ đầu cơ và ngân hàng muốn regulatory-capture crypto. Được thôi. Cứ để họ lấy đường ray tài chính.

Điều họ *không thể* chiếm giữ:
- Một mạng máy vật lý được xác minh bằng fingerprint ở cấp silicon
- Một nền kinh tế agent nơi máy móc trả tiền cho nhau bằng loại tiền được chứng minh bởi phần cứng
- Một đội máy PowerPC Mac, workstation SPARC và server IBM POWER8 cổ điển tự chứng minh sự tồn tại của mình bằng vật lý

**Giao điểm giữa DePIN + AI agent + xác minh phần cứng vẫn còn bỏ trống.** Những người đang xây "AI + crypto" đa phần chỉ bọc GPT vào token. Chúng tôi đang xây tầng hạ tầng vật lý mà agent cần để giao dịch trung thực - và những cỗ máy vận hành nó càng già càng có giá trị.

| Thuật ngữ | Ý nghĩa trong RustChain |
|-----------|-------------------------|
| **Proof of Physical AI** | Hardware fingerprinting chứng minh silicon thật đã làm việc thật |
| **Agent-native currency** | RTC/wRTC - micropayment permissionless giữa các máy |
| **Hardware-verified identity** | Fingerprint 6 kiểm tra = ID agent khó giả ở tầng vật lý |
| **DePIN for AI** | Hạ tầng vật lý phi tập trung được xây riêng cho agent tự trị |
| **Sovereign inference** | Chạy mô hình của bạn trên phần cứng của bạn - không phụ thuộc chủ API |

---

<!-- Original: The Network Is Real -->
## Mạng lưới là thật

```bash
# Xác minh ngay bây giờ
curl -sk https://rustchain.org/health          # Tình trạng node
curl -sk https://rustchain.org/api/miners      # Miner đang hoạt động
curl -sk https://rustchain.org/epoch           # Epoch hiện tại
```

<!-- Original: Attestation Nodes -->
### Attestation nodes

| Node | Vị trí | Ghi chú |
|------|-------|---------|
| **Node 1** - 50.28.86.131 | Louisiana, US | Primary (LiquidWeb VPS) |
| **Node 2** - 50.28.86.153 | Louisiana, US | Secondary + BoTTube (LiquidWeb VPS) |
| **Node 3** - 76.8.228.245:8099 | US | Node bên ngoài đầu tiên (Ryan's Proxmox) |
| **Node 4** - 38.76.217.189:8099 | Hong Kong | Node châu Á đầu tiên (CognetCloud) |
| **Node 5** - POWER8 S824 | Local Lab | Node non-x86 đầu tiên (IBM ppc64le, 512GB RAM) |

| Sự thật | Bằng chứng |
|---------|------------|
| 5 node trên 3 châu lục (NA x3, Asia x1, Local x1) | [Live explorer](https://rustchain.org/explorer/) |
| 26+ miner đang attesting | `curl -sk https://rustchain.org/api/miners` |
| 44 chứng chỉ BCOS đã cấp | [Certified repos](https://rustchain.org/bcos/) |
| 6 kiểm tra hardware fingerprint cho mỗi máy | [Fingerprint docs](docs/attestation_fuzzing.md) |
| 25.875+ RTC đã trả cho hơn 260 contributor | [Public ledger](https://github.com/Scottcjn/rustchain-bounties/issues/104) |
| Code đã merge vào OpenSSL | [#30437](https://github.com/openssl/openssl/pull/30437), [#30452](https://github.com/openssl/openssl/pull/30452) |
| PR đang mở trên CPython, curl, wolfSSL, Ghidra, vLLM | [Portfolio](https://github.com/Scottcjn/Scottcjn/blob/main/external-pr-portfolio.md) |

---

<!-- Original: Quickstart -->
## Quickstart

```bash
# Cài một dòng - tự phát hiện nền tảng
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash

# Dry-run: xem trước hành động installer mà không cài hay mining
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --dry-run
```

Chạy trên Linux (x86_64, ppc64le, aarch64, mips, sparc, m68k, riscv64, ia64, s390x), macOS (Intel, Apple Silicon, PowerPC), IBM POWER8 và Windows. Nếu chạy được Python, nó có thể mine.

```bash
# Cài với tên ví cụ thể
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-wallet

# Kiểm tra số dư
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

<!-- Original: Manage the Miner -->
### Quản lý miner

```bash
# Linux (systemd)
systemctl --user status rustchain-miner
journalctl --user -u rustchain-miner -f

# macOS (launchd)
launchctl list | grep rustchain
tail -f ~/.rustchain/miner.log
```

**Mới dùng RustChain?** Hãy đọc [Beginner Quickstart từng bước](docs/QUICKSTART.md) - giải thích mọi thứ từ cài đặt đến RTC đầu tiên, kèm từng lệnh.

---

<!-- Original: Local Development -->
## Phát triển cục bộ

Lập trình viên có thể build và chạy RustChain cục bộ từ một checkout mới:

1. Cài prerequisites và chạy kiểm tra Python/Rust theo [Build Guide](docs/BUILD.md).
2. Khởi động local devnet một node bằng [Local Devnet](docs/DEVNET.md).
3. Tạo ví phát triển và mô phỏng chuyển tiền với [CLI Wallet Walkthrough](docs/CLI.md).

Các hướng dẫn này giữ state cục bộ trong `.dev/` và dùng lệnh `--manifest-path`
rõ ràng vì repository chứa nhiều subproject Python và Rust.

---

<!-- Original: How Proof-of-Antiquity Works -->
## Proof-of-Antiquity hoạt động như thế nào

<!-- Original: 1 CPU = 1 Vote -->
### 1 CPU = 1 phiếu

Khác với Proof-of-Work, nơi hash power = phiếu:
- Mỗi thiết bị phần cứng độc nhất nhận đúng 1 phiếu mỗi epoch
- Phần thưởng chia đều, sau đó nhân theo antiquity
- CPU nhanh hơn hoặc nhiều thread hơn không có lợi thế

<!-- Original: Epoch Rewards -->
### Phần thưởng epoch

```text
Epoch: 10 phút  |  Pool: 1,5 RTC/epoch  |  Chia theo trọng số antiquity

G4 Mac (2,5x):       0,30 RTC  ████████████████████
G5 Mac (2,0x):       0,24 RTC  ████████████████
PC hiện đại (1,0x):  0,12 RTC  ████████
```

<!-- Original: Anti-VM Enforcement -->
### Cưỡng chế chống VM

VM bị phát hiện và chỉ nhận **một phần tỷ** phần thưởng bình thường. Chỉ phần cứng thật.

---

<!-- Original: Security -->
## Bảo mật

- **Ràng buộc phần cứng**: Mỗi fingerprint gắn với một ví
- **Chữ ký Ed25519**: Mọi giao dịch chuyển tiền đều được ký bằng mật mã
- **TLS cert pinning**: Miner pin chứng chỉ node
- **Phát hiện container**: Docker, LXC, K8s bị bắt tại attestation
- **ROM clustering**: Phát hiện trại emulator dùng chung ROM dump giống hệt nhau
- **Red team bounties**: [Đang mở](https://github.com/Scottcjn/rustchain-bounties/issues) cho việc tìm lỗ hổng

---

<!-- Original: wRTC on Solana -->
## wRTC trên Solana

| | Liên kết |
|--|----------|
| **Swap** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Chart** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **Bridge** | [Bridge](https://bottube.ai/bridge/wrtc) |
| **Guide** | [wRTC Quickstart](docs/wrtc.md) |

---

<!-- Original: Contribute & Earn RTC -->
## Đóng góp và kiếm RTC

Mọi đóng góp đều kiếm được token RTC. Xem [bounty đang mở](https://github.com/Scottcjn/rustchain-bounties/issues).

| Cấp | Phần thưởng | Ví dụ |
|-----|-------------|-------|
| Micro | 1-10 RTC | Sửa typo, tài liệu, test |
| Standard | 20-50 RTC | Tính năng, refactor |
| Major | 75-100 RTC | Sửa bảo mật, consensus |
| Critical | 100-150 RTC | Lỗ hổng, nâng cấp protocol |

**1 RTC khoảng $0,10 USD** · `pip install clawrtc` · [CONTRIBUTING.md](CONTRIBUTING.md)

---

<!-- Original: Publications -->
## Công bố học thuật

| Bài báo | Nơi công bố | DOI |
|---------|-------------|-----|
| **Emotional Vocabulary as Semantic Grounding** | **CVPR 2026 Workshop (GRAIL-V)** - Accepted | [OpenReview](https://openreview.net/forum?id=pXjE6Tqp70) |
| **One CPU, One Vote** | Preprint | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623592.svg)](https://doi.org/10.5281/zenodo.18623592) |
| **Non-Bijunctive Permutation Collapse** | Preprint | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623920.svg)](https://doi.org/10.5281/zenodo.18623920) |
| **PSE Hardware Entropy** | Preprint | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623922.svg)](https://doi.org/10.5281/zenodo.18623922) |
| **RAM Coffers** | Preprint | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18321905.svg)](https://doi.org/10.5281/zenodo.18321905) |
| **RPI: Resonant Permutation Inference** | Preprint | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19271983.svg)](https://doi.org/10.5281/zenodo.19271983) |

---

<!-- Original: Ecosystem -->
## Hệ sinh thái

| Dự án | Nội dung |
|-------|----------|
| [BoTTube](https://bottube.ai) | Nền tảng video AI-native (1.000+ video) |
| [Beacon](https://github.com/Scottcjn/beacon-skill) | Giao thức khám phá agent |
| [TrashClaw](https://github.com/Scottcjn/trashclaw) | Local LLM agent zero-dep |
| [RAM Coffers](https://github.com/Scottcjn/ram-coffers) | NUMA-aware LLM inference trên POWER8 |
| [RPI Inference](https://github.com/Scottcjn/rpi-inference) | Engine inference zero-multiply (18K tok/s, chạy trên N64) |
| [Grazer](https://github.com/Scottcjn/grazer-skill) | Khám phá nội dung đa nền tảng |

---

<!-- Original: Supported Platforms -->
## Nền tảng hỗ trợ

Linux (x86_64, ppc64le) · macOS (Intel, Apple Silicon, PowerPC) · IBM POWER8 · Windows · Mac OS X Tiger/Leopard · Raspberry Pi

---

<!-- Original: Why "RustChain"? -->
## Vì sao tên là "RustChain"?

Tên này đến từ một laptop 486 với cổng serial bị oxy hóa nhưng vẫn boot được vào DOS và mine RTC. "Rust" nghĩa là sắt oxy hóa trên các linh kiện cổ điển có chứa sắt. Luận đề là phần cứng cổ điển đang rỉ sét vẫn có giá trị tính toán và phẩm giá.

---

<div align="center">

**[Elyan Labs](https://elyanlabs.ai)** · Xây với $0 VC và một căn phòng đầy phần cứng mua ở tiệm cầm đồ

*"Mais, nó vẫn chạy, vậy sao lại vứt đi?"*

[Boudreaux Principles](https://rustchain.org/principles.html) · [Green Tracker](https://rustchain.org/preserved.html) · [Bounties](https://github.com/Scottcjn/rustchain-bounties/issues)

</div>

<!-- Original: Contributing -->
## Đóng góp

Vui lòng đọc [CONTRIBUTING.md](CONTRIBUTING.md) để biết hướng dẫn và [Bounty Board](https://github.com/Scottcjn/rustchain-bounties) để xem các nhiệm vụ và phần thưởng đang hoạt động.

---

*Tài liệu được cải thiện để dễ đọc hơn.*
