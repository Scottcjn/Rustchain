# Self-Audit: rips/python/rustchain/fleet_immune_system.py

## Wallet
RTC4642c5ee8467f61ed91b5775b0eeba984dd776ba

## Module reviewed
- Path: rips/python/rustchain/fleet_immune_system.py
- Commit: 487ed7885de075fa5f18eb5b73ef3f862aef35bf
- Lines reviewed: whole-file (~850 lines)

## Deliverable: 3 specific findings

1. **Hardcoded Admin Key Default Enables Authentication Bypass**
   - Severity: critical
   - Location: fleet_immune_system.py:654-655 (register_fleet_endpoints)
   - Description: Both `/admin/fleet/report` and `/admin/fleet/scores` endpoints authenticate via `X-Admin-Key` header compared against `os.environ.get("RC_ADMIN_KEY", "rustchain_admin_key_2025_secure64")`. If the `RC_ADMIN_KEY` environment variable is unset (common in development, testing, Docker default, or misconfigured production), the hardcoded fallback string `"rustchain_admin_key_2025_secure64"` becomes the valid admin credential. This string is visible in the public source code, meaning any attacker can authenticate as admin on fleet endpoints by reading the repo. The fleet report endpoint exposes fleet scores, IP subnet hashes, and detection signals — intelligence an attacker needs to craft fleet evasion strategies.
   - Reproduction: `curl -H "X-Admin-Key: rustchain_admin_key_2025_secure64" http://<target>/admin/fleet/report?epoch=1` — returns full fleet detection data without any valid admin credential when RC_ADMIN_KEY env var is unset.

2. **Fail-Open Arch Validation When cross_validation Module Is Unavailable**
   - Severity: high
   - Location: fleet_immune_system.py:189-197 (run_arch_validation_for_attestation)
   - Description: The `run_arch_validation_for_attestation()` function has a nested try/except ImportError that falls back to storing `validation_score=0.0, passed=False, bucket="modern"` when `arch_cross_validation` cannot be imported. This is a fail-closed default for the bucket assignment (correct), BUT the caller receives `(False, "modern")` which may be silently consumed without logging a warning. More critically, the validation result IS persisted to the DB with `passed=False`, meaning future calls to `get_validated_bucket()` will always return `"modern"` for that miner — even if the import failure was transient (e.g., a deployment race condition or missing dependency). Once the "modern" result is cached in `arch_validation_results`, the miner loses any vintage bonus permanently with no recovery path or re-validation trigger. A fleet operator could deliberately trigger this by timing submissions during deployments.
   - Reproduction: Deploy the node without `node/arch_cross_validation.py` in the Python path. Submit an attestation with `claimed_arch="g4"`. The miner is permanently locked to "modern" bucket even after the module becomes available, because `INSERT OR REPLACE` in `store_arch_validation_result` overwrites any prior record.

3. **Fleet Detection Bypass via Minimum Miner Threshold**
   - Severity: medium
   - Location: fleet_immune_system.py:46 and fleet_immune_system.py:402-404 (compute_fleet_scores)
   - Description: Fleet detection is gated by `FLEET_DETECTION_MINIMUM = 4`. In `compute_fleet_scores()`, if fewer than 4 miners have fleet signals for an epoch, ALL miners receive `fleet_score = 0.0` (no detection). `_detect_timing_correlation()` and `_detect_fingerprint_similarity()` also independently check this threshold and return 0.0 for everyone if below minimum. A fleet operator can exploit this by running exactly 3 fleet machines per epoch — enough to extract rewards but below the detection floor. The operator rotates which 3 machines attest each epoch, keeping each individual machine's fleet_score at 0.0 indefinitely. Combined with the bucket equal-split mode, 3 fleet machines in the "modern" bucket still capture 1/N of the reward pot with zero fleet penalty.
   - Reproduction: Run 3 miners with identical fingerprints and same /24 subnet. Submit attestations for the same epoch. Call `compute_fleet_scores()` — all return 0.0 despite identical hardware signatures and shared subnet. Increase to 4 miners and the same configuration triggers fleet detection with scores > 0.5.

## Known failures of this audit
- Did not test the actual Flask endpoint registration in a running server — findings are from static code analysis only
- Did not verify whether `arch_cross_validation.py` actually exists and is deployable — the import failure scenario is theoretical but plausible in containerized deployments
- Did not analyze the `rip_200_round_robin_1cpu1vote` module that is imported dynamically — there may be additional attack surface in the multiplier calculation
- Low confidence on the race condition aspect of Finding 2 (concurrent INSERT OR REPLACE) — SQLite write contention behavior depends on WAL mode configuration
- Did not assess whether the subnet hashing (SHA-256 truncated to 16 hex chars) has collision risks that could group unrelated miners

## Confidence
- Overall confidence: 0.78
- Per-finding confidence: [0.92, 0.70, 0.75]

## What I would test next
- Set up a local Rustchain node with `RC_ADMIN_KEY` unset and attempt to access `/admin/fleet/report` with the hardcoded key to confirm end-to-end exploitability
- Write an integration test that imports `fleet_immune_system` without `arch_cross_validation` in the path, submits an attestation, then restores the module and verifies the miner is stuck in "modern" bucket — this confirms the fail-open-then-stuck behavior
- Benchmark fleet detection with exactly 3 vs 4 miners sharing identical fingerprints to quantify the detection gap and determine if the threshold should be lowered to 2
