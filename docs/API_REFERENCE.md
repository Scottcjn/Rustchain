# RustChain API Reference

> **Complete API documentation for RustChain Proof-of-Antiquity blockchain**

**Base URL:** `https://50.28.86.131`  
**Protocol Version:** `2.2.1-rip200`  
**SSL:** Self-signed certificate (use `-k` flag with curl)

---

## Table of Contents

- [Quick Start](#quick-start)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [Health & Status](#health--status)
  - [Epoch Information](#epoch-information)
  - [Miners](#miners)
  - [Wallet](#wallet)
  - [Attestation](#attestation)
- [Data Types](#data-types)
- [Error Codes](#error-codes)
- [Rate Limits](#rate-limits)
- [Examples](#examples)

---

## Quick Start

Test the API is working:

```bash
# Check node health
curl -sk https://50.28.86.131/health | jq .

# Get current epoch
curl -sk https://50.28.86.131/epoch | jq .

# List active miners
curl -sk https://50.28.86.131/api/miners | jq .
```

> **Note:** The `-s` flag silences curl progress, and `-k` bypasses SSL certificate verification (required for self-signed certs).

---

## Authentication

Most read endpoints are public and don't require authentication. Write operations (transfers, attestations) require Ed25519 signatures.

### Signature Format

```json
{
  "from": "miner_id",
  "payload": { ... },
  "nonce": 12345,
  "signature": "base64_encoded_ed25519_signature"
}
```

The signature is computed over `SHA256(nonce + JSON.stringify(payload))`.

---

## Endpoints

### Health & Status

#### `GET /health`

Check node status, version, and sync state.

**Request:**
```bash
curl -sk https://50.28.86.131/health
```

**Response:**
```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 197968,
  "db_rw": true,
  "backup_age_hours": 15.99,
  "tip_age_slots": 0
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | `true` if node is healthy |
| `version` | string | Protocol version (e.g., "2.2.1-rip200") |
| `uptime_s` | integer | Seconds since node startup |
| `db_rw` | boolean | Database is writable |
| `backup_age_hours` | float | Hours since last backup |
| `tip_age_slots` | integer | Slots behind chain tip (0 = fully synced) |

**Status Codes:**
- `200 OK` - Node is healthy
- `503 Service Unavailable` - Node is syncing or unhealthy

---

### Epoch Information

#### `GET /epoch`

Get current epoch details and network state.

**Request:**
```bash
curl -sk https://50.28.86.131/epoch
```

**Response:**
```json
{
  "epoch": 65,
  "slot": 9497,
  "blocks_per_epoch": 144,
  "epoch_pot": 1.5,
  "enrolled_miners": 2
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `epoch` | integer | Current epoch number |
| `slot` | integer | Current slot within the epoch |
| `blocks_per_epoch` | integer | Total slots per epoch (144 = ~24h) |
| `epoch_pot` | float | RTC tokens to distribute this epoch |
| `enrolled_miners` | integer | Number of miners eligible for rewards |

**Understanding Epochs:**
- Each epoch is ~24 hours (144 slots × 10 minutes)
- Rewards are distributed at epoch boundaries
- Miners must re-enroll each epoch to receive rewards

---

### Miners

#### `GET /api/miners`

List all active/enrolled miners with their hardware details.

**Request:**
```bash
curl -sk https://50.28.86.131/api/miners
```

**Response:**
```json
[
  {
    "miner": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC",
    "device_family": "PowerPC",
    "device_arch": "G4",
    "hardware_type": "PowerPC G4 (Vintage)",
    "antiquity_multiplier": 2.5,
    "entropy_score": 0.0,
    "last_attest": 1770405548
  },
  {
    "miner": "modern-sophiacore-3a168058",
    "device_family": "x86_64",
    "device_arch": "modern",
    "hardware_type": "x86-64 (Modern)",
    "antiquity_multiplier": 0.8,
    "entropy_score": 0.0,
    "last_attest": 1770405483
  }
]
```

**Response Fields (per miner):**

| Field | Type | Description |
|-------|------|-------------|
| `miner` | string | Unique miner ID (wallet address) |
| `device_family` | string | CPU family: `PowerPC`, `x86_64`, `Apple Silicon` |
| `device_arch` | string | Architecture: `G3`, `G4`, `G5`, `modern`, `M1`, `M2`, etc. |
| `hardware_type` | string | Human-readable hardware description |
| `antiquity_multiplier` | float | Reward multiplier (0.8x - 2.5x) |
| `entropy_score` | float | Hardware entropy quality score |
| `last_attest` | integer | Unix timestamp of last attestation |

**Antiquity Multipliers:**

| Hardware | Multiplier |
|----------|------------|
| PowerPC G4 | 2.5× |
| PowerPC G5 | 2.0× |
| PowerPC G3 | 1.8× |
| IBM POWER8 | 1.5× |
| Apple Silicon M1 | 1.2× |
| Modern x86_64 | 0.8× - 1.0× |

---

### Wallet

#### `GET /wallet/balance`

Check RTC balance for a miner wallet.

**Request:**
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_ID"
```

**Example:**
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC"
```

**Response:**
```json
{
  "miner_id": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC",
  "amount_rtc": 118.357193,
  "amount_i64": 118357193
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `miner_id` | string | Wallet/miner identifier |
| `amount_rtc` | float | Balance in RTC (human-readable) |
| `amount_i64` | integer | Balance in micro-RTC (6 decimal places) |

**Query Parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `miner_id` | Yes | The wallet address to check |

---

#### `POST /wallet/transfer/signed`

Transfer RTC tokens to another wallet. Requires Ed25519 signature.

**Request:**
```bash
curl -sk -X POST https://50.28.86.131/wallet/transfer/signed \
  -H "Content-Type: application/json" \
  -d '{
    "from": "sender_miner_id",
    "to": "recipient_miner_id",
    "amount_i64": 1000000,
    "nonce": 12345,
    "signature": "base64_ed25519_signature"
  }'
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `from` | string | Yes | Sender wallet ID |
| `to` | string | Yes | Recipient wallet ID |
| `amount_i64` | integer | Yes | Amount in micro-RTC (1 RTC = 1,000,000) |
| `nonce` | integer | Yes | Unique transaction nonce |
| `signature` | string | Yes | Base64-encoded Ed25519 signature |

**Response (Success):**
```json
{
  "success": true,
  "tx_hash": "abc123def456...",
  "new_balance": 117357193
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "INSUFFICIENT_BALANCE",
  "detail": "Requested 10.0 RTC but balance is 5.5 RTC"
}
```

---

### Attestation

#### `POST /attest/challenge`

Request a challenge nonce for hardware attestation.

**Request:**
```bash
curl -sk -X POST https://50.28.86.131/attest/challenge \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Response:**
```json
{
  "nonce": "a1b2c3d4e5f6...",
  "expires_at": 1770406000
}
```

---

#### `POST /attest/submit`

Submit hardware fingerprint for epoch enrollment.

**Request:**
```bash
curl -sk -X POST https://50.28.86.131/attest/submit \
  -H "Content-Type: application/json" \
  -d '{
    "miner_id": "your_miner_id",
    "nonce": "challenge_nonce",
    "fingerprint": {
      "clock_skew": { ... },
      "cache_timing": { ... },
      "simd_identity": { ... },
      "thermal_entropy": { ... },
      "instruction_jitter": { ... },
      "behavioral_heuristics": { ... }
    },
    "device": {
      "family": "x86_64",
      "arch": "modern",
      "model": "AMD Ryzen 5 8645HS"
    },
    "signature": "base64_ed25519_signature"
  }'
```

**Fingerprint Checks (RIP-PoA):**

| Check | Description |
|-------|-------------|
| `clock_skew` | Oscillator drift patterns unique to silicon aging |
| `cache_timing` | L1/L2/L3 cache latency fingerprint |
| `simd_identity` | SIMD unit detection (SSE/AVX/AltiVec/NEON) |
| `thermal_entropy` | Thermal drift patterns under load |
| `instruction_jitter` | Microarchitecture timing variations |
| `behavioral_heuristics` | Anti-VM/emulation detection |

**Response (Success):**
```json
{
  "success": true,
  "enrolled": true,
  "epoch": 65,
  "multiplier": 2.5,
  "next_settlement_slot": 9600
}
```

**Response (Rejected - VM Detected):**
```json
{
  "success": false,
  "error": "VM_DETECTED",
  "check_failed": "behavioral_heuristics",
  "detail": "Hypervisor signature detected in CPUID"
}
```

---

#### `POST /epoch/enroll`

Enroll in the current epoch for mining rewards.

**Request:**
```bash
curl -sk -X POST https://50.28.86.131/epoch/enroll \
  -H "Content-Type: application/json" \
  -d '{
    "miner_pubkey": "your_wallet_address",
    "miner_id": "friendly-name-123",
    "device": {
      "family": "PowerPC",
      "arch": "G4"
    }
  }'
```

**Response (Success):**
```json
{
  "ok": true,
  "epoch": 65,
  "weight": 2.5,
  "hw_weight": 2.5
}
```

---

## Data Types

### Miner ID / Wallet Address

- Format: `[a-zA-Z0-9_-]{1,64}RTC` or SHA256 hash suffix
- Example: `eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC`
- Example: `my-vintage-mac-g4RTC`

### RTC Amounts

- `amount_rtc`: Float with up to 6 decimal places
- `amount_i64`: Integer representing micro-RTC (1 RTC = 1,000,000)
- Example: `1.5 RTC` = `1500000` in i64 format

### Unix Timestamps

- All timestamps are Unix epoch seconds (not milliseconds)
- Example: `1770405548` = February 2026

---

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VM_DETECTED` | 400 | Attestation failed - virtual machine detected |
| `EMULATOR_DETECTED` | 400 | Running on emulated hardware |
| `INVALID_SIGNATURE` | 401 | Ed25519 signature verification failed |
| `INSUFFICIENT_BALANCE` | 400 | Not enough RTC for transfer |
| `MINER_NOT_FOUND` | 404 | Unknown miner ID |
| `ATTESTATION_EXPIRED` | 400 | Attestation too old, request new challenge |
| `ALREADY_ENROLLED` | 400 | Miner already enrolled this epoch |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server-side error |

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| Public endpoints (`/health`, `/epoch`, `/api/miners`) | 100 requests/minute |
| Wallet balance | 60 requests/minute |
| Attestation | 1 per 10 minutes per miner |
| Transfers | 10 per minute per wallet |

Exceeding rate limits returns `429 Too Many Requests`.

---

## Examples

### Python SDK Example

```python
import requests
import json

NODE_URL = "https://50.28.86.131"

def get_health():
    """Check node health"""
    resp = requests.get(f"{NODE_URL}/health", verify=False)
    return resp.json()

def get_epoch():
    """Get current epoch info"""
    resp = requests.get(f"{NODE_URL}/epoch", verify=False)
    return resp.json()

def get_miners():
    """List all active miners"""
    resp = requests.get(f"{NODE_URL}/api/miners", verify=False)
    return resp.json()

def get_balance(miner_id: str) -> dict:
    """Check wallet balance"""
    resp = requests.get(
        f"{NODE_URL}/wallet/balance",
        params={"miner_id": miner_id},
        verify=False
    )
    return resp.json()

# Example usage
if __name__ == "__main__":
    print("Node Health:", get_health())
    print("Current Epoch:", get_epoch())
    print("Active Miners:", len(get_miners()))
```

### Bash Monitoring Script

```bash
#!/bin/bash
# RustChain monitoring script

NODE="https://50.28.86.131"
WALLET="your-wallet-id"

# Check if node is healthy
health=$(curl -sk "$NODE/health" | jq -r '.ok')
if [ "$health" != "true" ]; then
    echo "WARNING: Node unhealthy!"
    exit 1
fi

# Get current epoch
epoch=$(curl -sk "$NODE/epoch" | jq -r '.epoch')
echo "Current epoch: $epoch"

# Get miner count
miners=$(curl -sk "$NODE/api/miners" | jq 'length')
echo "Active miners: $miners"

# Check balance
balance=$(curl -sk "$NODE/wallet/balance?miner_id=$WALLET" | jq -r '.amount_rtc')
echo "Balance: $balance RTC"
```

---

## Explorer

The web explorer is available at:

**http://50.28.86.131/explorer**

Features:
- Real-time miner list with hardware details
- Epoch progress and rewards
- Transaction history
- Network statistics

---

## Changelog

### v2.2.1-rip200 (Current)
- Added RIP-200 consensus (1 CPU = 1 Vote)
- Enhanced hardware fingerprinting
- VM/emulator detection improvements

### v2.1.0
- Initial Proof-of-Antiquity implementation
- Basic wallet and attestation endpoints

---

*Documentation for RustChain v2.2.1-rip200*  
*Last updated: February 2026*
