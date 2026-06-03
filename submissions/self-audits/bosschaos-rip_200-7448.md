# Self-Audit Report: rip_200_round_robin_1cpu1vote.py

**File:** `node/rip_200_round_robin_1cpu1vote.py`
**Lines:** 719
**Commit:** fde7ed6
**Author:** BossChaos
**Wallet:** RTC6d1f27d28961279f1034d9561c2403697eb55602

---

## Vulnerability Summary

| # | Severity | Vulnerability | Location | CVSS 3.1 |
|---|----------|---------------|----------|----------|
| 1 | 🔴 HIGH | Griefable Block Producer Selection | Lines 415-434 | 8.0 |
| 2 | 🔴 HIGH | Stale Attestation Fallback in Delayed Settlement | Lines 585-612 | 7.8 |
| 3 | 🟠 MEDIUM | RIP-309 Active Check Selection is Fully Predictable | Lines 526-535 | 6.5 |
| 4 | 🟠 MEDIUM | Reward Distribution Rounding Bias | Lines 681-688 | 6.1 |
| 5 | 🟡 LOW | Miner ID Ordering Enables Position Manipulation | Lines 405-410 | 4.3 |

---

## Finding #1: Griefable Block Producer Selection (HIGH)

**Location:** `get_round_robin_producer()` — Lines 415-434

**Description:**

The block producer selection is fully deterministic and predictable:

```python
def get_round_robin_producer(slot: int, attested_miners: List[Tuple[str, str]]) -> str:
    producer_index = slot % len(attested_miners)
    return attested_miners[producer_index][0]
```

Given that:
1. The attested miner list is sorted alphabetically (`ORDER BY miner ASC`, line 409)
2. The slot number is public blockchain state
3. The number of attested miners is knowable from the database

Any attacker can compute the exact slot at which any specific miner will be the designated producer. This enables:

- **Targeted DoS**: An attacker can flood the network or the target miner's node exactly when they are supposed to produce a block, causing missed blocks
- **MEV exploitation**: Knowing the producer in advance allows front-running or sandwich attacks on transactions in the upcoming block
- **Slot stealing**: If the designated producer is offline or slow to respond, the next slot's producer effectively gets an extra block, creating an incentive to keep competitors offline

The `check_eligibility_round_robin()` function (lines 437-495) even helpfully tells each miner their `your_turn_at_slot`, making it trivial for miners to know exactly when they and their competitors will produce.

**Impact:** A motivated attacker can systematically disrupt specific miners' block production by targeting their known production slots, reducing their rewards and potentially driving them out of the network. This violates the "1 CPU = 1 Vote" fairness guarantee since some CPUs get fewer successful blocks than their turn allocation.

**Remediation:**
- Add a cryptographic commitment step: miners must commit to their readiness before the slot is revealed
- Implement a fallback mechanism: if the designated producer misses their slot, the next producer in rotation gets only a fraction of the reward (not the full block reward)
- Add slot-level VRF verification: the producer must prove they were selected, and the selection should incorporate an unpredictable element (e.g., hash of previous block + slot number)

---

## Finding #2: Stale Attestation Fallback in Delayed Settlement (HIGH)

**Location:** `calculate_epoch_rewards_time_aged()` fallback path — Lines 585-612

**Description:**

When `epoch_enroll` has no rows, the code falls back to a time-window query on `miner_attest_recent`:

```python
cursor.execute("""
    SELECT DISTINCT miner, device_arch, COALESCE(fingerprint_passed, 1) as fp,
           NULL as enrolled_weight,
           COALESCE(fingerprint_checks_json, '{}') as checks_json
    FROM miner_attest_recent
    WHERE ts_ok >= ? AND ts_ok <= ?
""", (epoch_start_ts - ATTESTATION_TTL, epoch_end_ts))
```

