# RustChain Developer Quickstart: First API Calls

> **Purpose**: Get developers making successful RustChain API calls in under 5 minutes.  
> **Related**: Tracks `Scottcjn/Rustchain#701` | Bounty: `rustchain-bounties#1494`

---

## Base URL & Setup

```bash
NODE_URL="https://50.28.86.131"
```

> ⚠️ **Self-Signed Certificate**: The node uses a self-signed TLS certificate. Always use `-k` or `--insecure` with curl.

---

## 1. First Read Call: Health Check

Verify the node is running:

```bash
curl -k "$NODE_URL/health"
```

**Response:**
```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 3966,
  "backup_age_hours": 20.74,
  "db_rw": true,
  "tip_age_slots": 0
}
```

**Field Explanations:**

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | Node health status |
| `version` | string | Node software version |
| `uptime_s` | integer | Seconds since last restart |
| `backup_age_hours` | float | Hours since last database backup |
| `db_rw` | boolean | Database read/write capability |
| `tip_age_slots` | integer | Slots behind chain tip (0 = synced) |

---

## 2. Check Network Epoch

Get current epoch and network stats:

```bash
curl -k "$NODE_URL/epoch"
```

**Response:**
```json
{
  "epoch": 96,
  "slot": 13845,
  "blocks_per_epoch": 144,
  "enrolled_miners": 16,
  "epoch_pot": 1.5,
  "total_supply_rtc": 8388608
}
```

**Field Explanations:**

| Field | Type | Description |
|-------|------|-------------|
| `epoch` | integer | Current epoch number |
| `slot` | integer | Current slot within epoch |
| `blocks_per_epoch` | integer | Total slots per epoch |
| `enrolled_miners` | integer | Active miners in network |
| `epoch_pot` | float | Total RTC rewards for this epoch |
| `total_supply_rtc` | integer | Total RTC in circulation |

---

## 3. Balance Lookup

Query a wallet balance with its RustChain address:

```bash
curl -k "$NODE_URL/wallet/balance?miner_id=YOUR_RTC_ADDRESS"
```

A placeholder value also returns the response shape, which is useful for onboarding:

```bash
curl -k "$NODE_URL/wallet/balance?miner_id=YOUR_WALLET_ID"
```

**Tested response (2026-03-09):**
```json
{
  "amount_i64": 0,
  "amount_rtc": 0.0,
  "miner_id": "YOUR_WALLET_ID"
}
```

**Field Explanations:**

| Field | Type | Description |
|-------|------|-------------|
| `miner_id` | string | The wallet address that was queried |
| `amount_i64` | integer | Raw amount in micro-RTC (6 decimal places) |
| `amount_rtc` | float | Human-readable RTC amount |

> 💡 For signed transfers, the server validates `from_address` / `to_address` as `RTC...` addresses with a fixed length. Do not use an ETH / SOL / Base address here.

---

## 4. Signed Transfer: Complete Guide

### ⚠️ Critical: RustChain Addresses vs External Addresses

**RustChain transfer addresses are not Ethereum / Solana / Base addresses.**

The current server validation expects:
- `from_address` starts with `RTC`
- `to_address` starts with `RTC`
- both addresses are fixed-length RustChain addresses derived from an Ed25519 public key

| Chain | Address Format | Example |
|-------|---------------|---------|
| **RustChain** | `RTC` + 40 hex chars | `RTC0123456789abcdef0123456789abcdef01234567` |
| Ethereum | `0x` + 40 hex chars | `0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb` |
| Solana | Base58, 32-44 chars | `7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU` |
| Base | Same as Ethereum | `0x...` |

In the codebase, RustChain addresses are derived as:

```text
"RTC" + sha256(public_key_hex)[:40]
```

---

### Transfer Endpoint

```
POST /wallet/transfer/signed
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `from_address` | string | Sender RustChain address (`RTC...`) |
| `to_address` | string | Recipient RustChain address (`RTC...`) |
| `amount_rtc` | number | Amount to send in RTC |
| `memo` | string | Optional memo; if omitted, the server treats it as an empty string |
| `nonce` | integer or numeric string | Unique positive nonce; current examples use a timestamp |
| `public_key` | string | Sender Ed25519 public key as hex |
| `signature` | string | Ed25519 signature as hex |

---

### What Gets Signed

The server does **not** verify the signature over the outer request body directly.
It reconstructs this canonical JSON object and signs/verifies that exact byte sequence:

```json
{
  "amount": 1.0,
  "from": "RTC...",
  "memo": "Payment for services",
  "nonce": "1709942400",
  "to": "RTC..."
}
```

Canonicalization rules from the server implementation:
- keys are sorted alphabetically
- separators are compact: `(",", ":")`
- `nonce` is verified as a string inside the signed message, even if submitted as a number in the request body

Equivalent Python used by the server:

```python
message = json.dumps(tx_data, sort_keys=True, separators=(",", ":")).encode()
```

---

### Payload Structure Sent to the Endpoint

```json
{
  "from_address": "RTC0123456789abcdef0123456789abcdef01234567",
  "to_address": "RTC89abcdef0123456789abcdef0123456789abcdef",
  "amount_rtc": 1.0,
  "memo": "Payment for services",
  "nonce": 1709942400,
  "public_key": "a1b2c3d4e5f6...",
  "signature": "9f8e7d6c5b4a..."
}
```

---

### Step-by-Step: Create and Sign Transfer

#### Step 1: Generate an Ed25519 key pair and derive the RustChain address

```python
import hashlib
from nacl.signing import SigningKey

signing_key = SigningKey.generate()
verify_key = signing_key.verify_key

