# Self-Audit Report: anti_double_mining.py

**File:** `node/anti_double_mining.py`
**Lines:** 1,035
**Commit:** f891b9b
**Author:** BossChaos
**Wallet:** RTC6d1f27d28961279f1034d9561c2403697eb55602

---

## Vulnerability Summary

| # | Severity | Vulnerability | Location | CVSS 3.1 |
|---|----------|---------------|----------|----------|
| 1 | 🔴 HIGH | Fingerprint Profile Spoofing | Lines 68-110 | 8.2 |
| 2 | 🔴 HIGH | Stale Attestation Data in Fallback | Lines 182-207, 366-388 | 7.8 |
| 3 | 🟠 MEDIUM | SQL Injection via Dynamic Placeholders | Lines 305-312 | 6.5 |
| 4 | 🟠 MEDIUM | Reward Distribution Rounding Manipulation | Lines 553-558 | 6.1 |
| 5 | 🟡 LOW | Duplicate Detection Only Checks Same Epoch | Lines 134-255 | 4.3 |

---

## Finding #1: Fingerprint Profile Spoofing (HIGH)

**Location:** `normalize_fingerprint()` — Lines 68-110

**Description:**

The `normalize_fingerprint()` function extracts only a small subset of fields from the fingerprint profile to build the machine identity hash: `clock_cv`, `clock_mean`, `thermal_var`, `cache_ratio`, and `cpu_serial`. An attacker who can control their attestation output can craft a fingerprint profile that matches another machine's identity by providing identical values for these specific fields.

**Attack Vector:**
```
Machine A has: clock_cv=0.001, clock_mean=100.0, cpu_serial="SERIAL-A"
Attacker creates fake attestation with same values → same identity_hash
Attacker's miner_id gets grouped with Machine A → only one reward per pair
```

This is particularly dangerous because:
- The `cpu_serial` field is optional — if absent, identity is based only on clock/thermal/cache metrics which are easier to replicate
- The `round()` function limits precision, increasing collision probability
- No cryptographic binding between hardware and attestation key

**Impact:** Attacker can create duplicate miner IDs that get grouped with legitimate miners, potentially claiming the representative position (highest entropy_score) and stealing rewards from the original machine owner.

**Remediation:**
- Include the raw attestation public key in the identity hash computation
- Add additional hardware-specific fields that are harder to spoof (e.g., TPM measurements, CPU microcode version)
- Reject attestations with `cpu_serial` set to known test/placeholder values

---

## Finding #2: Stale Attestation Data in Fallback Path (HIGH)

**Location:** `detect_duplicate_identities()` fallback — Lines 182-207, `get_epoch_miner_groups()` fallback — Lines 366-388

**Description:**

When `epoch_enroll` has no rows, the code falls back to querying `miner_attest_recent` with a time window filter. This introduces a critical data consistency issue:

```python
# Line 190-206
cursor.execute("""
    SELECT miner, device_arch, fingerprint_passed, entropy_score, ...
    FROM miner_attest_recent
    WHERE ts_ok >= ? AND ts_ok <= ?
""", (epoch_start_ts, epoch_end_ts))
```

The `miner_attest_recent` table is a rolling cache that gets updated as miners re-attest. When settlement is delayed (common under load), the time-window query may:
1. **Miss miners** who attested before `epoch_start_ts` but are valid for the epoch
2. **Include stale miners** who attested in the window but were deregistered before settlement
3. **Produce non-deterministic results** — re-running settlement on the same epoch can yield different miner lists if attestations were updated between runs

**Impact:** Non-deterministic reward distribution. Running settlement twice on the same epoch could produce different results, enabling double-spend or reward theft if an attacker can trigger a re-settlement after manipulating attestation data.

**Remediation:**
- Never fall back to `miner_attest_recent` for settlement; instead, store a per-epoch snapshot of attestation data at enrollment time
- Add a `settlement_locked` flag to prevent re-settlement after initial completion
- Include epoch number in the attestation query as a hard filter

---

