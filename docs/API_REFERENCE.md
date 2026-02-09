# RustChain API Reference

Complete API documentation for RustChain nodes with examples and response schemas.

**Base URL**: `https://50.28.86.131`  
**Version**: 2.2.1-rip200  
**Protocol**: HTTPS (self-signed certificate)

> **Note**: Use `-k` or `--insecure` flag with curl due to self-signed SSL certificate.

---

## Table of Contents

- [Authentication](#authentication)
- [Health & Status](#health--status)
- [Chain Information](#chain-information)
- [Miner Operations](#miner-operations)
- [Wallet Operations](#wallet-operations)
- [Attestation](#attestation)
- [Error Codes](#error-codes)

---

## Authentication

Most read operations require no authentication. Write operations (transfers, attestations) require Ed25519 cryptographic signatures.

**Signature Format**:
```
message = from_address + to_address + amount_rtc + nonce
signature = Ed25519_sign(message, private_key)
```

---

## Health & Status

### GET /health

Check node health and connectivity.

**Request**:
```bash
curl -sk https://50.28.86.131/health
```

**Response** (200 OK):
```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 97300,
  "db_rw": true,
  "tip_age_slots": 0,
  "backup_age_hours": 16.59
}
```

**Fields**:
- `ok` (boolean) - Overall health status
- `version` (string) - Node software version
- `uptime_s` (integer) - Seconds since node start
- `db_rw` (boolean) - Database read/write status
- `tip_age_slots` (integer) - Age of chain tip in slots (0 = synced)
- `backup_age_hours` (float) - Hours since last database backup

---

### GET /epoch

Get current epoch information.

**Request**:
```bash
curl -sk https://50.28.86.131/epoch
```

**Response** (200 OK):
```json
{
  "epoch": 61,
  "slot": 8784,
  "pot_rtc": 1.5,
  "enrolled_miners": 47,
  "block_time": 600,
  "next_settlement_in": 3600
}
```

**Fields**:
- `epoch` (integer) - Current epoch number
- `slot` (integer) - Current blockchain slot
- `pot_rtc` (float) - RTC available for distribution this epoch
- `enrolled_miners` (integer) - Number of miners enrolled in current epoch
- `block_time` (integer) - Seconds per block (600 = 10 minutes)
- `next_settlement_in` (integer) - Seconds until epoch settlement

---

## Chain Information

### GET /api/stats

Get comprehensive blockchain statistics.

**Request**:
```bash
curl -sk https://50.28.86.131/api/stats
```

**Response** (200 OK):
```json
{
  "chain_id": "rustchain-mainnet-v2",
  "version": "2.2.1-security-hardened",
  "epoch": 61,
  "block_time": 600,
  "total_miners": 11614,
  "total_balance": 5213.41835243,
  "pending_withdrawals": 0,
  "features": [
    "RIP-0005",
    "RIP-0008",
    "RIP-0009",
    "RIP-0142",
    "RIP-0143",
    "RIP-0144",
    "RIP-0200"
  ],
  "security": [
    "no_mock_sigs",
    "mandatory_admin_key",
    "replay_protection"
  ]
}
```

**Fields**:
- `chain_id` (string) - Network identifier
- `version` (string) - Node version with feature flags
- `epoch` (integer) - Current epoch
- `block_time` (integer) - Block time in seconds
- `total_miners` (integer) - Total registered miners
- `total_balance` (float) - Total RTC in circulation
- `pending_withdrawals` (integer) - Pending withdrawal count
- `features` (array) - Active RIP features
- `security` (array) - Security features enabled

---

## Miner Operations

### GET /api/miners

List all active miners with hardware information.

**Request**:
```bash
curl -sk https://50.28.86.131/api/miners
```

**Optional Query Parameters**:
- `limit` (integer) - Max results (default: 100)
- `offset` (integer) - Pagination offset (default: 0)
- `sort` (string) - Sort by: `multiplier`, `last_seen`, `balance` (default: `last_seen`)

**Example with parameters**:
```bash
curl -sk "https://50.28.86.131/api/miners?limit=10&sort=multiplier"
```

**Response** (200 OK):
```json
{
  "miners": [
    {
      "miner_id": "powerbook_g4_1.5ghz_RTC",
      "hardware": {
        "cpu_model": "PowerPC G4 1.5GHz",
        "architecture": "ppc",
        "release_year": 2005,
        "tier": "Vintage"
      },
      "multiplier": 2.5,
      "balance_rtc": 12.456789,
      "last_attestation": "2026-02-09T14:23:45Z",
      "enrolled_epochs": 45,
      "fingerprint_valid": true
    },
    {
      "miner_id": "ryzen_5_8645hs_RTC",
      "hardware": {
        "cpu_model": "AMD Ryzen 5 8645HS",
        "architecture": "x86_64",
        "release_year": 2024,
        "tier": "Modern"
      },
      "multiplier": 1.0,
      "balance_rtc": 8.123456,
      "last_attestation": "2026-02-09T14:20:12Z",
      "enrolled_epochs": 32,
      "fingerprint_valid": true
    }
  ],
  "total": 11614,
  "limit": 100,
  "offset": 0
}
```

**Miner Object Fields**:
- `miner_id` (string) - Unique miner identifier
- `hardware` (object) - Hardware specifications
  - `cpu_model` (string) - CPU model name
  - `architecture` (string) - CPU architecture (ppc, x86_64, arm64, etc.)
  - `release_year` (integer) - Hardware release year
  - `tier` (string) - Antiquity tier (Ancient, Sacred, Vintage, Classic, Retro, Modern, Recent)
- `multiplier` (float) - Current mining multiplier (0.5x - 2.5x)
- `balance_rtc` (float) - Current RTC balance
- `last_attestation` (string) - ISO 8601 timestamp of last attestation
- `enrolled_epochs` (integer) - Total epochs participated
- `fingerprint_valid` (boolean) - Hardware fingerprint validation status

---

### GET /api/miner/{miner_id}

Get detailed information for a specific miner.

**Request**:
```bash
curl -sk https://50.28.86.131/api/miner/powerbook_g4_1.5ghz_RTC
```

**Response** (200 OK):
```json
{
  "miner_id": "powerbook_g4_1.5ghz_RTC",
  "hardware": {
    "cpu_model": "PowerPC G4 1.5GHz",
    "architecture": "ppc",
    "release_year": 2005,
    "tier": "Vintage",
    "serial": "W8543XXXXXX",
    "fingerprint": {
      "clock_skew": {"drift_ppm": 12.5, "jitter_ns": 847},
      "cache_timing": {"l1_latency_ns": 4, "l2_latency_ns": 12},
      "simd_identity": {"instruction_set": "AltiVec", "pipeline_bias": 0.73},
      "thermal_entropy": {"idle_temp": 38.2, "load_temp": 67.8},
      "instruction_jitter": {"mean_ns": 2.3, "stddev_ns": 0.8},
      "behavioral_heuristics": {"cpuid_clean": true, "no_hypervisor": true}
    }
  },
  "multiplier": 2.5,
  "balance_rtc": 12.456789,
  "balance_urtc": 12456789,
  "last_attestation": "2026-02-09T14:23:45Z",
  "enrolled_epochs": 45,
  "total_earned_rtc": 67.89,
  "fingerprint_valid": true,
  "attestation_valid_until": 1739112225
}
```

**Response** (404 Not Found):
```json
{
  "error": "MINER_NOT_FOUND",
  "message": "Miner ID not found in registry"
}
```

---

## Wallet Operations

### GET /wallet/balance

Check wallet balance.

**Query Parameters**:
- `miner_id` (required) - Wallet/miner identifier

**Request**:
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=powerbook_g4_1.5ghz_RTC"
```

**Response** (200 OK):
```json
{
  "miner_id": "powerbook_g4_1.5ghz_RTC",
  "balance_rtc": 12.456789,
  "balance_urtc": 12456789,
  "last_updated": "2026-02-09T14:23:45Z"
}
```

**Fields**:
- `miner_id` (string) - Wallet identifier
- `balance_rtc` (float) - Balance in RTC (1 RTC = 1,000,000 micro-RTC)
- `balance_urtc` (integer) - Balance in micro-RTC (smallest unit)
- `last_updated` (string) - ISO 8601 timestamp of last balance update

**Response** (404 Not Found):
```json
{
  "error": "WALLET_NOT_FOUND",
  "balance_rtc": 0.0,
  "balance_urtc": 0
}
```

---

### POST /wallet/transfer/signed

Submit a signed RTC transfer.

**Request Body**:
```json
{
  "from_address": "abc123...RTC",
  "to_address": "def456...RTC",
  "amount_rtc": 5.0,
  "nonce": 1739112225,
  "signature": "base64_encoded_ed25519_signature",
  "public_key": "base64_encoded_ed25519_public_key"
}
```

**Request Example**:
```bash
curl -sk https://50.28.86.131/wallet/transfer/signed \
  -H "Content-Type: application/json" \
  -d '{
    "from_address": "powerbook_g4_1.5ghz_RTC",
    "to_address": "ryzen_5_8645hs_RTC",
    "amount_rtc": 5.0,
    "nonce": 1739112225,
    "signature": "SGVsbG8gV29ybGQh...",
    "public_key": "RWQyNTUxOSBwdWJsaWMga2V5..."
  }'
```

**Response** (200 OK):
```json
{
  "ok": true,
  "tx_hash": "a1b2c3d4e5f6...",
  "from_address": "powerbook_g4_1.5ghz_RTC",
  "to_address": "ryzen_5_8645hs_RTC",
  "amount_rtc": 5.0,
  "new_balance_rtc": 7.456789,
  "timestamp": "2026-02-09T14:30:00Z"
}
```

**Response** (400 Bad Request):
```json
{
  "error": "INSUFFICIENT_BALANCE",
  "message": "Balance 3.5 RTC is less than transfer amount 5.0 RTC"
}
```

**Response** (401 Unauthorized):
```json
{
  "error": "INVALID_SIGNATURE",
  "message": "Ed25519 signature verification failed"
}
```

**Response** (409 Conflict):
```json
{
  "error": "NONCE_REUSED",
  "message": "Nonce 1739112225 has already been used (replay protection)"
}
```

**Signature Generation** (Python example):
```python
from nacl.signing import SigningKey
import base64

# Create signing key from seed
signing_key = SigningKey.generate()

# Message to sign
message = f"{from_address}{to_address}{amount_rtc}{nonce}"

# Sign message
signature = signing_key.sign(message.encode())

# Encode for API
signature_b64 = base64.b64encode(signature.signature).decode()
public_key_b64 = base64.b64encode(signing_key.verify_key.encode()).decode()
```

---

## Attestation

### POST /attest/submit

Submit hardware fingerprint for epoch enrollment.

**Request Body**:
```json
{
  "miner_id": "powerbook_g4_1.5ghz_RTC",
  "timestamp": 1739112225,
  "hardware": {
    "cpu_model": "PowerPC G4 1.5GHz",
    "architecture": "ppc",
    "release_year": 2005,
    "serial": "W8543XXXXXX"
  },
  "fingerprint": {
    "clock_skew": {"drift_ppm": 12.5, "jitter_ns": 847},
    "cache_timing": {"l1_latency_ns": 4, "l2_latency_ns": 12},
    "simd_identity": {"instruction_set": "AltiVec", "pipeline_bias": 0.73},
    "thermal_entropy": {"idle_temp": 38.2, "load_temp": 67.8, "variance": 4.2},
    "instruction_jitter": {"mean_ns": 2.3, "stddev_ns": 0.8},
    "behavioral_heuristics": {
      "cpuid_clean": true,
      "mac_oui_valid": true,
      "no_hypervisor": true
    }
  },
  "signature": "base64_encoded_ed25519_signature"
}
```

**Request Example**:
```bash
curl -sk https://50.28.86.131/attest/submit \
  -H "Content-Type: application/json" \
  -d @attestation.json
```

**Response** (200 OK):
```json
{
  "ok": true,
  "enrolled": true,
  "miner_id": "powerbook_g4_1.5ghz_RTC",
  "multiplier": 2.5,
  "epoch": 61,
  "fingerprint_valid": true,
  "attestation_valid_until": 1739198625,
  "checks_passed": {
    "clock_skew": true,
    "cache_timing": true,
    "simd_identity": true,
    "thermal_entropy": true,
    "instruction_jitter": true,
    "behavioral_heuristics": true
  }
}
```

**Response** (403 Forbidden - VM Detected):
```json
{
  "error": "VM_DETECTED",
  "message": "Hardware fingerprint indicates virtual machine or emulator",
  "failed_checks": ["thermal_entropy", "behavioral_heuristics"],
  "multiplier": 0.0000000025
}
```

**Response** (409 Conflict - Hardware Bound to Different Wallet):
```json
{
  "error": "HARDWARE_BOUND",
  "message": "Hardware serial W8543XXXXXX is already bound to wallet xyz789RTC"
}
```

---

### POST /attest/challenge

Request attestation challenge for hardware proof.

**Request Body**:
```json
{
  "miner_id": "powerbook_g4_1.5ghz_RTC"
}
```

**Request Example**:
```bash
curl -sk https://50.28.86.131/attest/challenge \
  -H "Content-Type: application/json" \
  -d '{"miner_id": "powerbook_g4_1.5ghz_RTC"}'
```

**Response** (200 OK):
```json
{
  "challenge": "a1b2c3d4e5f6...",
  "challenge_type": "timing",
  "expires_at": 1739112525,
  "instructions": "Execute challenge code and return timing results within 5 minutes"
}
```

---

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `MINER_NOT_FOUND` | 404 | Miner ID not found in registry |
| `WALLET_NOT_FOUND` | 404 | Wallet has no balance record |
| `INSUFFICIENT_BALANCE` | 400 | Balance too low for transfer |
| `INVALID_SIGNATURE` | 401 | Ed25519 signature verification failed |
| `NONCE_REUSED` | 409 | Nonce already used (replay protection) |
| `VM_DETECTED` | 403 | Hardware fingerprint indicates VM/emulator |
| `HARDWARE_BOUND` | 409 | Hardware already bound to different wallet |
| `INVALID_FINGERPRINT` | 400 | Fingerprint data malformed or incomplete |
| `EPOCH_FULL` | 429 | Epoch enrollment limit reached |
| `RATE_LIMITED` | 429 | Too many requests from IP |
| `DB_ERROR` | 500 | Database operation failed |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## Rate Limits

- **Read operations**: 100 requests/minute per IP
- **Write operations**: 10 requests/minute per IP
- **Attestation submissions**: 1 per epoch per miner

---

## Additional Resources

- **OpenAPI Specification**: `docs/api/openapi.yaml`
- **Protocol Documentation**: `docs/PROTOCOL.md`
- **Miner Setup Guide**: `docs/MINER_SETUP_GUIDE.md`
- **Node Operator Guide**: `docs/NODE_OPERATOR_GUIDE.md`

---

**Last Updated**: February 9, 2026  
**API Version**: 2.2.1-rip200
