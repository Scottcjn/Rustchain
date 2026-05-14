# RustChain 节点运维指南 (NODE_OPERATOR_GUIDE.md)

> **适用版本**: RustChain v1.1.0+  
> **共识协议**: RIP-200 (Proof-of-Antiquity)  
> **文档定位**: 面向 DePIN 节点运维工程师、基础设施管理员与复古硬件矿机部署者

---

## 1. 什么是 Attestation Node？

在 RustChain 的 RIP-200 共识架构中，网络角色被严格划分为 **Miner（物理矿机）** 与 **Attestation Node（认证节点）**。理解两者的边界是高效运维的前提。

**Attestation Node 是网络的去中心化验证中枢**。它不直接参与底层硅晶振荡或热力学熵值的采集，而是负责：
- **接收与解析指纹**：监听全网矿工提交的硬件指纹（包含时钟偏移、缓存时序、SIMD 特征、热熵曲线、指令抖动等 6 项指标）。
- **反虚拟化校验**：通过 AI 特征库与已知物理硬件 Profile 进行交叉比对，拦截 Docker/VM/QEMU/云主机模拟层。仅允许真实物理硅片通过。
- **Epoch 周期管理**：维护每个 Epoch（144 slots）的矿工注册表、权重计算与奖励分配池（Epoch Pot）。
- **链下结算与链上锚定**：在 Slot 144 触发结算后，生成 Merkle Root 并将其最终状态锚定至 Ergo 主链，确保账本不可篡改。

运维 Attestation Node 要求高可用、低延迟网络与稳定的时序同步服务（NTP/Chrony）。它是 RustChain DePIN 网络的“信任路由器”，直接决定整个网络的出块稳定性与反作弊能力。

---

## 2. 硬件要求

RustChain 的硬件策略具有双重性：**矿机追求复古物理特性，节点追求现代计算与网络稳定性**。

### 2.1 Attestation Node / 全节点硬件基准
| 组件 | 推荐配置 | 说明 |
|------|----------|------|
| **CPU** | x86_64 / ARM64，4 核以上 | 需支持高强度加密验签与 AI 指纹匹配计算 |
| **内存** | ≥ 8 GB DDR4 | Epoch 状态缓存与并发连接池占用较高 |
| **存储** | 512 GB NVMe SSD | 区块数据库、Ergo 锚定日志、反欺诈特征库需高 IOPS |
| **网络** | 上行 ≥ 100 Mbps，延迟 < 50ms | 需维持全球矿工长连接与 P2P 广播 |
| **操作系统** | Ubuntu 22.04 LTS / Debian 12 | 推荐内核 5.15+，启用硬件时钟优化 |

### 2.2 Miner（DePIN 物理矿机）建议
- **高收益设备**：PowerBook G4 (2003)、Power Mac G5、Intel 486、早期 Pentium III/4。
- **核心要求**：必须运行于裸机（Bare-metal），禁用所有虚拟化扩展（VT-x/AMD-V），关闭 CPU 节能降频（C-States/P-States），确保时钟晶振自然老化特征暴露。
- **⚠️ 注意**：Docker/VM 内运行虽可通，但 RIP-200 协议会触发 `VM_DETECTED` 标记，奖励系数强制降至 `0.3x`。追求完整 `RTC` 收益请务必使用物理直连。

---

## 3. 安装和配置

### 3.1 环境依赖准备
```bash
# 系统级工具（时钟同步、硬件探测、编译链）
sudo apt update && sudo apt install -y git build-essential curl chrony dmidecode smartmontools python3.11 python3.11-venv

# 同步系统时钟（RIP-200 对时钟偏移极其敏感）
sudo systemctl enable --now chronyd
sudo chronyc makestep
```

### 3.2 源码部署与虚拟环境
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.3 节点配置参数
节点核心配置通过环境变量或 `config.yaml` 注入：
```yaml
# config.yaml 示例
network:
  node_url: "https://rustchain.org"
  block_time: 600          # 区块目标时间（秒）
  epoch_slots: 144         # RIP-200 Epoch 周期

attestation:
  ai_profile_version: "v2.1.0"
  vm_sensitivity: "strict" # strict / moderate / relaxed
  anchor_chain: "ergo"

wallet:
  keystore_path: "./data/wallet"
  min_confirmations: 3
```
启动前务必检查时区与硬件时钟同步状态：`timedatectl status` 与 `sudo hwclock --show`。

---

## 4. Docker 运行指南

RustChain 提供官方容器化方案，适合快速部署测试环境或受控生产集群。**再次强调：容器内运行将因硬件抽象层（HAL）拦截而触发降权奖励。**

### 4.1 构建镜像
```bash
docker build \
  --build-arg MINER_TYPE=linux \
  --build-arg MINER_ARCH=x86_64 \
  -t rustchain/miner:latest \
  -f Dockerfile.miner .
```

### 4.2 启动容器
```bash
docker run -d \
  --name rustchain-miner \
  --restart unless-stopped \
  --cap-add SYS_RAWIO \          # 允许底层硬件时钟读取
  --security-opt apparmor:unconfined \
  -e WALLET_NAME="your_erc20_or_rust_wallet" \
  -e NODE_URL="https://rustchain.org" \
  -e BLOCK_TIME=600 \
  -v /data/rustchain/wallet:/app/wallet:rw \
  -v /data/rustchain/logs:/app/logs:rw \
  rustchain/miner:latest
```

