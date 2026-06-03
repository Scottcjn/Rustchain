# RustChain Unified API Reference

> **Version:** 2.2.1-rip200
> **Base URL:** `https://rustchain.org`
> **Internal URL:** `http://localhost:8099` (VPS only)
> **Internal Dev:** `http://localhost:5000` (bridge API dev)
> **Internal Node:** `http://localhost:8765` (WebSocket feed)

All public endpoints use HTTPS. For production calls, use strict TLS verification.
For local development with self-signed certificates, use `curl -sk` or `verify=False` in Python.

---

## Table of Contents

- [Authentication](#authentication)
- [1. Network & Status](#1-network--status)
- [2. Miners](#2-miners)
- [3. Wallet](#3-wallet)
- [4. Attestation](#4-attestation)
- [5. Settlement](#5-settlement)
- [6. Bridge (Cross-Chain)](#6-bridge-cross-chain)
- [7. Lock Ledger](#7-lock-ledger)
- [8. WebSocket Feed](#8-websocket-feed)
- [9. Admin Endpoints](#9-admin-endpoints)
- [10. Premium / x402](#10-premium--x402)
- [Error Codes](#error-codes)
- [Rate Limits](#rate-limits)
- [SDK Examples](#sdk-examples)

---

## Authentication

Most endpoints are **public** and require no authentication.

### Admin Endpoints

Require the `X-Admin-Key` header:

```bash
-H "X-Admin-Key: YOUR_ADMIN_KEY"
```

### Bridge Service Callbacks

Use API key authentication:

```bash
-H "X-API-Key: <bridge-api-key>"
```

### Worker Endpoints

Use worker key authentication:

```bash
-H "X-Worker-Key: <worker-key>"
```

### Signed Transfers

Wallet-to-wallet transfers require Ed25519 signatures (no admin key needed, see [POST /wallet/transfer/signed](#post-wallettransfersigned)).

---

## 1. Network & Status

### GET /health

Check node health status.

**Method:** `GET`
**Path:** `/health`
**Auth:** None

**cURL:**
```bash
curl -fsS https://rustchain.org/health | jq .
```

**Response (200 OK):**
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
| `ok` | boolean | Node is healthy |
| `version` | string | Protocol version |
| `uptime_s` | integer | Seconds since node start |
| `db_rw` | boolean | Database read/write capable |
| `backup_age_hours` | float | Hours since last backup |
| `tip_age_slots` | integer | Slots behind tip (0 = synced) |

**Error Codes:** `500 INTERNAL_ERROR` (node unhealthy)

---

### GET /ready

Kubernetes-style readiness probe.

**Method:** `GET`
**Path:** `/ready`
**Auth:** None

**cURL:**
```bash
curl -fsS https://rustchain.org/ready | jq .
```

**Response (200 OK):**
```json
{
  "ready": true
}
```

---

### GET /epoch

Get current epoch and slot information.

**Method:** `GET`
**Path:** `/epoch`
**Auth:** None

**cURL:**
```bash
curl -fsS https://rustchain.org/epoch | jq .
```

**Response (200 OK):**
```json
{
  "epoch": 62,
  "slot": 9010,
  "blocks_per_epoch": 144,
  "epoch_pot": 1.5,
  "enrolled_miners": 2,
  "total_supply_rtc": 8388608
}
```

| Field | Type | Description |
|-------|------|-------------|
| `epoch` | integer | Current epoch number |
| `slot` | integer | Current slot within epoch |
| `blocks_per_epoch` | integer | Slots per epoch (144 = ~24h) |
| `epoch_pot` | float | RTC reward pool for this epoch |
| `enrolled_miners` | integer | Active miners this epoch |
| `total_supply_rtc` | integer | Total RTC supply in circulation |

**Error Codes:** `500 INTERNAL_ERROR`

---

### GET /api/network

Get network-level information including connected peers.

**Method:** `GET`
**Path:** `/api/network`
**Auth:** None

**cURL:**
```bash
curl -fsS https://rustchain.org/api/network | jq .
```

---

### GET /api/peers

List connected network peers.

**Method:** `GET`
**Path:** `/api/peers`
**Auth:** None

**cURL:**
```bash
curl -fsS https://rustchain.org/api/peers | jq .
```

---

## 2. Miners

### GET /api/miners

List all active/enrolled miners with hardware details.

**Method:** `GET`
**Path:** `/api/miners`
**Auth:** None

**cURL:**
```bash
curl -fsS https://rustchain.org/api/miners | jq .
```

**Response (200 OK):**
```json
[
  {
    "miner": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC",
    "device_arch": "G4",
    "device_family": "PowerPC",
    "hardware_type": "PowerPC G4 (Vintage)",
    "antiquity_multiplier": 2.5,
    "entropy_score": 0.0,
    "last_attest": 1770112912
  },
  {
    "miner": "g5-selena-179",
    "device_arch": "G5",
    "device_family": "PowerPC",
    "hardware_type": "PowerPC G5 (Vintage)",
    "antiquity_multiplier": 2.0,
    "entropy_score": 0.0,
    "last_attest": 1770112865
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `miner` | string | Miner wallet ID |
| `device_arch` | string | CPU architecture (G4, G5, x86_64, M2, etc.) |
| `device_family` | string | CPU family (PowerPC, Intel, etc.) |
| `hardware_type` | string | Human-readable hardware description |
| `antiquity_multiplier` | float | Reward multiplier (1.0–2.5x) |
| `entropy_score` | float | Hardware entropy quality |
| `last_attest` | integer | Unix timestamp of last attestation |

**Error Codes:** `500 INTERNAL_ERROR`

---

### GET /api/nodes

List connected attestation nodes.

**Method:** `GET`
**Path:** `/api/nodes`
**Auth:** None

**cURL:**
```bash
curl -fsS https://rustchain.org/api/nodes | jq .
```

**Response (200 OK):**
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

## 3. Wallet

### GET /wallet/balance

Check RTC balance for a miner wallet.

**Method:** `GET`
**Path:** `/wallet/balance`
**Auth:** None

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `miner_id` | string | Yes* | Wallet identifier (canonical) |
| `address` | string | Yes* | Backward-compatible alias for `miner_id` |

*Either `miner_id` or `address` is required.

**cURL:**
```bash
curl -fsS "https://rustchain.org/wallet/balance?miner_id=scott" | jq .
```

**Response (200 OK):**
```json
{
  "ok": true,
  "miner_id": "scott",
  "amount_rtc": 118.357193,
  "amount_i64": 118357193
}
```

**Error Response (404):**
```json
{
  "ok": false,
  "error": "WALLET_NOT_FOUND",
  "miner_id": "unknown"
}
```

---

### GET /wallet/history

Read recent transfer history for a wallet. Public, wallet-scoped.

**Method:** `GET`
**Path:** `/wallet/history`
**Auth:** None

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `miner_id` | string | Yes* | Wallet identifier (canonical) |
| `address` | string | Yes* | Backward-compatible alias |
| `limit` | integer | No | Max records (1–200, default: 50) |

*Either `miner_id` or `address` is required. If both provided, they must match.

**cURL:**
```bash
curl -fsS "https://rustchain.org/wallet/history?miner_id=scott&limit=10" | jq .
```

**Response (200 OK):**
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
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `tx_id` | string | Transaction hash, or `pending_{id}` for pending |
| `from_addr` | string | Sender wallet address |
| `to_addr` | string | Recipient wallet address |
| `amount` | float | Amount in RTC (human-readable) |
| `amount_i64` | integer | Amount in micro-RTC (6 decimals) |
| `timestamp` | integer | Creation Unix timestamp |
| `status` | string | `pending`, `confirmed`, or `failed` |
| `direction` | string | `sent` or `received` |
| `counterparty` | string | Other wallet |
| `memo` | string\|null | Memo from `signed_transfer:` prefix |
| `confirmed_at` | integer\|null | Confirmation timestamp |
| `confirms_at` | integer\|null | Scheduled confirmation time |

**Notes:**
- Ordered by `created_at DESC, id DESC` (newest first)
- Empty array `[]` for wallets with no history (not an error)
- Non-existent wallets return empty array

**Error Responses (400):**
```json
{ "ok": false, "error": "miner_id or address required" }
{ "ok": false, "error": "miner_id and address must match when both are provided" }
{ "ok": false, "error": "limit must be an integer" }
```

---

### POST /wallet/transfer/signed

Transfer RTC to another wallet. Requires Ed25519 signature. No admin key needed — uses cryptographic proof.

**Method:** `POST`
**Path:** `/wallet/transfer/signed`
**Auth:** Ed25519 signature

**cURL:**
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

**Response (200 OK):**
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

**Important:**
- Addresses must be `RTC...` format (43 chars: `RTC` + 40 hex)
- Nonce must be unique per transfer
- Confirmation takes 24 hours

**Error Codes:** `400 INVALID_SIGNATURE`, `400 INSUFFICIENT_BALANCE`, `400 BAD_REQUEST`

---

### GET /wallet/swap-info

Get USDC/wRTC swap guidance (premium x402 endpoint, currently free in beta).

**Method:** `GET`
**Path:** `/wallet/swap-info`
**Auth:** None (x402 payment protocol, free in beta)

**cURL:**
```bash
curl -fsS https://rustchain.org/wallet/swap-info | jq .
```

**Response (200 OK):**
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

### GET /explorer

Web UI for browsing blocks and transactions. Returns HTML.

**Method:** `GET`
**Path:** `/explorer`
**Auth:** None
**Response:** HTML page (block explorer web interface)

---

## 4. Attestation

### POST /attest/submit

Submit hardware fingerprint for epoch enrollment. The attestation validates that the miner is running on genuine physical hardware (not a VM).

**Method:** `POST`
**Path:** `/attest/submit`
**Auth:** Ed25519 signature

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/attest/submit \
  -H "Content-Type: application/json" \
  -d '{
    "miner_id": "your_miner_id",
    "fingerprint": {
      "clock_skew": {"drift_ppm": 24.3, "jitter_ns": 1247},
      "cache_timing": {"l1_latency_ns": 5, "l2_latency_ns": 15},
      "simd_identity": {"instruction_set": "AltiVec", "pipeline_bias": 0.76},
      "thermal_entropy": {"idle_temp_c": 42.1, "load_temp_c": 71.3, "variance": 3.8},
      "instruction_jitter": {"mean_ns": 3200, "stddev_ns": 890},
      "behavioral_heuristics": {"cpuid_clean": true, "no_hypervisor": true}
    },
    "signature": "base64_ed25519_signature"
  }'
```

**Response (Success, 200 OK):**
```json
{
  "success": true,
  "enrolled": true,
  "epoch": 62,
  "multiplier": 2.5,
  "next_settlement_slot": 9216
}
```

**Response (VM Detected, 400):**
```json
{
  "success": false,
  "error": "VM_DETECTED",
  "check_failed": "behavioral_heuristics",
  "detail": "Hypervisor signature detected in CPUID"
}
```

**Response (Hardware Already Bound, 409):**
```json
{
  "error": "HARDWARE_ALREADY_BOUND",
  "existing_miner": "other_wallet"
}
```

---

### GET /lottery/eligibility

Check if a miner is enrolled and eligible in the current epoch.

**Method:** `GET`
**Path:** `/lottery/eligibility`
**Auth:** None

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `miner_id` | string | Yes | Wallet identifier |

**cURL:**
```bash
curl -fsS "https://rustchain.org/lottery/eligibility?miner_id=scott" | jq .
```

**Response (Eligible, 200 OK):**
```json
{
  "eligible": true,
  "reason": null,
  "rotation_size": 27,
  "slot": 13840,
  "slot_producer": "miner_name"
}
```

**Response (Not Eligible, 200 OK):**
```json
{
  "eligible": false,
  "reason": "not_attested",
  "rotation_size": 27,
  "slot": 13839,
  "slot_producer": null
}
```

---

## 5. Settlement

### GET /api/settlement/{epoch}

Query historical settlement data for a specific epoch.

**Method:** `GET`
**Path:** `/api/settlement/{epoch}`
**Auth:** None

**cURL:**
```bash
curl -fsS https://rustchain.org/api/settlement/75 | jq .
```

**Response (200 OK):**
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

**Error Codes:** `404 NOT_FOUND` (epoch not found)

---

## 6. Bridge (Cross-Chain)

The Bridge API manages cross-chain transfers between RustChain and external chains (Solana, Ergo, Base). Follows RIP-0305 Track C.

### POST /api/bridge/initiate

Initiate a cross-chain bridge transfer (deposit or withdraw).

**Method:** `POST`
**Path:** `/api/bridge/initiate`
**Auth:** None (user-initiated)

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/api/bridge/initiate \
  -H "Content-Type: application/json" \
  -d '{
    "direction": "deposit",
    "source_chain": "rustchain",
    "dest_chain": "solana",
    "source_address": "RTC_miner123",
    "dest_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
    "amount_rtc": 100.0,
    "memo": "Cross-chain deposit"
  }'
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `direction` | string | Yes | `deposit` (RTC→external) or `withdraw` (external→RTC) |
| `source_chain` | string | Yes | `rustchain`, `solana`, `ergo`, `base` |
| `dest_chain` | string | Yes | Must differ from source |
| `source_address` | string | Yes | Source wallet address |
| `dest_address` | string | Yes | Destination wallet address |
| `amount_rtc` | number | Yes | Amount in RTC (minimum: 1.0) |
| `memo` | string | No | Optional memo (max 256 chars) |

**Response (200 OK):**
```json
{
  "ok": true,
  "bridge_transfer_id": 12345,
  "tx_hash": "abc123def456...",
  "status": "pending",
  "lock_epoch": 85,
  "unlock_at": 1709942400,
  "estimated_completion": "2026-03-10T12:00:00Z",
  "direction": "deposit",
  "source_chain": "rustchain",
  "dest_chain": "solana",
  "amount_rtc": 100.0
}
```

**Error Responses (400):**
```json
{
  "error": "Insufficient available balance",
  "available_rtc": 50.0,
  "pending_debits_rtc": 20.0,
  "requested_rtc": 100.0
}
```
```json
{
  "error": "Invalid solana address: length must be 32-44 characters"
}
```

---

### GET /api/bridge/status/{tx_hash}

Query status of a bridge transfer.

**Method:** `GET`
**Path:** `/api/bridge/status/{tx_hash}` or `/api/bridge/status?tx_hash=...` or `/api/bridge/status?id=...`
**Auth:** None

**cURL:**
```bash
curl -fsS https://rustchain.org/api/bridge/status/abc123def456 | jq .
```

**Response (200 OK):**
```json
{
  "ok": true,
  "transfer": {
    "id": 12345,
    "direction": "deposit",
    "source_chain": "rustchain",
    "dest_chain": "solana",
    "source_address": "RTC_miner123",
    "dest_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
    "amount_rtc": 100.0,
    "bridge_type": "bottube",
    "external_tx_hash": "5xKjPqR...",
    "external_confirmations": 8,
    "required_confirmations": 12,
    "status": "confirming",
    "lock_epoch": 85,
    "created_at": 1709856000,
    "updated_at": 1709859600,
    "expires_at": 1710460800,
    "tx_hash": "abc123def456...",
    "memo": null
  }
}
```

**Status Values:**

| Status | Description |
|--------|-------------|
| `pending` | Transfer initiated, awaiting lock |
| `locked` | Assets locked, awaiting external confirmation |
| `confirming` | External confirmations in progress |
| `completed` | Transfer completed successfully |
| `failed` | Transfer failed |
| `voided` | Transfer voided by admin/user |

**Error Response (404):**
```json
{ "error": "Bridge transfer not found" }
```

---

### GET /api/bridge/list

List bridge transfers with optional filters.

**Method:** `GET`
**Path:** `/api/bridge/list`
**Auth:** None

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | — | Filter by status |
| `source_address` | string | — | Filter by source address |
| `dest_address` | string | — | Filter by destination address |
| `direction` | string | — | Filter by direction |
| `limit` | integer | 100 | Max results (max: 500) |

**cURL:**
```bash
curl -fsS "https://rustchain.org/api/bridge/list?status=pending&limit=50" | jq .
```

**Response (200 OK):**
```json
{
  "ok": true,
  "count": 3,
  "transfers": [
    {
      "id": 12345,
      "direction": "deposit",
      "source_chain": "rustchain",
      "dest_chain": "solana",
      "amount_rtc": 100.0,
      "status": "confirming"
    }
  ]
}
```

---

### POST /api/bridge/void

Void a pending bridge transfer. **Admin only.**

**Method:** `POST`
**Path:** `/api/bridge/void`
**Auth:** `X-Admin-Key`

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/api/bridge/void \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tx_hash": "abc123def456...",
    "reason": "user_request",
    "voided_by": "admin_john"
  }'
```

**Response (200 OK):**
```json
{
  "ok": true,
  "voided_id": 12345,
  "tx_hash": "abc123def456...",
  "amount_rtc": 100.0,
  "voided_by": "admin_john",
  "reason": "user_request",
  "lock_released": true
}
```

---

### POST /api/bridge/update-external

Update external transaction confirmation data. **Bridge service callback only.**

**Method:** `POST`
**Path:** `/api/bridge/update-external`
**Auth:** `X-API-Key`

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/api/bridge/update-external \
  -H "X-API-Key: BRIDGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tx_hash": "abc123def456...",
    "external_tx_hash": "5xKjPqR...",
    "confirmations": 8,
    "required_confirmations": 12
  }'
```

---

## 7. Lock Ledger

### GET /api/lock/miner/{miner_id}

Get lock ledger entries for a miner.

**Method:** `GET`
**Path:** `/api/lock/miner/{miner_id}`
**Auth:** None

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | — | `locked`, `released`, `forfeited`, or `summary` |
| `limit` | integer | 100 | Max results |

**cURL:**
```bash
curl -fsS "https://rustchain.org/api/lock/miner/RTC_miner123?status=summary" | jq .
```

**Response — Summary (200 OK):**
```json
{
  "miner_id": "RTC_miner123",
  "total_locked_rtc": 150.0,
  "total_locked_count": 3,
  "breakdown": {
    "bridge_deposit": { "amount_rtc": 100.0, "count": 2 },
    "bridge_withdraw": { "amount_rtc": 50.0, "count": 1 }
  },
  "next_unlock": {
    "unlock_at": 1709942400,
    "amount_rtc": 50.0,
    "seconds_until": 86400
  }
}
```

**Response — List (200 OK):**
```json
{
  "ok": true,
  "miner_id": "RTC_miner123",
  "count": 2,
  "locks": [
    {
      "id": 789,
      "amount_rtc": 50.0,
      "lock_type": "bridge_deposit",
      "status": "locked",
      "locked_at": 1709856000,
      "unlock_at": 1709942400,
      "time_until_unlock": 86400
    }
  ]
}
```

---

### GET /api/lock/pending-unlock

Get locks ready to be released.

**Method:** `GET`
**Path:** `/api/lock/pending-unlock`
**Auth:** None

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `before` | integer | — | Unix timestamp filter |
| `limit` | integer | 100 | Max results |

**cURL:**
```bash
curl -fsS "https://rustchain.org/api/lock/pending-unlock?limit=50" | jq .
```

---

### POST /api/lock/release

Manually release a lock. **Admin only.**

**Method:** `POST`
**Path:** `/api/lock/release`
**Auth:** `X-Admin-Key`

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/api/lock/release \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "lock_id": 789,
    "release_tx_hash": "optional_tx_hash"
  }'
```

---

### POST /api/lock/forfeit

Forfeit a lock (penalty/slashing). **Admin only.**

**Method:** `POST`
**Path:** `/api/lock/forfeit`
**Auth:** `X-Admin-Key`

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/api/lock/forfeit \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "lock_id": 789,
    "reason": "penalty"
  }'
```

---

### POST /api/lock/auto-release

Auto-release expired locks. **Worker only.**

**Method:** `POST`
**Path:** `/api/lock/auto-release`
**Auth:** `X-Worker-Key`

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `batch_size` | integer | 100 | Max locks to release per call |

---

## 8. WebSocket Feed

Real-time WebSocket push for the Block Explorer. Connects to the internal WebSocket server (port 8765) via `/ws` or `/socket.io/` (proxied by nginx).

**Endpoint:** `wss://rustchain.org/ws` or `wss://rustchain.org/socket.io/`

### Connection

```javascript
// Native WebSocket
const ws = new WebSocket("wss://rustchain.org/ws");

// Socket.IO (auto-reconnect)
const socket = io("https://rustchain.org", {
  path: "/socket.io/",
  transports: ["websocket"]
});
```

### Client → Server Events

| Event | Payload | Description |
|-------|---------|-------------|
| `connect` | — | Client connects |
| `disconnect` | — | Client disconnects |
| `ping` | — | Heartbeat ping |
| `subscribe` | `{ room: string }` | Subscribe to a room |
| `unsubscribe` | `{ room: string }` | Unsubscribe from a room |
| `request_state` | — | Request current state |
| `request_metrics` | — | Request server metrics |

### Server → Client Events

| Event | Payload | Description |
|-------|---------|-------------|
| `connected` | `{ timestamp, state }` | Welcome message |
| `connection_status` | `{ status, server_version }` | Connection status |
| `block` | `{ height, hash, timestamp, miners_count, reward, epoch, slot }` | New block mined |
| `attestation` | `{ miner_id, device_arch, multiplier, epoch, weight, ticket_id }` | New attestation |
| `epoch_settlement` | `{ epoch, total_blocks, total_reward, miners_count }` | Epoch finalized |
| `miner_update` | `{ miners: [] }` | Miner list updated |
| `epoch_update` | `{ epoch, ... }` | Epoch info updated |
| `health` | `{ ok, service, ... }` | Health status |
| `pong` | `{ timestamp }` | Heartbeat response |

### JavaScript Usage

```javascript
// Check connection state
const state = RustChainWebSocket.getState();
console.log(state.isConnected);

// Listen for events
RustChainWebSocket.on('block', (block) => {
  console.log('New block:', block.height);
});

RustChainWebSocket.on('attestation', (attestation) => {
  console.log('New attestation from:', attestation.miner_id);
});

// Manual connect/disconnect
RustChainWebSocket.disconnect();
RustChainWebSocket.connect();
RustChainWebSocket.requestState();
```

### Performance

- **Latency:** < 100ms for real-time updates
- **Connections:** Supports 1000+ concurrent clients
- **Auto-reconnect:** Exponential backoff with max attempts
- **Fallback:** HTTP polling if WebSocket unavailable

---

## 9. Admin Endpoints

### POST /wallet/transfer

Transfer RTC between wallets. **Admin only.**

**Method:** `POST`
**Path:** `/wallet/transfer`
**Auth:** `X-Admin-Key`

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/wallet/transfer \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "from_miner": "treasury",
    "to_miner": "scott",
    "amount_rtc": 10.0,
    "memo": "Bounty payment #123"
  }'
```

**Response (200 OK):**
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

Manually trigger epoch settlement. **Admin only.**

**Method:** `POST`
**Path:** `/rewards/settle`
**Auth:** `X-Admin-Key`

**cURL:**
```bash
curl -fsS -X POST https://rustchain.org/rewards/settle \
  -H "X-Admin-Key: YOUR_ADMIN_KEY"
```

**Response (200 OK):**
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

## 10. Premium / x402

These endpoints support the x402 payment protocol. Currently **free during beta**.

### GET /api/premium/videos

Bulk video export (BoTTube integration).

**Method:** `GET`
**Path:** `/api/premium/videos` (on `https://bottube.ai`)
**Auth:** x402 (free in beta)

**cURL:**
```bash
curl -fsS https://bottube.ai/api/premium/videos | jq .
```

### GET /api/premium/analytics/{agent}

Deep agent analytics.

**Method:** `GET`
**Path:** `/api/premium/analytics/{agent}` (on `https://bottube.ai`)
**Auth:** x402 (free in beta)

**cURL:**
```bash
curl -fsS https://bottube.ai/api/premium/analytics/scott | jq .
```

### GET /beacon/api/x402/status

Beacon x402 status endpoint.

**cURL:**
```bash
curl -fsS https://rustchain.org/beacon/api/x402/status | jq .
```

### GET /beacon/api/premium/reputation

Beacon reputation export.

**cURL:**
```bash
curl -fsS https://rustchain.org/beacon/api/premium/reputation | jq .
```

### GET /beacon/api/premium/contracts/export

Beacon contracts export.

**cURL:**
```bash
curl -fsS https://rustchain.org/beacon/api/premium/contracts/export | jq .
```

---

## Error Codes

| HTTP Code | Error | Description |
|-----------|-------|-------------|
| 200 | — | Success |
| 400 | `BAD_REQUEST` | Invalid JSON or parameters |
| 400 | `VM_DETECTED` | Hardware fingerprint failed (VM detected) |
| 400 | `INVALID_SIGNATURE` | Ed25519 signature verification failed |
| 400 | `INSUFFICIENT_BALANCE` | Not enough RTC for transfer |
| 401 | `UNAUTHORIZED` | Missing or invalid auth key |
| 404 | `NOT_FOUND` | Endpoint, resource, or miner not found |
| 409 | `HARDWARE_ALREADY_BOUND` | Hardware enrolled to another wallet |
| 429 | `RATE_LIMITED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error |

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/health`, `/ready` | 60/min |
| `/epoch`, `/api/miners`, `/api/nodes` | 30/min |
| `/wallet/balance` | 30/min |
| `/wallet/history` | 30/min |
| `/attest/submit` | 1 per 10 min per miner |
| `/wallet/transfer/signed` | 10/min per wallet |
| Admin endpoints | 10/min |
| Bridge endpoints | 100/min |
| Public endpoints (general) | 100/min |

---

## Bridge Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `RC_BRIDGE_DEFAULT_CONFIRMATIONS` | 12 | External confirmations required |
| `RC_BRIDGE_LOCK_EXPIRY_SECONDS` | 604800 | Max lock duration (7 days) |
| `RC_BRIDGE_MIN_AMOUNT_RTC` | 1.0 | Minimum bridge amount |
| `RC_BRIDGE_API_KEY` | — | API key for bridge callbacks |

---

## SDK Examples

### Python — Quick Start

```python
import requests

BASE_URL = "https://rustchain.org"

# Health check
resp = requests.get(f"{BASE_URL}/health")
data = resp.json()
print(f"Node OK: {data['ok']}, Version: {data['version']}")

# Epoch info
resp = requests.get(f"{BASE_URL}/epoch")
data = resp.json()
print(f"Epoch {data['epoch']}, Slot {data['slot']}/{data['blocks_per_epoch']}")
print(f"Pot: {data['epoch_pot']} RTC, Miners: {data['enrolled_miners']}")

# Wallet balance
resp = requests.get(
    f"{BASE_URL}/wallet/balance",
    params={"miner_id": "scott"},
)
data = resp.json()
print(f"Balance: {data['amount_rtc']} RTC ({data['amount_i64']} micro-RTC)")

# List miners
resp = requests.get(f"{BASE_URL}/api/miners")
for m in resp.json():
    print(f"{m['miner'][:20]}... | {m['device_arch']} | mult={m['antiquity_multiplier']}x")
```

### Python — Signed Transfer

```python
import requests
import json
import nacl.signing
import nacl.encoding
import hashlib

# Load your Ed25519 private key
with open("/path/to/your/agent.key", "rb") as f:
    private_key = nacl.signing.SigningKey(f.read())

# Derive RTC address from public key
public_key_hex = private_key.verify_key.encode().hex()
from_address = "RTC" + hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:40]

# Create canonical message
transfer_msg = {
    "from": from_address,
    "to": "RTC_recipient_address",
    "amount": 100,
    "nonce": "1234567890",
    "memo": "",
    "chain_id": "rustchain-mainnet-v2"
}

# Sign
message = json.dumps(transfer_msg, sort_keys=True, separators=(",", ":")).encode()
signed = private_key.sign(message)
signature_hex = signed.signature.hex()

# Build outer payload
payload = {
    "from_address": from_address,
    "to_address": "RTC_recipient_address",
    "amount_rtc": 100,
    "nonce": "1234567890",
    "memo": "",
    "chain_id": "rustchain-mainnet-v2",
    "public_key": public_key_hex,
    "signature": signature_hex
}

# Send
resp = requests.post(
    f"{BASE_URL}/wallet/transfer/signed",
    json=payload,
)
print(resp.json())
```

### Python — Bridge Deposit

```python
def initiate_bridge_deposit(miner_id, dest_address, amount_rtc):
    """Initiate a bridge deposit from RustChain to Solana."""
    resp = requests.post(
        f"{BASE_URL}/api/bridge/initiate",
        json={
            "direction": "deposit",
            "source_chain": "rustchain",
            "dest_chain": "solana",
            "source_address": miner_id,
            "dest_address": dest_address,
            "amount_rtc": amount_rtc,
        }
    )
    result = resp.json()
    if resp.status_code == 200:
        print(f"Bridge initiated: {result['tx_hash']}")
        print(f"Status: {result['status']}")
        return result
    else:
        print(f"Error: {result}")
        return None

result = initiate_bridge_deposit(
    miner_id="RTC_miner123",
    dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
    amount_rtc=100.0
)
```

### Python — Error Handling

```python
import requests

try:
    resp = requests.get(
        f"{BASE_URL}/wallet/balance",
        params={"miner_id": "nonexistent"},
        timeout=5
    )
    if resp.status_code == 200:
        print(resp.json())
    else:
        print(f"Error {resp.status_code}: {resp.text}")
except requests.exceptions.Timeout:
    print("Request timed out — node may be overloaded")
except requests.exceptions.ConnectionError:
    print("Connection failed — node may be offline")
```

### JavaScript — Quick Start

```javascript
const BASE_URL = "https://rustchain.org";

async function getBalance(minerId) {
  const resp = await fetch(`${BASE_URL}/wallet/balance?miner_id=${minerId}`);
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

### Bash — Quick Start

```bash
#!/bin/bash
BASE_URL="https://rustchain.org"

# Health
curl -fsS "$BASE_URL/health" | jq .

# Balance
get_balance() {
  curl -fsS "$BASE_URL/wallet/balance?miner_id=$1" | jq .
}
get_balance "scott"

# Epoch
get_epoch() {
  curl -fsS "$BASE_URL/epoch" | jq .
}
get_epoch
```

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
| `miner_id` (in miners response) | `miner` |
| `multiplier` | `antiquity_multiplier` |
| `last_attestation` | `last_attest` |

---

## HTTPS Certificate

The public hostname `https://rustchain.org` uses a browser-trusted certificate.
For local development or raw-IP diagnostics with self-signed certificates:

```bash
# Option 1: Skip verification (development only)
curl -sk https://rustchain.org/health

# Option 2: Trust certificate
openssl s_client -connect rustchain.org:443 -showcerts < /dev/null 2>/dev/null | \
  openssl x509 -outform PEM > rustchain.pem
curl --cacert rustchain.pem https://rustchain.org/health
```

**Python:**
```python
# Production — use strict verification
requests.get(url)  # default: verify=True

# Local development only
requests.get(url, verify=False)
```

---

## Related Resources

- [RustChain GitHub](https://github.com/Scottcjn/Rustchain)
- [Bounties](https://github.com/Scottcjn/rustchain-bounties)
- [RIP-0305 Bridge Specification](../rips/docs/RIP-0305-bridge-lock-ledger.md)
- [Bridge Integration Guide](../contracts/erc20/docs/BRIDGE_INTEGRATION.md)
- [Block Explorer](https://rustchain.org/explorer)
- [BoTTube Bridge](https://bottube.ai/bridge)