private_key_hex = signing_key.encode().hex()
public_key_hex = verify_key.encode().hex()
rustchain_address = "RTC" + hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:40]

print("Address:", rustchain_address)
print("Public key:", public_key_hex)
```

#### Step 2: Create the canonical signed message and submit the outer payload

```python
import hashlib
import json
import time
import requests
from nacl.signing import SigningKey

NODE_URL = "https://50.28.86.131"
PRIVATE_KEY_HEX = "your_private_key_hex_here"
TO_ADDRESS = "RTC89abcdef0123456789abcdef0123456789abcdef"
AMOUNT_RTC = 1.0
MEMO = "Test transfer"
NONCE = int(time.time())

signing_key = SigningKey(bytes.fromhex(PRIVATE_KEY_HEX))
public_key_hex = signing_key.verify_key.encode().hex()
from_address = "RTC" + hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:40]

# This exact structure is what the server reconstructs and verifies.
tx_data = {
    "from": from_address,
    "to": TO_ADDRESS,
    "amount": AMOUNT_RTC,
    "memo": MEMO,
    "nonce": str(NONCE),
}

message = json.dumps(tx_data, sort_keys=True, separators=(",", ":")).encode()
signature_hex = signing_key.sign(message).signature.hex()

payload = {
    "from_address": from_address,
    "to_address": TO_ADDRESS,
    "amount_rtc": AMOUNT_RTC,
    "memo": MEMO,
    "nonce": NONCE,
    "public_key": public_key_hex,
    "signature": signature_hex,
}

response = requests.post(
    f"{NODE_URL}/wallet/transfer/signed",
    json=payload,
    verify=False,
    timeout=15,
)

print(response.status_code)
print(response.json())
```

---

### Complete Bash Example (with openssl)

```bash
#!/bin/bash

NODE_URL="https://50.28.86.131"
FROM_ADDRESS="RTC1234567890123456789012345678901234567890"
TO_ADDRESS="RTC0987654321098765432109876543210987654321"
AMOUNT=1.0
MEMO="Test transfer"
NONCE=$(date +%s%3N)

# Generate Ed25519 key (one-time setup)
# openssl genpkey -algorithm Ed25519 -out private_key.pem
# openssl pkey -in private_key.pem -pubout -out public_key.pem

# Extract public key
PUBLIC_KEY=$(openssl pkey -in public_key.pem -pubout -outform DER 2>/dev/null | tail -c 32 | xxd -p -c 64)

# Create the canonical message the node verifies.
# The signed bytes use legacy keys {from,to,amount,memo,nonce}
# even though the outer request body uses {from_address,to_address,amount_rtc,...}.
MESSAGE=$(cat <<EOF
{"amount":${AMOUNT},"from":"${FROM_ADDRESS}","memo":"${MEMO}","nonce":"${NONCE}","to":"${TO_ADDRESS}"}
EOF
)

# Sign message
SIGNATURE=$(echo -n "$MESSAGE" | openssl pkeyutl -sign -inkey private_key.pem -rawin | xxd -p -c 128)

# Send transfer
curl -k -X POST "$NODE_URL/wallet/transfer/signed" \
  -H "Content-Type: application/json" \
  -d "{
    \"from_address\": \"${FROM_ADDRESS}\",
    \"to_address\": \"${TO_ADDRESS}\",
    \"amount_rtc\": ${AMOUNT},
    \"memo\": \"${MEMO}\",
    \"nonce\": \"${NONCE}\",
    \"public_key\": \"${PUBLIC_KEY}\",
    \"signature\": \"${SIGNATURE}\"
  }" | jq .
```

---

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `invalid_from_address_format` | `from_address` is not a valid `RTC...` address | Derive the address from the Ed25519 public key; do not use `0x...` or a nickname |
| `invalid_to_address_format` | Recipient is not a valid `RTC...` address | Use the recipient's RustChain address |
| `missing_required_fields` | Missing one of the required outer payload fields | Include `from_address`, `to_address`, `amount_rtc`, `nonce`, `signature`, and `public_key` |
| `Invalid signature` | The server-reconstructed canonical message does not match what you signed | Sign `{from,to,amount,memo,nonce}` with sorted keys and compact separators |
| `insufficient_balance` | Wallet has insufficient RTC | Check balance first via `/wallet/balance` |
| `REPLAY_DETECTED` | Nonce already used for that sender | Use a fresh nonce for every transfer |

---

## Testing Checklist

Before submitting your transfer:

- [ ] Verified node health with `/health`
- [ ] Checked sender balance with `/wallet/balance?miner_id=YOUR_ID`
- [ ] Generated valid Ed25519 key pair
- [ ] Public key is 64 hex characters
- [ ] Signature is 128 hex characters
- [ ] Nonce is unique (not reused)
- [ ] Wallet IDs are RustChain format (not ETH/SOL)
- [ ] Using `-k` flag for self-signed cert

---

## Next Steps

- **Explore more endpoints**: See full [API documentation](https://github.com/Scottcjn/Rustchain/blob/main/docs/)
- **Start mining**: [Console Mining Setup Guide](https://github.com/Scottcjn/Rustchain/blob/main/docs/CONSOLE_MINING_SETUP.md)
- **Earn RTC**: Browse [open bounties](https://github.com/Scottcjn/rustchain-bounties/issues)
- **Get help**: Join community discussions

---

## References

- Product Issue: `Scottcjn/Rustchain#701`
- Bounty Issue: `Scottcjn/rustchain-bounties#1494`
- Node: `https://50.28.86.131`
- Tested: 2026-03-09

---

**Last Updated**: 2026-03-09  
**Tested Against**: Node v2.2.1-rip200
