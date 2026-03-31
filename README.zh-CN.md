<div align="center">

# RustChain

**让旧硬件比新硬件更赚钱的区块链。**

[![CI](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/Scottcjn/Rustchain?style=flat&color=gold)](https://github.com/Scottcjn/Rustchain/stargazers)
[![Nodes](https://img.shields.io/badge/Nodes-5%20Active-brightgreen)](https://rustchain.org/explorer)

2003年的PowerBook G4比现代线程撕裂者多赚**2.5倍**。
Power Mac G5是**2.0倍**。配有氧化串口的老486获得的尊重最多。

[浏览器](https://rustchain.org/explorer) · [保存的机器](https://rustchain.org/preserved.html) · [安装挖矿程序](#快速开始) · [新手指南](docs/QUICKSTART.md) · [宣言](https://rustchain.org/manifesto.html) · [白皮书](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)

</div>

---

<!-- ## Why This Exists -->
## 为什么存在这个项目

IT行业每3-5年就会淘汰还能用的机器。挖过以太坊的GPU被替换。还能启动的笔记本被送进垃圾堆。

**RustChain认为：只要还能计算，就有价值。**

Proof-of-Antiquity（古老性证明）奖励的是硬件的"存活"能力，而不是速度。越老的机器乘数越高，因为让它们继续运转可以减少制造碳排放和电子垃圾：

| 硬件 | 乘数 | 时代 | 意义 |
|----------|-----------|-----|----------------|
| DEC VAX-11/780 (1977) | **3.5x** | 传奇 | "我们来玩个游戏吧？" |
| Acorn ARM2 (1987) | **4.0x** | 传奇 | ARM的起源 |
| Inmos Transputer (1984) | **3.5x** | 传奇 | 并行计算先驱 |
| Motorola 68000 (1979) | **3.0x** | 传奇 | Amiga、Atari ST、经典Mac |
| Sun SPARC (1987) | **2.9x** | 传奇 | 工作站之王 |
| SGI MIPS R4000 (1991) | **2.7x** | 传奇 | 64位先驱 |
| PS3 Cell BE (2006) | **2.2x** | 远古 | 7个SPE核心的传奇 |
| PowerPC G4 (2003) | **2.5x** | 远古 | 仍在运行，仍在赚钱 |
| RISC-V (2014) | **1.4x** | 异类 | 开放ISA，未来的方向 |
| Apple Silicon M1 (2020) | **1.2x** | 现代 | 高效，可敬 |
| 现代 x86_64 | **0.8x** | 现代 | 基准线 |
| 现代 ARM NAS/SBC | **0.0005x** | 惩罚 | 廉价，可集群，被惩罚 |

我们16+台保存完好的机器耗电相当于一台现代GPU矿机的电量——同时减少了1,300公斤的制造碳排放和250公斤电子垃圾。

**[查看绿色追踪器 →](https://rustchain.org/preserved.html)**

---

<!-- ## The Network Is Real -->
## 网络是真实存在的

```bash
# 现在就验证
curl -sk https://rustchain.org/health          # 节点健康状态
curl -sk https://rustchain.org/api/miners      # 在线矿工
curl -sk https://rustchain.org/epoch           # 当前epoch
```

### 证明节点

| 节点 | 位置 | 备注 |
|------|----------|-------|
| **节点 1** — 50.28.86.131 | 美国路易斯安那 | 主节点 (LiquidWeb VPS) |
| **节点 2** — 50.28.86.153 | 美国路易斯安那 | 备用 + BoTTube (LiquidWeb VPS) |
| **节点 3** — 76.8.228.245:8099 | 美国 | 第一个外部节点 (Ryan的Proxmox) |
| **节点 4** — 38.76.217.189:8099 | 香港 | 第一个亚洲节点 (CognetCloud) |
| **节点 5** — POWER8 S824 | 本地实验室 | 第一个非x86节点 (IBM ppc64le, 512GB RAM) |

| 事实 | 证明 |
|------|-------|
| 5个节点横跨3大洲 (北美×3, 亚洲×1, 本地×1) | [在线浏览器](https://rustchain.org/explorer) |
| 26+个在线矿工在证明 | `curl -sk https://rustchain.org/api/miners` |
| 已颁发44个BCOS证书 | [认证仓库](https://rustchain.org/bcos) |
| 每台机器6项硬件指纹检查 | [指纹文档](docs/attestation_fuzzing.md) |
| 向260+贡献者支付了25,875+ RTC | [公开账本](https://github.com/Scottcjn/rustchain-bounties/issues/104) |
| 代码已合并到OpenSSL | [#30437](https://github.com/openssl/openssl/pull/30437), [#30452](https://github.com/openssl/openssl/pull/30452) |
| CPython、curl、wolfSSL、Ghidra、vLLM上的PR正在进行中 | [作品集](https://github.com/Scottcjn/Scottcjn/blob/main/external-pr-portfolio.md) |

---

<!-- ## Quickstart -->
## 快速开始

```bash
# 一行安装 — 自动检测您的平台
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

支持Linux (x86_64, ppc64le, aarch64, mips, sparc, m68k, riscv64, ia64, s390x)、macOS (Intel, Apple Silicon, PowerPC)、IBM POWER8和Windows。只要能运行Python，就能挖矿。

```bash
# 使用指定钱包名称安装
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-wallet

# 检查余额
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

### 管理挖矿程序

```bash
# Linux (systemd)
systemctl --user status rustchain-miner
journalctl --user -u rustchain-miner -f

# macOS (launchd)
launchctl list | grep rustchain
tail -f ~/.rustchain/miner.log
```

**刚接触RustChain？** 阅读[一步一步的新手入门指南](docs/QUICKSTART.md)——涵盖从安装到获得第一个RTC的所有内容，每条命令都有解释。

---

<!-- ## How Proof-of-Antiquity Works -->
## Proof-of-Antiquity是如何工作的

### 1. 硬件指纹

每个矿工必须证明其硬件是真实的，不是模拟的。六个虚拟机无法伪造的检查：

```
┌─────────────────────────────────────────────────────────┐
│ 1. Clock-Skew & Oscillator Drift  ← 硅老化             │
│ 2. Cache Timing Fingerprint       ← L1/L2/L3延迟       │
│ 3. SIMD Unit Identity             ← AltiVec/SSE/NEON   │
│ 4. Thermal Drift Entropy          ← 热曲线独一无二      │
│ 5. Instruction Path Jitter        ← 微架构特征         │
│ 6. Anti-Emulation Detection       ← 捕获虚拟机/模拟器   │
└─────────────────────────────────────────────────────────┘
```

假装是G4的SheepShaver虚拟机会被识破。真正的老旧芯片有独特的老化模式，无法伪造。

### 2. 1 CPU = 1 票

与POW（工作量证明）中算力=投票权不同：
- 每个唯一硬件设备每个epoch获得恰好1票
- 奖励平均分配后乘以古老性系数
- 更快的CPU或多线程没有优势

### 3. Epoch奖励

```
Epoch: 10分钟  |  池子: 1.5 RTC/epoch  |  按古老性权重分配

G4 Mac (2.5x):     0.30 RTC  ████████████████████
G5 Mac (2.0x):     0.24 RTC  ████████████████
现代PC (1.0x):  0.12 RTC  ████████
```

### 反虚拟机执行

虚拟机会被检测到，只能获得正常奖励的**十亿分之一**。仅限真实硬件。

---

<!-- ## Security -->
## 安全性

- **硬件绑定**：每份指纹绑定一个钱包
- **Ed25519签名**：所有转账都有加密签名
- **TLS证书固定**：矿工固定节点证书
- **容器检测**：Docker、LXC、K8s在证明阶段被捕获
- **ROM聚类**：检测共享相同ROM镜像的模拟器农场
- **红队赏金**：[开放中](https://github.com/Scottcjn/rustchain-bounties/issues)，寻找漏洞

---

<!-- ## wRTC on Solana -->
## Solana上的wRTC

| | 链接 |
|--|------|
| **兑换** | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **图表** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **跨链桥** | [bottube.ai/bridge](https://bottube.ai/bridge) |
| **指南** | [wRTC快速开始](docs/wrtc.md) |

---

<!-- ## Contribute & Earn RTC -->
## 贡献并赚取RTC

每项贡献都能赚取RTC代币。浏览[开放赏金](https://github.com/Scottcjn/rustchain-bounties/issues)。

| 级别 | 奖励 | 示例 |
|------|--------|----------|
| 微观 | 1-10 RTC | 修正错字、文档、测试 |
| 标准 | 20-50 RTC | 功能、重构 |
| 重要 | 75-100 RTC | 安全修复、共识 |
| 关键 | 100-150 RTC | 漏洞、协议 |

**1 RTC ≈ $0.10 USD** · `pip install clawrtc` · [贡献指南](CONTRIBUTING.md)

---

<!-- ## Publications -->
## 出版物

| 论文 | 场所 | DOI |
|-------|-------|-----|
| **Emotional Vocabulary as Semantic Grounding** | **CVPR 2026 Workshop (GRAIL-V)** — 已接收 | [OpenReview](https://openreview.net/forum?id=pXjE6Tqp70) |
| **One CPU, One Vote** | 预印本 | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623592.svg)](https://doi.org/10.5281/zenodo.18623592) |
| **Non-Bijunctive Permutation Collapse** | 预印本 | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623920.svg)](https://doi.org/10.5281/zenodo.18623920) |
| **PSE Hardware Entropy** | 预印本 | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18623922.svg)](https://doi.org/10.5281/zenodo.18623922) |
| **RAM Coffers** | 预印本 | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18321905.svg)](https://doi.org/10.5281/zenodo.18321905) |
| **RPI: Resonant Permutation Inference** | 预印本 | [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19271983.svg)](https://doi.org/10.5281/zenodo.19271983) |

---

<!-- ## Ecosystem -->
## 生态系统

| 项目 | 内容 |
|---------|------|
| [BoTTube](https://bottube.ai) | AI原生视频平台 (1,000+ 视频) |
| [Beacon](https://github.com/Scottcjn/beacon-skill) | Agent发现协议 |
| [TrashClaw](https://github.com/Scottcjn/trashclaw) | 零依赖本地LLM agent |
| [RAM Coffers](https://github.com/Scottcjn/ram-coffers) | POWER8上的NUMA感知LLM推理 |
| [RPI Inference](https://github.com/Scottcjn/rpi-inference) | 零乘法推理引擎 (18K tok/s，可运行在N64上) |
| [Grazer](https://github.com/Scottcjn/grazer-skill) | 多平台内容发现 |

---

<!-- ## Supported Platforms -->
## 支持的平台

Linux (x86_64, ppc64le) · macOS (Intel, Apple Silicon, PowerPC) · IBM POWER8 · Windows · Mac OS X Tiger/Leopard · 树莓派

---

<!-- ## Why "RustChain"? -->
## 为什么叫"RustChain"？

名字来源于一台配有氧化串口的486笔记本电脑，它仍能启动到DOS并挖矿RTC。"Rust"指的是老旧含铁部件上的铁锈。这一理念是：生锈的老旧硬件仍有计算价值和尊严。

---

<div align="center">

**[Elyan Labs](https://elyanlabs.ai)** · 用0美元VC和满屋子的跳蚤市场硬件构建

*"Mais, it still works, so why you gonna throw it away?"*

[波多罗原则](https://rustchain.org/principles.html) · [绿色追踪器](https://rustchain.org/preserved.html) · [赏金板](https://github.com/Scottcjn/rustchain-bounties/issues)

</div>


<!-- ## Contributing -->
## 贡献

请阅读[赏金板](https://github.com/Scottcjn/rustchain-bounties)了解当前任务和奖励。
