<div align="center">

# 🧱 RustChain: 古董证明区块链

[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PowerPC](https://img.shields.io/badge/PowerPC-G3%2FG4%2FG5-orange)](https://github.com/Scottcjn/Rustchain)
[![Blockchain](https://img.shields.io/badge/Consensus-Proof--of--Antiquity-green)](https://github.com/Scottcjn/Rustchain)
[![Python](https://img.shields.io/badge/Python-3.x-yellow)](https://python.org)
[![Network](https://img.shields.io/badge/Nodes-3%20Active-brightgreen)](https://rustchain.org/explorer)
[![As seen on BoTTube](https://bottube.ai/badge/seen-on-bottube.svg)](https://bottube.ai)

**第一个奖励古董硬件"年龄"而非"速度"的区块链。**

*您的 PowerPC G4 比现代 Threadripper 赚得更多。这就是重点。*

[官网](https://rustchain.org) • [实时浏览器](https://rustchain.org/explorer) • [交易 wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC 快速入门](docs/wrtc.md) • [wRTC 教程](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia 参考](https://grokipedia.com/search?q=RustChain) • [白皮书](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [快速开始](#-快速开始) • [工作原理](#-古董证明如何工作)

</div>

---

## 🪙 Solana 上的 wRTC

RustChain 代币（RTC）现已通过 BoTTube 桥在 Solana 上以 **wRTC** 形式提供：

| 资源 | 链接 |
|----------|------|
| **交易 wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **价格图表** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **RTC ↔ wRTC 桥接** | [BoTTube 桥](https://bottube.ai/bridge) |
| **快速入门指南** | [wRTC 快速入门（购买、桥接、安全）](docs/wrtc.md) |
| **新手教程** | [wRTC 桥接 + 交易安全指南](docs/WRTC_ONBOARDING_TUTORIAL.md) |
| **外部参考** | [Grokipedia 搜索：RustChain](https://grokipedia.com/search?q=RustChain) |
| **代币铸造地址** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## 📄 学术出版物

| 论文 | DOI | 主题 |
|-------|-----|-------|
| **RustChain: 一个 CPU，一票** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623592.svg)](https://doi.org/10.5281/zenodo.18623592) | 古董证明共识、硬件指纹 |
| **非双射排列折叠** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623920.svg)](https://doi.org/10.5281/zenodo.18623920) | AltiVec vec_perm 用于 LLM 注意力机制（27-96倍优势） |
| **PSE 硬件熵** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623922.svg)](https://doi.org/10.5281/zenodo.18623922) | POWER8 mftb 熵用于行为分歧 |
| **神经形态提示翻译** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623594.svg)](https://doi.org/10.5281/zenodo.18623594) | 情感提示在视频扩散中提升 20% |
| **RAM 保险库** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18321905.svg)](https://doi.org/10.5281/zenodo.18321905) | NUMA 分布式权重库用于 LLM 推理 |

---

## 🎯 RustChain 的与众不同之处

| 传统 PoW | 古董证明 |
|----------------|-------------------|
| 奖励最快的硬件 | 奖励最古老的硬件 |
| 越新越好 | 越旧越好 |
| 浪费能源消耗 | 保护计算历史 |
| 竞速到底 | 奖励数字保护 |

**核心原则**：存活数十年的真实古董硬件值得被认可。RustChain 颠覆了挖矿规则。

## ⚡ 快速开始

### 一键安装（推荐）
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

安装程序功能：
- ✅ 自动检测您的平台（Linux/macOS, x86_64/ARM/PowerPC）
- ✅ 创建隔离的 Python virtualenv（不污染系统）
- ✅ 下载适合您硬件的正确矿工
- ✅ 设置开机自启动（systemd/launchd）
- ✅ 提供简便卸载

### 带选项的安装

**使用指定钱包安装：**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner-wallet
```

**卸载：**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

### 支持的平台
- ✅ Ubuntu 20.04+, Debian 11+, Fedora 38+ (x86_64, ppc64le)
- ✅ macOS 12+ (Intel, Apple Silicon, PowerPC)
- ✅ IBM POWER8 系统

### 安装后操作

**检查钱包余额：**
```bash
# 注意：使用 -sk 标志，因为节点可能使用自签名 SSL 证书
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**列出活跃矿工：**
```bash
curl -sk https://50.28.86.131/api/miners
```

**检查节点健康：**
```bash
curl -sk https://50.28.86.131/health
```

**获取当前纪元：**
```bash
curl -sk https://50.28.86.131/epoch
```

**管理矿工服务：**

*Linux (systemd):*
```bash
systemctl --user status rustchain-miner    # 检查状态
systemctl --user stop rustchain-miner      # 停止挖矿
systemctl --user start rustchain-miner     # 启动挖矿
journalctl --user -u rustchain-miner -f    # 查看日志
```

*macOS (launchd):*
```bash
launchctl list | grep rustchain            # 检查状态
launchctl stop com.rustchain.miner         # 停止挖矿
launchctl start com.rustchain.miner        # 启动挖矿
tail -f ~/.rustchain/miner.log             # 查看日志
```

### 手动安装
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
pip install -r requirements.txt
python3 rustchain_universal_miner.py --wallet YOUR_WALLET_NAME
```

## 💰 赏金榜

通过为 RustChain 生态系统做贡献来赚取 **RTC**！

| 赏金 | 奖励 | 链接 |
|--------|--------|------|
| **首次真实贡献** | 10 RTC | [#48](https://github.com/Scottcjn/Rustchain/issues/48) |
| **网络状态页** | 25 RTC | [#161](https://github.com/Scottcjn/Rustchain/issues/161) |
| **AI 代理猎手** | 200 RTC | [代理赏金 #34](https://github.com/Scottcjn/rustchain-bounties/issues/34) |

---

## 💰 古董倍数

您的硬件年龄决定挖矿奖励：

| 硬件 | 年代 | 倍数 | 示例收益 |
|----------|-----|------------|------------------|
| **PowerPC G4** | 1999-2005 | **2.5×** | 0.30 RTC/纪元 |
| **PowerPC G5** | 2003-2006 | **2.0×** | 0.24 RTC/纪元 |
| **PowerPC G3** | 1997-2003 | **1.8×** | 0.21 RTC/纪元 |
| **IBM POWER8** | 2014 | **1.5×** | 0.18 RTC/纪元 |
| **Pentium 4** | 2000-2008 | **1.5×** | 0.18 RTC/纪元 |
| **Core 2 Duo** | 2006-2011 | **1.3×** | 0.16 RTC/纪元 |
| **Apple Silicon** | 2020+ | **1.2×** | 0.14 RTC/纪元 |
| **现代 x86_64** | 当前 | **1.0×** | 0.12 RTC/纪元 |

*倍数每年衰减 15%，以防止永久优势。*

## 🔧 古董证明如何工作

### 1. 硬件指纹（RIP-PoA）

每个矿工必须证明其硬件是真实的，而非模拟的：

```
┌─────────────────────────────────────────────────────────────┐
│                   6 项硬件检查                              │
├─────────────────────────────────────────────────────────────┤
│ 1. 时钟偏移 & 振荡器漂移   ← 硅片老化模式                   │
│ 2. 缓存时序指纹            ← L1/L2/L3 延迟特征               │
│ 3. SIMD 单元特征           ← AltiVec/SSE/NEON 偏差          │
│ 4. 热漂移熵                ← 热量曲线是独特的                │
│ 5. 指令路径抖动            ← 微架构抖动图                   │
│ 6. 反模拟检查              ← 检测虚拟机/模拟器              │
└─────────────────────────────────────────────────────────────┘
```

**为什么重要**：伪装成 G4 Mac 的 SheepShaver 虚拟机会未通过这些检查。真实的古董硅片具有无法伪造的独特老化模式。

### 2. 1 个 CPU = 1 票（RIP-200）

与算力即投票权的 PoW 不同，RustChain 使用**轮流共识**：

- 每个独特的硬件设备每纪元只有 1 票
- 奖励在所有投票者间平均分配，然后乘以古董倍数
- 运行多线程或更快的 CPU 没有优势

### 3. 基于纪元的奖励

```
纪元时长：10 分钟（600 秒）
基础奖励池：每纪元 1.5 RTC
分配方式：平均分配 × 古董倍数
```

**5 个矿工的示例：**
```
G4 Mac (2.5×):     0.30 RTC  ████████████████████
G5 Mac (2.0×):     0.24 RTC  ████████████████
现代 PC (1.0×):    0.12 RTC  ████████
现代 PC (1.0×):    0.12 RTC  ████████
现代 PC (1.0×):    0.12 RTC  ████████
                   ─────────
总计:              0.90 RTC (+ 0.60 RTC 返回池)
```

## 🌐 网络架构

### 活跃节点（3 个）

| 节点 | 位置 | 角色 | 状态 |
|------|----------|------|--------|
| **节点 1** | 50.28.86.131 | 主节点 + 浏览器 | ✅ 活跃 |
| **节点 2** | 50.28.86.153 | Ergo 锚定 | ✅ 活跃 |
| **节点 3** | 76.8.228.245 | 外部（社区） | ✅ 活跃 |

### Ergo 区块链锚定

RustChain 定期锚定到 Ergo 区块链以实现不可篡改性：

```
RustChain 纪元 → 承诺哈希 → Ergo 交易（R4 寄存器）
```

这提供了 RustChain 状态在特定时间存在的密码学证明。

## 📊 API 端点

```bash
# 检查网络健康
curl -sk https://50.28.86.131/health

# 获取当前纪元
curl -sk https://50.28.86.131/epoch

# 列出活跃矿工
curl -sk https://50.28.86.131/api/miners

# 检查钱包余额
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET"

# 区块浏览器（网页浏览器）
open https://rustchain.org/explorer
```

## 🖥️ 支持的平台

| 平台 | 架构 | 状态 | 备注 |
|----------|--------------|--------|-------|
| **Mac OS X Tiger** | PowerPC G4/G5 | ✅ 完全支持 | Python 2.5 兼容矿工 |
| **Mac OS X Leopard** | PowerPC G4/G5 | ✅ 完全支持 | 推荐用于古董 Mac |
| **Ubuntu Linux** | ppc64le/POWER8 | ✅ 完全支持 | 最佳性能 |
| **Ubuntu Linux** | x86_64 | ✅ 完全支持 | 标准矿工 |
| **macOS Sonoma** | Apple Silicon | ✅ 完全支持 | M1/M2/M3 芯片 |
| **Windows 10/11** | x86_64 | ✅ 完全支持 | Python 3.8+ |
| **DOS** | 8086/286/386 | 🔧 实验性 | 仅徽章奖励 |

## 🏅 NFT 徽章系统

达成挖矿里程碑即可获得纪念徽章：

| 徽章 | 要求 | 稀有度 |
|-------|-------------|--------|
| 🔥 **Bondi G3 火焰守护者** | 在 PowerPC G3 上挖矿 | 稀有 |
| ⚡ **QuickBasic 倾听者** | 从 DOS 机器挖矿 | 传奇 |
| 🛠️ **DOS WiFi 炼金术师** | 网络化 DOS 机器 | 神话 |
| 🏛️ **万神殿先驱** | 前 100 名矿工 | 限量 |

## 🔒 安全模型

### 反虚拟机检测
虚拟机会被检测到并获得普通奖励的 **十亿分之一**：
```
真实 G4 Mac:    2.5× 倍数  = 0.30 RTC/纪元
模拟 G4:        0.0000000025×    = 0.0000000003 RTC/纪元
```

### 硬件绑定
每个硬件指纹绑定到一个钱包。防止：
- 同一硬件使用多个钱包
- 硬件欺骗
- 女巫攻击

## 📁 仓库结构

```
Rustchain/
├── rustchain_universal_miner.py    # 主矿工（所有平台）
├── rustchain_v2_integrated.py      # 完整节点实现
├── fingerprint_checks.py           # 硬件验证
├── install.sh                      # 一键安装程序
├── docs/
│   ├── RustChain_Whitepaper_*.pdf  # 技术白皮书
│   └── chain_architecture.md       # 架构文档
├── tools/
│   └── validator_core.py           # 区块验证
└── nfts/                           # 徽章定义
```

## ✅ Beacon 认证开源（BCOS）

RustChain 接受 AI 辅助的 PR，但我们要求*证据*和*审查*，这样维护者就不会淹没在低质量的代码生成中。

阅读草案规范：
- `docs/BEACON_CERTIFIED_OPEN_SOURCE.md`

## 🔗 相关项目和链接

| 资源 | 链接 |
|---------|------|
| **官网** | [rustchain.org](https://rustchain.org) |
| **区块浏览器** | [rustchain.org/explorer](https://rustchain.org/explorer) |
| **交易 wRTC (Raydium)** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **价格图表** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **RTC ↔ wRTC 桥接** | [BoTTube 桥](https://bottube.ai/bridge) |
| **wRTC 代币铸造地址** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |
| **BoTTube** | [bottube.ai](https://bottube.ai) - AI 视频平台 |
| **Moltbook** | [moltbook.com](https://moltbook.com) - AI 社交网络 |
| [nvidia-power8-patches](https://github.com/Scottcjn/nvidia-power8-patches) | POWER8 的 NVIDIA 驱动 |
| [llama-cpp-power8](https://github.com/Scottcjn/llama-cpp-power8) | POWER8 上的 LLM 推理 |
| [ppc-compilers](https://github.com/Scottcjn/ppc-compilers) | 古董 Mac 的现代编译器 |

## 📝 文章

- [古董证明：奖励古董硬件的区块链](https://dev.to/scottcjn/proof-of-antiquity-a-blockchain-that-rewards-vintage-hardware-4ii3) - Dev.to
- [我在 768GB IBM POWER8 服务器上运行 LLM](https://dev.to/scottcjn/i-run-llms-on-a-768gb-ibm-power8-server-and-its-faster-than-you-think-1o) - Dev.to

## 🙏 署名

**一年的开发、真实的古董硬件、电费账单和专用实验室成就了这一切。**

如果您使用 RustChain：
- ⭐ **给这个仓库加星** - 帮助其他人找到它
- 📝 **在您的项目中署名** - 保留署名信息
- 🔗 **链接回来** - 分享这份热爱

```
RustChain - 古董证明 by Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain
```

## 📜 许可证

MIT 许可证 - 免费使用，但请保留版权声明和署名。

---

<div align="center">

**由 [Elyan Labs](https://elyanlabs.ai) 用 ⚡ 打造**

*"您的古董硬件获得奖励。让挖矿再次有意义。"*

**DOS 机器、PowerPC G4、Win95 机器——它们都有价值。RustChain 证明了这一点。**

</div>
