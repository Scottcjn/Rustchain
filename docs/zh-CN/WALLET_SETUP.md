# RustChain 钱包设置新手指南

本指南面向从未接触过加密货币的用户。

RustChain 使用 **RTC** 作为其原生代币。项目文档中常用的参考汇率为 **1 RTC = $0.10 USD**。该网络已达到 **500 个钱包持有者**，代码赏金的常见支付额度为 **1 到 400 RTC**，具体取决于难度。

## 首先：理解 RustChain 上的「钱包」是什么

在 RustChain 上，你会看到两种公开的钱包样式：

- 人类可读的 miner ID，例如 `victus-x86-scott`
- 基于 Ed25519 的 RustChain 地址，例如 `RTC14f06ee294f327f5685d3de5e1ed501cffab33e7`

两者都可以出现在余额查询和挖矿奖励中。

重要区别：

- **miner ID** 是矿工和浏览器使用的公开标识符
- **RTC... 地址** 是由私钥支持的公开标识符，可用于 **signed transfer**

如果你只想开始挖矿，自动生成的矿工钱包就足够了。
如果你想自己 **发送 RTC**，请创建或恢复一个 **基于 Ed25519 的 `RTC...` 钱包**。

## 网络和 API 端点

以下是本指南中使用的主要 RustChain 端点：

- 健康检查：`https://rustchain.org/health`
- 活跃矿工：`https://rustchain.org/api/miners`
- 当前 epoch：`https://rustchain.org/epoch`
- 钱包余额：`https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET`
- 浏览器：`https://rustchain.org/explorer/`

使用 `curl -sk`，因为公共节点使用的是自签名 TLS 证书。

## 1. 获取 RTC 钱包的三种方式

### 方法 A：安装矿机并让 RustChain 为你创建一个钱包

这是最快的入门方式。

```bash
curl -sL https://rustchain.org/install.sh | bash
```

接下来会发生什么：

1. 安装程序检查你的机器并下载 Python 矿机。
2. 它要求你输入一个钱包 ID。
3. 你可以输入自己的钱包 ID，也可以按回车让 RustChain 自动生成。
4. 最后，安装程序会在屏幕上打印你的钱包 ID。

钱包 ID 示例：

- `victus-x86-scott`
- `RTC14f06ee294f327f5685d3de5e1ed501cffab33e7`

在 Linux 上，安装程序将矿机配置保存在这里：

```bash
cat /opt/rustchain-miner/config.json
```

你应该能看到一个 `wallet_id` 字段。

示例：

```json
{
  "wallet_id": "victus-x86-scott",
  "node_url": "https://rustchain.org"
}
```

如果你的目标是以下情况，此方法最合适：

- 快速开始挖矿
- 自动接收 epoch 奖励
- 在不学习签名的情况下获取钱包 ID

### 方法 B：使用钱包 GUI

如果你想要一个可视化钱包，请使用仓库中的 RustChain 钱包 GUI。

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
python3 -m pip install requests
python3 wallet/rustchain_wallet_gui.py
```

在 GUI 中：

1. 点击 `New Wallet`
2. 保存它创建的钱包 ID
3. 以后使用 `Load` 重新打开
4. 使用余额面板刷新你的 RTC 数量

重要提示：

- `wallet/rustchain_wallet_gui.py` 是简单的 GUI 钱包
- 如果你的检出中包含 `wallet/rustchain_wallet_secure.py`，对于真实资金请优先使用它，因为它使用加密密钥库和 seed phrase 备份

按如下方式运行安全版 GUI：

```bash
python3 wallet/rustchain_wallet_secure.py
```

安全版 GUI 将加密的钱包文件存储在这里：

```bash
ls ~/.rustchain/wallets
```

### 方法 C：使用 Python 钱包和加密模块以编程方式创建

如果你熟悉运行 Python，这是最简单的自托管路径。

安装官方 Python SDK：

```bash
python3 -m pip install rustchain
```

创建钱包：

```bash
python3 - <<'PY'
from rustchain_sdk import RustChainWallet

