<div align="center">

# 🧱 RustChain: 古老性证明区块链

[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/Scottcjn/Rustchain?style=flat&color=gold)](https://github.com/Scottcjn/Rustchain/stargazers)
[![Contributors](https://img.shields.io/github/contributors/Scottcjn/Rustchain?color=brightgreen)](https://github.com/Scottcjn/Rustchain/graphs/contributors)
[![Last Commit](https://img.shields.io/github/last-commit/Scottcjn/Rustchain?color=blue)](https://github.com/Scottcjn/Rustchain/commits/main)
[![Open Issues](https://img.shields.io/github/issues/Scottcjn/Rustchain?color=orange)](https://github.com/Scottcjn/Rustchain/issues)
[![PowerPC](https://img.shields.io/badge/PowerPC-G3%2FG4%2FG5-orange)](https://github.com/Scottcjn/Rustchain)
[![Blockchain](https://img.shields.io/badge/Consensus-Proof--of--Antiquity-green)](https://github.com/Scottcjn/Rustchain)
[![Python](https://img.shields.io/badge/Python-3.x-yellow)](https://www.python.org)
[![Network](https://img.shields.io/badge/Nodes-3%20Active-brightgreen)](https://rustchain.org/explorer)
[![Bounties](https://img.shields.io/badge/Bounties-Open%20%F0%9F%92%B0-green)](https://github.com/Scottcjn/rustchain-bounties/issues)
[![As seen on BoTTube](https://bottube.ai/badge/seen-on-bottube.svg)](https://bottube.ai)
[![Discussions](https://img.shields.io/github/discussions/Scottcjn/Rustchain?color=purple)](https://github.com/Scottcjn/Rustchain/discussions)

**首个因硬件古老而奖励，而非因算力强大的区块链。**

*你的 PowerPC G4 赚得比现代 Threadripper 还多。这就是目的。*

[网站](https://rustchain.org) • [宣言](https://rustchain.org/manifesto.html) • [Boudreaux 原则](docs/BOUDREAUX_COMPUTING_PRINCIPLES.md) • [在线浏览器](https://rustchain.org/explorer) • [兑换 wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC 快速入门](docs/wrtc.md) • [wRTC 教程](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia 参考](https://grokipedia.com/search?q=RustChain) • [白皮书](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [快速开始](#-快速开始) • [工作原理](#-古老性证明如何工作)

</div>

---

## Q1 2026 发展数据

> *所有数据来自 GitHub API 实时抓取，对比 GitClear（878K 开发者年）、LinearB（810万 PRs）和 Electric Capital 基准。*

| 指标 (90天) | Elyan Labs | 行业中位数 | Sei Protocol ($85M) |
|-------------------|-----------|----------------|---------------------|
| 提交数 | **1,882** | 105-168 | 297 |
| 发版仓库数 | **97** | 1-3 | 0 新建 |
| GitHub stars | **1,334** | 5-30 | 2,837 (累计) |
| 开发者互动 | **150+** | 0-2 | 78 (累计) |
| 开发者/月提交数 | **627** | 56 | 7.6 |
| 外部贡献 PRs | **32 PRs** | 0-2 | 0 |
| 融资 | **$0** | $0 | $85,000,000 |

**[完整发展报告（含方法论和来源）→](https://github.com/Scottcjn/Rustchain/blob/main/docs/DEVELOPER_TRACTION_Q1_2026.md)**

---

## 🪙 Solana 上的 wRTC

RustChain 代币 (RTC) 现已通过 BoTTube Bridge 在 Solana 上以 **wRTC** 形式存在：

| 资源 | 链接 |
|----------|------|
| **兑换 wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **价格图表** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **桥接 RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **快速入门指南** | [wRTC 快速入门 (购买、桥接、安全)](docs/wrtc.md) |
| **入门教程** | [wRTC 桥接 + 兑换安全指南](docs/WRTC_ONBOARDING_TUTORIAL.md) |
| **外部参考** | [Grokipedia 搜索: RustChain](https://grokipedia.com/search?q=RustChain) |
| **代币 Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## 贡献并赚取 RTC

每一次贡献都能获得 RTC 代币。Bug 修复、功能开发、文档、安全审计 — 全部有报酬。

| 等级 | 奖励 | 示例 |
|------|--------|----------|
| 微型 | 1-10 RTC | 拼写修正、小文档、简单测试 |
| 标准 | 20-50 RTC | 功能开发、重构、新接口 |
| 重要 | 75-100 RTC | 安全修复、共识改进 |
| 关键 | 100-150 RTC | 漏洞补丁、协议升级 |

**入门步骤：**
1. 浏览 [开放赏金](https://github.com/Scottcjn/rustchain-bounties/issues)
2. 选择一个 [新手友好 issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue) (5-10 RTC)
3. Fork、修复、提交 PR — 以 RTC 获得报酬
4. 查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解完整细节

**1 RTC = $0.10 USD** | 运行 `pip install clawrtc` 开始挖矿

---

## 代理钱包 + x402 支付

RustChain 代理现在可以拥有 **Coinbase Base 钱包**，并使用 **x402 协议** (HTTP 402 Payment Required) 进行机器对机器支付：

| 资源 | 链接 |
|----------|------|
| **代理钱包文档** | [rustchain.org/wallets.html](https://rustchain.org/wallets.html) |
| **Base 上的 wRTC** | [`0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`](https://basescan.org/address/0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **USDC 兑换 wRTC** | [Aerodrome DEX](https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **Base 桥接** | [bottube.ai/bridge/base](https://bottube.ai/bridge/base) |

```bash
# 创建 Coinbase 钱包
pip install clawrtc[coinbase]
clawrtc wallet coinbase create

# 查看兑换信息
clawrtc wallet coinbase swap-info

# 关联现有 Base 地址
clawrtc wallet coinbase link 0xYourBaseAddress
```

**x402 高级 API 端点**已上线（验证流程期间免费）：
- `GET /api/premium/videos` - 批量视频导出 (BoTTube)
- `GET /api/premium/analytics/<agent>` - 深度代理分析 (BoTTube)
- `GET /api/premium/reputation` - 完整声誉导出 (Beacon Atlas)
- `GET /wallet/swap-info` - USDC/wRTC 兑换指导 (RustChain)

## 📄 学术出版物

| 论文 | DOI | 主题 |
|-------|-----|-------|
| **RustChain: One CPU, One Vote** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623592.svg)](https://doi.org/10.5281/zenodo.18623592) | 古老性证明共识、硬件指纹识别 |
| **Non-Bijunctive Permutation Collapse** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623920.svg)](https://doi.org/10.5281/zenodo.18623920) | AltiVec vec_perm 用于 LLM 注意力机制 (27-96倍优势) |
| **PSE Hardware Entropy** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623922.svg)](https://doi.org/10.5281/zenodo.18623922) | POWER8 mftb 熵用于行为分歧 |
| **Neuromorphic Prompt Translation** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623594.svg)](https://doi.org/10.5281/zenodo.18623594) | 情感提示带来 20% 视频扩散增益 |
| **RAM Coffers** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18321905.svg)](https://doi.org/10.5281/zenodo.18321905) | NUMA 分布式权重存储用于 LLM 推理 |

---

## 🎯 RustChain 的独特之处

| 传统 PoW | 古老性证明 |
|----------------|-------------------|
| 奖励最快硬件 | 奖励最古老硬件 |
| 越新 = 越好 | 越老 = 越好 |
| 浪费能源 | 保护计算历史 |
| 恶性竞争 | 奖励数字保护 |

**核心原则**：真正存活了数十年的古老硬件值得认可。RustChain 颠覆了挖矿。

## ⚡ 快速开始

### 一行安装（推荐）
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

安装程序功能：
- ✅ 自动检测平台 (Linux/macOS, x86_64/ARM/PowerPC)
- ✅ 创建隔离的 Python 虚拟环境（不污染系统）
- ✅ 下载适合您硬件的挖矿程序
- ✅ 设置开机自启动 (systemd/launchd)
- ✅ 提供轻松卸载

### 可选安装

**指定钱包安装：**
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

### 故障排除

- **安装失败权限错误**：使用有 `~/.local` 写入权限的账户重新运行，避免在系统 Python 全局 site-packages 内运行。
- **Python 版本错误**（`SyntaxError` / `ModuleNotFoundError`）：使用 Python 3.10+ 安装，并将 `python3` 指向该解释器。
  ```bash
  python3 --version
  curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
  ```
- **curl 中 HTTPS 证书错误**：这可能发生在非浏览器客户端环境；先检查连接 `curl -I https://rustchain.org`。
- **挖矿程序立即退出**：验证钱包存在且服务正在运行（`systemctl --user status rustchain-miner` 或 `launchctl list | grep rustchain`）

如果问题持续，请在新建 issue 或赏金评论中附上日志和操作系统详细信息，包括错误输出的精确内容和 `install-miner.sh --dry-run` 结果。

### 安装后

**查看钱包余额：**
```bash
# 注意：使用 -sk 标志，因为节点可能使用自签名 SSL 证书
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**列出活跃挖矿者：**
```bash
curl -sk https://rustchain.org/api/miners
```

**检查节点健康：**
```bash
curl -sk https://rustchain.org/health
```

**获取当前纪元：**
```bash
curl -sk https://rustchain.org/epoch
```

**管理挖矿服务：**

*Linux (systemd):*
```bash
systemctl --user status rustchain-miner    # 查看状态
systemctl --user stop rustchain-miner      # 停止挖矿
systemctl --user start rustchain-miner     # 开始挖矿
journalctl --user -u rustchain-miner -f    # 查看日志
```

*macOS (launchd):*
```bash
launchctl list | grep rustchain            # 查看状态
launchctl stop com.rustchain.miner         # 停止挖矿
launchctl start com.rustchain.miner        # 开始挖矿
tail -f ~/.rustchain/miner.log             # 查看日志
```

### 手动安装
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
bash install-miner.sh --wallet YOUR_WALLET_NAME
# 可选：预览操作而不更改您的系统
bash install-miner.sh --dry-run --wallet YOUR_WALLET_NAME
```

## 💰 赏金看板

通过为 RustChain 生态做贡献赚取 **RTC**！

| 赏金 | 奖励 | 链接 |
|--------|--------|------|
| **首次真实贡献** | 10 RTC | [#48](https://github.com/Scottcjn/Rustchain/issues/48) |
| **网络状态页面** | 25 RTC | [#161](https://github.com/Scottcjn/Rustchain/issues/161) |
| **AI 代理猎手** | 200 RTC | [代理赏金 #34](https://github.com/Scottcjn/rustchain-bounties/issues/34) |

---

## 测试说明

- 证明 malformed-input 模糊测试工具和可重放语料库：[docs/attestation_fuzzing.md](docs/attestation_fuzzing.md)

## 💰 古老性倍率

硬件的年龄决定您的挖矿奖励：

| 硬件 | 时代 | 倍率 | 示例收益 |
|----------|-----|------------|------------------|
| **PowerPC G4** | 1999-2005 | **2.5×** | 0.30 RTC/纪元 |
| **PowerPC G5** | 2003-2006 | **2.0×** | 0.24 RTC/纪元 |
| **PowerPC G3** | 1997-2003 | **1.8×** | 0.21 RTC/纪元 |
| **IBM POWER8** | 2014 | **1.5×** | 0.18 RTC/纪元 |
| **Pentium 4** | 2000-2008 | **1.5×** | 0.18 RTC/纪元 |
| **Core 2 Duo** | 2006-2011 | **1.3×** | 0.16 RTC/纪元 |
| **Apple Silicon** | 2020+ | **1.2×** | 0.14 RTC/纪元 |
| **现代 x86_64** | 当前 | **1.0×** | 0.12 RTC/纪元 |

*倍率会随时间衰减（每年 15%）以防止永久优势。*

## 🔧 古老性证明如何工作

### 1. 硬件指纹识别 (RIP-PoA)

每个挖矿者必须证明他们的硬件是真实的，而不是模拟的：

```
┌─────────────────────────────────────────────────────────────┐
│                   6 项硬件检查                               │
├─────────────────────────────────────────────────────────────┤
│ 1. 时钟偏移 & 振荡器漂移   ← 硅老化模式                     │
│ 2. 缓存时序指纹           ← L1/L2/L3 延迟特征               │
│ 3. SIMD 单元标识          ← AltiVec/SSE/NEON 偏差           │
│ 4. 热漂移熵               ← 热曲线独一无二                   │
│ 5. 指令路径抖动           ← 微架构抖动图                     │
│ 6. 反模拟检查             ← 检测虚拟机/模拟器               │
└─────────────────────────────────────────────────────────────┘
```

**意义**：假装是 G4 Mac 的 SheepShaver VM 将无法通过这些检查。真正的老旧芯片有独特的老化模式，无法伪造。

### 2. 1 CPU = 1 票 (RIP-200)

与 PoW（算力=投票）不同，RustChain 使用**轮询共识**：

- 每个唯一硬件设备在每个纪元获得恰好 1 票
- 奖励在所有投票者之间平均分配，然后乘以古老性倍率
- 运行多线程或更快 CPU 没有优势

### 3. 基于纪元的奖励

```
纪元时长：10 分钟（600 秒）
基础奖励池：每个纪元 1.5 RTC
分配：平均分配 × 古老性倍率
```

**5 个挖矿者示例：**
```
G4 Mac (2.5×):     0.30 RTC  ████████████████████
G5 Mac (2.0×):     0.24 RTC  ████████████████
现代 PC (1.0×):    0.12 RTC  ████████
现代 PC (1.0×):    0.12 RTC  ████████
现代 PC (1.0×):    0.12 RTC  ████████
                    ─────────
总计：              0.90 RTC (+ 0.60 RTC 返回池中)
```

## 🌐 网络架构

### 在线节点（3 个活跃）

| 节点 | 位置 | 角色 | 状态 |
|------|----------|------|--------|
| **节点 1** | 50.28.86.131 | 主节点 + 浏览器 | ✅ 活跃 |
| **节点 2** | 50.28.86.153 | Ergo 锚定 | ✅ 活跃 |
| **节点 3** | 76.8.228.245 | 外部（社区） | ✅ 活跃 |

### Ergo 区块链锚定

RustChain 定期锚定到 Ergo 区块链以确保不可变性：

```
RustChain 纪元 → 承诺哈希 → Ergo 交易（R4 寄存器）
```

这提供了 RustChain 状态在特定时间存在的加密证明。

## 📊 API 端点

```bash
# 检查网络健康
curl -sk https://rustchain.org/health

# 获取当前纪元
curl -sk https://rustchain.org/epoch

# 列出活跃挖矿者
curl -sk https://rustchain.org/api/miners

# 查看钱包余额
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET"

# 区块浏览器（网页浏览器）
open https://rustchain.org/explorer
```

### 治理提案与投票

规则：
- 提案生命周期：`草稿 -> 活跃 (7天) -> 通过/失败`
- 创建提案：钱包必须持有**超过 10 RTC**
- 投票资格：投票者必须是**活跃挖矿者**（来自经验证的挖矿者视图）
- 签名：投票需要 **Ed25519** 签名验证
- 投票权重：`1 RTC = 1 基础票`，然后乘以挖矿者古老性倍率
- 通过条件：`是 > 否`

端点：

```bash
# 创建提案
curl -sk -X POST https://rustchain.org/governance/propose \
  -H 'Content-Type: application/json' \
  -d '{
    "wallet":"RTC...",
    "title":"启用参数 X",
    "description":"理由和实现细节"
  }'

# 列出提案
curl -sk https://rustchain.org/governance/proposals

# 提案详情
curl -sk https://rustchain.org/governance/proposal/1

# 提交签名投票
curl -sk -X POST https://rustchain.org/governance/vote \
  -H 'Content-Type: application/json' \
  -d '{
    "proposal_id":1,
    "wallet":"RTC...",
    "vote":"yes",
    "nonce":"1700000000",
    "public_key":"<ed25519_pubkey_hex>",
    "signature":"<ed25519_signature_hex>"
  }'
```

网页界面：
- `GET /governance/ui` 提供一个轻量页面来列出提案和提交投票。

## 🖥️ 支持的平台

| 平台 | 架构 | 状态 | 备注 |
|----------|--------------|--------|-------|
| **Mac OS X Tiger** | PowerPC G4/G5 | ✅ 完全支持 | Python 2.5 兼容挖矿程序 |
| **Mac OS X Leopard** | PowerPC G4/G5 | ✅ 完全支持 | 推荐用于复古 Mac |
| **Ubuntu Linux** | ppc64le/POWER8 | ✅ 完全支持 | 最佳性能 |
| **Ubuntu Linux** | x86_64 | ✅ 完全支持 | 标准挖矿程序 |
| **macOS Sonoma** | Apple Silicon | ✅ 完全支持 | M1/M2/M3 芯片 |
| **Windows 10/11** | x86_64 | ✅ 完全支持 | Python 3.8+ |
| **DOS** | 8086/286/386 | 🔧 实验性 | 仅徽章奖励 |

## 🏅 NFT 徽章系统

通过挖矿里程碑获得纪念徽章：

| 徽章 | 要求 | 稀有度 |
|-------|-------------|--------|
| 🔥 **Bondi G3 火焰守护者** | 使用 PowerPC G3 挖矿 | 稀有 |
| ⚡ **QuickBasic 监听者** | 使用 DOS 机器挖矿 | 传奇 |
| 🛠️ **DOS WiFi 炼金术士** | 网络 DOS 机器 | 神话 |
| 🏛️ **万神殿先驱** | 前 100 名挖矿者 | 限量 |

## 🔒 安全模型

### 反虚拟机检测
虚拟机会被检测到，并获得**十亿分之一**的正常奖励：
```
真实 G4 Mac:   2.5× 倍率  = 0.30 RTC/纪元
模拟 G4:       0.0000000025×    = 0.0000000003 RTC/纪元
```

### 硬件绑定
每个硬件指纹绑定到一个钱包。防止：
- 同一硬件多个钱包
- 硬件欺骗
- 女巫攻击

## 📁 仓库结构

```
Rustchain/
├── install-miner.sh                # 通用挖矿程序安装脚本 (Linux/macOS)
├── node/
│   ├── rustchain_v2_integrated_v2.2.1_rip200.py  # 完整节点实现
│   └── fingerprint_checks.py       # 硬件验证
├── miners/
│   ├── linux/rustchain_linux_miner.py            # Linux 挖矿程序
│   └── macos/rustchain_mac_miner_v2.4.py         # macOS 挖矿程序
├── docs/
│   ├── RustChain_Whitepaper_*.pdf  # 技术白皮书
│   └── chain_architecture.md       # 架构文档
├── tools/
│   └── validator_core.py           # 区块验证
└── nfts/                           # 徽章定义
```

## ✅ 信标认证开源 (BCOS)

RustChain 接受 AI 辅助的 PR，但我们要求*证据*和*审查*，以免维护者被低质量代码淹没。

阅读草稿规范：
- `docs/BEACON_CERTIFIED_OPEN_SOURCE.md`

## 🔗 相关项目与链接

| 资源 | 链接 |
|---------|------|
| **网站** | [rustchain.org](https://rustchain.org) |
| **区块浏览器** | [rustchain.org/explorer](https://rustchain.org/explorer) |
| **兑换 wRTC (Raydium)** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **价格图表** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **桥接 RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **wRTC 代币 Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

### 生态项目

| 项目 | 链接 |
|---------|------|
| **BoTTube** | [bottube.ai](https://bottube.ai) - AI 视频平台 |
| **Moltbook** | [moltbook.com](https://moltbook.com) - AI 社交网络 |

### 相关仓库

| 资源 | 链接 |
|---------|------|
| [nvidia-power8-patches](https://github.com/Scottcjn/nvidia-power8-patches) | NVIDIA POWER8 驱动 |
| [llama-cpp-power8](https://github.com/Scottcjn/llama-cpp-power8) | POWER8 上运行 LLM 推理 |
| [ppc-compilers](https://github.com/Scottcjn/ppc-compilers) | 复古 Mac 现代编译器 |

---

*“I Built More in 90 Days Than Most Startups Do in a Year” — 90 天内我构建的东西比大多数初创公司一年做的还多*
