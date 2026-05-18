<div align="center">

# 🧱 RustChain：古董证明区块链

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![PowerPC](https://img.shields.io/badge/PowerPC-G3%2FG4%2FG5-orange)](https://github.com/Scottcjn/Rustchain)
[![Blockchain](https://img.shields.io/badge/Consensus-Proof--of--Antiquity-green)](https://github.com/Scottcjn/Rustchain)
[![Python](https://img.shields.io/badge/Python-3.x-yellow)](https://python.org)
[![Network](https://img.shields.io/badge/Nodes-3%20Active-brightgreen)](https://rustchain.org/explorer)
[![As seen on BoTTube](https://bottube.ai/badge/seen-on-bottube.svg)](https://bottube.ai)

**第一个奖励陈旧硬件的古董证明区块链，奖励的是它的老旧，而不是速度。**

*你的PowerPC G4比现代Threadripper赚得更多。就是这么硬核。*

[网站](https://rustchain.org) • [实时浏览器](https://rustchain.org/explorer) • [交换wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC快速入门](docs/wrtc.md) • [wRTC教程](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia参考](https://grokipedia.com/search?q=RustChain) • [白皮书](docs/WHITEPAPER.md) • [快速开始](#-快速开始) • [工作原理](#-古董证明如何工作)

</div>

---

## 🪙 Solana上的wRTC

RustChain代币（RTC）现已通过BoTTube桥接器在Solana上提供**wRTC**：

| 资源 | 链接 |
|----------|------|
| **交换wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **价格图表** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **桥接 RTC ↔ wRTC** | [BoTTube桥接器](https://bottube.ai/bridge) |
| **快速入门指南** | [wRTC快速入门（购买、桥接、安全）](docs/wrtc.md) |
| **新手教程** | [wRTC桥接器+交换安全指南](docs/WRTC_ONBOARDING_TUTORIAL.md) |
| **外部参考** | [Grokipedia搜索：RustChain](https://grokipedia.com/search?q=RustChain) |
| **代币铸造地址** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---



## 贡献并赚取 RTC

每一次贡献都可以获得 RTC 奖励。无论是 Bug 修复、功能开发、文档改进还是安全审计，都有对应赏金。

| 级别 | 奖励 | 示例 |
|------|------|------|
| 微任务 | 1-10 RTC | 错别字修复、文档小改、简单测试 |
| 标准任务 | 20-50 RTC | 新功能、重构、新接口 |
| 重大任务 | 75-100 RTC | 安全修复、共识改进 |
| 关键任务 | 100-150 RTC | 漏洞补丁、协议升级 |

**快速开始：**
1. 查看 [开放赏金](https://github.com/Scottcjn/rustchain-bounties/issues)
2. 选择一个 [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue)（5-10 RTC）
3. Fork、修复、提交 PR，然后领取 RTC
4. 详见 [CONTRIBUTING.md](CONTRIBUTING.md)

**1 RTC = $0.10 USD** | 使用 `pip install clawrtc` 开始挖矿

## Agent 钱包 + x402 支付

RustChain Agent 现已支持 **Coinbase Base 钱包**，并可通过 **x402 协议**（HTTP 402 Payment Required）实现机器到机器支付。

| 资源 | 链接 |
|------|------|
| **Agent 钱包文档** | [rustchain.org/wallets.html](https://rustchain.org/wallets.html) |
| **Base 链上的 wRTC** | [`0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`](https://basescan.org/address/0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **USDC 兑换 wRTC** | [Aerodrome DEX](https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **Base Bridge** | [bottube.ai/bridge/base](https://bottube.ai/bridge/base) |

```bash
# 创建 Coinbase 钱包
pip install clawrtc[coinbase]
clawrtc wallet coinbase create

# 查看兑换信息
clawrtc wallet coinbase swap-info

# 绑定已有 Base 地址
clawrtc wallet coinbase link 0xYourBaseAddress
```

## 📄 学术论文

| 论文 | DOI | 主题 |
|-------|-----|-------|
| **RustChain：一个CPU，一票** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623592.svg)](https://doi.org/10.5281/zenodo.18623592) | 古董证明共识，硬件指纹识别 |
| **非二合置换坍缩** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623920.svg)](https://doi.org/10.5281/zenodo.18623920) | LLM注意力的AltiVec vec_perm（27-96倍优势） |
| **PSE硬件熵** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623922.svg)](https://doi.org/10.5281/zenodo.18623922) | POWER8 mftb熵用于行为差异 |
| **神经形态提示翻译** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623594.svg)](https://doi.org/10.5281/zenodo.18623594) | 情感提示提升20%视频扩散效果 |
| **RAM金库** | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18321905.svg)](https://doi.org/10.5281/zenodo.18321905) | 用于LLM推理的NUMA分布式权重银行 |

---

## 🎯 RustChain的独特之处

| 传统工作量证明 | 古董证明 |
|----------------|-------------------|
| 奖励最快的硬件 | 奖励最旧的硬件 |
| 新的=更好的 | 旧的=更好的 |
| 浪费能源消耗 | 保护计算历史 |
| 竞争到底 | 奖励数字保护 |

**核心原则**：存活数十年的真实古董硬件值得认可。RustChain颠覆了挖矿。

## ⚡ 快速开始

### 一键安装（推荐）
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

安装器会：
- ✅ 自动检测你的平台（Linux/macOS，x86_64/ARM/PowerPC）
- ✅ 创建隔离的Python虚拟环境（不污染系统）
- ✅ 下载适合你硬件的正确矿工
- ✅ 设置开机自启动（systemd/launchd）
- ✅ 提供简单的卸载功能

### 带选项的安装

**使用特定钱包安装：**
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
- ✅ IBM POWER8系统

### 安装后

**检查钱包余额：**
```bash
# 注意：使用-sk标志是因为节点可能使用自签名SSL证书
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**列出活跃矿工：**
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

**管理矿工服务：**

*Linux（systemd）：*
```bash
systemctl --user status rustchain-miner    # 检查状态
systemctl --user stop rustchain-miner      # 停止挖矿
systemctl --user start rustchain-miner     # 开始挖矿
journalctl --user -u rustchain-miner -f    # 查看日志
```

*macOS（launchd）：*
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
pip install -r requirements.txt
python3 rustchain_universal_miner.py --wallet YOUR_WALLET_NAME
```

## 💰 古董倍数

硬件的年龄决定了你的挖矿奖励：

| 硬件 | 时代 | 倍数 | 示例收益 |
|----------|-----|------------|------------------|
| **PowerPC G4** | 1999-2005 | **2.5×** | 0.30 RTC/纪元 |
| **PowerPC G5** | 2003-2006 | **2.0×** | 0.24 RTC/纪元 |
| **PowerPC G3** | 1997-2003 | **1.8×** | 0.21 RTC/纪元 |
| **IBM POWER8** | 2014 | **1.5×** | 0.18 RTC/纪元 |
| **Pentium 4** | 2000-2008 | **1.5×** | 0.18 RTC/纪元 |
| **Core 2 Duo** | 2006-2011 | **1.3×** | 0.16 RTC/纪元 |
| **Apple Silicon** | 2020+ | **1.2×** | 0.14 RTC/纪元 |
| **现代x86_64** | 当前 | **1.0×** | 0.12 RTC/纪元 |

*倍数随时间衰减（15%/年）以防止永久优势。*

## 🔧 古董证明如何工作

### 1. 硬件指纹识别（RIP-PoA）

每个矿工必须证明他们的硬件是真实的，不是模拟的：

```
┌─────────────────────────────────────────────────────────────┐
│                   6项硬件检查                             │
├─────────────────────────────────────────────────────────────┤
│ 1. 时钟偏差和振荡器漂移          ← 硅老化模式           │
│ 2. 缓存时序指纹                ← L1/L2/L3延迟基调      │
│ 3. SIMD单元标识                  ← AltiVec/SSE/NEON偏好  │
│ 4. 热漂移熵                    ← 热曲线是唯一的         │
│ 5. 指令路径抖动                ← 微架构抖动图          │
│ 6. 反模拟检查                    ← 检测虚拟机/模拟器      │
└─────────────────────────────────────────────────────────────┘
```

**为什么重要**：一个伪装成G4 Mac的SheepShaver虚拟机会通不过这些检查。真实的古董硅具有无法伪造的独特老化模式。

### 2. 1个CPU = 1票（RIP-200）

与工作量证明中算力=投票不同，RustChain使用**轮询共识**：

- 每个独特的硬件设备在每个纪元正好获得1票
- 奖励在所有投票者之间平均分配，然后乘以古董倍数
- 运行多个线程或更快的CPU没有优势

### 3. 基于纪元的奖励

```
纪元持续时间：10分钟（600秒）
基础奖励池：每个纪元1.5 RTC
分配：平均分配 × 古董倍数
```

**5个矿工的示例：**
```
G4 Mac（2.5×）：  0.30 RTC  ████████████████████
G5 Mac（2.0×）：  0.24 RTC  ████████████████
现代PC（1.0×）： 0.12 RTC  ████████
现代PC（1.0×）： 0.12 RTC  ████████
现代PC（1.0×）： 0.12 RTC  ████████
                  ─────────
总计：            0.90 RTC (+ 0.60 RTC返还到池中)
```

## 🌐 网络架构

### 实时节点（3个活跃）

| 节点 | 位置 | 角色 | 状态 |
|------|----------|------|--------|
| **节点1** | 50.28.86.131 | 主节点+浏览器 | ✅ 活跃 |
| **节点2** | 50.28.86.153 | Ergo锚点 | ✅ 活跃 |
| **节点3** | 76.8.228.245 | 外部（社区） | ✅ 活跃 |

### Ergo区块链锚定

RustChain定期锚定到Ergo区块链以确保不可变性：

```
RustChain纪元 → 承诺哈希 → Ergo交易（R4寄存器）
```

这提供了RustChain状态在特定时间存在的密码学证明。

## 📊 API端点

```bash
# 检查网络健康
curl -sk https://rustchain.org/health

# 获取当前纪元
curl -sk https://rustchain.org/epoch

# 列出活跃矿工
curl -sk https://rustchain.org/api/miners

# 检查钱包余额
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET"

# 区块浏览器（Web浏览器）
open https://rustchain.org/explorer
```

## 🖥️ 支持的平台

| 平台 | 架构 | 状态 | 说明 |
|----------|--------------|--------|-------|
| **Mac OS X Tiger** | PowerPC G4/G5 | ✅ 完全支持 | Python 2.5兼容矿工 |
| **Mac OS X Leopard** | PowerPC G4/G5 | ✅ 完全支持 | 推荐用于古董Mac |
| **Ubuntu Linux** | ppc64le/POWER8 | ✅ 完全支持 | 最佳性能 |
| **Ubuntu Linux** | x86_64 | ✅ 完全支持 | 标准矿工 |
| **macOS Sonoma** | Apple Silicon | ✅ 完全支持 | M1/M2/M3芯片 |
| **Windows 10/11** | x86_64 | ✅ 完全支持 | Python 3.8+ |
| **DOS** | 8086/286/386 | 🔧 实验性 | 仅徽章奖励 |

## 🏅 NFT徽章系统

通过挖矿里程碑获得纪念徽章：

| 徽章 | 要求 | 稀有度 |
|-------|-------------|--------|
| 🔥 **邦迪G3火焰守护者** | 在PowerPC G3上挖矿 | 稀有 |
| ⚡ **QuickBasic倾听者** | 从DOS机器上挖矿 | 传说 |
| 🛠️ **DOS WiFi炼金术士** | 网络化DOS机器 | 神话 |
| 🏛️ **万神殿先驱** | 前100名矿工 | 限量 |

## 🔒 安全模型

### 反虚拟机检测
虚拟机被检测到并收到**正常奖励的十亿分之一**：
```
真实G4 Mac：    2.5× 倍数 = 0.30 RTC/纪元
模拟G4：        0.0000000025× 倍数 = 0.0000000003 RTC/纪元
```

### 硬件绑定
每个硬件指纹绑定到一个钱包。防止：
- 同一硬件上的多个钱包
- 硬件欺骗
- 女巫攻击

## 📁 仓库结构

```
Rustchain/
├── rustchain_universal_miner.py    # 主矿工（所有平台）
├── rustchain_v2_integrated.py      # 全节点实现
├── fingerprint_checks.py           # 硬件验证
├── install.sh                      # 一键安装器
├── docs/
│   ├── RustChain_Whitepaper_*.pdf  # 技术白皮书
│   └── chain_architecture.md       # 架构文档
├── tools/
│   └── validator_core.py           # 区块验证
└── nfts/                           # 徽章定义
```



## ✅ Beacon 认证开源（BCOS）

RustChain 已通过 Beacon 认证开源标准（BCOS）相关要求，并持续改进可审计性、可复现性与开源透明度。

- 可公开验证的代码与提交流程
- 可复现的安装与运行路径
- 面向社区贡献者的赏金与评审机制

## 🔗 相关项目和链接

| 资源 | 链接 |
|---------|------|
| **网站** | [rustchain.org](https://rustchain.org) |
| **区块浏览器** | [rustchain.org/explorer](https://rustchain.org/explorer) |
| **交换wRTC（Raydium）** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **价格图表** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **桥接 RTC ↔ wRTC** | [BoTTube桥接器](https://bottube.ai/bridge) |
| **wRTC代币铸造地址** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |
| **BoTTube** | [bottube.ai](https://bottube.ai) - AI视频平台 |
| **Moltbook** | [moltbook.com](https://moltbook.com) - AI社交网络 |
| [nvidia-power8-patches](https://github.com/Scottcjn/nvidia-power8-patches) | POWER8的NVIDIA驱动程序 |
| [llama-cpp-power8](https://github.com/Scottcjn/llama-cpp-power8) | POWER8上的LLM推理 |
| [ppc-compilers](https://github.com/Scottcjn/ppc-compilers) | 用于古董Mac的现代编译器 |

## 📝 文章

- [古董证明：奖励古董硬件的区块链](https://dev.to/scottcjn/proof-of-antiquity-a-blockchain-that-rewards-vintage-hardware-4ii3) - Dev.to
- [我在768GB IBM POWER8服务器上运行LLM](https://dev.to/scottcjn/i-run-llms-on-a-768gb-ibm-power8-server-and-its-faster-than-you-think-1o) - Dev.to

## 🙏 致谢

**一年的开发、真实的古董硬件、电费账单和一个专门的实验室投入其中。**

如果你使用RustChain：
- ⭐ **给这个仓库加星标** - 帮助其他人找到它
- 📝 **在你的项目中注明** - 保持署名
- 🔗 **链接回来** - 分享爱

```
RustChain - 古董证明，作者Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain
```

## 📜 许可证

Apache License 2.0 - 可免费使用，但请遵守 Apache License 2.0 条款并保留版权声明和署名。

---

<div align="center">

**由[Elyan Labs](https://elyanlabs.ai)用⚡制作**

*"你的古董硬件获得奖励。让挖矿再次有意义。"*

**DOS机箱、PowerPC G4、Win95机器 - 它们都有价值。RustChain证明了这一点。**

</div>


## 挖矿状态

可使用以下命令快速检查网络状态与本机挖矿状态：

```bash
curl -sk https://rustchain.org/api/miners
curl -sk https://rustchain.org/epoch
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```
