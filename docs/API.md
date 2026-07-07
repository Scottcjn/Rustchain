# RustChain API Reference

Base URL: `https://rustchain.org`

All public `rustchain.org` endpoints use HTTPS with a browser-trusted certificate.
Use strict TLS verification for production calls.

---

## Health & Status

### `GET /health`

Check node status and version.

**Request:**
```bash
curl -fsS https://rustchain.org/health | jq .
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
curl -fsS https://rustchain.org/epoch | jq .
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
curl -fsS https://rustchain.org/api/miners | jq .
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
curl -fsS "https://rustchain.org/wallet/balance?miner_id=eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC" | jq .
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

Read recent transaction history for a wallet. This is a public, wallet-scoped
view that merges the immutable ``ledger``, the ``epoch_rewards`` payout table,
and the ``pending_ledger`` 2-phase-commit log into a single time-sorted
response.

Canonical query parameter is ``miner_id``. The endpoint also accepts
``address`` as a compatibility alias for older callers.

**Unified response envelope (authoritative since #908 / #997):**

```json
{
  "ok": true,
  "miner_id": "aliceRTC",
  "transactions": [
    {
      "type": "transfer_in",
      "amount": 5.0,
      "epoch": 200,
      "timestamp": 1772848800,
      "tx_hash": "6df5d4d25b6deef8f0b2e0fa726cecf1",
      "from": "aliceRTC"
    },
    {
      "type": "transfer_out",
      "amount": 1.25,
      "epoch": 201,
      "timestamp": 1772849000,
      "tx_hash": "abc123def456...",
      "to": "bobRTC",
      "status": "pending"
    },
    {
      "type": "reward",
      "amount": 0.5,
      "epoch": 201,
      "timestamp": 1772850000,
      "tx_hash": null
    },
    {
      "type": "ledger",
      "amount": 0.1,
      "epoch": 202,
      "timestamp": 1772851000,
      "tx_hash": null,
      "reason": "manual_adjustment"
    }
  ],
  "total": 4
}
```

**Envelope fields:**

| Field | Type | Description |
|-------|------|-------------|
| `ok` | bool | Always `true` on success |
| `miner_id` | string | Resolved wallet identifier |
| `transactions` | array | Page of unified transaction entries (see below) |
| `total` | integer | Total number of transactions before pagination |

**Transaction entry types** -- every entry has the common shape
``{type, amount, epoch, timestamp, tx_hash}`` plus type-specific extras:

| `type` | Extra fields | Source |
|--------|--------------|--------|
| `transfer_in` | `from` (sender address) | `ledger` rows whose `reason` starts with `transfer_in:` |
| `transfer_out` | `to` (recipient address); `status` when pending | `ledger` (`transfer_out:` reason) and unconfirmed `pending_ledger` rows |
| `reward` | -- | `epoch_rewards` mining payouts |
| `ledger` | `reason` (raw ledger reason string) | `ledger` rows without a `transfer_*:` reason prefix |

**Per-field reference:**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | One of `transfer_in`, `transfer_out`, `reward`, `ledger` |
| `amount` | float | Amount in RTC (human-readable). Always non-negative. |
| `epoch` | integer\|null | Epoch number, when known (null for pending) |
| `timestamp` | integer | Unix timestamp used for sorting (DESC) |
| `tx_hash` | string\|null | Transaction hash, or null for reward / non-transfer rows |
| `from` | string | (transfer_in only) Sender wallet address |
| `to` | string | (transfer_out only) Recipient wallet address |
| `status` | string | (pending rows only) Raw `pending_ledger.status` |
| `reason` | string\|null | (ledger type only) Raw `reason` field from `ledger` |

**Migration from the legacy flat-array contract (pre-#997):**

The pre-#997 contract returned ``[{...}, ...]`` directly with aliases
``tx_id`` / ``from_addr`` / ``to_addr`` / ``counterparty`` / ``direction``
/ ``confirmations`` / ``memo`` / ``raw_status`` / ``status_reason``. These
fields are removed in the unified contract. Consumers should:

* Replace ``body[i]`` with ``body["transactions"][i]``
* Replace ``tx_id`` with ``tx_hash``
* Replace ``from_addr`` with ``from`` (and only present on ``transfer_in``)
* Replace ``to_addr`` with ``to`` (and only present on ``transfer_out``)
* Derive direction by checking whether ``type`` is ``transfer_in`` or
  ``transfer_out``; the counterparty is the value of ``from`` / ``to``
* Check ``status`` for in-flight transactions; ``confirmations`` is no
  longer surfaced (the row exists in the immutable ledger iff confirmed)

**Notes:**

- Transactions ordered by `timestamp DESC` (newest first)
- Confirmed rows come from `ledger`; pending rows from `pending_ledger`;
  mining payouts from `epoch_rewards`
- A `pending_ledger` row whose status is `confirmed` is deduped (already
  represented in `ledger`)
- Empty result: `{"ok": true, "miner_id": "...", "transactions": [], "total": 0}`

**Request:**

```bash
curl -fsS "https://rustchain.org/wallet/history?miner_id=eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC&limit=10" | jq .
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `miner_id` | string | Yes* | Wallet identifier (canonical) |
| `address` | string | Yes* | Backward-compatible alias for `miner_id` |
| `limit` | integer | No | Max records (1-200, default: 50) |
| `offset` | integer | No | Records to skip for pagination (0-9800, default: 0) |

