# RustChain API Walkthrough

First steps for developers integrating with RustChain.

---

## Quick API Test

### 1. Health Check

```bash
curl -sk https://50.28.86.131/health
```

**Response:**
```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 200000
}
```

### 2. Get Epoch Info

```bash
curl -sk https://50.28.86.131/epoch
```

**Response:**
```json
{
  "epoch": 95,
  "slot": 12345,
  "height": 67890
}
```

### 3. Check Balance

```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=Ivan-houzhiwen"
```

**Response:**
```json
{
  "amount_i64": 155000000,
  "amount_rtc": 155.0,
  "miner_id": "Ivan-houzhiwen"
}
```

---

## Signed Transfer

The transfer endpoint requires a signed transaction.

### Endpoint

```
POST /wallet/transfer/signed
```

### Request Body

```json
{
  "from_address": "RTCaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "to_address": "RTCbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "amount_rtc": 1.5,
  "nonce": 12345,
  "memo": "",
  "public_key": "ed25519_public_key_hex",
  "signature": "ed25519_signature_hex",
  "chain_id": "rustchain-mainnet-v2"
}
```

### Field Explanation

| Field | Type | Description |
|-------|------|-------------|
| `from_address` | string | Sender's `RTC...` address |
| `to_address` | string | Recipient's `RTC...` address |
| `amount_rtc` | number | Amount to transfer in RTC |
| `nonce` | integer | Unique nonce for replay protection |
| `memo` | string | Optional memo included in the signed payload |
| `public_key` | hex string | Sender Ed25519 public key |
| `signature` | hex string | Ed25519 signature over the canonical transfer payload |
| `chain_id` | string | Chain identifier, usually `rustchain-mainnet-v2` |

### Important Notes

1. **Use RustChain addresses** - Signed transfers use `RTC...` wallet addresses, not miner IDs like `Ivan-houzhiwen` and not Ethereum or Solana addresses.

2. **TLS certificates** - RustChain nodes use self-signed certificates. For production use, place the node's certificate at `~/.rustchain/node_cert.pem` and the `requests` library will automatically use it (default `verify=True`). For local testing with a self-signed certificate that is not pinned, you may temporarily set `verify=False` but be aware of MITM risks. The recommended pattern is to use the shared `tls_config` module from the RustChain codebase: `from node.tls_config import get_tls_session; session = get_tls_session()`.

3. **Amount is human-readable RTC** - `amount_rtc` is the RTC amount, not the micro-RTC integer balance field.

---

## Example: Python

```python
import requests
import json

# Check balance
response = requests.get(
    "https://50.28.86.131/wallet/balance",
    params={"miner_id": "Ivan-houzhiwen"},
)
print(f"Balance: {response.json()['amount_rtc']} RTC")

# Transfer (requires signature)
transfer_data = {
    "from_address": "RTCaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "to_address": "RTCbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "amount_rtc": 1.0,
    "nonce": 12345,
    "memo": "",
    "public_key": "ed25519_public_key_hex",
    "signature": "ed25519_signature_hex",
    "chain_id": "rustchain-mainnet-v2",
}
response = requests.post(
    "https://50.28.86.131/wallet/transfer/signed",
    json=transfer_data,
)
print(response.json())
```

See `docs/API.md` for the full canonical signing rules.

---

## Reference

- **Node base URL:** `https://50.28.86.131`
- **Explorer:** `https://50.28.86.131/explorer`
- **Health:** `https://50.28.86.131/health`

*Ref: Scottcjn/Rustchain#701*
