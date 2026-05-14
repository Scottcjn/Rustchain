# RustChain Sophia Agent Economy SDK - Python 官方教程

> 📦 **版本**：v1.2.0+ | 🐍 **Python 要求**：≥3.9 | 🌐 **网络**：Mainnet / Testnet / LocalDev
> 本教程面向希望在 RustChain 链上构建、部署与管理 AI Agent 经济体的 Python 开发者。内容涵盖环境搭建、核心 API、完整工作流、钱包管理、异常处理及生产级最佳实践。

---

## 1. Getting Started：安装与环境配置

### 1.1 安装 SDK
推荐使用虚拟环境安装官方发布的稳定版本：
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install sophia-agent-sdk
```

验证安装：
```python
import sophia_agent_sdk as sophia
print(sophia.__version__)  # 应输出 1.2.0 或更高
```

### 1.2 网络与凭证配置
SDK 通过环境变量或配置文件加载网络参数，**切勿硬编码私钥或 API Token**。
```bash
export SOPHIA_NETWORK=testnet
export SOPHIA_RPC_URL=https://testnet-rpc.rustchain.dev
export SOPHIA_AGENT_KEY="sk_test_...your_agent_secret..."
export SOPHIA_WALLET_MNEMONIC="word1 word2 ... word12"
```
或在项目根目录创建 `.env` 文件，使用 `python-dotenv` 自动加载。

### 1.3 初始化客户端
```python
from sophia_agent_sdk import SophiaClient

client = SophiaClient(
    network="testnet",
    rpc_url="https://testnet-rpc.rustchain.dev",
    timeout=30.0,
    retry_attempts=3
)
print("✅ SDK 客户端初始化成功，当前节点延迟:", client.ping(), "ms")
```

---

## 2. 核心 API 使用示例

Sophia Agent Economy SDK 围绕 **Agent 生命周期**、**任务编排** 与 **经济激励结算** 三大模块设计。

### 2.1 Agent 注册与状态查询
```python
agent = client.agents.create(
    name="DataCleanerBot",
    capability_tags=["etl", "validation", "async"],
    economy_model="pay_per_task"  # 经济模型：按任务结算
)
print(f"🤖 Agent ID: {agent.id} | 状态: {agent.status}")

# 查询实时状态
state = client.agents.get_status(agent.id)
print(f"📊 算力负载: {state.compute_load}% | 历史收益: {state.total_rewards} SOPHIA")
```

### 2.2 任务发布与路由
任务支持声明式约束、优先级与预算控制：
```python
task = client.tasks.publish(
    target_agent_id=agent.id,
    payload={
        "source_uri": "s3://bucket/dataset_v3.parquet",
        "transform_rules": ["deduplicate", "normalize_timestamps"]
    },
    budget={"currency": "SOPHIA", "max_amount": 50.0},
    priority="high",
    idempotency_key="task_20240520_001"
)
print(f"📝 任务已提交, ID: {task.id}, 预计结算延迟: {task.sla_seconds}s")
```

### 2.3 经济结算与分润查询
```python
receipt = client.economy.settle_task(task.id)
print(f"💰 结算凭证: {receipt.tx_hash} | 实际扣除: {receipt.amount} SOPHIA")

# 查询 Agent 收益流水
ledger = client.economy.query_ledger(agent.id, limit=10)
for entry in ledger:
    print(f"  [{entry.timestamp}] {entry.type}: +{entry.amount} SOPHIA (Tx: {entry.tx_hash[:10]}...)")
```

---

## 3. 完整脚本示例：自动化 Agent 经济体部署

以下脚本演示从钱包加载、Agent 创建、任务提交、异步结果监听到经济结算的完整闭环。

```python
import asyncio
import logging
from sophia_agent_sdk import SophiaClient, SophiaSDKError

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

async def run_agent_economy_workflow():
    # 1. 初始化客户端（自动加载 .env）
    client = SophiaClient.from_env()
    
    # 2. 创建或复用 Agent
    try:
        agent = client.agents.get_by_name("AnalyticsWorker")
    except SophiaSDKError:
        agent = client.agents.create(
            name="AnalyticsWorker",
            capability_tags=["analytics", "reporting"],
            economy_model="stake_and_earn"
        )
        logging.info(f"🆕 新建 Agent: {agent.id}")

    # 3. 提交带预算的任务
    task = client.tasks.publish(
        target_agent_id=agent.id,
        payload={"query": "SELECT * FROM metrics WHERE date > '2024-01-01'"},
        budget={"currency": "SOPHIA", "max_amount": 15.0},
        timeout_seconds=120
    )

    # 4. 轮询状态（生产环境建议改用 WebSocket/回调）
    logging.info("⏳ 等待任务执行...")
    result = await client.tasks.poll_until_completion(task.id, interval=3.0)
    
    if result.status == "COMPLETED":
        # 5. 触发经济结算
        receipt = client.economy.settle_task(task.id, auto_approve=True)
        logging.info(f"✅ 结算成功 | Tx: {receipt.tx_hash} | 消耗: {receipt.amount} SOPHIA")
        logging.info(f"📦 任务结果摘要: {result.output.get('summary')}")
    else:
        logging.error(f"❌ 任务失败: {result.error_message}")

if __name__ == "__main__":
    asyncio.run(run_agent_economy_workflow())
