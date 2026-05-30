# RustChain 统一 API 参考

> **版本:** 2.2.1-rip200
> **基础 URL:** `https://rustchain.org`
> **内部 URL:** `http://localhost:8099` (仅限 VPS)
> **内部开发:** `http://localhost:5000` (桥接 API 开发)
> **内部节点:** `http://localhost:8765` (WebSocket 数据流)

所有公共端点均使用 HTTPS。对于生产环境调用，请使用严格的 TLS 验证。
对于使用自签名证书的本地开发，请使用 `curl -sk` 或 Python 中的 `verify=False`。

---

## 目录

- [身份验证](#身份验证)
- [1. 网络与状态](#1-网络与状态)
- [2. 矿工](#2-矿工)
- [3. 钱包](#3-钱包)
- [4. 认证 (Attestation)](#4-认证)
- [5. 结算](#5-结算)
- [6. 桥接 (跨链)](#6-桥接-跨链)
- [7. 锁定账本](#7-锁定账本)
- [8. WebSocket 数据流](#8-websocket-数据流)
- [9. 管理员端点](#9-管理员端点)
- [10. 高级 / x402](#10-高级--x402)
- [错误代码](#错误代码)
- [速率限制](#速率限制)
- [SDK 示例](#sdk-示例)

---

## 身份验证

大多数端点是**公共的**，无需身份验证。

### 管理员端点

需要 `X-Admin-Key` 请求头：

```bash
-H "X-Admin-Key: YOUR_ADMIN_KEY"
```

### 桥接服务回调

使用 API 密钥进行身份验证：

```bash
-H "X-API-Key: <bridge-api-key>"
```

### 工作节点端点

使用工作节点密钥进行身份验证：

```bash
-H "X-Worker-Key: <worker-key>"
```

### 签名转账

钱包到钱包的转账需要 Ed25519 签名（无需管理员密钥，请参阅 [POST /wallet/transfer/signed](#post-wallettransfersigned)）。

---

## 1. 网络与状态

### GET /health

检查节点健康状态。

**方法:** `GET`
**路径:** `/health`
**权限:** 无

**cURL:**
```bash
curl -fsS https://rustchain.org/health | jq .
```

**响应 (200 OK):**
```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 18728,
  "db_rw": true,
  "backup_age_hours": 6.75,
  "tip_age_slots": 0
}
```

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| `ok` | boolean | 节点健康 |
| `version` | string | 协议版本 |
| `uptime_s` | integer | 节点启动后的秒数 |
| `db_rw` | boolean | 数据库可读写 |
| `backup_age_hours` | float | 上次备份至今的小时数 |
| `tip_age_slots` | integer | 落后于最新区块的槽位 (0 = 已同步) |

**错误代码:** `500 INTERNAL_ERROR` (节点不健康)

---

### GET /ready

Kubernetes 风格的就绪探针。

**方法:** `GET`
**路径:** `/ready`
**权限:** 无

**cURL:**
```bash
curl -fsS https://rustchain.org/ready | jq .
```

**响应 (200 OK):**
```json
{
  "ready": true
}
```

---

### GET /epoch

获取当前纪元 (epoch) 和槽位 (slot) 信息。

**方法:** `GET`
**路径:** `/epoch`
**权限:** 无

**cURL:**
```bash
curl -fsS https://rustchain.org/epoch | jq .
```

**响应 (200 OK):**
```json
{
  "epoch": 62,
  "slot": 9010,
  "blocks_per_epoch": 144,
  "epoch_pot": 1.5,
  "enrolled_miners": 2,
  "total_supply_rtc": 8388608
}
```

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| `epoch` | integer | 当前纪元编号 |
| `slot` | integer | 纪元内的当前槽位 |
| `blocks_per_epoch` | integer | 每个纪元的槽位数 (144 = ~24小时) |
| `epoch_pot` | float | 本纪元的 RTC 奖励池 |
| `enrolled_miners` | integer | 本纪元活跃的矿工数 |
| `total_supply_rtc` | integer | 流通中的 RTC 总量 |

**错误代码:** `500 INTERNAL_ERROR`

---

### GET /api/network

获取包括已连接对等节点在内的网络级信息。

**方法:** `GET`
**路径:** `/api/network`
**权限:** 无

**cURL:**
```bash
curl -fsS https://rustchain.org/api/network | jq .
```

---

### GET /api/peers

列出已连接的网络对等节点。

**方法:** `GET`
**路径:** `/api/peers`
**权限:** 无

**cURL:**
```bash
curl -fsS https://rustchain.org/api/peers | jq .
```

---

## 2. 矿工

### GET /api/miners

列出所有带有硬件详情的活跃/注册矿工。

**方法:** `GET`
**路径:** `/api/miners`
**权限:** 无

**cURL:**
```bash
curl -fsS https://rustchain.org/api/miners | jq .
```

**响应 (200 OK):**
```json
[
  {
    "miner": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC",
    "device_arch": "G4",
    "device_family": "PowerPC",
    "hardware_type": "PowerPC G4 (古董)",
    "antiquity_multiplier": 2.5,
    "entropy_score": 0.0,
    "last_attest": 1770112912
  },
  {
    "miner": "g5-selena-179",
    "device_arch": "G5",
    "device_family": "PowerPC",
    "hardware_type": "PowerPC G5 (古董)",
    "antiquity_multiplier": 2.0,
    "entropy_score": 0.0,
    "last_attest": 1770112865
  }
]
```

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| `miner` | string | 矿工钱包 ID |
| `device_arch` | string | CPU 架构 (G4, G5, x86_64, M2 等) |
| `device_family` | string | CPU 系列 (PowerPC, Intel 等) |
| `hardware_type` | string | 人类可读的硬件描述 |
| `antiquity_multiplier` | float | 奖励乘数 (1.0–2.5x) |
| `entropy_score` | float | 硬件熵质量 |
| `last_attest` | integer | 上次认证的 Unix 时间戳 |

**错误代码:** `500 INTERNAL_ERROR`

---

### GET /api/nodes

列出已连接的认证节点。

**方法:** `GET`
**路径:** `/api/nodes`
**权限:** 无

**cURL:**
```bash
curl -fsS https://rustchain.org/api/nodes | jq .
```

**响应 (200 OK):**
```json
[
  {
    "node_id": "primary",
    "address": "50.28.86.131",
    "role": "attestation",
    "status": "active",
    "last_seen": 1771187406
  },
  {
    "node_id": "ergo-anchor",
    "address": "50.28.86.153",
    "role": "anchor",
    "status": "active",
    "last_seen": 1771187400
  }
]
```

---

## 3. 钱包

### GET /wallet/balance

检查矿工钱包的 RTC 余额。

**方法:** `GET`
**路径:** `/wallet/balance`
**权限:** 无

**查询参数:**

| 参数 | 类型 | 必须 | 描述 |
|-----------|------|----------|-------------|
| `miner_id` | string | 是* | 钱包标识符 (规范名称) |
| `address` | string | 是* | 向后兼容的别名 |

*必须提供 `miner_id` 或 `address` 其中之一。

**cURL:**
```bash
curl -fsS "https://rustchain.org/wallet/balance?miner_id=scott" | jq .
```

**响应 (200 OK):**
```json
{
  "ok": true,
  "miner_id": "scott",
  "amount_rtc": 118.357193,
  "amount_i64": 118357193
}
```

**错误响应 (404):**
```json
{
  "ok": false,
  "error": "WALLET_NOT_FOUND",
  "miner_id": "unknown"
}
```

---

### GET /wallet/history

读取钱包的近期转账记录。公共的，钱包作用域。

**方法:** `GET`
**路径:** `/wallet/history`
**权限:** 无

**查询参数:**

| 参数 | 类型 | 必须 | 描述 |
|-----------|------|----------|-------------|
| `miner_id` | string | 是* | 钱包标识符 |
| `address` | string | 是* | 向后兼容别名 |
| `limit` | integer | 否 | 最大记录数 (1–200, 默认: 50) |

*必须提供 `miner_id` 或 `address` 其中之一。若两者皆提供，它们必须匹配。

**cURL:**
```bash
curl -fsS "https://rustchain.org/wallet/history?miner_id=scott&limit=10" | jq .
```

**响应 (200 OK):**
```json
[
  {
    "tx_id": "6df5d4d25b6deef8f0b2e0fa726cecf1",
    "tx_hash": "6df5d4d25b6deef8f0b2e0fa726cecf1",
    "from_addr": "aliceRTC",
    "to_addr": "bobRTC",
    "amount": 1.25,
    "amount_i64": 1250000,
    "amount_rtc": 1.25,
    "timestamp": 1772848800,
    "created_at": 1772848800,
    "confirmed_at": null,
    "confirms_at": 1772935200,
    "status": "pending",
    "raw_status": "pending",
    "status_reason": null,
    "confirmations": 0,
    "direction": "sent",
    "counterparty": "bobRTC",
    "reason": "signed_transfer:payment",
    "memo": "payment"
  }
]
```

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| `tx_id` | string | 交易哈希，或 `pending_{id}` (待定) |
| `from_addr` | string | 发送方钱包地址 |
| `to_addr` | string | 接收方钱包地址 |
| `amount` | float | RTC 金额 (人类可读) |
| `amount_i64` | integer | 微 RTC 金额 (6 位小数) |
| `timestamp` | integer | 创建 Unix 时间戳 |
| `status` | string | `pending` (待定), `confirmed` (确认), 或 `failed` (失败) |
| `direction` | string | `sent` (发送) 或 `received` (接收) |
| `counterparty` | string | 对手钱包 |
| `memo` | string\|null | 来自 `signed_transfer:` 前缀的备注 |
| `confirmed_at` | integer\|null | 确认时间戳 |
| `confirms_at` | integer\|null | 计划确认时间 |

**注意:**
- 按 `created_at DESC, id DESC` 排序 (从新到旧)
- 没有历史记录的钱包返回空数组 `[]` (不是错误)
- 不存在的钱包返回空数组

**错误响应 (400):**
```json
{ "ok": false, "error": "需要 miner_id 或 address" }
{ "ok": false, "error": "若两者皆提供，miner_id 和 address 必须匹配" }
{ "ok": false, "error": "limit 必须为整数" }
```

---

### POST /wallet/transfer/signed

将 RTC 转账到另一个钱包。需要 Ed25519 签名。无需管理员密钥 — 使用加密证明。

**方法:** `POST`
**路径:** `/wallet/transfer/signed`
**权限:** Ed25519 签名

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/wallet/transfer/signed \
  -H "Content-Type: application/json" \
  -d '{
    "from_address": "RTCaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "to_address": "RTCbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "amount_rtc": 1.5,
    "nonce": 12345,
    "memo": "",
    "public_key": "ed25519_public_key_hex",
    "signature": "ed25519_signature_hex",
    "chain_id": "rustchain-mainnet-v2"
  }'
```

**响应 (200 OK):**
```json
{
  "ok": true,
  "verified": true,
  "phase": "pending",
  "tx_hash": "abc123...",
  "amount_rtc": 1.5,
  "chain_id": "rustchain-mainnet-v2",
  "confirms_in_hours": 24
}
```

**重要提示:**
- 地址必须为 `RTC...` 格式 (43 个字符: `RTC` + 40 个十六进制字符)
- Nonce 必须在每次转账时唯一
- 确认需要 24 小时

**错误代码:** `400 INVALID_SIGNATURE`, `400 INSUFFICIENT_BALANCE`, `400 BAD_REQUEST`

---

### GET /wallet/swap-info

获取 USDC/wRTC 交换指南 (高级 x402 端点，目前在测试版免费)。

**方法:** `GET`
**路径:** `/wallet/swap-info`
**权限:** 无 (x402 付款协议，测试版免费)

**cURL:**
```bash
curl -fsS https://rustchain.org/wallet/swap-info | jq .
```

**响应 (200 OK):**
```json
{
  "rtc_price_usd": 0.10,
  "wrtc_solana_mint": "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X",
  "wrtc_base_contract": "0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6",
  "raydium_pool": "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb",
  "bridge_url": "https://bottube.ai/bridge"
}
```

---

### GET /explorer

用于浏览区块和交易的网页界面。返回 HTML。

**方法:** `GET`
**路径:** `/explorer`
**权限:** 无
**响应:** HTML 页面 (区块浏览器网页界面)

---

## 4. 认证 (Attestation)

### POST /attest/submit

提交硬件指纹以进行纪元注册。该认证验证矿工是否运行在真实的物理硬件上 (而非虚拟机)。

**方法:** `POST`
**路径:** `/attest/submit`
**权限:** Ed25519 签名

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/attest/submit \
  -H "Content-Type: application/json" \
  -d '{
    "miner_id": "your_miner_id",
    "fingerprint": {
      "clock_skew": {"drift_ppm": 24.3, "jitter_ns": 1247},
      "cache_timing": {"l1_latency_ns": 5, "l2_latency_ns": 15},
      "simd_identity": {"instruction_set": "AltiVec", "pipeline_bias": 0.76},
      "thermal_entropy": {"idle_temp_c": 42.1, "load_temp_c": 71.3, "variance": 3.8},
      "instruction_jitter": {"mean_ns": 3200, "stddev_ns": 890},
      "behavioral_heuristics": {"cpuid_clean": true, "no_hypervisor": true}
    },
    "signature": "base64_ed25519_signature"
  }'
```

**响应 (成功, 200 OK):**
```json
{
  "success": true,
  "enrolled": true,
  "epoch": 62,
  "multiplier": 2.5,
  "next_settlement_slot": 9216
}
```

**响应 (检测到虚拟机, 400):**
```json
{
  "success": false,
  "error": "VM_DETECTED",
  "check_failed": "behavioral_heuristics",
  "detail": "在 CPUID 中检测到管理程序特征"
}
```

**响应 (硬件已被绑定, 409):**
```json
{
  "error": "HARDWARE_ALREADY_BOUND",
  "existing_miner": "其他_钱包"
}
```

---

### GET /lottery/eligibility

检查矿工是否在本纪元已注册并具有资格。

**方法:** `GET`
**路径:** `/lottery/eligibility`
**权限:** 无

**查询参数:**

| 参数 | 类型 | 必须 | 描述 |
|-----------|------|----------|-------------|
| `miner_id` | string | 是 | 钱包标识符 |

**cURL:**
```bash
curl -fsS "https://rustchain.org/lottery/eligibility?miner_id=scott" | jq .
```

**响应 (有资格, 200 OK):**
```json
{
  "eligible": true,
  "reason": null,
  "rotation_size": 27,
  "slot": 13840,
  "slot_producer": "矿工名称"
}
```

**响应 (无资格, 200 OK):**
```json
{
  "eligible": false,
  "reason": "not_attested",
  "rotation_size": 27,
  "slot": 13839,
  "slot_producer": null
}
```

---

## 5. 结算

### GET /api/settlement/{epoch}

查询特定纪元的历史结算数据。

**方法:** `GET`
**路径:** `/api/settlement/{epoch}`
**权限:** 无

**cURL:**
```bash
curl -fsS https://rustchain.org/api/settlement/75 | jq .
```

**响应 (200 OK):**
```json
{
  "epoch": 75,
  "timestamp": 1771200000,
  "total_pot": 1.5,
  "total_distributed": 1.5,
  "miner_count": 5,
  "settlement_hash": "8a3f2e1d9c7b6a5e4f3d2c1b0a9e8d7c...",
  "ergo_tx_id": "abc123...",
  "rewards": {
    "scott": 0.487,
    "pffs1802": 0.390,
    "miner3": 0.195,
    "miner4": 0.195,
    "miner5": 0.234
  }
}
```

**错误代码:** `404 NOT_FOUND` (找不到该纪元)

---

## 6. 桥接 (跨链)

桥接 API 管理 RustChain 与外部链 (Solana, Ergo, Base) 之间的跨链转账。遵循 RIP-0305 Track C。

### POST /api/bridge/initiate

发起跨链转账 (存入或取出)。

**方法:** `POST`
**路径:** `/api/bridge/initiate`
**权限:** 无 (用户发起)

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/api/bridge/initiate \
  -H "Content-Type: application/json" \
  -d '{
    "direction": "deposit",
    "source_chain": "rustchain",
    "dest_chain": "solana",
    "source_address": "RTC_miner123",
    "dest_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
    "amount_rtc": 100.0,
    "memo": "跨链存入"
  }'
```

**请求字段:**

| 字段 | 类型 | 必须 | 描述 |
|-------|------|----------|-------------|
| `direction` | string | 是 | `deposit` (RTC→外部) 或 `withdraw` (外部→RTC) |
| `source_chain` | string | 是 | `rustchain`, `solana`, `ergo`, `base` |
| `dest_chain` | string | 是 | 必须与来源链不同 |
| `source_address` | string | 是 | 源钱包地址 |
| `dest_address` | string | 是 | 目标钱包地址 |
| `amount_rtc` | number | 是 | RTC 金额 (最小值: 1.0) |
| `memo` | string | 否 | 可选备注 (最多 256 字符) |

**响应 (200 OK):**
```json
{
  "ok": true,
  "bridge_transfer_id": 12345,
  "tx_hash": "abc123def456...",
  "status": "pending",
  "lock_epoch": 85,
  "unlock_at": 1709942400,
  "estimated_completion": "2026-03-10T12:00:00Z",
  "direction": "deposit",
  "source_chain": "rustchain",
  "dest_chain": "solana",
  "amount_rtc": 100.0
}
```

**错误响应 (400):**
```json
{
  "error": "余额不足",
  "available_rtc": 50.0,
  "pending_debits_rtc": 20.0,
  "requested_rtc": 100.0
}
```
```json
{
  "error": "无效的 solana 地址: 长度必须为 32-44 个字符"
}
```

---

### GET /api/bridge/status/{tx_hash}

查询跨链转账的状态。

**方法:** `GET`
**路径:** `/api/bridge/status/{tx_hash}` 或 `/api/bridge/status?tx_hash=...` 或 `/api/bridge/status?id=...`
**权限:** 无

**cURL:**
```bash
curl -fsS https://rustchain.org/api/bridge/status/abc123def456 | jq .
```

**响应 (200 OK):**
```json
{
  "ok": true,
  "transfer": {
    "id": 12345,
    "direction": "deposit",
    "source_chain": "rustchain",
    "dest_chain": "solana",
    "source_address": "RTC_miner123",
    "dest_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
    "amount_rtc": 100.0,
    "bridge_type": "bottube",
    "external_tx_hash": "5xKjPqR...",
    "external_confirmations": 8,
    "required_confirmations": 12,
    "status": "confirming",
    "lock_epoch": 85,
    "created_at": 1709856000,
    "updated_at": 1709859600,
    "expires_at": 1710460800,
    "tx_hash": "abc123def456...",
    "memo": null
  }
}
```

**状态值:**

| 状态 | 描述 |
|--------|-------------|
| `pending` | 转账已发起，等待锁定 |
| `locked` | 资产已锁定，等待外部确认 |
| `confirming` | 外部确认中 |
| `completed` | 转账成功 |
| `failed` | 转账失败 |
| `voided` | 由管理员/用户作废 |

**错误响应 (404):**
```json
{ "error": "找不到桥接转账记录" }
```

---

### GET /api/bridge/list

列出带有可选过滤器的跨链转账。

**方法:** `GET`
**路径:** `/api/bridge/list`
**权限:** 无

**查询参数:**

| 参数 | 类型 | 默认 | 描述 |
|-----------|------|---------|-------------|
| `status` | string | — | 按状态过滤 |
| `source_address` | string | — | 按源地址过滤 |
| `dest_address` | string | — | 按目标地址过滤 |
| `direction` | string | — | 按方向过滤 |
| `limit` | integer | 100 | 最大结果数 (最大: 500) |

**cURL:**
```bash
curl -fsS "https://rustchain.org/api/bridge/list?status=pending&limit=50" | jq .
```

**响应 (200 OK):**
```json
{
  "ok": true,
  "count": 3,
  "transfers": [
    {
      "id": 12345,
      "direction": "deposit",
      "source_chain": "rustchain",
      "dest_chain": "solana",
      "amount_rtc": 100.0,
      "status": "confirming"
    }
  ]
}
```

---

### POST /api/bridge/void

作废待定的跨链转账。**仅限管理员。**

**方法:** `POST`
**路径:** `/api/bridge/void`
**权限:** `X-Admin-Key`

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/api/bridge/void \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tx_hash": "abc123def456...",
    "reason": "用户请求",
    "voided_by": "admin_john"
  }'
```

**响应 (200 OK):**
```json
{
  "ok": true,
  "voided_id": 12345,
  "tx_hash": "abc123def456...",
  "amount_rtc": 100.0,
  "voided_by": "admin_john",
  "reason": "用户请求",
  "lock_released": true
}
```

---

### POST /api/bridge/update-external

更新外部交易确认数据。**仅限桥接服务回调。**

**方法:** `POST`
**路径:** `/api/bridge/update-external`
**权限:** `X-API-Key`

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/api/bridge/update-external \
  -H "X-API-Key: BRIDGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tx_hash": "abc123def456...",
    "external_tx_hash": "5xKjPqR...",
    "confirmations": 8,
    "required_confirmations": 12
  }'
```

---

## 7. 锁定账本

### GET /api/lock/miner/{miner_id}

获取矿工的锁定账本条目。

**方法:** `GET`
**路径:** `/api/lock/miner/{miner_id}`
**权限:** 无

**查询参数:**

| 参数 | 类型 | 默认 | 描述 |
|-----------|------|---------|-------------|
| `status` | string | — | `locked`, `released`, `forfeited`, 或 `summary` |
| `limit` | integer | 100 | 最大结果数 |

**cURL:**
```bash
curl -fsS "https://rustchain.org/api/lock/miner/RTC_miner123?status=summary" | jq .
```

**响应 — 摘要 (200 OK):**
```json
{
  "miner_id": "RTC_miner123",
  "total_locked_rtc": 150.0,
  "total_locked_count": 3,
  "breakdown": {
    "bridge_deposit": { "amount_rtc": 100.0, "count": 2 },
    "bridge_withdraw": { "amount_rtc": 50.0, "count": 1 }
  },
  "next_unlock": {
    "unlock_at": 1709942400,
    "amount_rtc": 50.0,
    "seconds_until": 86400
  }
}
```

**响应 — 列表 (200 OK):**
```json
{
  "ok": true,
  "miner_id": "RTC_miner123",
  "count": 2,
  "locks": [
    {
      "id": 789,
      "amount_rtc": 50.0,
      "lock_type": "bridge_deposit",
      "status": "locked",
      "locked_at": 1709856000,
      "unlock_at": 1709942400,
      "time_until_unlock": 86400
    }
  ]
}
```

---

### GET /api/lock/pending-unlock

获取准备解锁的锁定记录。

**方法:** `GET`
**路径:** `/api/lock/pending-unlock`
**权限:** 无

**查询参数:**

| 参数 | 类型 | 默认 | 描述 |
|-----------|------|---------|-------------|
| `before` | integer | — | Unix 时间戳过滤器 |
| `limit` | integer | 100 | 最大结果数 |

**cURL:**
```bash
curl -fsS "https://rustchain.org/api/lock/pending-unlock?limit=50" | jq .
```

---

### POST /api/lock/release

手动释放锁定。**仅限管理员。**

**方法:** `POST`
**路径:** `/api/lock/release`
**权限:** `X-Admin-Key`

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/api/lock/release \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "lock_id": 789,
    "release_tx_hash": "可选_tx_hash"
  }'
```

---

### POST /api/lock/forfeit

没收锁定 (惩罚/削减)。**仅限管理员。**

**方法:** `POST`
**路径:** `/api/lock/forfeit`
**权限:** `X-Admin-Key`

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/api/lock/forfeit \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "lock_id": 789,
    "reason": "惩罚"
  }'
```

---

### POST /api/lock/auto-release

自动释放已过期的锁定。**仅限工作节点。**

**方法:** `POST`
**路径:** `/api/lock/auto-release`
**权限:** `X-Worker-Key`

**查询参数:**

| 参数 | 类型 | 默认 | 描述 |
|-----------|------|---------|-------------|
| `batch_size` | integer | 100 | 每次调用的最大解锁数 |

---

## 8. WebSocket 数据流

用于区块浏览器实时推送的 WebSocket。连接到内部 WebSocket 服务器 (端口 8765)，路径为 `/ws` 或 `/socket.io/` (由 nginx 代理)。

**端点:** `wss://rustchain.org/ws` 或 `wss://rustchain.org/socket.io/`

### 连接

```javascript
// 原生 WebSocket
const ws = new WebSocket("wss://rustchain.org/ws");

// Socket.IO (自动重连)
const socket = io("https://rustchain.org", {
  path: "/socket.io/",
  transports: ["websocket"]
});
```

### 客户端 → 服务器事件

| 事件 | 负载 | 描述 |
|-------|---------|-------------|
| `connect` | — | 客户端连接 |
| `disconnect` | — | 客户端断开连接 |
| `ping` | — | 心跳 Ping |
| `subscribe` | `{ room: string }` | 订阅频道 |
| `unsubscribe` | `{ room: string }` | 取消订阅频道 |
| `request_state` | — | 请求当前状态 |
| `request_metrics` | — | 请求服务器指标 |

### 服务器 → 客户端事件

| 事件 | 负载 | 描述 |
|-------|---------|-------------|
| `connected` | `{ timestamp, state }` | 欢迎消息 |
| `connection_status` | `{ status, server_version }` | 连接状态 |
| `block` | `{ height, hash, timestamp, miners_count, reward, epoch, slot }` | 新区块产生 |
| `attestation` | `{ miner_id, device_arch, multiplier, epoch, weight, ticket_id }` | 新认证 |
| `epoch_settlement` | `{ epoch, total_blocks, total_reward, miners_count }` | 纪元终结 |
| `miner_update` | `{ miners: [] }` | 矿工列表已更新 |
| `epoch_update` | `{ epoch, ... }` | 纪元信息已更新 |
| `health` | `{ ok, service, ... }` | 健康状态 |
| `pong` | `{ timestamp }` | 心跳响应 |

### JavaScript 使用示例

```javascript
// 检查连接状态
const state = RustChainWebSocket.getState();
console.log(state.isConnected);

// 监听事件
RustChainWebSocket.on('block', (block) => {
  console.log('新区块:', block.height);
});

RustChainWebSocket.on('attestation', (attestation) => {
  console.log('新矿工认证:', attestation.miner_id);
});

// 手动连接/断开
RustChainWebSocket.disconnect();
RustChainWebSocket.connect();
RustChainWebSocket.requestState();
```

### 性能

- **延迟:** 实时更新延迟 < 100ms
- **连接数:** 支持 1000+ 并发客户端
- **自动重连:** 具有指数退避机制的最大尝试次数
- **回退:** 若 WebSocket 不可用，则使用 HTTP 轮询

---

## 9. 管理员端点

### POST /wallet/transfer

在钱包之间转账 RTC。**仅限管理员。**

**方法:** `POST`
**路径:** `/wallet/transfer`
**权限:** `X-Admin-Key`

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/wallet/transfer \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "from_miner": "treasury",
    "to_miner": "scott",
    "amount_rtc": 10.0,
    "memo": "赏金支付 #123"
  }'
```

**响应 (200 OK):**
```json
{
  "ok": true,
  "tx_id": "tx_abc123...",
  "from_balance": 990.0,
  "to_balance": 52.5
}
```

---

### POST /rewards/settle

手动触发纪元结算。**仅限管理员。**

**方法:** `POST`
**路径:** `/rewards/settle`
**权限:** `X-Admin-Key`

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/rewards/settle \
  -H "X-Admin-Key: YOUR_ADMIN_KEY"
```

**响应 (200 OK):**
```json
{
  "ok": true,
  "epoch": 75,
  "miners_rewarded": 5,
  "total_distributed": 1.5,
  "settlement_hash": "8a3f2e1d..."
}
```

---

## 10. 高级 / x402

这些端点支持 x402 付款协议。目前 **测试版免费**。

### GET /api/premium/videos

批量视频导出 (BoTTube 集成)。

**方法:** `GET`
**路径:** `/api/premium/videos` (在 `https://bottube.ai`)
**权限:** x402 (测试版免费)

**cURL:**
```bash
curl -fsS https://bottube.ai/api/premium/videos | jq .
```

### GET /api/premium/analytics/{agent}

深度代理分析。

**方法:** `GET`
**路径:** `/api/premium/analytics/{agent}` (在 `https://bottube.ai`)
**权限:** x402 (测试版免费)

**cURL:**
```bash
curl -fsS https://bottube.ai/api/premium/analytics/scott | jq .
```

### GET /beacon/api/x402/status

Beacon x402 状态端点。

**cURL:**
```bash
curl -fsS https://rustchain.org/beacon/api/x402/status | jq .
```

### GET /beacon/api/premium/reputation

Beacon 信誉导出。

**cURL:**
```bash
curl -fsS https://rustchain.org/beacon/api/premium/reputation | jq .
```

### GET /beacon/api/premium/contracts/export

Beacon 合约导出。

**cURL:**
```bash
curl -fsS https://rustchain.org/beacon/api/premium/contracts/export | jq .
```

---

## 错误代码

| HTTP 代码 | 错误 | 描述 |
|-----------|-------|-------------|
| 200 | — | 成功 |
| 400 | `BAD_REQUEST` | 无效的 JSON 或参数 |
| 400 | `VM_DETECTED` | 硬件指纹验证失败 (检测到虚拟机) |
| 400 | `INVALID_SIGNATURE` | Ed25519 签名验证失败 |
| 400 | `INSUFFICIENT_BALANCE` | RTC 余额不足 |
| 401 | `UNAUTHORIZED` | 无权限或无效的身份验证密钥 |
| 404 | `NOT_FOUND` | 找不到端点、资源或矿工 |
| 409 | `HARDWARE_ALREADY_BOUND` | 硬件已绑定到其他钱包 |
| 429 | `RATE_LIMITED` | 请求过多 |
| 500 | `INTERNAL_ERROR` | 服务器错误 |

---

## 速率限制

| 端点 | 限制 |
|----------|-------|
| `/health`, `/ready` | 60/分钟 |
| `/epoch`, `/api/miners`, `/api/nodes` | 30/分钟 |
| `/wallet/balance` | 30/分钟 |
| `/wallet/history` | 30/分钟 |
| `/attest/submit` | 每矿工每 10 分钟 1 次 |
| `/wallet/transfer/signed` | 每钱包每分钟 10 次 |
| 管理员端点 | 10/分钟 |
| 桥接端点 | 100/分钟 |
| 公共端点 (常规) | 100/分钟 |

---

## 桥接配置

| 环境变量 | 默认 | 描述 |
|---------------------|---------|-------------|
| `RC_BRIDGE_DEFAULT_CONFIRMATIONS` | 12 | 所需的外部确认数 |
| `RC_BRIDGE_LOCK_EXPIRY_SECONDS` | 604800 | 最大锁定持续时间 (7 天) |
| `RC_BRIDGE_MIN_AMOUNT_RTC` | 1.0 | 最小桥接金额 |
| `RC_BRIDGE_API_KEY` | — | 桥接回调 API 密钥 |

---

## SDK 示例

### Python — 快速入门

```python
import requests

BASE_URL = "https://rustchain.org"

# 健康检查
resp = requests.get(f"{BASE_URL}/health")
data = resp.json()
print(f"节点 OK: {data['ok']}, 版本: {data['version']}")

# 纪元信息
resp = requests.get(f"{BASE_URL}/epoch")
data = resp.json()
print(f"纪元 {data['epoch']}, 槽位 {data['slot']}/{data['blocks_per_epoch']}")
print(f"奖励池: {data['epoch_pot']} RTC, 矿工数: {data['enrolled_miners']}")

# 钱包余额
resp = requests.get(
    f"{BASE_URL}/wallet/balance",
    params={"miner_id": "scott"},
)
data = resp.json()
print(f"余额: {data['amount_rtc']} RTC ({data['amount_i64']} 微 RTC)")

# 列出矿工
resp = requests.get(f"{BASE_URL}/api/miners")
for m in resp.json():
    print(f"{m['miner'][:20]}... | {m['device_arch']} | 乘数={m['antiquity_multiplier']}x")
```

### Python — 签名转账

```python
import requests
import json
import nacl.signing
import nacl.encoding
import hashlib

# 加载您的 Ed25519 私钥
with open("/path/to/your/agent.key", "rb") as f:
    private_key = nacl.signing.SigningKey(f.read())

# 从公钥派生 RTC 地址
public_key_hex = private_key.verify_key.encode().hex()
from_address = "RTC" + hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:40]

# 创建规范消息
transfer_msg = {
    "from": from_address,
    "to": "RTC_recipient_address",
    "amount": 100,
    "nonce": "1234567890",
    "memo": "",
    "chain_id": "rustchain-mainnet-v2"
}

# 签名
message = json.dumps(transfer_msg, sort_keys=True, separators=(",", ":")).encode()
signed = private_key.sign(message)
signature_hex = signed.signature.hex()

# 构建外层负载
payload = {
    "from_address": from_address,
    "to_address": "RTC_recipient_address",
    "amount_rtc": 100,
    "nonce": "1234567890",
    "memo": "",
    "chain_id": "rustchain-mainnet-v2",
    "public_key": public_key_hex,
    "signature": signature_hex
}

# 发送
resp = requests.post(
    f"{BASE_URL}/wallet/transfer/signed",
    json=payload,
)
print(resp.json())
```

### Python — 桥接存入

```python
def initiate_bridge_deposit(miner_id, dest_address, amount_rtc):
    """发起从 RustChain 到 Solana 的桥接存入。"""
    resp = requests.post(
        f"{BASE_URL}/api/bridge/initiate",
        json={
            "direction": "deposit",
            "source_chain": "rustchain",
            "dest_chain": "solana",
            "source_address": miner_id,
            "dest_address": dest_address,
            "amount_rtc": amount_rtc,
        }
    )
    result = resp.json()
    if resp.status_code == 200:
        print(f"桥接已发起: {result['tx_hash']}")
        print(f"状态: {result['status']}")
        return result
    else:
        print(f"错误: {result}")
        return None

result = initiate_bridge_deposit(
    miner_id="RTC_miner123",
    dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
    amount_rtc=100.0
)
```

### Python — 错误处理

```python
import requests

try:
    resp = requests.get(
        f"{BASE_URL}/wallet/balance",
        params={"miner_id": "nonexistent"},
        timeout=5
    )
    if resp.status_code == 200:
        print(resp.json())
    else:
        print(f"错误 {resp.status_code}: {resp.text}")
except requests.exceptions.Timeout:
    print("请求超时 — 节点可能负载过重")
except requests.exceptions.ConnectionError:
    print("连接失败 — 节点可能离线")
```

### JavaScript — 快速入门

```javascript
const BASE_URL = "https://rustchain.org";

async function getBalance(minerId) {
  const resp = await fetch(`${BASE_URL}/wallet/balance?miner_id=${minerId}`);
  return resp.json();
}

async function getEpoch() {
  const resp = await fetch(`${BASE_URL}/epoch`);
  return resp.json();
}

// 使用示例
getBalance("scott").then(console.log);
getEpoch().then(console.log);
```

### Bash — 快速入门

```bash
#!/bin/bash
BASE_URL="https://rustchain.org"

# 健康检查
curl -fsS "$BASE_URL/health" | jq .

# 获取余额
get_balance() {
  curl -fsS "$BASE_URL/wallet/balance?miner_id=$1" | jq .
}
get_balance "scott"

# 获取纪元信息
get_epoch() {
  curl -fsS "$BASE_URL/epoch" | jq .
}
get_epoch
```

---

## 常见错误

### 错误的端点

| ❌ 错误 | ✅ 正确 |
|----------|-----------|
| `/balance/{address}` | `/wallet/balance?miner_id=NAME` |
| `/miners?limit=N` | `/api/miners` (无分页) |
| `/block/{height}` | `/explorer` (网页界面) |
| `/api/balance` | `/wallet/balance?miner_id=...` |

### 错误的字段名称

| ❌ 错误 | ✅ 正确 |
|----------|-----------|
| `epoch_number` | `epoch` |
| `current_slot` | `slot` |
| `miner_id` (在矿工响应中) | `miner` |
| `multiplier` | `antiquity_multiplier` |
| `last_attestation` | `last_attest` |

---

## HTTPS 证书

公共主机名 `https://rustchain.org` 使用浏览器信任的证书。
对于本地开发或使用自签名证书的原始 IP 诊断：

```bash
# 选项 1: 跳过验证 (仅限开发)
curl -sk https://rustchain.org/health

# 选项 2: 信任证书
openssl s_client -connect rustchain.org:443 -showcerts < /dev/null 2>/dev/null | \
  openssl x509 -outform PEM > rustchain.pem
curl --cacert rustchain.pem https://rustchain.org/health
```

**Python:**
```python
# 生产环境 — 使用严格验证
requests.get(url)  # 默认: verify=True

# 仅限本地开发
requests.get(url, verify=False)
```

---

## 相关资源

- [RustChain GitHub](https://github.com/Scottcjn/Rustchain)
- [赏金计划](https://github.com/Scottcjn/rustchain-bounties)
- [RIP-0305 桥接规范](../rips/docs/RIP-0305-bridge-lock-ledger.md)
- [桥接集成指南](../contracts/erc20/docs/BRIDGE_INTEGRATION.md)
- [区块浏览器](https://rustchain.org/explorer)
- [BoTTube 桥接](https://bottube.ai/bridge)
