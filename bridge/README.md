# RIP-305 Track C: Bridge API

Cross-chain bridge endpoints for wRTC (Wrapped RTC) on Solana + Base L2.

Part of [RIP-305: Cross-Chain Airdrop Protocol](../../docs/RIP-305-cross-chain-airdrop.md).

## Overview

Phase 1 bridge: admin-controlled mint/burn with explicit proof confirmation (upgrades to trustless lock in Phase 2).

### Architecture

```
User / Agent
    │
    ▼
POST /bridge/lock   ─── lock_id,state=requested/confirmed ──▶ Admin confirms proof if needed
                                                           │
                                               POST /bridge/confirm
                                                           │
                                               Solana: spl-token mint-to
                                               Base:   ERC-20.mint()
                                                           │
                                                           ▼
                                             POST /bridge/release  (with release_tx)
                                        │
                                        ▼
                          GET /bridge/status/<lock_id>
                               state: "complete"
```

## Endpoints

### `POST /bridge/lock`

Lock RTC and request wRTC mint on a target chain.

**Request:**
```json
{
  "sender_wallet": "my-rtc-wallet",
  "amount": 100.0,
  "target_chain": "solana",
  "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
  "tx_hash": "rustchain-lock-tx-hash",
  "receipt_signature": "optional-hmac-sha256-receipt"
}
```

**Response (201):**
```json
{
  "lock_id": "lock_6752ac1dc0140e90a2852eab",
  "state": "requested",
  "amount_rtc": 100.0,
  "target_chain": "solana",
  "target_wallet": "7xKXtg2CW87d...",
  "tx_hash": "rustchain-lock-tx-hash",
  "proof_type": "tx_hash_review",
  "expires_at": 1741680000,
  "message": "Lock requested. Admin will only mint 100.0 wRTC on solana to 7xKXtg2CW87... after proof confirmation."
}
```

**Validations:**
- `target_chain`: must be `"solana"` or `"base"`
- `amount`: min 1 RTC, max 10,000 RTC
- Base wallet: must start with `0x`
- Solana wallet: must be ≥32 chars (base58)
- `tx_hash`: required for every lock request
- Locks expire after 24h
- Duplicate `tx_hash` values are rejected

**Proof modes:**
- `tx_hash_review`: default Phase 1 mode. Creates a `requested` lock that must be confirmed by an admin before release.
- `signed_receipt`: if `BRIDGE_RECEIPT_SECRET` is configured and `receipt_signature` is valid, the lock is created directly as `confirmed`.

---

### `POST /bridge/confirm` _(admin only)_

Confirm a requested lock after independent proof review.

**Headers:** `X-Admin-Key: <admin-key>`

**Request:**
```json
{
  "lock_id": "lock_6752ac1dc0140e90a2852eab",
  "proof_ref": "manual-review:explorer-proof-or-receipt-id",
  "notes": "optional proof review notes"
}
```

**Response (200):**
```json
{
  "lock_id": "lock_6752ac1dc0140e90a2852eab",
  "state": "confirmed",
  "proof_ref": "manual-review:explorer-proof-or-receipt-id",
  "message": "Lock confirmed and eligible for release"
}
```

---

### `POST /bridge/release` _(admin only)_

Mark a confirmed lock as released after minting wRTC on target chain.

**Headers:** `X-Admin-Key: <admin-key>`

**Request:**
```json
{
  "lock_id": "lock_6752ac1dc0140e90a2852eab",
  "release_tx": "0xabc123...",
  "notes": "optional admin notes"
}
```

**Response (200):**
```json
{
  "lock_id": "lock_6752ac1dc0140e90a2852eab",
  "state": "complete",
  "release_tx": "0xabc123..."
}
```

---

### `GET /bridge/ledger`

Query the transparent lock ledger.

**Query params:**
| Param | Description |
|-------|-------------|
| `state` | Filter: `requested`, `pending`, `confirmed`, `complete`, `failed` |
| `chain` | Filter: `solana`, `base` |
| `sender` | Filter by sender wallet |
| `limit` | Max results (default 50, max 200) |
| `offset` | Pagination offset |

**Response:**
```json
{
  "locks": [...],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

---

### `GET /bridge/status/<lock_id>`

Get full status + event history for a lock.

**Response:**
```json
{
  "lock_id": "lock_...",
  "state": "complete",
  "amount_rtc": 100.0,
  "target_chain": "solana",
  "release_tx": "...",
  "events": [
    {"type": "lock_created", "actor": "my-wallet", "ts": 1741593600, "details": {...}},
    {"type": "released", "actor": "admin", "ts": 1741594000, "details": {...}}
  ]
}
```

---

### `GET /bridge/stats`

Bridge-wide statistics.

```json
{
  "by_state": {
    "pending":   {"count": 3,  "total_rtc": 150.0},
    "complete":  {"count": 12, "total_rtc": 800.0},
    ...
  },
  "by_chain": {
    "solana": {"bridged_count": 7, "total_wrtc_minted": 400.0},
    "base":   {"bridged_count": 5, "total_wrtc_minted": 400.0}
  },
  "all_time": {"total_locks": 15, "total_rtc_locked": 950.0}
}
```

## Integration with Main Node

```python
# In integrated_node.py or wsgi.py:
from bridge.bridge_api import register_bridge_routes

