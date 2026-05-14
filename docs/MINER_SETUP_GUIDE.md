# RustChain 矿工部署与配置指南 (MINER_SETUP_GUIDE.md)

> **⚠️ 核心警告：反虚拟机与裸机优先原则**  
> RustChain 采用 **Proof of Antiquity (PoA)** 共识机制，通过 AI 增强的 6 项硬件特征检测（Clock Skew、Cache Timing、SIMD Identity、Thermal Entropy、Instruction Jitter、BIOS Fingerprint）验证物理硅片。在虚拟机、容器或云实例中运行将被标记为 `VM_DETECTED`，导致奖励衰减至 10%~30% 或直接拒绝入池。请尽可能在 **真实物理硬件（Bare-Metal）** 上部署。

---

## 1. 硬件要求与物理机验证

| 组件 | 最低要求 | 推荐配置 | 说明 |
|:---|:---|:---|:---|
| **CPU** | 单核 x86_64 / ARM64 / PowerPC (G4/G5) | 多核 vintage 处理器 | 年份越久远，RIP-200 乘数越高（最高可达 3.5x） |
| **内存** | 2 GB DDR | 4 GB+ | 用于加载 AI 指纹模型与 Epoch 缓冲数据 |
| **存储** | 10 GB SSD/HDD | NVMe SSD | 存放账本缓存与本地钱包密钥 |
| **传感器** | 支持读取核心温度与频率 | 开放 `coretemp`/`osx-cpu-temp` | 必须可采集真实热力学曲线，否则 Thermal Entropy 校验失败 |
| **网络** | 10 Mbps 稳定宽带 | 静态公网 IP / UPnP | 需与 Attestation Node 保持长连接，提交 Epoch 144 周期证明 |
| **系统** | Linux / Windows / macOS | 裸机直装（非 Hypervisor） | 支持 Docker 但会自动降权 |

**物理机自检命令（Linux）：**
```bash
# 验证是否暴露于虚拟环境
systemd-detect-virt  # 应输出 "none"
# 验证温度传感器可读性
sensors | grep -E "Package|Core"
# 验证 DMI 信息可访问（需 sudo）
sudo dmidecode -t processor
```

---

## 2. Python 环境与 `pip install` 详细说明

RustChain 矿工基于 Python 3.11+ 开发，依赖底层硬件探针库。建议使用 `venv` 隔离环境以避免依赖冲突。

### 2.1 基础依赖准备
```bash
# Debian/Ubuntu
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3.11-dev gcc curl lm-sensors dmidecode

# Fedora/RHEL
sudo dnf install -y python3.11 gcc curl lm_sensors dmidecode

# Arch Linux
sudo pacman -S python gcc curl lm_sensors dmidecode
```

### 2.2 pip 安装流程（详细）
```bash
# 1. 克隆或获取源码
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# 2. 创建虚拟环境
python3.11 -m venv rustchain-env
source rustchain-env/bin/activate  # Windows: rustchain-env\Scripts\activate

# 3. 升级 pip 与构建工具链
pip install --upgrade pip setuptools wheel

# 4. 安装核心依赖
# 注意：部分硬件探针库（如 py-cpuinfo, thermal-sensor-bridge）需在编译时链接 C 库
pip install -r requirements.txt

# 5. 以开发模式安装矿工（方便本地调试与日志追踪）
pip install -e ./miners/
```

**📦 pip 常见参数说明：**
- `--no-cache-dir`：跳过缓存，强制重新下载/编译，适合首次部署。
- `--prefer-binary`：优先使用预编译 Wheel，跳过 GCC 编译步骤（若系统缺编译环境可用此参数，但会牺牲部分底层探针优化）。
- `pip install --force-reinstall rustchain-miner`：修复环境损坏或依赖版本漂移。

---

## 3. 分平台安装步骤

