---
title: "RIP-0305: Bridge API + Lock Ledger (Track C)"
author: RustChain Core Team
status: Draft
created: 2026-03-09
last_updated: 2026-03-09
license: Apache 2.0
track: C
---

# RIP-0305: Bridge API + Lock Ledger (Track C)

## Summary

This RIP defines the **Bridge API** and **Lock Ledger** subsystems for RustChain, enabling secure cross-chain asset transfers with time-locked confirmation semantics. Track C focuses on the core bridge infrastructure: API endpoints for initiating/monitoring bridge transfers, and a lock ledger for tracking locked assets during the bridge confirmation window.

## Abstract

RustChain requires secure cross-chain bridging capabilities to enable RTC token transfers between RustChain and external chains (Solana, Ergo, Base). This specification defines:

1. **Bridge API**: REST endpoints for initiating, querying, and managing bridge transfers
2. **Lock Ledger**: Database schema and logic for tracking locked assets during bridge confirmation windows
3. **Security Model**: Time-lock delays, admin oversight, and void mechanisms for bridge transfers

## Motivation

Current RustChain implementation has a `pending_ledger` for internal transfers but lacks:
- Dedicated bridge transfer tracking
- Cross-chain metadata (destination chain, bridge address, external tx hash)
- Bridge-specific confirmation workflows
- Lock ledger for assets committed to bridge but not yet released

This RIP addresses these gaps with a focused bridge API + lock ledger implementation.

## Specification

### 1. Database Schema

#### 1.1 Bridge Transfers Table

```sql
CREATE TABLE IF NOT EXISTS bridge_transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Core transfer data
    direction TEXT NOT NULL CHECK (direction IN ('deposit', 'withdraw')),
    source_chain TEXT NOT NULL,
    dest_chain TEXT NOT NULL,
    source_address TEXT NOT NULL,
    dest_address TEXT NOT NULL,
    
    -- Amount (stored in micro-units for precision)
    amount_i64 INTEGER NOT NULL CHECK (amount_i64 > 0),
    amount_rtc REAL NOT NULL,
    
    -- Bridge metadata
    bridge_type TEXT NOT NULL DEFAULT 'bottube',
    bridge_fee_i64 INTEGER DEFAULT 0,
    external_tx_hash TEXT,
    external_confirmations INTEGER DEFAULT 0,
    required_confirmations INTEGER DEFAULT 12,
    
    -- State tracking
    status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'locked', 'confirming', 'completed', 'failed', 'voided')),
    lock_epoch INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    expires_at INTEGER,
    completed_at INTEGER,
    
    -- Audit fields
    tx_hash TEXT UNIQUE NOT NULL,
    voided_by TEXT,
    voided_reason TEXT,
    failure_reason TEXT,
    
    -- Optional memo
    memo TEXT
);

CREATE INDEX IF NOT EXISTS idx_bridge_status ON bridge_transfers(status);
CREATE INDEX IF NOT EXISTS idx_bridge_source ON bridge_transfers(source_address);
CREATE INDEX IF NOT EXISTS idx_bridge_dest ON bridge_transfers(dest_address);
CREATE INDEX IF NOT EXISTS idx_bridge_lock_epoch ON bridge_transfers(lock_epoch);
CREATE INDEX IF NOT EXISTS idx_bridge_tx_hash ON bridge_transfers(tx_hash);
```

#### 1.2 Lock Ledger Table

```sql
CREATE TABLE IF NOT EXISTS lock_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Reference to bridge transfer
    bridge_transfer_id INTEGER NOT NULL,
    
    -- Lock metadata
    miner_id TEXT NOT NULL,
    amount_i64 INTEGER NOT NULL CHECK (amount_i64 > 0),
    lock_type TEXT NOT NULL CHECK (lock_type IN ('bridge_deposit', 'bridge_withdraw', 'epoch_settlement')),
    
    -- Timing
    locked_at INTEGER NOT NULL,
    unlock_at INTEGER NOT NULL,
    unlocked_at INTEGER,
    
    -- State
    status TEXT NOT NULL DEFAULT 'locked'
        CHECK (status IN ('locked', 'released', 'forfeited')),
    
    -- Audit
    created_at INTEGER NOT NULL,
    released_by TEXT,
    release_tx_hash TEXT,
    
    FOREIGN KEY (bridge_transfer_id) REFERENCES bridge_transfers(id)
);

CREATE INDEX IF NOT EXISTS idx_lock_miner ON lock_ledger(miner_id);
CREATE INDEX IF NOT EXISTS idx_lock_status ON lock_ledger(status);
CREATE INDEX IF NOT EXISTS idx_lock_unlock_at ON lock_ledger(unlock_at);
```

