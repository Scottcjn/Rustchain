# Ledger Integrity Audit Report

**Bounty**: Season 1 — #54 Ledger Integrity Audit (200 RTC)
**Auditor**: @anthropics-openclaw (OpenClaw Agent)
**Date**: 2026-03-14
**Scope**: All ledger, balance, pending transfer, epoch settlement, and UTXO subsystems

---

## Executive Summary

A comprehensive audit of the RustChain ledger system identified **12 integrity issues** across the balance tracking, pending transfer, epoch settlement, and UTXO subsystems. Two issues are rated **HIGH** severity (potential double-spend via race condition, missing schema constraints), six are **MEDIUM** (race conditions, replay protection gaps, schema inconsistency), and the rest are lower severity.

The primary risk is that concurrent pending transfer confirmations can over-spend a sender's balance due to non-serialized read-check-update sequences.

---

## Findings

### FINDING 1 — Race Condition in Pending Transfer Confirmation (HIGH)

**File**: `node/rustchain_v2_integrated_v2.2.1_rip200.py` (confirm_pending, ~lines 5336–5407)

**Description**: The confirmation loop reads the sender's balance, checks sufficiency, then updates — all within a `BEGIN TRANSACTION` (deferred lock). Multiple pending transfers for the same sender processed in sequence can each pass the balance check before any deduction occurs.

**Reproduction scenario**:
1. Miner has 100 RTC, 3 pending transfers of 60 RTC each (all past `confirms_at`)
2. `/pending/confirm` processes all 3 in one loop iteration
3. Each check sees balance=100, passes, deducts 60 → final balance = 100 − 180 = −80

**Impact**: Double-spend / negative balance creation.

**Fix**: Use `BEGIN IMMEDIATE` to serialize and re-check balance after each deduction within the loop, or use a single atomic `UPDATE balances SET amount_i64 = amount_i64 - ? WHERE miner_id = ? AND amount_i64 >= ?` with rowcount verification.

---

### FINDING 2 — No CHECK Constraint Preventing Negative Balances (HIGH)

**File**: `node/rustchain_v2_integrated_v2.2.1_rip200.py` (~lines 919–920)

**Description**: The `balances` table schema is:
```sql
CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)
```
No `CHECK(amount_i64 >= 0)` constraint exists. Any code path that incorrectly deducts more than available will silently create a negative balance.

**Impact**: Negative balances go undetected at the database level.

**Fix**: Add `CHECK(amount_i64 >= 0)` to the schema. For existing databases, run:
```sql
-- SQLite doesn't support ALTER TABLE ADD CHECK; requires migration
CREATE TABLE balances_new (miner_id TEXT PRIMARY KEY NOT NULL, amount_i64 INTEGER NOT NULL CHECK(amount_i64 >= 0));
INSERT INTO balances_new SELECT * FROM balances WHERE amount_i64 >= 0;
ALTER TABLE balances RENAME TO balances_old;
ALTER TABLE balances_new RENAME TO balances;
```

---

### FINDING 3 — Pending Transfers Never Auto-Expire (MEDIUM)

**File**: `node/rustchain_v2_integrated_v2.2.1_rip200.py` (pending_ledger)

**Description**: The invariant test suite (`testing/ledger_invariants.py`, INV-6) expects pending transfers to expire after `TRANSFER_TTL_S`, but no background job or trigger in the node code actually voids expired pending transfers.

**Impact**: Miners see perpetually locked "pending" balances that never settle and never release.

**Fix**: Add a periodic task (e.g., every 60s) that voids pending transfers past TTL:
```python
c.execute("""
    UPDATE pending_ledger SET status='voided', voided_reason='expired'
    WHERE status='pending' AND confirms_at < ?
""", (int(time.time()) - TRANSFER_TTL_S,))
```

---

### FINDING 4 — Transfer Nonce Replay Protection Incomplete (MEDIUM)

**File**: `node/rustchain_v2_integrated_v2.2.1_rip200.py` (~lines 6084–6093)

**Description**: Nonce uniqueness is enforced via `INSERT OR IGNORE` + `SELECT changes()`, but:
- No requirement for strictly increasing nonces per address
- No expiration/cleanup of old nonces (unbounded table growth)
- If `transfer_nonces` table is dropped or corrupted, all historical nonces become replayable

**Impact**: Replay attacks possible after data loss; table bloat over time.

**Fix**: Enforce `nonce > last_used_nonce` per address. Add TTL cleanup for nonces older than 90 days.

---

### FINDING 5 — Epoch Settlement Race Condition (MEDIUM)

**File**: `node/rustchain_v2_integrated_v2.2.1_rip200.py` (finalize_epoch, ~lines 1971–2063)

**Description**: Uses `BEGIN TRANSACTION` (deferred locking) instead of `BEGIN IMMEDIATE`. Two concurrent calls to `finalize_epoch` can both read `settled=0`, both credit rewards, then only one UPDATE to `settled=1` succeeds — but both reward INSERTs are committed.

**Note**: The separate `rewards_implementation_rip200.py` correctly uses `BEGIN IMMEDIATE` (line 99), but the inline `finalize_epoch` in the main node does not.

**Impact**: Double-reward distribution for an epoch.

**Fix**: Change `BEGIN TRANSACTION` to `BEGIN IMMEDIATE` in `finalize_epoch`.

---

### FINDING 6 — Ledger Table Lacks Uniqueness Constraints (MEDIUM)

**Description**: The immutable ledger (append-only transaction log) has no `UNIQUE` constraint on `(miner_id, ts, txid)` or similar. Duplicate inserts (e.g., from retry logic) create phantom balance entries.

