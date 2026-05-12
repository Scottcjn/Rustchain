# Harden the Chain: Attestation and Reward Security Assessment

**Repository:** RustChain
**Bounty:** [Harden the Chain security quest](https://github.com/Scottcjn/rustchain-bounties/issues/398)
**Contributor:** ctzxw520-lab
**RTC wallet name:** ctzxw520-lab
**Date:** 2026-05-12

## Scope

This review was performed as a local, good-faith source review under `SECURITY.md`.
No production endpoint was probed, no private data was accessed, and no funds were
moved. The review focused on:

- `/attest/submit` attestation intake and automatic epoch enrollment
- hardware fingerprint and anti-emulation controls
- hardware binding v2 serial plus entropy checks
- prior reward-downgrade regression coverage

## Summary

RustChain's current attestation path has several important hardening controls in
place:

- The attestation lifecycle requires miners to collect hardware evidence, submit
  it to `/attest/submit`, and enroll into epoch settlement before rewards are
  calculated (`docs/attestation-flow.md`, lines 17-45).
- Signed attestations are verified when `signature` and `public_key` are present,
  and signed payloads fail closed when Ed25519 verification is unavailable
  (`node/rustchain_v2_integrated_v2.2.1_rip200.py`, lines 3265-3303).
- Challenge nonce validation runs before fingerprint, binding, and enrollment
  logic, which limits direct attestation replay (`node/rustchain_v2_integrated_v2.2.1_rip200.py`, lines 3316-3353).
- Hardware binding v2 rejects sparse first-time entropy profiles and checks for
  cross-serial entropy collisions before binding a serial to a wallet
  (`node/hardware_binding_v2.py`, lines 137-225).
- Failed fingerprints are allowed to attest but receive only the minimum failed
  fingerprint weight, preserving liveness while limiting reward abuse
  (`node/rustchain_v2_integrated_v2.2.1_rip200.py`, lines 3497-3526 and 3610-3614).
- A previous reward downgrade class is covered by regression tests and fixed in
  current enrollment code (`node/rustchain_v2_integrated_v2.2.1_rip200.py`, lines 3619-3626).

## Step 1 Security Assessment

### `/attest/submit` Flow

The endpoint accepts a JSON object, validates payload shape, extracts miner,
nonce, device, signal, and fingerprint fields, then applies the security gates
in this order:

1. Signed attestation verification when signature material is present.
2. IP rate limiting.
3. Challenge nonce validation and replay rejection.
4. wallet review gate.
5. hardware binding v2 or legacy hardware binding.
6. OUI gate.
7. fingerprint replay and entropy collision checks.
8. final fingerprint validation and server-side VM checks.
9. attestation status persistence and automatic epoch enrollment.

The ordering is mostly sound: cheap request-shape checks happen first, replay
and binding gates run before enrollment, and failed fingerprint results cannot
receive normal hardware weight.

### Hardware Fingerprinting and Anti-Emulation

Hardware binding v2 extracts comparable entropy signals from clock drift, cache
timing, thermal drift, and instruction jitter. New bindings must provide at
least `MIN_COMPARABLE_FIELDS` non-zero entropy fields before the serial is
accepted (`node/hardware_binding_v2.py`, lines 16, 207-216). Collision checks
also require enough overlap on stored and current profiles, reducing false
positive collision decisions for sparse payloads (`node/hardware_binding_v2.py`,
lines 137-179).

The separate proof-of-antiquity score calculator applies a large penalty when
emulation is detected and adds only bounded bonuses for collected hardware
markers (`rustchain-poa/validator/score_calculator.py`). This is directionally
safe because the score does not rely on one marker alone.

### Epoch Rewards

The auto-enrollment path computes the current epoch, derives a verified device
family and architecture, applies rotating fingerprint checks, and stores a
fixed-point epoch weight. If the fingerprint fails, the weight is reduced to
`MIN_FAILED_FINGERPRINT_WEIGHT_UNITS`; otherwise the hardware weight is scaled
by the active check ratio (`node/rustchain_v2_integrated_v2.2.1_rip200.py`,
lines 3587-3626).

The use of `INSERT OR IGNORE` for `epoch_enroll` is important because it prevents
a later low-weight attestation in the same epoch from overwriting an earlier
high-weight enrollment.

## Step 2 Known Fix Reproduction

The prior vulnerability class was:

1. A miner first attests successfully and receives a high epoch weight.
2. The same miner later re-attests in the same epoch with a failed fingerprint.
3. If `miner_attest_recent` or `epoch_enroll` uses `INSERT OR REPLACE`, the later
   failed attestation downgrades the already-earned state.
4. Epoch settlement can then give the miner zero or near-zero reward despite an
   earlier valid attestation.

The regression test file documents both the vulnerable behavior and the fixed
behavior (`node/tests/test_attestation_overwrite_reward_loss.py`, lines 5-21,
99-156, and 162-256).

Current code mitigates this in two places:

- `record_attestation_success()` preserves `fingerprint_passed=1` with
  `MAX(miner_attest_recent.fingerprint_passed, excluded.fingerprint_passed)`
  (`node/rustchain_v2_integrated_v2.2.1_rip200.py`, lines 2189-2236).
- auto-enrollment uses `INSERT OR IGNORE INTO epoch_enroll`, preserving the first
  enrollment for the epoch (`node/rustchain_v2_integrated_v2.2.1_rip200.py`,
  lines 3619-3626).

## Finding: Low - Fingerprint Anomaly Detection Is Effectively Unreachable

**Severity:** Low
**Impact:** Monitoring blind spot, not a direct reward bypass
**Affected area:** `/attest/submit` replay-defense telemetry

In `_submit_attestation_impl()`, `fingerprint_passed` is initialized to `False`
before replay defense. The anomaly detection branch is guarded by
`if fingerprint_passed and not replay_blocked`, but final fingerprint validation
does not happen until later (`node/rustchain_v2_integrated_v2.2.1_rip200.py`,
lines 3404-3485 and 3497-3506). As a result, that anomaly detection branch will
not execute for a successful fingerprint in this control flow.

`record_fingerprint_submission()` also receives the pre-validation
`fingerprint_passed` value, so the stored `attestation_valid` field can be false
even when the later validator accepts the fingerprint (`node/hardware_fingerprint_replay.py`,
lines 456-495).

### Recommended Mitigation

Move final fingerprint validation before the anomaly-detection and submission
recording steps, or perform a second post-validation update:

- keep replay and nonce checks before validation;
- run `validate_fingerprint_data()` before anomaly detection;
- pass the final `fingerprint_passed` value into `record_fingerprint_submission()`;
- add a regression test asserting that a valid fingerprint reaches
  `detect_fingerprint_anomalies()` and records `attestation_valid=1`.

This is a defense-in-depth fix because existing replay and entropy collision
checks still operate on hashes before the anomaly telemetry branch.

## Verification

Local command on macOS/Unix-like host:

```bash
python3 -m pytest tests/test_hardware_binding_v2_security.py tests/test_attestation_regression.py node/tests/test_attestation_overwrite_reward_loss.py -q
```

Result:

```text
79 passed, 18 skipped in 1.81s
```

The first attempt with `python -m pytest ...` failed locally because `python` is
not installed under that command name in this environment. The same test set was
rerun with `python3` and passed on this local host.

This result is environment-specific. A Windows review host reported the same
logical pytest target with `python` and backslash paths as `68 passed, 18
skipped, 11 failed`; the failures were `PermissionError: [WinError 32]` in
`node/tests/test_attestation_overwrite_reward_loss.py::tearDown()` while
unlinking the temporary SQLite database. This report therefore does not claim a
portable clean pass for the full pytest command on Windows.

Portable syntax validation reported by review:

```bash
python -m py_compile node\hardware_binding_v2.py node\rustchain_v2_integrated_v2.2.1_rip200.py node\tests\test_attestation_overwrite_reward_loss.py tests\test_hardware_binding_v2_security.py tests\test_attestation_regression.py
```

Result: passed.

## Conclusion

The reviewed path shows meaningful hardening around attestation signatures,
nonce replay, entropy quality, hardware binding, failed-fingerprint reward
weighting, and enrollment downgrade prevention. The main follow-up from this
review is to move fingerprint anomaly telemetry after final fingerprint
validation so accepted attestations are recorded and monitored with their final
validation status.
