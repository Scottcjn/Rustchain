# RustChain 升级迁移指南

> **奖励：** 3 RTC  
> **Issue:** [#1667](https://github.com/Scottcjn/rustchain-bounties/issues/1667)  
> **版本：** v1.0.0 → v1.x.x  
> **最后更新：** 2026-03-12

---

## 📋 目录

1. [概述](#概述)
2. [版本历史](#版本历史)
3. [升级前准备](#升级前准备)
4. [升级流程](#升级流程)
5. [版本兼容性矩阵](#版本兼容性矩阵)
6. [常见问题与解决方案](#常见问题与解决方案)
7. [回滚指南](#回滚指南)
8. [验证与测试](#验证与测试)

---

## 概述

本指南帮助矿工和节点运营商从 RustChain v1.0.0 升级到后续版本。升级过程应保持挖矿连续性和钱包安全性。

### 核心变更

- **Proof-of-Antiquity 共识**：RIP-200 协议（1 CPU = 1 票）
- **硬件指纹认证**：6 项硬件检查防止虚拟机作弊
- **复古硬件乘数**：G4 (2.5×), G5 (2.0×), POWER8 (1.5×)
- **Ergo 链锚定**： epoch 结算哈希锚定到 Ergo 区块链

---

## 版本历史

| 版本 | 发布日期 | 主要特性 | 兼容性 |
|------|----------|----------|--------|
| v1.0.0 | 2026-01-02 | 初始发布，RIP-200 共识 | 所有平台 |
| v1.0.0 (Windows) | 2026-02-21 | GUI 矿工，独立 EXE | Windows 10/11 |
| ClawRTC v1.0.0 | 2026-02-08 | 跨平台 CLI 工具 | 多平台 |

---

## 升级前准备

### 1. 备份钱包

```bash
# Linux/macOS
cp -r ~/.rustchain/wallet ~/.rustchain/wallet.backup.$(date +%Y%m%d)

# Windows
xcopy %USERPROFILE%\.rustchain\wallet %USERPROFILE%\.rustchain\wallet.backup.%DATE:~-4,4%%DATE:~-7,2%%DATE:~-10,2% /E /I
```

### 2. 记录当前配置

```bash
# 检查当前版本
clawrtc --version

# 导出钱包信息
clawrtc wallet show > wallet_info.txt

# 记录矿工配置
cat ~/.rustchain/config.yaml > config.backup
```

### 3. 检查系统要求

| 平台 | 最低要求 | 推荐 |
|------|----------|------|
| Linux | Ubuntu 20.04+, Python 3.10+ | Ubuntu 22.04+, Python 3.11+ |
| macOS | macOS 12+, Python 3.10+ | macOS 13+, Python 3.11+ |
| Windows | Windows 10/11, Python 3.8+ | Windows 11, Python 3.10+ |
| PowerPC | Mac OS X Tiger/Leopard | Tigerbrew + Python 2.5 |

### 4. 停止当前矿工

```bash
# Linux (systemd)
systemctl --user stop rustchain-miner

# macOS (launchd)
launchctl stop com.rustchain.miner

# Windows (GUI)
# 点击 "Stop Mining" 按钮

# Windows (服务)
net stop RustChainMiner
```

---

## 升级流程

### 方式 A: 自动安装器（推荐）

```bash
# 下载并运行安装器
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash

# 指定钱包名称
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet YOUR_WALLET

# 预览操作（不实际安装）
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --dry-run
```

### 方式 B: 手动升级

#### Linux/macOS

```bash
# 1. 克隆仓库
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行安装脚本
bash install-miner.sh --wallet YOUR_WALLET

# 5. 启动矿工
systemctl --user start rustchain-miner  # Linux
launchctl start com.rustchain.miner     # macOS
```

#### Windows

**选项 A: 独立 EXE（最简单）**

1. 下载 `RustChainMiner.exe`
2. 双击运行（自动生成钱包）
3. 点击 "Start Mining"

**选项 B: Python 安装器**

```powershell
# 1. 下载并解压 RustChain-Miner-Installer.zip
# 2. 运行 install.bat
# 3. 按提示完成安装
```

### 方式 C: 包管理器

```bash
# pip
pip install --upgrade clawrtc

# npm
npm install -g clawrtc

# Homebrew (macOS)
brew upgrade clawrtc

# Tigerbrew (PowerPC Mac)
brew upgrade clawrtc

# AUR (Arch Linux)
yay -S clawrtc
```

---

## 版本兼容性矩阵

### 硬件乘数

| 硬件 | 时代 | v1.0.0 | v1.x.x | 备注 |
|------|------|--------|--------|------|
| PowerPC G4 | 1999-2005 | 2.5× | 2.5× | 年衰减 15% |
| PowerPC G5 | 2003-2006 | 2.0× | 2.0× | 年衰减 15% |
| PowerPC G3 | 1997-2003 | 1.8× | 1.8× | 年衰减 15% |
| IBM POWER8 | 2014 | 1.5× | 1.5× | 年衰减 15% |
| Pentium 4 | 2000-2008 | 1.5× | 1.5× | 年衰减 15% |
| Core 2 Duo | 2006-2011 | 1.3× | 1.3× | 年衰减 15% |
| Apple Silicon | 2020+ | 1.2× | 1.2× | 年衰减 15% |
| Modern x86_64 | Current | 1.0× | 1.0× | 年衰减 15% |

### 平台支持

| 平台 | 架构 | v1.0.0 | v1.x.x | 状态 |
|------|------|--------|--------|------|
| Mac OS X Tiger | PowerPC G4/G5 | ✅ | ✅ | 完全支持 |
| Mac OS X Leopard | PowerPC G4/G5 | ✅ | ✅ | 推荐 |
| Ubuntu Linux | ppc64le/POWER8 | ✅ | ✅ | 最佳性能 |
| Ubuntu Linux | x86_64 | ✅ | ✅ | 标准 |
| macOS Sonoma | Apple Silicon | ✅ | ✅ | M1/M2/M3 |
| Windows 10/11 | x86_64 | ✅ | ✅ | Python 3.8+ |
| DOS | 8086/286/386 | 🔧 | 🔧 | 实验性（徽章奖励） |

---

## 常见问题与解决方案

### 1. 权限错误

**问题：** `Permission denied` 或 `Access denied`

**解决方案：**
```bash
# Linux/macOS - 使用有权限的账户
# 避免在系统 Python 全局 site-packages 中安装

# Windows - 以管理员身份运行 PowerShell
# 或使用用户级安装
pip install --user clawrtc
```

### 2. Python 版本错误

**问题：** `SyntaxError` 或 `ModuleNotFoundError`

**解决方案：**
```bash
# 检查 Python 版本
python3 --version  # 需要 3.10+

# 使用正确的 Python 解释器
python3.11 -m pip install clawrtc
```

### 3. 网络连接问题

**问题：** `could not reach network`

**解决方案：**
```bash
# 检查节点健康
curl -sk https://rustchain.org/health

# 检查钱包余额（替换 YOUR_WALLET）
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET"

# 如果使用旧版本，可能引用已退役的主机
# 升级到最新版本修复
```

### 4. HTTPS 证书错误

**问题：** SSL 证书验证失败

**解决方案：**
```bash
# 使用 -sk 标志跳过证书验证（节点可能使用自签名证书）
curl -sk https://rustchain.org/health

# 或更新系统证书
# Ubuntu/Debian
sudo apt update && sudo apt install --reinstall ca-certificates

# macOS
sudo security find-certificate -a -p /System/Library/Keychains/SystemRootCertificates.keychain | \
  sudo tee /etc/ssl/certs/ca-certificates.crt
```

### 5. 矿工立即退出

**问题：** 矿工启动后立即停止

**解决方案：**
```bash
# 检查服务状态
systemctl --user status rustchain-miner  # Linux
launchctl list | grep rustchain          # macOS

# 查看日志
journalctl --user -u rustchain-miner -f  # Linux
tail -f ~/.rustchain/miner.log           # macOS/通用

# 验证钱包存在
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET"
```

### 6. 硬件指纹验证失败

**问题：** 6 项硬件检查未通过

**解决方案：**
```bash
# 确保在真实硬件上运行（非虚拟机）
# 虚拟机检测到仅获得正常奖励的 10 亿分之一

# 检查硬件指纹
clawrtc attestation --dry-run

# 如果在虚拟机中开发，使用 --dev 模式
clawrtc mine --dev
```

---

## 回滚指南

### 回滚到 v1.0.0

```bash
# 1. 停止当前矿工
systemctl --user stop rustchain-miner  # Linux
launchctl stop com.rustchain.miner     # macOS

# 2. 恢复备份
cp -r ~/.rustchain/wallet.backup.* ~/.rustchain/wallet

# 3. 卸载当前版本
pip uninstall clawrtc

# 4. 安装 v1.0.0
pip install clawrtc==1.0.0

# 5. 恢复配置
cp config.backup ~/.rustchain/config.yaml

# 6. 重启矿工
systemctl --user start rustchain-miner  # Linux
launchctl start com.rustchain.miner     # macOS
```

---

## 验证与测试

### 1. 验证安装

```bash
# 检查版本
clawrtc --version

# 运行干跑测试
# Linux/macOS/WSL only: current Windows clawrtc releases do not support miner dry-run.
clawrtc mine --dry-run

# 预期：所有 6 项硬件指纹检查执行成功
```

### 2. 检查挖矿状态

```bash
# 查看矿工状态
systemctl --user status rustchain-miner  # Linux
launchctl list | grep rustchain          # macOS

# 查看实时日志
journalctl --user -u rustchain-miner -f  # Linux
tail -f ~/.rustchain/miner.log           # macOS
```

### 3. 验证钱包余额

```bash
# 等待 1-2 个 epoch（10-20 分钟）后检查余额
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET"
```

### 4. 网络健康检查

```bash
# 节点健康
curl -sk https://rustchain.org/health | jq .

# 当前 epoch
curl -sk https://rustchain.org/epoch | jq .

# 活跃矿工列表
curl -sk https://rustchain.org/api/miners | jq .

# 区块浏览器
open https://rustchain.org/explorer
```

---

## 📞 获取帮助

### 文档资源

- [主文档](https://github.com/Scottcjn/Rustchain/tree/main/docs)
- [协议规范](https://github.com/Scottcjn/Rustchain/blob/main/docs/PROTOCOL.md)
- [API 参考](https://github.com/Scottcjn/Rustchain/blob/main/docs/API.md)
- [常见问题](https://github.com/Scottcjn/Rustchain/blob/main/docs/FAQ_TROUBLESHOOTING.md)
- [钱包指南](https://github.com/Scottcjn/Rustchain/blob/main/docs/WALLET_USER_GUIDE.md)

### 社区支持

- **Discord:** https://discord.gg/VqVVS2CW9Q
- **GitHub Issues:** https://github.com/Scottcjn/Rustchain/issues
- **赏金任务:** https://github.com/Scottcjn/rustchain-bounties/issues

### 报告问题

提交 issue 时请包含：

1. 操作系统和版本
2. Python 版本（如适用）
3. RustChain 版本
4. 完整错误信息
5. 相关日志片段
6. `install-miner.sh --dry-run` 输出（如适用）

---

## ✅ 升级检查清单

- [ ] 已备份钱包和配置文件
- [ ] 已记录当前版本和配置
- [ ] 已检查系统要求
- [ ] 已停止当前矿工
- [ ] 已下载/安装新版本
- [ ] 已验证安装（`clawrtc --version`）
- [ ] 已运行干跑测试（Linux/macOS/WSL: `clawrtc mine --dry-run`）
- [ ] 已启动新矿工
- [ ] 已验证挖矿状态
- [ ] 已检查钱包余额（1-2 epoch 后）
- [ ] 已确认网络健康

---

**最后更新：** 2026-03-12  
**维护者：** RustChain 社区  
**许可证：** MIT
