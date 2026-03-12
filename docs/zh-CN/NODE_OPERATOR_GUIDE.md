# RustChain 节点运营商指南

> **奖励：** 3 RTC  
> **类型：** 文档  
> **目标读者：** 节点运营商、系统管理员、技术爱好者

---

## 📋 目录

1. [简介](#简介)
2. [系统要求](#系统要求)
3. [快速开始](#快速开始)
4. [节点设置](#节点设置)
5. [配置详解](#配置详解)
6. [日常维护](#日常维护)
7. [监控与告警](#监控与告警)
8. [故障排查](#故障排查)
9. [安全最佳实践](#安全最佳实践)
10. [常见问题](#常见问题)

---

## 简介

RustChain 是一个基于 Proof-of-Antiquity（古董证明）共识机制的区块链网络。与传统的 Proof-of-Work 不同，RustChain 奖励使用老旧硬件的矿工，而非最新最快的设备。

作为节点运营商，您的职责包括：

- 运行 RustChain 全节点
- 验证交易和区块
- 为矿工提供 attestation（证明）服务
- 维护网络健康和去中心化

### 节点类型

| 节点类型 | 描述 | 奖励 |
|---------|------|------|
| 全节点 | 完整验证所有交易和区块 | 无直接奖励 |
| 证明节点 | 提供硬件指纹验证服务 | 网络费用分成 |
| 矿工节点 | 参与挖矿获得 RTC 奖励 | 区块奖励 |

---

## 系统要求

### 硬件要求

| 组件 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU | 双核 2.0 GHz | 四核 3.0 GHz+ |
| 内存 | 4 GB RAM | 8-16 GB RAM |
| 存储 | 50 GB SSD | 100 GB NVMe SSD |
| 网络 | 10 Mbps | 100 Mbps+ |
| 带宽 | 100 GB/月 | 500 GB+/月 |

### 支持的操作系统

- ✅ Ubuntu 20.04+, Debian 11+, Fedora 38+ (x86_64, ppc64le)
- ✅ macOS 12+ (Intel, Apple Silicon)
- ✅ IBM POWER8 系统
- ✅ Windows 10/11 (Python 3.8+)

### 软件依赖

- Python 3.10+
- Git
- systemd (Linux) 或 launchd (macOS)

---

## 快速开始

### 1. 安装 RustChain 矿工

```bash
# 一键安装（推荐）
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash

# 指定钱包名称安装
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-node-wallet

# 预览安装操作（不实际执行）
bash install-miner.sh --dry-run --wallet my-node-wallet
```

### 2. 验证安装

```bash
# 检查节点健康状态
curl -sk https://rustchain.org/health

# 查看当前 epoch
curl -sk https://rustchain.org/epoch

# 列出活跃矿工
curl -sk https://rustchain.org/api/miners
```

### 3. 启动挖矿

```bash
# Linux (systemd)
systemctl --user start rustchain-miner

# macOS (launchd)
launchctl start com.rustchain.miner
```

---

## 节点设置

### 步骤 1: 创建钱包

```bash
# 安装 clawrtc 库
pip install clawrtc

# 创建新钱包
clawrtc wallet create --name node-operator-wallet

# 显示钱包地址
clawrtc wallet show --name node-operator-wallet
```

### 步骤 2: 配置节点

创建配置文件 `~/.rustchain/config.toml`:

```toml
# 节点配置
[node]
wallet_name = "node-operator-wallet"
node_name = "My RustChain Node"
network = "mainnet"

# 挖矿设置
[mining]
enabled = true
auto_start = true
priority = "normal"  # low, normal, high

# 网络设置
[network]
rpc_port = 8545
ws_port = 8546
max_peers = 50

# 日志设置
[logging]
level = "info"  # debug, info, warn, error
file = "~/.rustchain/node.log"
max_size_mb = 100
backup_count = 5
```

### 步骤 3: 设置自动启动

#### Linux (systemd)

创建服务文件 `~/.config/systemd/user/rustchain-miner.service`:

```ini
[Unit]
Description=RustChain Miner Service
After=network.target

[Service]
Type=simple
ExecStart=/home/user/.rustchain/venv/bin/python -m clawrtc mine
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
```

启用服务：

```bash
# 重新加载 systemd
systemctl --user daemon-reload

# 启用开机自启
systemctl --user enable rustchain-miner

# 启动服务
systemctl --user start rustchain-miner

# 查看状态
systemctl --user status rustchain-miner
```

#### macOS (launchd)

创建 plist 文件 `~/Library/LaunchAgents/com.rustchain.miner.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rustchain.miner</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/user/.rustchain/venv/bin/python</string>
        <string>-m</string>
        <string>clawrtc</string>
        <string>mine</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/user/.rustchain/miner.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/user/.rustchain/miner.err</string>
</dict>
</plist>
```

加载服务：

```bash
# 加载配置
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist

# 启动服务
launchctl start com.rustchain.miner

# 查看状态
launchctl list | grep rustchain
```

---

## 配置详解

### 硬件指纹配置

RustChain 通过 6 项硬件检查来验证设备真实性：

```python
# ~/.rustchain/fingerprint_config.py

HARDWARE_CHECKS = {
    "clock_skew": {
        "enabled": True,
        "threshold_ms": 100,
        "description": "硅晶片老化模式检测"
    },
    "cache_timing": {
        "enabled": True,
        "levels": ["L1", "L2", "L3"],
        "description": "缓存延迟指纹"
    },
    "simd_identity": {
        "enabled": True,
        "detect": ["AltiVec", "SSE", "NEON"],
        "description": "SIMD 单元识别"
    },
    "thermal_drift": {
        "enabled": True,
        "sampling_interval_s": 60,
        "description": "热漂移熵检测"
    },
    "instruction_jitter": {
        "enabled": True,
        "iterations": 1000,
        "description": "微架构抖动画像"
    },
    "anti_emulation": {
        "enabled": True,
        "checks": ["VM", "Docker", "QEMU", "VirtualBox"],
        "description": "反虚拟化检测"
    }
}
```

### 古董倍数配置

硬件年代决定挖矿奖励倍数：

```toml
# ~/.rustchain/antiquity_multipliers.toml

[multipliers]
powerpc_g4 = 2.5      # 1999-2005
powerpc_g5 = 2.0      # 2003-2006
powerpc_g3 = 1.8      # 1997-2003
ibm_power8 = 1.5      # 2014
pentium_4 = 1.5       # 2000-2008
core_2_duo = 1.3      # 2006-2011
apple_silicon = 1.2   # 2020+
modern_x86 = 1.0      # 当前硬件

# 倍数每年衰减 15%
decay_rate = 0.15
```

### 网络配置

```toml
# ~/.rustchain/network.toml

[network]
# 主网节点
mainnet_nodes = [
    "https://rustchain.org",
    "https://rustchain-backup.org"
]

# 连接设置
max_connections = 100
connection_timeout_s = 30
read_timeout_s = 60

# 代理设置（可选）
# proxy = "http://localhost:7890"

# SSL 验证
verify_ssl = false  # 节点使用自签名证书
```

---

## 日常维护

### 每日检查清单

```bash
#!/bin/bash
# ~/.rustchain/scripts/daily-check.sh

echo "=== RustChain 节点日常检查 ==="
echo "日期：$(date)"
echo ""

# 1. 检查节点健康
echo "1. 节点健康状态:"
curl -sk https://rustchain.org/health | jq .

# 2. 检查钱包余额
echo -e "\n2. 钱包余额:"
curl -sk "https://rustchain.org/wallet/balance?miner_id=node-operator-wallet" | jq .

# 3. 检查服务状态
echo -e "\n3. 服务状态:"
systemctl --user status rustchain-miner --no-pager

# 4. 查看最新日志
echo -e "\n4. 最新日志 (最后 10 行):"
journalctl --user -u rustchain-miner -n 10 --no-pager

# 5. 检查磁盘空间
echo -e "\n5. 磁盘空间:"
df -h ~/.rustchain

# 6. 检查网络连接
echo -e "\n6. 网络延迟:"
curl -sk -o /dev/null -w "延迟：%{time_total}s\n" https://rustchain.org/health
```

### 每周维护任务

```bash
#!/bin/bash
# ~/.rustchain/scripts/weekly-maintenance.sh

echo "=== RustChain 周维护 ==="
echo "日期：$(date)"
echo ""

# 1. 清理旧日志
echo "1. 清理旧日志文件..."
find ~/.rustchain/logs -name "*.log" -mtime +7 -delete

# 2. 更新软件
echo -e "\n2. 更新 clawrtc..."
pip install --upgrade clawrtc

# 3. 备份配置
echo -e "\n3. 备份配置..."
cp -r ~/.rustchain/config ~/.rustchain/backup/config-$(date +%Y%m%d)

# 4. 重启服务（可选）
echo -e "\n4. 重启服务..."
systemctl --user restart rustchain-miner

# 5. 生成周报
echo -e "\n5. 生成周报..."
curl -sk "https://rustchain.org/api/miners" | jq '.[] | select(.wallet=="node-operator-wallet")' > ~/.rustchain/reports/weekly-$(date +%Y%m%d).json

echo -e "\n✅ 周维护完成!"
```

### 日志管理

```bash
# 查看实时日志
journalctl --user -u rustchain-miner -f

# 查看特定时间段日志
journalctl --user -u rustchain-miner --since "2026-03-12 00:00:00" --until "2026-03-12 23:59:59"

# 导出日志
journalctl --user -u rustchain-miner --since today > ~/rustchain-today.log

# 日志轮转配置
# /etc/logrotate.d/rustchain
~/.rustchain/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 user user
}
```

---

## 监控与告警

### 内置监控端点

```bash
# 节点健康
GET https://rustchain.org/health
# 响应：{"status": "healthy", "epoch": 12345, "peers": 42}

# 当前 epoch
GET https://rustchain.org/epoch
# 响应：{"epoch": 12345, "start_time": "...", "end_time": "..."}

# 矿工列表
GET https://rustchain.org/api/miners
# 响应：[{"wallet": "...", "hardware": "...", "multiplier": 2.5}]

# 钱包余额
GET https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET
# 响应：{"balance": 100.5, "pending": 2.3}
```

### Prometheus 监控配置

```yaml
# ~/.rustchain/monitoring/prometheus.yml

global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'rustchain-node'
    static_configs:
      - targets: ['localhost:8545']
    metrics_path: '/metrics'

  - job_name: 'rustchain-network'
    static_configs:
      - targets: ['rustchain.org:443']
    metrics_path: '/health'
```

### Grafana 仪表板

导入以下仪表板 ID 或创建自定义面板：

1. **节点健康概览**
   - 在线状态
   - 连接数
   - 响应时间

2. **挖矿性能**
   - 每个 epoch 的收益
   - 硬件倍数
   - 累计奖励

3. **系统资源**
   - CPU 使用率
   - 内存使用率
   - 磁盘空间
   - 网络带宽

### 告警规则

```yaml
# ~/.rustchain/monitoring/alerts.yml

groups:
  - name: rustchain
    rules:
      - alert: NodeDown
        expr: up{job="rustchain-node"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "RustChain 节点宕机"
          description: "节点 {{ $labels.instance }} 已离线超过 5 分钟"

      - alert: LowDiskSpace
        expr: node_filesystem_avail_bytes{mountpoint="/"} < 10737418240
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "磁盘空间不足"
          description: "可用空间少于 10GB"

      - alert: MiningRewardDrop
        expr: delta(rustchain_mining_rewards_total[1h]) < 0.1
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "挖矿奖励异常下降"
          description: "过去 1 小时奖励低于预期"
```

### 告警通知配置

#### 邮件通知

```yaml
# ~/.rustchain/monitoring/alertmanager.yml

route:
  receiver: 'email-notifications'
  group_by: ['alertname']
  group_wait: 30s
  group_interval: 5m

receivers:
  - name: 'email-notifications'
    email_configs:
      - to: 'your-email@example.com'
        from: 'alertmanager@rustchain.org'
        smarthost: 'smtp.example.com:587'
        auth_username: 'your-email@example.com'
        auth_password: 'your-password'
```

#### 飞书/钉钉 webhook

```yaml
receivers:
  - name: 'feishu-webhook'
    webhook_configs:
      - url: 'https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK_ID'
        send_resolved: true
```

---

## 故障排查

### 常见问题及解决方案

#### 1. 矿工无法启动

```bash
# 检查 Python 版本
python3 --version  # 需要 3.10+

# 检查依赖
pip list | grep clawrtc

# 重新安装
pip install --upgrade --force-reinstall clawrtc

# 查看详细错误
journalctl --user -u rustchain-miner -n 50 --no-pager
```

#### 2. 钱包余额显示为 0

```bash
# 验证钱包名称
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET"

# 检查矿工是否活跃
curl -sk https://rustchain.org/api/miners | jq '.[] | select(.wallet=="YOUR_WALLET")'

# 等待至少一个 epoch（10 分钟）后余额才会更新
```

#### 3. HTTPS 证书错误

```bash
# 使用 -sk 标志跳过证书验证
curl -sk https://rustchain.org/health

# 或在配置中设置
# ~/.rustchain/config.toml
[network]
verify_ssl = false
```

#### 4. 硬件指纹验证失败

```bash
# 运行诊断
clawrtc diagnose --full

# 检查是否运行在虚拟机中
# RustChain 会检测并降低 VM 的奖励
systemd-detect-virt  # Linux
system_profiler SPHardwareDataType  # macOS

# 如果是真实硬件但验证失败，提交 issue 并附上诊断日志
```

#### 5. 网络连接问题

```bash
# 测试连通性
ping rustchain.org

# 测试端口
telnet rustchain.org 443

# 检查防火墙
sudo ufw status  # Linux
sudo pfctl -s rules  # macOS

# 使用代理（如果需要）
export http_proxy=http://localhost:7890
export https_proxy=http://localhost:7890
```

### 日志分析

```bash
# 查找错误
journalctl --user -u rustchain-miner | grep -i error

# 查找警告
journalctl --user -u rustchain-miner | grep -i warn

# 查找连接问题
journalctl --user -u rustchain-miner | grep -i "connection\|network\|timeout"

# 导出日志进行分析
journalctl --user -u rustchain-miner --since yesterday > debug.log
```

### 性能优化

```bash
# 监控资源使用
top -p $(pgrep -f clawrtc)  # Linux
htop  # 需要安装

# 调整进程优先级
renice -n 10 -p $(pgrep -f clawrtc)

# 限制 CPU 使用（systemd）
# ~/.config/systemd/user/rustchain-miner.service
[Service]
CPUQuota=50%
MemoryMax=2G
```

---

## 安全最佳实践

### 1. 钱包安全

```bash
# 永远不要分享私钥
# 定期备份钱包文件
cp -r ~/.rustchain/wallets ~/secure-backup/location

# 使用强密码加密钱包
clawrtc wallet encrypt --name node-operator-wallet

# 考虑使用硬件钱包存储大额 RTC
```

### 2. 网络安全

```toml
# ~/.rustchain/security.toml

[firewall]
# 仅开放必要端口
allowed_ports = [8545, 8546]

# 限制连接速率
rate_limit_per_minute = 100

# IP 白名单（可选）
# whitelist = ["192.166.1.0/24"]

[ssl]
# 使用自签名证书
cert_file = "~/.rustchain/ssl/cert.pem"
key_file = "~/.rustchain/ssl/key.pem"
```

### 3. 系统加固

```bash
# 禁用 root SSH 登录
sudo sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config

# 启用防火墙
sudo ufw enable
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 8545/tcp  # RustChain RPC

# 定期更新系统
sudo apt update && sudo apt upgrade -y  # Debian/Ubuntu
sudo dnf update -y  # Fedora

# 安装入侵检测
sudo apt install fail2ban -y
```

### 4. 监控异常活动

```bash
#!/bin/bash
# ~/.rustchain/scripts/security-monitor.sh

# 监控异常登录
lastb | head -20

# 检查异常进程
ps aux | grep -v grep | grep clawrtc

# 监控网络连接
netstat -tulpn | grep 8545

# 检查日志中的可疑活动
grep -i "failed\|unauthorized\|attack" ~/.rustchain/logs/*.log
```

### 5. 备份策略

```bash
#!/bin/bash
# ~/.rustchain/scripts/backup.sh

BACKUP_DIR=~/backups/rustchain-$(date +%Y%m%d-%H%M%S)
mkdir -p $BACKUP_DIR

# 备份钱包
cp -r ~/.rustchain/wallets $BACKUP_DIR/

# 备份配置
cp -r ~/.rustchain/config $BACKUP_DIR/

# 备份密钥
cp ~/.rustchain/*.key $BACKUP_DIR/ 2>/dev/null

# 压缩备份
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

# 上传到远程存储（可选）
# rsync -avz $BACKUP_DIR.tar.gz user@backup-server:/backups/

echo "备份完成：$BACKUP_DIR.tar.gz"
```

---

## 常见问题

### Q1: 挖矿收益如何计算？

**A:** 收益 = 基础奖励 × 古董倍数 × (1 - 衰减率)^年数

示例：
- G4 Mac (2.5×) 使用 3 年：2.5 × (0.85)^3 ≈ 1.54×
- 每个 epoch 基础奖励：0.12 RTC
- 实际收益：0.12 × 1.54 ≈ 0.185 RTC/epoch

### Q2: 为什么我的硬件倍数比别人低？

**A:** 可能原因：
1. 硬件较新（倍数自然较低）
2. 倍数衰减（每年 15%）
3. 被检测为虚拟机（大幅降低）
4. 硬件指纹验证失败

### Q3: 如何最大化收益？

**A:** 建议：
1. 使用真实的老硬件（PowerPC G4/G5 最佳）
2. 保持节点持续在线
3. 定期维护避免故障
4. 参与治理投票获得额外奖励

### Q4: 节点需要 24 小时在线吗？

**A:** 是的，离线期间：
- 无法获得挖矿奖励
- 可能影响网络健康度
- 重新上线需要重新验证

### Q5: 如何提取/转移 RTC？

**A:** 
```bash
# 查看余额
clawrtc wallet balance

# 转账
clawrtc wallet send --to RECIPIENT_ADDRESS --amount 10

# 桥接到 Solana（wRTC）
clawrtc bridge --to solana --amount 10
```

### Q6: 遇到技术问题时如何获取帮助？

**A:** 
1. 查看文档：https://rustchain.org/docs
2. 加入 Discord: https://discord.gg/VqVVS2CW9Q
3. 提交 GitHub Issue: https://github.com/Scottcjn/Rustchain/issues
4. 查看赏金任务：https://github.com/Scottcjn/rustchain-bounties/issues

---

## 附录

### A. 快速命令参考

```bash
# 服务管理
systemctl --user start|stop|restart|status rustchain-miner

# 日志查看
journalctl --user -u rustchain-miner -f

# 钱包操作
clawrtc wallet create|show|balance|send

# 节点查询
curl -sk https://rustchain.org/health
curl -sk https://rustchain.org/epoch
curl -sk https://rustchain.org/api/miners
curl -sk "https://rustchain.org/wallet/balance?miner_id=WALLET"

# 区块浏览器
open https://rustchain.org/explorer
```

### B. 资源链接

| 资源 | 链接 |
|------|------|
| 官方网站 | https://rustchain.org |
| 区块浏览器 | https://rustchain.org/explorer |
| GitHub 仓库 | https://github.com/Scottcjn/Rustchain |
| 赏金任务 | https://github.com/Scottcjn/rustchain-bounties |
| Discord 社区 | https://discord.gg/VqVVS2CW9Q |
| 文档 | https://rustchain.org/docs |
| wRTC (Solana) | 12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X |

### C. 贡献与奖励

| 贡献类型 | 奖励 (RTC) | 链接 |
|---------|-----------|------|
| 文档改进 | 10-25 | [#72](https://github.com/Scottcjn/rustchain-bounties/issues/72) |
| Bug 修复 | 20-50 | 查看 open issues |
| 新功能 | 50-100 | 查看 open issues |
| 安全审计 | 100-150 | 联系核心团队 |

---

**最后更新：** 2026-03-12  
**版本：** 1.0  
**维护者：** RustChain 社区

---

*本指南由 AI 助手生成，经人工审核。如有错误或遗漏，请提交 PR 改进。*
