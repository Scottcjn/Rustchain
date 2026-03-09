# RustChain API Walkthrough

First steps for developers integrating with RustChain.

**Node:** `https://50.28.86.131`

---

## 1. Health Check

```bash
curl -sk https://50.28.86.131/health
```

**Response:**
```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 37901,
  "db_rw": true,
  "backup_age_hours": 8.17,
  "tip_age_slots": 0
}
```

---

## 2. Get Epoch Info

```bash
curl -sk https://50.28.86.131/epoch
```

**Response:**
```json
{
  "epoch": 96,
  "slot": 13914,
  "blocks_per_epoch": 144,
  "enrolled_miners": 21,
  "epoch_pot": 1.5,
  "total_supply_rtc": 8388608
}
```

**Field Explanation:**
| Field | Type | Description |
|-------|------|-------------|
| `epoch` | integer | Current epoch number |
| `slot` | integer | Current slot within epoch |
| `blocks_per_epoch` | integer | Blocks per epoch (144) |
| `enrolled_miners` | integer | Number of active miners |
| `epoch_pot` | float | RTC reward for this epoch |
| `total_supply_rtc` | integer | Total RTC supply |

---

## 3. Check Wallet Balancecurl -sk "https://50.

```bash
28.86.131/wallet/balance?miner_id=YOUR_WALLET_ID"
```

**Example:**
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=RTC7f91106cf192aecd213be7ca02c1a022d48bf34d"
```

**Response:**
```json
{
  "amount_i64": 0,
  "amount_rtc": 0.0,
  "miner_id": "RTC7f91106cf192aecd213be7ca02c1a022d48bf34d"
}
```

**Field Explanation:**
| Field | Type | Description |
|-------|------|-------------|
| `amount_i64` | integer | Balance in smallest unit (1 RTC = 1) |
| `amount_rtc` | float | Balance in RTC |
| `miner_id` | string | The wallet ID queried |

---

## 4. List Active Miners

```bash
curl -sk https://50.28.86.131/api/miners
```

**Response:**
```json
[
  {
    "miner_id": "RTC...",
    "last_attestation": 1234567890,
    "weight": 1.0
  },
  ...
]
```

---

## 5. Signed Transfer

The transfer endpoint requires a signed transaction.

### Endpoint

```
POST https://50.28.86.131/wallet/transfer/signed
```

### Request Body

```json
{
  "from_address": "RTCsender_address",
  "to_address": "RTCrecipient_address",
  "amount_rtc": 10.0,
  "nonce": 1234567890,
  "memo": "optional message",
  "public_key": "ed25519_public_key_hex",
  "signature": "ed25519_signature_hex"
}
```

### Field Explanation

| Field | Type | Description |
|-------|------|-------------|
| `from_address` | string | Sender's RTC wallet ID (starts with `RTC`) |
| `to_address` | string | Recipient's RTC wallet ID |
| `amount_rtc` | float | Amount in RTC |
| `nonce` | integer | Unix timestamp for replay protection |
| `memo` | string | Optional message (max 256 chars) |
| `public_key` | hex string | Ed25519 public key (64 hex chars) |
| `signature` | hex string | Ed25519 signature (128 hex chars) |

### How to Sign

The transfer payload must be signed with Ed25519. Here's how:

```python
import json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# Build transfer data
tx_data = {
    "from": "RTCsender_address",
    "to": "RTCrecipient_address", 
    "amount": 10.0,
    "memo": "hello",
    "nonce": 1234567890
}

# Sign with Ed25519
message = json.dumps(tx_data, sort_keys=True, separators=(",", ":")).encode()
private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("private_key_hex"))
signature = private_key.sign(message).hex()
public_key = private_key.public_key().public_key().public_bytes_raw().hex()

# Final payload
transfer = {
    "from_address": tx_data["from"],
    "to_address": tx_data["to"],
    "amount_rtc": tx_data["amount"],
    "nonce": tx_data["nonce"],
    "memo": tx_data["memo"],
    "public_key": public_key,
    "signature": signature
}
```

---

## Important Notes

### ⚠️ Wallet IDs vs External Addresses

**RustChain wallet IDs are NOT Ethereum/Solana/Base addresses!**

- ✅ Correct: `RTC7f91106cf192aecd213be7ca02c1a022d48bf34d`
- ❌ Wrong: `0x...` (Ethereum) or `...` (Solana)

### 🔐 Self-Signed Certificates

The node uses self-signed TLS certificates. Use `-k` flag or `verify=False`:

```bash
curl -k https://50.28.86.131/health
```

```python
requests.get(url, verify=False)
```

### 💰 Amount Units

- `amount_rtc`: Display units (1.0 = 1 RTC)
- `amount_i64`: Internal units (1 = 0.000001 RTC)

---

## Quick Test Commands

```bash
# Health check
curl -sk https://50.28.86.131/health | jq .

# Epoch info
curl -sk https://50.28.86.131/epoch | jq .

# Check balance
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET" | jq .

# List miners
curl -sk https://50.28.86.131/api/miners | jq '. | length'
```

---

## Reference

- **Node:** `https://50.28.86.131`
- **Explorer:** `https://50.28.86.131/explorer`

*References: Scottcjn/Rustchain#701, Scottcjn/rustchain-bounties#1494*
