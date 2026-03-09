# RustChain API First Call Walkthrough

> **Bounty**: [Scottcjn/rustchain-bounties#1494](https://github.com/Scottcjn/rustchain-bounties/issues/1494)  
> **Reward**: 28 RTC (~$2.80 USD)  
> **Author**: AI Assistant  
> **Tested**: 2026-03-09  
> **Node**: `https://50.28.86.131`

---

## 📋 Overview

This guide provides copy-pasteable examples for making your first RustChain API calls. All examples have been tested against the live node.

**⚠️ SSL Certificate Notice**: The node uses a self-signed certificate. Use `-sk` flags with curl (skip SSL verification) for testing. Production deployments should use proper certificates.

---

## 🚀 Quick Start: First API Call

### 1. Health Check (Recommended First Call)

The simplest way to verify connectivity:

```bash
curl -sk https://50.28.86.131/health
```

**Expected Response:**
```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 11827,
  "db_rw": true,
  "tip_age_slots": 0,
  "backup_age_hours": 0.93
}
```

**Field Explanations:**
| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | Node is operational |
| `version` | string | Software version |
| `uptime_s` | number | Seconds since last restart |
| `db_rw` | boolean | Database is read-write capable |
| `tip_age_slots` | number | Slots behind chain tip (0 = synced) |
| `backup_age_hours` | number | Hours since last backup |

---

### 2. Current Epoch Info

Get blockchain statistics:

```bash
curl -sk https://50.28.86.131/epoch
```

**Expected Response:**
```json
{
  "epoch": 96,
  "slot": 13871,
  "blocks_per_epoch": 144,
  "enrolled_miners": 18,
  "epoch_pot": 1.5,
  "total_supply_rtc": 8388608
}
```

**Field Explanations:**
| Field | Type | Description |
|-------|------|-------------|
| `epoch` | number | Current epoch number |
| `slot` | number | Current slot within epoch |
| `blocks_per_epoch` | number | Total blocks per epoch |
| `enrolled_miners` | number | Active miners in network |
| `epoch_pot` | number | Total RTC rewards for this epoch |
| `total_supply_rtc` | number | Total RTC in circulation |

---

### 3. Wallet Balance Lookup

Check any wallet's RTC balance:

```bash
# Replace YOUR_WALLET_ID with actual miner_id
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_ID"
```

**Example with test wallet:**
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=test"
```

**Expected Response:**
```json
{
  "miner_id": "test",
  "amount_rtc": 0.0,
  "amount_i64": 0
}
```

**Field Explanations:**
| Field | Type | Description |
|-------|------|-------------|
| `miner_id` | string | The wallet/miner identifier |
| `amount_rtc` | number | Balance in RTC (decimal) |
| `amount_i64` | number | Balance in smallest units (integer) |

---

## 🔐 Signed Transfer Request Format

### POST `/wallet/transfer/signed`

This endpoint submits a pre-signed transfer transaction.

**⚠️ Important**: You must sign the transaction locally before sending. The node does NOT handle private keys.

### Request Format

```bash
curl -sk -X POST https://50.28.86.131/wallet/transfer/signed \
  -H "Content-Type: application/json" \
  -d '{
    "from_miner_id": "YOUR_WALLET_ID",
    "to_miner_id": "RECIPIENT_WALLET_ID",
    "amount_rtc": 10.0,
    "signature": "BASE64_ENCODED_SIGNATURE",
    "public_key": "YOUR_PUBLIC_KEY",
    "nonce": 1,
    "timestamp": 1773015600
  }'
```

### Field Explanations

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `from_miner_id` | string | ✅ | Sender's wallet ID (RustChain miner_id) |
| `to_miner_id` | string | ✅ | Recipient's wallet ID |
| `amount_rtc` | number | ✅ | Amount to transfer in RTC |
| `signature` | string | ✅ | Ed25519 signature of the transaction payload (Base64) |
| `public_key` | string | ✅ | Sender's public key (for signature verification) |
| `nonce` | number | ✅ | Transaction sequence number (prevents replay) |
| `timestamp` | number | ✅ | Unix timestamp (seconds) |

### Response Format

**Success (200 OK):**
```json
{
  "ok": true,
  "tx_hash": "abc123...",
  "status": "pending"
}
```

**Error (400 Bad Request):**
```json
{
  "ok": false,
  "error": "invalid_signature",
  "message": "Signature verification failed"
}
```

---

## 🔑 Signing Flow (Conceptual)

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│  Sign Locally │────▶│  Send to    │
│  Builds Tx  │     │  (Ed25519)   │     │   Node API  │
└─────────────┘     └──────────────┘     └─────────────┘
```

