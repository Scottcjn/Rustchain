<!-- SPDX-License-Identifier: MIT -->
# Security Audit Report — UTXO Mempool / Transaction Layer

**Auditor:** @waefrebeorn  
**Wallet:** `15wLLZxFzNesJKEXo6E9NMVhpZWEUcAC4R` (BTC)  
**Requested Payout:** 90-150 RTC  
**Date:** 2026-05-24  

---

## Executive Summary

A targeted security audit of the RustChain UTXO mempool and transaction application layer identified **4 vulnerabilities** in the mempool admission path:

| ID | Severity | Finding | Est. RTC |
|----|----------|---------|----------|
| A1 | MEDIUM | `mempool_add()` missing `MAX_INPUTS` bound — DoS via unbounded SELECTs in write lock | 25-50 |
| A2 | MEDIUM | `apply_transaction()` missing `MAX_INPUTS` bound — block production delay | 25-50 |
| A3 | LOW-MED | `tx_data_json` stores full caller dict with no field/size validation — storage/response bloat | 10-25 |
| A4 | LOW | TOCTOU: `mempool_add` + `apply_transaction` both claim same box — stale mempool entries | 5-15 |

**Total estimate:** 65-140 RTC ($6.50-$14.00 at $0.10/RTC)

PoC tests are included in `node/test_utxo_no_max_inputs_poc.py`, `node/test_utxo_no_max_inputs_apply_poc.py`, `node/test_utxo_mempool_garbage_injection_poc.py`, and `node/test_utxo_mempool_apply_toctou_poc.py`.

---

## A1: `mempool_add()` missing `MAX_INPUTS` bound

**File:** `node/utxo_db.py`, Line 842  
**Severity:** Medium (25-50 RTC)  
**Category:** Denial of Service

### Description

`mempool_add()` at line 842 has no upper bound on the number of inputs a transaction can carry. Each input triggers multiple SELECT queries inside `BEGIN IMMEDIATE` (double-spend check, box existence, value accumulation), creating an unbounded DoS vector.

The codebase has `MAX_OUTPUTS = 100` (line 45) as a symmetrical anti-bloat guard, but no analogous `MAX_INPUTS` constant exists.

### Impact

An attacker can submit a transaction with 10,000+ inputs, forcing 10,000+ SELECT queries inside the write lock. At ~100K queries/sec (measured on local SQLite), this locks the DB for ~100ms per call. Multiple concurrent admissions compound the effect.

### PoC

```python
# Submits 200-input tx to mempool — accepted with no rejection
ok = db.mempool_add({
    'tx_id': 'big_input_tx',
    'tx_type': 'transfer',
    'inputs': [{'box_id': bid, 'spending_proof': 'sig'} for bid in 200_boxes],
    'outputs': [{'address': 'bob', 'value_nrtc': 200 * UNIT}],
    'fee_nrtc': 0,
})
assert ok  # BUG: Should be rejected
# Output: 200-input tx accepted: True (0.002s, 100K queries/sec)
```

### Fix

Add `MAX_INPUTS = 1000` and reject `if len(inputs) > MAX_INPUTS` at the top of the validation block in `mempool_add()`.

---

## A2: `apply_transaction()` missing `MAX_INPUTS` bound

**File:** `node/utxo_db.py`, Line 485  
**Severity:** Medium (25-50 RTC)  
**Category:** Denial of Service / Consensus Stall

### Description

Same root cause as A1, but in the block application path. `apply_transaction()` performs one `UPDATE utxo_boxes SET spent_at` per input (line 668-676) with no input count guard. A 500-input transaction executes 500 UPDATE statements inside the write lock.

The `coin_select()` function (line 1185) uses a heuristic cap of 20 inputs, but this is a soft limit in the client — the database layer enforces nothing.

### Impact

Block producers accepting mempool candidates with excessive inputs stall block production while iterating the input UPDATE loop. At ~100K updates/sec, 10K inputs → ~100ms per candidate.

### PoC

```python
# 100-input apply_transaction accepted with no rejection
ok = db.apply_transaction({
    'tx_type': 'transfer',
    'inputs': [{'box_id': bid, 'spending_proof': 'sig'} for bid in 100_boxes],
    'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
    'fee_nrtc': 0,
    'timestamp': int(time.time()),
}, block_height=200)
assert ok
# Output: 100 inputs: True (0.0013s)
```

