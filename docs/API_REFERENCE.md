# RustChain API Reference

## 概述
RustChain 提供了一套标准的 RESTful API，用于与区块链网络进行安全、高效的交互。本参考文档详细列出了所有公共端点、请求格式、响应结构及身份验证机制。适用于节点监控、钱包开发、矿工管理及应用集成。

**基础地址 (Base URL)**:
- 公网环境: `https://rustchain.org`
- 内网/测试环境: `http://localhost:8099` (仅限 VPS 内部访问)

**通用约定**:
- 所有请求与响应均使用 `application/json` 格式。
- 节点默认使用自签名证书。使用 `curl` 时需添加 `-k` 或 `--insecure` 参数。
- 时间戳统一采用 Unix Timestamp (秒级)。
- 金额单位支持原始整数 (`amount_i64`) 与人类可读浮点数 (`amount_rtc`)。

---

## 认证机制 (Authentication)

RustChain 采用标准的 **Bearer Token** 认证方案保护敏感操作（如转账、查询私有交易记录等）。公共查询端点（如 `/health`, `/epoch`）无需认证。

### 获取 Token
通过 `POST /auth/token` 接口使用钱包凭证换取短期访问令牌（具体签发流程请参阅身份认证模块文档）。

### 请求头传递方式
```http
Authorization: Bearer <YOUR_ACCESS_TOKEN>
```
若 Token 无效、过期或缺失，网关将返回 `401 Unauthorized`。管理员级别操作需额外携带 `X-Admin-Key` 头部，此处不作展开。

---

## API 端点详解

### 1. 节点健康状态检查
检查 RustChain 节点运行状态、数据库读写能力及同步进度。

- **HTTP Method**: `GET`
- **URL Path**: `/health`
- **Request Headers**: 无
- **Query Parameters**: 无

**响应 JSON 结构**:
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `ok` | boolean | 节点整体健康状态 (`true` 表示正常) |
| `version` | string | 节点软件版本标识 |
| `uptime_s` | integer | 节点自启动以来的运行秒数 |
| `db_rw` | boolean | 数据库是否处于可读写状态 |
| `backup_age_hours` | float | 距离上一次完整备份的小时数 |
| `tip_age_slots` | integer | 当前区块落后最新 Slot 的数量 (0 表示已完全同步) |

**cURL 示例**:
```bash
curl -sk https://rustchain.org/health
```

**Python Requests 示例**:
```python
import requests

url = "https://rustchain.org/health"
response = requests.get(url, verify=False)
print(response.json())
```

---

### 2. 服务就绪探针
提供 Kubernetes 兼容的就绪性检查接口。

- **HTTP Method**: `GET`
- **URL Path**: `/ready`
- **Query Parameters**: 无

**响应 JSON 结构**:
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `ready` | boolean | 服务是否准备好接收外部流量 |

**cURL 示例**:
```bash
curl -sk https://rustchain.org/ready
```

**Python Requests 示例**:
```python
import requests
resp = requests.get("https://rustchain.org/ready", verify=False)
print(resp.json()["ready"])
```

---

### 3. 当前纪元 (Epoch) 信息
获取当前区块链纪元、Slot 进度及网络奖励池详情。

- **HTTP Method**: `GET`
- **URL Path**: `/epoch`
- **Query Parameters**: 无

**响应 JSON 结构**:
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `epoch` | integer | 当前纪元编号 |
| `slot` | integer | 当前纪元内的 Slot 序号 |
| `blocks_per_epoch` | integer | 每个纪元包含的 Slot 总数 (固定为 144) |
| `epoch_pot` | float | 本纪元可分配的 RTC 奖励总量 |
| `enrolled_miners` | integer | 已注册且具备挖矿资格的矿工数量 |
| `total_supply_rtc` | integer | 当前全网 RTC 流通总量 |

**cURL 示例**:
```bash
curl -sk https://rustchain.org/epoch
```

**Python Requests 示例**:
```python
import requests
data = requests.get("https://rustchain.org/epoch", verify=False).json()
print(f"Current Slot: {data['slot']} / {data['blocks_per_epoch']}")
```

---

### 4. 矿工列表查询
获取网络中所有已注册矿工的硬件配置与最近心跳时间。

- **HTTP Method**: `GET`
- **URL Path**: `/api/miners`
- **Query Parameters**: 支持可选过滤参数 `hardware_type` (字符串)

**响应 JSON 结构** (数组格式):
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `miner` | string | 矿工钱包 ID 或唯一标识符 |
| `device_arch` | string | CPU 架构 (如 G4, G5, x86_64, arm64) |
| `device_family` | string | CPU 所属家族 |
| `hardware_type` | string | 人类可读的硬件描述 |
| `antiquity_multiplier` | float | 历史硬件加权奖励系数 (1.0 ~ 2.5) |
| `entropy_score` | float | 硬件熵值评分 (越高代表随机性生成质量越好) |
| `last_attest` | integer | 最后一次证明(Attestation)的 Unix 时间戳 |

