# RustChain API Walkthrough

This guide walks you through making your first API calls to RustChain.

## Base URL

```
https://50.28.86.131
```

> ⚠️ **Note**: The node uses a self-signed certificate. Use `-k` or `--insecure` with curl.

---

## 1. Check Node Health

The simplest way to verify the node is running:

```bash
curl -k "https://50.28.86.131/health"
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
curl -k "https://50.28.86.131/wallet/balance?miner_id=tomisnotcat"
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
curl -k "https://50.28.86.131/lottery/eligibility?miner_id=tomisnotcat"
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
curl -k "https://50.28.86.131/api/miners"
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
  "from": "sender_wallet_id",
  "to": "recipient_wallet_id", 
  "amount": 100,
  "nonce": "unique_value",
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

# Create transfer message
transfer_msg = {
    "from": "sender_wallet",
    "to": "recipient_wallet",
    "amount": 100,
    "nonce": "1234567890"
}

# Sign the message
signed = private_key.sign(json.dumps(transfer_msg).encode())
signature = signed.signature.hex()

# Add signature to payload
payload = {
    **transfer_msg,
    "signature": signature
}

# Send transfer
response = requests.post(
    "https://50.28.86.131/wallet/transfer/signed",
    json=payload,
    verify=False  # For self-signed cert
)
print(response.json())
```

### Important Notes

- **Wallet ID ≠ Blockchain Address**: RustChain uses simple string IDs (like `tomisnotcat`), not ETH/SOL addresses
- **Private Key**: Your Ed25519 key from `beacon identity new`
- **Nonce**: Must be unique per transfer (use timestamp or counter)

---

## Common API Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `{"ok":false,"reason":"admin_required"}` | Endpoint requires admin | Use appropriate endpoint |
| `404 Not Found` | Wrong URL | Check endpoint path |
| Connection refused | Node down | Check node status |

---

## SDK Alternative

Instead of raw API calls, use the Python SDK:

```bash
pip install rustchain-sdk
```

```python
from rustchain_sdk import Client

client = Client("https://50.28.86.131")

# Check balance
balance = client.get_balance("tomisnotcat")
print(balance)

# Get miners
miners = client.get_miners()
print(miners)
```

---

## Next Steps

- Explore the [RustChain GitHub](https://github.com/Scottcjn/Rustchain)
- Check [Bounties](https://github.com/Scottcjn/rustchain-bounties) for earning opportunities
- Join the community for help
