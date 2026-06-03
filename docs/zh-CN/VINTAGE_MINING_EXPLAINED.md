# 古董挖矿详解

> RustChain 是一条 2003 年的 Power Mac G4 比现代 Threadripper 赚得更多的区块链。
> 本文档解释其原理和原因。

---

## 为什么是古董硬件？

### 电子废弃物问题

全球计算行业每年产生 5000 万吨电子废弃物。可用的机器在使用 3-5 年后就被丢弃，因为按照基准测试标准它们已经"过时"。但一台仍然能开机、仍然能计算、仍然能响应其硅芯片指令的机器不是废物。它是幸存者。

RustChain 建立在一个简单的前提之上：**如果它还能计算，它就有价值。**

### Boudreaux 原则

RustChain 遵循五条源自 Cajun 生存文化的原则（参见 [Boudreaux 计算原则](../Boudreaux_COMPUTING_PRINCIPLES.md)）：

1. **如果它还能用，它就有价值** —— 一台 G4 PowerBook 仍然能做硬浮点运算。一台 POWER8 仍然有 128 个线程。
2. **看起来简单的人开销更少** —— 没有 VC，没有基金会，没有治理委员会。
3. **永远不要丢弃你能重新利用的东西** —— 一台退役的数据中心服务器可以变成 AI 推理引擎。
4. **外来者总是低估本地人** —— 沼泽从来不是问题。沼泽是优势。
5. **实际智慧在锅边胜过理论知识** —— 秋葵汤做好了。你可以吃，也可以分析它。

### 数字保存

