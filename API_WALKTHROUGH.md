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
  "from": "sender_wallet_id",
  "to": "recipient_wallet_id", 
  "amount": 10,
  "fee": 0.001,
  "signature": "hex_encoded_signature",
  "timestamp": 1234567890
}
```

### Field Explanation

| Field | Type | Description |
|-------|------|-------------|
| `from` | string | Sender's RustChain wallet ID |
| `to` | string | Recipient's RustChain wallet ID |
| `amount` | integer | Amount in RTC (smallest unit) |
| `fee` | float | Transaction fee |
| `signature` | hex string | Ed25519 signature of the transfer payload |
| `timestamp` | integer | Unix timestamp for replay protection |

### Important Notes

1. **Wallet IDs are NOT external addresses** - RustChain uses its own wallet system (e.g., `Ivan-houzhiiwen`), not Ethereum or Solana addresses.

2. **Self-signed certificates** - Use `curl -k` or `verify=False` in Python.

3. **Amount is in smallest unit** - 1 RTC = 1,000,000 smallest units.

---

## Example: Python

```python
import requests
import json

# Check balance
response = requests.get(
    "https://50.28.86.131/wallet/balance",
    params={"miner_id": "Ivan-houzhiwen"},
    verify=False
)
print(f"Balance: {response.json()['amount_rtc']} RTC")

# Transfer (requires signature)
transfer_data = {
    "from": "sender_wallet",
    "to": "recipient_wallet",
    "amount": 1000000,  # 1 RTC
    "fee": 1000,
    "signature": "...",
    "timestamp": 1234567890
}
response = requests.post(
    "https://50.28.86.131/wallet/transfer/signed",
    json=transfer_data,
    verify=False
)
print(response.json())
```

---

## Reference

- **Node:** `https://50.28.86.131`
- **Explorer:** `https://50.28.86.131/explorer`
- **Health:** `https://50.28.86.131/health`

*Ref: Scottcjn/Rustchain#701*
