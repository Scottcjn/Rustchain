# Epoch Settlement Security Report
## Red Team Assessment — Bounty #56

**Target:** RustChain Epoch Settlement System (RIP-200)  
**Files Audited:**
- `node/rewards_implementation_rip200.py`
- `node/claims_settlement.py`
- `node/settle_epoch.py`

**Severity Summary:** 1 Critical · 2 High · 2 Medium · 1 Low  
**Researcher:** @B1tor  
**RTC Wallet:** `RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`

---

## Finding #1 — CRITICAL: Race Condition in `settle_epoch_rip200()`

**File:** `node/rewards_implementation_rip200.py`  
**Lines:** ~136–155  
**CVSS v3:** 9.0 (AV:N/AC:H/PR:N/UI:N/S:C/C:N/I:H/A:H)

### Description

`settle_epoch_rip200()` correctly acquires a SQLite `BEGIN IMMEDIATE` transaction to serialize concurrent settlement attempts. However, when `ANTI_DOUBLE_MINING_AVAILABLE=True` (the default production path), it delegates to `settle_epoch_with_anti_double_mining()` at line ~150 **before writing the `epoch_state.settled=1` flag** and **using a brand-new database connection** (it receives `db_path` as a string, not the locked `db` handle).

```python
# settle_epoch_rip200() — holds the IMMEDIATE lock on `db`
db.execute("BEGIN IMMEDIATE")                    # lock acquired on `db`
...
if enable_anti_double_mining and ANTI_DOUBLE_MINING_AVAILABLE:
    result = settle_epoch_with_anti_double_mining(
        db_path if isinstance(db_path, str) else DB_PATH,  # NEW connection!
        epoch, PER_EPOCH_URTC, current
    )
    return result   # <-- returns WITHOUT committing settled=1 on the locked `db`
```

The callee opens a **separate** SQLite connection. SQLite `BEGIN IMMEDIATE` only blocks other writers on the *same connection's transaction scope*; a second connection with its own `BEGIN IMMEDIATE` can race in. Two concurrent HTTP requests to `/rewards/settle` with the same epoch can both:

1. Pass the `already_settled` guard (settled flag not yet written)
2. Both call `settle_epoch_with_anti_double_mining()`
3. Both credit miners — **doubling the epoch payout**

### Proof of Concept

See `security/epoch-poc/settlement_race_poc.py` — `demo_race_condition()`.

### Remediation

```python
# Option A: Pass the live `db` handle, not db_path, to the anti-double-mining function
result = settle_epoch_with_anti_double_mining(db, epoch, PER_EPOCH_URTC, current)

# Option B: Mark epoch settled BEFORE delegating
db.execute(
    "INSERT OR REPLACE INTO epoch_state (epoch, settled, settled_ts) VALUES (?, 1, ?)",
    (epoch, int(time.time()))
)
db.commit()   # release lock, epoch marked
# now call the anti-double-mining path
```

Option A is preferred — it keeps the write inside a single atomic transaction.

---

## Finding #2 — HIGH: No Authentication on `/rewards/settle`

**File:** `node/rewards_implementation_rip200.py`  
**Lines:** ~253–265

### Description

The `POST /rewards/settle` endpoint accepts an arbitrary `{"epoch": N}` JSON body with **zero authentication or authorization**. Any network-reachable client can trigger settlement for any epoch number.

```python
@app.route('/rewards/settle', methods=['POST'])
def settle_rewards():
    data = request.json or {}
    epoch = data.get('epoch')          # fully attacker-controlled
    ...
    result = settle_epoch_rip200(DB_PATH, epoch)
    return jsonify(result)
```

This allows:
- **Unauthorized settlement** of arbitrary epochs by external actors
- **Denial of service** — settling epochs prematurely prevents legitimate re-settlement
- Combined with Finding #1, an attacker can trigger the race from outside the network boundary

### Proof of Concept

```bash
curl -X POST http://node:8099/rewards/settle \
     -H 'Content-Type: application/json' \
     -d '{"epoch": 42}'
```

No token, no signature, no IP allowlist — succeeds immediately.

### Remediation

- Require a pre-shared bearer token or HMAC-signed request header
- Restrict endpoint to localhost / admin network via reverse-proxy ACL
- Add rate limiting and audit logging

```python
ADMIN_TOKEN = os.environ["SETTLEMENT_ADMIN_TOKEN"]

@app.route('/rewards/settle', methods=['POST'])
def settle_rewards():
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {ADMIN_TOKEN}":
        abort(403)
    ...
```

---

## Finding #3 — HIGH: Auto-Approve Verification Timeout in `claims_settlement.py`

**File:** `node/claims_settlement.py`  
**Lines:** ~105–130, ~270–290

### Description

`get_verifying_claims()` fetches all claims with `status='verifying'` that have been waiting longer than `older_than_seconds` (default: `max_wait_seconds // 2 = 900 s`). These are merged **without additional verification** with the `approved` claim pool and processed in the same settlement batch:

