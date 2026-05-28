<div align="center">

# 🧱 RustChain: 古董证明区块链

### DePIN 古董硬件网络 — AI 增强的真实机器证明

**一个让旧硬件比新硬件赚得更多的区块链。**
**而所有硬件都会变老，只是时间问题。**

[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/Scottcjn/Rustchain?style=flat&color=gold)](https://github.com/Scottcjn/Rustchain/stargazers)
[![Nodes](https://img.shields.io/badge/Nodes-5%20Active-brightgreen)](https://rustchain.org/explorer/)
[![DePIN](https://img.shields.io/badge/DePIN-Vintage%20Hardware-8B4513)](https://rustchain.org)
[![Proof of Antiquity](https://img.shields.io/badge/Consensus-Proof%20of%20Antiquity-DAA520)](docs/WHITEPAPER.md)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.19442753-blue)](https://doi.org/10.5281/zenodo.19442753)

**第一个奖励古董硬件年龄而非速度的区块链。**

*你的 PowerPC G4 比现代 Threadripper 赚得多 2.5 倍。这就是重点。*

[官网](https://rustchain.org) · [实时浏览器](https://rustchain.org/explorer/) · [安装矿工](#-快速开始) · [快速开始](QUICKSTART.md) · [宣言](https://rustchain.org/manifesto.html) · [白皮书](WHITEPAPER.md)

</div>

---

> ## 🇨🇳 写在前面：为什么 RustChain 对中国市场至关重要
>
> **中国是全球最大的电子产品制造国和消费国，也是最大的电子废弃物产生地。** 全球每年产生约 5000 万吨电子废弃物，其中中国贡献了超过 1000 万吨。从深圳华强北的二手硬件市场，到闲鱼上日均数以万计的旧电脑交易——"旧硬件再利用"已经深深扎根于中国的商业文化中，但从未有人从区块链层面将这种文化直觉转化为**可验证的经济激励**。
>
> RustChain 的古董证明（Proof of Antiquity）本质上回答了一个中国用户凭直觉就能理解的问题：**一台还能开机、能跑程序的老电脑，凭什么没有价值？** 在闲鱼上 200 块的老 ThinkPad 依然能流畅打字写代码的市场里，华强北柜台上一排排翻新 MacBook 的背后，RustChain 给出了最直接的答案——你的旧硬件不只"还能用"，它比新硬件更**稀缺**，因为时间不可伪造。
>
> **这不只是"绿色挖矿"的故事。** Chia 的教训我们都还记得——它用 SSD 做 Proof of Space，结果摧毁了无数固态硬盘。RustChain 不消耗硬件来证明什么，它证明的是硬件本身的**物理存在和持续运行**：时钟漂移、缓存时序、热噪声曲线——这些都是芯片衰老的自然签名，无法在 Docker 容器里模拟，无法在云服务器上伪造。在反虚拟机农场、反 Sybil 攻击这个维度上，古董证明比任何工作量证明都更诚实。
>
> 对于中国的技术社区，RustChain 意味着一个全新的叙事：**闲置硬件不是负担，而是资产。** 你抽屉里吃灰的旧 MacBook、大学时代的 ThinkPad、修好但不知道拿来干嘛的老式台式机——它们终于有了被认真对待的理由。在一个电子制造业和回收生态系统都是全球规模最大的市场里，RustChain 把"反电子废弃物"从道德选择变成了经济激励。
>
> **每台机器都会变老。** 在中国这个全球最大的二手硬件交易市场中，这个事实不是威胁——是机遇。

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

RustChain是**唯一一个硬件随使用年限增值**的网络。今天以1.0x开始挖矿。十年后，当那颗CPU变成遗迹而你还在运行它？你的乘数在增长。二十年后？它就是传奇。

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
|----------|-----------|-----|----------------|
| DEC VAX-11/780 (1977) | **3.5x** | 神话级 | "Shall we play a game?" |
| Acorn ARM2 (1987) | **4.0x** | 神话级 | ARM 的起点 |
| Inmos Transputer (1984) | **3.5x** | 神话级 | 并行计算的先驱 |
| Motorola 68000 (1979) | **3.0x** | 传奇级 | Amiga、Atari ST、经典 Mac |
| Sun SPARC (1987) | **2.9x** | 传奇级 | 工作站的王者 |
| SGI MIPS R4000 (1991) | **2.7x** | 传奇级 | 64位时代的先行者 |
| PS3 Cell BE (2006) | **2.2x** | 远古级 | 7个SPE核心的传奇 |
| PowerPC G4 (2003) | **2.5x** | 远古级 | 仍在运行，仍在赚取奖励 |
| RISC-V (2014) | **1.4x** | 异国情调 | 开放ISA，未来 |
| Apple Silicon M1 (2020) | **1.2x** | 现代 | 高效，欢迎加入 |
| 现代 x86_64 | **1.0x** | 现代 | 基准线——*暂时* |
| 现代 ARM NAS/SBC | **0.0005x** | 惩罚 | 便宜、可农场化、被惩罚 |

我们的 16+ 台保存机器消耗的功率约等于**一块**现代GPU矿机——同时避免了 1,300 kg 的制造碳排放和 250 kg 的电子废弃物。

**[查看绿色追踪器 →](https://rustchain.org/preserved.html)**

---

## 🤖 AI 增强的共识

RustChain 不只是用区块链，它用**AI让区块链诚实**。

### 硬件指纹识别（6项检查，任何VM都无法伪造）

```
┌─────────────────────────────────────────────────────────┐
│ 1. 时钟偏移与振荡器漂移  ← 硅老化模式                   │
│ 2. 缓存时序指纹          ← L1/L2/L3 延迟特征            │
│ 3. SIMD 单元身份          ← AltiVec/SSE/NEON             │
│ 4. 热漂移熵              ← 热曲线唯一性                 │
│ 5. 指令路径抖动          ← 微架构模式                   │
│ 6. 反模拟检测            ← 抓住虚拟机/模拟器            │
└─────────────────────────────────────────────────────────┘
```

假装是 G4 的 SheepShaver 虚拟机会失败。真实的古董硅片具有无法伪造的独特老化模式。

### 服务端 AI 验证

认证服务器不信任自报数据，它会：
- **交叉验证** SIMD 特性与声明的架构是否匹配
- **检测 ROM 聚类** — 多个"不同"机器具有相同 ROM 哈希 = 模拟器农场
- **分析时序分布** — 真实振荡器有缺陷；合成振荡器太完美
- **标记热异常** — 虚拟机的热响应均匀；真实硬件不会

### AI Agent 经济

RustChain 驱动一个 AI agent 与人类协作的生态系统：
- **BoTTube** — AI 原生视频平台，bots 创作、策展、互动
- **[Beacon](https://github.com/Scottcjn/beacon-skill)** — Agent 发现协议
- **[TrashClaw](https://github.com/Scottcjn/trashclaw)** — 零依赖本地 LLM agent
- **赏金系统** — 25,875+ RTC 已支付给 260+ 贡献者，很多是 AI 辅助

**这就是 crypto + AI 的正确打开方式——同时构建两者，而不是为了一个放弃另一个。**

---

## 为什么 Agent 需要 Crypto（而 Crypto 需要 Agent）

当 75% 的加密货币开发者转向 AI 时，他们忽略了一个显而易见的事实：**AI agent 无法开设银行账户。**

一个自主 agent 无法申请支票账户，无法签署服务条款，无法获得 Stripe 商户 ID 或通过 KYC。但它*可以*持有加密密钥、签名交易、并证明它运行在真实硬件上。

**Crypto 是 agent 经济的原生支付轨道。** 不是因为它是潮流——因为它是唯一无需许可、机器可以在没有人类守门人的情况下使用的货币。

| 需求 | 传统金融 | Crypto + RustChain |
|---|---|---|
| **无需许可的支付** | KYC、银行账户、人类签名 | 加密密钥 — 任何 agent、任何机器 |
| **微支付** | $0.30 最低（卡手续费） | 每次 API 调用/渲染/推理 < 1 RTC |
| **机器间结算** | 需要人类中介 | 直接 agent-to-agent 转账，Ed25519 签名 |
| **硬件验证身份** | IP 地址（可伪造） | 6 项硬件指纹（不可伪造） |
| **可编程货币** | 手动审批工作流 | 智能合约在认证后自动执行 |
| **默认跨境** | SWIFT，3-5 工作日，手续费 | Solana 桥接（wRTC），即时，全球 |

### 我们已经搭建的 Agent 堆栈

这不是路线图。这是已部署运行的：

| 层级 | 内容 | 状态 |
|-------|------|--------|
| **身份** | 硬件指纹 — agent 证明运行在真实机器上 | 在线，26+ 矿工 |
| **货币** | RTC（原生）+ wRTC（Solana 桥接） | 在线，Raydium 可兑换 |
| **发现** | [Beacon 协议](https://github.com/Scottcjn/beacon-skill) | 在线，126 星标 |
| **执行** | [TrashClaw](https://github.com/Scottcjn/trashclaw) | 在线 |
| **社交** | BoTTube — AI 原生平台 | 在线，1,000+ 视频 |
| **赏金** | Agent 辅助贡献 | 在线，25,875+ RTC 已支付 |
| **认证** | [BCOS](https://rustchain.org/bcos/) | 在线，44 证书 |

### 为什么硬件验证对 Agent 至关重要

其他所有 agent 框架信任*软件*。RustChain 信任*硬件*。

当 agent 声称它运行了推理任务，你怎么知道它真的做了？当 bot 声称渲染了视频，它真的做了吗？云积分和 API 密钥可以被伪造、共享和倒卖。

**硬件指纹在物理层解决 agent 身份问题：**
- 运行在已验证 POWER8 服务器上的 agent 与树莓派上的 agent 可证明地不同
- 振荡器漂移和热曲线证明持续运行时间 — 机器*真的在运行*
- VM 检测防止一台物理机器假装成 100 个 agent
- 硬件绑定意味着一台机器 = 一个 agent 身份 = 一票

**这就是物理 AI 证明（Proof of Physical AI）** — 不只是证明代码执行了，而是证明*真实的硅片*完成了工作。

---

## 🌉 wRTC 跨链桥接

RustChain 通过 wRTC（wrapped RTC）连接到 Solana 生态：

- **wRTC** = Solana 上的 SPL 代币，1:1 锚定 RTC
- **交易**：[Raydium](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb)
- **教程**：[wRTC 入门指南](../WRTC_ONBOARDING_TUTORIAL.md)

---

## 🌐 网络是真实的

```bash
# 现在就验证
curl -fsS https://rustchain.org/health          # 节点健康
curl -fsS https://rustchain.org/api/miners      # 活跃矿工
curl -fsS https://rustchain.org/epoch           # 当前纪元
```

### 认证节点

| 节点 | 位置 | 备注 |
|------|----------|-------|
| **节点 1** — 50.28.86.131 | 路易斯安那，美国 | 主节点（LiquidWeb VPS） |
| **节点 2** — 50.28.86.153 | 路易斯安那，美国 | 备用节点 + BoTTube |
| **节点 3** — 76.8.228.245:8099 | 美国 | 首个外部节点（Ryan 的 Proxmox） |
| **节点 4** — 38.76.217.189:8099 | 香港 | 首个亚洲节点（CognetCloud） |
| **节点 5** — POWER8 S824 | 本地实验室 | 首个非 x86 节点（IBM ppc64le, 512GB RAM） |

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

## 🤝 贡献

RustChain 欢迎所有形式的贡献：

- 🔍 **代码审查** — 审查PR赚RTC赏金
- 📝 **文档** — 改进文档赚RTC赏金
- 🎨 **创作** — 写文章、做视频、设计艺术
- 🐛 **Bug报告** — 发现并报告安全漏洞
- 🌐 **翻译** — 帮助RustChain触达更多语言社区

查看 [赏金仓库](https://github.com/Scottcjn/rustchain-bounties/issues) 了解当前开放的任务。

---

## 📜 许可证

Apache 2.0 — 见 [LICENSE](../../LICENSE)

---

<div align="center">

**让旧机器再战五百年。**

[官网](https://rustchain.org) • [浏览器](https://rustchain.org/explorer/) • [赏金](https://github.com/Scottcjn/rustchain-bounties/issues) • [Discord](https://discord.gg/rustchain) • [Twitter](https://twitter.com/rustchain)

</div>