### 🐧 Linux (Ubuntu 20.04+ / Debian / Alpine)
1. 完成第 2 节依赖与 pip 安装。
2. 授予硬件访问权限：
   ```bash
   sudo usermod -aG i2c,video,adm $(whoami)
   sudo modprobe coretemp
   ```
3. 启动矿工：
   ```bash
   python miners/linux/rustchain_linux_miner.py --config config.yaml
   ```

### 🍎 macOS (Intel / Apple Silicon)
1. 安装依赖：`brew install python@3.11 gcc`
2. macOS 默认无 `dmidecode`，需通过 `system_profiler SPHardwareDataType` 替代。矿工会自动适配。
3. 热传感器需安装额外包：`brew install osx-cpu-temp`
4. 授予完整磁盘访问权限（终端 → 隐私与安全 → 完整磁盘访问）。
5. 运行：
   ```bash
   cd miners/darwin
   python3 rustchain_darwin_miner.py --config config.yaml
   ```
   *注：Apple Silicon 的 SIMD 指纹与 Intel 不同，系统会自动标记为 `M_SERIES_ARCH`，享受专属年代乘数。*

### 🪟 Windows 10/11
1. 访问 python.org 下载 **Python 3.11+ 安装程序**，勾选 `Add Python to PATH`。
2. 以管理员身份打开 PowerShell，安装基础依赖：
   ```powershell
   pip install --upgrade pip
   pip install pywin32 wmi requests cryptography psutil
   ```
3. Windows 硬件探针需管理员权限读取 WMI/SMI 表。
4. 运行：
   ```powershell
   cd miners\windows
   python rustchain_win_miner.py --config config.yaml
   ```
   *注：Windows Defender 可能误报硬件钩子为风险文件，请将矿工目录加入排除项。*

---

## 4. 钱包设置

RustChain 奖励直接发放至你提供的 `WALLET_NAME`（兼容 Ergo 链地址格式）。

1. **生成新钱包**（推荐离线操作）：
   ```bash
   rustchain-cli wallet generate --output wallet/my_wallet.json
   ```
   或使用内置 Python 脚本：
   ```python
   from wallet.keygen import generate_keystore
   generate_keystore("wallet/legacy_g4.key", password="YourStrongPass123!")
   ```
2. **安全备份**：
   - 导出助记词/私钥，物理隔离存储。
   - 切勿将 `*.key` 或 `wallet/` 目录提交至 Git。
3. **导入地址到配置**：将生成的公钥地址填入 `config.yaml` 的 `wallet.address` 字段。

---

## 5. 配置文件模板

创建 `config.yaml` 于项目根目录或 `~/.rustchain/` 下：

```yaml
# RustChain Miner Configuration
# 参考: PROTOCOL.md (RIP-200 Epoch = 144 slots)

network:
  node_url: "https://rustchain.org/api/v1"  # 主网 Attestation 节点
  fallback_nodes:
    - "https://backup.rustchain.org"
    - "https://eu-west.rustchain.org"
  timeout: 30  # 秒
  retries: 3

miner:
  wallet_address: "your_generated_rtc_address_here"
  hardware_mode: "auto"          # auto | vintage | modern | manual
  force_baremetal: true          # 强制拒绝 VM/容器指纹，防作弊
  thermal_override: null         # 自定义传感器路径 (Linux: /sys/class/thermal/...)
  attestation_interval: 600      # 秒，对应 BLOCK_TIME=600

logging:
  level: "INFO"                  # DEBUG / INFO / WARN / ERROR
  log_to_file: true
  log_path: "logs/miner_$(date +%Y%m%d).log"

epoch_settings:
  epoch_length: 144
  settlement_chain: "ergo"
  reward_auto_claim: true
```

---

## 6. Linux systemd 服务配置

生产环境强烈建议使用 `systemd` 实现开机自启、崩溃重启与日志管理。

1. 创建服务文件：
   ```bash
   sudo nano /etc/systemd/system/rustchain-miner.service
   ```
