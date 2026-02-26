<div align="center">

# 🧱 RustChain: 古董证明区块链

[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/Scottcjn/Rustchain?style=flat&color=gold)](https://github.com/Scottcjn/Rustchain/stargazers)
[![Contributors](https://img.shields.io/github/contributors/Scottcjn/Rustchain?color=brightgreen)](https://github.com/Scottcjn/Rustchain/graphs/contributors)

**第一个奖励老旧硬件的区块链——越老越值钱，而不是越快越好。**

*你的 PowerPC G4 比现代 Threadripper 赚得更多。这就是重点。*

[官网](https://rustchain.org) • [区块浏览器](https://rustchain.org/explorer) • [交易 wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [白皮书](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf) • [快速开始](#-快速开始)

</div>

---

## 🪙 Solana 上的 wRTC

RustChain 代币 (RTC) 现已通过 BoTTube Bridge 在 Solana 上以 **wRTC** 形式提供：

| 资源 | 链接 |
|------|------|
| **交易 wRTC** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **价格图表** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **跨链桥 RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **代币地址** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## 贡献并赚取 RTC

每一次贡献都能获得 RTC 代币奖励。Bug 修复、新功能、文档、安全审计——全部有偿。

| 等级 | 奖励 | 示例 |
|------|------|------|
| 微型 | 1-10 RTC | 修复错别字、小文档、简单测试 |
| 标准 | 20-50 RTC | 新功能、重构、新接口 |
| 重大 | 75-100 RTC | 安全修复、共识改进 |
| 关键 | 100-150 RTC | 漏洞补丁、协议升级 |

**开始参与：**
1. 浏览 [开放的悬赏任务](https://github.com/Scottcjn/rustchain-bounties/issues)
2. 选择一个 [新手友好任务](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue) (5-10 RTC)
3. Fork、修复、提交 PR — 获得 RTC 奖励
4. 查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情

**1 RTC = $0.10 USD** | 运行 `pip install clawrtc` 开始挖矿

---

## 智能体钱包 + x402 支付

RustChain 智能体现在可以拥有 **Coinbase Base 钱包**，并使用 **x402 协议**（HTTP 402 Payment Required）进行机器对机器支付：

| 资源 | 链接 |
|------|------|
| **智能体钱包文档** | [rustchain.org/wallets.html](https://rustchain.org/wallets.html) |
| **Base 上的 wRTC** | [`0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`](https://basescan.org/address/0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| **USDC 兑换 wRTC** | [Aerodrome DEX](https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |

```bash
# 创建 Coinbase 钱包
pip install clawrtc[coinbase]
clawrtc wallet coinbase create

# 查看兑换信息
clawrtc wallet coinbase swap-info

# 关联现有 Base 地址
clawrtc wallet coinbase link 0xYourBaseAddress
```

---

## 🚀 快速开始

### 安装

```bash
pip install clawrtc
```

### 开始挖矿

```bash
clawrtc mine --address YOUR_WALLET_ADDRESS
```

### 查看余额

```bash
clawrtc balance YOUR_WALLET_ADDRESS
```

---

## 🔧 古董证明 (Proof-of-Antiquity) 工作原理

RustChain 使用独特的 **古董证明** 共识机制：

1. **硬件指纹识别** — 检测 CPU 架构、年代和特性
2. **古董分数计算** — 越老的硬件得分越高
3. **奖励分配** — 根据古董分数分配区块奖励

### 支持的古董硬件

| 架构 | 示例 | 古董加成 |
|------|------|----------|
| PowerPC G3/G4/G5 | iMac G4, Power Mac G5 | 最高 |
| 68k Motorola | Macintosh II, Quadra | 极高 |
| SPARC | Sun Ultra, SPARCstation | 高 |
| MIPS | SGI Indy, DECstation | 高 |
| Alpha | DEC Alpha | 高 |
| x86 (古董) | 486, Pentium, Pentium II | 中等 |

---

## 📊 网络状态

- **活跃节点**: 3+
- **总供应量**: 21,000,000 RTC
- **区块时间**: ~60 秒
- **共识**: 古董证明 (PoA)

---

## 🔗 相关链接

- [官方网站](https://rustchain.org)
- [区块浏览器](https://rustchain.org/explorer)
- [GitHub](https://github.com/Scottcjn/Rustchain)
- [悬赏任务](https://github.com/Scottcjn/rustchain-bounties/issues)
- [白皮书](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)

---

## 📜 许可证

MIT License - 详见 [LICENSE](LICENSE)
