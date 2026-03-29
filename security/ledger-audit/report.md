# Security Red Team Report: Ledger Integrity & Transfer Logging

**Bounty:** #54 — Ledger Integrity Audit (200 RTC)
**Auditor:** LaphoqueRC
**Date:** 2026-03-28
**Scope:** `rips/rustchain-core/ledger/utxo_ledger.py`, `node/rustchain_tx_handler.py`
**Severity Scale:** Critical / High / Medium / Low / Info

---

## Executive Summary

Audit of RustChain's UTXO ledger and transaction handler revealed **2 Critical, 3 High, 2 Medium, and 1 Low** severity findings. The most severe issue is a failed rollback in `apply_transaction()` that silently loses spent inputs on exception, effectively burning funds. The nonce validation logic has a race condition enabling transaction replay under concurrent access.

---

## Findings

### C1 — Silent Fund Loss on Transaction Rollback Failure

**Severity:** Critical
**File:** `rips/rustchain-core/ledger/utxo_ledger.py`, lines ~280-300
**CVSS:** 9.1

**Description:**
In `UTXOSet.apply_transaction()`, when output creation fails after inputs have been spent, the rollback logic is incomplete. The catch block prints an error but does not actually restore the spent boxes:

```python
except Exception as e:
    # Rollback on failure (restore spent boxes)
    # In production, this would be more sophisticated
    print(f"Transaction failed: {e}")
    return False
```

The spent boxes have already been:
1. Removed from `self._boxes`
2. Added to `self._spent` set
3. Removed from `self._by_address` index

But the rollback does NOT:
- Re-add boxes to `self._boxes`
- Remove box IDs from `self._spent`
- Re-add to `self._by_address`

**Impact:** Any transaction that fails during output creation permanently destroys the input UTXOs. An attacker can craft a transaction with valid inputs but malformed outputs (e.g., negative creation_height) to intentionally burn any address's funds.

**Remediation:**
```python
except Exception as e:
    # Proper rollback
    for box in spent_boxes:
        self._boxes[box.box_id] = box
        self._spent.discard(box.box_id)
        owner = self._proposition_to_address(box.proposition_bytes)
        if owner not in self._by_address:
            self._by_address[owner] = set()
        self._by_address[owner].add(box.box_id)
    return False
```

---

### C2 — Race Condition in Nonce Validation

**Severity:** Critical
**File:** `node/rustchain_tx_handler.py`, lines ~240-260
**CVSS:** 8.7

**Description:**
The nonce validation in `validate_transaction()` reads the expected nonce and pending nonces in separate queries without holding a lock:

```python
expected_nonce = self.get_wallet_nonce(tx.from_addr) + 1
pending_nonces = self._get_pending_nonces(tx.from_addr)

while expected_nonce in pending_nonces:
    expected_nonce += 1
```

Between `get_wallet_nonce()` and `_get_pending_nonces()`, another thread can:
1. Submit a transaction that increments the pending nonces
2. Confirm a pending transaction that changes the wallet nonce

This creates a TOCTOU (Time of Check, Time of Use) window where:
- Two transactions with the same nonce can both pass validation
- A transaction with a gap nonce passes validation, then blocks confirmation of intermediate nonces

**Impact:** Double-spend via concurrent transaction submission with identical nonces.

**Remediation:** Wrap nonce check + pending insertion in a single SQLite transaction with `BEGIN EXCLUSIVE`:
```python
with self._get_connection() as conn:
    conn.execute("BEGIN EXCLUSIVE")
    # All nonce checks and insertion here
    conn.commit()
```

---

### H1 — Missing Atomicity in confirm_transaction()

**Severity:** High
**File:** `node/rustchain_tx_handler.py`, lines ~374-420

**Description:**
`confirm_transaction()` performs multiple SQL operations (move from pending to history, update balances, update nonces) but uses the default auto-commit SQLite behavior within a `with` block. If the process crashes between operations:
- Transaction moved to history but balance not updated → funds vanish
- Balance updated but nonce not incremented → nonce replay possible

**Impact:** State corruption on crash leading to fund loss or nonce replay.

**Remediation:** Use explicit `BEGIN` / `COMMIT` / `ROLLBACK` around the full confirmation sequence.

---

### H2 — Integer Overflow in Balance Calculation

**Severity:** High
**File:** `rips/rustchain-core/ledger/utxo_ledger.py`, line ~265

