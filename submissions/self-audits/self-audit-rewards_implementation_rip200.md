# Self-Audit: node/rewards_implementation_rip200.py

## Wallet
RTC4642c5ee8467f61ed91b5775b0eeba984dd776ba

## Module reviewed
- Path: node/rewards_implementation_rip200.py
- Commit: cb17137e6bebae777f01cffc18a05db235679e28
- Lines reviewed: whole-file (280 lines)

## Deliverable: 3 specific findings

1. **Double-Credit via Anti-Double-Mining Exception Fallback**
   - Severity: critical
   - Location: node/rewards_implementation_rip200.py:140-170 (settle_epoch_rip200, anti-double-mining try/except)
   - Description: When `enable_anti_double_mining=True` and the anti-double-mining module is loaded, `settle_epoch_with_anti_double_mining()` is called with `db_path` (string) as the first argument AND `existing_conn=db`. If the callee opens its own SQLite connection from the string path and writes partial reward records before raising an exception, those writes persist on a separate connection not covered by the outer `db.rollback()`. The except block catches the exception and falls through to the standard rewards path, which credits the same miners again on the original `db` connection. This results in double-crediting: each affected epoch drains an extra 1.5 RTC (PER_EPOCH_URTC) from the reward pool.
   - Reproduction: (1) Configure anti-double-mining to be available. (2) Trigger a settle_epoch_rip200 call where settle_epoch_with_anti_double_mining writes partial rewards on its own connection then raises (e.g., attestation validation failure after INSERT). (3) Observe that the fallback standard path credits the same miners again. (4) Query `SELECT * FROM ledger WHERE epoch=X` — duplicate delta_i64 entries appear.

2. **Floating-Point Precision Loss in Financial Ledger Conversions**
   - Severity: high
   - Location: node/rewards_implementation_rip200.py:180, 218, 230 (amount_i64 / UNIT conversions)
   - Description: All uRTC-to-RTC conversions use Python float division (`amount_i64 / UNIT`). IEEE 754 double has ~15-17 significant digits; for balances exceeding ~10^9 uRTC (1,000 RTC), precision loss occurs. The `get_all_balances()` endpoint applies `int(row[1]) / UNIT` to every row, compounding errors across the entire balance sheet. The `round(..., 8)` in `get_balance()` masks but does not fix the underlying issue. Over many settlement epochs, cumulative rounding errors cause the sum of displayed `amount_rtc` values to diverge from `total_urtc / UNIT`, violating the financial integrity invariant.
   - Reproduction: (1) Accumulate a miner balance to 1,500,000,001 uRTC. (2) Call `/wallet/balance?miner_id=X` — observe `amount_rtc` shows `1500.00000100` via round(), but `1_500_000_001 / 1_000_000` in Python gives `1500.00000100000002`. (3) Call `/wallet/balances/all` — `total_rtc` uses unrounded float division, producing a different value than the sum of individually rounded balances.

3. **Unvalidated Epoch Input Type in Settle Endpoint**
   - Severity: medium
   - Location: node/rewards_implementation_rip200.py:190-200 (/rewards/settle route handler)
   - Description: The settle endpoint reads `epoch = data.get('epoch')` from the JSON request body with no type or range validation. The value is passed directly to `settle_epoch_rip200()` and used in integer comparison (`epoch > current_epoch`) and SQL INSERT. Float input (e.g., `42.7`) bypasses the future-epoch guard because `42.7 > 42` is True in Python but `42.7 // 144` produces `0.0` (float), corrupting the integer epoch schema. Negative input (`epoch=-1`) passes the future-epoch check and creates phantom entries in `epoch_state`. String input is stored as TEXT in the integer column, corrupting the table schema.
   - Replication: (1) POST to `/rewards/settle` with `{"epoch": -1}` — succeeds and inserts epoch=-1 into epoch_state. (2) POST with `{"epoch": 42.7}` — `slot_to_epoch` returns `0.0` (float), inserted as REAL into integer column. (3) POST with `{"epoch": "abc"}` — INSERT succeeds due to SQLite loose typing, corrupting the epoch_state table.

## Known failures of this audit
- Did not review `rip_200_round_robin_1cpu1vote.py` or `anti_double_mining.py` — those are separate modules and their internal behavior affects Issue #1 severity. If `anti_double_mining.py` always uses `existing_conn` and never opens its own connection, Issue #1 is downgraded to medium.
- Did not test against a live database — all analysis is static code review. The actual SQLite version and WAL mode configuration could affect transaction isolation behavior.
- Did not review the Flask deployment configuration (WSGI server, reverse proxy) — if behind a multi-worker server, additional race conditions beyond Issue #1 may exist.
- Confidence on Issue #1 depends on whether `settle_epoch_with_anti_double_mining` respects `existing_conn` consistently. The function signature suggests it should, but the fallback path passing `db_path` as the first argument creates ambiguity.
- Did not analyze the `calculate_epoch_rewards_time_aged()` return value for potential reward calculation errors in the external module.

## Confidence
- Overall confidence: 0.75
- Per-finding confidence: [0.70, 0.90, 0.85]
  - Issue #1: 0.70 — depends on anti_double_mining.py internal connection handling; the code pattern is clearly risky but severity depends on callee behavior
  - Issue #2: 0.90 — float precision loss is deterministic and provable with specific inputs
  - Issue #3: 0.85 — input validation gap is clear from code; exact behavior depends on SQLite version and schema constraints

## What I would test next
- Read `anti_double_mining.py` to confirm whether `settle_epoch_with_anti_double_mining` opens its own DB connection or strictly uses `existing_conn` — this determines if Issue #1 is exploitable in practice
- Run `settle_epoch_rip200()` with concurrent threads settling the same epoch to empirically verify the race condition and double-credit behavior
- Test the `/rewards/settle` endpoint with edge-case inputs (float, negative, very large, string) against a live SQLite database to confirm Issue #3 reproduction