```python
old_verifying = get_verifying_claims(db_path, max_wait_seconds // 2)

# Combine and deduplicate — verifying treated as approved
all_claims = pending_claims + old_verifying
...
claims_to_process = unique_claims[:max_claims]
```

A claim stuck in `verifying` (e.g., due to a verifier crash, network partition, or deliberate stalling) is silently promoted to `approved` and paid out after a timeout. There is no re-verification step, no flag in the output, and no alert.

An attacker who can stall verification (e.g., by flooding a verifier node) can cause fraudulent claims to be auto-approved and settled.

### Remediation

- Separate auto-approved-by-timeout claims from legitimately approved claims in the settlement logic
- Emit an alert / audit log entry for each timeout auto-approval
- Require explicit admin confirmation before paying out timed-out claims, or at minimum tag them in the database for review

```python
# Mark auto-approved timeout claims separately
for claim in old_verifying:
    update_claim_status(db_path, claim["claim_id"], "timeout_approved",
                        {"auto_approved": True, "reason": "verification_timeout"})
    # Do NOT include in settlement without human review
```

---

## Finding #4 — MEDIUM: Future Epoch Settlement

**File:** `node/rewards_implementation_rip200.py`  
**Lines:** ~253–265

### Description

The `epoch` parameter from the request body is passed directly to `settle_epoch_rip200()` with no validation against the current blockchain time. An attacker (or any caller) can settle an epoch that has not yet ended:

```python
epoch = data.get('epoch')     # e.g., current_epoch + 9999
result = settle_epoch_rip200(DB_PATH, epoch)
```

This distributes rewards for a future epoch based on whatever miner data currently exists in the database — potentially rewarding miners who will later become ineligible, or locking the epoch before legitimate participants join.

### Proof of Concept

```python
# Settle an epoch 1000 blocks in the future
requests.post("http://node:8099/rewards/settle", json={"epoch": current_epoch + 1000})
```

### Remediation

```python
current_epoch = slot_to_epoch(current_slot())
if epoch >= current_epoch:
    return jsonify({"ok": False, "error": "cannot_settle_future_epoch"}), 400
```

---

## Finding #5 — MEDIUM: 10% Random Failure in Production Transaction Broadcast

**File:** `node/claims_settlement.py`  
**Lines:** ~185–205

### Description

`sign_and_broadcast_transaction()` contains a hard-coded 10% random failure rate with **no retry logic**:

```python
# Simulate success (90% success rate for testing)
import random
if random.random() < 0.9:
    tx_hash = "0x" + "".join(random.choices("0123456789abcdef", k=64))
    return True, tx_hash, None
else:
    return False, None, "Simulated transaction failure"
```

This is a **testing stub left in production code**. On failure, the entire batch is marked `failed` with `retry_scheduled=True` — but no retry is actually scheduled anywhere in the codebase. Affected claims remain in a failed state indefinitely, blocking legitimate reward payouts.

Additionally, the "transaction hash" returned is cryptographically meaningless random hex — not a real chain transaction. There is no actual signing or broadcasting taking place.

### Remediation

- Remove the `random.random()` stub entirely before any mainnet deployment
- Implement actual transaction signing with the treasury key
- Add exponential backoff retry with a maximum attempt count
- Fail loudly (page on-call) rather than silently

---

## Finding #6 — LOW: Integer Overflow Potential in Balance Accumulation

**File:** `node/rewards_implementation_rip200.py`  
**Lines:** ~180–181

### Description

Miner balances are accumulated using SQLite's `ON CONFLICT DO UPDATE SET amount_i64 = amount_i64 + ?` with no upper bound:

```sql
INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)
ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = amount_i64 + ?
```

SQLite stores integers as up to 8-byte signed (max: 9,223,372,036,854,775,807 µRTC ≈ 92 billion RTC). While this is extremely large, combining the race condition (Finding #1) with repeated double-settlements could cause this value to grow faster than expected. Python's `int` type is unbounded, but values stored in SQLite are silently truncated or raise an `OverflowError` that rolls back the transaction.

### Remediation

- Add a per-miner balance cap in the application layer
- Add a constraint or trigger in the DB schema to enforce the cap
- Monitor total `SUM(amount_i64)` against expected epoch distribution totals

---

## Attack Chain Summary

The most dangerous combined attack path:

1. **No auth** (Finding #2) → attacker can reach `/rewards/settle` from anywhere
2. **Race condition** (Finding #1) → two concurrent requests double-credit miners
3. **Future epoch** (Finding #4) → attacker settles epochs not yet earned
4. **Timeout auto-approve** (Finding #3) → fraudulent claims pass verification via stall
5. **10% failure / fake TX** (Finding #5) → legitimate settlements randomly fail while fraudulent ones may succeed

---

## Timeline

| Date | Event |
|------|-------|
| 2026-03-28 | Audit conducted, findings documented |
| 2026-03-28 | Report submitted via PR to Scottcjn/rustchain-bounties |

---

*Submitted for Bounty #56 (150 RTC) by @B1tor*  
*Wallet: `RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`*