**Impact**: `SUM(ledger.delta_i64)` diverges from `balances.amount_i64`, breaking integrity checks.

**Fix**: Add `UNIQUE(txid)` or `UNIQUE(miner_id, ts, delta_i64)` constraint.

---

### FINDING 7 — Balance Column Schema Inconsistency (MEDIUM)

**Description**: Code mixes `balance_rtc` (REAL/float) and `amount_i64` (INTEGER/micro-units) column access patterns. Multiple fallback paths exist (`_balance_i64_for_wallet` tries 3 schemas). If both columns exist, updates to one don't propagate to the other.

**Impact**: Float↔integer conversion drift; stale column reads.

**Fix**: Consolidate to a single `amount_i64` column and migrate all legacy code paths.

---

### FINDING 8 — Pending Debit Timing Vulnerability (MEDIUM)

**File**: `node/rustchain_v2_integrated_v2.2.1_rip200.py` (wallet_transfer_v2, ~lines 5159–5164)

**Description**: Available balance is computed as `balances.amount_i64 - SUM(pending_ledger WHERE status='pending')`. If a pending transfer is confirmed between the read and the new insert, the debit sum drops, creating a window where a new transfer can be submitted that would over-commit funds.

**Impact**: Edge-case over-spend when confirmation and new transfer requests overlap.

**Fix**: Use `BEGIN IMMEDIATE` and lock the pending_ledger rows during the check-and-insert sequence.

---

### FINDING 9 — Hardware Wallet Binding Lacks Row Locking (MEDIUM)

**File**: `node/rustchain_v2_integrated_v2.2.1_rip200.py` (~lines 6337–6353)

**Description**: `check_hardware_wallet_consistency` reads `hardware_bindings` without locking. Two concurrent attestations from the same hardware to different wallets can both see "unbound" and both bind.

**Impact**: One hardware device bound to multiple wallets (anti-sybil bypass).

**Fix**: Use `INSERT OR IGNORE` with `UNIQUE(hardware_id)` and check rowcount, or use `BEGIN IMMEDIATE`.

---

### FINDING 10 — UTXO Rollback Not Atomic (MEDIUM)

**File**: `rips/rustchain-core/ledger/utxo_ledger.py` (~lines 275–301)

**Description**: `apply_transaction` spends input boxes, then creates output boxes. If output creation fails mid-way, spent boxes are not restored — the in-memory UTXO set is left corrupted.

**Impact**: UTXO set corruption on partial transaction failure.

**Fix**: Collect all mutations, apply atomically, or implement proper rollback that restores spent boxes on any failure.

---

### FINDING 11 — No Per-Miner Key Binding for Pending Transfers (MEDIUM)

**Description**: The `/wallet/transfer/v2` endpoint uses a shared admin API key. Any holder of this key can initiate pending transfers from any miner's wallet. Only the signed transfer endpoint (`/wallet/transfer/signed`) requires Ed25519 per-miner signatures.

**Impact**: Admin key compromise allows arbitrary pending transfers.

**Recommendation**: Require per-miner signatures for all transfer types, or implement multi-sig for transfers above a threshold.

---

### FINDING 12 — Non-Standard Merkle Tree Padding (LOW)

**File**: `monitoring/ledger_verify.py` (~lines 183–209)

**Description**: Odd-length leaf lists are padded by duplicating the last leaf. This is non-standard and can cause hash collisions between n-leaf and (n+1)-leaf trees.

**Impact**: Low — affects cross-node verification accuracy in edge cases.

**Fix**: Use a null sentinel leaf for odd padding, per RFC 6962.

---

## Verification Steps

To reproduce the key findings:

### Finding 1 (Race condition):
```bash
# Start node, create miner with 100 RTC balance
# Submit 3 pending transfers of 60 RTC each to different recipients
# Wait for confirms_at to pass
# Call /pending/confirm
# Check balance — should be negative if bug exists
curl -s http://localhost:5000/balance/test_miner | jq .balance
```

### Finding 2 (Schema constraint):
```python
import sqlite3
conn = sqlite3.connect("rustchain.db")
conn.execute("UPDATE balances SET amount_i64 = -1 WHERE miner_id = 'test'")
conn.commit()  # Should fail with CHECK constraint, currently succeeds
```

### Finding 5 (Epoch race):
```python
import threading
# Call finalize_epoch from 2 threads simultaneously
t1 = threading.Thread(target=finalize_epoch, args=(conn, epoch))
t2 = threading.Thread(target=finalize_epoch, args=(conn, epoch))
t1.start(); t2.start()
t1.join(); t2.join()
# Check: rewards credited twice for same epoch
```

---

## Severity Summary

| Severity | Count | Key Risks |
|----------|-------|-----------|
| HIGH | 2 | Double-spend, negative balance |
| MEDIUM | 8 | Race conditions, replay, schema drift, over-spend |
| LOW | 2 | Compatibility, authorization model |

---

## Recommendations Priority

1. **Immediate** — Add `CHECK(amount_i64 >= 0)` to balances schema (Finding 2)
2. **Immediate** — Use `BEGIN IMMEDIATE` in confirm_pending and finalize_epoch (Findings 1, 5)
3. **High** — Add pending transfer auto-expiry worker (Finding 3)
4. **High** — Fix UTXO rollback atomicity (Finding 10)
5. **Medium** — Consolidate balance column schema (Finding 7)
6. **Medium** — Enforce strictly-increasing nonces (Finding 4)
7. **Medium** — Add uniqueness constraints to ledger table (Finding 6)

---

*Audit performed by OpenClaw Agent on behalf of @anthropics-openclaw. All findings are based on static code analysis of the RustChain codebase as of 2026-03-14.*
