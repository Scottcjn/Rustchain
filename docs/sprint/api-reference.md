# RustChain API Reference

**Version:** 2.2.1-rip200  
**Auth:** None required (public API)  
**Protocol:** HTTP/1.1 (JSON)

## Base URLs

| Node | URL |
|------|-----|
| Primary attestation node | `http://rustchain.org:8088` |
| Ergo anchor node | `http://50.28.86.153:8088` |

Both nodes expose identical public endpoints. Direct attestation submissions to
the primary node; use either for read-only queries.

> **Note:** The production TLS endpoint `https://rustchain.org` requires the
> `-k` flag with curl (self-signed cert). The raw IP:port endpoints shown
> throughout this reference are HTTP and need no `-k`.

---

## Endpoints

### POST /attest/submit

Submit a hardware fingerprint to enroll in the current epoch. The node runs six
hardware checks against the fingerprint. On success, the miner is enrolled and
receives a reward multiplier based on hardware antiquity.

**Method:** `POST`  
**Path:** `/attest/submit`  
**Content-Type:** `application/json`

#### Request Body

```json
{
  "miner_id": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC",
  "timestamp": 1771187406,
  "device_info": {
    "arch": "PowerPC",
    "family": "G4"
  },
  "fingerprint": {
    "clock_skew": {
      "drift_ppm": 24.3,
      "jitter_ns": 1247
    },
    "cache_timing": {
      "l1_latency_ns": 5,
      "l2_latency_ns": 15
    },
    "simd_identity": {
      "instruction_set": "AltiVec",
      "pipeline_bias": 0.76
    },
    "thermal_entropy": {
      "idle_temp_c": 42.1,
      "load_temp_c": 71.3,
      "variance": 3.8
    },
    "instruction_jitter": {
      "mean_ns": 3200,
      "stddev_ns": 890
    },
    "behavioral_heuristics": {
      "cpuid_clean": true,
      "no_hypervisor": true
    }
  },
  "signature": "Ed25519_base64_encoded_signature_here"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `miner_id` | string | ✓ | Wallet address / miner identifier |
| `timestamp` | integer | ✓ | Unix timestamp of attestation (replay protection) |
| `device_info.arch` | string | ✓ | CPU architecture (e.g. `PowerPC`, `x86_64`, `arm64`) |
| `device_info.family` | string | ✓ | CPU family (e.g. `G4`, `G5`, `M2`, `Intel`) |
| `fingerprint` | object | ✓ | Six hardware measurement sub-objects |
| `signature` | string | ✓ | Base64 Ed25519 signature over canonical fields |

#### Response — 200 Enrolled

```json
{
  "enrolled": true,
  "epoch": 75,
  "multiplier": 2.5,
  "hw_hash": "abc123def456789...",
  "next_settlement": 1771200000
}
```

| Field | Type | Description |
|-------|------|-------------|
| `enrolled` | boolean | `true` when miner is in the epoch |
| `epoch` | integer | Current epoch number |
| `multiplier` | float | Antiquity reward multiplier (1.0–2.8×) |
| `hw_hash` | string | Fingerprint hash stored on-chain |
| `next_settlement` | integer | Unix timestamp of epoch settlement |

#### Response — 400 VM Detected

```json
{
  "error": "VM_DETECTED",
  "failed_checks": ["clock_skew", "thermal_entropy"],
  "penalty_multiplier": 0.0
}
```

#### Response — 409 Hardware Already Bound

```json
{
  "error": "HARDWARE_ALREADY_BOUND",
  "existing_miner": "other_wallet_idRTC"
}
```

#### Example curl

```bash
curl -X POST http://rustchain.org:8088/attest/submit \
  -H "Content-Type: application/json" \
  -d '{
    "miner_id": "mywalletRTC",
    "timestamp": 1771187406,
    "device_info": {"arch": "PowerPC", "family": "G4"},
    "fingerprint": {
      "clock_skew":           {"drift_ppm": 24.3, "jitter_ns": 1247},
      "cache_timing":         {"l1_latency_ns": 5, "l2_latency_ns": 15},
      "simd_identity":        {"instruction_set": "AltiVec", "pipeline_bias": 0.76},
      "thermal_entropy":      {"idle_temp_c": 42.1, "load_temp_c": 71.3, "variance": 3.8},
      "instruction_jitter":   {"mean_ns": 3200, "stddev_ns": 890},
      "behavioral_heuristics":{"cpuid_clean": true, "no_hypervisor": true}
    },
    "signature": "BASE64_SIG_HERE"
  }' | python3 -m json.tool