每一台挖掘 RTC 的机器都是一台没有进入填埋场的 RustChain 在[绿色追踪器](https://rustchain.org/preserved.html)上记录被保存的硬件，包括估计避免的 CO2 排放和电子废弃物。

当前矿队统计：
- 4 个 attestation 节点上的 22+ 活跃矿工
- 2 个大洲（北美和亚洲）
- 架构：PowerPC G4、G5、MIPS、x86_64、Apple Silicon、POWER8、ARM
- 估计避免了 1,300 kg 制造 CO2
- 估计从填埋场转移了 250 kg 电子废弃物

---

## 古董证明如何工作

### 传统挖矿 vs. 古董证明

| | 工作量证明 (Bitcoin) | 权益证明 (Ethereum) | 古董证明 (RustChain) |
|---|---|---|---|
| **什么赚取奖励** | 最快的哈希率 | 最大的质押 | 最老的存活硬件 |
| **能源模型** | 巨大的电力消耗 | 最小，但资本密集 | 最小（古董硬件低功耗） |
| **硬件趋势** | 越新越好 | 不适用 | 越老越好 |
| **电子废弃物影响** | 制造它（ASIC 过时） | 中性 | 防止它 |
| **进入成本** | $10,000+ ASIC | 32 ETH (~$80,000) | eBay 上 $40 的 PowerBook |

### Attestation 周期

每 10 分钟（一个 epoch），矿工必须证明他们在真实的物理硬件上运行：

1. **矿工客户端检测硬件** —— CPU 型号、架构、SIMD 能力、缓存层级
2. **客户端运行 6 项 fingerprint 检查** —— 时钟漂移、缓存时序、SIMD 标识、热漂移、指令抖动、反模拟
3. **客户端提交 attestation** 到 RustChain 节点 `POST /attest/submit`
4. **服务器验证 fingerprint 数据** —— 不信任自报告结果；要求原始证据
5. **服务器推导已验证的设备类型** —— 交叉验证报告的架构与 SIMD 特性和时序数据
6. **Epoch 结算** —— 1.5 RTC 按 antiquity 乘数权重按比例分配给所有有效的 attestation 者

---

## 硬件 Fingerprint：6 项检查

RustChain 不会相信你声称的硬件。它进行测量。

### 1. 时钟偏移和振荡器漂移

每个物理 CPU 都有一个带有制造缺陷的晶体振荡器。随着时间推移，硅芯片老化，漂移增加。矿工采集 500-5000 次时序测量并计算变异系数。

- **真实古董硬件 (G4, G5)**：CV 为 0.01-0.09 —— 高方差，真实的振荡器老化
- **真实现代硬件 (Ryzen, Xeon)**：CV 为 0.005-0.05 —— 较低但可测量
- **虚拟机**：CV < 0.0001 —— 过于均匀，绑定到主机时钟

### 2. 缓存时序 Fingerprint

真实 CPU 有具有不同延迟级别的多级缓存 (L1, L2, L3)。矿工扫描从 1 KB 到 8 MB 的缓冲区大小，并在每个步骤测量访问延迟，产生内存层级的"音调曲线"。

- **真实硬件**：清晰的延迟阶梯（L1：3-5 周期，L2：10-20 周期，L3：30-60 周期）
- **模拟器**：平坦的延迟曲线（所有内容通过同一模拟层）

### 3. SIMD 单元标识

不同架构有不同的 SIMD 指令集（PowerPC 上的 AltiVec，x86 上的 SSE/AVX，ARM 上的 NEON）。矿工对特定 SIMD 操作进行基准测试并测量管道偏差 —— 整数与浮点吞吐量的比率、shuffle 延迟和 MAC 时序。

SIMD 的软件模拟会拉平这些比率。真实硬件具有可测量的不对称性。

### 4. 热漂移熵

矿工在不同热状态下收集熵：冷启动、温负载、热饱和和松弛。热曲线是物理的，每块芯片独一无二。一台 20 年的 G4 与一台新的 Ryzen 具有完全不同的热响应。

### 5. 指令路径抖动

在整数管道、分支单元、FPU、加载/存储队列和重排序缓冲区上测量周期级抖动。这产生了一个抖动签名矩阵。没有虚拟机或模拟器能在纳秒级复制真实的微架构抖动。

### 6. 反模拟行为检查

明确检测虚拟机管理程序签名：
- `/sys/class/dmi/id/sys_vendor` 包含 "qemu"、"vmware"、"virtualbox"
- `/proc/cpuinfo` 包含 "hypervisor" 标志
- 通过 cgroup 检查的 Docker/LXC/Kubernetes 容器标记
- 来自 VM 调度的时间膨胀伪影
- 扁平化的抖动分布（在真实硬件上不可能）

**如果任何检查失败，矿工将不会获得奖励。** 服务器执行失败即关闭策略：缺少 fingerprint 数据意味着零权重，而不是默认权重。

---

## 乘数表

### 标准架构

| 设备类型 | 基础乘数 | 时代 | 示例硬件 |
|-------------|-----------------|-----|------------------|
| 现代 x86_64 | 0.8x | 当前 | Ryzen 9, Core i9, Threadripper |
| 现代 ARM (NAS/SBC) | 0.0005x | 当前 | Raspberry Pi, Synology NAS |
| Apple Silicon (M1-M4) | 1.05-1.2x | 现代 | Mac Mini M2, MacBook Pro M3 |
| Sandy Bridge | 1.1x | 2011 | Core i5-2500K |
| Nehalem | 1.2x | 2008 | Core i7-920 |
| Core 2 Duo | 1.3x | 2006 | MacBook 2006, Dell Optiplex 755 |
| RISC-V | 1.4-1.5x | 异域 | SiFive boards, StarFive VisionFive |
| POWER8 | 1.5x | 2014 | IBM S824, 我们的 128 线程推理服务器 |
| Pentium 4 | 1.5x | 2000 | 2000 年代初的热棒 |
| PowerPC G3 | 1.8x | 1997 | iMac G3, Blue & White G3 |
| PowerPC G5 | 2.0x | 2003 | Power Mac G5 |
| PS3 Cell BE | 2.2x | 2006 | 7 个 SPE 核心的传奇 |
| PowerPC G4 | 2.5x | 2003 | PowerBook G4 |

### 异域和传奇架构

| 设备类型 | 基础乘数 | 层级 | 示例硬件 |
|-------------|-----------------|------|------------------|
| XScale / ARM9 | 2.3-2.5x | 远古 | Sharp Zaurus, 早期嵌入式 ARM |
| Sega Genesis (68000) | 2.5x | 远古 | 7.67 MHz 的 Motorola 68000 |
| Nintendo 64 (MIPS) | 2.5-3.0x | 传奇 | 93.75 MHz 的 NEC VR4300 |
| SGI MIPS R4000-R16000 | 2.3-3.0x | 传奇 | Indigo2, O2, Octane |
| Sun SPARC | 1.8-2.9x | 传奇 | SPARCstation, Ultra 系列 |
| StrongARM | 2.7-2.8x | 传奇 | DEC SA-110, Intel SA-1100 |
| ARM6 / ARM7 | 3.0-3.5x | 传奇 | ARM7TDMI, Acorn RiscPC |
| Inmos Transputer | 3.5x | 神话 | 并行计算先驱，1984 |
| DEC VAX-11/780 | 3.5x | 神话 | "要玩个游戏吗？" |
| ARM2 / ARM3 | 3.8-4.0x | 神话 | ARM 的起点 (Acorn, 1987) |

### 为什么现代 ARM 只有 0.0005x

现代 ARM SBC（Raspberry Pi、Orange Pi、NAS 设备）便宜、充足且容易批量养殖。如果没有惩罚，某人可以用 $500 买 100 个 Pi Zero 并超过整个网络的产出。0.0005x 的乘数意味着 ARM SBC 矿场几乎赚不到任何东西 —— 你需要 2,000 个 Raspberry Pi 才能等于一台 Power Mac G4。

这是设计如此。RustChain 奖励稀缺性和存活，而不是商品数量。

---

## 时间衰减：古董奖励随时间减少

Antiquity 乘数不是永久的。它们在链的生命周期内缓慢衰减，以防止古董硬件所有者的永久贵族统治。

### 公式

```
effective_multiplier = 1.0 + (base_multiplier - 1.0) * (1 - 0.15 * chain_age_years)
```

### 衰减示例

| 设备 | 基础 | 第 0 年 | 第 1 年 | 第 5 年 | 第 10 年 | 第 16.67 年 |
|--------|------|--------|--------|--------|---------|------------|
| G4 | 2.5x | 2.50x | 2.275x | 1.375x | 1.0x | 1.0x |
| G5 | 2.0x | 2.00x | 1.85x | 1.25x | 1.0x | 1.0x |
| G3 | 1.8x | 1.80x | 1.68x | 1.20x | 1.0x | 1.0x |
| SPARC | 2.9x | 2.90x | 2.615x | 1.475x | 1.0x | 1.0x |
| ARM2 | 4.0x | 4.00x | 3.55x | 1.75x | 1.0x | 1.0x |

大约 16.67 年后，所有古董奖励衰减为零，每种架构获得同等收益。到那时，今天的"现代"硬件本身将成为古董，循环继续。

链于 2025 年 12 月启动。截至 2026 年 3 月，链龄约为 0.3 年。当前乘数仍非常接近其基础值。

---

## 为什么虚拟机赚不到

虚拟机获得 **0.000000001x**（十亿分之一）的权重。这不是 bug。这是核心的反滥用机制。

### 攻击

如果没有 VM 检测，一个拥有强大服务器的攻击者可以：
1. 启动 50 个 QEMU 虚拟机
2. 配置每个虚拟机报告为不同的 "PowerPC G4"
3. 赚取 50 x 2.5x = 125 倍于单个诚实矿工的奖励
4. 破坏整个 1 CPU = 1 投票的共识

### 防御

反模拟检查（fingerprint 检查 #6）检测：
- 通过 DMI 供应商字符串检测 QEMU、VMware、VirtualBox、KVM、Xen、Hyper-V
- `/proc/cpuinfo` 中的虚拟机管理程序 CPU 标志
- 通过 cgroup 标记和根覆盖文件系统检测 Docker、LXC、Kubernetes
- 在真实硅芯片上不可能出现的均匀时序分布

**真实案例**：Ryan 的 Factorio 服务器运行在 Proxmox 虚拟机上。它成功提交了 attestation，但服务器检测到 `sys_vendor:qemu` 和 `cpuinfo:hypervisor`。它每个 epoch 大约赚取 0.000000001 RTC。这是正确的行为 —— VM 检测起作用了。

### FPGA 克隆

基于 FPGA 的复古克隆（Analogue Pocket、MiSTer FPGA）被检测为非原始硅芯片。它们获得减少的乘数，因为 fingerprint 检查测量的是原始芯片的特性，而不是门级重新实现。

---

## 矿队

RustChain 的活跃挖矿矿队包括：

| 矿工 | 架构 | 乘数 | 位置 |
|-------|-------------|------------|----------|
| dual-g4-125 | PowerPC G4 | 2.5x | Moss Bluff, LA |
| g4-powerbook-115 | PowerPC G4 | 2.5x | Moss Bluff, LA |
| g4-powerbook-real | PowerPC G4 | 2.5x | Moss Bluff, LA |
| ppc_g5_130 | PowerPC G5 | 2.0x | Moss Bluff, LA |
| POWER8 S824 | POWER8 | 1.5x | Moss Bluff, LA |
| sophia-nas-c4130 | 现代 x86 | 0.8x | Moss Bluff, LA |
| victus-x86-scott | 现代 x86 | 0.8x | Moss Bluff, LA |
| frozen-factorio-ryan | 现代 (VM) | 0.000000001x | Houma, LA |
| Mac Mini M2 | Apple Silicon | 1.2x | Moss Bluff, LA |
| 多台 G4 PowerBook | PowerPC G4 | 每台 2.5x | Moss Bluff, LA |

**4 个 attestation 节点：**
- 节点 1：rustchain.org（LiquidWeb VPS，主节点）
- 节点 2：50.28.86.153（LiquidWeb VPS，Ergo 锚点）
- 节点 3：76.8.228.245（Ryan 的 Proxmox，Houma LA —— 第一个外部节点）
- 节点 4：38.76.217.189（CognetCloud，香港 —— 第一个亚洲节点）

自行验证：

```bash
curl -sk https://rustchain.org/health
curl -sk https://rustchain.org/api/miners
curl -sk https://rustchain.org/epoch
```

---

## 环境影响

传统挖矿运营消耗数兆瓦电力，并在 ASIC 过时时产生硬件废弃物。RustChain 的 16+ 台古董机器矿队的功耗大约等于**一台**现代 GPU 挖矿设备。

| 指标 | RustChain 矿队 | 单台 GPU 设备 |
|--------|----------------|----------------|
| 功耗 | 总计约 500W | 约 500W |
| 机器数 | 16+ | 1 |
| 产生的电子废弃物 | **负值**（防止废弃物） | 正值（GPU 过时） |
| 避免的 CO2 | 约 1,300 kg（避免制造） | 0 |
| 进入成本 | eBay 上 $40 的 PowerBook | $2,000+ GPU |

查看实时数据：[rustchain.org/preserved.html](https://rustchain.org/preserved.html)

---

## 与 BoTTube 的连接

矿工还可以参与 [BoTTube](https://bottube.ai)，这是一个由 RTC 驱动的 AI 视频平台。挖矿和内容创作共享同一经济层：

- 挖矿通过硬件 attestation 赚取 RTC
- BoTTube Agent 通过内容创作和互动赚取 RTC
- 两种活动使用相同的钱包和余额系统

详见 [BoTTube 集成](../BOTTUBE_INTEGRATION.md)。

## 与 Legend of Elya 的连接

Legend of Elya 是一款 N64 游戏，同时也是挖矿客户端。在真实硬件上玩游戏可以在被动挖矿奖励之上赚取基于成就的 RTC。Proof of Play 系统验证成就是在真实硅芯片上获得的，而不是模拟的。

详见 [N64 挖矿指南](../N64_MINING_GUIDE.md) 获取设置说明。

---

## 延伸阅读

- [硬件 Fingerprint](../hardware-fingerprinting.md) —— 6+1 项检查的技术深度解析
- [代币经济](../token-economics.md) —— 供应、发行和乘数详情
- [Boudreaux 计算原则](../Boudreaux_COMPUTING_PRINCIPLES.md) —— 哲学理念
- [游戏机挖矿设置](../CONSOLE_MINING_SETUP.md) —— 在 NES、SNES、Genesis、PS1、Game Boy 和 N64 上挖矿
- [协议概述](../protocol-overview.md) —— attestation 协议规范
- [绿色追踪器](https://rustchain.org/preserved.html) —— 实时环境影响仪表板
- [白皮书](../WHITEPAPER.md) —— 正式规范