wallet = RustChainWallet.create(strength=256)  # 24-word wallet
print("Address:", wallet.address)
print("Public key:", wallet.public_key_hex)
print("Seed phrase:", " ".join(wallet.seed_phrase))
PY
```

需要立即保存的内容：

- `RTC...` 地址
- 24 个单词的 seed phrase
- 私钥（仅在你懂得如何保护它时保存）

## 2. 如何查询余额

### 方法一：curl

这是最直接的余额查询方式：

```bash
curl -sk 'https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET'
```

示例：

```bash
curl -sk 'https://rustchain.org/wallet/balance?miner_id=victus-x86-scott'
```

典型响应：

```json
{
  "amount_i64": 266673241,
  "amount_rtc": 266.673241,
  "miner_id": "victus-x86-scott"
}
```

### 方法二：浏览器

打开浏览器：

```text
https://rustchain.org/explorer/
```

使用方式：

1. 查看 `Active Attestations`
2. 在列表中找到你的 miner ID 或 `RTC...` 地址
3. 确认你的机器在网络上在线
4. 要获取精确的数值余额，请在浏览器中打开余额端点：

```text
https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET
```

浏览器是确认你的矿机在线的最佳可视化方式。余额端点是精确数值的真实来源。

### 方法三：钱包 GUI

在 GUI 钱包中：

1. 输入你的钱包 ID 或加载已保存的钱包
2. 点击 `Load` 或 `Refresh`
3. 读取余额面板中显示的余额

如果你不想使用终端，GUI 会更加方便。

## 3. 如何接收 RTC

### 选项一：挖矿获取

一旦你的矿机安装完成并在线，挖矿就是自动进行的。

有用的检查：

```bash
curl -sk https://rustchain.org/health
curl -sk https://rustchain.org/api/miners
curl -sk https://rustchain.org/epoch
```

你会看到什么：

- 矿机会出现在 `/api/miners` 中
- RustChain 每个 epoch 支付挖矿奖励
- 当前公共文档将 epoch 描述为大约 10 分钟的奖励周期

### 选项二：赚取赏金

RustChain 为代码贡献支付 RTC。

典型的赏金支付流程：

1. 选择一个赏金 issue
2. 提交一个 pull request
3. PR 被审查并合并
4. 被询问时分享你的钱包地址，或将其包含在 PR 描述中
5. 从社区基金接收 RTC

典型的奖励额度：

- 小型文档/测试：`1-10 RTC`
- 标准工作：`20-50 RTC`
- 大型工作：`75-150 RTC`
- 关键或特殊安全工作：最高 `400 RTC`

### 选项三：从另一个钱包接收转账

要接收 RTC，只需分享你的 **公开钱包**：

- miner ID，如 `victus-x86-scott`，或
- `RTC...` 地址，如 `RTC14f06ee294f327f5685d3de5e1ed501cffab33e7`

永远不要分享你的 seed phrase 或私钥。

## 4. 如何发送 RTC

### 发送之前：了解你拥有哪种钱包类型

如果你的钱包只是一个简单的 miner ID，你可以向它挖矿并在那里接收资金。
但 **公开的 signed transfer 需要一个基于 Ed25519 的 `RTC...` 钱包**。
一个可读的 miner ID（如 `victus-x86-scott`）本身不足以用于 `POST /wallet/transfer/signed`。

如果你打算自己发送 RTC，请使用：

- 安全版 GUI 钱包，或
- 由 Python SDK 创建的编程式 `RTC...` 钱包

### 方法一：使用安全版钱包 GUI 发送

如果你使用的是 `wallet/rustchain_wallet_secure.py`：

1. 从 `~/.rustchain/wallets` 加载你的钱包
2. 复制并粘贴收件人的 `RTC...` 地址
3. 输入金额
4. 可选地添加备注
5. 输入你的钱包密码
6. 点击 `SIGN & SEND`

在底层，GUI 会对你的转账进行签名并发布到：

```text
POST https://rustchain.org/wallet/transfer/signed
```

### 方法二：通过 signed transfer API 发送

你不能仅用普通的 `curl` 安全地发送 RTC，因为转账必须先进行签名。

安装所需的 Python 包：

```bash
python3 -m pip install pynacl requests
```

然后运行：

```bash
python3 - <<'PY'
import hashlib
import json
import time
import requests
from nacl.signing import SigningKey

NODE_URL = "https://rustchain.org"
PRIVATE_KEY_HEX = "YOUR_PRIVATE_KEY_HEX"
TO_ADDRESS = "RTC_RECIPIENT_ADDRESS"
AMOUNT_RTC = 1.0
MEMO = "First RustChain transfer"
NONCE = int(time.time())

signing_key = SigningKey(bytes.fromhex(PRIVATE_KEY_HEX))
public_key_hex = signing_key.verify_key.encode().hex()
from_address = "RTC" + hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:40]

