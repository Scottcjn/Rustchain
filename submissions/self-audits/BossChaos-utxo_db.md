# Self-Audit: node/utxo_db.py

## Wallet
RTC6d1f27d28961279f1034d9561c2403697eb55602

## Module reviewed
- Path: node/utxo_db.py
- Commit: fe2cdd7
- Lines reviewed: 1–913 (whole file)

## Deliverable: 3 specific findings

### 1. Transaction ID malleability — outputs are excluded from tx_id hash when inputs are present

- Severity: **high**
- Location: node/utxo_db.py:453-467
- Description: The `tx_id` is computed at `apply_transaction()` lines 456-467 as `SHA256(sorted_input_box_ids || timestamp)`. For coinbase transactions (no inputs), the tx_type, block_height, and output details are included (lines 461-466). However, for regular transactions with inputs, the outputs are **not** included in the tx_id hash. This means an attacker who intercepts a transaction can modify the output addresses or values, recompute the tx_id (which changes because the box_id computation at line 473 depends on tx_id), and the modified transaction's inputs remain valid (they reference the same box_ids). While the balance conservation check at line 450 would prevent minting funds, an attacker can redirect outputs to their own address if they can control the tx submission path (e.g., via a man-in-the-middle on the API). The tx_id is meant to be a unique identifier for the transaction, but without output commitment, it only commits to the inputs, not the full transaction semantics.
- Reproduction:
  1. Alice submits a transaction spending box_A with outputs to Bob (500 nRTC) and change to Alice (500 nRTC)
  2. tx_id = SHA256(box_A || timestamp) — outputs not included
  3. Attacker intercepts, changes output address from Bob to Attacker
  4. Recompute box_ids for outputs using new tx_id (which changes because output values/addresses affect box_id at line 473)
  5. The new transaction has a different tx_id but the same input validity
  6. If the node processes the modified version first, Bob's payment is redirected

### 2. Exception handling swallows critical database errors — potential silent data corruption

- Severity: **medium**
- Location: node/utxo_db.py:278-279, 547-548, 791-792
- Description: Three locations in the file catch `Exception` during ROLLBACK operations and silently `pass` (lines 278-279, 547-548, 791-792). If the ROLLBACK itself fails (e.g., due to database corruption, connection closure, or a concurrent COMMIT), the exception is swallowed and the calling code receives no indication that the transaction state is inconsistent. In `spend_box()` (lines 274-280), if the ROLLBACK fails after a partial state mutation, the box may be in an unknown state — neither spent nor unspent. The finally block at line 282 closes the connection, but the database may have an open transaction with uncommitted changes. This is particularly dangerous because SQLite's WAL mode (not configured here) or journal mode could leave the database in an inconsistent state after a failed ROLLBACK.
- Reproduction:
  1. Open two connections to the same database
  2. Connection A begins a transaction and marks a box as spent
  3. Connection B holds a lock on the same row
  4. Connection A's ROLLBACK fails with "database is locked"
  5. The except block at line 278 swallows the error
  6. Connection A closes (line 282-283) but the database has an uncommitted transaction
  7. Future queries from Connection B may see inconsistent state

### 3. Mempool input tracking is not cleaned up on transaction abort

- Severity: **medium**
- Location: node/utxo_db.py:128-138 (schema) and apply_transaction() logic
- Description: The `utxo_mempool_inputs` table (lines 128-138) tracks which mempool transactions have claimed which input box_ids, to prevent double-spends at the mempool level. However, the `apply_transaction()` method does not interact with this table at all — it only checks the `utxo_boxes` table's `spent_at` column (line 408-416). The mempool input tracking appears to be managed by a separate code path (likely in `utxo_endpoints.py`). If a mempool transaction is added to `utxo_mempool_inputs` but then fails to apply (e.g., due to insufficient balance, a double-spend race, or a database error), the mempool input entry is never cleaned up. This means a box_id can be permanently blocked in the mempool even though no transaction successfully spent it, preventing all future legitimate transactions from using that UTXO. The cleanup only happens when a transaction successfully applies and the box is marked as spent in `utxo_boxes`.
- Reproduction:
  1. Submit transaction A spending box_X to the mempool — creates entry in utxo_mempool_inputs
  2. Transaction A fails validation (e.g., insufficient balance after another transaction)
  3. The mempool input entry for box_X in utxo_mempool_inputs is not removed
  4. Submit transaction B spending box_X — rejected because utxo_mempool_inputs shows box_X is claimed by A
  5. box_X is permanently unspendable until node restart and mempool flush

## Known failures of this audit
- I did not run the code live to verify runtime behavior or test the race conditions
- I did not audit the `utxo_endpoints.py` file which is the caller responsible for spending_proof validation — the security boundary between these two modules is critical but I only reviewed one side
- I did not check the SQLite PRAGMA settings (journal mode, WAL mode, synchronous) which affect the behavior of the ROLLBACK failure scenario in Finding 2
- I did not verify whether the mempool input tracking is actually used by the endpoint layer or if it's dead code
- I did not analyze the `compute_state_root()` function (lines 556-602) for Merkle tree construction vulnerabilities (e.g., second preimage attacks on the pairwise hashing scheme)

## Confidence
- Overall confidence: 0.80
- Per-finding confidence:
  - Finding 1 (tx_id malleability): 0.85
  - Finding 2 (silent ROLLBACK failure): 0.75
  - Finding 3 (mempool cleanup): 0.82

## What I would test next
- Read `utxo_endpoints.py` to verify the spending_proof validation logic and check if the tx_id is used for replay protection
- Start a local node and submit concurrent transactions to the same box_id to test the double-spend race condition
- Check the SQLite PRAGMA settings in the main node application to assess the impact of ROLLBACK failures
- Audit the mempool input tracking lifecycle — find all INSERT and DELETE operations on utxo_mempool_inputs
- Test the Merkle tree with duplicate leaf inputs to check for second preimage vulnerabilities in compute_state_root()