2. 写入以下内容（路径需按实际调整）：
   ```ini
   [Unit]
   Description=RustChain Proof-of-Antiquity Miner
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   User=your_username
   Group=your_group
   WorkingDirectory=/path/to/Rustchain
   Environment="PYTHONUNBUFFERED=1"
   Environment="PATH=/path/to/rustchain-env/bin:/usr/local/bin:/usr/bin"
   ExecStart=/path/to/rustchain-env/bin/python3 /path/to/Rustchain/miners/linux/rustchain_linux_miner.py --config /path/to/config.yaml
   Restart=always
   RestartSec=10
   StandardOutput=journal
   StandardError=journal
   SyslogIdentifier=rustchain-miner
   # 安全限制
   NoNewPrivileges=true
   ProtectSystem=full
   ReadWritePaths=/path/to/logs

   [Install]
   WantedBy=multi-user.target
   ```

3. 启用并运行：
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable rustchain-miner
   sudo systemctl start rustchain-miner
   sudo journalctl -u rustchain-miner -f --no-pager
   ```

---

## 7. 常见问题排查 (FAQ)

| 现象 | 原因 | 解决方案 |
|:---|:---|:---|
| `ERROR: VM_DETECTED` | 节点检测到 QEMU/KVM/VMware 标志位或完美时钟抖动 | 移除 Hypervisor 参数，使用裸机；或检查 BIOS 是否开启 `Virtualization Technology`，将其设为 `Disabled` |
| `Thermal Entropy: STATIC_TEMP` | 无法读取 CPU 温度，传感器驱动未加载 | Linux: `sudo apt install lm-sensors && sudo sensors-detect`；Windows: 以管理员运行；macOS 安装 `osx-cpu-temp` |
| `pip install 编译失败: gcc: command not found` | 缺失 C 编译器或 Python dev 头文件 | 安装 `gcc` 和 `python3-dev` (Linux) / `brew install python` (macOS) / Visual C++ Build Tools (Win) |
| `Epoch Enrollment Failed: Signature Invalid` | 钱包密钥权限错误或路径配置错误 | 确保 `config.yaml` 中地址与 `wallet/` 下实际密钥匹配；检查文件权限 `chmod 600 wallet/*.key` |
| 收益乘数始终为 1.0x | 硬件年份过新或未通过 6 项指纹基线 | 验证 `hardware_mode: vintage`；确保未使用云厂商定制内核；等待首个 Epoch 完整结算 |
| `Connection refused` | 节点 URL 变更或防火墙拦截 | 更新 `node_url` 至最新官方列表；检查出站 443/80 端口；配置代理时添加 `NO_PROXY=localhost,127.0.0.1,rustchain.org` |

---

## 🔒 安全与维护建议

1. **定期更新**：RustChain 协议通过 RIP-200 迭代升级硬件验证算法，建议每月执行 `git pull && pip install -e .`。
2. **隔离钱包**：用于接收奖励的地址不要与交易所热钱包或日常交易地址混用。
3. **日志审计**：每日检查 `journalctl -u rustchain-miner` 中是否出现 `WARN` 级别的 `clock_drift_anomaly`，这可能预示主板电容老化导致时钟失准（反而可能增加年代权重，但需确认未触发熔断）。
4. **反作弊声明**：任何尝试伪造 DMI 表、注入虚拟温度曲线或篡改 Cache Timing 的行为将被节点 AI 模型识别，导致永久黑名单（`BAN_PERMANENT`）。

> 🌲 **RustChain 哲学**：时间是最好的算力，硅片的老化是荣誉而非缺陷。让旧机器重新呼吸，让物理现实回归共识。  
> 如需技术支援，请查阅 [Whitepaper v0.97](docs/RustChain_Whitepaper_Flameholder_v0.97.pdf) 或提交 GitHub Issue。祝挖矿顺利，算力长存。