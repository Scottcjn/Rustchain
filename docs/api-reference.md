# RustChain API Reference

## Overview

RustChain is a Proof-of-Antiquity blockchain that rewards real vintage hardware with higher mining multipliers. The REST API provides comprehensive endpoints for interacting with the network.

## Base URL

```
https://50.28.86.131
```

## Authentication

### Admin Key Authentication
For admin endpoints, include the header:
```
X-Admin-Key: <admin-key>
```

### Ed25519 Signature Verification
Some endpoints require Ed25519 signatures for transaction verification.

### SR25519 Key Registration
Hardware attestation uses sr25519 key pairs for registration.

---

## Endpoints

### Health & Status

#### GET /health
Returns node health status and chain information.

**Response:**
```json
{
  "status": "healthy",
  "block_height": 12345,
  "epoch": 42,
  "network_version": "2.2.1-rip200",
  "timestamp": 1707614000
}
```

### Epoch Management

#### GET /epoch
Get current epoch information.

**Response:**
```json
{
  "epoch": 42,
  "block_height": 12345,
  "miners_count": 9,
  "attestation_nodes": 3,
  "started_at": 1707600000,
  "ends_at": 1707686400
}
```

### Miner Registry

#### GET /api/miners
List all active miners with hardware details.

**Response:**
```json
{
  "miners": [
    {
      "id": "miner_001",
      "hardware": "PowerPC G5",
      "hashrate": 1500000,
      "status": "active",
      "joined_at": 1707500000
    }
  ]
}
```

#### POST /api/miners/register
Register a new miner.

**Request:**
```json
{
  "hardware_id": "g5_001",
  "public_key": "ed25519_pub_key",
  "timestamp": 1707614000
}
```

### Wallet Operations

#### GET /api/wallet/:address/balance
Get wallet balance.

**Parameters:**
- `address` (string): RTC wallet address

**Response:**
```json
{
  "address": "RTC-user-001",
  "balance": 1500.50,
  "pending": 100.00,
  "currency": "RTC"
}
```

#### POST /api/wallet/transfer
Transfer RTC between wallets.

**Request:**
```json
{
  "from": "RTC-sender",
  "to": "RTC-receiver",
  "amount": 100.00,
  "signature": "ed25519_signature"
}
```

### Withdrawal System

#### POST /api/withdrawals/register
Register a withdrawal address.

**Request:**
```json
{
  "address": "RTC-user-001",
  "withdrawal_method": "exchange",
  "destination": "binance_address"
}
```

#### POST /api/withdrawals/request
Request a withdrawal.

**Request:**
```json
{
  "address": "RTC-user-001",
  "amount": 50.00,
  "signature": "ed25519_signature"
}
```

#### GET /api/withdrawals/status/:request_id
Get withdrawal status.

**Response:**
```json
{
  "request_id": "wd_12345",
  "status": "pending",
  "amount": 50.00,
  "created_at": 1707614000,
  "processed_at": null
}
```

#### GET /api/withdrawals/history/:address
Get withdrawal history.

**Response:**
```json
{
  "address": "RTC-user-001",
  "withdrawals": [
    {
      "request_id": "wd_12345",
      "amount": 50.00,
      "status": "completed",
      "created_at": 1707614000,
      "processed_at": 1707700000
    }
  ]
}
```

### Hardware Attestation

#### POST /api/attestation/register
Register hardware with attestation keys.

**Request:**
```json
{
  "miner_id": "miner_001",
  "hardware_fingerprint": "ppc_g5_serial_123",
  "attestation_key": "sr25519_pub_key"
}
```

#### GET /api/attestation/verify/:miner_id
Verify hardware attestation.

**Response:**
```json
{
  "miner_id": "miner_001",
  "verified": true,
  "hardware_type": "PowerPC G5",
  "last_verified": 1707614000
}
```

### Rewards Distribution

#### GET /api/rewards/:address
Get pending rewards for an address.

**Response:**
```json
{
  "address": "RTC-user-001",
  "pending_rewards": 150.75,
  "claimed_rewards": 500.00,
  "total_earned": 650.75
}
```

