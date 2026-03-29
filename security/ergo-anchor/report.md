# Security Red Team Report: Ergo Anchor Manipulation

**Bounty:** #60 — Ergo Anchor Integrity (100 RTC)
**Auditor:** LaphoqueRC
**Date:** 2026-03-29
**Scope:** `node/rustchain_ergo_anchor.py`, `node/beacon_anchor.py`
**Severity Scale:** Critical / High / Medium / Low

---

## Executive Summary

Audit of the RustChain → Ergo anchoring system revealed **1 Critical, 2 High, 2 Medium, 1 Low** severity findings. The critical finding is a hardcoded Ergo API key enabling unauthorized anchor transactions. High-severity issues include anchor commitment forgery via hash collision and a missing anchor verification gap.

---

## Findings

### C1 — Hardcoded Ergo Node API Key

**Severity:** Critical
**File:** `node/rustchain_ergo_anchor.py`, top-level constants
**CVSS:** 9.3

**Description:**
The Ergo node API key is stored as a plaintext constant:
```python
ERGO_API_KEY = "..."  # Hardcoded in source
```

The `ErgoClient.__init__()` sets this directly in session headers:
```python
self.session.headers['api_key'] = api_key
```

This key provides full wallet access to the Ergo node including:
- `POST /wallet/transaction/generate` — create arbitrary transactions
- `POST /wallet/transaction/sign` — sign with wallet keys
- `POST /transactions` — broadcast to network

**Impact:** Anyone with source code access can drain the Ergo wallet, create fraudulent anchor transactions, or sign arbitrary data with the anchor wallet key.

**Remediation:** 
1. Move API key to environment variable: `ERGO_API_KEY = os.environ.get("ERGO_API_KEY")`
2. Rotate the current key immediately
3. Use separate keys for read-only vs. transaction signing operations

---

### H1 — Anchor Commitment Forgery via Weak Hash Binding

**Severity:** High
**File:** `node/rustchain_ergo_anchor.py`, `AnchorCommitment.compute_hash()`

**Description:**
The commitment hash is computed from:
```python
def compute_hash(self) -> str:
    hasher = hashlib.sha256()
    hasher.update(str(self.rustchain_height).encode())
    hasher.update(self.state_root.encode())
    hasher.update(str(self.timestamp).encode())
    return hasher.digest().hex()
```

The inputs are string-concatenated without domain separators. This enables length-extension ambiguity:
- Height `12` + state root `3abc...` produces the same hash as
- Height `123` + state root `abc...` (shifted boundary)

Additionally, `timestamp` as a string allows different representations (with/without leading zeros) that hash differently for the same logical time.

**Impact:** An attacker can create a valid-looking anchor commitment for a different block height by manipulating the string boundary between fields.

**Remediation:** Use structured hashing with length-prefixed fields:
```python
hasher.update(self.rustchain_height.to_bytes(8, 'big'))
hasher.update(bytes.fromhex(self.state_root))
hasher.update(self.timestamp.to_bytes(8, 'big'))
```

---

### H2 — No Anchor Continuity Verification

**Severity:** High
**File:** `node/rustchain_ergo_anchor.py`, `AnchorService.should_anchor()`

**Description:**
`should_anchor()` only checks if enough blocks have passed since the last anchor:
```python
def should_anchor(self, current_height: int) -> bool:
    last = self.get_last_anchor()
    if not last:
        return True
    return (current_height - last['rustchain_height']) >= self.interval_blocks
```

There's no verification that:
1. The previous anchor was actually confirmed on Ergo
2. The chain of anchors is continuous (no gaps)
3. The state root in the previous anchor matches the current chain state

An attacker who controls the RustChain node can skip anchoring during an attack window, perform state manipulation, then resume anchoring — creating an appearance of integrity while the historical record has a gap.

**Impact:** Anchor integrity gaps enabling undetected state manipulation.

**Remediation:** Before creating a new anchor, verify the previous anchor's Ergo transaction has ≥N confirmations and the state root chain is continuous.

---

### M1 — Ergo Transaction Verification Bypass

**Severity:** Medium
**File:** `node/rustchain_ergo_anchor.py`, `verify_anchor()`

**Description:**
`verify_anchor()` checks R5 register for the commitment hash:
```python
if r5.startswith("0e40"):
    stored_hash = r5[4:]
    if stored_hash == commitment.commitment_hash:
        return True, ""
```

Issues:
1. Only checks if `r5.startswith("0e40")` — doesn't validate the full Ergo serialization format
2. Doesn't verify the transaction was sent to `ANCHOR_WALLET_ADDRESS`
3. Doesn't check R4 (height) or R6 (timestamp) match the commitment
4. An attacker can create a transaction with the right R5 but wrong height/timestamp

**Impact:** Partial anchor forgery — valid commitment hash but mismatched metadata.

**Remediation:** Verify all three registers (R4, R5, R6) match, check the output address, and verify the transaction has sufficient confirmations.

---

### M2 — Anchor Interval Race Condition

**Severity:** Medium
**File:** `node/rustchain_ergo_anchor.py`, `submit_anchor()` + `_save_anchor()`

**Description:**
`submit_anchor()` creates the Ergo transaction then calls `_save_anchor()` to record it locally. If the process crashes between submission and saving:
1. The Ergo transaction is broadcast and will be mined
2. The local database doesn't record it
3. On restart, `should_anchor()` sees no recent anchor and creates a duplicate
4. Duplicate anchors waste Ergo fees and create confusing audit trail

**Impact:** Duplicate anchor transactions, wasted fees, confusing anchor history.

**Remediation:** Save anchor with `status='pending'` before submission, update to `status='confirmed'` after. On restart, check for pending anchors on Ergo.

---

### L1 — Unvalidated Ergo Node URL

**Severity:** Low
**File:** `node/rustchain_ergo_anchor.py`, `ErgoClient.__init__()`

**Description:**
The Ergo node URL is used directly in HTTP requests without validation:
```python
self.node_url = node_url.rstrip('/')
```

A malicious node URL (e.g., `http://attacker.com`) would receive the API key in headers and all transaction signing requests. If the URL is configured via environment variable, DNS poisoning or typosquatting could redirect anchor operations.

**Impact:** API key exfiltration, anchor manipulation via rogue Ergo node.

**Remediation:** Validate URL scheme (https only in production), pin expected hostname, consider certificate pinning.

---

## Summary Table

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| C1 | Critical | Hardcoded Ergo API key | Open |
| H1 | High | Weak commitment hash binding | Open |
| H2 | High | No anchor continuity verification | Open |
| M1 | Medium | Incomplete transaction verification | Open |
| M2 | Medium | Anchor submission race condition | Open |
| L1 | Low | Unvalidated Ergo node URL | Open |
