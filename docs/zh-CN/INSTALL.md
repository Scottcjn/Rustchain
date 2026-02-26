# RustChain 矿工安装指南

本指南介绍如何在 Linux 和 macOS 系统上安装和设置 RustChain 矿工。

## 快速安装（推荐）

### 默认安装
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

安装程序将：
1. 自动检测您的平台（操作系统和架构）
2. 在 `~/.rustchain/venv` 创建隔离的 Python 虚拟环境
3. 在虚拟环境中安装所需依赖（requests）
4. 下载适合您硬件的矿工程序
5. 提示输入钱包名称（或自动生成）
6. 询问是否设置开机自启动
7. 显示钱包余额查询命令

### 指定钱包安装
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner-wallet
```

这将跳过交互式钱包提示，直接使用指定的钱包名称。

## 支持的平台

### Linux
- ✅ Ubuntu 20.04, 22.04, 24.04
- ✅ Debian 11, 12
- ✅ Fedora 38, 39, 40
- ✅ RHEL 8, 9
- ✅ 其他基于 systemd 的发行版

**架构：**
- x86_64（Intel/AMD 64位）
- ppc64le（PowerPC 64位小端序）
- ppc（PowerPC 32位）

### macOS
- ✅ macOS 12 (Monterey) 及更高版本
- ✅ macOS 11 (Big Sur) 有限支持

**架构：**
- arm64（Apple Silicon M1/M2/M3）
- x86_64（Intel Mac）
- powerpc（PowerPC G3/G4/G5）

### 特殊硬件
- ✅ IBM POWER8 系统
- ✅ PowerPC G4/G5 Mac
- ✅ 古董 x86 CPU（Pentium 4、Core 2 Duo 等）

## 系统要求

### 基本要求
- Python 3.6+（古董 PowerPC 系统支持 Python 2.5+）
- curl 或 wget
- 50 MB 磁盘空间
- 网络连接

### Linux 特定要求
- systemd（用于自启动功能）
- python3-venv 或 virtualenv 包

### macOS 特定要求
- 命令行工具（如需要会自动安装）
- launchd（macOS 内置）

## 安装目录结构

安装后，`~/.rustchain/` 目录结构如下：

```
~/.rustchain/
├── venv/                    # 隔离的 Python 虚拟环境
│   ├── bin/
│   │   ├── python          # 虚拟环境 Python 解释器
│   │   └── pip             # 虚拟环境 pip
│   └── lib/
├── miner.py                 # 矿工脚本
├── wallet.txt               # 钱包名称
└── logs/                    # 日志目录
    └── miner.log           # 矿工日志
```

## 手动安装

如果您更喜欢手动安装：

```bash
# 1. 创建目录
mkdir -p ~/.rustchain

# 2. 创建虚拟环境
python3 -m venv ~/.rustchain/venv

# 3. 激活虚拟环境
source ~/.rustchain/venv/bin/activate

# 4. 安装依赖
pip install requests

# 5. 下载矿工
curl -o ~/.rustchain/miner.py https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/miner.py

# 6. 运行矿工
python ~/.rustchain/miner.py --wallet YOUR_WALLET_NAME
```

## 常用命令

### 启动矿工
```bash
~/.rustchain/venv/bin/python ~/.rustchain/miner.py --wallet YOUR_WALLET
```

### 查看余额
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET"
```

### 查看日志
```bash
tail -f ~/.rustchain/logs/miner.log
```

### 停止矿工
```bash
# Linux (systemd)
systemctl --user stop rustchain-miner

# macOS (launchd)
launchctl unload ~/Library/LaunchAgents/com.rustchain.miner.plist
```

## 故障排除

### 常见问题

**问题：Python 未找到**
```bash
# Ubuntu/Debian
sudo apt install python3 python3-venv

# Fedora/RHEL
sudo dnf install python3

# macOS
xcode-select --install
```

**问题：网络连接失败**
- 检查防火墙设置
- 确保可以访问 GitHub 和 RustChain 节点
- 尝试使用 VPN

**问题：权限被拒绝**
```bash
chmod +x ~/.rustchain/miner.py
```

## 获取帮助

- **文档：** https://github.com/Scottcjn/Rustchain
- **问题反馈：** https://github.com/Scottcjn/Rustchain/issues
- **区块浏览器：** https://rustchain.org/explorer
- **悬赏任务：** https://github.com/Scottcjn/rustchain-bounties

## 安全说明

1. 安装程序使用 HTTPS 从 GitHub 下载文件
2. Python 依赖安装在隔离的虚拟环境中（不污染系统）
3. 矿工以您的用户身份运行（非 root）
4. 服务是用户级别的（systemd --user, ~/Library/LaunchAgents）
5. 所有日志存储在您的主目录中

## 贡献

发现 bug 或想改进安装程序？请提交 PR 到：
https://github.com/Scottcjn/Rustchain

## 许可证

RustChain 采用 MIT 许可证。详见 LICENSE 文件。
