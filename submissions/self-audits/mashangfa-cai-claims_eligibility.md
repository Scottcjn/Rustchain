# Self-Audit: node/claims_eligibility.py

## Wallet
RTC4642c5ee8467f61ed91b5775b0eeba984dd776ba

## Module reviewed
- Path: node/claims_eligibility.py
- Commit: 1841b902db3ea7ccf4d4ff6d29926a98f81dba18
- Lines reviewed: whole-file (397 lines)

## Deliverable: 3 specific findings

1. **Fleet Immune System Bypass via Silent Import Failure**
   - Severity: high
   - Location: node/claims_eligibility.py:48-58
   - Description: When `fleet_immune_system` module fails to import, the code defines a mock `get_fleet_status_for_miner` that always returns `fleet_flagged: False` and `penalty_applied: False`. If a miner is flagged by RIP-0201 for fleet/collusion behavior, but the import fails for any reason (missing dependency, version mismatch, filesystem error), the flagged miner will still pass eligibility checks and claim rewards. The fallback completely defeats the fleet detection system without any warning or logging.
   - Reproduction:
     1. Deploy node without `fleet_immune_system.py` in the Python path, or rename it temporarily
     2. Submit a claim for a miner that should be fleet-flagged
     3. `check_claim_eligibility()` returns `eligible: True` because the mock returns `penalty_applied: False`
     4. Fleet penalty check at line 349-354 passes silently
   - Fix: Raise `RuntimeError` on import failure instead of silently degrading. Or at minimum, log a CRITICAL warning and set `eligible=False` when fleet module is unavailable and cannot verify status.

2. **TOCTOU Race Condition in Duplicate Claim Prevention**
   - Severity: medium
   - Location: node/claims_eligibility.py:193-210 (check_pending_claim) and lines 359-362 (usage in check_claim_eligibility)
   - Description: `check_pending_claim` performs a SELECT query to check for existing claims, but there is no database-level unique constraint, row-level lock, or `INSERT ... ON CONFLICT` pattern to prevent two concurrent requests from both passing the check and both inserting claims for the same miner/epoch. Under concurrent load, a miner could submit the same claim twice and receive double rewards.
   - Reproduction:
     1. Send two simultaneous `check_claim_eligibility` + claim submission requests for the same miner_id and epoch
     2. Both calls execute `check_pending_claim` before either inserts a new claim row
     3. Both return `no_pending_claim: True`
     4. Both submissions proceed, resulting in duplicate reward payouts
   - Fix: Add a UNIQUE constraint on `(miner_id, epoch)` in the claims table, and use `INSERT OR IGNORE` or `INSERT ... ON CONFLICT DO NOTHING` at the claim submission layer. Consider `BEGIN IMMEDIATE` transactions for the check-and-insert sequence.

3. **No Cryptographic Signature Verification — Claim Impersonation**
   - Severity: critical
   - Location: node/claims_eligibility.py:263-376 (check_claim_eligibility, entire function)
   - Description: The eligibility verification flow validates attestation status, epoch participation, fingerprint, wallet registration, and fleet status, but **never requires or verifies a cryptographic signature** from the miner. The only identifier is `miner_id`, which follows a predictable format (`^[a-zA-Z0-9_-]+$`). An attacker who discovers or guesses a miner_id can check eligibility and — if the downstream claim submission endpoint similarly lacks signature verification — submit claims on behalf of any miner, redirecting rewards to their own wallet. The wallet_address is fetched from the DB but never verified against the claim submitter's identity.
   - Reproduction:
     1. Enumerate miner IDs (they follow patterns like `n64-<name>-unit<N>`)
     2. Call `check_claim_eligibility(db_path, "n64-victim-unit1", epoch, current_slot, current_ts)`
     3. If eligible, submit a claim with a different wallet address (if the submission endpoint doesn't cross-check)
     4. Rewards are sent to the attacker's wallet
   - Fix: Require a signed message (e.g., `sign(miner_id || epoch || wallet_address)`) verified against the miner's registered public key. The eligibility check should include `verify_signature(miner_pubkey, message, signature)` as a mandatory step. The wallet in the claim must match the wallet that was signed over.

## Known failures of this audit
- Could not test the actual claim submission endpoint (`submit_claim` function not present in this module) — the signature gap may be mitigated downstream, but the eligibility module itself provides no cryptographic guarantees
- Did not verify whether the claims table has a UNIQUE constraint in the actual schema (the code creates a test table without one, suggesting it may not exist)
- Could not test `rewards_implementation_rip200` integration — the fallback reward calculation (line 221-236) may have different security properties than the primary path
- Did not review the `fleet_immune_system` module to confirm the severity of bypassing it
- Low confidence on the TOCTOU finding's exploitability in production without knowing the claim submission concurrency model

## Confidence
- Overall confidence: 0.75
- Per-finding confidence: [0.85, 0.70, 0.80]

## What I would test next
- Review the actual claim submission endpoint to verify whether signature verification happens at the submission layer (if so, Finding 3 drops to medium)
- Check the production claims table schema for UNIQUE constraints on (miner_id, epoch)
- Fuzz the `miner_id` parameter with SQL injection payloads (parameterized queries appear safe, but edge cases in SQLite binding with unusual unicode could be tested)
