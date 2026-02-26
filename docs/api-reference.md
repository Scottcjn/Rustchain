# RustChain API Reference

## Overview

RustChain provides a REST API for interacting with the network. All endpoints use HTTPS with a self-signed certificate (use `-k` flag with curl).

**Base URL**: `https://50.28.86.131`

**Internal URL**: `http://localhost:8099` (on VPS only)

## Authentication

Most endpoints are public. Admin endpoints require the `X-Admin-Key` header:

```bash
-H "X-Admin-Key: YOUR_ADMIN_KEY"
```

## Public Endpoints

### Health & Status

#### GET /health

Check node health status.

```bash
curl -sk https://50.28.86.131/health
```

**Response**:
```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 4313,
  "db_rw": true,
  "backup_age_hours": 17.15,
  "tip_age_slots": 0
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | Node is healthy |
| `version` | string | Node software version |
| `uptime_s` | integer | Seconds since node start |
| `db_rw` | boolean | Database is read/write |
| `backup_age_hours` | float | Hours since last backup |
| `tip_age_slots` | integer | Slots behind tip (0 = synced) |

---

#### GET /ready

Kubernetes-style readiness probe.

```bash
curl -sk https://50.28.86.131/ready
```

**Response**:
```json
{
  "ready": true
}
```

---

### Epoch Information

#### GET /epoch

Get current epoch and slot information.

```bash
curl -sk https://50.28.86.131/epoch
```

**Response**:
```json
{
  "epoch": 75,
  "slot": 10800,
  "blocks_per_epoch": 144,
  "epoch_pot": 1.5,
  "enrolled_miners": 10
}
```

| Field | Type | Description |
|-------|------|-------------|
| `epoch` | integer | Current epoch number |
| `slot` | integer | Current slot within epoch |
| `blocks_per_epoch` | integer | Slots per epoch (144) |
| `epoch_pot` | float | RTC reward pool for epoch |
| `enrolled_miners` | integer | Active miners this epoch |

---

### Network Data

#### GET /api/miners

List all active miners with hardware details.

```bash
curl -sk https://50.28.86.131/api/miners
```

**Response**:
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
    "first_attest": null
  },
  {
    "miner": "scott",
    "device_arch": "x86_64",
    "device_family": "Intel",
    "hardware_type": "Modern x86_64",
    "antiquity_multiplier": 1.0,
    "entropy_score": 0.0,
    "last_attest": 1771187200,
    "first_attest": 1770000000
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `miner` | string | Miner wallet ID |
| `device_arch` | string | CPU architecture |
| `device_family` | string | CPU family |
| `hardware_type` | string | Human-readable hardware description |
| `antiquity_multiplier` | float | Reward multiplier |
| `entropy_score` | float | Hardware entropy score |
| `last_attest` | integer | Unix timestamp of last attestation |
| `first_attest` | integer | Unix timestamp of first attestation |

---

#### GET /api/nodes

List connected attestation nodes.

```bash
curl -sk https://50.28.86.131/api/nodes
```

**Response**:
```json
[
  {
    "node_id": "primary",
    "address": "50.28.86.131",
    "role": "attestation",
    "status": "active",
    "last_seen": 1771187406
  },
  {
    "node_id": "ergo-anchor",
    "address": "50.28.86.153",
    "role": "anchor",
    "status": "active",
    "last_seen": 1771187400
  }
]
```

---

### Wallet Operations

#### GET /wallet/balance

Check RTC balance for a miner wallet.

```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=scott"
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `miner_id` | string | Yes | Wallet identifier |

**Response**:
```json
{
  "ok": true,
  "miner_id": "scott",
  "amount_rtc": 42.5
}
```

**Error Response** (wallet not found):
```json
{
  "ok": false,
  "error": "WALLET_NOT_FOUND",
  "miner_id": "unknown"
}
```

---

### Attestation

#### POST /attest/submit

Submit hardware attestation to enroll in current epoch.

