# RIP-201 Fleet Score Manipulation — Security Report

**Bounty:** #494 — 150 RTC  
**Target:** `fleet_immune_system.py` — fleet detection scoring algorithm  
**Attack type:** Black-box score manipulation (no server-side changes)

## Summary

This report demonstrates four techniques to manipulate RIP-201 fleet scores,
allowing 10+ coordinated miners on shared infrastructure to maintain CLEAN
status (scores < 0.3) across multiple consecutive epochs while receiving
full epoch rewards.

## Vulnerability Analysis

### Fleet Score Composition

```
fleet_score = (ip_score × 0.4) + (fingerprint_score × 0.4) + (timing_score × 0.2)
```

With corroboration boost: if 2+ signals > 0.3, `score *= 1.3`.

### Core Weaknesses

1. **Client-controlled fingerprints** — Hardware fingerprint data is generated
   by the miner client and submitted as-is. The server cannot independently
   verify cache latency, SIMD profiles, or thermal signatures.

2. **IP-based clustering trusts headers** — The detector groups miners by
   /24 subnet prefix. Any proxy, VPN, or X-Forwarded-For header bypasses this.

3. **Fixed timing window** — The 30-second correlation window
   (`FLEET_TIMING_WINDOW_S = 30`) is static and known to attackers.

4. **Minimum threshold gate** — `FLEET_DETECTION_MINIMUM = 4` means
   any epoch with fewer than 4 signals per group returns score 0.0.

## Techniques

### Technique 1: IP Rotation (defeats 40% weight)

Each miner uses a unique /24 subnet via VPN exit nodes or proxy rotation.
The IP clustering detector groups by `subnet_hash` of the /24 prefix —
different /24s mean different groups, each with only 1 member.

```python
ip_address = f"198.{51 + miner_index}.{...}.{10 + miner_index}"
```

**Result:** IP clustering score → 0.0

### Technique 2: Fingerprint Variance (defeats 40% weight)

Two sub-techniques:

**2a. Minimal fingerprint:** Submit only `anti_emulation` + `clock_drift`
checks (the minimum for `all_passed: True`). With only 1 hashable dimension,
the similarity engine cannot reach the 2-match threshold needed for detection.

**2b. Diverse full fingerprint:** Submit all 4 check types but with unique
values per miner. Each miner gets different `cv`, `l1_hit_ns`, `entropy`,
and `profile` — ensuring `shared_hashes < 2` for any pair.

```python
# 2a: Minimal — only clock_drift varies
{"cv": 0.03 + miner_index * 0.007}

# 2b: Full diverse — all 4 dimensions unique
{"cv": unique, "l1_hit_ns": unique, "entropy": unique, "profile": unique}
```

**Result:** Fingerprint similarity score → 0.0

### Technique 3: Timing Stagger (defeats 20% weight)

Attestation timestamps are spaced using Poisson-distributed intervals with
mean gap of 45 seconds (minimum 35s). The detector's 30-second window
(`FLEET_TIMING_WINDOW_S`) catches at most 1-2 miners per window —
well below the 60% threshold for timing correlation.

```python
gap = max(35, random.expovariate(1.0 / 45))  # mean 45s, min 35s
```

**Result:** Timing correlation score → 0.0

### Technique 4: Threshold Exploitation

`FLEET_DETECTION_MINIMUM = 4` means the detector requires at least 4
signals in an epoch to produce any non-zero score. By splitting a fleet
into sub-groups of 3 (via distinct subnet groups or staggered registration),
each sub-group stays below the threshold.

**Result:** All scores → 0.0 for groups < 4

## PoC Results

### Baseline (no evasion) — 12 miners, same IP/fingerprint/timing
- Average fleet score: **> 0.5** (DETECTED)
- Reward multiplier: **severely penalized**

### Full manipulation — 12 miners, all 3 techniques applied
- Average fleet score: **< 0.05** (CLEAN)
- All miners below 0.3 threshold
- Sustained across **5 consecutive epochs**
- Full reward multiplier preserved (2.5x → ~2.5x)

## Recommended Mitigations

1. **Server-side fingerprint validation:** Don't trust client-submitted hashes.
   Implement challenge-response: server sends a nonce, client must produce
   hardware-derived proof that includes the nonce. This prevents replay and
   spoofing.

2. **Cross-epoch identity tracking:** Track miner identity across epochs
   using persistent identifiers (e.g., signed attestation keys). Detect
   miners that appear/disappear in correlated patterns.

3. **ASN/RTT correlation:** Instead of /24 subnet, use BGP ASN lookups
   and RTT fingerprinting to detect miners behind different VPN exits
   but same physical infrastructure.

4. **Dynamic timing window:** Randomize the correlation window per epoch
   (e.g., 15-60s) so attackers cannot predict the exact stagger needed.

5. **Minimum fingerprint dimensions:** Require all 4 fingerprint checks
   to produce valid data. Reject attestations with only 1-2 checks, or
   penalize sparse fingerprints with a suspicion score.

6. **Behavioral analysis:** Track work patterns (attestation frequency,
   epoch participation rate, reward claiming patterns) across time to
   detect coordinated fleet behavior that single-epoch analysis misses.

---

**PoC scripts:**
- `tools/rip201_fleet_score_manipulation.py` — Full simulation
- `tests/test_fleet_score_manipulation.py` — Automated verification

**Author:** B1tor  
**PAYOUT:** `RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`
