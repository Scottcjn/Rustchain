# RustChain API Reference

Base URL: `https://50.28.86.131`

All endpoints use HTTPS. Self-signed certificates require `-k` flag with curl.

---

## Health & Status

### `GET /health`

Check node status and version.

**Request:**
```bash
curl -sk https://50.28.86.131/health | jq .
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
curl -sk https://50.28.86.131/epoch | jq .
```

**Response:**
```json
{
  "blocks_per_epoch": 144,
  "enrolled_miners": 2,
  "epoch": 62,
  "epoch_pot": 1.5,
  "slot": 9010
}
```

| Field | Type | Description |
|-------|------|-------------|
| `epoch` | integer | Current epoch number |
| `slot` | integer | Current slot within epoch |
| `blocks_per_epoch` | integer | Slots per epoch (144 = ~24h) |
| `epoch_pot` | float | RTC to distribute this epoch |
| `enrolled_miners` | integer | Miners eligible for rewards |

---

## Miners

### `GET /api/miners`

List all active/enrolled miners.

**Request:**
```bash
curl -sk https://50.28.86.131/api/miners | jq .
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

**Request:**
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC" | jq .
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

### `POST /wallet/transfer/signed`

Transfer RTC to another wallet. Requires Ed25519 signature.

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

**Response (Success):**
```json
{
  "success": true,
  "tx_hash": "abc123...",
  "new_balance": 117357193
}
```

---

## Attestation

### `POST /attest/submit`

Submit hardware fingerprint for epoch enrollment.

**Request:**
```bash
curl -sk -X POST https://50.28.86.131/attest/submit \
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
