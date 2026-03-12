# RustChain 多签钱包指南

> **奖励：** 3 RTC  
> **难度：** 标准  
> **作者：** 牛 2  
> **日期：** 2026-03-12

---

## 📋 目录

1. [什么是多签钱包](#什么是多签钱包)
2. [多签钱包应用场景](#多签钱包应用场景)
3. [技术架构](#技术架构)
4. [设置多签钱包](#设置多签钱包)
5. [使用多签钱包](#使用多签钱包)
6. [安全最佳实践](#安全最佳实践)
7. [故障排除](#故障排除)
8. [参考资源](#参考资源)

---

## 什么是多签钱包

多签钱包（Multi-Signature Wallet）是一种需要多个私钥授权才能执行交易的加密货币钱包。在 RustChain 网络中，多签钱包通过 Ed25519 签名机制实现，提供比单签钱包更高的安全性。

### 核心概念

| 术语 | 说明 |
|------|------|
| **M-of-N 多签** | N 个签名者中需要 M 个签名才能执行交易 |
| **签名者 (Signer)** | 拥有多签钱包访问权限的私钥持有者 |
| **提案 (Proposal)** | 待签名的交易请求 |
| **阈值 (Threshold)** | 执行交易所需的最小签名数 |

### 多签 vs 单签

| 特性 | 单签钱包 | 多签钱包 |
|------|----------|----------|
| 私钥数量 | 1 个 | N 个 (2-10 推荐) |
| 签名要求 | 1/1 | M/N (如 2/3, 3/5) |
| 安全性 | 单点故障 | 分布式安全 |
| 适用场景 | 个人日常使用 | 团队资金、大额存储 |

---

## 多签钱包应用场景

### 🏢 企业资金管理
- **3/5 多签**：公司财务团队 5 人，任意 3 人同意即可动用资金
- **防止单点故障**：避免一人掌控全部资金

### 👨‍👩‍👧 家庭遗产规划
- **2/3 多签**：夫妻双方 + 律师，任意 2 人可访问
- **遗产继承**：一方意外，另一方仍可管理资产

### 🤝 合伙投资项目
- **2/2 多签**：两个合伙人，必须双方同意
- **资金托管**：防止单方挪用资金

### 🛡️ 个人资产保护
- **2/3 多签**：自己 2 个设备 + 信任的第三方
- **防盗增强**：即使一个私钥泄露，资金仍安全

---

## 技术架构

### RustChain 多签实现原理

```
┌─────────────────────────────────────────────────────────────┐
│                    RustChain 多签架构                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  签名者 A ──┐                                               │
│  (私钥 A)   │                                               │
│             ├──→ Ed25519 签名 ──┐                           │
│  签名者 B ──┤                   │                           │
│  (私钥 B)   │                   ├──→ 聚合签名 ──→ 交易执行  │
│             ├──→ Ed25519 签名 ──┤                           │
│  签名者 C ──┤                   │                           │
│  (私钥 C)   │                   │                           │
│             └───────────────────┘                           │
│                                                             │
│  配置：2/3 多签 (任意 2 个签名即可执行)                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 多签交易流程

```
1. 创建交易提案
   ↓
2. 提案广播给所有签名者
   ↓
3. 签名者验证并签名
   ↓
4. 收集足够签名 (达到 M 阈值)
   ↓
5. 提交到 RustChain 网络
   ↓
6. 网络验证签名有效性
   ↓
7. 交易执行
```

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/multisig/create` | POST | 创建多签钱包配置 |
| `/api/multisig/propose` | POST | 创建交易提案 |
| `/api/multisig/sign` | POST | 对提案签名 |
| `/api/multisig/execute` | POST | 执行已签名的交易 |
| `/api/multisig/status` | GET | 查询多签钱包状态 |

---

## 设置多签钱包

### 前置要求

- ✅ RustChain 钱包地址（至少 M 个）
- ✅ 安全的通信渠道（用于协调签名）
- ✅ 理解 Ed25519 签名机制
- ✅ 备份所有私钥

### 步骤 1：规划多签配置

确定你的 M-of-N 配置：

| 场景 | 推荐配置 | 说明 |
|------|----------|------|
| 夫妻共管 | 2/2 | 双方必须同意 |
| 小团队 | 2/3 | 允许一人缺席 |
| 公司财务 | 3/5 | 多数决策，防止勾结 |
| 个人备份 | 2/3 | 自己 2 设备 + 信任方 |

### 步骤 2：生成签名者密钥

每个签名者生成自己的 RustChain 钱包：

```bash
# 签名者 A
clawrtc wallet create --name signer-a
# 输出：RTC1A2B3C4D5E6F7G8H9I0J...

# 签名者 B
clawrtc wallet create --name signer-b
# 输出：RTC2B3C4D5E6F7G8H9I0J1K...

# 签名者 C
clawrtc wallet create --name signer-c
# 输出：RTC3C4D5E6F7G8H9I0J1K2L...
```

### 步骤 3：创建多签钱包配置

```bash
# 创建 2/3 多签钱包
clawrtc multisig create \
  --threshold 2 \
  --signers RTC1A2B3C4D5E6F7G8H9I0J...,RTC2B3C4D5E6F7G8H9I0J1K...,RTC3C4D5E6F7G8H9I0J1K2L... \
  --name "family-multisig"
```

**响应示例：**
```json
{
  "multisig_address": "RTCms7X8Y9Z0A1B2C3D4E5F6G...",
  "threshold": 2,
  "signers": [
    "RTC1A2B3C4D5E6F7G8H9I0J...",
    "RTC2B3C4D5E6F7G8H9I0J1K...",
    "RTC3C4D5E6F7G8H9I0J1K2L..."
  ],
  "created_at": "2026-03-12T10:30:00Z"
}
```

### 步骤 4：验证配置

```bash
# 查询多签钱包详情
curl -sk "https://rustchain.org/api/multisig/status?address=RTCms7X8Y9Z0A1B2C3D4E5F6G..."
```

**响应示例：**
```json
{
  "address": "RTCms7X8Y9Z0A1B2C3D4E5F6G...",
  "threshold": 2,
  "total_signers": 3,
  "balance": 0.0,
  "pending_proposals": 0
}
```

### 步骤 5：资金存入

向多签钱包地址转账：

```bash
# 从个人钱包转入多签钱包
clawrtc wallet transfer \
  --from signer-a \
  --to RTCms7X8Y9Z0A1B2C3D4E5F6G... \
  --amount 100 \
  --memo "Initial multisig funding"
```

---

## 使用多签钱包

### 发起交易提案

任何签名者都可以发起提案：

```bash
# 签名者 A 发起转账提案
clawrtc multisig propose \
  --multisig RTCms7X8Y9Z0A1B2C3D4E5F6G... \
  --to RTC9Z8Y7X6W5V4U3T2S1R0Q... \
  --amount 50 \
  --memo "Payment for services" \
  --proposer signer-a
```

**响应示例：**
```json
{
  "proposal_id": "prop_abc123def456",
  "multisig_address": "RTCms7X8Y9Z0A1B2C3D4E5F6G...",
  "transaction": {
    "to": "RTC9Z8Y7X6W5V4U3T2S1R0Q...",
    "amount": 50,
    "memo": "Payment for services"
  },
  "proposer": "RTC1A2B3C4D5E6F7G8H9I0J...",
  "signatures_collected": 1,
  "threshold": 2,
  "status": "pending",
  "created_at": "2026-03-12T11:00:00Z"
}
```

### 签名提案

其他签名者收到提案后进行签名：

```bash
# 签名者 B 签名提案
clawrtc multisig sign \
  --proposal prop_abc123def456 \
  --signer signer-b
```

**响应示例：**
```json
{
  "proposal_id": "prop_abc123def456",
  "signer": "RTC2B3C4D5E6F7G8H9I0J1K...",
  "signature": "ed25519_sig_xyz789...",
  "signatures_collected": 2,
  "threshold": 2,
  "status": "ready_to_execute"
}
```

### 执行交易

当收集到足够签名后，任何签名者都可以执行：

```bash
# 执行已签名的提案
clawrtc multisig execute \
  --proposal prop_abc123def456
```

**响应示例：**
```json
{
  "proposal_id": "prop_abc123def456",
  "transaction_hash": "tx_9876543210abcdef",
  "status": "executed",
  "executed_at": "2026-03-12T11:15:00Z",
  "block_height": 123456
}
```

### 查询提案状态

```bash
# 查询提案详情
curl -sk "https://rustchain.org/api/multisig/proposal/prop_abc123def456"
```

**响应示例：**
```json
{
  "proposal_id": "prop_abc123def456",
  "multisig_address": "RTCms7X8Y9Z0A1B2C3D4E5F6G...",
  "transaction": {
    "to": "RTC9Z8Y7X6W5V4U3T2S1R0Q...",
    "amount": 50,
    "memo": "Payment for services"
  },
  "proposer": "RTC1A2B3C4D5E6F7G8H9I0J...",
  "signers": [
    {
      "address": "RTC1A2B3C4D5E6F7G8H9I0J...",
      "signed": true,
      "signed_at": "2026-03-12T11:00:00Z"
    },
    {
      "address": "RTC2B3C4D5E6F7G8H9I0J1K...",
      "signed": true,
      "signed_at": "2026-03-12T11:10:00Z"
    },
    {
      "address": "RTC3C4D5E6F7G8H9I0J1K2L...",
      "signed": false
    }
  ],
  "signatures_collected": 2,
  "threshold": 2,
  "status": "executed",
  "executed_at": "2026-03-12T11:15:00Z",
  "transaction_hash": "tx_9876543210abcdef"
}
```

### 撤销提案

提案执行前，提案者可以撤销：

```bash
# 撤销提案
clawrtc multisig cancel \
  --proposal prop_abc123def456 \
  --proposer signer-a
```

---

## 安全最佳实践

### 🔐 私钥管理

#### ✅ 应该做的

1. **离线存储私钥**
   - 使用硬件钱包（Ledger, Trezor）
   - 纸钱包备份（防火防水保险箱）
   - 加密的 USB 驱动器（多处存放）

2. **分散存储**
   - 不同地理位置存放备份
   - 不同签名者独立保管
   - 避免单一故障点

3. **定期轮换**
   - 每 6-12 个月检查备份完整性
   - 怀疑泄露时立即更换
   - 更新多签配置

#### ❌ 不应该做的

1. **不要**将私钥存储在云端
2. **不要**通过明文传输私钥
3. **不要**在公共电脑输入私钥
4. **不要**截图保存私钥

### 🛡️ 通信安全

#### 安全协调渠道

| 渠道 | 安全性 | 推荐场景 |
|------|--------|----------|
| Signal | ⭐⭐⭐⭐⭐ | 日常协调 |
| Session | ⭐⭐⭐⭐⭐ | 匿名通信 |
| 面对面 | ⭐⭐⭐⭐⭐ | 重大决策 |
| PGP 加密邮件 | ⭐⭐⭐⭐ | 正式记录 |
| Telegram | ⭐⭐⭐ | 一般讨论 |
| 微信/WhatsApp | ⭐⭐ | 不推荐 |

#### 提案验证流程

```
1. 收到提案通知
   ↓
2. 通过独立渠道确认（电话/视频）
   ↓
3. 验证提案详情（金额、收款方、用途）
   ↓
4. 检查多签地址是否正确
   ↓
5. 确认无误后签名
```

### 🔍 交易验证清单

签名前必须验证：

- [ ] 多签钱包地址正确
- [ ] 收款地址经过二次确认
- [ ] 转账金额无误
- [ ] 交易用途明确
- [ ] 提案者身份已验证
- [ ] 网络费用合理
- [ ] 没有可疑的附加条件

### 📋 审计与监控

#### 定期检查

```bash
# 每周检查多签钱包余额
curl -sk "https://rustchain.org/wallet/balance?miner_id=RTCms7X8Y9Z0A1B2C3D4E5F6G..."

# 每月检查待处理提案
curl -sk "https://rustchain.org/api/multisig/pending?address=RTCms7X8Y9Z0A1B2C3D4E5F6G..."

# 每季度审查交易历史
curl -sk "https://rustchain.org/api/multisig/history?address=RTCms7X8Y9Z0A1B2C3D4E5F6G..."
```

#### 告警设置

建议设置以下告警：

| 事件 | 通知方式 | 响应时间 |
|------|----------|----------|
| 新提案创建 | 即时通知 | 24 小时内处理 |
| 大额转账 (>100 RTC) | 电话 + 消息 | 立即确认 |
| 未知签名者尝试 | 即时告警 | 立即调查 |
| 提案过期 | 提前 24 小时提醒 | 决定是否延期 |

### 🚨 应急响应

#### 私钥泄露

1. **立即通知**其他签名者
2. **冻结**多签钱包（如有此功能）
3. **创建新多签**配置
4. **转移资金**到新多签钱包
5. **撤销**泄露签名者权限

#### 签名者失联

1. **等待**预设的超时期限（如 7 天）
2. **启动**备用签名者流程
3. **更新**多签配置
4. **记录**变更原因

---

## 故障排除

### 常见问题

#### 问题 1：提案无法执行

**症状：** 收集到足够签名但执行失败

**可能原因：**
- 签名验证失败
- 余额不足
- 提案已过期

**解决方案：**
```bash
# 检查提案状态
curl -sk "https://rustchain.org/api/multisig/proposal/prop_abc123def456"

# 检查多签钱包余额
curl -sk "https://rustchain.org/wallet/balance?miner_id=RTCms7X8Y9Z0A1B2C3D4E5F6G..."

# 重新签名（如签名过期）
clawrtc multisig sign --proposal prop_abc123def456 --signer signer-b --force
```

#### 问题 2：签名者无法访问提案

**症状：** 签名者收不到提案通知

**可能原因：**
- 通知配置错误
- 网络问题
- 地址不匹配

**解决方案：**
```bash
# 手动查询待签名提案
curl -sk "https://rustchain.org/api/multisig/pending-signer?address=RTC2B3C4D5E6F7G8H9I0J1K..."

# 验证签名者地址是否在多签配置中
curl -sk "https://rustchain.org/api/multisig/status?address=RTCms7X8Y9Z0A1B2C3D4E5F6G..."
```

#### 问题 3：交易执行后未确认

**症状：** 交易已提交但长时间未确认

**可能原因：**
- 网络拥堵
- 交易费用过低
- 节点同步问题

**解决方案：**
```bash
# 查询交易状态
curl -sk "https://rustchain.org/explorer/tx/tx_9876543210abcdef"

# 检查网络状态
curl -sk "https://rustchain.org/health"

# 联系节点运营商（如超过 30 分钟未确认）
```

### 错误代码参考

| 错误代码 | 说明 | 解决方案 |
|----------|------|----------|
| `ERR_MULTISIG_001` | 签名数量不足 | 等待更多签名者签名 |
| `ERR_MULTISIG_002` | 签名验证失败 | 重新生成签名 |
| `ERR_MULTISIG_003` | 提案已过期 | 创建新提案 |
| `ERR_MULTISIG_004` | 余额不足 | 充值多签钱包 |
| `ERR_MULTISIG_005` | 签名者不在配置中 | 检查多签配置 |
| `ERR_MULTISIG_006` | 重复签名 | 忽略，已签名 |
| `ERR_MULTISIG_007` | 提案已执行 | 无需再次执行 |

---

## 参考资源

### 官方文档

- [RustChain 白皮书](https://github.com/Scottcjn/Rustchain/blob/main/docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)
- [协议规范](https://github.com/Scottcjn/Rustchain/blob/main/docs/PROTOCOL.md)
- [API 参考](https://github.com/Scottcjn/Rustchain/blob/main/docs/API.md)
- [钱包用户指南](https://github.com/Scottcjn/Rustchain/blob/main/docs/WALLET_USER_GUIDE.md)
- [wRTC 快速入门](https://github.com/Scottcjn/Rustchain/blob/main/docs/wrtc.md)

### 工具与库

- **clawrtc CLI**: `pip install clawrtc`
- **RustChain 区块浏览器**: https://rustchain.org/explorer
- **BoTTube 桥接**: https://bottube.ai/bridge

### 社区支持

- **GitHub Issues**: https://github.com/Scottcjn/Rustchain/issues
- **Discord**: https://discord.gg/VqVVS2CW9Q
- **开发者论坛**: https://github.com/Scottcjn/Rustchain/discussions

### 延伸阅读

- [Ed25519 签名算法详解](https://ed25519.cr.yp.to/)
- [比特币多签实现](https://en.bitcoin.it/wiki/Multisignature)
- [以太坊 Gnosis Safe](https://gnosis-safe.io/)
- [加密货币安全最佳实践](https://github.com/bitcoinbook/bitcoinbook)

---

## 附录：命令行速查表

```bash
# === 创建多签钱包 ===
clawrtc multisig create \
  --threshold 2 \
  --signers RTC1...,RTC2...,RTC3... \
  --name "my-multisig"

# === 查询多签状态 ===
curl -sk "https://rustchain.org/api/multisig/status?address=RTCms..."

# === 发起提案 ===
clawrtc multisig propose \
  --multisig RTCms... \
  --to RTC9Z8Y... \
  --amount 50 \
  --memo "Payment" \
  --proposer signer-a

# === 签名提案 ===
clawrtc multisig sign \
  --proposal prop_abc123 \
  --signer signer-b

# === 执行提案 ===
clawrtc multisig execute \
  --proposal prop_abc123

# === 撤销提案 ===
clawrtc multisig cancel \
  --proposal prop_abc123 \
  --proposer signer-a

# === 查询提案状态 ===
curl -sk "https://rustchain.org/api/multisig/proposal/prop_abc123"

# === 查询待处理提案 ===
curl -sk "https://rustchain.org/api/multisig/pending?address=RTCms..."

# === 查询交易历史 ===
curl -sk "https://rustchain.org/api/multisig/history?address=RTCms..."
```

---

## 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| 1.0.0 | 2026-03-12 | 初始版本发布 |

---

**免责声明：** 本指南仅供参考，不构成投资建议。使用多签钱包前，请确保充分理解相关风险。RustChain 多签功能可能随协议升级而变化，请以官方文档为准。

**许可证：** MIT License
