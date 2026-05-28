# RustChain 快速入门指南

面向首次用户的分步指南。每条命令都可以直接复制粘贴。

---

## 什么是 RustChain？

RustChain 是一个奖励你让老电脑继续"活着"的区块链。与比特币奖励最快机器不同，RustChain 奖励的是*最老*的机器。一台 2003 年的 PowerBook G4 赚取的 RTC 是全新游戏 PC 的 2.5 倍。代币叫做 **RTC**（RustChain Token），具有真实价值——1 RTC 约合 $0.10 USD。超过 260 名贡献者已通过挖矿和代码赏金赚取了 25,000+ RTC。

---

## 前置条件

你只需要两样东西：

- **一台电脑**——任何电脑都行。Linux、macOS、Windows、树莓派、PowerPC Mac，甚至 SPARC 工作站。只要能运行 Python，就能挖矿。
- **网络连接**——你的矿机需要连接 RustChain 网络来证明你的硬件是真实的。

就这些。不需要 GPU，不需要特殊硬件，不需要注册账号。

---

## 第 1 步：安装矿机

打开终端（macOS：搜索"Terminal"；Windows：使用 PowerShell），运行：

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

**这个命令会：**

1. 检测你的操作系统和 CPU 架构
2. 如果没有 Python 3 则自动安装（仅限 Linux——macOS/Windows 用户需要预装 Python）
3. 下载矿机脚本到 `~/.rustchain/`
4. 创建 Python 虚拟环境并安装依赖
5. 让你选择钱包名称
6. 设置矿机开机自启
7. 测试与 RustChain 网络的连接

**想先预览一下？** 加上 `--dry-run`：

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --dry-run
```

### 选择钱包名称

安装过程中，你会看到：

```
[?] Enter wallet name (or Enter for auto):
```

输入一个你能记住的名字，比如 `scott-laptop` 或 `my-g4-mac`。这是你的钱包地址——你通过它接收 RTC。如果直接按回车，安装程序会自动生成一个（比如 `miner-myhost-4821`）。

**请记下你的钱包名称。** 后续查询余额时需要用到。

### 指定钱包名称安装（跳过提示）

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-cool-wallet
```

---

## 第 2 步：验证安装

安装完成后，检查一切是否就绪：

```bash
ls ~/.rustchain/
```

你应该看到：

```
rustchain_miner.py      # 矿机脚本
fingerprint_checks.py   # 硬件验证模块
start.sh                # 快速启动脚本
venv/                   # Python 虚拟环境
```

检查网络是否可达：

```bash
curl -sk https://rustchain.org/health
```

你应该看到类似这样的输出：

```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 3966,
  "db_rw": true
}
```

如果出现 `"ok": true`，说明网络在线，你的机器可以连接。

---

## 第 3 步：开始挖矿

如果安装程序设置了自启动（默认会），你的矿机已经在运行了。检查状态：

**Linux：**

```bash
systemctl --user status rustchain-miner
```

**macOS：**

```bash
launchctl list | grep rustchain
```

### 手动启动（如有需要）

```bash
~/.rustchain/start.sh
```

或者直接运行矿机：

```bash
~/.rustchain/venv/bin/python ~/.rustchain/rustchain_miner.py --wallet YOUR_WALLET_NAME
```

### 你会看到什么

矿机启动后，会运行 6 项硬件指纹检查来证明你的机器是真实的（不是虚拟机）：

```
[1/6] Clock-Skew & Oscillator Drift... PASS
[2/6] Cache Timing Fingerprint... PASS
[3/6] SIMD Unit Identity... PASS
[4/6] Thermal Drift Entropy... PASS
[5/6] Instruction Path Jitter... PASS
[6/6] Anti-Emulation Checks... PASS

OVERALL RESULT: ALL CHECKS PASSED
```

然后它会每隔几分钟向网络证明（attest）你的硬件。你会看到类似这样的日志：

```
[+] Attestation accepted. Next attestation in 300s.
```

这说明你的矿机正在工作。让它继续运行。

---

## 第 4 步：查看余额

奖励每 **10 分钟**分配一次（一个"epoch"）。第一个 epoch 结算后，查看余额：

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

