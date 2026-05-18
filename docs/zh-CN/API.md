# RustChain API 快速参考

本文是 `docs/API.md` 的中文快速入口，面向需要先跑通常用查询的矿工、集成者和文档读者。完整字段说明和更多端点请参考英文版 [API Reference](../API.md)。

Base URL: `https://rustchain.org`

所有示例使用 `curl -sk`，其中 `-k` 用于当前节点证书环境。

## 健康检查

检查节点是否在线、数据库是否可写、版本和同步状态：

```bash
curl -sk https://rustchain.org/health | jq .
```

| 字段 | 类型 | 含义 |
|------|------|------|
| `ok` | boolean | 节点是否健康 |
| `version` | string | 节点协议版本 |
| `uptime_s` | integer | 节点运行秒数 |
| `db_rw` | boolean | 数据库是否可读写 |

## Epoch 信息

查询当前 epoch、slot、奖励池和已登记矿工数量：

```bash
curl -sk https://rustchain.org/epoch | jq .
```

| 字段 | 类型 | 含义 |
|------|------|------|
| `epoch` | integer | 当前 epoch |
| `slot` | integer | 当前 slot |
| `blocks_per_epoch` | integer | 每个 epoch 的 slot 数 |
| `epoch_pot` | number | 当前 epoch 待分配 RTC |
| `enrolled_miners` | integer | 已登记矿工数量 |

## 活跃矿工

列出当前活跃或已登记矿工：

```bash
curl -sk https://rustchain.org/api/miners | jq .
```

| 字段 | 类型 | 含义 |
|------|------|------|
| `miner` | string | 矿工 ID 或钱包地址 |
| `device_family` | string | CPU 家族 |
| `device_arch` | string | 具体架构 |
| `hardware_type` | string | 可读硬件描述 |
| `antiquity_multiplier` | number | 古董证明奖励倍率 |
| `last_attest` | integer | 最近一次 attestation 时间戳 |

## 钱包余额

使用 `miner_id` 查询 RTC 余额：

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_OR_MINER_ID" | jq .
```

| 字段 | 类型 | 含义 |
|------|------|------|
| `miner_id` | string | 钱包或矿工标识 |
| `amount_rtc` | number | RTC 可读余额 |
| `amount_i64` | integer | micro-RTC 整数余额 |

## 钱包历史

查询钱包近期转账历史：

```bash
curl -sk "https://rustchain.org/wallet/history?miner_id=YOUR_WALLET_OR_MINER_ID&limit=10" | jq .
```

| 参数 | 必填 | 含义 |
|------|------|------|
| `miner_id` | 是* | 推荐的钱包或矿工标识参数 |
| `address` | 是* | 兼容旧客户端的别名 |
| `limit` | 否 | 最大返回数量，默认 50 |

`miner_id` 和 `address` 二选一即可。

## Explorer

浏览器查看交易、钱包和矿工：

```text
https://rustchain.org/explorer/
```

可以搜索钱包地址、交易哈希或矿工 ID。

## 安全边界

本文只覆盖公开只读查询和文档入口。不要在公开 issue、PR 或聊天中粘贴私钥、助记词、keystore、验证码或密码。钱包创建、提现、转账、跨链桥和交易所操作应由用户本人在可信环境中完成。
