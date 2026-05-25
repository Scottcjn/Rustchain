# Battleship 300 Bug Hunt — RustChain UTXO

## A1: mempool_add() missing MAX_INPUTS ✅ DONE
**File:** `node/utxo_db.py:842` → `mempool_add()`
**Severity:** MEDIUM (DoS via unbounded query count in write lock)
**Evidence:**
  - 200-input tx accepted: True (93,539 qps)
  - 500-input tx accepted: True (111,043 qps)
  - No MAX_INPUTS constant in utxo_db.py
  - MAX_OUTPUTS=100 exists → asymmetry
  - 10K inputs → ~90ms locked DB time
**PoC:** `node/test_utxo_no_max_inputs_poc.py`
**Fix:** Add `MAX_INPUTS = 1000` + reject `if len(inputs) > MAX_INPUTS` in mempool_add()

## A2: apply_transaction() missing MAX_INPUTS ✅ DONE
**File:** `node/utxo_db.py:485` → `apply_transaction()`
**Severity:** MEDIUM (block production delay, consensus stall)
**Evidence:**
  - 100-input tx accepted: True (71,429 updates/sec)
  - 500-input tx accepted: True (103,456 updates/sec)
  - Same root cause as A1 — no MAX_INPUTS constant
  - coin_select() caps at 20 inputs (heuristic) but DB layer has no guard
  - 10K inputs → ~100ms locked time during block production
**PoC:** `node/test_utxo_no_max_inputs_apply_poc.py`
**Fix:** Same `MAX_INPUTS` check in apply_transaction()

## A3: mempool_add() stores full tx dict with no field/size validation ✅ DONE
**File:** `node/utxo_db.py:1001` → `json.dumps(tx)` in `mempool_add()`
**Severity:** LOW-MEDIUM (storage inflation, response bloat)
**Evidence:**
  - 20KB garbage field injected → survives store→retrieve round-trip
  - Extra keys: `garbage`, `_allow_minting`, `nested_spam` all survive
  - tx_data_json has NO size limit, NO field whitelist
  - 9999 max pool × 50KB = ~500MB potential mempool bloat
**PoC:** `node/test_utxo_mempool_garbage_injection_poc.py`
**Fix:** Whitelist allowed fields before json.dumps(). Add MAX_TX_JSON_BYTES cap.

## A5: mempool_get_block_candidates() fetchall() loads all tx_data_json in memory ✅ DONE
**File:** `node/utxo_db.py:1055` → `fetchall()` in `mempool_get_block_candidates()`
**Severity:** MEDIUM (DoS — memory exhaustion via garbage-padded mempool entries)
**Evidence:**
  - `mempool_add()` stores `json.dumps(tx)` at line 1001 with NO size cap
  - `mempool_get_block_candidates()` uses `.fetchall()` at line 1055 — loads ALL rows into Python memory
  - Same A3 garbage injection vector inflates each tx_data_json to 100KB+
  - MAX_POOL_SIZE=10000 × 100KB = ~977MB loaded by fetchall()
  - Processing loop iterates ALL rows before reaching max_count (line 1091)
**PoC:** `node/test_utxo_mempool_fetchall_oom_poc.py`
**Fix:** Add MAX_TX_DATA_JSON_BYTES cap in mempool_add(). Use server-side cursor / LIMIT+OFFSET in mempool_get_block_candidates(). Strip non-essential fields before json.dumps().

## A4: TOCTOU — mempool_add + apply_transaction both claim same box ✅ DONE
**File:** `node/utxo_db.py:842` (`mempool_add()`) vs `node/utxo_db.py:485` (`apply_transaction()`)
**Severity:** LOW (sequential gap; SQLite IMMEDIATE lock mostly mitigates concurrent race)
**Evidence:**
  - Sequential: mempool_add and apply_transaction both return True on same box
  - mempool_add claims in utxo_mempool_inputs, apply_transaction spends in utxo_boxes.spent_at
  - No cross-check between the two systems → stale mempool entries
  - Carol gets 100 UNIT (apply_tx), Bob gets 0 (stale mempool entry)
  - Concurrent: SQLite IMMEDIATE lock serializes, preventing concurrent race
**PoC:** `node/test_utxo_mempool_apply_toctou_poc.py`
**Fix:** In apply_transaction or block production, check mempool_inputs doesn't claim the box.