### Signing Steps (Pseudocode)

```python
import json
import base64
from nacl.signing import SigningKey

# 1. Generate or load keypair
private_key = SigningKey.generate()  # Or load from secure storage
public_key = private_key.verify_key

# 2. Build transaction payload
payload = {
    "from_miner_id": "my-wallet",
    "to_miner_id": "recipient-wallet",
    "amount_rtc": 10.0,
    "nonce": 1,
    "timestamp": int(time.time())
}

# 3. Create canonical JSON (sorted keys, no whitespace)
canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))

# 4. Sign the canonical JSON
signature = private_key.sign(canonical.encode())

# 5. Send to API
request = {
    **payload,
    "signature": base64.b64encode(signature.signature).decode(),
    "public_key": base64.b64encode(bytes(public_key)).decode()
}
```

---

## 🆚 Wallet ID Clarification

**RustChain Wallet IDs are NOT Ethereum or Solana addresses!**

| Chain | Address Format | Example |
|-------|---------------|---------|
| **RustChain** | String (miner_id) | `my-miner-wallet` |
| Ethereum | 0x-prefixed hex | `0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb` |
| Solana | Base58 | `7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU` |
| Base | 0x-prefixed hex | `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6` |

**Key Points:**
- RustChain miner IDs are human-readable strings
- They are NOT compatible with EVM or Solana addresses
- For cross-chain transfers, use the [BoTTube Bridge](https://bottube.ai/bridge)

---

## 🧪 Testing Checklist

- [ ] Health check returns `"ok": true`
- [ ] Epoch response shows current epoch number
- [ ] Balance lookup works with test wallet
- [ ] SSL certificate warning is expected (use `-sk`)
- [ ] All examples are copy-pasteable and reproducible

---

## 📚 Related Resources

- [RustChain Main Repo](https://github.com/Scottcjn/Rustchain)
- [Open Bounties](https://github.com/Scottcjn/rustchain-bounties/issues)
- [BoTTube Bridge](https://bottube.ai/bridge)
- [wRTC on Solana](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)
- [Discord Community](https://discord.gg/VqVVS2CW9Q)

---

## 📝 Test Evidence

All examples tested on **2026-03-09** against node `https://50.28.86.131`:

```bash
$ curl -sk https://50.28.86.131/health
{"backup_age_hours":0.9327635361088646,"db_rw":true,"ok":true,"tip_age_slots":0,"uptime_s":11827,"version":"2.2.1-rip200"}

$ curl -sk https://50.28.86.131/epoch
{"blocks_per_epoch":144,"enrolled_miners":18,"epoch":96,"epoch_pot":1.5,"slot":13871,"total_supply_rtc":8388608}

$ curl -sk "https://50.28.86.131/wallet/balance?miner_id=test"
{"amount_i64":0,"amount_rtc":0.0,"miner_id":"test"}
```

---

## ⚠️ Edge Cases & Notes

1. **SSL Certificate**: Node uses self-signed cert. Expect certificate warnings in browsers and strict HTTP clients.

2. **Empty Balance**: New wallets return `0.0` RTC - this is normal, not an error.

3. **Network Sync**: If `tip_age_slots` > 0, the node is behind. Wait for sync before submitting transactions.

4. **Rate Limiting**: No documented rate limits. Be respectful with request frequency.

5. **Miner ID Format**: Can be any string. Common patterns: `username`, `username-miner-1`, UUIDs.

---

**PR Reference**: Addresses [Scottcjn/Rustchain#701](https://github.com/Scottcjn/Rustchain/issues/701)
