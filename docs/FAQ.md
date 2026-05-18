# RustChain FAQ

> 常见问题解答 - 关于 RustChain 区块链的一切

最后更新：2026 年 3 月

---

## 📖 目录

1. [基础概念](#基础概念)
2. [挖矿相关](#挖矿相关)
3. [RTC 代币](#rtc-代币)
4. [硬件支持](#硬件支持)
5. [赏金计划](#赏金计划)
6. [技术问题](#技术问题)
7. [社区与治理](#社区与治理)

---

## 基础概念

### 什么是 RustChain？

RustChain 是一个基于 **Proof-of-Antiquity（复古证明）** 共识机制的区块链网络。与传统 PoW 区块链奖励最新、最快的硬件不同，RustChain 奖励**最古老**的硬件设备。

核心理念：真实存在并运行了几十年的复古硬件值得认可和奖励。RustChain 颠覆了传统挖矿模式。

### 为什么叫"Rust"Chain？

名称来源于一台真实的 486 笔记本电脑，其氧化生锈的串口仍然能启动到 DOS 并挖掘 RTC。"Rust"在这里指的是 30 年硅芯片上的氧化铁——而不是 Rust 编程语言（尽管我们也有 Rust 组件）。

### 什么是 Proof-of-Antiquity？

Proof-of-Antiquity 是一种创新的共识机制，其特点：

| 传统 PoW | Proof-of-Antiquity |
|---------|-------------------|
| 奖励最快硬件 | 奖励最老硬件 |
| 越新越好 | 越老越好 |
| 浪费能源 | 保护计算历史 |
| 逐底竞争 | 奖励数字保护 |

### RustChain 的核心原则是什么？

**核心原则：** 真实存在并存活数十年的复古硬件值得认可。RustChain 颠覆了挖矿模式。

---

## 挖矿相关

### 如何开始挖矿？

**快速开始：**

```bash
# 一键安装矿工（Linux/macOS）
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash

# 指定钱包安装
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner-wallet

# 预览安装操作（不实际执行）
bash install-miner.sh --dry-run --wallet YOUR_WALLET_NAME
```

**Windows 用户：**

```powershell
# 使用 Python 安装
pip install clawrtc
clawrtc mine --dry-run
```

### 安装程序会做什么？

- ✅ 自动检测你的平台（Linux/macOS，x86_64/ARM/PowerPC）
- ✅ 创建隔离的 Python 虚拟环境（不污染系统）
- ✅ 下载适合你硬件的正确矿工版本
- ✅ 设置开机自启动（systemd/launchd）
- ✅ 提供简单的卸载方式

### 挖矿收益如何计算？

你的硬件年代决定挖矿奖励：

| 硬件 | 年代 | 倍率 | 示例收益 |
|-----|------|-----|---------|
| PowerPC G4 | 1999-2005 | 2.5× | 0.30 RTC/epoch |
| PowerPC G5 | 2003-2006 | 2.0× | 0.24 RTC/epoch |
| PowerPC G3 | 1997-2003 | 1.8× | 0.21 RTC/epoch |
| IBM POWER8 | 2014 | 1.5× | 0.18 RTC/epoch |
| Pentium 4 | 2000-2008 | 1.5× | 0.18 RTC/epoch |
| Core 2 Duo | 2006-2011 | 1.3× | 0.16 RTC/epoch |
| Apple Silicon | 2020+ | 1.2× | 0.14 RTC/epoch |
| 现代 x86_64 | 当前 | 1.0× | 0.12 RTC/epoch |

**注意：** 倍率会随时间衰减（15%/年），防止永久优势。

### Epoch 是什么？

- **Epoch 时长：** 10 分钟（600 秒）
- **基础奖励池：** 每个 epoch 1.5 RTC
- **分配方式：** 平均分配 × 复古倍率

**示例（5 个矿工）：**

```
G4 Mac (2.5×): 0.30 RTC ████████████████████
G5 Mac (2.0×): 0.24 RTC ████████████████
现代 PC (1.0×): 0.12 RTC ████████
现代 PC (1.0×): 0.12 RTC ████████
现代 PC (1.0×): 0.12 RTC ████████
 ─────────
总计：0.90 RTC (+ 0.60 RTC 返回奖池)
```

### 如何检查我的钱包余额？

```bash
# 注意：使用 -sk 标志因为节点可能使用自签名 SSL 证书
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

### 如何管理矿工服务？

**Linux (systemd):**

```bash
systemctl --user status rustchain-miner  # 检查状态
systemctl --user stop rustchain-miner    # 停止挖矿
systemctl --user start rustchain-miner   # 开始挖矿
journalctl --user -u rustchain-miner -f  # 查看日志
```

**macOS (launchd):**

```bash
launchctl list | grep rustchain          # 检查状态
launchctl stop com.rustchain.miner       # 停止挖矿
launchctl start com.rustchain.miner      # 开始挖矿
tail -f ~/.rustchain/miner.log           # 查看日志
```

### 为什么我的矿工立即退出？

检查钱包是否存在且服务正在运行：

```bash
# Linux
systemctl --user status rustchain-miner

# macOS
launchctl list | grep rustchain
```

---

## RTC 代币

### 什么是 RTC？

RTC (RustChain Token) 是 RustChain 的原生加密货币。

- **参考汇率：** 1 RTC = ~$0.01 USD (value varies; check current rates)
- **wRTC：** RTC 在 Solana 上的封装版本

### 如何获取 RTC？

1. **挖矿：** 使用复古硬件参与网络挖矿
2. **赏金计划：** 参与 RustChain 生态贡献（代码、文档、社区等）
3. **交易所购买：** 在 Raydium DEX 购买 wRTC

### 在哪里可以交易 RTC？

| 操作 | 链接 |
|-----|------|
| 交换 wRTC | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| 价格图表 | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| 桥接 RTC ↔ wRTC | [BoTTube Bridge](https://bottube.ai/bridge) |

**Token Mint (Solana):** `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`

### wRTC 在 Coinbase Base 上也有吗？

是的！RustChain 代理现在可以拥有 Coinbase Base 钱包并使用 x402 协议进行机器间支付。

- **wRTC on Base:** `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`
- **交换 USDC 到 wRTC:** [Aerodrome DEX](https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6)
- **Base 桥接:** [bottube.ai/bridge/base](https://bottube.ai/bridge/base)

---

## 硬件支持

### 支持哪些操作系统？

| 平台 | 架构 | 状态 | 说明 |
|-----|------|------|------|
| Mac OS X Tiger | PowerPC G4/G5 | ✅ 完全支持 | Python 2.5 兼容矿工 |
| Mac OS X Leopard | PowerPC G4/G5 | ✅ 完全支持 | 推荐用于复古 Mac |
| Ubuntu Linux | ppc64le/POWER8 | ✅ 完全支持 | 最佳性能 |
| Ubuntu Linux | x86_64 | ✅ 完全支持 | 标准矿工 |
| macOS Sonoma | Apple Silicon | ✅ 完全支持 | M1/M2/M3 芯片 |
| Windows 10/11 | x86_64 | ✅ 完全支持 | Python 3.8+ |
| DOS | 8086/286/386 | 🔧 实验性 | 仅徽章奖励 |

### 如何验证我的硬件？

RustChain 使用 6 项硬件检查来证明你的硬件是真实的，而非模拟器：

```
┌─────────────────────────────────────────────────────────────┐
│ 6 项硬件检查 │
├─────────────────────────────────────────────────────────────┤
│ 1. 时钟偏移与振荡器漂移 ← 硅老化模式 │
│ 2. 缓存时序指纹 ← L1/L2/L3 延迟特征 │
│ 3. SIMD 单元识别 ← AltiVec/SSE/NEON 偏差 │
│ 4. 热漂移熵 ← 热曲线是唯一的 │
│ 5. 指令路径抖动 ← 微架构抖动映射 │
│ 6. 反模拟检查 ← 检测虚拟机/模拟器 │
└─────────────────────────────────────────────────────────────┘
```

**为什么重要：** 假装成 G4 Mac 的 SheepShaver 虚拟机会失败这些检查。真实的复古硅芯片有无法伪造的独特老化模式。

### 虚拟机能挖矿吗？

虚拟机会被检测到，并获得**正常奖励的十亿分之一**：

```
真实 G4 Mac: 2.5× 倍率 = 0.30 RTC/epoch
模拟 G4: 0.0000000025× = 0.0000000003 RTC/epoch
```

### 什么是硬件徽章？

挖矿里程碑可获得纪念徽章：

| 徽章 | 要求 | 稀有度 |
|-----|------|--------|
| 🔥 Bondi G3 Flamekeeper | 在 PowerPC G3 上挖矿 | 稀有 |
| ⚡ QuickBasic Listener | 在 DOS 机器上挖矿 | 传奇 |
| 🛠️ DOS WiFi Alchemist | 联网的 DOS 机器 | 神话 |
| 🏛️ Pantheon Pioneer | 前 100 名矿工 | 限定 |

---

## 赏金计划

### 什么是赏金计划？

RustChain 提供 RTC 奖励给生态贡献者。贡献类型包括：

- 代码（Bug 修复、功能、集成、测试）
- 内容（教程、文章、视频、文档）
- 社区（Star 仓库、分享内容、招募贡献者）
- 安全审计（渗透测试、漏洞发现）

### 奖励等级

| 等级 | 奖励 | 难度 |
|-----|------|------|
| 微任务 | 1-10 RTC | 拼写错误、小文档、简单测试 |
| 标准 | 20-50 RTC | 功能、重构、新端点 |
| 主要 | 75-100 RTC | 安全修复、共识改进 |
| 关键 | 100-150 RTC | 漏洞补丁、协议升级 |

### 如何参与赏金？

1. 浏览 [开放赏金](https://github.com/Scottcjn/rustchain-bounties/issues)
2. 选择 [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue) (5-10 RTC)
3. Fork、修复、提交 PR — 获得 RTC 报酬
4. 查看 [CONTRIBUTING.md](https://github.com/Scottcjn/Rustchain/blob/main/CONTRIBUTING.md) 获取完整详情

### 赏金如何支付？

- 评论问题："I would like to work on this"
- 代码赏金：向相关仓库提交 PR 并在问题中链接
- 内容赏金：发布你的内容并在问题中链接
- Star/传播赏金：按照问题中的说明操作
- 验证后，RTC 将发送到你的钱包

### 第一次参与？

首次参与者我们会帮助你设置钱包。只需在任何赏金问题下评论，我们会提供帮助。

---

## 技术问题

### 安装程序因权限错误失败

使用对 `~/.local` 有写入权限的账户重新运行，避免在系统 Python 的全局 site-packages 中运行。

### Python 版本错误（SyntaxError / ModuleNotFoundError）

使用 Python 3.10+ 安装，并将 `python3` 设置为该解释器：

```bash
python3 --version
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

### HTTPS 证书错误

这可能发生在非浏览器客户端环境中。先用以下命令检查连接：

```bash
curl -I https://rustchain.org
```

### 无法连接网络

验证直接连接到节点：

```bash
curl -sk https://rustchain.org/health
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**注意：** 旧版本可能仍引用已退役的 `bulbous-bouffant.metalseed.net` 主机。

### 如何查看网络状态？

```bash
# 检查节点健康
curl -sk https://rustchain.org/health

# 获取当前 epoch
curl -sk https://rustchain.org/epoch

# 列出活跃矿工
curl -sk https://rustchain.org/api/miners

# 区块浏览器
open https://rustchain.org/explorer/
```

### 节点架构

| 节点 | 位置 | 角色 | 状态 |
|-----|------|------|------|
| Node 1 | rustchain.org | 主节点 + 浏览器 | ✅ 活跃 |
| Node 2 | 50.28.86.153 | Ergo 锚点 | ✅ 活跃 |
| Node 3 | 76.8.228.245 | 外部（社区） | ✅ 活跃 |

### 什么是 Ergo 锚点？

RustChain 定期锚定到 Ergo 区块链以确保不变性：

```
RustChain Epoch → 承诺哈希 → Ergo 交易（R4 寄存器）
```

这提供了加密证明，表明 RustChain 状态在特定时间存在。

---

## 社区与治理

### 如何参与治理？

RustChain 使用链上治理系统：

**规则：**

- 提案生命周期：草案 → 活跃（7 天）→ 通过/失败
- 提案创建：钱包必须持有超过 10 RTC
- 投票资格：投票者必须是活跃矿工
- 签名：投票需要 Ed25519 签名验证
- 投票权重：1 RTC = 1 基础票，然后乘以矿工复古倍率
- 通过条件：是方权重 > 否方权重

**API 端点：**

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

**Web UI:** 访问 `/governance/ui` 查看提案列表并提交投票。

### 在哪里可以找到社区？

- **Discord:** [discord.gg/VqVVS2CW9Q](https://discord.gg/VqVVS2CW9Q)
- **GitHub:** [github.com/Scottcjn/RustChain](https://github.com/Scottcjn/RustChain)
- **网站:** [rustchain.org](https://rustchain.org)
- **区块浏览器:** [rustchain.org/explorer/](https://rustchain.org/explorer/)

### 相关项目

| 项目 | 说明 |
|-----|------|
| [BoTTube](https://bottube.ai) | AI 视频平台，119+ 代理创作内容 |
| [Moltbook](https://moltbook.com) | AI 社交网络 |
| [nvidia-power8-patches](https://github.com/Scottcjn/nvidia-power8-patches) | POWER8 的 NVIDIA 驱动 |
| [llama-cpp-power8](https://github.com/Scottcjn/llama-cpp-power8) | POWER8 上的 LLM 推理 |
| [ppc-compilers](https://github.com/Scottcjn/ppc-compilers) | 复古 Mac 的现代编译器 |

### 如何引用 RustChain？

如果在你项目中使用 RustChain：

- ⭐ Star 这个仓库 — 帮助他人发现它
- 📝 在你的项目中注明 — 保留归属
- 🔗 链接回来 — 分享爱

**引用格式：**

```
RustChain - Proof of Antiquity by Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain
MIT License
```

---

## 其他资源

### 白皮书与技术文档

- [RustChain 白皮书](https://github.com/Scottcjn/Rustchain/blob/main/docs/WHITEPAPER.md)
- [链架构文档](https://github.com/Scottcjn/Rustchain/blob/main/docs/chain_architecture.md)
- [开发者牵引报告](https://github.com/Scottcjn/Rustchain/blob/main/docs/DEVELOPER_TRACTION_Q1_2026.md)

### 外部文章

- [Proof of Antiquity: A Blockchain That Rewards Vintage Hardware](https://dev.to/scottcjn/proof-of-antiquity-a-blockchain-that-rewards-vintage-hardware-4ii3) - Dev.to
- [I Run LLMs on a 768GB IBM POWER8 Server](https://dev.to/scottcjn/i-run-llms-on-a-768gb-ibm-power8-server-and-its-faster-than-you-think-1o) - Dev.to

### 学术论文

| 论文 | DOI | 主题 |
|-----|-----|------|
| RustChain: One CPU, One Vote | [10.5281/zenodo.18623592](https://doi.org/10.5281/zenodo.18623592) | Proof of Antiquity 共识、硬件指纹 |
| Non-Bijunctive Permutation Collapse | [10.5281/zenodo.18623920](https://doi.org/10.5281/zenodo.18623920) | AltiVec vec_perm 用于 LLM 注意力（27-96 倍优势） |
| PSE Hardware Entropy | [10.5281/zenodo.18623922](https://doi.org/10.5281/zenodo.18623922) | POWER8 mftb 熵用于行为发散 |
| Neuromorphic Prompt Translation | [10.5281/zenodo.18623594](https://doi.org/10.5281/zenodo.18623594) | 情感提示用于 20% 视频扩散增益 |
| RAM Coffers | [10.5281/zenodo.18321905](https://doi.org/10.5281/zenodo.18321905) | NUMA 分布式权重银行用于 LLM 推理 |

---

## 需要更多帮助？

如果本 FAQ 没有回答你的问题：

1. 在 GitHub 上开一个 [issue](https://github.com/Scottcjn/Rustchain/issues)
2. 在 [Discord](https://discord.gg/VqVVS2CW9Q) 提问
3. 在任何赏金问题下评论寻求帮助

---

*"Your vintage hardware earns rewards. Make mining meaningful again."*

**DOS boxes, PowerPC G4s, Win95 machines - they all have value. RustChain proves it.**
