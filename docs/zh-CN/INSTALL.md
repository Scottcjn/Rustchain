# RustChain 矿工安装指南

本指南涵盖在 Linux 和 macOS 系统上安装和设置 RustChain 矿工的步骤。

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
5. 提示输入您的钱包名称（或自动生成一个）
6. 询问是否要设置开机自启动
7. 显示钱包余额查询命令

### 使用指定钱包安装
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
- ppc64le（PowerPC 64位小端）
- ppc（PowerPC 32位）

### macOS
- ✅ macOS 12（Monterey）及更高版本
- ✅ macOS 11（Big Sur）有限支持

**架构：**
- arm64（Apple Silicon M1/M2/M3）
- x86_64（Intel Mac）
- powerpc（PowerPC G3/G4/G5）

### 特殊硬件
- ✅ IBM POWER8 系统
- ✅ PowerPC G4/G5 Mac
- ✅ 老式 x86 CPU（Pentium 4、Core 2 Duo 等）

## 系统要求

### 基本要求
- Python 3.6+（老式 PowerPC 系统支持 Python 2.5+）
- curl 或 wget
- 50 MB 磁盘空间
- 互联网连接

### Linux 特定要求
- systemd（用于自启动功能）
- python3-venv 或 virtualenv 包

### macOS 特定要求
- 命令行工具（如需要会自动安装）
- launchd（macOS 内置）

## 安装目录结构

安装后，您将在 `~/.rustchain/` 目录下看到以下结构：

```
~/.rustchain/
├── venv/                    # 隔离的 Python 虚拟环境
│   ├── bin/
│   │   ├── python          # 虚拟环境 Python 解释器
│   │   └── pip             # 虚拟环境 pip
│   └── lib/                # 已安装的包（requests 等）
├── rustchain_miner.py      # 主矿工脚本
├── fingerprint_checks.py   # 硬件认证模块
├── start.sh                # 便捷启动脚本
└── miner.log               # 矿工日志（如启用自启动）
```

## 自启动配置

### Linux（systemd）

安装程序会在以下位置创建用户服务：
```
~/.config/systemd/user/rustchain-miner.service
```

**服务管理命令：**
```bash
# 检查矿工状态
systemctl --user status rustchain-miner

# 启动挖矿
systemctl --user start rustchain-miner

# 停止挖矿
systemctl --user stop rustchain-miner

# 重启挖矿
systemctl --user restart rustchain-miner

# 禁用自启动
systemctl --user disable rustchain-miner

# 启用自启动
systemctl --user enable rustchain-miner

# 查看日志
journalctl --user -u rustchain-miner -f
```

### macOS（launchd）

安装程序会在以下位置创建启动代理：
```
~/Library/LaunchAgents/com.rustchain.miner.plist
```

**服务管理命令：**
```bash
# 检查矿工是否运行
launchctl list | grep rustchain

# 启动挖矿
launchctl start com.rustchain.miner

# 停止挖矿
launchctl stop com.rustchain.miner

# 禁用自启动
launchctl unload ~/Library/LaunchAgents/com.rustchain.miner.plist

# 启用自启动
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist

# 查看日志
tail -f ~/.rustchain/miner.log
```

## 查询钱包信息

### 余额查询
```bash
# 注意：使用 -k 标志是因为节点可能使用自签名 SSL 证书
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

示例输出：
```json
{
  "miner_id": "my-miner-wallet",
  "amount_rtc": 12.456,
  "amount_i64": 12456000
}
```

### 活跃矿工
```bash
curl -sk https://50.28.86.131/api/miners
```

### 节点健康状态
```bash
curl -sk https://50.28.86.131/health
```

### 当前纪元
```bash
curl -sk https://50.28.86.131/epoch
```

## 手动运行

如果您选择不设置自启动，可以手动运行矿工：

### 使用启动脚本
```bash
cd ~/.rustchain && ./start.sh
```

### 直接执行 Python
```bash
cd ~/.rustchain
./venv/bin/python rustchain_miner.py --wallet YOUR_WALLET_NAME
```

### 使用便捷命令（如果可用）
```bash
rustchain-mine
```

注意：便捷命令仅在安装期间 `/usr/local/bin` 可写时才可用。

## 卸载

### 完全卸载
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

这将：
1. 停止并删除 systemd/launchd 服务
2. 删除整个 `~/.rustchain` 目录（包括虚拟环境）
3. 删除便捷符号链接（如果存在）
4. 清理所有配置文件

### 手动卸载

如果自动卸载不起作用，您可以手动删除：

**Linux：**
```bash
# 停止并禁用服务
systemctl --user stop rustchain-miner
systemctl --user disable rustchain-miner
rm ~/.config/systemd/user/rustchain-miner.service
systemctl --user daemon-reload