将 `YOUR_WALLET_NAME` 替换为你安装时选择的钱包名称。例如：

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=scott-laptop"
```

响应：

```json
{
  "miner_id": "scott-laptop",
  "balance_rtc": 0.119051
}
```

这个 `0.119` RTC 就是你的第一笔挖矿奖励。只要矿机持续运行，它就会不断增长。

### 在区块浏览器上查看

你也可以在以下地址查看完整网络、所有矿机和你的奖励：

[https://rustchain.org/explorer/](https://rustchain.org/explorer/)

---

## 第 5 步：理解你的收益

每 10 分钟，1.5 RTC 分配给所有活跃矿机。你的份额取决于你硬件的**古董乘数**——更老的硬件获得更大份额。

### 硬件乘数表

| 硬件 | 乘数 | 示例 |
|------|------|------|
| DEC VAX, Inmos Transputer | 3.5x | 博物馆级铁器 |
| Motorola 68000 | 3.0x | Amiga, 经典 Mac |
| Sun SPARC | 2.9x | 工作站贵族 |
| PowerPC G4 | **2.5x** | PowerBook, iBook, Power Mac |
| PowerPC G5 | **2.0x** | Power Mac G5 塔式机 |
| PowerPC G3 | 1.8x | Bondi Blue iMac 时代 |
| IBM POWER8 | 1.5x | 企业级服务器 |
| Pentium 4 | 1.5x | 2000 年代初期 |
| RISC-V | 1.4x | 开放硬件，未来趋势 |
| Apple Silicon (M1-M4) | 1.2x | 现代但受欢迎 |
| 现代 x86 (AMD/Intel) | 0.8x | 基准线 |
| ARM NAS/SBC | 0.0005x | 太便宜，太容易伪造 |

**衣柜里有吃灰的 PowerBook G4？** 插上电源。它赚的是你游戏 PC 的 2.5 倍。

### 收益示例（8 台矿机在线）

```
PowerPC G4 (2.5x):       0.30 RTC/epoch
PowerPC G5 (2.0x):       0.24 RTC/epoch
现代 x86 PC (0.8x):      0.12 RTC/epoch
```

24 小时内（144 个 epoch），一台 G4 Mac 大约赚 **43 RTC**（$4.30），而现代 PC 大约赚 **17 RTC**（$1.70）。网络上矿机越多，每个矿机分到的就越少，但网络也更健康。

---

## 第 6 步：通过赏金赚更多

挖矿是被动收入。想要更大回报，可以贡献代码。

### 浏览开放赏金

[https://github.com/Scottcjn/rustchain-bounties/issues](https://github.com/Scottcjn/rustchain-bounties/issues)

每个标记了赏金的 issue 都有 RTC 奖励。奖励从 1 RTC（修复拼写错误）到 200 RTC（安全漏洞）不等。

| 等级 | 奖励 | 示例 |
|------|------|------|
| 微型 | 1-10 RTC | 修复拼写错误、改进文档、添加测试 |
| 标准 | 20-50 RTC | 新功能、重构、集成 |
| 重大 | 75-100 RTC | 安全修复、协议改进 |
| 关键 | 100-200 RTC | 漏洞发现、共识机制工作 |

### 如何领取赏金

1. 找到你想做的赏金 issue
2. 在 issue 下评论你的钱包名称（这样我们知道付给你）
3. Fork 仓库并提交 Pull Request
4. PR 审核合并后，RTC 会发送到你的钱包

### 最简单的首次贡献

查找标记为 `good first issue` 的 issue，或提交文档改进。即使只修复 README 中的一个拼写错误也能赚 RTC。

---

## 第 7 步：查看网络

### 实时浏览器

在以下地址查看所有矿机、区块和余额：

[https://rustchain.org/explorer/](https://rustchain.org/explorer/)

### API 端点（供好奇者使用）

这些在终端中都可以直接使用：

```bash
# 网络是否存活？
curl -sk https://rustchain.org/health

# 谁在挖矿？
curl -sk https://rustchain.org/api/miners

# 当前是哪个 epoch？
curl -sk https://rustchain.org/epoch

# 我的余额是多少？
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

`-sk` 标志告诉 curl 接受自签名 TLS 证书。这是正常的——节点使用自签名证书，而非商业证书。

---

## 故障排除

### `ConnectionRefused` 或 "Cannot connect to bootstrap node"

这通常意味着你的机器还无法连接到 RustChain 节点。

1. 检查公共节点是否响应：

```bash
curl -sk https://rustchain.org/health
```

2. 如果失败，等待 30-60 秒后重试。节点可能正在重启。
3. 确认你的网络连接、防火墙、VPN 或代理没有阻止出站 HTTPS。
4. 如果你设置了自定义节点 URL，验证主机名、端口和协议。

### `InsufficientBalance`

挖矿奖励不需要付费账户，但某些钱包或桥接操作可能需要现有 RTC 余额来支付手续费。