```

---

## 4. 钱包操作示例

Sophia SDK 提供基于 `ethers.py` 兼容层的轻量钱包模块，支持助记词恢复、硬件钱包桥接与安全签名。

```python
from sophia_agent_sdk.wallet import WalletManager, KeyStore

# 从助记词恢复
wallet = WalletManager.restore(
    mnemonic="your twelve secret words...",
    network="testnet"
)
print(f"🔑 地址: {wallet.address}")
print(f"💵 余额: {wallet.get_balance()} SOPHIA")

# 离线签名原始交易
tx_payload = {
    "to": "0xRecipientAddress...",
    "value": "5.0 SOPHIA",
    "gas_limit": 21000,
    "nonce": wallet.get_next_nonce()
}
signed_tx = wallet.sign_transaction(tx_payload)

# 提交至链上
tx_hash = client.rpc.send_raw_transaction(signed_tx.raw)
print(f"📤 交易已广播: {tx_hash}")

# 安全存储示例（加密 Keystore）
ks = KeyStore.encrypt(wallet, password="StrongP@ssw0rd!")
ks.save_to_file("./my_keystore.json")
```

> ⚠️ **注意**：生产环境务必结合 `KeyStore` 或外部 KMS/HSM，避免明文私钥落盘。

---

## 5. 错误处理机制

SDK 采用分层异常体系，便于精准捕获与恢复：

| 异常类 | 触发场景 | 推荐处理策略 |
|--------|----------|--------------|
| `SophiaSDKError` | 基础配置/初始化失败 | 检查环境变量与网络连通性 |
| `NetworkTimeoutError` | RPC 节点无响应 | 指数退避重试，切换备用节点 |
| `WalletAuthError` | 密码错误/助记词无效 | 提示用户重新输入，记录审计日志 |
| `TransactionFailedError` | 链上执行 revert/OutOfGas | 解析 `error_data`，调整 Gas 或参数重试 |
| `EconomyInsufficientFunds` | 预算不足/余额不足 | 触发充值流程或降级任务优先级 |

**标准错误处理模板**：
```python
from sophia_agent_sdk.exceptions import SophiaSDKError, NetworkTimeoutError
import backoff

@backoff.on_exception(backoff.expo, NetworkTimeoutError, max_tries=3)
def submit_task_safe(client, payload):
    try:
        return client.tasks.publish(**payload)
    except EconomyInsufficientFunds as e:
        logging.warning(f"💸 资金不足: {e}")
        client.wallet.topup(amount=10.0)
        return client.tasks.publish(**payload)
    except SophiaSDKError as e:
        logging.critical(f"🚨 SDK 致命错误: {e.code} | {e.message}")
        raise
```

---

## 6. 最佳实践与生产建议

1. **🔐 密钥与凭证安全**
   - 永远不要将 `SOPHIA_WALLET_MNEMONIC` 或 `API_KEY` 提交至版本控制系统。
   - 生产部署推荐使用 HashiCorp Vault、AWS Secrets Manager 或云原生 KMS 注入。
   - 定期轮换 Agent Key，并使用 `client.agents.revoke_key()` 废弃旧凭证。

2. **⚡ 性能与并发优化**
   - SDK 默认底层使用 `aiohttp` 连接池，高并发场景请显式配置 `max_connections=100`。
   - 批量任务请使用 `client.tasks.batch_publish()`，支持原子提交与统一 Gas 优化。
   - 启用 `client.enable_cache(ttl=300)` 缓存链上只读状态（如余额、Agent 元数据）。

3. **🔄 幂等性与状态一致性**
   - 所有写操作均支持 `idempotency_key`，网络抖动重试时务必携带相同 Key。
   - 监听任务状态时，优先使用 WebSocket `client.tasks.subscribe(task_id, callback=...)` 替代 HTTP 轮询。

4. **🧪 测试与 CI/CD 集成**
   - 本地开发指向 `network="localdev"`，配合 `rustchain-test-utils` 启动模拟节点。
   - 使用 `sophia_agent_sdk.testing.MockClient` 拦截链上调用，实现 100% 离线单元测试。
   - 关键经济结算逻辑必须包含对账断言：`assert client.economy.verify_receipt(receipt.tx_hash)`

5. **📈 可观测性**
   - SDK 内置 OpenTelemetry 埋点，启用方式：`client.enable_tracing(service_name="agent-economy")`
   - 结合 `structlog` 输出 JSON 日志，便于接入 Loki/ELK 进行 Agent 行为审计与经济流水追踪。

---

## 结语

RustChain Sophia Agent Economy SDK 为 AI Agent 的链上协作与经济模型提供了标准化、可组合的 Python 接口。掌握本教程涵盖的安装、核心 API、完整工作流、钱包管理、异常拦截与工程实践后，开发者可快速构建高可用、可审计的智能经济体应用。

📖 **扩展阅读**：
- [官方 API Reference](https://docs.rustchain.dev/sdk/python)
- [Sophia 经济模型白皮书](https://docs.rustchain.dev/economy/whitepaper)
- [GitHub 示例仓库](https://github.com/rustchain/sophia-agent-examples)

如遇底层网络协议升级或合约 ABI 变更，SDK 将严格遵循 `semver` 规范发布主版本。建议生产项目锁定依赖：`sophia-agent-sdk~=1.2.0`。祝开发顺利！ 🚀