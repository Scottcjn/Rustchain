# 📚 RustChain Comprehensive API Reference

**Official endpoint documentation for RustChain v2.2.1-rip200**

> **Base URL**: `https://50.28.86.131`  
> **Internal URL**: `http://localhost:8099` (on VPS)  
> **Certificate**: Self-signed (use `-k` with curl)

---

## 🔍 Quick Start

### Health Check
```bash
curl -sk https://50.28.86.131/health | jq .
```

### Get Current Epoch
```bash
curl -sk https://50.28.86.131/epoch | jq .
```

### List All Miners
```bash
curl -sk https://50.28.86.131/api/miners | jq .
```

### Check Wallet Balance
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=your_miner_id" | jq .
```

---

## 🏥 Health & Status Endpoints

### `GET /health`
Node health check and version information.

**Response Example:**
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
| `ok` | boolean | Node is healthy and operational |
| `version` | string | Protocol version (format: `major.minor.patch-tag`) |
| `uptime_s` | integer | Seconds since node started |
| `db_rw` | boolean | Database is readable and writable |
| `backup_age_hours` | float | Hours since last database backup |
| `tip_age_slots` | integer | Slots behind chain tip (0 = fully synced) |

---

### `GET /ready`
Readiness probe for Kubernetes/container orchestration.

**Response:** Same structure as `/health` but focuses on service readiness.

**Use Case:** Load balancer health checks, container startup probes.

---

## 📊 Epoch & Chain Information

### `GET /epoch`
Current epoch details and mining statistics.

**Response Example:**
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
| `epoch` | integer | Current epoch number (resets every ~24h) |
| `slot` | integer | Current slot within epoch (144 slots = 1 epoch) |
| `blocks_per_epoch` | integer | Total slots per epoch (144 = 24 hours) |
| `epoch_pot` | float | RTC available for distribution this epoch |
| `enrolled_miners` | integer | Number of miners eligible for rewards |

---

### `GET /api/stats`
Comprehensive blockchain statistics.

**Response Example:**
```json
{
  "chain_id": "rustchain-mainnet-v2",
  "version": "2.2.1-security-hardened",
  "epoch": 75,
  "block_time": 600,
  "total_miners": 11614,
  "total_balance": 5213.41835243,
  "pending_withdrawals": 0,
  "features": ["RIP-0005", "RIP-0008", "RIP-0009", "RIP-0142", "RIP-0143", "RIP-0144"],
  "security": ["no_mock_sigs", "mandatory_admin_key", "replay_protection", "validated_json"]
}
```

---

## 👥 Miner Registry

### `GET /api/miners`
List all active miners with hardware details.

**Response Example:**
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
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `miner` | string | Unique miner ID (wallet address format) |
| `device_family` | string | CPU family (`PowerPC`, `x86_64`, `Apple Silicon`) |
| `device_arch` | string | Specific architecture (`G4`, `G5`, `M2`, `modern`) |
| `hardware_type` | string | Human-readable hardware description |
| `antiquity_multiplier` | float | Reward multiplier (1.0-2.5x based on hardware age) |
| `entropy_score` | float | Hardware entropy contribution quality |
| `last_attest` | integer | Unix timestamp of last successful attestation |
| `first_attest` | integer/null | Unix timestamp of first attestation (null if unknown) |

**Antiquity Multiplier Guide:**
- **Vintage Hardware** (PowerPC G4/G5): 2.0-2.5x
- **Classic Hardware** (Intel Core 2, early AMD): 1.5x  
- **Modern Hardware** (x86-64, Apple Silicon): 0.8x
- **Virtual Machines**: Rejected (multiplier = 0)

---

### `GET /api/nodes`
Connected attestation nodes in the network.

**Response:** List of node addresses and connection status.

---

## 💰 Wallet Operations

### `GET /wallet/balance`
Check RTC balance for a specific miner.

**Query Parameters:**
- `miner_id` (required): Miner/wallet identifier

**Request:**
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=scott" | jq .
```

**Response:**
```json
{
  "ok": true,
  "miner_id": "scott",
  "amount_rtc": 42.5,
  "amount_i64": 4250000000
}
```

| Field | Type | Description |
|-------|------|-------------|
| `miner_id` | string | Requested miner identifier |
| `amount_rtc` | float | Balance in RTC (human readable, 6 decimal places) |
| `amount_i64` | integer | Balance in micro-RTC (raw integer for precision) |

---

### `POST /wallet/transfer` (Admin Only)
Internal RTC transfer between wallets.

**Headers Required:**
- `X-Admin-Key: rustchain_admin_key_2025_secure64`
- `Content-Type: application/json`

**Request Body:**
```json
{
  "from_miner": "scott",
  "to_miner": "pffs1802", 
  "amount_rtc": 5.0
}
```

**Response (Success):**
```json
{
  "success": true,
  "tx_hash": "9e75c9b8e67c87d9fb898aa8891f83a6",
  "from_balance": 37.5,
  "to_balance": 47.5
}
```

---

## 🎯 Attestation Endpoints

### `POST /attest/submit`
Submit hardware fingerprint for epoch enrollment.

**Request Body:**
```json
{
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
}
```

