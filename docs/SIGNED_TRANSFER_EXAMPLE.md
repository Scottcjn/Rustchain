# Signed Transfer Example — Bounty #1494

Complete guide for creating and submitting signed transfers on RustChain.

---

## Overview

RustChain uses **Ed25519** digital signatures for transfer authorization. This document provides:

1. **Quick cURL example** (for testing)
2. **Python script** (for production use)
3. **Signature specification** (for custom implementations)

---

## Quick Start: cURL Example

### Step 1: Generate Test Keys (Python one-liner)

```bash
python3 -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import hashlib, json

priv = Ed25519PrivateKey.generate()
pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
addr = 'RTC' + hashlib.sha256(pub).hexdigest()[:40]

print(f'Address: {addr}')
print(f'Public Key (hex): {pub.hex()}')
print(f'Private Key (hex): {priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw).hex()}')
"
```

### Step 2: Construct and Sign Payload

```python
#!/usr/bin/env python3
"""Quick signed transfer with cURL-compatible output."""

import hashlib
import json
import time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

# Configuration
PRIVATE_KEY_HEX = "YOUR_PRIVATE_KEY_HEX"  # Replace with actual key
RECIPIENT = "RTC..."  # Replace with recipient address
AMOUNT = 1.0

# Load private key
priv_bytes = bytes.fromhex(PRIVATE_KEY_HEX)
priv = Ed25519PrivateKey.from_private_bytes(priv_bytes)
pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
from_address = "RTC" + hashlib.sha256(pub).hexdigest()[:40]

# Construct payload
nonce = int(time.time() * 1000)
payload = {
    "from_address": from_address,
    "to_address": RECIPIENT,
    "amount_rtc": AMOUNT,
    "nonce": nonce,
    "memo": "Bounty #1494 test"
}

# Sign (canonical JSON with sorted keys)
message = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
signature = priv.sign(message)

# Output cURL command
print(f"Public Key: {pub.hex()}")
print(f"Signature: {signature.hex()}")
print(f"\ncURL command:")
print(f"""
curl -sk -X POST https://rustchain.org/wallet/transfer/signed \\
  -H "Content-Type: application/json" \\
  -d '{{
    \"from_address\": \"{from_address}\",
    \"to_address\": \"{RECIPIENT}\",
    \"amount_rtc\": {AMOUNT},
    \"nonce\": {nonce},
    \"signature\": \"{signature.hex()}\",
    \"public_key\": \"{pub.hex()}\",
    \"memo\": \"Bounty #1494 test\"
  }}'
""")
```

---

## Full Python Example

See `examples/signed_transfer_example.py` for the complete script.

### Installation

```bash
pip install cryptography requests mnemonic
```

### Usage

```bash
# Generate new wallet
python3 examples/signed_transfer_example.py --generate

# Check balance
python3 examples/signed_transfer_example.py --mnemonic "word1 word2 ..." --balance-only

# Send transfer (dry run)
python3 examples/signed_transfer_example.py --generate --to RTCabc... --amount 1.0 --dry-run

# Send transfer (actual)
python3 examples/signed_transfer_example.py --generate --to RTCabc... --amount 1.0
```

---

## API Specification

### Endpoint

```
POST /wallet/transfer/signed
```

### Request Body

```json
{
  "from_address": "RTC<40 hex chars>",
  "to_address": "RTC<40 hex chars>",
  "amount_rtc": 1.5,
  "nonce": 1740783600000,
  "signature": "<128 hex chars>",
  "public_key": "<64 hex chars>",
  "memo": "optional memo"
}
```

### Field Details

| Field | Type | Description |
|-------|------|-------------|
| `from_address` | string | Sender's RTC address (RTC + 40 hex) |
| `to_address` | string | Recipient's RTC address |
| `amount_rtc` | float | Amount in RTC (smallest unit) |
| `nonce` | integer | Millisecond timestamp for replay protection |
| `signature` | hex string | Ed25519 signature (64 bytes = 128 hex chars) |
| `public_key` | hex string | Ed25519 public key (32 bytes = 64 hex chars) |
| `memo` | string | Optional memo (max 256 chars) |

### Signature Algorithm

1. **Construct payload** (without `signature` and `public_key` fields):
   ```json
   {
     "from_address": "...",
     "to_address": "...",
     "amount_rtc": 1.5,
     "nonce": 1234567890000,
     "memo": "..."
   }
   ```

2. **Canonicalize JSON**:
   - Sort keys alphabetically
   - No spaces/whitespace
   - Use `separators=(',', ':')` in Python

3. **Sign**:
   ```python
   message = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
   signature = private_key.sign(message)
   ```

4. **Encode** signature as hex string.

### Response

**Success (200 OK):**
```json
{
  "ok": true,
  "tx_hash": "abc123...",
  "replay_protected": true
}
```

**Error (400 Bad Request):**
```json
{
  "ok": false,
  "error": "Insufficient balance",
  "code": "INSUFFICIENT_BALANCE"
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INSUFFICIENT_BALANCE` | 400 | Sender has insufficient funds |
| `REPLAY_DETECTED` | 400 | Nonce already used |
| `INVALID_SIGNATURE` | 400 | Signature verification failed |
| `INVALID_ADDRESS` | 400 | Malformed wallet address |
| `INVALID_AMOUNT` | 400 | Amount must be positive |

---

## Replay Protection

The `nonce` field prevents replay attacks:

- **Must be unique** per transaction from each address
- **Recommended**: Use millisecond timestamp (`Date.now()` in JS, `time.time() * 1000` in Python)
- **Server behavior**: Rejects duplicate nonces with `REPLAY_DETECTED` error

### Nonce Collision Handling

If you accidentally reuse a nonce:

1. Wait for the previous transaction to be processed
2. Use a new nonce (higher timestamp)
3. The nonce is only consumed on **successful** transactions

---

## Testing Checklist

- [ ] Node health check returns `ok: true`
- [ ] Balance query returns valid response
- [ ] Signature is exactly 128 hex characters
- [ ] Public key is exactly 64 hex characters
- [ ] Address starts with `RTC` and is 43 characters total
- [ ] Nonce is unique (not reused)
- [ ] Amount is positive number
- [ ] SSL verification disabled (`-k` flag or `verify=False`)

---

## Common Issues

### "Invalid signature"

**Cause:** Message was not canonicalized correctly.

**Fix:** Ensure JSON is serialized with sorted keys and no spaces:
```python
json.dumps(payload, sort_keys=True, separators=(',', ':'))
```

### "Nonce already used"

**Cause:** Reusing a nonce from a previous transaction.

**Fix:** Use a new timestamp-based nonce.

### "SSL certificate verify failed"

**Cause:** Node uses self-signed certificate.

**Fix:** Use `-k` flag with curl or `verify=False` in Python.

### "Insufficient balance"

**Cause:** Wallet doesn't have enough RTC.

**Fix:** Fund the wallet first via faucet or transfer.

---

## Security Notes

⚠️ **Never share your private key or seed phrase!**

- Store seed phrases offline (paper, hardware wallet)
- Never commit keys to version control
- Use environment variables for sensitive data
- Consider using a hardware wallet for large amounts

---

## Reference

- **Ed25519 Spec:** https://ed25519.cr.yp.to/
- **BIP39 Mnemonic:** https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki
- **RustChain API:** `docs/api-reference.md`

---

*Last Updated: March 2026 | Bounty #1494*