```bash
curl -sk -X POST https://50.28.86.131/attest/submit \
  -H "Content-Type: application/json" \
  -d '{
    "miner_id": "scott",
    "timestamp": 1771187406,
    "device_info": {
      "arch": "PowerPC",
      "family": "G4"
    },
    "fingerprint": {
      "clock_skew": {"drift_ppm": 24.3, "jitter_ns": 1247},
      "cache_timing": {"l1_latency_ns": 5, "l2_latency_ns": 15},
      "simd_identity": {"instruction_set": "AltiVec", "pipeline_bias": 0.76},
      "thermal_entropy": {"idle_temp_c": 42.1, "load_temp_c": 71.3, "variance": 3.8},
      "instruction_jitter": {"mean_ns": 3200, "stddev_ns": 890},
      "behavioral_heuristics": {"cpuid_clean": true, "no_hypervisor": true}
    },
    "signature": "Ed25519_base64_signature..."
  }'
```

**Response (Success)**:
```json
{
  "enrolled": true,
  "epoch": 75,
  "multiplier": 2.5,
  "hw_hash": "abc123def456...",
  "next_settlement": 1771200000
}
```

**Response (VM Detected)**:
```json
{
  "error": "VM_DETECTED",
  "failed_checks": ["clock_skew", "thermal_entropy"],
  "penalty_multiplier": 0.0000000025
}
```

**Response (Hardware Already Bound)**:
```json
{
  "error": "HARDWARE_ALREADY_BOUND",
  "existing_miner": "other_wallet"
}
```

---

#### GET /lottery/eligibility

Check if miner is enrolled in current epoch.

```bash
curl -sk "https://50.28.86.131/lottery/eligibility?miner_id=scott"
```

**Response**:
```json
{
  "eligible": true,
  "epoch": 75,
  "multiplier": 2.5,
  "last_attest": 1771187406,
  "status": "active"
}
```

---

### Block Explorer

#### GET /explorer

Web UI for browsing blocks and transactions.

```bash
open https://50.28.86.131/explorer
```

Returns HTML page (not JSON).

---

### Settlement Data

#### GET /api/settlement/{epoch}

Query historical settlement data for a specific epoch.

```bash
curl -sk https://50.28.86.131/api/settlement/75
```

**Response**:
```json
{
  "epoch": 75,
  "timestamp": 1771200000,
  "total_pot": 1.5,
  "total_distributed": 1.5,
  "miner_count": 5,
  "settlement_hash": "8a3f2e1d9c7b6a5e4f3d2c1b0a9e8d7c...",
  "ergo_tx_id": "abc123...",
  "rewards": {
    "scott": 0.487,
    "pffs1802": 0.390,
    "miner3": 0.195,
    "miner4": 0.195,
    "miner5": 0.234
  }
}
```

---

## Admin Endpoints

These endpoints require the `X-Admin-Key` header.

### POST /wallet/transfer

Transfer RTC between wallets (admin only).

```bash
curl -sk -X POST https://50.28.86.131/wallet/transfer \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "from_miner": "treasury",
    "to_miner": "scott",
    "amount_rtc": 10.0,
    "memo": "Bounty payment #123"
  }'
```

**Response**:
```json
{
  "ok": true,
  "tx_id": "tx_abc123...",
  "from_balance": 990.0,
  "to_balance": 52.5
}
```

---

### POST /rewards/settle

Manually trigger epoch settlement (admin only).

```bash
curl -sk -X POST https://50.28.86.131/rewards/settle \
  -H "X-Admin-Key: YOUR_ADMIN_KEY"
```

**Response**:
```json
{
  "ok": true,
  "epoch": 75,
  "miners_rewarded": 5,
  "total_distributed": 1.5,
  "settlement_hash": "8a3f2e1d..."
}
```

---

## Premium Endpoints (x402)

These endpoints support the x402 payment protocol (currently free during beta).

### GET /api/premium/videos

Bulk video export (BoTTube integration).