#### POST /api/rewards/claim
Claim pending rewards.

**Request:**
```json
{
  "address": "RTC-user-001",
  "signature": "ed25519_signature"
}
```

### Transaction Management

#### GET /api/transactions/pending
Get pending transactions.

**Response:**
```json
{
  "pending": [
    {
      "tx_id": "tx_001",
      "from": "RTC-sender",
      "to": "RTC-receiver",
      "amount": 100.00,
      "status": "pending",
      "created_at": 1707614000
    }
  ]
}
```

### Governance

#### GET /api/governance/rotation
Get current governance rotation status.

**Response:**
```json
{
  "current_lead": "Scottcjn",
  "election_block": 12000,
  "voters": 12,
  "total_votes": 150000
}
```

### Monitoring

#### GET /metrics
Prometheus metrics endpoint.

Returns standard Node/Rust application metrics.

#### GET /api/stats
System statistics.

**Response:**
```json
{
  "uptime_seconds": 86400,
  "transactions_processed": 5000,
  "avg_block_time_ms": 12000,
  "cpu_percent": 15.5,
  "memory_mb": 256
}
```

---

## Error Codes

| Code | Status | Meaning |
|------|--------|---------|
| 200 | OK | Successful request |
| 400 | Bad Request | Invalid parameters |
| 401 | Unauthorized | Missing/invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |

---

## Rate Limiting

- **Default limit:** 100 requests per minute per IP
- **Burst limit:** 200 requests per 10 seconds
- **Headers:**
  - `X-RateLimit-Limit`: Maximum requests
  - `X-RateLimit-Remaining`: Requests remaining
  - `X-RateLimit-Reset`: Reset time (Unix timestamp)

---

## Common Workflows

### Get Miner Status and Rewards
```bash
# 1. Get miner info
curl -sk https://50.28.86.131/api/miners

# 2. Get pending rewards
curl -sk https://50.28.86.131/api/rewards/RTC-user-001

# 3. Claim rewards
curl -sk -X POST https://50.28.86.131/api/rewards/claim \
  -H "Content-Type: application/json" \
  -d '{
    "address": "RTC-user-001",
    "signature": "ed25519_sig..."
  }'
```

### Transfer RTC
```bash
curl -sk -X POST https://50.28.86.131/api/wallet/transfer \
  -H "Content-Type: application/json" \
  -d '{
    "from": "RTC-sender",
    "to": "RTC-receiver",
    "amount": 100.00,
    "signature": "ed25519_sig..."
  }'
```

### Request Withdrawal
```bash
# 1. Register withdrawal address
curl -sk -X POST https://50.28.86.131/api/withdrawals/register \
  -H "Content-Type: application/json" \
  -d '{
    "address": "RTC-user-001",
    "withdrawal_method": "exchange",
    "destination": "binance_123..."
  }'

# 2. Request withdrawal
curl -sk -X POST https://50.28.86.131/api/withdrawals/request \
  -H "Content-Type: application/json" \
  -d '{
    "address": "RTC-user-001",
    "amount": 50.00,
    "signature": "ed25519_sig..."
  }'

# 3. Check status
curl -sk https://50.28.86.131/api/withdrawals/status/wd_12345
```

---

## SDK Examples

### Python
```python
import requests

BASE_URL = "https://50.28.86.131"

# Get miner info
response = requests.get(f"{BASE_URL}/api/miners", verify=False)
miners = response.json()

# Check rewards
rewards = requests.get(
    f"{BASE_URL}/api/rewards/RTC-user-001",
    verify=False
).json()
print(f"Pending rewards: {rewards['pending_rewards']}")
```

### cURL
```bash
# Get health status
curl -sk https://50.28.86.131/health

# List miners
curl -sk https://50.28.86.131/api/miners

# Get rewards
curl -sk https://50.28.86.131/api/rewards/RTC-user-001
```

---

## Links

- **RustChain GitHub:** https://github.com/Scottcjn/Rustchain
- **Network Explorer:** https://50.28.86.131/explorer
- **Community:** https://discord.gg/VqVVS2CW9Q