### 4.3 容器运维要点
- **健康检查**：内置 `HEALTHCHECK` 每 5 分钟探测 `${NODE_URL}/health`，失败 3 次自动标记 Unhealthy。
- **硬件直通**：若需在 Docker 中获得接近裸机的表现，建议添加 `--device /dev/rtc0` 与 `--privileged`（仅限测试，生产环境慎用）。
- **日志轮转**：配置 `logrotate` 挂载目录，防止 `docker logs` 占满磁盘。

---

## 5. 监控和维护

### 5.1 核心指标采集
建议使用 Prometheus + Grafana 搭建监控面板。暴露以下关键 Metrics：
- `attestation_submissions_total`：认证提交总量
- `vm_detection_rejects`：反虚拟化拦截次数
- `epoch_current_slot`：当前 Epoch Slot 进度（0~143）
- `thermal_entropy_drift`：热熵曲线标准差
- `clock_skew_ms`：晶振偏移量（应维持在 1.5~8.0ms 为佳）

### 5.2 周期性维护
1. **Epoch 结算验证**：每 144 Slot（约 24 小时）结束后，核对 `ergo_anchor_tx` 哈希是否与 Ergo 区块浏览器一致。
2. **特征库更新**：每周执行 `git pull origin main` 获取最新 `ai_profiles/`，确保新型虚拟机逃逸特征被收录。
3. **钱包与密钥备份**：将 `wallet/keystore` 目录冷备份至离线介质。RustChain 采用非对称签名，私钥丢失将永久丧失 `RTC` 领取权。
4. **日志审计**：定期巡检 `/app/logs/attestation.log`，过滤 `WARN` 与 `ERROR` 级别，重点关注 `FINGERPRINT_INVALID` 与 `ANCHOR_TIMEOUT`。

### 5.3 安全基线
- 禁用 SSH 密码登录，强制使用 ED25519 密钥。
- 防火墙仅放行 `TCP 8080`（Attestation API）、`TCP 8090`（P2P Sync）与 `TCP 9100`（Prometheus）。
- 启用 `fail2ban` 拦截异常高频请求（防 DDoS 与指纹伪造刷量）。

---

## 6. 故障排查

| 错误代码/现象 | 可能原因 | 排查与修复步骤 |
|---------------|----------|----------------|
| `VM_DETECTED` | 运行于 Hypervisor/WSL/Docker 抽象层；BIOS 开启虚拟化；系统时钟被 NTP 强锁 | 1. 关闭 BIOS 的 `Intel VT-x/AMD-V`<br>2. 检查 `systemd-detect-virt` 输出是否为 `none`<br>3. 改用裸机或直通 PCIe 物理网卡/时钟卡 |
| `CLOCK_SKEW_OUT_OF_RANGE` | NTP 同步过于完美或主板晶振老化严重偏移 | 1. 停止 `chrony`，改用 `ntpdate -u pool.ntp.org` 手动校准<br>2. 在 BIOS 调整 `HPET` 设置<br>3. 接受复古硬件的自然漂移（协议奖励区间内即可） |
| `CACHE_TIMING_FLAT` | L1/L2 延迟曲线过于平滑，疑似模拟或容器资源隔离干扰 | 1. 禁用 CPU 调度器节能策略 `echo performance > /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`<br>2. 检查 `dmidecode -t cache` 输出是否完整 |
| `EPOCH_POT_SETTLEMENT_FAILED` | 节点网络波动或 Ergo 锚定 Gas 不足 | 1. 检查出站 RPC 节点连通性 `curl -v https://rustchain.org/anchor/status`<br>2. 查看 `ergo_anchor.log` 确认签名与手续费<br>3. 重启服务前执行 `docker exec rustchain-miner python3 wallet/recover_epoch.py` |
| 奖励未到账 | 钱包未注册 / Epoch 内未保持在线 > 70% Slot | 1. 验证 `WALLET_NAME` 是否已绑定至 Explorer<br>2. 检查运行时长覆盖率 `uptime_percentage = online_slots / 144`<br>3. 确认未触发 `ANTI_SPAM_THROTTLE` 限速规则 |

### 高级调试指令
```bash
# 查看实时硬件指纹生成过程（仅调试模式）
RUSTCHAIN_DEBUG=1 python3 miners/linux/rustchain_linux_miner.py --verbose

# 验证系统底层时钟精度
hwclock --verbose --debug

# 检查 CPU 微指令与 SIMD 扩展暴露状态
lscpu | grep -E "Model|Flags|Architecture|Virtualization"

# 提取 Epoch 结算 Merkle Root
curl -s https://rustchain.org/api/v1/epoch/latest/merkle | jq
```

---

> **运维箴言**：RustChain 的共识哲学是“时间赋予硅片价值，物理对抗虚拟化”。优秀的节点运维不在于追求极限算力，而在于保持硬件指纹的真实性、网络通信的稳定性与 Epoch 结算的严谨性。遵循本指南操作，可确保您的节点在 DePIN 生态中获得稳定 `RTC` 收益，并为复古硬件复兴运动提供坚实基础设施。  
> 📜 *Whitepaper Reference: `docs/RustChain_Whitepaper_Flameholder_v0.97.pdf`*  
> 🔗 *Explorer: `https://rustchain.org/explorer/`*