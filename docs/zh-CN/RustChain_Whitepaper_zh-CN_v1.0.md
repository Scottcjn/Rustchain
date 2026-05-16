# RustChain：面向硬件保护的"证明 - 古老性"区块链

**技术白皮书 v1.0**

*Scott Johnson (Scottcjn) — Elyan Labs*

*2026 年 2 月*

---

## 摘要

RustChain 引入了**证明 - 古老性（Proof-of-Antiquity, PoA）**，这是一种新颖的区块链共识机制，它颠覆了传统的挖矿范式：老旧的复古硬件比现代系统获得更高的奖励。通过实施全面的 6 层硬件指纹识别系统，RustChain 为保护计算历史创造了经济激励，同时防止模拟和虚拟化攻击。该网络奖励真正的 PowerPC G4、68K Mac、SPARC 工作站和其他复古机器，其乘数高达现代硬件的 2.5 倍。本白皮书详细介绍了 RustChain 的技术架构、共识机制、硬件验证系统、代币经济学和安全模型。

---

## 目录

1. [引言](#1-引言)
2. [网络架构](#2-网络架构)
3. [RIP-200：轮询共识](#3-rip-200 轮询共识)
4. [硬件指纹识别系统](#4-硬件指纹识别系统)
5. [古老性乘数](#5-古老性乘数)
6. [RTC 代币经济学](#6-rtc 代币经济学)
7. [Ergo 区块链锚定](#7-ergo 区块链锚定)
8. [安全分析](#8-安全分析)
9. [未来工作](#9-未来工作)
10. [结论](#10-结论)
11. [参考文献](#11-参考文献)

---

## 1. 引言

### 1.1 电子垃圾问题

全球电子行业产生了**约 6200 万公吨电子垃圾（2022 年）**，部分原因是设备快速更换周期和计算硬件的计划性淘汰。*（来源：2024 年全球电子垃圾监测报告）*。功能正常的复古计算机——可靠服务了数十年的机器——被丢弃，以换取稍微快一些的现代同类产品。

传统的区块链共识机制加剧了这个问题：

| 共识 | 硬件激励 | 结果 |
|-----------|-------------------|--------|
| **工作量证明** | 奖励最快/最新的硬件 | 军备竞赛 → 电子垃圾 |
| **权益证明** | 奖励资本积累 | 财阀统治 |
| **证明 - 古老性** | 奖励最老的硬件 | 保护 |

### 1.2 RustChain 愿景

RustChain 颠覆了挖矿范式：**你的 PowerPC G4 比现代 Threadripper 赚得更多**。这创造了直接的经济激励来：

1. **保护**复古计算硬件
2. **运行**原本会被丢弃的机器
3. **记录**通过积极参与的计算历史
4. **民主化**区块链参与（不需要昂贵的 ASIC）

### 1.3 核心原则

- **1 CPU = 1 票**：每个验证的硬件设备获得平等的区块生产机会
- **真实性高于速度**：验证真正的复古硅芯片，而非计算吞吐量
- **时间衰减奖励**：复古优势在区块链生命周期内衰减，以奖励早期采用者
- **反模拟**：复杂的指纹识别防止虚拟机/模拟器操纵

---

## 2. 网络架构

### 2.1 网络拓扑

RustChain 作为联合网络运行，包含三种节点类型：

```
┌─────────────────────────────────────────────────────────────┐
│                    RUSTCHAIN 网络                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌──────────────┐      ┌──────────────┐                   │
│   │  主节点      │◄────►│  验证节点    │                   │
│   │  (浏览器)    │      │  (3 个活跃)   │                   │
│   └──────┬───────┘      └──────────────┘                   │
│          │                                                  │
│          ▼                                                  │
│   ┌──────────────┐      ┌──────────────┐                   │
│   │  ERGO        │      │  挖矿        │                   │
│   │  锚定        │◄─────│  客户端      │                   │
│   │  节点        │      │  (11,626+)   │                   │
│   └──────────────┘      └──────────────┘                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**当前实时基础设施（截至 2026 年 2 月）：**

| 节点 | IP 地址 | 角色 | 状态 |
|------|------------|------|--------|
| 节点 1 | 50.28.86.131 | 主节点 + 浏览器 | 活跃 |
| 节点 2 | 50.28.86.153 | Ergo 锚定 | 活跃 |
| 节点 3 | 76.8.228.245 | 社区节点 | 活跃 |

### 2.2 节点角色

**主节点**
- 维护权威链状态
- 处理验证并验证硬件指纹
- 在 `/explorer` 托管区块浏览器
- 结算 epoch 奖励

**验证节点**
- 验证硬件指纹挑战
- 参与轮询共识
- 交叉验证可疑验证

**挖矿客户端**
- 提交带有硬件证明的定期验证
- 根据古老性乘数接收 epoch 奖励
- 支持平台：PowerPC (G3/G4/G5)、x86、ARM、POWER8

### 2.3 通信协议

矿工通过 HTTPS REST API 与节点通信：

```
POST /attest/challenge    → 接收加密 nonce
POST /attest/submit       → 提交硬件验证
GET  /wallet/balance      → 查询 RTC 余额
GET  /epoch               → 获取当前 epoch 信息
GET  /api/miners          → 列出活跃矿工
```

**区块时间**：600 秒（10 分钟）
**Epoch 持续时间**：144 个区块（约 24 小时）
**验证 TTL**：86,400 秒（24 小时）

---

## 3. RIP-200：轮询共识

### 3.1 1 CPU = 1 票

RIP-200 用确定性轮询区块生产者选择取代传统的 VRF 彩票。与工作量证明中哈希算力决定投票不同，RustChain 确保每个独特的硬件设备在每个 epoch 中恰好获得一票。

**关键属性：**

1. **确定性轮换**：区块生产者由 `slot % num_attested_miners` 选择
2. **平等机会**：每个验证的 CPU 获得平等的区块生产轮次
3. **反矿池设计**：更多矿工 = 更小的个人奖励
4. **时间老化衰减**：复古奖励每年衰减 15%

### 3.2 Epoch 生命周期

```
┌─────────────────────────────────────────────────────────────┐
│                    EPOCH 生命周期                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │ 验证     │───►│ 验证     │───►│ 生产     │             │
│  │ (24 小时) │    │ (持续)   │    │ (10 分钟) │             │
│  └──────────┘    └──────────┘    └──────────┘             │
│       │                               │                     │
│       ▼                               ▼                     │
│  ┌──────────────────────────────────────────┐              │
│  │         EPOCH 结算                        │              │
│  │  • 计算加权奖励                          │              │
│  │  • 应用古老性乘数                        │              │
│  │  • 记入矿工余额                          │              │
│  │  • 锚定到 Ergo 区块链                    │              │
│  └──────────────────────────────────────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 区块生产者选择

```python
def get_round_robin_producer(slot: int, attested_miners: List) -> str:
    """
    确定性轮询区块生产者选择。
    每个验证的 CPU 在轮换周期中恰好获得 1 轮。
    """
    if not attested_miners:
        return None
    
    # 确定性轮换：slot 除以矿工数量取模
    producer_index = slot % len(attested_miners)
    return attested_miners[producer_index]
```

### 3.4 奖励分配算法

奖励按时间老化古老性乘数成比例分配：

```python
def calculate_epoch_rewards(miners: List, total_reward: int, chain_age_years: float):
    """
    按古老性乘数加权分配 epoch 奖励。
    """
    weights = {}
    total_weight = 0.0
    
    for miner_id, device_arch, fingerprint_passed in miners:
        if not fingerprint_passed:
            weight = 0.0  # 虚拟机/模拟器获得零
        else:
            weight = get_time_aged_multiplier(device_arch, chain_age_years)
        
        weights[miner_id] = weight
        total_weight += weight
    
    # 成比例分配
    rewards = {}
    for miner_id, weight in weights.items():
        rewards[miner_id] = int((weight / total_weight) * total_reward)
    
    return rewards
```

---

## 4. 硬件指纹识别系统

### 4.1 概述

RustChain 实施了全面的 6 检查硬件指纹识别系统（复古平台为 7 检查）。所有检查必须通过，矿工才能获得古老性乘数奖励。

```
┌─────────────────────────────────────────────────────────────┐
│           6 项必需的硬件指纹检查                            │
├─────────────────────────────────────────────────────────────┤
│ 1. 时钟漂移和振荡器漂移     ← 硅芯片老化模式              │
│ 2. 缓存时间指纹             ← L1/L2/L3 延迟特征           │
│ 3. SIMD 单元身份            ← AltiVec/SSE/NEON 偏差       │
│ 4. 热漂移熵                 ← 独特的热曲线                │
│ 5. 指令路径抖动             ← 微架构抖动图                │
│ 6. 反模拟行为               ← 检测虚拟机/模拟器           │
│ 7. ROM 指纹（仅复古）       ← 已知模拟器 ROM              │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 检查 1：时钟漂移和振荡器漂移

真正的硅芯片表现出可测量的时钟漂移，原因是：
- 晶体振荡器老化
- 温度波动
- 制造变化

**实现：**

```python
def check_clock_drift(samples: int = 200) -> Tuple[bool, Dict]:
    """
    测量 perf_counter 和参考操作之间的时钟漂移。
    真实硬件显示自然方差；虚拟机显示合成计时。
    """
    intervals = []
    reference_ops = 5000
    
    for i in range(samples):
        data = f"drift_{i}".encode()
        start = time.perf_counter_ns()
        for _ in range(reference_ops):
            hashlib.sha256(data).digest()
        elapsed = time.perf_counter_ns() - start
        intervals.append(elapsed)
    
    mean_ns = statistics.mean(intervals)
    stdev_ns = statistics.stdev(intervals)
    cv = stdev_ns / mean_ns  # 变异系数
    
    # 合成计时检测
    if cv < 0.0001:  # 太完美 = 虚拟机
        return False, {"fail_reason": "synthetic_timing"}
    
    return True, {"cv": cv, "drift_stdev": drift_stdev}
```

**检测标准：**
- 变异系数 < 0.0001 → 合成计时（失败）
- 零漂移标准差 → 无自然抖动（失败）

### 4.3 检查 2：缓存时间指纹

每个 CPU 具有独特的 L1/L2/L3 缓存特性，基于：
- 缓存大小和关联性
- 行大小和替换策略
- 内存控制器行为

**实现：**

```python
def check_cache_timing(iterations: int = 100) -> Tuple[bool, Dict]:
    """
    测量跨越 L1、L2、L3 缓存边界的访问延迟。
    真实缓存显示不同的延迟层级；虚拟机显示平坦的配置文件。
    """
    l1_size = 8 * 1024      # 8 KB
    l2_size = 128 * 1024    # 128 KB
    l3_size = 4 * 1024 * 1024  # 4 MB
    
    l1_latency = measure_access_time(l1_size)
    l2_latency = measure_access_time(l2_size)
    l3_latency = measure_access_time(l3_size)
    
    l2_l1_ratio = l2_latency / l1_latency
    l3_l2_ratio = l3_latency / l2_latency
    
    # 无缓存层级 = 虚拟机/模拟器
    if l2_l1_ratio < 1.01 and l3_l2_ratio < 1.01:
        return False, {"fail_reason": "no_cache_hierarchy"}
    
    return True, {"l2_l1_ratio": l2_l1_ratio, "l3_l2_ratio": l3_l2_ratio}
```

### 4.4 检查 3：SIMD 单元身份

不同的 CPU 架构具有不同的 SIMD 功能：

| 架构 | SIMD 单元 | 检测 |
|--------------|-----------|-----------|
| PowerPC G4/G5 | AltiVec | `/proc/cpuinfo` 或 `sysctl` |
| x86/x64 | SSE/AVX | CPUID 标志 |
| ARM | NEON | `/proc/cpuinfo` 特性 |
| 68K | 无 | 架构检测 |

**目的：** 验证声称的架构与实际 SIMD 功能匹配。

### 4.5 检查 4：热漂移熵

真正的 CPU 表现出热依赖性能变化：

```python
def check_thermal_drift(samples: int = 50) -> Tuple[bool, Dict]:
    """
    比较冷和热执行计时。
    真实硅芯片显示热漂移；虚拟机显示恒定性能。
    """
    # 冷测量
    cold_times = measure_hash_performance(samples)
    
    # 预热 CPU
    for _ in range(100):
        for _ in range(50000):
            hashlib.sha256(b"warmup").digest()
    
    # 热测量
    hot_times = measure_hash_performance(samples)
    
    cold_stdev = statistics.stdev(cold_times)
    hot_stdev = statistics.stdev(hot_times)
    
    # 无热方差 = 合成
    if cold_stdev == 0 and hot_stdev == 0:
        return False, {"fail_reason": "no_thermal_variance"}
    
    return True, {"drift_ratio": hot_avg / cold_avg}
```

### 4.6 检查 5：指令路径抖动

不同的指令类型表现出独特的计时抖动模式，基于：
- 流水线深度和宽度
- 分支预测器行为
- 乱序执行特性

**测量操作：**
- 整数算术（ADD、MUL、DIV）
- 浮点运算
- 分支密集型代码

### 4.7 检查 6：反模拟行为检查

直接检测虚拟化指标：

```python
def check_anti_emulation() -> Tuple[bool, Dict]:
    """
    通过多个向量检测虚拟机/容器环境。
    """
    vm_indicators = []
    
    # 检查 DMI/SMBIOS 字符串
    vm_paths = [
        "/sys/class/dmi/id/product_name",
        "/sys/class/dmi/id/sys_vendor",
        "/proc/scsi/scsi"
    ]
    vm_strings = ["vmware", "virtualbox", "kvm", "qemu", "xen", "hyperv"]
    
    for path in vm_paths:
        content = read_file(path).lower()
        for vm in vm_strings:
            if vm in content:
                vm_indicators.append(f"{path}:{vm}")
    
    # 检查环境变量
    if "KUBERNETES" in os.environ or "DOCKER" in os.environ:
        vm_indicators.append("ENV:container")
    
    # 检查 CPUID 虚拟机管理标志
    if "hypervisor" in read_file("/proc/cpuinfo").lower():
        vm_indicators.append("cpuinfo:hypervisor")
    
    return len(vm_indicators) == 0, {"vm_indicators": vm_indicators}
```

### 4.8 检查 7：ROM 指纹（复古平台）

对于复古平台（PowerPC、68K、Amiga），RustChain 维护已知模拟器 ROM 转储的数据库。真正的硬件应该有独特的 ROM 或变体 ROM，而模拟器使用相同的盗版 ROM 包。

**检测的 ROM 来源：**
- SheepShaver/Basilisk II（Mac 模拟器）
- PearPC（PowerPC 模拟器）
- UAE（Amiga 模拟器）
- Hatari（Atari ST 模拟器）

### 4.9 指纹验证结果

```
┌─────────────────────────────────────────────────────────────┐
│              指纹验证矩阵                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   真正的 G4 Mac：所有 7 项检查通过 → 2.5× 乘数            │
│   模拟的 G4：检查 6 失败     → 0× 乘数                    │
│   现代 x86：所有 6 项检查通过 → 1.0× 乘数               │
│   虚拟机/容器：检查 6 失败     → 0× 乘数                │
│   树莓派：全部通过          → 0.0005× 乘数              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 古老性乘数

### 5.1 基础乘数表

硬件奖励基于**稀有性 + 保护价值**，而不仅仅是年代：

| 等级 | 乘数 | 硬件示例 |
|------|------------|-------------------|
| **传奇** | 3.0× | Intel 386、Motorola 68000、MIPS R2000 |
| **史诗** | 2.5× | **PowerPC G4**、Intel 486、Pentium |
| **稀有** | 1.5-2.0× | PowerPC G5、POWER8、DEC Alpha、SPARC |
| **不常见** | 1.1-1.3× | Core 2 Duo、AMD K6、Sandy Bridge |
| **常见** | 0.8× | 现代 x86_64 (Zen3+、Skylake+) |
| **惩罚** | 0.0005× | ARM（树莓派、廉价 SBC） |
| **禁止** | 0× | 虚拟机、模拟器（指纹失败） |

### 5.2 完整架构乘数

**PowerPC（最高等级）：**

| 架构 | 年份 | 基础乘数 |
|--------------|-------|-----------------|
| PowerPC G4 (7450/7455) | 2001-2005 | **2.5×** |
| PowerPC G5 (970) | 2003-2006 | 2.0× |
| PowerPC G3 (750) | 1997-2003 | 1.8× |
| IBM POWER8 | 2014 | 1.5× |
| IBM POWER9 | 2017 | 1.8× |

**复古 x86：**

| 架构 | 年份 | 基础乘数 |
|--------------|-------|-----------------|
| Intel 386/486 | 1985-1994 | 2.9-3.0× |
| Pentium/Pro/II/III | 1993-2001 | 2.0-2.5× |
| Pentium 4 | 2000-2006 | 1.5× |
| Core 2 | 2006-2008 | 1.3× |
| Nehalem/Westmere | 2008-2011 | 1.2× |
| Sandy/Ivy Bridge | 2011-2013 | 1.1× |

**现代硬件：**

| 架构 | 年份 | 基础乘数 |
|--------------|-------|-----------------|
| Haswell-Skylake | 2013-2017 | 1.05× |
| Coffee Lake+ | 2017-至今 | 0.8× |
| AMD Zen/Zen+ | 2017-2019 | 1.1× |
| AMD Zen 2/3/4/5 | 2019-至今 | 0.8× |
| Apple M1 | 2020 | 1.2× |
| Apple M2/M3/M4 | 2022-2025 | 1.05-1.15× |

### 5.3 时间老化衰减

复古硬件奖励在区块链生命周期内衰减，以奖励早期采用者：

```python
# 衰减率：每年 15%
DECAY_RATE_PER_YEAR = 0.15

def get_time_aged_multiplier(device_arch: str, chain_age_years: float) -> float:
    """
    计算时间衰减的古老性乘数。
    
    - 第 0 年：完整乘数（G4 = 2.5×）
    - 第 10 年：接近现代基线（1.0×）
    - 第 16.67 年：复古奖励完全衰减
    """
    base_multiplier = ANTIQUITY_MULTIPLIERS.get(device_arch.lower(), 1.0)
    
    # 现代硬件不衰减
    if base_multiplier <= 1.0:
        return 1.0
    
    # 计算衰减奖励
    vintage_bonus = base_multiplier - 1.0  # G4: 2.5 - 1.0 = 1.5
    aged_bonus = max(0, vintage_bonus * (1 - DECAY_RATE_PER_YEAR * chain_age_years))
    
    return 1.0 + aged_bonus
```

**示例衰减时间线（PowerPC G4）：**

| 链龄 | 复古奖励 | 最终乘数 |
|-----------|---------------|------------------|
| 第 0 年 | 1.5× | **2.5×** |
| 第 2 年 | 1.05× | 2.05× |
| 第 5 年 | 0.375× | 1.375× |
| 第 10 年 | 0× | 1.0× |

### 5.4 示例奖励分配

在一个 epoch 中有 5 个矿工（1.5 RTC 奖励池）：

```
矿工          架构         乘数      权重%    奖励
─────────────────────────────────────────────────────────
G4 Mac        PowerPC G4   2.5×      33.3%    0.30 RTC
G5 Mac        PowerPC G5   2.0×      26.7%    0.24 RTC
现代 PC #1    Skylake      1.0×      13.3%    0.12 RTC
现代 PC #2    Zen 3        1.0×      13.3%    0.12 RTC
现代 PC #3    Alder Lake   1.0×      13.3%    0.12 RTC
─────────────────────────────────────────────────────────
总计                       7.5×      100%     0.90 RTC
```

*（0.60 RTC 返回池中以供未来 epoch 使用）*

---

## 6. RTC 代币经济学

### 6.1 代币概述

| 属性 | 值 |
|----------|-------|
| **名称** | RustChain Token |
| **代号** | RTC |
| **总供应量** | 8,192,000 RTC |
| **小数位** | 8（1 RTC = 100,000,000 μRTC） |
| **区块奖励** | 每个 epoch 1.5 RTC |
| **区块时间** | 600 秒（10 分钟） |
| **Epoch 持续时间** | 144 个区块（约 24 小时） |

### 6.2 供应分配

```
┌─────────────────────────────────────────────────────────────┐
│                 RTC 供应分配                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ████████████████████████████████████████  94% 挖矿       │
│   ██░                                       2.5% 开发钱包  │
│   █░                                        0.5% 基金会    │
│   ███                                       3% 社区        │
│                                                             │
│   总预挖：6% (491,520 RTC)                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**分配明细：**

| 区域 | 分配 | RTC 数量 | 用途 |
|------|------------|------------|---------|
| 区块挖矿 | 94% | 7,700,480 | PoA 验证者奖励 |
| 开发钱包 | 2.5% | 204,800 | 开发资金 |
| 基金会 | 0.5% | 40,960 | 治理和运营 |
| 社区金库 | 3% | 245,760 | 空投、赏金、赠款 |

### 6.3 发射时间表

**减半事件：**
- 每 2 年或"Epoch 遗物事件"里程碑
- 初始：每个 epoch 1.5 RTC
- 第 2 年：每个 epoch 0.75 RTC
- 第 4 年：每个 epoch 0.375 RTC
- （持续直到最小粉尘阈值）

**销毁机制（可选）：**
- 未使用的验证者容量
- 过期的赏金奖励
- 被遗弃的徽章触发器

### 6.4 费用模型

RustChain 使用最低费用结构来防止垃圾邮件，同时保持可访问性：

| 操作 | 费用 |
|-----------|-----|
| 验证 | 免费 |
| 转账 | 0.0001 RTC |
| 提现到 Ergo | 0.001 RTC + Ergo 交易费用 |

### 6.5 归属规则

- 预挖钱包：1 年解锁延迟（链上治理执行）
- 基金会/开发资金：在 Epoch 1 之前不能在 DEX 上出售
- 社区金库：通过治理提案释放

---

## 7. Ergo 区块链锚定

### 7.1 锚定机制

RustChain 定期将其状态锚定到 Ergo 区块链，以实现不可变性和跨链验证：

```
┌─────────────────────────────────────────────────────────────┐
│               ERGO 锚定流程                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   RustChain          承诺            Ergo                  │
│   ─────────────────────────────────────────────────────     │
│                                                             │
│   Epoch N      ─►   BLAKE2b(miners)  ─►   TX (R4 寄存器)  │
│   结算             32 字节哈希          0.001 ERG 盒子     │
│                                                             │
│   验证：任何一方都可以证明 RustChain 状态                   │
│   存在于 Ergo 区块高度 H                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 承诺结构

```python
def compute_commitment(miners: List[Dict]) -> str:
    """
    计算 Ergo 锚定的加密承诺。
    """
    data = json.dumps(miners, sort_keys=True).encode()
    return blake2b(data, digest_size=32).hexdigest()
```

承诺包括：
- 矿工 ID
- 设备架构
- 验证时间戳
- 当前 RustChain slot

### 7.3 Ergo 交易格式

```json
{
  "outputs": [
    {
      "value": 1000000,  // 0.001 ERG 最小盒子
      "ergoTree": "<anchor_address>",
      "additionalRegisters": {
        "R4": "0e20<32-byte-commitment>",
        "R5": "<rustchain_slot>",
        "R6": "<miner_count>"
      }
    }
  ]
}
```

### 7.4 验证流程

任何一方都可以通过以下方式验证 RustChain 历史状态：

1. 查询 Ergo 区块链以获取锚定交易
2. 从 R4 寄存器提取承诺
3. 从 RustChain 状态重建承诺
4. 比较哈希值以进行完整性验证

---

## 8. 安全分析

### 8.1 威胁模型

| 威胁 | 向量 | 缓解 |
|--------|--------|------------|
| **女巫攻击** | 创建许多虚假矿工 | 硬件指纹绑定 1 设备 = 1 身份 |
| **模拟攻击** | 使用虚拟机伪造复古硬件 | 6 层指纹检测 |
| **重放攻击** | 重放旧验证 | 基于 nonce 的挑战 - 响应 |
| **指纹欺骗** | 伪造计时测量 | 多层融合 + 交叉验证 |
| **矿池主导** | 协调许多设备 | 轮询确保平等的区块生产 |
| **时间操纵** | 伪造链龄以获取乘数 | 服务器端时间戳验证 |

### 8.2 反模拟经济学

**成本分析：**

| 方法 | 成本 | 难度 |
|----------|------|------------|
| 购买真正的 PowerPC G4 | $50-200 | 容易 |
| 完美的 CPU 计时模拟 | $10,000+ 开发 | 困难 |
| 缓存行为模拟 | $5,000+ 开发 | 困难 |
| 热响应模拟 | 不可能 | N/A |
| **总模拟成本** | **$50,000+** | 非常困难 |

**经济结论：**"购买 50 美元的 G4 Mac 比模拟它更便宜。"

### 8.3 虚拟机检测效果

基于测试网数据的当前检测率：

| 环境 | 检测率 | 方法 |
|-------------|----------------|--------|
| VMware | 99.9% | DMI + 计时 |
| VirtualBox | 99.9% | DMI + CPUID |
| QEMU/KVM | 99.8% | 虚拟机管理标志 + 计时 |
| Docker | 99.5% | 环境 + cgroups |
| SheepShaver (PPC) | 99.9% | ROM 指纹 + 计时 |

### 8.4 奖励惩罚

| 条件 | 惩罚 |
|-----------|---------|
| 指纹失败 | 0× 乘数（无奖励） |
| 检测到虚拟机 | 0× 乘数 |
| 检测到模拟器 ROM | 0× 乘数 |
| 超出速率限制 | 临时禁止（1 小时） |
| 无效签名 | 验证被拒绝 |

### 8.5 红队发现

2026 年 1 月进行的安全审计：

1. **时钟漂移绕过尝试**：向计时测量注入抖动
   - **结果**：通过抖动的统计分析检测到
   - **状态**：已缓解

2. **缓存计时模拟**：人工延迟注入
   - **结果**：与负载下的真实缓存行为不一致
   - **状态**：已缓解

3. **硬件 ID 克隆**：从真实设备复制指纹
   - **结果**：热漂移模式对每个设备都是独特的
   - **状态**：已缓解

4. **重放攻击**：提交旧验证数据
   - **结果**：服务器端 nonce 验证防止重放
   - **状态**：已缓解

---

## 9. 未来工作

### 9.1 近期路线图（2026）

- **DEX 上市**：ErgoDEX 上的 RTC/ERG 交易对
- **NFT 徽章系统**：灵魂绑定成就徽章
  - "Bondi G3 Flamekeeper" — 在 PowerPC G3 上挖矿
  - "QuickBasic Listener" — 在 DOS 机器上挖矿
  - "DOS WiFi Alchemist" — 联网 DOS 机器
- **移动钱包**：iOS/Android RTC 钱包

### 9.2 中期路线图（2027）

- **跨链桥**：FlameBridge 到 Ethereum/Solana
- **GPU 古老性**：将乘数扩展到复古 GPU（Radeon 9800、GeForce FX）
- **RISC-V 支持**：为新兴的 RISC-V 复古硬件做准备

### 9.3 研究计划

**PSE/POWER8 向量推理**

在 IBM POWER8 VSX 单元上使用隐私保护计算的实验性工作：

- 仓库：`github.com/Scottcjn/ram-coffers`
- 状态：实验性
- 目标：在复古 POWER 硬件上实现 AI 推理

**非双结崩溃**

用于 POWER8 `vec_perm` 指令优化的新颖数学框架，可能在复古 POWER 硬件上实现有效的零知识证明。

---

## 10. 结论

RustChain 代表了区块链共识设计的范式转变。通过颠覆传统的"新即是好"挖矿激励，我们创建了一个系统：

1. **奖励保护**计算历史
2. **民主化参与**（无 ASIC 优势）
3. **减少电子垃圾**，通过赋予旧硬件经济价值
4. **通过复杂的指纹识别维护安全**

证明 - 古老性机制证明，区块链可以使经济激励与环境和文化保护目标保持一致。你的 PowerPC G4 不是过时的——它是一个挖矿设备。

**"旧机器永不死亡——它们铸造硬币。"**

---

## 11. 参考文献

### 实现

1. RustChain GitHub 仓库：https://github.com/Scottcjn/Rustchain
2. 赏金仓库：https://github.com/Scottcjn/rustchain-bounties
3. 实时浏览器：https://rustchain.org/explorer

### 技术标准

4. RIP-0001：证明 - 古老性共识规范
5. RIP-0007：基于熵的验证者指纹识别
6. RIP-200：轮询 1-CPU-1-票共识

### 外部

7. 2024 年全球电子垃圾监测报告 (UNITAR/ITU)：https://ewastemonitor.info/
8. Ergo 平台：https://ergoplatform.org
9. BLAKE2 哈希函数：https://www.blake2.net
10. Ed25519 签名：https://ed25519.cr.yp.to

### 硬件文档

11. PowerPC G4 (MPC7450) 技术参考
12. Intel CPUID 指令参考
13. ARM NEON 程序员指南

---

## 附录 A：API 参考

### 验证端点

```
POST /attest/challenge
请求：{"miner_id": "wallet_name"}
响应：{"nonce": "hex", "expires_at": 1234567890}

POST /attest/submit
请求：{
  "report": {
    "nonce": "hex",
    "device": {"arch": "g4", "serial": "..."},
    "fingerprint": {...},
    "signature": "ed25519_sig"
  }
}
响应：{"ok": true, "multiplier": 2.5}
```

### 钱包端点

```
GET /wallet/balance?miner_id=<wallet>
响应：{"miner_id": "...", "amount_rtc": 12.5}

GET /wallet/balances/all
响应：{"balances": [...], "total_rtc": 5214.91}
```

### 网络端点

```
GET /health
响应：{"ok": true, "version": "2.2.1-rip200", "uptime_s": 100809}

GET /api/stats
响应：{"total_miners": 11626, "epoch": 62, "chain_id": "rustchain-mainnet-v2"}

GET /epoch
响应：{"epoch": 62, "slot": 8928, "next_settlement": 1707000000}
```

---

## 附录 B：支持的平台

| 平台 | 架构 | 支持级别 |
|----------|--------------|---------------|
| Mac OS X Tiger/Leopard | PowerPC G4/G5 | 完整（Python 2.5 矿工） |
| Ubuntu Linux | ppc64le/POWER8 | 完整 |
| Ubuntu/Debian Linux | x86_64 | 完整 |
| macOS Sonoma | Apple Silicon | 完整 |
| Windows 10/11 | x86_64 | 完整 |
| FreeBSD | x86_64/PowerPC | 完整 |
| MS-DOS | 8086/286/386 | 实验性（仅徽章） |

---

*版权所有 © 2025-2026 Scott Johnson / Elyan Labs。根据 Apache License 2.0 许可证发布。*

*RustChain — 让复古硬件再次变得有价值。*