## Finding #3: SQL Injection via Dynamic Placeholder Construction (MEDIUM)

**Location:** `select_representative_miner()` — Lines 305-312

**Description:**

```python
placeholders = ",".join("?" * len(miner_ids))
cursor.execute(f"""
    SELECT miner, entropy_score, ts_ok
    FROM miner_attest_recent
    WHERE miner IN ({placeholders})
    ORDER BY entropy_score DESC, ts_ok DESC, miner ASC
""", miner_ids)
```

While the miner_ids are passed as parameters (not directly interpolated), the dynamic placeholder construction creates a code injection surface. If `miner_ids` contains more entries than expected (e.g., via a crafted database state with thousands of duplicate miner IDs for one machine), the SQL query could exceed SQLite's `SQLITE_MAX_VARIABLE_NUMBER` (default 32,766) or cause a DoS via excessive query size.

Additionally, the f-string for the SQL template means any future modification to the query structure could accidentally introduce interpolation of user-controlled data.

**Impact:** Potential DoS via query size exhaustion. In a worst-case scenario, an attacker who can register many miner IDs under one machine identity could cause settlement to fail with a SQLite error, halting reward distribution for the entire epoch.

**Remediation:**
- Batch the query: split `miner_ids` into chunks of ≤1000 per query
- Use a temporary table approach for large miner groups
- Replace f-string SQL with a constant query template

---

## Finding #4: Reward Distribution Rounding Manipulation (MEDIUM)

**Location:** `calculate_anti_double_mining_rewards()` — Lines 553-558

**Description:**

```python
for i, (miner_id, weight) in enumerate(positive_weight_miners):
    if i == len(positive_weight_miners) - 1:
        share = remaining  # Last miner gets the remainder
    else:
        share = int((weight / total_weight) * total_reward_urtc)
        remaining -= share
```

The order of miners in `positive_weight_miners` is determined by dictionary iteration order of `representative_map`, which is insertion-ordered based on `miner_groups` iteration. This means:
- The "last miner" (who gets the rounding remainder) is not deterministic across runs if the insertion order varies
- An attacker who can control the insertion order (by timing their attestation) can ensure they are the last miner and receive a larger share due to accumulated rounding remainders
- With many miners, the accumulated rounding error could be significant (e.g., 0.999 uRTC per miner × N miners)

**Impact:** Non-deterministic reward amounts. An attacker could potentially extract ~N × 1 uRTC extra by being the last miner in the distribution loop, where N is the number of other miners.

**Remediation:**
- Sort miners by a deterministic key (e.g., miner_id hash) before distribution
- Use banker's rounding (`round()`) instead of `int()` truncation
- Distribute rounding errors proportionally rather than dumping all remainder on the last miner

---

## Finding #5: Duplicate Detection Only Checks Within Same Epoch (LOW)

**Location:** `detect_duplicate_identities()` — Lines 134-255

**Description:**

The duplicate detection function only checks for miners with the same machine identity within a single epoch. It does not detect or penalize miners who:
1. Run one miner ID per epoch but rotate identities across epochs
2. Use different hardware fingerprints each epoch to appear as distinct machines

This means the anti-double-mining enforcement only catches "horizontal" duplication (multiple miner IDs in one epoch) but not "vertical" duplication (one miner ID per epoch, but the same machine earning rewards across many epochs with different identities).

**Impact:** Reduced effectiveness of anti-double-mining enforcement. A sophisticated attacker could still earn multiple rewards by rotating their machine identity between epochs, though this requires more effort than simple same-epoch duplication.

**Remediation:**
- Maintain a persistent mapping of historical machine identities
- Flag machines whose identity changes between epochs for manual review
- Add cross-epoch attestation correlation using stable hardware characteristics

---

## Conclusion

The `anti_double_mining.py` module implements a reasonable first-pass approach to preventing double-mining, but has several critical gaps in its fingerprint-based identity system and settlement determinism guarantees. The two HIGH-severity findings (fingerprint spoofing and stale data fallback) should be prioritized as they directly enable reward theft.
