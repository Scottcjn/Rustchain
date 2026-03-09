# RustChain API Walkthrough

This guide provides the shortest technical path to interacting with the RustChain network via its REST API.

## 1. Primary Node
The primary public node for testing and interaction is:
`https://50.28.86.131`

*Note: Since this node uses an IP-based SSL certificate, you may need to disable hostname verification in your client (e.g., `curl -k`).*

## 2. First Successful Read Call
The simplest way to verify connectivity is the `/health` endpoint.

**Request:**
```bash
curl -sk https://50.28.86.131/health
```

**Expected Response:**
```json
{
  "ok": true,
  "version": "1.5.0",
  "uptime_s": 123456
}
```

## 3. Balance Lookup
To check the RTC balance of a specific miner/wallet ID.

**Request:**
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_ID"
```

**Expected Response:**
```json
{
  "balance": 100.5,
  "unlocked": 75.0,
  "locked": 25.5,
  "nonce": 5
}
```

## 4. Signed Transfer (POST /wallet/transfer/signed)
To perform a transfer, you must submit a signed JSON payload.

### Request Payload Format
```json
{
  "from_address": "RTC...",
  "to_address": "RTC...",
  "amount_rtc": 10.0,
  "nonce": 1710000000,
  "memo": "Payment for services",
  "public_key": "hex_encoded_public_key",
  "signature": "hex_encoded_ed25519_signature"
}
```

### Field Explanations
| Field | Type | Description |
|-------|------|-------------|
| `from_address` | String | The RTC wallet ID of the sender. |
| `to_address` | String | The RTC wallet ID of the recipient. |
| `amount_rtc` | Float | Amount of RTC to transfer. |
| `nonce` | Integer | Unique transaction identifier (usually timestamp). |
| `memo` | String | Optional message (max 64 chars). |
| `public_key` | Hex | Sender's Ed25519 public key. |
| `signature` | Hex | Ed25519 signature of the serialized transaction data. |

### Signing Flow (Python Example)
The message to sign is a JSON string of the transaction data with sorted keys and no extra whitespace:

```python
import json
import ed25519

tx_data = {
    "from": from_addr,
    "to": to_addr,
    "amount": amount_rtc,
    "memo": memo,
    "nonce": str(nonce),
}
# Canonical JSON serialization
message = json.dumps(tx_data, sort_keys=True, separators=(",", ":")).encode()

# Sign using private key
signature = priv_key.sign(message).hex()
```

## 5. Wallet IDs vs External Addresses
RustChain uses internal **Wallet IDs** (e.g., `whitebrendan`) for its on-chain operations. These are distinct from Ethereum, Solana, or Base addresses. Cross-chain interactions require using the bridge protocol.