**cURL 示例**:
```bash
curl -sk https://rustchain.org/api/miners | jq '.[0]'
```

**Python Requests 示例**:
```python
import requests
miners = requests.get("https://rustchain.org/api/miners", verify=False).json()
for m in miners:
    print(f"{m['miner']}: {m['hardware_type']} (Last: {m['last_attest']})")
```

---

### 5. 钱包余额查询
查询指定矿工地址的 RTC 资产余额。

- **HTTP Method**: `GET`
- **URL Path**: `/wallet/balance`
- **Query Parameters**:
  | 参数名 | 必填 | 类型 | 说明 |
  |--------|------|------|------|
  | `miner_id` | 是 | string | 目标钱包标识符或地址 |

**响应 JSON 结构**:
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `amount_i64` | integer | 余额原始整数值 (最小单位) |
| `amount_rtc` | float | 人类可读的 RTC 数量 |
| `miner_id` | string | 查询的目标地址 |

**cURL 示例**:
```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=tomisnotcat"
```

**Python Requests 示例**:
```python
import requests

url = "https://rustchain.org/wallet/balance"
params = {"miner_id": "tomisnotcat"}
resp = requests.get(url, params=params, verify=False)
print(f"Balance: {resp.json()['amount_rtc']} RTC")
```

---

### 6. 挖矿抽签资格检查
校验指定矿工在当前 Slot 是否具备出块/抽奖资格。

- **HTTP Method**: `GET`
- **URL Path**: `/lottery/eligibility`
- **Query Parameters**:
  | 参数名 | 必填 | 类型 | 说明 |
  |--------|------|------|------|
  | `miner_id` | 是 | string | 矿工标识符 |

**响应 JSON 结构**:
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `eligible` | boolean | 是否具备当前轮次出块资格 |
| `reason` | string \| null | 若不具备资格的原因 (`"not_attested"`, `"not_staked"`, 等) |
| `rotation_size` | integer | 当前轮转池中的活跃矿工总数 |
| `slot` | integer | 查询的 Slot 编号 |
| `slot_producer` | string \| null | 若已选出，返回该 Slot 的预测生产者 |

**cURL 示例**:
```bash
curl -sk "https://rustchain.org/lottery/eligibility?miner_id=stepehenreed"
```

**Python Requests 示例**:
```python
import requests

url = "https://rustchain.org/lottery/eligibility"
resp = requests.get(url, params={"miner_id": "stepehenreed"}, verify=False).json()
if resp["eligible"]:
    print("✅ Miner is eligible for current slot.")
else:
    print(f"❌ Reason: {resp['reason']}")
```

---

### 7. 签名转账 (POST)
提交经过 Ed25519 签名的链上转账交易。

- **HTTP Method**: `POST`
- **URL Path**: `/wallet/transfer/signed`
- **Headers**: `Authorization: Bearer <TOKEN>`
- **Body 参数** (JSON):
  | 字段名 | 类型 | 必填 | 说明 |
  |--------|------|------|------|
  | `from_address` | string | ✅ | 发送方 RTC 地址 |
  | `to_address` | string | ✅ | 接收方 RTC 地址 |
  | `amount_rtc` | float | ✅ | 转账金额 |
  | `nonce` | string | ✅ | 防重放随机值 (建议 UUID 或递增整数) |
  | `chain_id` | string | ✅ | 网络标识 (`rustchain-mainnet-v2`) |
  | `public_key` | string | ✅ | 发送方 Ed25519 公钥 (Hex) |
  | `signature` | string | ✅ | 对交易 Payload 的签名结果 (Hex) |

**响应 JSON 结构**:
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `status` | string | 交易提交状态 (`accepted`, `queued`) |
| `tx_hash` | string | 交易唯一哈希 (用于后续查询) |
| `block_number` | integer | 预计/实际入块编号 |
| `network_fee_rtc` | float | 扣除的矿工手续费 |

**cURL 示例**:
```bash
curl -sk -X POST https://rustchain.org/wallet/transfer/signed \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6..." \
  -H "Content-Type: application/json" \
  -d '{
    "from_address": "RTC_sender_addr...",
    "to_address": "RTC_recipient_addr...",
    "amount_rtc": 50.5,
    "nonce": "uuid-v4-...",
    "chain_id": "rustchain-mainnet-v2",
    "public_key": "hex_pub_key...",
    "signature": "hex_sig..."
  }'
```

