# RustChain API Walkthrough

This guide walks you through making your first API calls to RustChain.

## Base URL

`https://rustchain.org`

> :warning: **Note**: The node uses a self-signed certificate. Use `-k` or `--insecure` with curl.

> :bulb: **Tip**: The examples below use `jq` for JSON formatting. If you don't have `jq` installed, simply remove `| jq .` from any command — the JSON response will still be returned.

---

## 1. Check Node Health

The simplest way to verify the node is running:

```bash
curl -k "https://rustchain.org/health" | jq .
```

**Response:**
```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 223,
  "backup_age_hours": 19.7,
  "db_rw": true,
  "tip_age_slots": 0
}
```

---

## 2. Check Wallet Balance

Query any wallet balance using the `miner_id` parameter:

```bash
curl -k "https://rustchain.org/wallet/balance?miner_id=tomisnotcat" | jq .
```

**Response:**
```json
{
  "amount_i64": 0,
  "amount_rtc": 0.0,
  "miner_id": "tomisnotcat"
}
```

### Understanding the Response

| Field | Type | Description |
|-------|------|-------------|
| `amount_i64` | integer | Raw amount (in smallest units) |
| `amount_rtc` | float | Human-readable RTC amount |
| `miner_id` | string | The wallet ID queried |

---

## 3. Check Mining Eligibility

If you're mining, check your eligibility status:

```bash
curl -k "https://rustchain.org/lottery/eligibility?miner_id=tomisnotcat" | jq .
```

**Response (not eligible):**
```json
{
  "eligible": false,
  "reason": "not_attested",
  "rotation_size": 27,
  "slot": 13839,
  "slot_producer": null
}
```

**Response (eligible):**
```json
{
  "eligible": true,
  "reason": null,
  "rotation_size": 27,
  "slot": 13840,
  "slot_producer": "miner_name"
}
```

---

## 4. List Active Miners

```bash
curl -k "https://rustchain.org/api/miners" | jq .
```

**Response (truncated):**
```json
[
  {
    "miner": "stepehenreed",
    "hardware_type": "PowerPC G4",
    "antiquity_multiplier": 2.5,
    "device_arch": "powerpc_g4",
    "last_attest": 1773010433
  },
  {
    "miner": "nox-ventures",
    "hardware_type": "x86-64 (Modern)",
    "antiquity_multiplier": 1.0,
    "device_arch": "modern",
    "last_attest": 1773010407
  }
]
```

---

## 5. Signed Transfer (Advanced)

To send RTC from one wallet to another, you need to create a signed transfer.

### Understanding Signed Transfers

RustChain uses Ed25519 signatures for transfers. You need:

1. **Your private key** (from `beacon identity new`)
2. **The transfer payload**
3. **Sign the payload with your key**

### Transfer Endpoint

```
POST /wallet/transfer/signed
```

### Transfer Payload Structure

```json
{
  "from_address": "RTC_sender_address",
  "to_address": "RTC_recipient_address",
  "amount_rtc": 100,
  "nonce": "unique_value",
  "chain_id": "rustchain-mainnet-v2",
  "public_key": "sender_ed25519_public_key_hex",
  "signature": "ed25519_signature_hex"
}
```

### Example (Python)

```python
import requests
import json
import nacl.signing
import nacl.encoding

# Load your private key
with open("/path/to/your/agent.key", "rb") as f:
    private_key = nacl.signing.SigningKey(f.read())

# Derive RTC address from public key
import hashlib
public_key_hex = private_key.verify_key.encode(encoder=nacl.encoding.HexEncoder)
address = "RTC_" + hashlib.sha256(public_key_hex).hexdigest()[:40]

# Create transfer payload
payload = {
    "from_address": address,
    "to_address": "RTC_recipient_address",
    "amount_rtc": 100,
    "nonce": "unique_value",
    "chain_id": "rustchain-mainnet-v2",
    "public_key": public_key_hex.decode(),
}

# Sign the payload
signed = private_key.sign(json.dumps(payload).encode())
payload["signature"] = signed.signature.hex()

# Submit transfer
resp = requests.post(
    "https://rustchain.org/wallet/transfer/signed",
    json=payload,
    verify=False  # self-signed cert
)
print(resp.json())
```
