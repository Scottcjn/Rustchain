# RustChain API Reference

Base URL: `https://rustchain.org`

All endpoints use HTTPS. Self-signed certificates require `-k` flag with curl.

---

## Health & Status

### `GET /health`

Check node status and version.

**Request:**
```bash
curl -sk https://rustchain.org/health | jq .
```

**Response:**
```json
{
  "backup_age_hours": 6.75,
  "db_rw": true,
  "ok": true,
  "tip_age_slots": 0,
  "uptime_s": 18728,
  "version": "2.2.1-rip200"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | Node healthy |
| `version` | string | Protocol version |
| `uptime_s` | integer | Seconds since node start |
| `db_rw` | boolean | Database writable |
| `backup_age_hours` | float | Hours since last backup |
| `tip_age_slots` | integer | Slots behind tip (0 = synced) |

---

## Epoch Information

### `GET /epoch`

Get current epoch details.

**Request:**
```bash
curl -sk https://rustchain.org/epoch | jq .
```

**Response:**
```json
{
  "blocks_per_epoch": 144,
  "enrolled_miners": 2,
  "epoch": 62,
  "epoch_pot": 1.5,
  "slot": 9010,
  "total_supply_rtc": 8388608
}
```

| Field | Type | Description |
|-------|------|-------------|
| `epoch` | integer | Current epoch number |
| `slot` | integer | Current slot within epoch |
| `blocks_per_epoch` | integer | Slots per epoch (144 = ~24h) |
| `epoch_pot` | float | RTC to distribute this epoch |
| `enrolled_miners` | integer | Miners eligible for rewards |
| `total_supply_rtc` | integer | Total RTC supply in circulation |

---

## Miners

### `GET /api/miners`

List all active/enrolled miners.

**Request:**
```bash
curl -sk https://rustchain.org/api/miners | jq .
```

**Response:**
```json
[
  {
    "antiquity_multiplier": 2.5,
    "device_arch": "G4",
    "device_family": "PowerPC",
    "entropy_score": 0.0,
    "hardware_type": "PowerPC G4 (Vintage)",
    "last_attest": 1770112912,
    "miner": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC"
  },
  {
    "antiquity_multiplier": 2.0,
    "device_arch": "G5",
    "device_family": "PowerPC",
    "entropy_score": 0.0,
    "hardware_type": "PowerPC G5 (Vintage)",
    "last_attest": 1770112865,
    "miner": "g5-selena-179"
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `miner` | string | Unique miner ID (wallet address) |
| `device_family` | string | CPU family (PowerPC, x86_64, etc.) |
| `device_arch` | string | Specific architecture (G4, G5, M2) |
| `hardware_type` | string | Human-readable hardware description |
| `antiquity_multiplier` | float | Reward multiplier (1.0-2.5x) |
| `entropy_score` | float | Hardware entropy quality |
| `last_attest` | integer | Unix timestamp of last attestation |

---

## Wallet

### `GET /wallet/balance`

Check RTC balance for a miner.

Canonical query parameter is `miner_id`. The endpoint also accepts `address`
as a compatibility alias for older callers.

**Request:**
```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC" | jq .
```

**Response:**
```json
{
  "amount_i64": 118357193,
  "amount_rtc": 118.357193,
  "miner_id": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `miner_id` | string | Wallet/miner identifier |
| `amount_rtc` | float | Balance in RTC (human readable) |
| `amount_i64` | integer | Balance in micro-RTC (6 decimals) |

### `GET /wallet/history`

Read recent transfer history for a wallet. This is a public, wallet-scoped view
over the pending transfer ledger and includes pending, confirmed, and voided
transfers. Returns an empty array for wallets with no history.

Canonical query parameter is `miner_id`. The endpoint also accepts `address`
as a compatibility alias for older callers.

**Request:**
```bash
curl -sk "https://rustchain.org/wallet/history?miner_id=eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC&limit=10" | jq .
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `miner_id` | string | Yes* | Wallet identifier (canonical) |
| `address` | string | Yes* | Backward-compatible alias for `miner_id` |
| `limit` | integer | No | Max records (1-200, default: 50) |

*Either `miner_id` or `address` is required.

**Response:**
```json
[
  {
    "tx_id": "6df5d4d25b6deef8f0b2e0fa726cecf1",
    "tx_hash": "6df5d4d25b6deef8f0b2e0fa726cecf1",
    "from_addr": "aliceRTC",
    "to_addr": "bobRTC",
    "amount": 1.25,
    "amount_i64": 1250000,
    "amount_rtc": 1.25,
    "timestamp": 1772848800,
    "created_at": 1772848800,
    "confirmed_at": null,
    "confirms_at": 1772935200,
    "status": "pending",
    "raw_status": "pending",
    "status_reason": null,
    "confirmations": 0,
    "direction": "sent",
    "counterparty": "bobRTC",
    "reason": "signed_transfer:payment",
    "memo": "payment"
  },
  {
    "tx_id": "abc123def456...",
    "tx_hash": "abc123def456...",
    "from_addr": "carolRTC",
    "to_addr": "aliceRTC",
    "amount": 5.0,
    "amount_i64": 5000000,
    "amount_rtc": 5.0,
    "timestamp": 1772762400,
    "created_at": 1772762400,
    "confirmed_at": 1772848800,
    "confirms_at": 1772848800,
    "status": "confirmed",
    "raw_status": "confirmed",
    "status_reason": null,
    "confirmations": 1,
    "direction": "received",
    "counterparty": "carolRTC",
    "reason": null,
    "memo": null
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `tx_id` | string | Transaction hash, or `pending_{id}` for pending |
| `tx_hash` | string | Same as `tx_id` (alias) |
| `from_addr` | string | Sender wallet address |
| `to_addr` | string | Recipient wallet address |
| `amount` | float | Amount in RTC (human-readable) |
| `amount_i64` | integer | Amount in micro-RTC (6 decimals) |
| `amount_rtc` | float | Same as `amount` (alias) |
| `timestamp` | integer | Transfer creation Unix timestamp |
| `created_at` | integer | Same as `timestamp` (alias) |
| `confirmed_at` | integer\|null | Confirmation timestamp (null if pending) |
| `confirms_at` | integer\|null | Scheduled confirmation time |
| `status` | string | `pending`, `confirmed`, or `failed` |
| `raw_status` | string | Raw DB status (`pending`, `confirmed`, `voided`) |
| `status_reason` | string\|null | Reason for failure/void |
| `confirmations` | integer | 1 if confirmed, 0 otherwise |
| `direction` | string | `sent` or `received` (relative to queried wallet) |
| `counterparty` | string | Other wallet in the transfer |
| `reason` | string\|null | Raw reason field from ledger |
| `memo` | string\|null | Extracted memo from `signed_transfer:` prefix |

**Notes:**
- Transactions ordered by `created_at DESC, id DESC` (newest first)
- `memo` extracted from `reason` when it starts with `signed_transfer:`
- Pending transfers use `pending_{id}` as `tx_id` until confirmed
- Empty array `[]` returned for wallets with no history
- Status normalized: `pending`→`pending`, `confirmed`→`confirmed`, others→`failed`

**Pagination:**
- Default limit: 50 records
- Clamped to range 1-200
- Invalid limit (non-integer) returns 400 error
```

| Field | Type | Description |
|-------|------|-------------|
| `tx_id` | string | Transaction hash, or a stable pending fallback ID |
| `from_addr` | string | Sender wallet address |
| `to_addr` | string | Recipient wallet address |
| `amount` | float | Amount transferred in RTC |
| `amount_i64` | integer | Amount in micro-RTC |
| `timestamp` | integer | Transfer creation timestamp |
| `status` | string | `pending`, `confirmed`, or `failed` |
| `direction` | string | `sent` or `received`, relative to the requested wallet |
| `counterparty` | string | The other wallet in the transfer |
| `memo` | string | Signed-transfer memo when present |
| `confirmed_at` | integer | Confirmation timestamp when confirmed |
| `confirms_at` | integer | Scheduled confirmation time for pending transfers |

### `POST /wallet/transfer/signed`

Transfer RTC to another wallet. Requires Ed25519 signature.

**Request:**
```bash
curl -sk -X POST https://rustchain.org/wallet/transfer/signed \
  -H "Content-Type: application/json" \
  -d '{
    "from_address": "RTCaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "to_address": "RTCbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "amount_rtc": 1.5,
    "nonce": 12345,
    "memo": "",
    "public_key": "ed25519_public_key_hex",
    "signature": "ed25519_signature_hex",
    "chain_id": "rustchain-mainnet-v2"
  }'
```

**Response (Success):**
```json
{
  "ok": true,
  "verified": true,
  "phase": "pending",
  "tx_hash": "abc123...",
  "amount_rtc": 1.5,
  "chain_id": "rustchain-mainnet-v2",
  "confirms_in_hours": 24
}
```

---

## Attestation

### `POST /attest/submit`

Submit hardware fingerprint for epoch enrollment.

**Request:**
```bash
curl -sk -X POST https://rustchain.org/attest/submit \
  -H "Content-Type: application/json" \
  -d '{
    "miner_id": "your_miner_id",
    "fingerprint": {
      "clock_skew": {...},
      "cache_timing": {...},
      "simd_identity": {...},
      "thermal_entropy": {...},
      "instruction_jitter": {...},
      "behavioral_heuristics": {...}
    },
    "signature": "base64_ed25519_signature"
  }'
```

**Response (Success):**
```json
{
  "success": true,
  "enrolled": true,
  "epoch": 62,
  "multiplier": 2.5,
  "next_settlement_slot": 9216
}
```

**Response (Rejected):**
```json
{
  "success": false,
  "error": "VM_DETECTED",
  "check_failed": "behavioral_heuristics",
  "detail": "Hypervisor signature detected in CPUID"
}
```

---

## Error Codes

| Code | Meaning |
|------|---------|
| `VM_DETECTED` | Attestation failed - virtual machine detected |
| `INVALID_SIGNATURE` | Ed25519 signature verification failed |
| `INSUFFICIENT_BALANCE` | Not enough RTC for transfer |
| `MINER_NOT_FOUND` | Unknown miner ID |
| `RATE_LIMITED` | Too many requests |

---

## Rate Limits

- Public endpoints: 100 requests/minute
- Attestation: 1 per 10 minutes per miner
- Transfers: 10 per minute per wallet

---

*Documentation generated for RustChain v2.2.1-rip200*


---

## Python Examples

All examples use the `requests` library. Install with `pip install requests`.

### Health Check

```python
import requests

resp = requests.get("https://rustchain.org/health", verify=False)
data = resp.json()
print(f"Node OK: {data['ok']}, Version: {data['version']}")
print(f"Uptime: {data['uptime_s']}s, Epoch: {data.get('epoch', 'N/A')}")
```

### Get Epoch Info

```python
import requests

resp = requests.get("https://rustchain.org/epoch", verify=False)
data = resp.json()
print(f"Epoch {data['epoch']}, Slot {data['slot']}/{data['blocks_per_epoch']}")
print(f"Pot: {data['epoch_pot']} RTC, Miners: {data['enrolled_miners']}")
```

### List Active Miners

```python
import requests

resp = requests.get("https://rustchain.org/api/miners", verify=False)
miners = resp.json()
for m in miners:
    print(f"{m['miner'][:20]}... | {m['device_arch']} | "
          f"mult={m['antiquity_multiplier']:.1f}x | "
          f"last={m['last_attest']}")
```

### Check Wallet Balance

```python
import requests

miner_id = "your_wallet_name"
resp = requests.get(
    f"https://rustchain.org/wallet/balance",
    params={"miner_id": miner_id},
    verify=False
)
data = resp.json()
print(f"Balance: {data['amount_rtc']} RTC ({data['amount_i64']} micro-RTC)")
```

### Get Wallet History

```python
import requests

miner_id = "your_wallet_name"
resp = requests.get(
    "https://rustchain.org/wallet/history",
    params={"miner_id": miner_id, "limit": 10},
    verify=False
)
for tx in resp.json().get("transfers", []):
    print(f"{tx['txid'][:12]}... | {tx['direction']} | {tx['amount_rtc']} RTC")
```

### Submit Attestation (Authenticated)

```python
import requests, json, time, hashlib, secp256k1

# Build attestation payload
payload = {
    "version": 1,
    "miner_id": "your_wallet_name",
    "arch": "x86_64",
    "entropy": hashlib.sha256(str(time.time()).encode()).hexdigest()[:32],
    "timestamp": int(time.time()),
}

# Sign with secp256k1 (requires `pip install secp256k1`)
priv = secp256k1.PrivateKey(bytes.fromhex("YOUR_PRIVATE_KEY_HEX"))
sig = priv.ecdsa_sign_recoverable(
    bytes.fromhex(hashlib.sha256(json.dumps(payload, separators=(',',':')).encode()).digest())
)
sig_serialized, _ = priv.ecdsa_recoverable_serialize(sig)

resp = requests.post(
    "https://rustchain.org/attest/submit",
    json={**payload, "signature": sig_serialized.hex()},
    verify=False,
    timeout=10,
)
print(resp.json())
```

### Error Handling

```python
import requests

try:
    resp = requests.get("https://rustchain.org/wallet/balance", 
                       params={"miner_id": "nonexistent"}, 
                       verify=False,
                       timeout=5)
    if resp.status_code == 200:
        print(resp.json())
    else:
        print(f"Error {resp.status_code}: {resp.text}")
except requests.exceptions.Timeout:
    print("Request timed out — node may be overloaded")
except requests.exceptions.ConnectionError:
    print("Connection failed — node may be offline")
```

### Self-Signed Certificate Note

The node uses a self-signed certificate. Use `verify=False` with requests, or add the cert to your trust store:

```python
import requests, ssl

# Option 1: Disable verification (less secure)
requests.get(url, verify=False)

# Option 2: Download cert and verify specifically
import httpx
client = httpx.Client(verify="/path/to/rustchain.crt")
```
