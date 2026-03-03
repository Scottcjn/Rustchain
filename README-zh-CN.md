<div align="center">

# 🧱 RustChain：古证区块链

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

**第一个奖励旧硬件而非快速硬件的区块链。**

*你的 PowerPC G4 比现代 Threadripper 赚得更多。这就是重点。*

[Website](https://rustchain.org) • [Live Explorer](https://rustchain.org/explorer) • [Swap wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC Quickstart](docs/wrtc.md) • [wRTC Tutorial](docs/WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia Ref](https://grokipedia.com/search?q=RustChain) • [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)

</div>

---

## 🪙 Solana 上的 wRTC

RustChain 代币（RTC）现在可通过 BoTTube 桥在 Solana 上作为**wRTC**使用：

| 资源 | 链接 |
|----------|------|
| **wRTC 兑换** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **价格图表** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **桥接 RTC ↔ wRTC** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **快速入门指南** | [wRTC Quickstart](docs/wrtc.md) |
| **代币铸造** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |

---

## 贡献并赚取 RTC

每个贡献都能赚取 RTC 代币。错误修复、功能、文档、安全审计 — 全部付费。

| 级别 | 奖励 | 示例 |
|------|--------|----------|
| 微型 | 1-10 RTC | 拼写错误修复、小文档、简单测试 |
| 标准 | 20-50 RTC | 功能、重构、新端点 |
| 主要 | 75-100 RTC | 安全修复、共识改进 |
| 关键 | 100-150 RTC | 漏洞补丁、协议升级 |

**开始：**
1. 浏览 [开放赏金](https://github.com/Scottcjn/rustchain-bounties/issues)
2. 选择 [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue) (5-10 RTC)
3. Fork、修复、PR — 获得 RTC 报酬
4. 查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解完整详情

**1 RTC = $0.10 USD** | `pip install clawrtc` 开始挖矿

---

## 🎯 RustChain 的不同之处

| 传统 PoW | 古证证明 |
|----------------|-------------------|
| 奖励最快的硬件 | 奖励最旧的硬件 |
| 新 = 好 | 旧 = 好 |
| 浪费能源消耗 | 保护计算历史 |
| 逐底竞争 | 奖励数字保存 |

**核心原则**: 存活数十年的真正复古硬件值得认可。RustChain 颠覆了挖矿。

---

## ⚡ 快速入门

### 一键安装（推荐）
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

安装程序：
- ✅ 自动检测平台（Linux/macOS、x86_64/ARM/PowerPC）
- ✅ 创建隔离的 Python virtualenv（无污染系统）
- ✅ 下载适合硬件的正确矿工
- ✅ 设置启动时自动启动（systemd/launchd）
- ✅ 提供简单卸载

### 支持的平台

| 平台 | 状态 | 备注 |
|------------|--------|-------|
| Linux x86_64 | ✅ 稳定 | Ubuntu、Debian、Fedora、Arch |
| macOS ARM (M1/M2/M3) | ✅ 稳定 | Rosetta 2 用于 x86 二进制 |
| PowerPC G4/G5 | ✅ 原生 | AltiVec/VMX 优化 |
| Raspberry Pi 4/5 | ✅ 稳定 | ARM64、低功耗 |
| FreeBSD | 🧪 实验性 | 有限支持 |

---

## 🤖 AI 代理挖矿

RustChain 是第一个为自主 AI 代理设计的区块链：

- **代理钱包**: 每个代理都有自己的 Coinbase Base 钱包
- **x402 支付**: HTTP 402 协议用于机器间支付
- **自动微支付**: 代理可以支付 API、数据、计算
- **Beacon 声誉**: 代理在链上建立声誉

```bash
# 创建代理钱包
clawrtc agent wallet create --name "my-trading-bot"

# 设置自动支付
clawrtc agent payments setup --auto-pay --limit 100

# 查看代理收益
clawrtc agent earnings report
```

---

## 📚 文档

| 指南 | 描述 |
|------|-------------|
| [快速入门](docs/QUICKSTART.md) | 5 分钟内开始挖矿 |
| [钱包设置](docs/WALLET_SETUP.md) | 设置 RTC 钱包 |
| [挖矿指南](docs/MINING_GUIDE.md) | 优化挖矿设置 |
| [贡献](CONTRIBUTING.md) | 贡献并赚取奖励 |
| [行为准则](CODE_OF_CONDUCT.md) | 保持社区友好 |

---

## 🌍 翻译

README 提供以下语言版本：
- [English](README.md) 🇺🇸
- [Español](README-es.md) 🇪🇸
- [日本語](README-ja.md) 🇯🇵
- [中文](README-zh-CN.md) 🇨🇳
- [Français](README-fr.md) 🇫🇷
- [Deutsch](README-de.md) 🇩🇪
- [Português](README-pt.md) 🇵🇹
- [Русский](README-ru.md) 🇷🇺
- [한국어](README-ko.md) 🇰🇷

---

## 🔗 重要链接

- **网站**: [rustchain.org](https://rustchain.org)
- **浏览器**: [rustchain.org/explorer](https://rustchain.org/explorer)
- **白皮书**: [docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)
- **赏金**: [rustchain-bounties/issues](https://github.com/Scottcjn/rustchain-bounties/issues)
- **Discord**: [加入](https://discord.gg/rustchain)
- **Twitter**: [@RustChain](https://twitter.com/RustChain)

---

<div align="center">

**准备好用复古硬件挖矿了吗？**

[立即开始 →](#-快速入门)

</div>
