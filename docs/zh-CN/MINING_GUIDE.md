# RustChain 挖矿指南

## 概述

本指南将帮助您设置 RustChain 矿工，参与网络并赚取 RTC 奖励。RustChain 使用**工作量证明（Proof-of-Antiquity，PoA）**共识机制——奖励基于硬件年龄而非计算能力。越老的机器获得越高的乘数。

> **RustChain 新手？** 阅读[新手快速入门](QUICKSTART.md)获取每一步命令都详细说明的逐步教程。

---

## 工作量证明工作原理

与工作量证明（更快硬件获胜）不同，工作量证明奖励的是那些"存活下来"的机器。每个独特的硬件设备每个 epoch 正好获得 **1 票**，奖励均分后乘以基于硬件年龄的**古董乘数**。

### 硬件指纹识别

每个矿工必须证明他们的硬件是真实的，而不是模拟的。虚拟机无法伪造的六项检查：

```
┌─────────────────────────────────────────────────────────┐
│ 1. 时钟偏移与振荡器漂移  ← 硅老化                        │
│ 2. 缓存时序指纹           ← L1/L2/L3 延迟                │
│ 3. SIMD 单元标识          ← AltiVec/SSE/NEON             │
│ 4. 热漂移熵               ← 独特的热曲线                  │
│ 5. 指令路径抖动           ← 微架构模式                    │
│ 6. 反模拟检测             ← 捕获虚拟机/模拟器             │
└─────────────────────────────────────────────────────────┘
```

伪装成 G4 的虚拟机将失败。真正的老式硅芯片具有无法伪造的独特老化模式。

### 反虚拟机执行

虚拟机（VMware、VirtualBox、QEMU、WSL）会被检测到，获得的奖励仅为正常的**十亿分之一**。仅支持真实硬件。

---

## 硬件乘数

| 硬件 | 乘数 | 时代 |
|----------|-----------|-----|
| DEC VAX-11/780 (1977) | **3.5x** | 神话 |
| Acorn ARM2 (1987) | **4.0x** | 神话 |
| Motorola 68000 (1979) | **3.0x** | 传奇 |
| Sun SPARC (1987) | **2.9x** | 传奇 |
| PowerPC G4 (2003) | **2.5x** | 远古 |
| PowerPC G5 | **2.0x** | 远古 |
| RISC-V (2014) | **1.4x** | 异域 |
| Apple Silicon M1-M4 | **1.2x** | 现代 |
| 现代 x86_64 | **0.8x** | 现代 |
| 现代 ARM NAS/SBC | **0.0005x** | 惩罚 |

**1 RTC 约等于 0.10 美元** · 每 10 分钟，1.5 RTC 在所有活跃矿工之间分配。

---

## 硬件要求

工作量证明挖矿优先考虑真实的、可识别的硬件年龄，而非原始速度。矿工只需要足够的本地资源来运行 Python 客户端、保持硬件指纹检查稳定，并能连接到 RustChain 节点。

最低要求：

- CPU：任何支持 Python 3.8 或更高版本的真实硬件；不需要 GPU。
- 内存：足够的 RAM 来创建 Python 虚拟环境并运行矿工程序。
- 存储：至少 50 MB 可用磁盘空间，用于矿工、虚拟环境、日志和更新。
- 网络：能够稳定地通过出站 HTTPS 连接到 `https://rustchain.org`，用于健康检查、认证、余额查询和浏览器访问。
- 工具：`curl` 或 `wget`，以及可用的 Python 3.8+ 解释器。安装程序可以在 Linux 上尝试自动设置 Python。

支持的 CPU 系列包括 Linux `x86_64`、`ppc64le`、`aarch64`、`mips`、`sparc`、`m68k`、`riscv64`、`ia64` 和 `s390x`，以及 macOS Intel、Apple Silicon、PowerPC、IBM POWER8、Windows、老版 Mac OS X 和树莓派系统。现代 ARM NAS 或单板系统可以运行矿工，但会获得文档中所述的惩罚乘数。

有关安装前提条件，请参见 [INSTALL.md](../INSTALL.md)。有关完整的古董乘数和架构验证模型，请参见 [CPU_ANTIQUITY_SYSTEM.md](../CPU_ANTIQUITY_SYSTEM.md)。

---

## 安装

### 一键安装

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

### 手动安装

1. 克隆仓库：
   ```bash
   git clone https://github.com/Scottcjn/Rustchain.git
   cd Rustchain
   ```

2. 创建虚拟环境并安装依赖：
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. 运行矿工设置：
   ```bash
   python3 setup_miner.py
   ```

### Docker 安装

```bash
docker pull ghcr.io/scottcjn/rustchain-miner:latest
docker run -d --name rustchain-miner \
  -v $(pwd)/miner_data:/data \
  ghcr.io/scottcjn/rustchain-miner:latest
```

---

## 运行矿工

### 开始挖矿

```bash
python3 miners/linux/rustchain_linux_miner.py
```

首次运行时，矿工将：
1. 生成一个独特的硬件指纹
2. 提示您输入钱包地址
3. 开始每 10 分钟提交一次认证

### 试运行模式

在不向网络提交的情况下进行测试：

```bash
python3 miners/linux/rustchain_linux_miner.py --dry-run
```

### 详细模式

查看详细的指纹记录和日志：

```bash
python3 miners/linux/rustchain_linux_miner.py --verbose
```

---

## 钱包设置

您需要一个 RustChain 钱包来接收挖矿奖励。生成一个：

```bash
python3 wallet/rustchain_wallet.py generate
```

这将输出一个类似 `RTC...` 的钱包地址。请安全保存您的私钥。

> 参见 [WALLET_SETUP.md](WALLET_SETUP.md) 获取完整的钱包管理指南。

---

## 故障排查

### 常见问题

1. **反模拟检查失败** — 这在 WSL/Docker 中是预期的。请在裸机上运行以获得完整奖励。
2. **网络超时** — 确保您的网络可以访问 `https://rustchain.org`。
3. **奖励低** — 使用 `--verbose` 检查矿工的指纹，查看哪些检查通过/失败。
4. **"找不到兼容钱包"** — 先使用 `wallet/rustchain_wallet.py generate` 生成钱包。

### 获取帮助

- 加入 [Discord](https://discord.gg/rustchain) 获取实时支持
- 在 [GitHub](https://github.com/Scottcjn/rustchain/issues) 上提交 Issue 报告错误
- 查看 [FAQ_TROUBLESHOOTING.md](FAQ_TROUBLESHOOTING.md) 获取常见解决方案

---

## 奖励费率

| 组成部分 | 费率 |
|-----------|------|
| 基础 epoch 奖励 | 每 10 分钟 1.5 RTC |
| 乘数 | 基于硬件年龄的 0.0005x - 4.0x |
| 日均收益 | 每个矿工约 10-50 RTC |

奖励在每个 epoch 自动发放到您的钱包。

---

## 后续步骤

1. 设置矿工 → 2. 生成钱包 → 3. 开始挖矿 → 4. 追踪奖励

返回 [README](../README.md) 获取更多文档。
