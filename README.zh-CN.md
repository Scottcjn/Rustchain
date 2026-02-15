<div align="center">

# 🧱 RustChain: 过时证明（Proof-of-Antiquity）区块链

[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PowerPC](https://img.shields.io/badge/PowerPC-G3%2FG4%2FG5-orange)](https://github.com/Scottcjn/Rustchain)
[![Blockchain](https://img.shields.io/badge/Consensus-Proof--of--Antiquity-green)](https://github.com/Scottcjn/Rustchain)
[![Python](https://img.shields.io/badge/Python-3.x-yellow)](https://python.org)
[![Network](https://img.shields.io/badge/Nodes-3%20Active-brightgreen)](https://rustchain.org/explorer)
[![As seen on BoTTube](https://bottube.ai/badge/seen-on-bottube.svg)](https://bottube.ai)

**第一个奖励老旧硬件而非高性能硬件的区块链。**

*你的 PowerPC G4 赚得比现代 Threadripper 还多。这就是核心意义。*

[网站](https://rustchain.org) • [实时浏览器](https://rustchain.org/explorer) • [兑换 wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC 快速入门](docs/wrtc.md) • [wRTC 教程](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia 参考](https://grokipedia.com/search?q=RustChain) • [白皮书](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [快速开始](#-快速开始) • [运作原理](#-过时证明如何运作)

</div>

---

## 🪙 Solana 上的 wRTC

RustChain 代币 (RTC) 现在通过 BoTTube 桥以 **wRTC** 的形式在 Solana 上可用：

| 资源 | 链接 |
|----------|------|
| **兑换 wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **价格图表** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **RTC ↔ wRTC 跨链桥** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **快速入门指南** | [wRTC 快速入门（购买、跨链、安全）](docs/wrtc.md) |
| **入门教程** | [wRTC 跨链 + 兑换安全指南](docs/WRTC_ONBOARDING_TUTORIAL.md) |
| **外部参考** | [Grokipedia 搜索: RustChain](https://grokipedia.com/search?q=RustChain) |
| **代币合约** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## 📄 学术出版物

| 论文 | DOI | 主题 |
|-------|-----|-------|
| **RustChain: One CPU, One Vote** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623592.svg)](https://doi.org/10.5281/zenodo.18623592) | 过时证明共识，硬件指纹识别 |
| **Non-Bijunctive Permutation Collapse** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623920.svg)](https://doi.org/10.5281/zenodo.18623920) | AltiVec vec_perm 用于 LLM 注意力机制 (27-96x 优势) |
| **PSE Hardware Entropy** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623922.svg)](https://doi.org/10.5281/zenodo.18623922) | POWER8 mftb 熵用于行为差异 |
| **Neuromorphic Prompt Translation** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623594.svg)](https://doi.org/10.5281/zenodo.18623594) | 情感提示词用于 20% 视频扩散收益 |
| **RAM Coffers** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18321905.svg)](https://doi.org/10.5281/zenodo.18321905) | NUMA 分布式权重库用于 LLM 推理 |

---

## 🎯 RustChain 的独特之处

| 传统 PoW | 过时证明 (PoA) |
|----------------|-------------------|
| 奖励最快的硬件 | 奖励最旧的硬件 |
| 越新 = 越好 | 越旧 = 越好 |
| 巨大的能源消耗 | 保护计算机历史 |
| 向底线的种族竞争 | 奖励数字保存 |

**核心原则**：存活了几十年的真实老旧硬件值得被认可。RustChain 彻底颠覆了挖矿。

## ⚡ 快速开始

### 一键安装（推荐）
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

安装程序将：
- ✅ 自动检测你的平台（Linux/macOS, x86_64/ARM/PowerPC）
- ✅ 创建隔离的 Python 虚拟环境（不污染系统）
- ✅ 下载适合你硬件的正确挖矿程序
- ✅ 设置开机自启 (systemd/launchd)
- ✅ 提供简单的卸载方式

### 安装选项

**使用特定钱包安装：**
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

### 安装之后

**查看钱包余额：**
```bash
# 注意：使用 -sk 参数，因为节点可能使用自签名 SSL 证书
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**列出活跃矿工：**
```bash
curl -sk https://50.28.86.131/api/miners
```

**检查节点健康状况：**
```bash
curl -sk https://50.28.86.131/health
```

**获取当前 Epoch：**
```bash
curl -sk https://50.28.86.131/epoch
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
pip install -r requirements.txt
python3 rustchain_universal_miner.py --wallet YOUR_WALLET_NAME
```

## 💰 过时加成倍率

硬件的年龄决定了你的挖矿奖励：

| 硬件 | 时代 | 倍率 | 预估收益示例 |
|----------|-----|------------|------------------|
| **PowerPC G4** | 1999-2005 | **2.5×** | 0.30 RTC/epoch |
| **PowerPC G5** | 2003-2006 | **2.0×** | 0.24 RTC/epoch |
| **PowerPC G3** | 1997-2003 | **1.8×** | 0.21 RTC/epoch |
| **IBM POWER8** | 2014 | **1.5×** | 0.18 RTC/epoch |
| **Pentium 4** | 2000-2008 | **1.5×** | 0.18 RTC/epoch |
| **Core 2 Duo** | 2006-2011 | **1.3×** | 0.16 RTC/epoch |
| **Apple Silicon** | 2020+ | **1.2×** | 0.14 RTC/epoch |
| **Modern x86_64** | 当前 | **1.0×** | 0.12 RTC/epoch |

*倍率会随时间衰减（15%/年），以防止永久性优势。*

## 🔧 过时证明如何运作

### 1. 硬件指纹识别 (RIP-PoA)

每个矿工必须证明其硬件是真实的，而非模拟的：

```
┌─────────────────────────────────────────────────────────────┐
│                   6 项硬件检查                               │
├─────────────────────────────────────────────────────────────┤
│ 1. 时钟偏移与振荡器漂移          ← 硅片老化模式              │
│ 2. 缓存定时指纹                  ← L1/L2/L3 延迟特性         │
│ 3. SIMD 单元标识                 ← AltiVec/SSE/NEON 偏置     │
│ 4. 热漂移熵                      ← 热曲线是唯一的            │
│ 5. 指令路径抖动                  ← 微架构抖动图              │
│ 6. 反模拟检查                    ← 检测虚拟机/模拟器         │
└─────────────────────────────────────────────────────────────┘
```

**为什么这很重要**：一个假装成 G4 Mac 的 SheepShaver 虚拟机将无法通过这些检查。真实的老旧硅片具有无法伪造的独特老化模式。

### 2. 每个 CPU = 一票 (RIP-200)

与算力即投票的 PoW 不同，RustChain 使用 **轮询共识**：

- 每个独特的硬件设备在每个 Epoch 获得且仅获得 1 票
- 奖励在所有投票者中平均分配，然后乘以过时倍率
- 运行多个线程或使用更快的 CPU 没有优势

### 3. 基于 Epoch 的奖励

```
Epoch 时长：10 分钟 (600 秒)
基础奖励池：每个 Epoch 1.5 RTC
分配方式：等额分配 × 过时加成倍率
```

**5 个矿工的分配示例：**
```
G4 Mac (2.5×):     0.30 RTC  ████████████████████
G5 Mac (2.0×):     0.24 RTC  ████████████████
现代 PC (1.0×):    0.12 RTC  ████████
现代 PC (1.0×):    0.12 RTC  ████████
现代 PC (1.0×):    0.12 RTC  ████████
                   ─────────
总计：             0.90 RTC (+ 0.60 RTC 返回池中)
```

## 🌐 网络架构

### 活跃节点 (3 个活跃)

| 节点 | 位置 | 角色 | 状态 |
|------|----------|------|--------|
| **Node 1** | 50.28.86.131 | 主节点 + 浏览器 | ✅ 活跃 |
| **Node 2** | 50.28.86.153 | Ergo 锚点 | ✅ 活跃 |
| **Node 3** | 76.8.228.245 | 外部（社区） | ✅ 活跃 |

### Ergo 区块链锚定

RustChain 定期在 Ergo 区块链上锚定以保证不可篡改性：

```
RustChain Epoch → 承诺哈希 → Ergo 交易 (R4 寄存器)
```

这提供了 RustChain 状态在特定时间存在的加密证明。

## 📊 API 端点

```bash
# 检查网络健康
curl -sk https://50.28.86.131/health

# 获取当前 Epoch
curl -sk https://50.28.86.131/epoch

# 列出活跃矿工
curl -sk https://50.28.86.131/api/miners

# 查看钱包余额
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET"

# 区块浏览器（网页版）
open https://rustchain.org/explorer
```

## 🖥️ 支持的平台

| 平台 | 架构 | 状态 | 备注 |
|----------|--------------|--------|-------|
| **Mac OS X Tiger** | PowerPC G4/G5 | ✅ 完全支持 | Python 2.5 兼容矿工 |
| **Mac OS X Leopard** | PowerPC G4/G5 | ✅ 完全支持 | 推荐老旧 Mac 使用 |
| **Ubuntu Linux** | ppc64le/POWER8 | ✅ 完全支持 | 最佳性能 |
| **Ubuntu Linux** | x86_64 | ✅ 完全支持 | 标准矿工 |
| **macOS Sonoma** | Apple Silicon | ✅ 完全支持 | M1/M2/M3 芯片 |
| **Windows 10/11** | x86_64 | ✅ 完全支持 | Python 3.8+ |
| **DOS** | 8086/286/386 | 🔧 实验性 | 仅限徽章奖励 |

## 🏅 NFT 徽章系统

通过挖矿里程碑赢取纪念徽章：

| 徽章 | 要求 | 稀有度 |
|-------|-------------|--------|
| 🔥 **Bondi G3 守焰者** | 在 PowerPC G3 上挖矿 | 稀有 |
| ⚡ **QuickBasic 听众** | 在 DOS 机器上挖矿 | 传奇 |
| 🛠️ **DOS WiFi 炼金术士** | 使 DOS 机器联网 | 神话 |
| 🏛️ **万神殿先驱** | 前 100 名矿工 | 限量 |

## 🔒 安全模型

### 反虚拟机检测
虚拟机被检测到后仅获得正常奖励的 **十亿分之一**：
```
真实 G4 Mac:     2.5× 倍率  = 0.30 RTC/epoch
模拟 G4:         0.0000000025× = 0.0000000003 RTC/epoch
```

### 硬件绑定
每个硬件指纹都绑定到一个钱包。防止：
- 同一硬件运行多个钱包
- 硬件伪造
- 女巫攻击

## 📁 仓库结构

```
Rustchain/
├── rustchain_universal_miner.py    # 主挖矿程序（全平台）
├── rustchain_v2_integrated.py      # 全节点实现
├── fingerprint_checks.py           # 硬件验证
├── install.sh                      # 一键安装脚本
├── docs/
│   ├── RustChain_Whitepaper_*.pdf  # 技术白皮书
│   └── chain_architecture.md       # 架构文档
├── tools/
│   └── validator_core.py           # 区块验证
└── nfts/                           # 徽章定义
```

## ✅ Beacon 认证开源 (BCOS)

RustChain 接受 AI 辅助的 PR，但我们需要*证据*和*审查*，以确保维护者不会淹没在低质量的自动生成代码中。

阅读草案规范：
- `docs/BEACON_CERTIFIED_OPEN_SOURCE.md`

## 🔗 相关项目与链接

| 资源 | 链接 |
|---------|------|
| **网站** | [rustchain.org](https://rustchain.org) |
| **区块浏览器** | [rustchain.org/explorer](https://rustchain.org/explorer) |
| **兑换 wRTC (Raydium)** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **价格图表** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **RTC ↔ wRTC 跨链桥** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **wRTC 代币合约** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |
| **BoTTube** | [bottube.ai](https://bottube.ai) - AI 视频平台 |
| **Moltbook** | [moltbook.com](https://moltbook.com) - AI 社交网络 |
| [nvidia-power8-patches](https://github.com/Scottcjn/nvidia-power8-patches) | 适用于 POWER8 的 NVIDIA 驱动 |
| [llama-cpp-power8](https://github.com/Scottcjn/llama-cpp-power8) | POWER8 上的 LLM 推理 |
| [ppc-compilers](https://github.com/Scottcjn/ppc-compilers) | 适用于老旧 Mac 的现代编译器 |

## 📝 文章

- [Proof of Antiquity: A Blockchain That Rewards Vintage Hardware](https://dev.to/scottcjn/proof-of-antiquity-a-blockchain-that-rewards-vintage-hardware-4ii3) - Dev.to
- [I Run LLMs on a 768GB IBM POWER8 Server](https://dev.to/scottcjn/i-run-llms-on-a-768gb-ibm-power8-server-and-its-faster-than-you-think-1o) - Dev.to

## 🙏 致谢

**这是一年的开发、真实的硬件、电费账单和专门实验室的心血结晶。**

如果你使用 RustChain：
- ⭐ **关注 (Star) 此仓库** - 帮助他人发现它
- 📝 **在你的项目中注明出处** - 保留版权声明
- 🔗 **回链** - 分享热爱

```
RustChain - Proof of Antiquity by Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain
```

## 📜 许可证

MIT 许可证 - 免费使用，但请保留版权声明和致谢。

---

<div align="center">

**由 [Elyan Labs](https://elyanlabs.ai) 倾情打造 ⚡**

*"你的老旧硬件值得奖励。让挖矿重新产生意义。"*

**DOS 盒子、PowerPC G4、Win95 机器 —— 它们都有价值。RustChain 证明了这一点。**

</div>