```bash
curl -sk https://50.28.86.131/api/premium/videos
```

---

### GET /api/premium/analytics/{agent}

Deep agent analytics.

```bash
curl -sk https://50.28.86.131/api/premium/analytics/scott
```

---

### GET /wallet/swap-info

USDC/wRTC swap guidance.

```bash
curl -sk https://50.28.86.131/wallet/swap-info
```

**Response**:
```json
{
  "rtc_price_usd": 0.10,
  "wrtc_solana_mint": "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X",
  "wrtc_base_contract": "0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6",
  "raydium_pool": "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb",
  "bridge_url": "https://bottube.ai/bridge"
}
```

---

## Error Codes

| HTTP Code | Error | Description |
|-----------|-------|-------------|
| 200 | - | Success |
| 400 | `BAD_REQUEST` | Invalid JSON or parameters |
| 400 | `VM_DETECTED` | Hardware fingerprint failed |
| 400 | `INVALID_SIGNATURE` | Ed25519 signature invalid |
| 401 | `UNAUTHORIZED` | Missing or invalid X-Admin-Key |
| 404 | `NOT_FOUND` | Endpoint or resource not found |
| 409 | `HARDWARE_ALREADY_BOUND` | Hardware enrolled to another wallet |
| 429 | `RATE_LIMITED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error |

---

## Common Mistakes

### Wrong Endpoints

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| `/balance/{address}` | `/wallet/balance?miner_id=NAME` |
| `/miners?limit=N` | `/api/miners` (no pagination) |
| `/block/{height}` | `/explorer` (web UI) |
| `/api/balance` | `/wallet/balance?miner_id=...` |

### Wrong Field Names

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| `epoch_number` | `epoch` |
| `current_slot` | `slot` |
| `miner_id` (in response) | `miner` |
| `multiplier` | `antiquity_multiplier` |
| `last_attestation` | `last_attest` |

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/health`, `/ready` | 60/min |
| `/epoch`, `/api/miners` | 30/min |
| `/wallet/balance` | 30/min |
| `/attest/submit` | 1/min per miner |
| Admin endpoints | 10/min |

---

## HTTPS Certificate

The node uses a self-signed certificate. Options:

```bash
# Option 1: Skip verification (development)
curl -sk https://50.28.86.131/health

# Option 2: Download and trust certificate
openssl s_client -connect 50.28.86.131:443 -showcerts < /dev/null 2>/dev/null | \
  openssl x509 -outform PEM > rustchain.pem
curl --cacert rustchain.pem https://50.28.86.131/health
```

---

## SDK Examples

### Python

```python
import requests

BASE_URL = "https://50.28.86.131"

def get_balance(miner_id):
    resp = requests.get(
        f"{BASE_URL}/wallet/balance",
        params={"miner_id": miner_id},
        verify=False  # Self-signed cert
    )
    return resp.json()

def get_epoch():
    resp = requests.get(f"{BASE_URL}/epoch", verify=False)
    return resp.json()

# Usage
print(get_balance("scott"))
print(get_epoch())
```

### JavaScript

```javascript
const BASE_URL = "https://50.28.86.131";

async function getBalance(minerId) {
  const resp = await fetch(
    `${BASE_URL}/wallet/balance?miner_id=${minerId}`
  );
  return resp.json();
}

async function getEpoch() {
  const resp = await fetch(`${BASE_URL}/epoch`);
  return resp.json();
}

// Usage
getBalance("scott").then(console.log);
getEpoch().then(console.log);
```

### Bash

```bash
#!/bin/bash
BASE_URL="https://50.28.86.131"

# Get balance
get_balance() {
  curl -sk "$BASE_URL/wallet/balance?miner_id=$1" | jq
}

# Get epoch
get_epoch() {
  curl -sk "$BASE_URL/epoch" | jq
}

# Usage
get_balance "scott"
get_epoch
```

---

**Next**: See [glossary.md](./glossary.md) for terminology reference.