**Python Requests 示例**:
```python
import requests

url = "https://rustchain.org/wallet/transfer/signed"
headers = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6...",
    "Content-Type": "application/json"
}
payload = {
    "from_address": "RTC_sender",
    "to_address": "RTC_receiver",
    "amount_rtc": 100.0,
    "nonce": "7f8a9b0c-d1e2-f3a4-b5c6-7890abcdef12",
    "chain_id": "rustchain-mainnet-v2",
    "public_key": "ed25519_public_key_hex",
    "signature": "ed25519_signature_hex"
}
resp = requests.post(url, json=payload, headers=headers, verify=False)
print(resp.json())
```

---

### 8. 交易历史查询
分页获取指定钱包的入出账交易流水。

- **HTTP Method**: `GET`
- **URL Path**: `/wallet/history`
- **Headers**: `Authorization: Bearer <TOKEN>`
- **Query Parameters**:
  | 参数名 | 必填 | 类型 | 说明 |
  |--------|------|------|------|
  | `miner_id` | 是 | string | 目标钱包地址 |
  | `limit` | 否 | int | 每页返回条数 (默认 20, 最大 100) |
  | `offset` | 否 | int | 分页偏移量 |
  | `type` | 否 | string | 过滤类型: `inbound`, `outbound`, 或留空查全部 |

**响应 JSON 结构** (数组 + 分页元数据):
```json
{
  "data": [
    {
      "tx_hash": "abc123...",
      "block_height": 88210,
      "timestamp": 1773010500,
      "from": "miner_a",
      "to": "tomisnotcat",
      "amount_rtc": 5.2,
      "type": "inbound",
      "fee_rtc": 0.01,
      "status": "confirmed"
    }
  ],
  "pagination": { "total": 145, "limit": 20, "offset": 0 }
}
```

**cURL 示例**:
```bash
curl -sk "https://rustchain.org/wallet/history?miner_id=tomisnotcat&limit=10&offset=0" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Python Requests 示例**:
```python
import requests

url = "https://rustchain.org/wallet/history"
headers = {"Authorization": "Bearer YOUR_TOKEN"}
params = {"miner_id": "tomisnotcat", "limit": 10, "type": "outbound"}
resp = requests.get(url, headers=headers, params=params, verify=False).json()
for tx in resp["data"]:
    print(f"[{tx['tx_hash']}] -> {tx['amount_rtc']} RTC ({tx['status']})")
```

---

## 错误码参考表

RustChain API 遵循标准 HTTP 状态码，并结合业务错误码提供结构化错误响应。所有错误响应均包含以下字段：
```json
{
  "error": true,
  "code": 40103,
  "message": "Invalid or expired Bearer token.",
  "trace_id": "req_9a8b7c6d5e4f"
}
```

| HTTP 状态 | 业务错误码 (`code`) | 触发条件 | 解决建议 |
|-----------|-------------------|----------|----------|
| `200` | `0` | 请求成功 | 无 |
| `400` | `10001` | 请求体格式非法或缺失必填参数 | 检查 JSON 结构及参数类型 |
| `400` | `10002` | `nonce` 重复或已过期 | 使用新生成的唯一 Nonce 重试 |
| `400` | `10005` | 签名验证失败 (Ed25519 mismatch) | 核对公私钥配对及签名 Payload |
| `401` | `40101` | 缺少 `Authorization` 头部 | 补充 Bearer Token |
| `401` | `40103` | Token 无效或已过期 | 重新调用 `/auth/token` 获取新令牌 |
| `403` | `40302` | Token 权限不足 (如普通 Token 调用 Admin 接口) | 申请高权限凭证或使用 `X-Admin-Key` |
| `404` | `40401` | 矿工地址不存在或未注册 | 确认地址拼写或先执行注册 |
| `429` | `42900` | 触发全局速率限制 (Rate Limit) | 降低请求频率，检查 `Retry-After` 头部 |
| `500` | `50001` | 节点内部数据库异常或共识层冲突 | 稍后重试，若持续发生联系节点运维 |
| `503` | `50300` | 节点正在同步或维护 | 查看 `/health` 的 `tip_age_slots` 和 `ok` 字段 |

---

## 附录：最佳实践与安全建议

1. **证书处理**: 生产环境强烈建议配置反向代理 (Nginx/Caddy) 并使用 Let's Encrypt 等受信 CA 签发的证书，避免客户端忽略 SSL 验证带来的中间人攻击风险。
2. **Nonce 管理**: 转账接口依赖 `nonce` 防重放。客户端应实现本地 Nonce 计数器，并在收到 `10002` 错误时同步链上最新 Nonce。
3. **大数处理**: 链上金额底层使用 128-bit 整数存储。浮点数 (`amount_rtc`) 仅供展示，涉及计算或合约交互时务必使用 `amount_i64` 配合定点数库。
4. **重试机制**: 对 `429` 和 `5xx` 错误建议实现指数退避 (Exponential Backoff) 重试策略。网络分叉或 Slot 切换期间 `/health` 可能短暂返回非 `true`，属正常现象。