# 删除文件
rm -rf ~/.rustchain
rm -f /usr/local/bin/rustchain-mine
```

**macOS：**
```bash
# 停止并删除服务
launchctl unload ~/Library/LaunchAgents/com.rustchain.miner.plist
rm ~/Library/LaunchAgents/com.rustchain.miner.plist

# 删除文件
rm -rf ~/.rustchain
rm -f /usr/local/bin/rustchain-mine
```

## 故障排除

### Python 虚拟环境创建失败

**错误：** `Could not create virtual environment`

**解决方案：**
```bash
# Ubuntu/Debian
sudo apt-get install python3-venv

# Fedora/RHEL
sudo dnf install python3-virtualenv

# macOS
pip3 install --user virtualenv
```

### 创建符号链接时权限被拒绝

**错误：** `ln: /usr/local/bin/rustchain-mine: Permission denied`

这是正常的。安装程序将继续而不创建便捷命令。您仍然可以使用启动脚本：
```bash
~/.rustchain/start.sh
```

### systemd 服务启动失败

**查看日志：**
```bash
journalctl --user -u rustchain-miner -n 50
```

常见问题：
- 启动时网络不可用：服务将自动重试
- Python 路径不正确：重新安装矿工
- 钱包名称包含特殊字符：仅使用字母数字字符

### macOS 上 launchd 服务无法加载

**检查是否已加载：**
```bash
launchctl list | grep rustchain
```

**手动重新加载：**
```bash
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist
```

**查看日志：**
```bash
cat ~/.rustchain/miner.log
```

### 连接节点失败

**错误：** `Could not connect to node`

**检查：**
1. 互联网连接正常
2. 节点可访问：`curl -sk https://50.28.86.131/health`
3. 防火墙未阻止 HTTPS（端口 443）

### 矿工未获得奖励

**检查：**
1. 矿工实际在运行：`systemctl --user status rustchain-miner` 或 `launchctl list | grep rustchain`
2. 钱包余额：`curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"`
3. 矿工日志中的错误：`journalctl --user -u rustchain-miner -f` 或 `tail -f ~/.rustchain/miner.log`
4. 硬件认证通过：在日志中查找 "fingerprint validation" 消息

### 运行多个矿工

要在不同硬件上运行多个矿工：

1. 在每台机器上分别安装
2. 为每个矿工使用不同的钱包名称
3. 每个矿工将被网络独立跟踪

### 更新矿工

要更新到最新版本：
```bash
# 卸载旧版本
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall

# 安装新版本
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet YOUR_WALLET_NAME
```

## 获取帮助

- **文档：** https://github.com/Scottcjn/Rustchain
- **问题反馈：** https://github.com/Scottcjn/Rustchain/issues
- **区块浏览器：** http://50.28.86.131/explorer
- **赏金任务：** https://github.com/Scottcjn/rustchain-bounties

## 安全说明

1. 安装程序使用 HTTPS 从 GitHub 下载文件
2. Python 依赖安装在隔离的虚拟环境中（不污染系统）
3. 矿工以您的用户身份运行（非 root）
4. 服务是用户级别的（systemd --user，~/Library/LaunchAgents）
5. 所有日志存储在您的主目录中
6. **SSL 证书：** RustChain 节点（50.28.86.131）可能使用自签名 SSL 证书。curl 命令中的 `-k` 标志会绕过证书验证。这是当前基础设施的已知限制。在生产环境中，您应该通过其他方式验证节点身份（社区共识、浏览器验证等）。

查看证书 SHA-256 指纹：

```bash
openssl s_client -connect 50.28.86.131:443 < /dev/null 2>/dev/null | openssl x509 -fingerprint -sha256 -noout
```

如果您想避免使用 `-k`，可以在本地保存证书并固定它：

```bash
# 保存证书一次（如果更改则覆盖）
openssl s_client -connect 50.28.86.131:443 < /dev/null 2>/dev/null | openssl x509 > ~/.rustchain/rustchain-cert.pem

# 然后使用它代替 -k
curl --cacert ~/.rustchain/rustchain-cert.pem "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

## 贡献

发现错误或想改进安装程序？请提交 PR 到：
https://github.com/Scottcjn/Rustchain

## 许可证

RustChain 采用 MIT 许可证。详见 LICENSE 文件。
