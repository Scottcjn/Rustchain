# Self-Audit: node/bridge_api.py

## Wallet
RTC6d1f27d28961279f1034d9561c2403697eb55602

## Module reviewed
- Path: node/bridge_api.py
- Commit: 59ef682
- Lines reviewed: 1–876 (whole file)

## Deliverable: 3 specific findings

### 1. Cross-chain bridge deposits skip balance lock — funds can be double-spent during transfer

- Severity: **high**
- Location: node/bridge_api.py:301
- Description: In `create_bridge_transfer()`, when `admin_initiated=True`, the balance check at line 301 is bypassed entirely. The `admin_initiated` flag is set at line 682 by comparing the `X-Admin-Key` header against `RC_ADMIN_KEY`. However, the same endpoint (`/api/bridge/initiate`, line 661) also calls `create_bridge_transfer()` with `admin_initiated` when the admin key header matches. An attacker who obtains the admin key (via environment variable leak, log exposure, or timing attack on the string comparison at line 682) can initiate unlimited bridge deposits without any balance check, creating phantom lock_ledger entries. Worse, even without the admin key, the `admin_initiated` parameter is a boolean passed through a function call chain — if any upstream code path sets it to True without validating the admin key, the balance check is silently skipped.
- Reproduction:
  1. Send POST to /api/bridge/initiate with a valid bridge request
  2. Include header `X-Admin-Key: <value of RC_ADMIN_KEY env var>`
  3. The balance check is bypassed — a deposit is created with no actual funds locked
  4. The lock_ledger entry at line 349-369 creates a "locked" record referencing a non-existent balance
  5. When the external chain confirms the (non-existent) deposit, the lock is released at line 626-633, and the destination chain mints tokens based on the phantom deposit record

### 2. update_external endpoint has no replay protection — attacker can alter transfer status

- Severity: **high**
- Location: node/bridge_api.py:785-816
- Description: The `/api/bridge/update-external` endpoint accepts `confirmations` and `required_confirmations` values directly from the request body with no nonce, signature, or idempotency key. Once a transfer reaches "completed" status (line 602-604), the function returns an error at line 592-596, but the status transition logic at lines 601-610 allows an attacker to downgrade a transfer from "completed" back to "confirming" or "locked" by sending a subsequent update with lower confirmation counts. While there is a guard at line 592 for completed/failed/voided transfers, this check only prevents the function from running — it does not prevent the race condition where two concurrent update requests arrive, one with confirmations >= req_conf and one with confirmations = 0. Without database-level locking (e.g., SELECT ... FOR UPDATE), the second request can overwrite the first's completed status.
- Reproduction:
  1. Initiate a bridge transfer, get tx_hash
  2. Send POST to /api/bridge/update-external with tx_hash, confirmations=12, required_confirmations=12 → status becomes "completed"
  3. Immediately send another POST with confirmations=0 → if the race window at line 592 is hit, the status reverts to "locked"
  4. The lock_ledger entry (line 626-633) is only released when new_status == "completed", so a reverted transfer leaves the lock unreleased but the transfer in "locked" state indefinitely

### 3. Bridge transfer amount stored as REAL (floating point) causes precision loss in cross-chain accounting

- Severity: **medium**
- Location: node/bridge_api.py:842
- Description: The `bridge_transfers` table stores `amount_rtc` as REAL (SQLite floating point, line 842) alongside `amount_i64` (INTEGER, line 841). While `amount_i64` is used for balance checks and lock_ledger entries, `amount_rtc` is used in the API response (lines 310, 384, 427, 500, 564). The conversion at line 281 uses `Decimal(str(request.amount_rtc)) * BRIDGE_UNIT`, which is correct for the i64 conversion, but the original `amount_rtc` float value is persisted as-is. For amounts that cannot be exactly represented in IEEE 754 (e.g., 0.1 RTC), the stored REAL value differs from the reconstructed value (amount_i64 / BRIDGE_UNIT), creating a discrepancy in audit trails. Over many transfers, this rounding drift makes it impossible to reconcile total bridge volume from the database.
- Reproduction:
  1. Initiate a bridge transfer with amount_rtc = 0.1
  2. Query the database: SELECT amount_rtc, amount_i64 FROM bridge_transfers WHERE id = <new_id>
  3. amount_i64 will be 100000 (0.1 * 1000000), but amount_rtc may be stored as 0.10000000000000001
  4. Reconstructing: 100000 / 1000000 = 0.1, but the stored REAL is 0.10000000000000001
  5. SUM(amount_rtc) across many rows will diverge from SUM(amount_i64) / 1000000

## Known failures of this audit
- I did not run the code live to verify runtime behavior or test the race conditions described in Finding 2
- I did not check the lock_ledger table schema for foreign key constraints or cascading delete behavior
- I did not verify whether the main node application (rustchain_v2_integrated_*.py) adds middleware (rate limiting, auth) that would mitigate Finding 1
- I did not audit the `validate_chain_address_format()` function (line 188) for chain-specific address validation bypasses (e.g., Solana address length check allows 32-44 chars but does not verify base58 charset)

## Confidence
- Overall confidence: 0.82
- Per-finding confidence:
  - Finding 1 (admin bypass): 0.90
  - Finding 2 (replay protection): 0.78
  - Finding 3 (float precision): 0.88

## What I would test next
- Start a local node with MOCK_MODE=1 and initiate bridge transfers with admin key to confirm Finding 1's balance bypass
- Send concurrent update_external requests with Python threading to reproduce the race condition in Finding 2
- Insert 10,000 bridge transfers with varying decimal amounts and compare SUM(amount_rtc) vs SUM(amount_i64)/1000000
- Check if the Solana address validation at line 199-202 accepts invalid base58 characters (e.g., '0', 'O', 'I', 'l')
