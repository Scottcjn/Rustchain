# RustChain 快速入门指南

本指南将帮助您快速开始使用 RustChain 进行挖矿。

## 什么是 RustChain？

RustChain 是第一个奖励**古董硬件**而非最快硬件的区块链。您的 PowerPC G4 Mac 比现代 Threadripper 赚得更多——这正是我们的设计初衷。

### 核心理念：古董证明（Proof-of-Antiquity）

- **传统 PoW**：更快 = 更好，能源浪费
- **古董证明**：更老 = 更好，保护计算历史

## 一键安装（推荐）

### Linux / macOS

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

安装程序会自动：
- ✅ 检测您的平台（Linux/macOS，x86_64/ARM/PowerPC）
- ✅ 创建独立的 Python 虚拟环境
- ✅ 下载适合您硬件的矿工程序
- ✅ 设置开机自启动（systemd/launchd）
- ✅ 提供简单的卸载方式

### 指定钱包名称安装

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner-wallet
```

## 支持的平台

| 平台 | 架构 | 状态 | 备注 |
|------|------|------|------|
| **Mac OS X Tiger** | PowerPC G4/G5 | ✅ 完全支持 | Python 2.5 兼容 |
| **Mac OS X Leopard** | PowerPC G4/G5 | ✅ 完全支持 | 推荐用于古董 Mac |
| **Ubuntu Linux** | ppc64le/POWER8 | ✅ 完全支持 | 最佳性能 |
| **Ubuntu Linux** | x86_64 | ✅ 完全支持 | 标准矿工 |
| **macOS Sonoma** | Apple Silicon | ✅ 完全支持 | M1/M2/M3 芯片 |
| **Windows 10/11** | x86_64 | ✅ 完全支持 | Python 3.8+ |

## 安装后操作

### 检查钱包余额

```bash
# 注意：使用 -sk 标志因为节点可能使用自签名 SSL 证书
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

### 查看活跃矿工

```bash
curl -sk https://50.28.86.131/api/miners
```

### 检查节点健康状态

```bash
curl -sk https://50.28.86.131/health
```

### 获取当前纪元（epoch）

```bash
curl -sk https://50.28.86.131/epoch
```

## 管理矿工服务

### Linux (systemd)

```bash
# 检查状态
systemctl --user status rustchain-miner

# 停止挖矿
systemctl --user stop rustchain-miner

# 启动挖矿
systemctl --user start rustchain-miner

# 查看日志
journalctl --user -u rustchain-miner -f
```

### macOS (launchd)

```bash
# 检查状态
launchctl list | grep rustchain

# 停止挖矿
launchctl stop com.rustchain.miner

# 启动挖矿
launchctl start com.rustchain.miner

# 查看日志
tail -f ~/.rustchain/miner.log
```

## 古董倍数（Antiquity Multipliers）

您的硬件年代决定挖矿奖励：

| 硬件 | 年代 | 倍数 | 示例收益 |
|------|------|------|----------|
| **PowerPC G4** | 1999-2005 | **2.5×** | 0.30 RTC/纪元 |
| **PowerPC G5** | 2003-2006 | **2.0×** | 0.24 RTC/纪元 |
| **PowerPC G3** | 1997-2003 | **1.8×** | 0.21 RTC/纪元 |
| **IBM POWER8** | 2014 | **1.5×** | 0.18 RTC/纪元 |
| **Pentium 4** | 2000-2008 | **1.5×** | 0.18 RTC/纪元 |
| **Core 2 Duo** | 2006-2011 | **1.3×** | 0.16 RTC/纪元 |
| **Apple Silicon** | 2020+ | **1.2×** | 0.14 RTC/纪元 |
| **现代 x86_64** | 当前 | **1.0×** | 0.12 RTC/纪元 |

*倍数随时间衰减（每年 15%）以防止永久优势。*

## 工作原理

### 1 CPU = 1 票（RIP-200）

与 PoW 不同（算力 = 票数），RustChain 使用**轮询共识**：

- 每个独特的硬件设备每个纪元获得恰好 1 票
- 奖励在所有投票者之间平均分配，然后乘以古董倍数
- 运行多线程或更快的 CPU 没有优势

### 纪元奖励机制

```
纪元时长：10 分钟（600 秒）
基础奖励池：每纪元 1.5 RTC
分配方式：平均分配 × 古董倍数
```

**5 个矿工的示例：**
```
G4 Mac (2.5×):     0.30 RTC  ████████████████████
G5 Mac (2.0×):     0.24 RTC  ████████████████
现代 PC (1.0×):    0.12 RTC  ████████
现代 PC (1.0×):    0.12 RTC  ████████
现代 PC (1.0×):    0.12 RTC  ████████
                   ─────────
总计：             0.90 RTC（+ 0.60 RTC 返回奖励池）
```

## 常见问题排查

### 安装程序权限错误

使用对 `~/.local` 有写权限的账户重新运行，避免在系统 Python 的全局 site-packages 中运行。

### Python 版本错误

安装 Python 3.10+ 并设置 `python3` 指向该解释器：

```bash
python3 --version
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

### HTTPS 证书错误

检查连接性：

```bash
curl -I https://rustchain.org
```

### 矿工立即退出

验证钱包存在且服务正在运行：

```bash
# Linux
systemctl --user status rustchain-miner

# macOS
launchctl list | grep rustchain
```

## 获取帮助

- **GitHub Issues**: [github.com/Scottcjn/Rustchain/issues](https://github.com/Scottcjn/Rustchain/issues)
- **Discord**: [discord.gg/VqVVS2CW9Q](https://discord.gg/VqVVS2CW9Q)
- **文档**: [rustchain.org](https://rustchain.org)

## 下一步

- 查看 [完整安装指南](INSTALL.md) 了解高级选项
- 浏览 [开放赏金](https://github.com/Scottcjn/rustchain-bounties/issues) 赚取 RTC
- 阅读 [白皮书](../RustChain_Whitepaper_Flameholder_v0.97-1.pdf) 了解技术细节

---

**开始挖矿，让您的古董硬件创造价值！** 🧱⚡