This fallback has the same issues identified in the `anti_double_mining.py` audit:
1. **Non-deterministic results**: If a miner re-attests between the epoch window and settlement time, their record in `miner_attest_recent` is updated (it's a rolling cache with `miner` as PRIMARY KEY). This changes the query results.
2. **Stale data**: Miners who were valid during the epoch but expired their attestation before settlement are silently dropped.
3. **New data inclusion**: Miners who attested after the epoch window but within `ATTESTATION_TTL` of the epoch start may be incorrectly included.

The code correctly logs a warning (lines 591-595) but doesn't prevent the non-deterministic settlement from proceeding.

**Impact:** Delayed settlement produces different reward distributions than immediate settlement, violating the fundamental guarantee that reward calculation is deterministic and reproducible. An attacker who can time their re-attestation to occur between epoch end and settlement could manipulate the reward pool distribution.

**Remediation:**
- Never fall back to `miner_attest_recent` for settlement; require `epoch_enroll` to have data
- If `epoch_enroll` is empty, return an error and require manual intervention
- Store a per-epoch snapshot of attestation data at epoch boundary time

---

## Finding #3: RIP-309 Active Check Selection is Fully Predictable (MEDIUM)

**Location:** Lines 526-535

**Description:**

```python
fp_checks = ['clock_drift', 'cache_timing', 'simd_identity',
             'thermal_drift', 'instruction_jitter', 'anti_emulation']
if prev_block_hash:
    nonce = hashlib.sha256(prev_block_hash + b"measurement_nonce").digest()
    seed = int.from_bytes(nonce[:4], 'big')
    active_checks = set(random.Random(seed).sample(fp_checks, 4))
else:
    active_checks = set(fp_checks)  # Fallback: all checks active
```

The RIP-309 rotating fingerprint check mechanism selects 4 of 6 checks per epoch using a seed derived from `prev_block_hash`. While this appears random, it's fully deterministic:

1. The `prev_block_hash` is public blockchain state (known to all participants)
2. `hashlib.sha256(prev_block_hash + b"measurement_nonce")` produces a fixed output
3. `random.Random(seed).sample(fp_checks, 4)` with a known seed produces a known subset

An attacker who knows which checks will be active can:
- **Optimize their attestation** to pass exactly those 4 checks while potentially failing the other 2
- **Target specific miners** whose weaknesses align with the active checks
- **Predict the exact reward impact** of the rotating checks before submitting their attestation

The fallback path (`prev_block_hash` is empty) enables ALL checks, which creates an inconsistency: epochs with a previous block use 4 checks, while the first epoch uses all 6.

**Impact:** Miners can game the rotating check system by pre-computing which checks will be active and optimizing their attestation accordingly. The rotating check mechanism provides the illusion of unpredictability but is trivially computable by anyone with access to the blockchain state.

**Remediation:**
- Use a future block hash (e.g., hash of block N-2) as the seed, so the active checks for epoch N are not knowable until after block N-2 is produced
- Use a verifiable random function (VRF) instead of SHA-256 hashing
- Log both active and inactive check results so failures are recorded even for inactive checks

---

## Finding #4: Reward Distribution Rounding Bias (MEDIUM)

**Location:** Lines 681-688

**Description:**

```python
for i, (miner_id, weight) in enumerate(eligible_miners):
    if i == len(eligible_miners) - 1:
        share = remaining  # Last miner gets remainder
    else:
        share = int((weight / total_weight) * total_reward_urtc)
        remaining -= share
```

Same vulnerability as `anti_double_mining.py`. The last miner in the iteration order receives all accumulated rounding remainders from the other miners' truncated shares. With N miners, each losing up to 0.999 uRTC to truncation, the last miner gains approximately (N-1) × 0.5 uRTC extra.

The iteration order is determined by the order of `eligible_miners`, which depends on the order of `epoch_miners`, which depends on either `epoch_enroll` ordering or `miner_attest_recent` ordering (both potentially non-deterministic across runs).

**Impact:** Non-deterministic reward amounts due to rounding bias concentrated on the last miner in the iteration order.

**Remediation:**
- Sort miners by a deterministic key before distribution
- Use proportional rounding (banker's rounding) instead of truncation
- Distribute rounding errors across all miners proportionally to their weight

---

## Finding #5: Miner ID Ordering Enables Position Manipulation (LOW)

**Location:** `get_attested_miners()` — Lines 395-412

**Description:**

The attested miner list is sorted alphabetically by miner ID (`ORDER BY miner ASC`). Since the round-robin producer selection uses `slot % len(attested_miners)` to determine the producer, the alphabetical ordering directly determines which miner produces at which slot.

An attacker who can choose their miner ID (e.g., by generating new keypairs) can position themselves at a specific point in the rotation. For example, by choosing a miner ID that sorts between two high-value targets, the attacker can ensure they produce blocks immediately before or after their targets.

This is a minor concern because:
- The rotation is deterministic regardless of ordering
- The attacker still gets exactly 1/N of the blocks
- However, it enables targeted griefing strategies when combined with Finding #1

**Impact:** Attackers can optimize their miner ID to achieve favorable positions in the round-robin rotation, potentially enabling more effective griefing or MEV strategies.

**Remediation:**
- Sort miners by a cryptographic hash of their ID (e.g., `SHA256(miner_id)`) instead of alphabetically
- Use a slot-dependent permutation to shuffle the order each epoch

---

## Conclusion

The `rip_200_round_robin_1cpu1vote.py` module implements a deterministic round-robin consensus mechanism with time-aged antiquity multipliers. The two HIGH-severity findings (griefable producer selection and stale attestation fallback) directly threaten the fairness and determinism guarantees of the consensus mechanism. The rotating fingerprint check system (RIP-309) provides an illusion of unpredictability that could be exploited by miners who pre-compute the active checks.

Priority fixes:
1. **Add cryptographic commitment to producer selection** — prevent griefing (Finding #1)
2. **Remove stale attestation fallback** — enforce deterministic settlement (Finding #2)
3. **Use future block hash for RIP-309 seed** — make active checks unpredictable (Finding #3)
4. **Fix rounding distribution** — deterministic reward amounts (Finding #4)
