<div align="center">

# 🧱 RustChain：古董證明區塊鏈

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PowerPC](https://img.shields.io/badge/PowerPC-G3%2FG4%2FG5-orange)](https://github.com/Scottcjn/Rustchain)
[![Blockchain](https://img.shields.io/badge/Consensus-Proof--of--Antiquity-green)](https://github.com/Scottcjn/Rustchain)
[![Python](https://img.shields.io/badge/Python-3.x-yellow)](https://python.org)
[![Network](https://img.shields.io/badge/Nodes-3%20Active-brightgreen)](https://rustchain.org/explorer)
[![As seen on BoTTube](https://bottube.ai/badge/seen-on-bottube.svg)](https://bottube.ai)

**第一個獎勵老舊硬體的區塊鏈 —— 重視年份，而非速度。**

*你的 PowerPC G4 賺得比最新的 Threadripper 還多。這就是重點。*

[官網](https://rustchain.org) • [區塊瀏覽器](https://rustchain.org/explorer) • [交換 wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [價格圖表](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC 快速入門](docs/wrtc.md) • [wRTC 教學](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia 參考](https://grokipedia.com/search?q=RustChain) • [白皮書](docs/RustChain_Whitepaper_Flameholder_v0.97.pdf) • [快速開始](#-快速開始) • [運作原理](#-古董證明如何運作)

</div>

---

## 🪙 Solana 上的 wRTC

RustChain 代幣 (RTC) 現已透過 BoTTube Bridge 在 Solana 上以 **wRTC** 形式流通：

| 資源 | 連結 |
|------|------|
| **交換 wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **價格圖表** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **RTC ↔ wRTC 跨鏈橋** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **快速入門指南** | [wRTC 快速入門（購買、跨鏈、安全須知）](docs/wrtc.md) |
| **新手教學** | [wRTC 跨鏈 + 交易安全指南](docs/WRTC_ONBOARDING_TUTORIAL.md) |
| **外部參考** | [Grokipedia 搜尋：RustChain](https://grokipedia.com/search?q=RustChain) |
| **代幣鑄造地址** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## 📄 學術出版品

| 論文 | DOI | 主題 |
|------|-----|------|
| **RustChain: One CPU, One Vote** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623592.svg)](https://doi.org/10.5281/zenodo.18623592) | 古董證明共識機制、硬體指紋識別 |
| **Non-Bijunctive Permutation Collapse** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623920.svg)](https://doi.org/10.5281/zenodo.18623920) | AltiVec vec_perm 用於 LLM 注意力機制（27-96 倍優勢）|
| **PSE Hardware Entropy** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623922.svg)](https://doi.org/10.5281/zenodo.18623922) | POWER8 mftb 熵值用於行為分歧 |
| **Neuromorphic Prompt Translation** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623594.svg)](https://doi.org/10.5281/zenodo.18623594) | 情感提示用於 20% 影片擴散增益 |
| **RAM Coffers** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18321905.svg)](https://doi.org/10.5281/zenodo.18321905) | NUMA 分散式權重儲存用於 LLM 推論 |

---

## 🎯 RustChain 的獨特之處

| 傳統 PoW | 古董證明 |
|----------|---------|
| 獎勵最快的硬體 | 獎勵最老的硬體 |
| 越新越好 | 越老越好 |
| 浪費能源 | 保存計算歷史 |
| 競相貶值 | 獎勵數位保存 |

**核心理念**：存活數十年的真正古董硬體值得被認可。RustChain 徹底翻轉挖礦規則。

## ⚡ 快速開始

### 一行安裝（推薦）
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

安裝程式會：
- ✅ 自動偵測你的平台（Linux/macOS，x86_64/ARM/PowerPC）
- ✅ 建立獨立的 Python 虛擬環境（不污染系統）
- ✅ 下載適合你硬體的礦工程式
- ✅ 設定開機自動啟動（systemd/launchd）
- ✅ 提供簡易解除安裝

### 安裝選項

**指定錢包安裝：**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner-wallet
```

**解除安裝：**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

### 支援平台
- ✅ Ubuntu 20.04+、Debian 11+、Fedora 38+（x86_64、ppc64le）
- ✅ macOS 12+（Intel、Apple Silicon、PowerPC）
- ✅ IBM POWER8 系統

### 安裝完成後

**查詢錢包餘額：**
```bash
# 注意：使用 -sk 參數是因為節點可能使用自簽 SSL 憑證
curl -sk "https://rustchain.org/wallet/balance?miner_id=你的錢包名稱"
```

**列出活躍礦工：**
```bash
curl -sk https://rustchain.org/api/miners
```

**檢查節點健康狀態：**
```bash
curl -sk https://rustchain.org/health
```

**取得當前週期：**
```bash
curl -sk https://rustchain.org/epoch
```

**管理礦工服務：**

*Linux (systemd)：*
```bash
systemctl --user status rustchain-miner    # 檢查狀態
systemctl --user stop rustchain-miner      # 停止挖礦
systemctl --user start rustchain-miner     # 開始挖礦
journalctl --user -u rustchain-miner -f    # 查看日誌
```

*macOS (launchd)：*
```bash
launchctl list | grep rustchain            # 檢查狀態
launchctl stop com.rustchain.miner         # 停止挖礦
launchctl start com.rustchain.miner        # 開始挖礦
tail -f ~/.rustchain/miner.log             # 查看日誌
```

### 手動安裝
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
pip install -r requirements.txt
python3 rustchain_universal_miner.py --wallet 你的錢包名稱
```

## 💰 古董倍率

你的硬體年齡決定挖礦獎勵：

| 硬體 | 年代 | 倍率 | 每週期收益範例 |
|------|------|------|---------------|
| **PowerPC G4** | 1999-2005 | **2.5×** | 0.30 RTC/週期 |
| **PowerPC G5** | 2003-2006 | **2.0×** | 0.24 RTC/週期 |
| **PowerPC G3** | 1997-2003 | **1.8×** | 0.21 RTC/週期 |
| **IBM POWER8** | 2014 | **1.5×** | 0.18 RTC/週期 |
| **Pentium 4** | 2000-2008 | **1.5×** | 0.18 RTC/週期 |
| **Core 2 Duo** | 2006-2011 | **1.3×** | 0.16 RTC/週期 |
| **Apple Silicon** | 2020+ | **1.2×** | 0.14 RTC/週期 |
| **現代 x86_64** | 現今 | **1.0×** | 0.12 RTC/週期 |

*倍率隨時間遞減（每年 15%）以防止永久優勢。*

## 🔧 古董證明如何運作

### 1. 硬體指紋識別 (RIP-PoA)

每個礦工必須證明其硬體是真實的，而非模擬的：

```
┌─────────────────────────────────────────────────────────────┐
│                      6 項硬體檢查                            │
├─────────────────────────────────────────────────────────────┤
│ 1. 時脈偏移與振盪器漂移       ← 矽晶片老化模式              │
│ 2. 快取時序指紋               ← L1/L2/L3 延遲特徵           │
│ 3. SIMD 單元識別              ← AltiVec/SSE/NEON 偏差       │
│ 4. 熱漂移熵值                 ← 獨特的熱曲線                │
│ 5. 指令路徑抖動               ← 微架構抖動圖                │
│ 6. 反模擬器檢查               ← 偵測虛擬機/模擬器           │
└─────────────────────────────────────────────────────────────┘
```

**為何重要**：假裝成 G4 Mac 的 SheepShaver 虛擬機無法通過這些檢查。真正的古董矽晶片有獨特的老化模式，無法偽造。

### 2. 一 CPU 一票 (RIP-200)

不同於 PoW 以算力決定投票權，RustChain 使用**輪流共識**：

- 每個獨特硬體裝置每週期只有 1 票
- 獎勵在所有投票者間平均分配，再乘以古董倍率
- 執行多執行緒或更快 CPU 沒有任何優勢

### 3. 週期制獎勵

```
週期時長：10 分鐘（600 秒）
基礎獎勵池：每週期 1.5 RTC
分配方式：平均分配 × 古董倍率
```

**5 個礦工的範例：**
```
G4 Mac (2.5×):     0.30 RTC  ████████████████████
G5 Mac (2.0×):     0.24 RTC  ████████████████
現代 PC (1.0×):    0.12 RTC  ████████
現代 PC (1.0×):    0.12 RTC  ████████
現代 PC (1.0×):    0.12 RTC  ████████
                   ─────────
總計：             0.90 RTC（+ 0.60 RTC 返還獎勵池）
```

## 🌐 網路架構

### 活躍節點（3 個）

| 節點 | 位置 | 角色 | 狀態 |
|------|------|------|------|
| **節點 1** | 50.28.86.131 | 主節點 + 瀏覽器 | ✅ 運行中 |
| **節點 2** | 50.28.86.153 | Ergo 錨定 | ✅ 運行中 |
| **節點 3** | 76.8.228.245 | 外部（社群）| ✅ 運行中 |

### Ergo 區塊鏈錨定

RustChain 定期錨定到 Ergo 區塊鏈以確保不可篡改性：

```
RustChain 週期 → 承諾雜湊 → Ergo 交易（R4 暫存器）
```

這提供了 RustChain 狀態在特定時間存在的密碼學證明。

## 📊 API 端點

```bash
# 檢查網路健康狀態
curl -sk https://rustchain.org/health

# 取得當前週期
curl -sk https://rustchain.org/epoch

# 列出活躍礦工
curl -sk https://rustchain.org/api/miners

# 查詢錢包餘額
curl -sk "https://rustchain.org/wallet/balance?miner_id=你的錢包"

# 區塊瀏覽器（網頁）
open https://rustchain.org/explorer
```

## 🖥️ 支援平台

| 平台 | 架構 | 狀態 | 備註 |
|------|------|------|------|
| **Mac OS X Tiger** | PowerPC G4/G5 | ✅ 完整支援 | Python 2.5 相容礦工 |
| **Mac OS X Leopard** | PowerPC G4/G5 | ✅ 完整支援 | 古董 Mac 推薦使用 |
| **Ubuntu Linux** | ppc64le/POWER8 | ✅ 完整支援 | 最佳效能 |
| **Ubuntu Linux** | x86_64 | ✅ 完整支援 | 標準礦工 |
| **macOS Sonoma** | Apple Silicon | ✅ 完整支援 | M1/M2/M3 晶片 |
| **Windows 10/11** | x86_64 | ✅ 完整支援 | Python 3.8+ |
| **DOS** | 8086/286/386 | 🔧 實驗性 | 僅徽章獎勵 |

## 🏅 NFT 徽章系統

達成挖礦里程碑可獲得紀念徽章：

| 徽章 | 要求 | 稀有度 |
|------|------|--------|
| 🔥 **Bondi G3 火炬守護者** | 在 PowerPC G3 上挖礦 | 稀有 |
| ⚡ **QuickBasic 聆聽者** | 在 DOS 機器上挖礦 | 傳奇 |
| 🛠️ **DOS WiFi 煉金術士** | 網路連接 DOS 機器 | 神話 |
| 🏛️ **先驅殿堂** | 前 100 名礦工 | 限量 |

## 🔒 安全模型

### 反虛擬機偵測
虛擬機會被偵測並只獲得**十億分之一**的正常獎勵：
```
真正的 G4 Mac：    2.5× 倍率  = 0.30 RTC/週期
模擬的 G4：        0.0000000025×    = 0.0000000003 RTC/週期
```

### 硬體綁定
每個硬體指紋綁定一個錢包。防止：
- 同一硬體使用多個錢包
- 硬體偽造
- 女巫攻擊

## 📁 專案結構

```
Rustchain/
├── rustchain_universal_miner.py    # 主礦工程式（所有平台）
├── rustchain_v2_integrated.py      # 完整節點實作
├── fingerprint_checks.py           # 硬體驗證
├── install.sh                      # 一行安裝程式
├── docs/
│   ├── RustChain_Whitepaper_*.pdf  # 技術白皮書
│   └── chain_architecture.md       # 架構文件
├── tools/
│   └── validator_core.py           # 區塊驗證
└── nfts/                           # 徽章定義
```

## 🔗 相關專案與連結

| 資源 | 連結 |
|------|------|
| **官方網站** | [rustchain.org](https://rustchain.org) |
| **區塊瀏覽器** | [rustchain.org/explorer](https://rustchain.org/explorer) |
| **交換 wRTC (Raydium)** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **價格圖表** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **RTC ↔ wRTC 跨鏈橋** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **wRTC 代幣鑄造地址** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |
| **BoTTube** | [bottube.ai](https://bottube.ai) - AI 影片平台 |
| **Moltbook** | [moltbook.com](https://moltbook.com) - AI 社群網路 |
| [nvidia-power8-patches](https://github.com/Scottcjn/nvidia-power8-patches) | POWER8 的 NVIDIA 驅動程式 |
| [llama-cpp-power8](https://github.com/Scottcjn/llama-cpp-power8) | POWER8 上的 LLM 推論 |
| [ppc-compilers](https://github.com/Scottcjn/ppc-compilers) | 古董 Mac 的現代編譯器 |

## 📝 相關文章

- [古董證明：獎勵古董硬體的區塊鏈](https://dev.to/scottcjn/proof-of-antiquity-a-blockchain-that-rewards-vintage-hardware-4ii3) - Dev.to
- [我在 768GB IBM POWER8 伺服器上執行 LLM](https://dev.to/scottcjn/i-run-llms-on-a-768gb-ibm-power8-server-and-its-faster-than-you-think-1o) - Dev.to

## 🙏 致謝

**這是一年的開發心血、真正的古董硬體、電費帳單，以及一個專屬實驗室的結晶。**

如果你使用 RustChain：
- ⭐ **給這個 repo 星星** - 幫助更多人發現它
- 📝 **在你的專案中註明出處** - 保留原作者資訊
- 🔗 **附上連結** - 分享這份愛

```
RustChain - 古董證明 by Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain
```

## 📜 授權條款

MIT 授權條款 - 可自由使用，但請保留版權聲明與出處。

---

<div align="center">

**由 [Elyan Labs](https://elyanlabs.ai) 用 ⚡ 製作**

*「你的古董硬體能賺取獎勵。讓挖礦再次有意義。」*

**DOS 主機、PowerPC G4、Win95 電腦 —— 它們都有價值。RustChain 證明了這一點。**

</div>
