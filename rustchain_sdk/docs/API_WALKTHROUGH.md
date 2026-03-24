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
public_key_hex = private_key.verify_key.encode().hex()
from_address = "RTC" + hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:40]

# Create canonical message to sign (uses from/to/amount, not from_address/to_address/amount_rtc)
transfer_msg = {
    "from": from_address,
    "to": "RTC_recipient_address",
    "amount": 100,
    "nonce": "1234567890",
    "memo": "",
    "chain_id": "rustchain-mainnet-v2"
}

# Sign the canonical message
message = json.dumps(transfer_msg, sort_keys=True, separators=(",", ":")).encode()
signed = private_key.sign(message)
signature_hex = signed.signature.hex()

# Build outer payload (uses from_address/to_address/amount_rtc)
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

# Send transfer
response = requests.post(
    "https://50.28.86.131/wallet/transfer/signed",
    json=payload,
    verify=False  # For self-signed cert
)
print(response.json())
```

### Important Notes

- **RustChain Addresses**: Signed transfers require `RTC...` addresses (43 chars: `RTC` + 40 hex), not simple wallet IDs or ETH/SOL addresses
- **Private Key**: Your Ed25519 key from `beacon identity new`
- **Nonce**: Must be unique per transfer (use timestamp or counter)
- **Public Key**: Required in outer payload; must match the `from_address`
- **Chain ID**: Optional for backward compatibility, but recommended. If supplied, it is verified and included in the signed message.

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
