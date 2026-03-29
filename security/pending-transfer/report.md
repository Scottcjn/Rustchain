# Security Red Team Report: Pending Transfer Exploits

**Bounty:** #59 — Pending Transfer Edge Cases (150 RTC)
**Auditor:** LaphoqueRC
**Date:** 2026-03-28
**Scope:** `node/rustchain_tx_handler.py` — pending transaction lifecycle
**Severity Scale:** Critical / High / Medium / Low / Info

---

## Executive Summary

Audit of RustChain's pending transfer system revealed **1 Critical, 2 High, 2 Medium** severity findings. The critical issue is a double-spend via concurrent pending submissions exploiting the non-atomic validate+insert path. High-severity findings include stuck pending transactions with no timeout enforcement and a balance underflow during confirmation.

---

## Findings

### C1 — Double-Spend via Concurrent Pending Submission

**Severity:** Critical
**File:** `node/rustchain_tx_handler.py`, `validate_transaction()` + `submit_transaction()`
**CVSS:** 9.0

**Description:**
`validate_transaction()` and `submit_transaction()` are not atomic. The flow is:
1. `validate_transaction()` — checks balance, nonce, signature (read-only)
2. `submit_transaction()` — calls validate then INSERT

Between step 1's balance check and step 2's INSERT, another thread can submit a transaction spending the same funds. Both pass validation because neither sees the other's pending entry yet.

```python
def submit_transaction(self, tx):
    is_valid, error = self.validate_transaction(tx)  # Check
    if not is_valid:
        return False, error
    # ... TOCTOU WINDOW HERE ...
    cursor.execute("INSERT INTO pending_transactions ...")  # Use
```

**Impact:** Double-spend. Two transactions spending the full balance both enter the pending pool. When confirmed, the second confirmation either creates funds from nothing or fails silently.

**Remediation:** Use `BEGIN EXCLUSIVE` to hold a write lock during validate+insert:
```python
with self._get_connection() as conn:
    conn.execute("BEGIN EXCLUSIVE")
    is_valid, error = self._validate_under_lock(conn, tx)
    if is_valid:
        conn.execute("INSERT INTO pending_transactions ...")
    conn.commit()
```

---

### H1 — No Pending Transaction Timeout Enforcement

**Severity:** High
**File:** `node/rustchain_tx_handler.py`

**Description:**
Pending transactions have a `created_at` timestamp but no mechanism to expire them. A transaction can sit in `status='pending'` indefinitely, blocking the sender's nonce sequence and balance.

If a transaction enters the pending pool but is never confirmed (e.g., the block producer skips it), the sender's balance is permanently locked. There's no:
- Periodic cleanup job
- TTL on pending entries
- User-initiated cancellation
- Automatic nonce gap recovery

**Impact:** Permanent fund lockup. An attacker can submit a transaction with a high nonce gap, blocking all subsequent transactions from that address.

**Remediation:**
1. Add a `expires_at` column: `created_at + TTL (e.g., 3600 seconds)`
2. Periodic sweep: `DELETE FROM pending_transactions WHERE expires_at < NOW() AND status = 'pending'`
3. Allow nonce gap recovery: if a pending tx expires, subsequent nonces should become valid

---

### H2 — Balance Underflow on Concurrent Confirmation

**Severity:** High
**File:** `node/rustchain_tx_handler.py`, `confirm_transaction()`

**Description:**
`confirm_transaction()` updates the sender's balance by subtracting the transaction amount. If two transactions from the same sender are confirmed concurrently (e.g., in the same block), the second confirmation may underflow the balance:

```python
# Pseudo-code of the issue
balance = get_balance(sender)  # 1000
# Thread 1: confirm tx1 (500 RTC) → balance = 500
# Thread 2: confirm tx2 (800 RTC) → balance = 500 - 800 = -300
```

SQLite doesn't enforce unsigned integers, so the balance goes negative. The validation was done at submission time when both transactions saw 1000 RTC available, but by confirmation time the math doesn't add up.

**Impact:** Negative balances, funds created from nothing.

**Remediation:** Add a `CHECK(balance >= 0)` constraint and wrap confirmation in exclusive transaction with re-validation.

---

### M1 — Pending Pool DoS via Mass Submissions

**Severity:** Medium
**File:** `node/rustchain_tx_handler.py`, `submit_transaction()`

**Description:**
There's no per-address limit on pending transactions. An attacker can submit thousands of minimum-value transactions from a funded address, filling the pending pool:

- `get_pending_transactions(limit=100)` caps the query but not the pool size
- Each pending tx locks balance, preventing legitimate transactions
- The block producer must iterate through all pending txs

**Impact:** Mempool flooding, blocking legitimate transactions, slow block production.

**Remediation:** Limit pending transactions per address (e.g., max 16). Reject submissions that exceed the limit.

---

### M2 — Transaction Ordering Manipulation

**Severity:** Medium
**File:** `node/rustchain_tx_handler.py`, `get_pending_transactions()`

**Description:**
Pending transactions are ordered by nonce only:
```sql
ORDER BY nonce ASC LIMIT ?
```

There's no fee-based prioritization. A miner/block producer has no incentive to include high-fee transactions first. This also means:
- No MEV protection
- No priority lanes for urgent transfers
- Transactions from one address always ordered before another's regardless of fee

**Impact:** Unfair transaction ordering, no market-based fee mechanism.

**Remediation:** Order by `fee DESC, nonce ASC` to prioritize high-fee transactions.

---

## Summary Table

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| C1 | Critical | Double-spend via concurrent pending | Open |
| H1 | High | No pending timeout enforcement | Open |
| H2 | High | Balance underflow on concurrent confirm | Open |
| M1 | Medium | Pending pool DoS | Open |
| M2 | Medium | No fee-based ordering | Open |
