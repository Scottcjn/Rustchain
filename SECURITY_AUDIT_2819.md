# Security Audit: UTXO Implementation (Bounty #2819)

**Auditor**: rafaio1 (automated red-team agent)
**Target**: `node/utxo_db.py`, `node/utxo_endpoints.py`
**Date**: 2026-09-03
**Scope**: Red Team review of UTXO database layer and transfer endpoint

## Executive Summary

The UTXO implementation has undergone significant hardening. Critical attack surfaces including double-spend TOCTOU windows, JSON bomb DoS, minting authorization, and mempool eviction have been addressed through multiple fix iterations. The codebase demonstrates mature defense-in-depth practices.

**Findings**: 2 medium-severity issues identified, 3 informational observations. No critical or high-severity vulnerabilities found.

---

## Findings

### MEDIUM-1: Non-Atomic Stale Transaction Cleanup in `mempool_get_block_candidates`

**Location**: `node/utxo_db.py:1585-1672`

**Description**: The `mempool_get_block_candidates()` method performs stale transaction cleanup (DELETE operations on `utxo_mempool` and `utxo_mempool_inputs`) without wrapping the SELECT-then-DELETE sequence in a `BEGIN IMMEDIATE` transaction. While `mempool_clear_expired()` (called at line 1587) correctly uses `BEGIN IMMEDIATE`, the subsequent inline cleanup of stale candidates discovered during iteration does not.

**Impact**: Under concurrent load, a `mempool_add()` call could interleave between the candidate selection loop's identification of a stale tx and its deletion, potentially causing:
- A transaction to be added to the mempool after being selected as valid but before deletion
- Inconsistent mempool state where `utxo_mempool_inputs` and `utxo_mempool` diverge
- Low probability due to narrow window, but violates the atomicity pattern established elsewhere

**Evidence**: Compare with `mempool_clear_expired()` at line 1678 which explicitly documents: "Uses BEGIN IMMEDIATE to ensure the SELECT-then-DELETE sequence is atomic. Without it, a concurrent mempool_add() or apply_transaction() can interleave between the SELECT and the DELETEs, causing mempool state corruption / double-spend (B2, issue #8176)."

The same race condition applies to the inline cleanup in `mempool_get_block_candidates`.

**Recommendation**: Wrap the stale candidate deletion block (lines 1660-1671) in `BEGIN IMMEDIATE` / `COMMIT`, or refactor to use a single atomic DELETE with subquery.

**Severity**: Medium (race condition, low exploitability, no direct fund loss)

---

### MEDIUM-2: Performance DoS via JSON Parsing in Hot Path

**Location**: `node/utxo_db.py:1543-1556` (`_evict_stale_data_input_txs`)

**Description**: During every block application, `_evict_stale_data_input_txs` iterates over ALL mempool transactions and parses each `tx_data_json` to check for data_input references to spent boxes. With `MAX_POOL_SIZE=10,000`, this means up to 10,000 JSON parse operations per block in the worst case.

**Impact**: An attacker who fills the mempool with transactions containing large or deeply nested `tx_data_json` payloads can amplify block processing time. While individual JSON parsing is O(n) with depth guards, the aggregate cost across 10K transactions creates a CPU amplification vector. The existing `_json_max_depth()` guard prevents stack overflow but does not limit total CPU time.

**Context**: This was introduced as BUG-4 fix for availability (preventing stale txs from holding inputs reserved). The fix trades one availability problem for another under adversarial conditions.

**Recommendation**: 
1. Add an index or auxiliary table mapping `box_id → tx_id` for data_inputs (similar to `utxo_mempool_inputs` for regular inputs), eliminating the need for JSON parsing in the hot path.
2. Alternatively, cap the scan to N transactions and defer remaining cleanup to a background task.

**Severity**: Medium (DoS amplification, mitigated by existing pool size limits and JSON depth guards)

---

### INFO-1: `coin_select` Returns Mutable References

**Location**: `node/utxo_db.py:1737-1800`

**Description**: `coin_select()` returns references to the original dict objects from the input `utxos` list. If any caller mutates the returned dicts, the original list is corrupted. Current callers (`utxo_transfer` endpoint) do not mutate, but this is a latent fragility.

**Recommendation**: Return defensive copies (`dict(u) for u in selected`) or document immutability contract.

**Severity**: Informational (no current exploit, defensive coding improvement)

---

### INFO-2: `compute_box_id` Output Index Encoding Width

**Location**: `node/utxo_db.py:135`

**Description**: Uses `output_index.to_bytes(2, 'big')` allowing indices up to 65535, while `MAX_OUTPUTS=100`. The encoding is wider than necessary but safe.

**Severity**: Informational (cosmetic, no security impact)

---

### INFO-3: Error Message Information Disclosure in `spend_box`

**Location**: `node/utxo_db.py:381-386`

**Description**: On double-spend attempt, `spend_box()` raises `ValueError` containing the `spent_by_tx` hash of the consuming transaction. The `/utxo/transfer` endpoint catches exceptions generically and returns a 500 error without leaking this detail to unauthenticated callers. Verified safe at endpoint layer.

**Severity**: Informational (defense-in-depth already present at API boundary)

---

## Verified Hardened Areas

| Attack Surface | Status | Reference |
|---|---|---|
| Double-spend TOCTOU | ✅ Fixed | Atomic UPDATE with `WHERE spent_at IS NULL` (#6345) |
| Minting authorization | ✅ Fixed | `_allow_minting` flag + coinbase cap + mempool rejection |
| JSON bomb/depth DoS | ✅ Fixed | O(n) `_json_max_depth()` scanner before `json.loads` |
| Mempool double-spend | ✅ Fixed | `INSERT OR ABORT` + input claim tracking |
| Fund destruction | ✅ Fixed | Empty output rejection + conservation check |
| Mirror double-write | ✅ Fixed | Per-wallet `_check_mirror_provenance()` assertion |
| Account-model cross-spend | ✅ Fixed | Mirror box exclusion in coin selection regardless of dual_write state |
| Signature domain separation | ✅ Fixed | UTXO domain tag prevents account-signature substitution |
| Replay protection | ✅ Fixed | Nonce reservation + monotonicity check under BEGIN IMMEDIATE |
| Fee manipulation MITM | ✅ Fixed | Fee included in signed payload (#2202) |

---

## Methodology

1. Full source review of `node/utxo_db.py` (1,791 lines) and `node/utxo_endpoints.py` (900+ lines)
2. Cross-referenced fix history against issue tracker (#6345, #8176, #2867, #2202, #6114, #8286)
3. Analyzed concurrency model (SQLite transaction isolation, BEGIN IMMEDIATE usage)
4. Reviewed test coverage in `node/test_utxo_db.py` and red-team PoC files
5. Traced all external callers of sensitive functions

## Conclusion

The UTXO implementation is well-hardened against known attack classes. The two medium findings represent residual risk in non-critical paths (block template construction performance and mempool maintenance atomicity) rather than direct fund-loss vectors. Both are suitable for incremental improvement rather than emergency patching.

**Recommended bounty tier**: Lower range (33-50 RTC) — findings are valid but the codebase shows extensive prior security investment.