### 2. Bridge API Endpoints

#### 2.1 Initiate Bridge Transfer

```
POST /api/bridge/initiate
Content-Type: application/json
X-API-Key: <optional>

Request:
{
    "direction": "deposit" | "withdraw",
    "source_chain": "rustchain",
    "dest_chain": "solana" | "ergo" | "base",
    "source_address": "RTC...",
    "dest_address": "<chain-specific address>",
    "amount_rtc": 100.0,
    "memo": "optional memo"
}

Response (200 OK):
{
    "ok": true,
    "bridge_transfer_id": 12345,
    "tx_hash": "abc123...",
    "status": "pending",
    "lock_epoch": 85,
    "unlock_at": 1709942400,
    "estimated_completion": "2026-03-10T12:00:00Z"
}
```

#### 2.2 Query Bridge Transfer Status

```
GET /api/bridge/status/<tx_hash>
GET /api/bridge/status?id=<bridge_transfer_id>

Response (200 OK):
{
    "ok": true,
    "transfer": {
        "id": 12345,
        "direction": "deposit",
        "source_chain": "rustchain",
        "dest_chain": "solana",
        "source_address": "RTC...",
        "dest_address": "4TR...",
        "amount_rtc": 100.0,
        "status": "confirming",
        "external_tx_hash": "5xKj...",
        "external_confirmations": 8,
        "required_confirmations": 12,
        "created_at": 1709856000,
        "estimated_completion": "2026-03-10T12:00:00Z"
    }
}
```

#### 2.3 List Bridge Transfers

```
GET /api/bridge/list?status=pending&limit=50&source_address=RTC...

Response (200 OK):
{
    "ok": true,
    "count": 3,
    "transfers": [...]
}
```

#### 2.4 Lock Ledger Queries

```
GET /api/lock/miner/<miner_id>?status=locked
GET /api/lock/pending-unlock?before=<timestamp>

Response (200 OK):
{
    "ok": true,
    "locks": [
        {
            "id": 789,
            "miner_id": "RTC...",
            "amount_rtc": 50.0,
            "lock_type": "bridge_deposit",
            "locked_at": 1709856000,
            "unlock_at": 1709942400,
            "status": "locked"
        }
    ]
}
```

#### 2.5 Admin: Release Locks

```
POST /api/lock/release
X-Admin-Key: <required>

Request:
{
    "lock_id": 789,
    "release_tx_hash": "optional"
}

Response (200 OK):
{
    "ok": true,
    "released_id": 789,
    "miner_id": "RTC...",
    "amount_rtc": 50.0
}
```

#### 2.6 Admin: Void Bridge Transfer

```
POST /api/bridge/void
X-Admin-Key: <required>

Request:
{
    "tx_hash": "abc123...",
    "reason": "user_request" | "security_hold" | "failed_external"
}

Response (200 OK):
{
    "ok": true,
    "voided_id": 12345,
    "lock_released": true
}
```

### 3. Bridge Workflow

#### 3.1 Deposit Flow (RustChain → External)

```
1. User calls POST /api/bridge/initiate (direction=deposit)
2. System validates:
   - Source address owns sufficient balance
   - Destination address format is valid for target chain
   - Amount exceeds minimum bridge amount
3. System creates bridge_transfers entry with status='pending'
4. System creates lock_ledger entry (locks user's RTC)
5. User receives tx_hash for tracking
6. External bridge service processes transfer
7. Bridge service updates external_tx_hash and confirmations
8. Once confirmations >= required, status='completed'
9. Lock ledger entry is released
```