1. 确认你使用的是安装时的准确钱包名称：

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_EXACT_WALLET_NAME"
```

2. 矿机首次启动后至少等待一个完整 epoch。奖励大约每 10 分钟结算一次。
3. 如果你在获得奖励前测试钱包操作，可以向社区求助或使用水龙头/测试网流程。

### `HardwareFingerprintMismatch`

这可能发生在 BIOS 更新、固件更改、虚拟机/容器更改或在不同硬件之间移动矿机之后。

1. 在裸机上运行矿机，而不是在虚拟机或容器内。
2. 重启矿机以执行新的证明。
3. 如果你最近更新了 BIOS 或固件，将机器视为已更改的硬件配置，并使用相同钱包名称重新运行安装/证明流程。

### 矿机配置检查清单

- 命令中的钱包名称与你想收款的钱包匹配。
- `curl -sk https://rustchain.org/health` 返回 `"ok": true`。
- 系统时钟正确；时钟偏差过大会导致 TLS 和证明窗口失败。
- 你在真实硬件上运行（如果期望正常奖励）。
- 你至少等待了 2-3 个 epoch 才判定奖励缺失。

### "Python 3 not found"

安装程序会尝试在 Linux 上自动安装 Python。在 macOS 或 Windows 上，你需要先自行安装：

- **macOS：** `brew install python3`（或从 https://python.org 下载）
- **Windows：** 从 https://python.org/downloads 下载，并勾选"Add to PATH"

### "curl: command not found"

- **Linux：** `sudo apt install curl`（Debian/Ubuntu）或 `sudo dnf install curl`（Fedora）
- **macOS：** curl 在所有 Mac 上预装。

### SSL 证书错误

如果运行 `curl` 命令时出现证书相关错误，加上 `-k`：

```bash
curl -sk https://rustchain.org/health
```

矿机脚本会自动处理这个问题。

### 矿机启动但 30 分钟后仍无奖励

1. 确认你的矿机出现在活跃矿机列表中：

```bash
curl -sk https://rustchain.org/api/miners
```

在输出中查找你的钱包名称。

2. 确认你查询的是正确的钱包名称：

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_EXACT_WALLET_NAME"
```

3. 奖励每 10 分钟结算一次。至少等待 2-3 个 epoch（20-30 分钟）。

### 虚拟机几乎得不到奖励

这是设计如此。虚拟机（VMware、VirtualBox、QEMU、WSL）会被反模拟指纹检测发现，获得的奖励大约是正常奖励的十亿分之一。RustChain 只奖励真实硬件。在裸机上运行矿机，而不是虚拟机内。

### 卸载

要完全移除矿机：

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

### 获取帮助

- **GitHub Issues：** https://github.com/Scottcjn/Rustchain/issues
- **Discord：** https://discord.gg/VqVVS2CW9Q
- **Moltbook：** https://www.moltbook.com/m/rustchain
- **FAQ：** [FAQ_TROUBLESHOOTING.md](FAQ_TROUBLESHOOTING.md)

---

## 术语表

| 术语 | 含义 |
|------|------|
| **RTC** | RustChain Token——你通过挖矿赚取的加密货币。1 RTC 约合 $0.10 USD。 |
| **Epoch** | 10 分钟的时间窗口。每个 epoch 结束时，1.5 RTC 分配给所有活跃矿机。 |
| **Attestation（证明）** | 你的矿机通过运行 6 项指纹检查来证明其硬件真实性的过程。 |
| **Antiquity Multiplier（古董乘数）** | 基于硬件年龄的奖励加成。更老的 CPU 获得更高的乘数。 |
| **Wallet（钱包）** | 你的矿机名称/地址。RTC 会被发送到这里。你在安装时选择了它。 |
| **Miner（矿机）** | 运行在你机器上的软件，向网络证明并赚取 RTC。 |
| **Fingerprint（指纹）** | 6 项硬件测量（时钟漂移、缓存时序、SIMD 身份、热漂移、指令抖动、反模拟），用于证明你的机器是真实的。 |
| **wRTC** | Solana 上的 Wrapped RTC。你可以在 bottube.ai/bridge 使用桥接在 RTC 和 wRTC 之间兑换。 |
| **Block Explorer（区块浏览器）** | 显示所有网络活动的网页：矿机、余额、epoch。访问 rustchain.org/explorer。 |

---

## 后续步骤

- **将 RTC 兑换为 Solana 代币：** [wRTC 指南](wrtc.md)
- **运行完整节点：** [协议文档](PROTOCOL.md)
- **深入了解 Proof-of-Antiquity：** [白皮书](WHITEPAPER.md)
- **贡献代码：** [贡献指南](../CONTRIBUTING.md)
- **API 参考：** [API 教程](API_WALKTHROUGH.md)

---

*由 [Elyan Labs](https://elyanlabs.ai) 构建——$0 风投，一屋子当铺硬件，以及一个信念：老机器仍有尊严。*
