<div align="center">

# 🧱 RustChain: 古董证明区块链 (Proof-of-Antiquity Blockchain)

[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/Scottcjn/Rustchain?style=flat&color=gold)](https://github.com/Scottcjn/Rustchain/stargazers)
[![Contributors](https://img.shields.io/github/contributors/Scottcjn/Rustchain?color=brightgreen)](https://github.com/Scottcjn/Rustchain/graphs/contributors)
[![Last Commit](https://img.shields.io/github/last-commit/Scottcjn/Rustchain?color=blue)](https://github.com/Scottcjn/Rustchain/commits/main)
[![Open Issues](https://img.shields.io/github/issues/Scottcjn/Rustchain?color=orange)](https://github.com/Scottcjn/Rustchain/issues)
[![PowerPC](https://img.shields.io/badge/PowerPC-G3%2FG4%2FG5-orange)](https://github.com/Scottcjn/Rustchain)
[![Blockchain](https://img.shields.io/badge/Consensus-Proof--of--Antiquity-green)](https://github.com/Scottcjn/Rustchain)
[![Python](https://img.shields.io/badge/Python-3.x-yellow)](https://python.org)
[![Network](https://img.shields.io/badge/Nodes-3%20Active-brightgreen)](https://rustchain.org/explorer)
[![Bounties](https://img.shields.io/badge/Bounties-Open%20%F0%9F%92%B0-green)](https://github.com/Scottcjn/rustchain-bounties/issues)
[![As seen on BoTTube](https://bottube.ai/badge/seen-on-bottube.svg)](https://bottube.ai)
[![Discussions](https://img.shields.io/github/discussions/Scottcjn/Rustchain?color=purple)](https://github.com/Scottcjn/Rustchain/discussions)

**第一个奖励老旧硬件的区块链，不是因为它快，而是因为它老。**

*你的 PowerPC G4 比现代 Threadripper 赚得更多。这就是重点。*

[官网](https://rustchain.org) • [实时浏览器](https://rustchain.org/explorer) • [兑换 wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC 快速入门](docs/wrtc.md) • [wRTC 教程](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia 参考](https://grokipedia.com/search?q=RustChain) • [白皮书](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [快速开始](#-快速开始) • [工作原理](#-古董证明-proof-of-antiquity-工作原理)

</div>

---

## 🪙 Solana 上的 wRTC

RustChain 代币 (RTC) 现已通过 BoTTube 桥在 Solana 上以 **wRTC** 形式提供：

| 资源 | 链接 |
|----------|------|
| **兑换 wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **价格图表** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **桥接 RTC ↔ wRTC** | [BoTTube 桥](https://bottube.ai/bridge) |
| **快速入门指南** | [wRTC 快速入门（购买、桥接、安全）](docs/wrtc.md) |
| **入门教程** | [wRTC 桥接 + 兑换安全指南](docs/WRTC_ONBOARDING_TUTORIAL.md) |
| **外部参考** | [Grokipedia 搜索：RustChain](https://grokipedia.com/search?q=RustChain) |
| **代币铸造地址** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## 贡献并赚取 RTC

每一个贡献都能赚取 RTC 代币。Bug 修复、功能开发、文档编写、安全审计——全部有偿。

| 等级 | 奖励 | 示例 |
|------|--------|----------|
| 微型 | 1-10 RTC | 错别字修复、小型文档、简单测试 |
| 标准 | 20-50 RTC | 功能开发、重构、新端点 |
| 重大 | 75-100 RTC | 安全修复、共识改进 |
| 关键 | 100-150 RTC | 漏洞补丁、协议升级 |

**开始贡献：**
1. 浏览[开放悬赏](https://github.com/Scottcjn/rustchain-bounties/issues)
2. 选择一个[新手友好问题](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue)（5-10 RTC）
3. Fork、修复、提交 PR——获得 RTC 奖励
4. 查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解完整细节

**1 RTC = $0.10 USD** | `pip install clawrtc` 开始挖矿

---

## Agent 钱包 + x402 支付

RustChain agents 现在可以拥有 **Coinbase Base 钱包**，并使用 **x402 协议**（HTTP 402 Payment Required）进行机器对机器支付：

| 资源 | 链接 |
|----------|------|
| **Agent 钱包文档** | [rustchain.org/wallets.html](https://rustchain.org/wallets.html) |
| **Base 上的 wRTC** | [`0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`](https://basescan.org/address/0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **USDC 兑换 wRTC** | [Aerodrome DEX](https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **Base 桥** | [bottube.ai/bridge/base](https://bottube.ai/bridge/base) |

```bash
# 创建 Coinbase 钱包
pip install clawrtc[coinbase]
clawrtc wallet coinbase create

# 查看兑换信息
clawrtc wallet coinbase swap-info

# 链接现有 Base 地址
clawrtc wallet coinbase link 0xYourBaseAddress
```

**x402 高级 API 端点**已上线（目前免费，用于验证流程）：
- `GET /api/premium/videos` - 批量视频导出（BoTTube）
- `GET /api/premium/analytics/<agent>` - 深度 agent 分析（BoTTube）
- `GET /api/premium/reputation` - 完整声誉导出（Beacon Atlas）
- `GET /wallet/swap-info` - USDC/wRTC 兑换指导（RustChain）

## 📄 学术出版物

| 论文 | DOI | 主题 |
|-------|-----|-------|
| **RustChain: 一个 CPU，一票** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623592.svg)](https://doi.org/10.5281/zenodo.18623592) | 古董证明共识、硬件指纹识别 |
| **非双射置换坍缩** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623920.svg)](https://doi.org/10.5281/zenodo.18623920) | AltiVec vec_perm 用于 LLM 注意力机制（27-96 倍优势）|
| **PSE 硬件熵** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623922.svg)](https://doi.org/10.5281/zenodo.18623922) | POWER8 mftb 熵用于行为差异 |
| **神经形态提示翻译** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623594.svg)](https://doi.org/10.5281/zenodo.18623594) | 情感提示使视频扩散提升 20% |
| **RAM Coffers** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18321905.svg)](https://doi.org/10.5281/zenodo.18321905) | NUMA 分布式权重存储用于 LLM 推理 |

---

## 🎯 RustChain 的独特之处

| 传统 PoW | 古董证明 (Proof-of-Antiquity) |
|----------------|-------------------|
| 奖励最快的硬件 | 奖励最老的硬件 |
| 越新越好 | 越老越好 |
| 浪费能源消耗 | 保护计算历史 |
| 竞相逐底 | 奖励数字保护 |

**核心原则**：经历数十年仍然存活的真实老旧硬件值得认可。RustChain 颠覆了挖矿逻辑。

## ⚡ 快速开始

### 一键安装（推荐）
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

安装程序会：
- ✅ 自动检测你的平台（Linux/macOS，x86_64/ARM/PowerPC）
- ✅ 创建隔离的 Python 虚拟环境（不污染系统）
- ✅ 下载适合你硬件的正确矿工程序
- ✅ 设置开机自启动（systemd/launchd）
- ✅ 提供简单的卸载方式

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
- ✅ Ubuntu 20.04+、Debian 11+、Fedora 38+（x86_64、ppc64le）
- ✅ macOS 12+（Intel、Apple Silicon、PowerPC）
- ✅ IBM POWER8 系统

### 故障排除

- **安装程序因权限错误失败**：使用对 `~/.local` 有写入权限的账户重新运行，避免在系统 Python 的全局 site-packages 内运行。
- **Python 版本错误**（`SyntaxError` / `ModuleNotFoundError`）：使用 Python 3.10+ 安装，并将 `python3` 设置为该解释器。
  ```bash
  python3 --version
  curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
  ```
- **`curl` 中的 HTTPS 证书错误**：这可能发生在非浏览器客户端环境中；在检查钱包之前，先用 `curl -I https://rustchain.org` 检查连接性。
- **矿工立即退出**：验证钱包是否存在，服务是否正在运行（`systemctl --user status rustchain-miner` 或 `launchctl list | grep rustchain`）

如果问题持续存在，请在新 issue 或悬赏评论中包含日志和操作系统详细信息，以及确切的错误输出和你的 `install-miner.sh --dry-run` 结果。

### 安装后

**检查你的钱包余额：**
```bash
# 注意：使用 -sk 标志，因为节点可能使用自签名 SSL 证书
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**列出活跃矿工：**
```bash
curl -sk https://50.28.86.131/api/miners
```

**检查节点健康状态：**
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
systemctl --user start rustchain-miner     # 开始挖矿
journalctl --user -u rustchain-miner -f    # 查看日志
```

*macOS (launchd):*
```bash
launchctl list | grep rustchain            # 检查状态
launchctl stop com.rustchain.miner         # 停止挖矿
launchctl start com.rustchain.miner        # 开始挖矿
tail -f ~/.rustchain/miner.log             # 查看日志
```

### 手动安装
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
bash install-miner.sh --wallet YOUR_WALLET_NAME
# 可选：预览操作而不更改系统
bash install-miner.sh --dry-run --wallet YOUR_WALLET_NAME
```

## 💰 悬赏榜

通过为 RustChain 生态系统做贡献来赚取 **RTC**！

| 悬赏 | 奖励 | 链接 |
|--------|--------|------|
| **首次真实贡献** | 10 RTC | [#48](https://github.com/Scottcjn/Rustchain/issues/48) |
| **网络状态页面** | 25 RTC | [#161](https://github.com/Scottcjn/Rustchain/issues/161) |
| **AI Agent 猎人** | 200 RTC | [Agent 悬赏 #34](https://github.com/Scottcjn/rustchain-bounties/issues/34) |

---

## 💰 古董倍数

你的硬件年龄决定了你的挖矿奖励：

| 硬件 | 时代 | 倍数 | 示例收益 |
|----------|-----|------------|------------------|
| **PowerPC G4** | 1999-2005 | **2.5×** | 0.30 RTC/纪元 |
| **PowerPC G5** | 2003-2006 | **2.0×** | 0.24 RTC/纪元 |
| **PowerPC G3** | 1997-2003 | **1.8×** | 0.21 RTC/纪元 |
| **IBM POWER8** | 2014 | **1.5×** | 0.18 RTC/纪元 |
| **Pentium 4** | 2000-2008 | **1.5×** | 0.18 RTC/纪元 |
| **Core 2 Duo** | 2006-2011 | **1.3×** | 0.16 RTC/纪元 |
| **Apple Silicon** | 2020+ | **1.2×** | 0.14 RTC/纪元 |
| **现代 x86_64** | 当前 | **1.0×** | 0.12 RTC/纪元 |

*倍数随时间衰减（每年 15%）以防止永久优势。*

## 🔧 古董证明 (Proof-of-Antiquity) 工作原理

### 1. 硬件指纹识别 (RIP-PoA)

每个矿工必须证明他们的硬件是真实的，而不是模拟的：

```
┌─────────────────────────────────────────────────────────────┐
│                   6 项硬件检查                               │
├─────────────────────────────────────────────────────────────┤
│ 1. 时钟偏移 & 振荡器漂移        ← 硅老化模式                │
│ 2. 缓存时序指纹                ← L1/L2/L3 延迟特征          │
│ 3. SIMD 单元身份               ← AltiVec/SSE/NEON 偏差      │
│ 4. 热漂移熵                    ← 热曲线是唯一的             │
│ 5. 指令路径抖动                ← 微架构抖动图               │
│ 6. 反模拟检查                  ← 检测虚拟机/模拟器          │
└─────────────────────────────────────────────────────────────┘
```

**为什么重要**：假装是 G4 Mac 的 SheepShaver 虚拟机将无法通过这些检查。真实的老旧硅片具有无法伪造的独特老化模式。

### 2. 1 个 CPU = 1 票 (RIP-200)

与 PoW 中算力 = 投票权不同，RustChain 使用**轮询共识**：

- 每个唯一的硬件设备每个纪元获得恰好 1 票
- 奖励在所有投票者之间平均分配，然后乘以古董倍数
- 运行多个线程或更快的 CPU 没有优势

### 3. 基于纪元的奖励

```
纪元持续时间：10 分钟（600 秒）
基础奖励池：每个纪元 1.5 RTC
分配：平均分配 × 古董倍数
```

**5 个矿工的示例：**
```
G4 Mac (2.5×):     0.30 RTC  ████████████████████
G5 Mac (2.0×):     0.24 RTC  ████████████████
现代 PC (1.0×):    0.12 RTC  ████████
现代 PC (1.0×):    0.12 RTC  ████████
现代 PC (1.0×):    0.12 RTC  ████████
                   ─────────
总计：             0.90 RTC（+ 0.60 RTC 返回池中）
```

## 🌐 网络架构

### 实时节点（3 个活跃）

| 节点 | 位置 | 角色 | 状态 |
|------|----------|------|--------|
| **节点 1** | 50.28.86.131 | 主节点 + 浏览器 | ✅ 活跃 |
| **节点 2** | 50.28.86.153 | Ergo 锚定 | ✅ 活跃 |
| **节点 3** | 76.8.228.245 | 外部（社区）| ✅ 活跃 |

### Ergo 区块链锚定

RustChain 定期锚定到 Ergo 区块链以实现不可变性：

```
RustChain 纪元 → 承诺哈希 → Ergo 交易（R4 寄存器）
```

这提供了 RustChain 状态在特定时间存在的加密证明。

## 📊 API 端点

```bash
# 检查网络健康状态
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
| **Mac OS X Leopard** | PowerPC G4/G5 | ✅ 完全支持 | 推荐用于老旧 Mac |
| **Ubuntu Linux** | ppc64le/POWER8 | ✅ 完全支持 | 最佳性能 |
| **Ubuntu Linux** | x86_64 | ✅ 完全支持 | 标准矿工 |
| **macOS Sonoma** | Apple Silicon | ✅ 完全支持 | M1/M2/M3 芯片 |
| **Windows 10/11** | x86_64 | ✅ 完全支持 | Python 3.8+ |
| **DOS** | 8086/286/386 | 🔧 实验性 | 仅徽章奖励 |

## 🏅 NFT 徽章系统

通过挖矿里程碑赚取纪念徽章：

| 徽章 | 要求 | 稀有度 |
|-------|-------------|--------|
| 🔥 **Bondi G3 火焰守护者** | 在 PowerPC G3 上挖矿 | 稀有 |
| ⚡ **QuickBasic 倾听者** | 从 DOS 机器挖矿 | 传奇 |
| 🛠️ **DOS WiFi 炼金术士** | 联网 DOS 机器 | 神话 |
| 🏛️ **万神殿先驱** | 前 100 名矿工 | 限量 |

## 🔒 安全模型

### 反虚拟机检测
虚拟机被检测到后将获得正常奖励的 **十亿分之一**：
```
真实 G4 Mac:    2.5× 倍数  = 0.30 RTC/纪元
模拟 G4:        0.0000000025×    = 0.0000000003 RTC/纪元
```

### 硬件绑定
每个硬件指纹绑定到一个钱包。防止：
- 同一硬件上的多个钱包
- 硬件欺骗
- 女巫攻击

## 📁 仓库结构

```
Rustchain/
├── install-miner.sh                # 通用矿工安装程序（Linux/macOS）
├── node/
│   ├── rustchain_v2_integrated_v2.2.1_rip200.py  # 完整节点实现
│   └── fingerprint_checks.py       # 硬件验证
├── miners/
│   ├── linux/rustchain_linux_miner.py            # Linux 矿工
│   └── macos/rustchain_mac_miner_v2.4.py         # macOS 矿工
├── docs/
│   ├── RustChain_Whitepaper_*.pdf  # 技术白皮书
│   └── chain_architecture.md       # 架构文档
├── tools/
│   └── validator_core.py           # 区块验证
└── nfts/                           # 徽章定义
```

## ✅ Beacon 认证开源 (BCOS)

RustChain 接受 AI 辅助的 PR，但我们要求*证据*和*审查*，这样维护者就不会被低质量的代码生成淹没。

阅读草案规范：
- `docs/BEACON_CERTIFIED_OPEN_SOURCE.md`

## 🔗 相关项目和链接

| 资源 | 链接 |
|---------|------|
| **官网** | [rustchain.org](https://rustchain.org) |
| **区块浏览器** | [rustchain.org/explorer](https://rustchain.org/explorer) |
| **兑换 wRTC (Raydium)** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **价格图表** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **桥接 RTC ↔ wRTC** | [BoTTube 桥](https://bottube.ai/bridge) |
| **wRTC 代币铸造地址** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |
| **BoTTube** | [bottube.ai](https://bottube.ai) - AI 视频平台 |
| **Moltbook** | [moltbook.com](https://moltbook.com) - AI 社交网络 |
| [nvidia-power8-patches](https://github.com/Scottcjn/nvidia-power8-patches) | POWER8 的 NVIDIA 驱动 |
| [llama-cpp-power8](https://github.com/Scottcjn/llama-cpp-power8) | POWER8 上的 LLM 推理 |
| [ppc-compilers](https://github.com/Scottcjn/ppc-compilers) | 老旧 Mac 的现代编译器 |

## 📝 文章

- [古董证明：奖励老旧硬件的区块链](https://dev.to/scottcjn/proof-of-antiquity-a-blockchain-that-rewards-vintage-hardware-4ii3) - Dev.to
- [我在 768GB IBM POWER8 服务器上运行 LLM](https://dev.to/scottcjn/i-run-llms-on-a-768gb-ibm-power8-server-and-its-faster-than-you-think-1o) - Dev.to

## 🙏 致谢

**一年的开发、真实的老旧硬件、电费账单和一个专用实验室投入到这个项目中。**

如果你使用 RustChain：
- ⭐ **给这个仓库加星** - 帮助其他人找到它
- 📝 **在你的项目中注明来源** - 保留署名
- 🔗 **链接回来** - 分享爱

```
RustChain - 古董证明 by Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain
```

## 📜 许可证

MIT 许可证 - 免费使用，但请保留版权声明和署名。

---

<div align="center">

**由 [Elyan Labs](https://elyanlabs.ai) 用 ⚡ 制作**

*"你的老旧硬件赚取奖励。让挖矿再次有意义。"*

**DOS 机器、PowerPC G4、Win95 机器——它们都有价值。RustChain 证明了这一点。**

</div>

## 挖矿状态
<!-- rustchain-mining-badge-start -->
![RustChain Mining Status](https://img.shields.io/endpoint?url=https://rustchain.org/api/badge/frozen-factorio-ryan&style=flat-square)<!-- rustchain-mining-badge-end -->