*Either `miner_id` or `address` is required.

**Pagination:**
- Default limit: 50 records
- Clamped to range 1-200
- Invalid limit or offset (non-integer) returns 400 error

**Errors:**

| HTTP | `error` | Cause |
|------|---------|-------|
| 400 | `miner_id or address required` | Neither parameter supplied |
| 400 | `miner_id and address must match when both are provided` | Alias conflict |
| 400 | `limit must be an integer` | `limit` not parseable as int |
| 400 | `offset must be an integer` | `offset` not parseable as int |
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
curl -fsS -X POST https://rustchain.org/wallet/transfer/signed \
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

### Fee market compatibility

RustChain keeps legacy signed-transfer fees backward compatible while exposing
EIP-1559-compatible fee math for new callers and block builders:

- Legacy transfers may continue to provide `fee_rtc`; that fixed fee is treated
  as a priority tip until a block context supplies a base fee.
- Legacy fixed fees preserve the exact total in `priority_tip_nrtc` and
  `total_fee_nrtc`; if a fee is not evenly divisible by `gas_limit`,
  `priority_fee_per_gas_nrtc` rounds down and should not be used to
  reconstruct the total by multiplication.
- EIP-1559-style callers can split fees into a burned base fee and a
  priority tip using `base_fee_per_gas_nrtc`, `max_fee_per_gas_nrtc`,
  `max_priority_fee_per_gas_nrtc`, and `gas_limit`.
- The next base fee follows the bounded EIP-1559 adjustment formula:
  `parent_base_fee + parent_base_fee * gas_delta / target_gas / 8` when the
  parent block is above target gas, and the corresponding subtraction when it
  is below target gas.

---

## Attestation

### `POST /attest/submit`

Submit hardware fingerprint for epoch enrollment.

**Request:**
```bash
curl -fsS -X POST https://rustchain.org/attest/submit \
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

resp = requests.get("https://rustchain.org/health")
data = resp.json()
print(f"Node OK: {data['ok']}, Version: {data['version']}")
print(f"Uptime: {data['uptime_s']}s, Epoch: {data.get('epoch', 'N/A')}")
```

### Get Epoch Info

```python
import requests

resp = requests.get("https://rustchain.org/epoch")
data = resp.json()
print(f"Epoch {data['epoch']}, Slot {data['slot']}/{data['blocks_per_epoch']}")
print(f"Pot: {data['epoch_pot']} RTC, Miners: {data['enrolled_miners']}")
```

### List Active Miners

```python
import requests

resp = requests.get("https://rustchain.org/api/miners")
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

### Local or Raw-IP Certificate Note

The public `https://rustchain.org` hostname should use normal certificate
verification. Only use a custom trust store or disabled verification for local
development nodes or raw-IP diagnostics with self-signed certificates.

```python
import requests

# Local/raw-IP diagnostic only; avoid this for https://rustchain.org.
requests.get(url, verify=False)

# Better: download the local diagnostic certificate and verify it explicitly.
import httpx
client = httpx.Client(verify="/path/to/rustchain.crt")
```