# After creating your Flask app:
register_bridge_routes(app)
```

## SPL Token Integration (Track A)

The `/bridge/lock` endpoint now creates either:
- a `requested` lock that must be proof-confirmed by admin
- a directly `confirmed` lock if a valid signed receipt is supplied

Admin then calls:
```bash
# Solana: mint wRTC to target wallet
spl-token mint <WRTC_MINT_ADDRESS> <AMOUNT> <TARGET_WALLET>
# Then POST /bridge/release with the Solana tx signature
```

## ERC-20 Integration (Track B)

```bash
# Base: mint wRTC ERC-20 to target wallet
cast send <WRTC_CONTRACT> "mint(address,uint256)" <TARGET_WALLET> <AMOUNT>
# Then POST /bridge/release with the Base tx hash
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BRIDGE_DB_PATH` | SQLite DB path | `bridge_ledger.db` |
| `BRIDGE_ADMIN_KEY` | Admin API key (required) | _(empty)_ |
| `BRIDGE_RECEIPT_SECRET` | Optional HMAC secret for signed lock receipts | _(empty)_ |

## Tests

```bash
pip install flask pytest
python3 -m pytest bridge/test_bridge_api.py -v
# 14 tests pass
```

## Lock States

```
requested → confirmed → releasing → complete
                ↓                        ↑
              failed                 refunded
```

| State | Description |
|-------|-------------|
| `pending` | Lock received, awaiting confirmation |
| `confirmed` | Confirmed on RustChain ledger |
| `releasing` | Admin is minting wRTC |
| `complete` | wRTC minted on target chain |
| `failed` | Lock failed |
| `refunded` | RTC refunded to sender |

---

## RIP-305 Track D: Airdrop API

The airdrop API provides GitHub-based eligibility checking and wRTC claim management for the RIP-305 cross-chain airdrop.

### Integration with Flask App

```python
from bridge import register_bridge_routes, register_airdrop_routes

# Register both bridge (Track C) and airdrop (Track D) routes:
register_bridge_routes(app)
register_airdrop_routes(app)
```

### Endpoints

#### `GET /airdrop/eligibility`

Check GitHub-based eligibility and tier.

**Query params:**
| Param | Description |
|-------|-------------|
| `github_token` | GitHub OAuth token |
| `code` | GitHub OAuth code (alternative to token) |
| `rustchain_wallet` | RustChain wallet name |

**Response:**
```json
{
  "eligible": true,
  "github_username": "contributor",
  "tier": "contributor",
  "base_amount": 50,
  "requirement": "1+ merged PRs",
  "allocations": {
    "solana": 30000,
    "base": 20000,
    "remaining_solana": 29950,
    "remaining_base": 20000
  },
  "already_claimed": false,
  "previous_claims": []
}
```

**Anti-Sybil:** Accounts < 30 days old are rejected with `github_account_too_new`.

#### `POST /airdrop/claim`

Submit a wRTC airdrop claim.

**Body:**
```json
{
  "github_token": "oauth_token",
  "rustchain_wallet": "my-rtc-wallet",
  "target_chain": "base",
  "target_address": "0xABC..."
}
```

**Response (201):**
```json
{
  "claim_id": "claim_a1b2c3d4e5f6...",
  "state": "pending",
  "github_username": "contributor",
  "tier": "contributor",
  "base_amount": 50,
  "final_amount": 50.0,
  "target_chain": "base",
  "target_address": "0xABC...",
  "message": "Claim submitted! ..."
}
```

**Anti-Sybil checks:**
- GitHub account age > 30 days
- One claim per GitHub account (no duplicate claims)
- One claim per RustChain wallet (no wallet recycling)

#### `GET /airdrop/status/<claim_id>`

Get full claim status + event history.

#### `GET /airdrop/wallet/<wallet>`

Get all claims for a RustChain wallet.

#### `GET /airdrop/leaderboard`

Top claimants by tier. Query params: `limit` (default 20, max 100), `tier` (filter).

#### `GET /airdrop/stats`

Overall airdrop statistics: total claims, wRTC distributed, allocations remaining, breakdown by tier and chain.

#### `POST /airdrop/process` _(admin only)_

Mark a pending claim as complete after wRTC minting.

**Headers:** `X-Admin-Key: <admin-key>`

```json
{"claim_id": "claim_...", "tx_hash": "0xMintTx...", "notes": "optional"}
```

#### `POST /airdrop/reject` _(admin only)_

Reject a pending claim. Body: `{"claim_id": "...", "reason": "..."}`.

### Airdrop Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AIRDROP_DB_PATH` | SQLite DB path | `airdrop_ledger.db` |
| `AIRDROP_ADMIN_KEY` | Admin API key | _(empty)_ |
| `GITHUB_CLIENT_ID` | GitHub OAuth app client ID | _(empty)_ |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth app client secret | _(empty)_ |

### Airdrop Tests

```bash
python -m pytest bridge/test_airdrop_api.py -v
```

### Eligibility Tiers

| Tier | Requirement | Base wRTC |
|------|-------------|-----------|
| Stargazer | 10+ Scottcjn repos starred | 25 |
| Contributor | 1+ merged PRs | 50 |
| Builder | 3+ merged PRs | 100 |
| Security | Verified vulnerability | 150 |
| Core | 5+ merged PRs / Star King | 200 |
| Miner | Active attestation history | 100 |