**Description:**
The balance check `total_out > total_in` uses Python integers (unbounded), but the `value` field in Box is typed as `int` and comes from untrusted input. While Python handles big integers natively, the `to_bytes(8, 'little')` call in `_compute_id()` will raise `OverflowError` for values > 2^63-1.

More critically, if values are negative (no validation), the sum check passes:
```python
total_in = sum(b.value for b in input_boxes)  # Could be negative!
total_out = tx.total_output_value() + tx.fee
if total_out > total_in:  # Negative total_in always < total_out
    return False
```

But a malicious Box with `value = -1000` would subtract from the total, potentially allowing spending of more than available.

**Impact:** Funds creation from thin air via negative-value boxes.

**Remediation:** Validate `box.value > 0` in `add_box()` and `Box.__post_init__()`.

---

### H3 — Merkle Tree Second Preimage Attack

**Severity:** High
**File:** `rips/rustchain-core/ledger/utxo_ledger.py`, lines ~315-335

**Description:**
`compute_state_root()` duplicates the last hash when the tree has an odd number of leaves:
```python
if len(hashes) % 2 == 1:
    hashes.append(hashes[-1])
```

This is a known vulnerability in Merkle trees — an attacker can craft two different UTXO sets that produce the same root hash by exploiting the duplication of the last leaf. This enables light clients to be tricked into accepting an invalid state.

**Impact:** State commitment forgery, light client spoofing.

**Remediation:** Use a domain separator for leaf vs internal nodes, and use a unique sentinel for odd-length padding instead of duplicating the last hash.

---

### M1 — Weak Proposition Validation

**Severity:** Medium
**File:** `rips/rustchain-core/ledger/utxo_ledger.py`, lines ~302-308

**Description:**
`_proposition_to_address()` performs minimal validation:
```python
if prop.startswith(b'\x00\x08'):
    return prop[2:].decode('utf-8', errors='ignore')
return f"RTC_UNKNOWN_{prop[:8].hex()}"
```

The `errors='ignore'` silently drops invalid UTF-8 bytes, meaning two different propositions could map to the same address. Additionally, there's no length validation — an empty proposition after the prefix maps to an empty string address.

**Impact:** Address collision enabling fund theft; empty-string address can aggregate unrelated funds.

**Remediation:** Validate proposition length >= 34 bytes (2 prefix + 32 pubkey minimum), reject invalid UTF-8 instead of ignoring.

---

### M2 — Transaction Log Injection via Memo Field

**Severity:** Medium
**File:** `node/rustchain_tx_handler.py`, lines ~320-340

**Description:**
The `memo` field in `submit_transaction()` is stored directly in SQLite without sanitization and logged via `logger.info()` without escaping. A crafted memo containing:
- SQL injection payloads (mitigated by parameterized queries, but risky if format strings are used elsewhere)
- Log injection: newlines + fake log entries
- Unicode RTL override characters that make logs misleading

**Impact:** Log poisoning, potential log analysis confusion.

**Remediation:** Sanitize memo: strip control characters, enforce max length (256 bytes), reject non-printable characters.

---

### L1 — Deterministic Box ID Enables Front-Running

**Severity:** Low
**File:** `rips/rustchain-core/ledger/utxo_ledger.py`, lines ~70-80

**Description:**
`_compute_id()` is deterministic based on box contents:
```python
hasher.update(self.value.to_bytes(8, 'little'))
hasher.update(self.proposition_bytes)
hasher.update(self.creation_height.to_bytes(8, 'little'))
hasher.update(self.transaction_id)
hasher.update(self.output_index.to_bytes(2, 'little'))
```

An observer can predict the box ID of a pending transaction's outputs and pre-compute spending proofs for a follow-up transaction, enabling MEV-style front-running.

**Impact:** Transaction ordering manipulation.

**Remediation:** Include a random nonce or the block hash in box ID computation.

---

## Summary Table

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| C1 | Critical | Silent fund loss on rollback failure | Open |
| C2 | Critical | Nonce validation TOCTOU race | Open |
| H1 | High | Non-atomic confirm_transaction | Open |
| H2 | High | No negative value validation | Open |
| H3 | High | Merkle tree second preimage | Open |
| M1 | Medium | Weak proposition validation | Open |
| M2 | Medium | Log injection via memo | Open |
| L1 | Low | Deterministic box ID front-running | Open |
