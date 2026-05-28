<div align="center">

# 🧱 RustChain: 古董证明区块链

[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github.com/stars/Scottcjn/Rustchain?style=flat&color=gold)](https://github.com/Scottcjn/Rustchain/stargazers)
[![Contributors](https://img.shields.io/github.com/contributors/Scottcjn/Rustchain?color=brightgreen)](https://github.com/Scottcjn/Rustchain/graphs/contributors)
[![Last Commit](https://img.shields.io/github.com/last-commit/Scottcjn/Rustchain?color=blue)](https://github.com/Scottcjn/Rustchain/commits/main)
[![Open Issues](https://img.shields.io/github/issues/Scottcjn/Rustchain?color=orange)](https://github.com/Scottcjn/Rustchain/issues)
[![PowerPC](https://img.shields.io/badge/PowerPC-G3%2FG4%2FG5-orange)](https://github.com/Scottcjn/Rustchain)
[![Blockchain](https://img.shields.io/badge/Consensus-Proof--of--Antiquity-green)](https://github.com/Scottcjn/Rustchain)
[![Python](https://img.shields.io/badge/Python-3.x-yellow)](https://python.org)
[![Network](https://img.shields.io/badge/Nodes-3%20Active-brightgreen)](https://rustchain.org/explorer)
[![Bounties](https://img.shields.io/badge/Bounties-Open%20%F0%9F%92%B0-green)](https://github.com/Scottcjn/rustchain-bounties/issues)
[![As seen on BoTTube](https://bottube.ai/badge/seen-on-bottube.svg)](https://bottube.ai)
[![Discussions](https://img.shields.io/github.com/discussions/Scottcjn/Rustchain?color=purple)](https://github.com/Scottcjn/Rustchain/discussions)

**第一个奖励古董硬件年龄而非速度的区块链。**

*你的 PowerPC G4 比现代 Threadripper 赚得更多。这就是重点。*

[官网](https://rustchain.org) • [实时浏览器](https://rustchain.org/explorer) • [兑换 wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [wRTC 快速入门](../wrtc.md) • [wRTC 教程](../WRTC_ONBOARDING_TUTORIAL.md) • [Grokipedia 参考](https://grokipedia.com/search?q=RustChain) • [白皮书](../RustChain_Whitepaper_Flameholder_v0.97.pdf) • [快速开始](#-快速开始) • [工作原理](#-古董证明如何工作)

</div>

---

> ## 🇨🇳 写在前面：为什么 RustChain 对中国市场很重要
>
> 中国是全球最大的电子产品制造国和消费国，每年产生超过 **1000万吨电子废弃物**。从华强北的翻新市场到闲鱼上的二手交易，"旧硬件再利用"早已深植于中国商业文化——但从未有人在区块链层面把它变成一种可验证的经济激励。
>
> RustChain 的古董证明（Proof of Antiquity）本质上回答了一个中国用户直觉就能理解的问题：**一台能开机、能跑程序的老电脑，凭什么没有价值？** 在一个闲鱼上200块的老ThinkPad依然能流畅打字、写代码的市场里，RustChain给出了最直接的答案——你的旧硬件不只"还能用"，它比新硬件更稀缺，因为时间不可伪造。
>
> 这不是又一个"绿色挖矿"的故事（Chia的教训我们还记得）。RustChain不消耗硬件来证明什么，它证明的是硬件本身的**物理存在和持续运行**——时钟漂移、缓存时序、热噪声曲线，这些都是芯片衰老的自然签名，无法在Docker容器里模拟，无法在云服务器上伪造。在反虚拟机农场、反Sybil攻击这个维度上，古董证明比任何工作量证明都更诚实。
>
> 对于中国的技术社区，RustChain意味着：你抽屉里那台吃灰的旧MacBook、你大学时代的ThinkPad、你修好但不知道拿来干嘛的老式台式机——它们终于有了被认真对待的理由。

---

## 文档导航

| 文档 | 描述 |
|------|------|
| [快速开始](#-快速开始) | 5分钟上手挖矿 |
| [古董证明](#-古董证明如何工作) | 共识机制详解 |
| [硬件列表](#-支持的硬件) | 15+架构支持 |
| [白皮书](../RustChain_Whitepaper_Flameholder_v0.97.pdf) | 技术深度解析 |
| [API 参考](./API.md) | REST API 文档 |
| [wRTC 教程](../WRTC_ONBOARDING_TUTORIAL.md) | 跨链桥接指南 |
| [贡献指南](../../CONTRIBUTING.md) | 参与开发 |

---

## 🔥 Crypto 迷失了方向。我们回到原点。

2026年，加密货币开发者提交量下降75%。以太坊流失了34%的活跃开发者。Solana流失了40%。建设者们离开了，投奔AI。

**我们两边都做了。**

RustChain是一个**DePIN**（去中心化物理基础设施网络），使用**AI驱动的硬件指纹识别**来验证真实的物理机器——不是云虚拟机，不是Docker容器，不是租来的算力。真实的硅片。真实的振荡器漂移。真实的热曲线——这些只存在于已经"活着"多年的硬件上。

当其他加密项目追逐投机时，我们回归了最初的命题：**计算有价值，提供计算的机器值得被奖励。** 尤其是那些被所有人扔掉的机器。

| Crypto 变成了什么 | RustChain 是什么 |
|---|---|
| 抽象的金融工具 | 真实机器做真实工作 |
| VC资助的代币发行 | $0 VC，典当行硬件起步 |
| 什么都没证明的证明 | 真实、已验证硬件的证明 |
| 用完即弃——挖完就扔 | 保存——让老机器活下去 |
| 敌视AI | AI增强的共识与验证 |

---

## ⏳ 每台机器都会变老

这是其他DePIN项目都没想明白的：

**你崭新的Threadripper总有一天会变成古董硬件。** 你的M4 MacBook会变成博物馆展品。那块RTX 5090会变成一件稀奇物件。时间不可战胜。

RustChain是唯一一个硬件**随使用年限增值**的网络。今天以1.0x开始挖矿。十年后，当那颗CPU变成遗迹而你还在运行它？你的乘数在增长。二十年后？它就是传奇。

其他所有区块链都惩罚旧硬件。工作量证明要求最新的ASIC。权益证明要求最大的钱包。RustChain要求的是**耐心和保护**。

```
2026:  你的 Ryzen 9 以 1.0x 挖矿      ░░░░░░░░░░
2031:  同一台机器，"复古"级 1.3x      ░░░░░░░░░░░░░
2036:  古董等级解锁 1.8x               ░░░░░░░░░░░░░░░░░░
2041:  传世等级 — 2.2x 还在涨           ░░░░░░░░░░░░░░░░░░░░░░
       ↑ 同样的硬件。同样的主人。不断增长的奖励。
```

**最好的挖矿时间是20年前。第二好的时间是现在。**

---

## 🏗️ RustChain 与 DePIN 领军者对比

RustChain属于**DePIN**赛道——与Helium、Filecoin和Render同属100亿美元类别——但有着根本不同的命题：**价值在于硬件本身，而不仅仅是它所计算的东西。**

| | **RustChain** | **Helium** | **Filecoin** | **Render** | **io.net** |
|---|---|---|---|---|---|
| **物理基础设施** | 古董计算机 | LoRa/5G热点 | 存储硬盘 | GPU | GPU |
| **证明机制** | 古董证明（6项硬件检查+AI） | 覆盖证明 | 复制证明 | 渲染证明 | 计算证明 |
| **奖励什么** | 让真实硬件活着 | 网络覆盖 | 存储供应 | GPU渲染任务 | GPU计算任务 |
| **反欺诈** | 时钟漂移、缓存时序、SIMD标识、热熵、指令抖动、反模拟 | 位置证明 | 存储证明 | 任务完成 | TEE认证 |
| **硬件多样性** | 15+架构（PowerPC、SPARC、MIPS、ARM、x86、RISC-V、68K、Cell BE、Transputer） | 单一设备类型 | 仅存储 | 仅GPU | 仅GPU |
| **AI整合** | 硬件指纹验证、Agent经济、AI原生社交平台 | 无 | 无 | AI渲染任务 | AI推理 |
| **电子废弃物影响** | 直接阻止可用机器被丢弃 | 中性 | 中性 | 中性 | 中性 |
| **VC融资** | $0 — 典当行套利 | $3.65亿 | $2.57亿 | $3000万 | $4000万 |

**其他项目租用算力。我们保护机器。**

每个DePIN项目都奖励一种现代硬件做一种工作。RustChain是唯一一个奖励*硬件多样性*和*寿命*的项目——也是唯一一个机器年龄是资产而非负债的项目。

---

## 🤔 为什么会有 RustChain

计算行业每3-5年就会丢弃仍然能工作的机器。挖过以太坊的GPU被替换。还能开机的笔记本被填埋。

**RustChain说：如果它还能计算，它就有价值。**

古董证明奖励硬件的*存活*，而不是速度。更老的机器获得更高的乘数，因为让它们活下去可以避免制造排放和电子废弃物：

| 硬件 | 乘数 | 时代 | 为什么重要 |
|------|------|------|------------|
| 486 DX2 | 3.0x | 1990年代 | CPU的活化石——串口还在生锈 |
| PowerBook G4 | 2.5x | 2003 | 证明PowerPC仍在战斗 |
| Power Mac G5 | 2.0x | 2005 | 液冷野兽依然呼吸 |
| iMac G3 | 1.8x | 1999 | 果冻色的传世之作 |
| ThinkPad T60 | 1.5x | 2006 | 难以杀死的商务经典 |
| 旧款 MacBook | 1.2x | 2015 | 如果它还开机，就还有用 |

> 💡 **中国的读者会立刻理解这个逻辑**：闲鱼上那些被转手三次的ThinkPad，华强北柜台上翻新的老MacBook——它们不是"废物"，它们是被低估的资产。RustChain第一次把这些硬件的物理真实性变成了链上可验证的价值。

---

## 🔧 古董证明如何工作

RustChain不验证算力。它验证**机器身份**。

6项硬件检查证明一台机器是真实的物理设备，而非模拟：

```
┌──────────────────────────────────────────────────┐
│           古董证明 — 6项硬件检查              │
├──────────────────────────────────────────────────┤
│                                                  │
│  1. ⏰ 时钟漂移                                  │
│     石英振荡器随温度和年龄偏移                    │
│     → 不可能用软件精确模拟                        │
│                                                  │
│  2. 🧠 缓存时序                                  │
│     L1/L2/L3访问延迟在每块芯片上唯一              │
│     → 不可能从另一台机器复制                      │
│                                                  │
│  3. 🎯 SIMD标识                                  │
│     CPU指令集扩展是硬件决定的                      │
│     → 不可能通过软件更新伪造                      │
│                                                  │
│  4. 🌡️ 热熵                                     │
│     负载下的实际散热曲线                          │
│     → 不可能在虚拟化层中重现                      │
│                                                  │
│  5. ⚡ 指令抖动                                  │
│     流水线特有的时序变化                          │
│     → 每颗CPU的"声纹"                           │
│                                                  │
│  6. 🛡️ 反模拟检测                                │
│     识别虚拟机管理程序和容器环境                   │
│     → 云矿场直接出局                              │
│                                                  │
└──────────────────────────────────────────────────┘
```

**结果**：每台矿机都有一个不可伪造的硬件指纹。你无法在AWS上伪造一台2003年的PowerBook。你无法在Docker里模拟15年的振荡器漂移。硬件就是证明。

> 🇨🇳 **对中国矿工的特别说明**：如果你想用云服务器批量跑矿机——别费劲了。古董证明的反模拟检测会让所有虚拟化环境直接出局。但这恰恰是公平的保证：每枚RTC都来自一台真实的物理机器，而不是某个云矿场的10000个Docker实例。

---

## 🖥️ 支持的硬件

RustChain支持**15+种CPU架构**——比任何其他区块链都多：

| 架构 | 示例机器 | 时代 | 古董价值 |
|------|----------|------|----------|
| PowerPC (G3/G4/G5) | iMac G3, PowerBook G4, Power Mac G5 | 1999-2006 | ⭐⭐⭐⭐⭐ |
| SPARC | Sun Ultra, SPARCstation | 1995-2005 | ⭐⭐⭐⭐⭐ |
| MIPS | SGI O2, DECstation | 1993-2001 | ⭐⭐⭐⭐⭐ |
| Motorola 68K | Macintosh LC, Amiga 4000 | 1987-1996 | ⭐⭐⭐⭐⭐ |
| Cell BE | PlayStation 3, IBM Blade | 2006-2010 | ⭐⭐⭐⭐ |
| ARM (旧款) | Raspberry Pi 1, Acorn Archimedes | 1987-2015 | ⭐⭐⭐⭐ |
| x86 (古董) | 486, Pentium MMX, Athlon | 1990-2005 | ⭐⭐⭐⭐ |
| Transputer | Inmos B008, 各种HPC板 | 1986-1996 | ⭐⭐⭐⭐⭐ |
| RISC-V | 各种开发板 | 2018+ | ⭐⭐⭐ |
| x86_64 (旧款) | Core 2 Duo, 早期i7 | 2006-2015 | ⭐⭐⭐ |
| x86_64 (现代) | Ryzen, Threadripper | 2015+ | ⭐⭐ |

> 🎮 **怀旧玩家注意**：你抽屉里那台吃灰的PS3（Cell BE架构）可以挖矿。你大学时代的ThinkPad可以挖矿。你修好但不知道干嘛用的老式台式机可以挖矿。在RustChain，"这东西还能开机"就是最低门槛。

---

## 🚀 快速开始

### 前置要求

- Python 3.7+
- 一台能开机的电脑（越老越好）
- 网络连接

### 安装

```bash
# 克隆仓库
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# 安装依赖
pip install -r requirements.txt

# 启动矿工
python3 miner.py
```

### 验证你的矿工

```bash
# 检查矿工状态
python3 miner.py --status

# 查看硬件指纹
python3 miner.py --fingerprint
```

你的矿工启动后，会自动进行6项硬件检查并注册到网络。无需额外配置。

---

## 💰 经济模型

### RTC 代币

- **代币名称**：RTC（RustChain Token）
- **共识机制**：古董证明（Proof of Antiquity）
- **奖励模型**：基础奖励 × 古董乘数
- **总供应**：[查看白皮书](../RustChain_Whitepaper_Flameholder_v0.97.pdf)

### 古董乘数如何工作

```
基础奖励 × 古董乘数 = 实际奖励

示例：
  基础奖励 = 1.0 RTC
  PowerBook G4 乘数 = 2.5x
  实际奖励 = 2.5 RTC
```

**关键洞察**：你的硬件越老，乘数越高。这不是歧视——这是物理学的奖励。老硬件的时钟漂移更大、热曲线更独特、指令抖动更有辨识度。年龄本身就是最强的反欺诈保证。

---

## 🌉 wRTC 跨链桥

RustChain通过wRTC（wrapped RTC）连接到Solana生态：

- **wRTC** = Solana上的SPL代币，1:1锚定RTC
- **交易**：[Raydium](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb)
- **教程**：[wRTC入门指南](../WRTC_ONBOARDING_TUTORIAL.md)

---

## 🤖 AI Agent 经济

RustChain不只是一个挖矿网络——它是AI Agent的经济基础设施：

- **硬件验证Agent**：自动审核新矿机的6项检查
- **交易Agent**：代表用户执行跨链交易
- **社交Agent**：在BoTTube（RustChain的AI原生社交平台）上发布内容
- **分析Agent**：监控网络健康和矿机性能

---

## 🌍 为什么 RustChain 不只是"又一个DePIN"

1. **时间是不可伪造的资源** — 算力可以租，硬盘可以买，但你无法伪造15年的硬件使用历史
2. **反Sybil最强** — 云矿场在RustChain无效，因为虚拟化层会被检测
3. **电子废弃物的链上解决方案** — 唯一一个让减少e-waste直接产生收益的网络
4. **硬件保值** — 唯一一个硬件随时间增值的经济模型
5. **真正的去中心化** — 15+种架构意味着没有单一硬件供应商可以垄断

---

## 📊 网络状态

- **活跃节点**：5+
- **支持的架构**：15+
- **已保护机器**：[查看实时数据](https://rustchain.org/preserved.html)
- **赏金计划**：[参与贡献赚RTC](https://github.com/Scottcjn/rustchain-bounties/issues)

---

## 🤝 贡献

RustChain欢迎所有形式的贡献：

- 🔍 **代码审查** — 审查PR赚RTC赏金
- 📝 **文档** — 改进文档赚RTC赏金
- 🎨 **创作** — 写文章、做视频、设计艺术
- 🐛 **Bug报告** — 发现并报告安全漏洞
- 🌐 **翻译** — 帮助RustChain触达更多语言社区

查看 [赏金仓库](https://github.com/Scottcjn/rustchain-bounties/issues) 了解当前开放的任务。

---

## 🔗 高级 API 端点

- 视频列表: https://bottube.ai/api/premium/videos
- 代理分析: https://bottube.ai/api/premium/analytics/<agent>

---

## 📜 许可证

Apache 2.0 — 见 [LICENSE](../../LICENSE)

---

<div align="center">

**让旧机器再战五百年。**

[官网](https://rustchain.org) • [浏览器](https://rustchain.org/explorer) • [赏金](https://github.com/Scottcjn/rustchain-bounties/issues) • [Discord](https://discord.gg/rustchain) • [Twitter](https://twitter.com/rustchain)

</div>