**Response (Success):**
```json
{
  "success": true,
  "enrolled": true,
  "epoch": 75,
  "multiplier": 2.5,
  "next_settlement_slot": 11088
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

### `GET /lottery/eligibility`
Check reward eligibility for a miner.

**Query Parameters:**
- `miner_id` (required): Miner identifier

**Response:**
```json
{
  "eligible": true,
  "reason": "Valid vintage hardware",
  "multiplier": 2.5,
  "next_eligible_epoch": 76
}
```

---

## 🌐 Web Interface

### `GET /explorer`
Web-based block explorer UI.

**Access:** Open `https://50.28.86.131/explorer` in browser

**Features:**
- Block browsing
- Transaction lookup  
- Miner statistics
- Network visualization

---

## 🔒 Authenticated Endpoints

All admin endpoints require the `X-Admin-Key` header:

```bash
-H "X-Admin-Key: rustchain_admin_key_2025_secure64"
```

### Available Admin Endpoints:
- `POST /wallet/transfer` - Internal transfers
- `POST /rewards/settle` - Trigger epoch settlement  
- `POST /admin/miner/disable` - Disable problematic miners
- `GET /admin/logs` - Access node logs

---

## ⚠️ Common Mistakes & Troubleshooting

### ❌ Wrong Endpoints (Don't Use These)
| Incorrect | Correct |
|-----------|---------|
| `/balance/{address}` | `/wallet/balance?miner_id=NAME` |
| `/miners?limit=N` | `/api/miners` (no pagination) |
| `/block/{height}` | Use `/explorer` web UI |
| `/tx/{txid}` | Use `/explorer` web UI |
| `/blocks` | Check `/epoch` for block info |
| `/api/balance` | Use `/wallet/balance?miner_id=...` |

### ❌ Wrong Field Names
**Epoch Response - CORRECT:**
```json
{
  "epoch": 75,
  "slot": 10800,
  "blocks_per_epoch": 144,
  "epoch_pot": 1.5,
  "enrolled_miners": 10
}
```

**NOT:**
- `epoch_number` → use `epoch`
- `current_slot` → use `slot`  
- `per_epoch_pot` → use `epoch_pot`
- `total_miners` → use `enrolled_miners`

**Miner Object - CORRECT:**
```json
{
  "miner": "wallet_id",
  "device_arch": "G4",
  "device_family": "PowerPC", 
  "antiquity_multiplier": 2.5,
  "last_attest": 1771187406
}
```

**NOT:**
- `miner_id` → use `miner`
- `architecture` → use `device_arch`
- `multiplier` → use `antiquity_multiplier`
- `last_attestation` → use `last_attest`

---

## 💳 Wallet Format Rules

**Valid Wallet Names:**
- ✅ `scott`
- ✅ `pffs1802`  
- ✅ `liu971227-sys`
- ✅ `my-wallet-2025`
- ✅ `sophia-nas-c4130`

**Invalid Wallet Names (Will Be Rejected):**
- ❌ Solana addresses: `4TRdr...`
- ❌ Ethereum addresses: `0x2A91...`
- ❌ Ed25519 public keys: `88c394...`
- ❌ Bitcoin addresses: `1A1z...`

Wallet identifiers are simple UTF-8 strings (1-256 characters).

---

## 🔐 HTTPS Certificate Handling

The node uses a self-signed certificate. Always use the `-k` flag with curl:

```bash
# ✅ Correct
curl -sk https://50.28.86.131/health

# To verify the certificate manually:
openssl s_client -connect 50.28.86.131:443 -showcerts
```

For production integrations, pin the certificate fingerprint:

```bash
# Get certificate fingerprint
openssl s_client -connect 50.28.86.131:443 < /dev/null 2>/dev/null | openssl x509 -fingerprint -sha256 -noout
```

---

## 📈 Response Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| `200` | ✅ Success | Process response normally |
| `400` | ❌ Bad Request | Check JSON syntax and required fields |
| `401` | ❌ Unauthorized | Missing or invalid `X-Admin-Key` |
| `404` | ❌ Not Found | Endpoint doesn't exist |
| `500` | ❌ Server Error | Check node logs, retry later |

---

## 🏢 Node Infrastructure

### Primary Node (RIP-200 Consensus)
- **Address**: `50.28.86.131` (LiquidWeb VPS)
- **HTTPS Port**: 443 (nginx proxy)
- **Internal Port**: 8099 (Flask app)
- **Version**: 2.2.1-rip200

### Secondary Node (Ergo Anchor)
- **Address**: `50.28.86.153` (LiquidWeb VPS)
- **Note**: Serves different services, not mirrored

### Tertiary Node (Community)
- **Address**: `76.8.228.245` (Ryan's Proxmox)
- **Tailscale**: `100.88.109.32:8099`
- **Status**: Community-operated

---

## 🛠️ For Contributors & Integrators

When submitting RustChain integration code:

1. **Always test endpoints first** using the examples above
2. **Use exact field names** from response JSON
3. **Handle HTTP 401 errors gracefully** (node may restart)
4. **Don't hardcode IP addresses** – use documented URLs
5. **Reference issue #213** in your PR if adding new API usage

**Miner Integration Guide**: [Wiki Link](https://github.com/Scottcjn/Rustchain/wiki/Miner-Integration)

---

## 📅 Last Updated
**Date**: 2026-02-16  
**Epoch**: 75  
**Active Miners**: 10  
**Epoch Pot**: 1.5 RTC

*This documentation covers RustChain v2.2.1-rip200. Check the [GitHub repository](https://github.com/Scottcjn/Rustchain) for updates.*

---

## 🎁 Bounty Information
**Issue**: [#213](https://github.com/Scottcjn/Rustchain/issues/213)  
**Reward**: 75 RTC  
**Status**: Ready for review