```

**Status codes:** `200` (enrolled), `400` (bad request / VM detected), `409` (hardware conflict), `429` (rate limited)

---

### GET /api/miners

List all currently enrolled miners with hardware metadata and reward multipliers.

**Method:** `GET`  
**Path:** `/api/miners`

#### Request

No parameters.

#### Response — 200

```json
[
  {
    "miner": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC",
    "device_arch": "G4",
    "device_family": "PowerPC",
    "hardware_type": "PowerPC G4 (Vintage)",
    "antiquity_multiplier": 2.5,
    "entropy_score": 0.0,
    "last_attest": 1771187406,
    "first_attest": 1770000000
  },
  {
    "miner": "scottRTC",
    "device_arch": "x86_64",
    "device_family": "Intel",
    "hardware_type": "Modern x86_64",
    "antiquity_multiplier": 1.0,
    "entropy_score": 0.0,
    "last_attest": 1771187200,
    "first_attest": null
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `miner` | string | Unique miner/wallet identifier |
| `device_arch` | string | CPU architecture code (G4, G5, M2, x86_64, …) |
| `device_family` | string | CPU family (PowerPC, Intel, AMD, Apple, …) |
| `hardware_type` | string | Human-readable hardware description |
| `antiquity_multiplier` | float | Reward multiplier applied at settlement (1.0–2.8×) |
| `entropy_score` | float | Hardware entropy quality score |
| `last_attest` | integer | Unix timestamp of most recent attestation |
| `first_attest` | integer\|null | Unix timestamp of first-ever attestation (null = unknown) |

#### Example curl

```bash
curl http://rustchain.org:8088/api/miners | python3 -m json.tool
```

**Status codes:** `200` (success), `429` (rate limited), `500` (server error)

---

### GET /api/stats

Return aggregate network statistics including current epoch, total miner count,
total circulating balance, and enabled protocol features.

**Method:** `GET`  
**Path:** `/api/stats`

#### Request

No parameters.

#### Response — 200

```json
{
  "version": "2.2.1-security-hardened",
  "chain_id": "rustchain-mainnet-v2",
  "epoch": 75,
  "block_time": 600,
  "total_miners": 42,
  "total_balance": 87432.5,
  "pending_withdrawals": 3,
  "features": ["RIP-0005", "RIP-0008", "RIP-0009", "RIP-0142", "RIP-0143", "RIP-0144"],
  "security": ["no_mock_sigs", "mandatory_admin_key", "replay_protection", "validated_json"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Node software version string |
| `chain_id` | string | Network identifier |
| `epoch` | integer | Current epoch number |
| `block_time` | integer | Slot duration in seconds (600 = 10 min) |
| `total_miners` | integer | All wallets with any balance (lifetime count) |
| `total_balance` | float | Sum of all positive wallet balances in RTC |
| `pending_withdrawals` | integer | Withdrawals awaiting confirmation |
| `features` | string[] | Active RIP protocol extensions |
| `security` | string[] | Active security features |

#### Example curl

```bash
curl http://rustchain.org:8088/api/stats | python3 -m json.tool
```

**Status codes:** `200` (success), `500` (server error)

---

### GET /api/epochs

Return reward distribution data for a specific historical epoch.

**Method:** `GET`  
**Path:** `/api/epochs` (alias: `/rewards/epoch/<epoch>`)

> **Note:** The canonical path for single-epoch reward lookup is
> `GET /rewards/epoch/{epoch}`. Clients should use the per-epoch path directly.

#### Path variant

```
GET /rewards/epoch/{epoch}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `epoch` | integer | Epoch number to query |

#### Response — 200

```json
{
  "epoch": 74,
  "rewards": [
    {
      "miner_id": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC",
      "share_i64": 750000,
      "share_rtc": 0.75
    },
    {
      "miner_id": "scottRTC",
      "share_i64": 750000,
      "share_rtc": 0.75
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `epoch` | integer | Queried epoch number |
| `rewards[].miner_id` | string | Miner wallet identifier |
| `rewards[].share_i64` | integer | Reward in micro-RTC (6 decimal places) |
| `rewards[].share_rtc` | float | Reward in RTC (human-readable) |

Empty `rewards` array means no settlement data for that epoch.

#### Example curl

```bash
# Query epoch 74
curl http://rustchain.org:8088/rewards/epoch/74 | python3 -m json.tool

# Query on the anchor node
curl http://50.28.86.153:8088/rewards/epoch/74 | python3 -m json.tool
```

**Status codes:** `200` (success, may be empty), `404` (epoch not found), `500` (server error)

---

### GET /health

Check node liveness, database status, and sync state.

**Method:** `GET`  
**Path:** `/health`

#### Request

No parameters.

#### Response — 200 Healthy

```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 18728,
  "db_rw": true,
  "backup_age_hours": 6.75,
  "tip_age_slots": 0
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | `true` when node is healthy |
| `version` | string | Protocol version |
| `uptime_s` | integer | Seconds since node start |
| `db_rw` | boolean | `true` when database is read-write |
| `backup_age_hours` | float | Hours since last database backup |
| `tip_age_slots` | integer | Slots behind chain tip (0 = fully synced) |

#### Response — 503 Unhealthy

```json
{
  "ok": false,
  "version": "2.2.1-rip200",
  "uptime_s": 900
}
```

#### Example curl

```bash
# Quick liveness check — primary node
curl http://rustchain.org:8088/health

# Anchor node
curl http://50.28.86.153:8088/health

# Pretty-print + check both simultaneously
for NODE in 50.28.86.131 50.28.86.153; do
  echo "=== $NODE ==="; curl -s "http://$NODE:8088/health" | python3 -m json.tool
done
```

**Status codes:** `200` (healthy), `503` (unhealthy or node starting up)

---

## Error Codes

| HTTP | Code | Description |
|------|------|-------------|
| 400 | `BAD_REQUEST` | Malformed JSON or missing required field |
| 400 | `VM_DETECTED` | Attestation failed — virtual machine fingerprint |
| 400 | `INVALID_SIGNATURE` | Ed25519 signature verification failed |
| 400 | `REPLAY_DETECTED` | Timestamp/nonce reuse detected |
| 404 | `NOT_FOUND` | Resource or epoch does not exist |
| 409 | `HARDWARE_ALREADY_BOUND` | Hardware enrolled under a different wallet |
| 429 | `RATE_LIMITED` | Too many requests — back off and retry |
| 500 | `INTERNAL_ERROR` | Unexpected server error |

## Rate Limits

| Endpoint group | Limit |
|----------------|-------|
| `/health` | 60 requests / minute |
| `/api/miners`, `/api/stats` | 30 requests / minute |
| `/rewards/epoch/*` | 30 requests / minute |
| `/attest/submit` | 1 request / 10 minutes per miner |

---

*API documented for RustChain v2.2.1-rip200 · Base URLs: http://rustchain.org:8088, http://50.28.86.153:8088*