canonical = {
    "from": from_address,
    "to": TO_ADDRESS,
    "amount": AMOUNT_RTC,
    "memo": MEMO,
    "nonce": str(NONCE),
}

message = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
signature_hex = signing_key.sign(message).signature.hex()

payload = {
    "from_address": from_address,
    "to_address": TO_ADDRESS,
    "amount_rtc": AMOUNT_RTC,
    "memo": MEMO,
    "nonce": NONCE,
    "chain_id": "rustchain-mainnet-v2",
    "public_key": public_key_hex,
    "signature": signature_hex,
}

resp = requests.post(
    f"{NODE_URL}/wallet/transfer/signed",
    json=payload,
    verify=False,
    timeout=15,
)

print(resp.status_code)
print(resp.json())
PY
```

### 为什么 Ed25519 签名很重要

RustChain 要求 Ed25519 签名，以便网络可以验证：

- 你确实拥有你正在发送资金的钱包
- 签名后没有人更改金额或目的地
- 转账与唯一的 nonce 绑定，这有助于阻止重放攻击

如果有人只知道你的公开钱包名称，没有你的私钥，他们仍然无法发送你的资金。

## 5. 安全基础

### 备份你的钱包

备份什么内容取决于你是如何创建钱包的：

- 矿机安装：保存打印出的钱包 ID 并复制 `/opt/rustchain-miner/config.json`
- 安全版 GUI：备份 24 个单词的 seed phrase 和 `~/.rustchain/wallets/*.json`
- 编程式钱包：备份 seed phrase 以及你创建的任何加密密钥库

### 永远不要分享你的私钥

永远不要向任何人发送：

- 你的私钥十六进制值
- 你的 seed phrase
- 你的钱包密码
- 你的加密密钥库文件，除非你完全信任目的地并清楚为什么要这样做

### 钱包名称与私钥

公开信息：

- Miner ID
- `RTC...` 地址

保密信息：

- Seed phrase
- 私钥
- 用于解锁加密钱包的密码

你可以在 PR 评论中安全地发布你的公开钱包以获取赏金支付。
你绝不能发布你的 seed phrase 或私钥。

## 6. 常见问题

### 我的钱包存储在哪里？

通常在以下位置：

- 矿机安装：`/opt/rustchain-miner/config.json`
- 运行中的 Linux 矿机：有时也在 `/tmp/local_miner_wallet.txt`
- 安全版 GUI 和 CLI 密钥库：`~/.rustchain/wallets/`
- 编程式钱包：你保存它的任何位置

### 我忘记了钱包名称

按以下顺序尝试：

```bash
cat /opt/rustchain-miner/config.json
ls ~/.rustchain/wallets
curl -sk https://rustchain.org/api/miners
```

如果你仍然拥有安全钱包密钥库或 seed phrase，通常可以恢复公开的 `RTC...` 地址。
如果你丢失了自托管钱包的 seed phrase 和私钥，任何人都无法为你恢复资金。

### 为什么我的余额为零？

常见原因：

- 你查询了错误的钱包 ID
- 你的矿机尚未完成一个奖励周期
- 你的矿机没有出现在 `/api/miners` 中
- 钱包是全新的，从未接收过 RTC
- 你正在检查人类可读的 miner ID，但你的资金在另一个 `RTC...` 钱包中，或者反过来

快速检查：

```bash
curl -sk https://rustchain.org/health
curl -sk https://rustchain.org/api/miners
curl -sk 'https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET'
```

### 多久才能赚到 RTC？

对于挖矿：

- 你的矿机必须成功完成证明
- 你的矿机必须在整个奖励周期内保持在线
- 然后 RustChain 在 epoch 结算时发放奖励

在当前的公共文档中，epoch 被描述为大约 **10 分钟**。如果你刚刚开始，在假设出现问题之前，至少等待一个完整的 epoch。

对于赏金：

- 支付发生在审查和合并之后
- 通常在向维护者分享你的钱包地址后收到资金

## 如果你想走最短路径的快速开始

1. 安装矿机：

```bash
curl -sL https://rustchain.org/install.sh | bash
```

2. 复制最后显示的钱包 ID。

3. 查询你的余额：

```bash
curl -sk 'https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET'
```

4. 确认你已在线：

```bash
curl -sk https://rustchain.org/api/miners
curl -sk https://rustchain.org/epoch
```

5. 如果你以后想自己发送 RTC，请使用安全版 GUI 或 Python 钱包模块创建一个安全的 `RTC...` 钱包。