### Fix

Add the same `MAX_INPUTS` check in `apply_transaction()` before the input processing loop.

---

## A3: `tx_data_json` stores full caller dict with no field/size validation

**File:** `node/utxo_db.py`, Line 1001  
**Severity:** Low-Medium (10-25 RTC)  
**Category:** Data Integrity / Storage Bloat

### Description

`mempool_add()` stores `json.dumps(tx)` (line 1001) with the entire caller-provided transaction dict — no field whitelist, no size limit. Injected fields like `_allow_minting`, 50KB garbage payloads, and nested structures survive the store→retrieve round-trip.

The `/utxo/mempool` endpoint (line 316 of `utxo_endpoints.py`) returns these raw candidate dicts, propagating injected data to HTTP responses.

### Impact

- **Storage bloat:** 50KB/tx × 9,999 max pool = ~500MB garbage in mempool
- **Response bloat:** `/utxo/mempool` serves attacker-controlled payloads
- **Downstream confusion:** Consumers see injected fields (`_allow_minting: True`, etc.)

### PoC

```python
# Injected garbage fields survive store → retrieve
tx = {
    'tx_id': 'inj1',
    'tx_type': 'transfer',
    'inputs': [{'box_id': bid, 'spending_proof': 'sig'}],
    'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
    'fee_nrtc': 0,
    'garbage': 'X' * 10000,
    '_allow_minting': True,
    'nested_spam': {'key': ['a', 'b'] * 1000},
}
db.mempool_add(tx)
candidates = db.mempool_get_block_candidates()
assert 'garbage' in candidates[0]  # BUG: extra field survived
assert '_allow_minting' in candidates[0]  # BUG: internal flag leaked
# Output: Extra keys found: {'garbage', '_allow_minting', 'nested_spam'}
```

### Fix

Whitelist allowed fields before `json.dumps()`. Only persist: `tx_type`, `inputs`, `outputs`, `data_inputs`, `fee_nrtc`, `timestamp`. Add `MAX_TX_JSON_BYTES` cap.

---

## A4: TOCTOU — `mempool_add` + `apply_transaction` both claim same box

**File:** `node/utxo_db.py`, Lines 842 and 485  
**Severity:** Low (5-15 RTC)  
**Category:** Race Condition / Mempool Integrity

### Description

`mempool_add()` claims a box in `utxo_mempool_inputs` (mempool claim), while `apply_transaction()` spends the same box in `utxo_boxes.spent_at`. These use separate `BEGIN IMMEDIATE` transactions on separate connections with no cross-coordination. Calling both methods sequentially on the same box — both return `True`.

The mempool entry becomes stale/unmineable: the box is spent in `utxo_boxes` but the mempool entry persists until expiry or cleanup.

### Impact

- Sequential (demonstrated): both `mempool_add` and `apply_transaction` return `True` for the same box
- Concurrent: SQLite `BEGIN IMMEDIATE` serialization mostly prevents the race, but the API-level coordination gap exists
- Result: stale mempool entries consume pool slots until cleanup

### PoC

```python
# Sequential: BOTH return True on the same box
mempool_ok = db.mempool_add(tx_mempool)          # claims box X in mempool_inputs
apply_ok = db.apply_transaction(tx_apply)         # spends box X in utxo_boxes
assert mempool_ok  # True
assert apply_ok     # True (BUG: should fail - box already in mempool)
# Carol (apply_tx): 100 UNIT, Bob (mempool): 0 UNIT — stale mempool entry
```

### Fix

In `apply_transaction()` (or the block production endpoint), check that none of the input boxes are currently claimed in `utxo_mempool_inputs` before spending. Alternatively, add a cross-table coordination mechanism.

---

## Summary of Fixes

| Finding | File | Fix |
|---------|------|-----|
| A1 | `utxo_db.py:842` | Add `MAX_INPUTS = 1000` + guard in `mempool_add()` |
| A2 | `utxo_db.py:485` | Add `MAX_INPUTS` guard in `apply_transaction()` |
| A3 | `utxo_db.py:1001` | Whitelist tx fields, cap JSON size |
| A4 | `utxo_db.py:842+485` | Cross-check mempool_inputs in apply_transaction |
