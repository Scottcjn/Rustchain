# Self-Audit: node/settle_epoch.py + node/auto_epoch_settler.py + node/claims_settlement.py

## Wallet
RTC4642c5ee8467f61ed91b5775b0eeba984dd776ba

## Module reviewed
- Path: node/settle_epoch.py, node/auto_epoch_settler.py, node/claims_settlement.py
- Commit: cb17137e6bebae777f01cffc18a05db235679e28
- Lines reviewed: whole-file (all three files)

## Deliverable: 3 specific findings

1. **Production Transaction Simulation Uses `random.random()` Instead of Actual Signing**
   - Severity: critical
   - Location: node/claims_settlement.py:163-175
   - Description: `sign_and_broadcast_transaction()` uses `random.random() < 0.9` in the production code path (not guarded by any test/dev flag). This means real settlement transactions have a ~10% random failure rate. The only guard is `os.environ.get('PYTEST_CURRENT_TEST')` which only activates during pytest — production calls fall through to the random branch, generating mock transaction hashes instead of real ones.
   - Reproduction:
     ```python
     # In sign_and_broadcast_transaction(), lines 163-175:
     import random
     if random.random() < 0.9:  # <-- Production code path
         tx_hash = "0x" + "".join(random.choices("0123456789abcdef", k=64))
         return True, tx_hash, None  # Fake hash, no actual broadcast
     else:
         return False, None, "Simulated transaction failure"  # Random failure
     ```
     Any call to `process_claims_batch(dry_run=False)` outside pytest hits this path. Settlement claims get marked "settled" with a random hex string as tx_hash, no actual on-chain transfer occurs.

2. **Auto-Settle Daemon Has No Locking — Concurrent Settlement Race Condition**
   - Severity: high
   - Location: node/auto_epoch_settler.py:90-115 (get_unsettled_epochs + settle_epoch_via_api)
   - Description: The auto-settle daemon uses a simple loop with no file lock, database lock, or distributed mutex. If two instances run (e.g., systemd restart, container orchestration, operator error), both will read the same unsettled epochs and both will call `/rewards/settle` for the same epoch concurrently. The `/rewards/settle` API endpoint has no idempotency protection documented, meaning duplicate reward distribution is possible.
   - Reproduction:
     ```bash
     # Terminal 1:
     python node/auto_epoch_settler.py &
     # Terminal 2 (simultaneously):
     python node/auto_epoch_settler.py &
     # Both will detect the same unsettled epochs and call
     # POST /rewards/settle with the same epoch number
     ```
     The `CHECK_INTERVAL = 300` (5 minutes) provides a wide window for overlap during daemon restarts. No `fcntl.flock()` or SQLite advisory lock is used.

3. **Balance Check Defaults to "Sufficient Funds" on Database Error**
   - Severity: high
   - Location: node/claims_settlement.py:99-110 (check_rewards_pool_balance)
   - Description: When `check_rewards_pool_balance()` encounters a `sqlite3.Error`, it returns `(True, required_urtc)` — meaning "yes, funds are sufficient." This is an insecure fail-open pattern. If the database is locked, corrupted, or the `rewards_pool` table doesn't exist, settlement proceeds as if unlimited funds are available. The fallback at line 108 (`balance = required_urtc * 10`) compounds this by assuming a 10x buffer when the table is missing.
   - Reproduction:
     ```python
     # Simulate database error:
     result = check_rewards_pool_balance("/nonexistent/path.db", 1_500_000)
     assert result == (True, 1_500_000)  # Returns "sufficient" on error
     
     # Or with a locked database — sqlite3.OperationalError triggers
     # the except block which returns (True, required_urtc)
     ```
     Combined with Finding 1 (fake transaction signing), this means settlement can be triggered against any epoch, claims get marked "settled" with fake tx hashes, and no balance is actually deducted.

## Known failures of this audit
- **I did not test the `/rewards/settle` API endpoint directly** — only the Python client code. The server-side settlement logic in the node may have additional guards not visible from these files.
- **I did not check `node/rip_200_round_robin_1cpu1vote.py`'s `calculate_epoch_rewards_time_aged()` for the duplicate-epoch edge case** where epoch_enroll has stale data from a previous failed settlement.
- **I did not verify whether systemd/Docker configurations prevent multiple daemon instances** — the race condition in Finding 2 may be mitigated by deployment tooling not visible in the codebase.
- **I did not check whether the `/rewards/settle` endpoint has server-side idempotency** (e.g., checking `epoch_state.settled` before distributing). If it does, Finding 2 severity drops to medium.
- **My confidence is lower on Finding 1** because there may be environment variable guards or deployment configs (not in these files) that disable the random path in production.

## Confidence
- Overall confidence: 0.78
- Per-finding confidence: [0.85, 0.75, 0.80]

## What I would test next
- Run `python node/auto_epoch_settler.py` in two terminals against a test database to confirm duplicate settlement actually occurs (requires a running node or mock server)
- Check the `/rewards/settle` server endpoint for idempotency guards — if `epoch_state.settled` is checked before distributing rewards, Finding 2 is partially mitigated
- Test `check_rewards_pool_balance` with an actual locked SQLite database (e.g., `BEGIN EXCLUSIVE` in another connection) to confirm the fail-open behavior under realistic conditions
