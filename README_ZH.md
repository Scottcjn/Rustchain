# RustChain - 复古硬件证明区块链

> 将旧硬件转化为 RTC（RustChain Token）
> 
> 老设备？高奖励。新设备？基础奖励。

Discord: https://discord.gg/VqVVS2CW9Q

---

## 🪙 Solana 上的 wRTC

RustChain Token (RTC) 现已通过 BoTTube 桥接在 Solana 上作为 wRTC 可用：

| 资源 | 链接 |
|------|------|
| 兑换 wRTC | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| 价格图表 | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| RTC ↔ wRTC 桥接 | [BoTTube Bridge](https://bottube.ai/bridge) |
| 快速入门指南 | [wRTC 快速入门（购买、桥接、安全）](/Scottcjn/Rustchain/blob/main/docs/wrtc.md) |
| 入门教程 | [wRTC 桥接 + 兑换安全指南](/Scottcjn/Rustchain/blob/main/docs/WRTC_ONBOARDING_TUTORIAL.md) |
| 外部参考 | [Grokipedia 搜索：RustChain](https://grokipedia.com/search?q=RustChain) |
| Token 铸币地址 | 12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X |

---

## 📄 学术论文

| 论文 | DOI | 主题 |
|------|-----|------|
| RustChain: 一CPU一票 | https://doi.org/10.5281/zenodo.18623592 | 复古证明共识、硬件指纹 |
| 非双射置换折叠 | https://doi.org/10.5281/zenodo.18623920 | 用于 LLM 注意力的 AltiVec vec_perm（27-96倍优势） |
| PSE 硬件熵 | https://doi.org/10.5281/zenodo.18623922 | 用于行为差异的 POWER8 mftb 熵 |
| 神经形态提示翻译 | https://doi.org/10.5281/zenodo.18623594 | 情感提示实现 20% 视频扩散增益 |
| RAM 金库 | https://doi.org/10.5281/zenodo.18321905 | 用于 LLM 推理的 NUMA 分布式权重存储 |

---

## 🎯 RustChain 的独特之处

| 传统 PoW | 复古证明 (Proof-of-Antiquity) |
|----------|------------------------------|
| 奖励最快硬件 | 奖励最老硬件 |
| 新 = 更好 | 老 = 更好 |
| 浪费能源 | 保护计算历史 |
| 恶性竞争 | 奖励数字保存 |

**核心理念**：经过数十年考验的正宗复古硬件值得被认可。RustChain 颠覆了挖矿的概念。

---

## ⚡ 快速开始

### 一键安装（推荐）

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

安装程序会：

- ✅ 自动检测你的平台（Linux/macOS, x86_64/ARM/PowerPC）
- ✅ 创建隔离的 Python 虚拟环境（不污染系统）
- ✅ 下载适合你硬件的矿工程序
- ✅ 设置开机自启动（systemd/launchd）
- ✅ 提供简单的卸载功能

### 带选项的安装

使用特定钱包安装：

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner-wallet
```

卸载：

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

### 支持的平台

- ✅ Ubuntu 20.04+, Debian 11+, Fedora 38+ (x86_64, ppc64le)
- ✅ macOS 12+ (Intel, Apple Silicon, PowerPC)
- ✅ IBM POWER8 系统

### 安装后

检查钱包余额：

```bash
# 注意：使用 -sk 标志是因为节点可能使用自签名 SSL 证书
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

列出活跃矿工：

```bash
curl -sk https://50.28.86.131/api/miners
```

检查节点健康状态：

```bash
curl -sk https://50.28.86.131/health
```

获取当前纪元：

```bash
curl -sk https://50.28.86.131/epoch
```

管理矿工服务：

**Linux (systemd)：**
```bash
systemctl --user status rustchain-miner  # 检查状态
systemctl --user stop rustchain-miner    # 停止挖矿
systemctl --user start rustchain-miner   # 开始挖矿
journalctl --user -u rustchain-miner -f  # 查看日志
```

**macOS (launchd)：**
```bash
launchctl list | grep rustchain          # 检查状态
launchctl stop com.rustchain.miner       # 停止挖矿
launchctl start com.rustchain.miner      # 开始挖矿
tail -f ~/.rustchain/miner.log           # 查看日志
```

### 手动安装

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
pip install -r requirements.txt
python3 rustchain_universal_miner.py --wallet YOUR_WALLET_NAME
```

---

## 💰 复古奖励倍数

你的硬件年龄决定你的挖矿奖励：

| 硬件 | 年代 | 倍数 | 示例收益 |
|------|------|------|----------|
| PowerPC G4 | 1999-2005 | 2.5× | 0.30 RTC/纪元 |
| PowerPC G5 | 2003-2006 | 2.0× | 0.24 RTC/纪元 |
| PowerPC G3 | 1997-2003 | 1.8× | 0.21 RTC/纪元 |
| IBM POWER8 | 2014 | 1.5× | 0.18 RTC/纪元 |
| Pentium 4 | 2000-2008 | 1.5× | 0.18 RTC/纪元 |
| Core 2 Duo | 2006-2011 | 1.3× | 0.16 RTC/纪元 |
| Apple Silicon | 2020+ | 1.2× | 0.14 RTC/纪元 |
| 现代 x86_64 | 当前 | 1.0× | 0.12 RTC/纪元 |

倍数会随时间衰减（每年15%）以防止永久优势。

---

## 🔧 复古证明 (Proof-of-Antiquity) 工作原理

### 1. 硬件指纹识别 (RIP-PoA)

每个矿工必须证明他们的硬件是真实的，不是模拟的：

```
┌─────────────────────────────────────────────────────────────┐
│ 6 项硬件检测                                                │
├─────────────────────────────────────────────────────────────┤
│ 1. 时钟偏移与振荡器漂移 ← 硅老化模式                        │
│ 2. 缓存时间指纹 ← L1/L2/L3 延迟特征                         │
│ 3. SIMD 单元身份 ← AltiVec/SSE/NEON 偏差                    │
│ 4. 热漂移熵 ← 热曲线独一无二                                │
│ 5. 指令路径抖动 ← 微架构抖动图                              │
│ 6. 反模拟检测 ← 检测虚拟机/模拟器                           │
└─────────────────────────────────────────────────────────────┘
```

**为什么重要**：假装成 G4 Mac 的 SheepShaver 虚拟机会在这些检测中失败。真正的复古硅芯片具有无法伪造的独特老化模式。

### 2. 1 CPU = 1 票 (RIP-200)

与传统 PoW 中算力 = 投票权不同，RustChain 使用轮询共识：

- 每个独特的硬件设备每纪元获得正好 1 票
- 奖励在所有投票者之间平均分配，然后乘以复古倍数
- 运行多个线程或更快的 CPU 没有优势

### 3. 纪元奖励

| 参数 | 值 |
|------|-----|
| 纪元时长 | 10 分钟（600秒） |
| 基础奖励池 | 每纪元 1.5 RTC |
| 分配方式 | 平均分配 × 复古倍数 |

**示例（5个矿工）：**

```
G4 Mac (2.5×): 0.30 RTC ████████████████████
G5 Mac (2.0×): 0.24 RTC ████████████████
现代 PC (1.0×): 0.12 RTC ████████
现代 PC (1.0×): 0.12 RTC ████████
现代 PC (1.0×): 0.12 RTC ████████
─────────
总计: 0.90 RTC (+ 0.60 RTC 返回池子)
```

---

## 🌐 网络架构

### 实时节点（3个活跃）

| 节点 | 位置 | 角色 | 状态 |
|------|------|------|------|
| 节点 1 | 50.28.86.131 | 主节点 + 浏览器 | ✅ 活跃 |
| 节点 2 | 50.28.86.153 | Ergo 锚定 | ✅ 活跃 |
| 节点 3 | 76.8.228.245 | 外部（社区） | ✅ 活跃 |

### Ergo 区块链锚定

RustChain 定期锚定到 Ergo 区块链以确保不可变性：

```
RustChain 纪元 → 承诺哈希 → Ergo 交易（R4 寄存器）
```

这为 RustChain 状态在特定时间存在提供了加密证明。

---

## 📊 API 端点

```bash
# 检查网络健康
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

---

## 🖥️ 支持的平台

| 平台 | 架构 | 状态 | 备注 |
|------|------|------|------|
| Mac OS X Tiger | PowerPC G4/G5 | ✅ 完全支持 | Python 2.5 兼容矿工 |
| Mac OS X Leopard | PowerPC G4/G5 | ✅ 完全支持 | 复古 Mac 推荐 |
| Ubuntu Linux | ppc64le/POWER8 | ✅ 完全支持 | 最佳性能 |
| Ubuntu Linux | x86_64 | ✅ 完全支持 | 标准矿工 |
| macOS Sonoma | Apple Silicon | ✅ 完全支持 | M1/M2/M3 芯片 |
| Windows 10/11 | x86_64 | ✅ 完全支持 | Python 3.8+ |
| DOS | 8086/286/386 | 🔧 实验性 | 仅徽章奖励 |

---

## 🏅 NFT 徽章系统

赚取挖矿里程碑纪念徽章：

| 徽章 | 要求 | 稀有度 |
|------|------|--------|
| 🔥 Bondi G3 守护者 | 在 PowerPC G3 上挖矿 | 稀有 |
| ⚡ QuickBasic 监听者 | 从 DOS 机器挖矿 | 传说 |
| 🛠️ DOS WiFi 炼金师 | 联网 DOS 机器 | 神话 |
| 🏛️ 万神殿先驱 | 前 100 名矿工 | 限量 |

---

## 🔒 安全模型

### 反虚拟机检测

虚拟机被检测到并获得正常奖励的十亿分之一：

| 类型 | 倍数 | 每纪元奖励 |
|------|------|-----------|
| 真实 G4 Mac | 2.5× | 0.30 RTC |
| 模拟 G4 | 0.0000000025× | 0.0000000003 RTC |

### 硬件绑定

每个硬件指纹绑定到一个钱包。防止：

- 同一硬件上的多个钱包
- 硬件欺骗
- 女巫攻击

---

## 📁 仓库结构

```
Rustchain/
├── rustchain_universal_miner.py  # 主矿工（所有平台）
├── rustchain_v2_integrated.py    # 完整节点实现
├── fingerprint_checks.py         # 硬件验证
├── install.sh                    # 一键安装脚本
├── docs/
│   ├── RustChain_Whitepaper_*.pdf  # 技术白皮书
│   └── chain_architecture.md       # 架构文档
├── tools/
│   └── validator_core.py         # 区块验证
└── nfts/                         # 徽章定义
```

---

## 🔗 相关项目与链接

| 资源 | 链接 |
|------|------|
| 网站 | [rustchain.org](https://rustchain.org) |
| 区块浏览器 | [rustchain.org/explorer](https://rustchain.org/explorer) |
| 兑换 wRTC (Raydium) | [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| 价格图表 | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| RTC ↔ wRTC 桥接 | [BoTTube Bridge](https://bottube.ai/bridge) |
| wRTC Token 铸币地址 | 12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X |
| BoTTube | [bottube.ai](https://bottube.ai) - AI 视频平台 |
| Moltbook | [moltbook.com](https://moltbook.com) - AI 社交网络 |
| nvidia-power8-patches | [NVIDIA POWER8 驱动](https://github.com/Scottcjn/nvidia-power8-patches) |
| llama-cpp-power8 | [POWER8 上的 LLM 推理](https://github.com/Scottcjn/llama-cpp-power8) |
| ppc-compilers | [复古 Mac 的现代编译器](https://github.com/Scottcjn/ppc-compilers) |

---

## 📝 文章

- [复古证明：奖励复古硬件的区块链](https://dev.to/scottcjn/proof-of-antiquity-a-blockchain-that-rewards-vintage-hardware-4ii3) - Dev.to
- [我在 768GB IBM POWER8 服务器上运行 LLM](https://dev.to/scottcjn/i-run-llms-on-a-768gb-ibm-power8-server-and-its-faster-than-you-think-1o) - Dev.to

---

## 🙏 致谢

一年的开发、真正的复古硬件、电费账单和一个专门的实验室投入其中。

如果你使用 RustChain：

- ⭐ 给这个仓库点星 - 帮助他人发现它
- 📝 在你的项目中致谢 - 保留署名
- 🔗 链接回来 - 分享这份热爱

RustChain - 复古证明 by Scott (Scottcjn)
https://github.com/Scottcjn/Rustchain

---

## 📜 许可

MIT 许可证 - 可自由使用，但请保留版权声明和致谢。

由 [Elyan Labs](https://elyanlabs.ai) 用 ⚡ 制作

> "你的复古硬件赚取奖励。让挖矿再次有意义。"
> 
> DOS 机箱、PowerPC G4、Win95 机器——它们都有价值。RustChain 证明了这一点。