#### 3.2 Withdraw Flow (External → RustChain)

```
1. User initiates withdraw on external bridge UI
2. External bridge service calls POST /api/bridge/initiate (direction=withdraw)
3. System creates bridge_transfers entry with status='pending'
4. External bridge locks assets on source chain
5. Bridge service updates external_tx_hash
6. RustChain node monitors external confirmations
7. Once confirmed, status='completed'
8. System credits user's RustChain balance
9. Lock ledger entry is released (if created)
```

### 4. Security Model

#### 4.1 Time-Lock Delays

- Bridge deposits: Locked until external chain confirms (default: 12 confirmations)
- Bridge withdrawals: Locked until RustChain confirms (default: 6 slots)
- Maximum lock duration: 7 days (auto-void after expiry)

#### 4.2 Admin Oversight

- Admin key required for:
  - Voiding bridge transfers
  - Releasing locks manually
  - Adjusting confirmation requirements
- All admin actions logged with voided_by/reason

#### 4.3 Void Mechanisms

Bridge transfers can be voided when:
- User requests cancellation (before external confirmation)
- Security hold triggered (suspicious activity)
- External transfer fails permanently
- Lock expires (7-day timeout)

When voided:
- Lock ledger entry is released back to user
- Bridge transfer status set to 'voided'
- Audit trail preserved

### 5. Integration Points

#### 5.1 BoTTube Bridge

Default bridge provider. Integration via:
- Webhook callbacks for external confirmations
- Shared tx_hash for correlation
- Fee calculation and deduction

#### 5.2 Ergo Anchor

For Ergo anchoring (RIP-0001):
- Bridge transfers can reference anchor digest
- Anchor confirmations count toward bridge completion

#### 5.3 Pending Ledger

Bridge transfers are separate from internal pending_ledger:
- Bridge: cross-chain, external confirmations
- Pending: internal transfers, time-delayed confirmation

## Rationale

### Why Separate Bridge and Pending Ledgers?

Bridge transfers have different semantics:
- External chain confirmations required
- Different failure modes (network issues, wrong address)
- Bridge-specific metadata (dest_chain, external_tx_hash)

### Why Lock Ledger?

Lock ledger provides:
- Clear audit trail of locked assets
- Separation from spendable balance
- Support for multiple lock types (bridge, epoch, etc.)

### Time-Lock vs Instant

Time-lock delays:
- Prevent fraud during confirmation window
- Allow admin intervention if issues detected
- Match external chain finality guarantees

## Backwards Compatibility

This RIP is additive:
- New tables: `bridge_transfers`, `lock_ledger`
- New endpoints: `/api/bridge/*`, `/api/lock/*`
- No changes to existing `pending_ledger` behavior

Existing integrations continue to work unchanged.

## Implementation Notes

### Database Migration

```sql
-- Run during node startup or migration
CREATE TABLE IF NOT EXISTS bridge_transfers (...);
CREATE TABLE IF NOT EXISTS lock_ledger (...);
-- Indexes as specified in Section 1
```

### Configuration

Environment variables:
- `RC_BRIDGE_DEFAULT_CONFIRMATIONS`: Default external confirmations (default: 12)
- `RC_BRIDGE_LOCK_EXPIRY_SECONDS`: Max lock duration (default: 604800 = 7 days)
- `RC_BRIDGE_MIN_AMOUNT_RTC`: Minimum bridge amount (default: 1.0)

### Testing

Required test coverage:
- Bridge initiation (deposit/withdraw)
- Status queries (by tx_hash, by id)
- Lock ledger creation/release
- Admin void operations
- Edge cases (insufficient balance, invalid addresses)

## Reference Implementation

See:
- `node/bridge_api.py` - Bridge API endpoints
- `node/lock_ledger.py` - Lock ledger management
- `tests/test_bridge.py` - Bridge API tests
- `tests/test_lock_ledger.py` - Lock ledger tests

---

© 2026 RustChain Core Team — Apache 2.0 License
