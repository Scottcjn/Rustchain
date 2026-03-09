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

Query any wallet balance:

```bash
curl -k "$NODE_URL/wallet/balance?miner_id=tomisnotcat"
```

**Response:**
```json
{
  "miner_id": "tomisnotcat",
  "amount_i64": 0,
  "amount_rtc": 0.0
}
```

**Field Explanations:**

| Field | Type | Description |
|-------|------|-------------|
| `miner_id` | string | The wallet ID queried |
| `amount_i64` | integer | Raw amount in smallest units (int64) |
| `amount_rtc` | float | Human-readable RTC amount |

> 💡 **Replace `tomisnotcat`** with your actual RustChain wallet ID.

---

## 4. Signed Transfer: Complete Guide

### ⚠️ Critical: RustChain Wallet IDs vs External Addresses

**RustChain wallet IDs are NOT Ethereum/Solana/Base addresses!**

| Chain | Address Format | Example |
|-------|---------------|---------|
| **RustChain** | Simple string ID | `tomisnotcat`, `miner001` |
| Ethereum | 0x + 40 hex chars | `0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb` |
| Solana | Base58, 32-44 chars | `7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU` |
| Base | Same as Ethereum | `0x...` |

**RustChain uses Ed25519 keys** with human-readable wallet IDs, not EVM-style addresses.

---

### Transfer Endpoint

```
POST /wallet/transfer/signed
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `from_address` | string | **Your RustChain wallet ID** (e.g., `tomisnotcat`) |
| `to_address` | string | **Recipient's RustChain wallet ID** |
| `amount_rtc` | number | Amount to send in RTC (e.g., `1.5`) |
| `memo` | string | Optional transfer note (max 256 chars) |
| `nonce` | string | Unique value per transfer (use timestamp or UUID) |
| `public_key` | string | Your Ed25519 public key (64 hex chars) |
| `signature` | string | Ed25519 signature of payload (128 hex chars) |

---

### Payload Structure

```json
{
  "from_address": "your_wallet_id",
  "to_address": "recipient_wallet_id",
  "amount_rtc": 1.0,
  "memo": "Payment for services",
  "nonce": "1709942400000",
  "public_key": "a1b2c3d4e5f6...",
  "signature": "9f8e7d6c5b4a..."
}
```

---

### Step-by-Step: Create a Signed Transfer

#### Step 1: Generate Ed25519 Key Pair

```bash
# Using Python (requires pynacl)
pip install pynacl
```

```python
import nacl.signing
import nacl.encoding

# Generate new key pair
signing_key = nacl.signing.SigningKey.generate()
verify_key = signing_key.verify_key

# Export keys (save these securely!)
private_key_hex = signing_key.encode().hex()
public_key_hex = verify_key.encode().hex()

print(f"Public Key: {public_key_hex}")
print(f"Private Key: {private_key_hex}")
```

#### Step 2: Create and Sign Transfer

```python
import requests
import json
import nacl.signing
import nacl.encoding
import time

# Configuration
NODE_URL = "https://50.28.86.131"
PRIVATE_KEY_HEX = "your_private_key_hex_here"  # From Step 1
FROM_WALLET = "your_wallet_id"
TO_WALLET = "recipient_wallet_id"
AMOUNT = 1.0
MEMO = "Test transfer"

# Load private key
private_key_bytes = bytes.fromhex(PRIVATE_KEY_HEX)
signing_key = nacl.signing.SigningKey(private_key_bytes)

# Create transfer message (fields to sign)
transfer_msg = {
    "from_address": FROM_WALLET,
    "to_address": TO_WALLET,
    "amount_rtc": AMOUNT,
    "memo": MEMO,
    "nonce": str(int(time.time() * 1000))  # Millisecond timestamp
}

# Sign the message
message_bytes = json.dumps(transfer_msg, sort_keys=True).encode('utf-8')
signed = signing_key.sign(message_bytes)
signature_hex = signed.signature.hex()

# Get public key
public_key_hex = signing_key.verify_key.encode().hex()

# Build full payload
payload = {
    **transfer_msg,
    "public_key": public_key_hex,
    "signature": signature_hex
}

# Send transfer
response = requests.post(
    f"{NODE_URL}/wallet/transfer/signed",
    json=payload,
    verify=False  # Self-signed cert
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
```

---

### Complete Bash Example (with openssl)

```bash
#!/bin/bash

NODE_URL="https://50.28.86.131"
FROM_WALLET="your_wallet_id"
TO_WALLET="recipient_wallet_id"
AMOUNT=1.0
MEMO="Test transfer"
NONCE=$(date +%s%3N)

# Generate Ed25519 key (one-time setup)
# openssl genpkey -algorithm Ed25519 -out private_key.pem
# openssl pkey -in private_key.pem -pubout -out public_key.pem

# Extract public key
PUBLIC_KEY=$(openssl pkey -in public_key.pem -pubout -outform DER 2>/dev/null | tail -c 32 | xxd -p -c 64)

# Create message to sign
MESSAGE=$(cat <<EOF
{"amount_rtc":${AMOUNT},"from_address":"${FROM_WALLET}","memo":"${MEMO}","nonce":"${NONCE}","to_address":"${TO_WALLET}"}
EOF
)

# Sign message
SIGNATURE=$(echo -n "$MESSAGE" | openssl pkeyutl -sign -inkey private_key.pem -rawin | xxd -p -c 128)

# Send transfer
curl -k -X POST "$NODE_URL/wallet/transfer/signed" \
  -H "Content-Type: application/json" \
  -d "{
    \"from_address\": \"${FROM_WALLET}\",
    \"to_address\": \"${TO_WALLET}\",
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
| `invalid_from_address_format` | Wallet ID format incorrect | Use simple string ID, not 0x address |
| `missing_required_fields` | Missing `from_address`, `to_address`, `amount_rtc`, or `public_key` | Include all 7 required fields |
| `invalid_signature` | Signature doesn't match payload | Ensure JSON is sorted keys, UTF-8 encoded |
| `insufficient_balance` | Wallet has insufficient RTC | Check balance first via `/wallet/balance` |
| `duplicate_nonce` | Nonce already used | Use unique nonce (timestamp + random) |

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
