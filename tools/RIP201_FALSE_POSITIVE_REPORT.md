# RIP-201 False Positive Analysis — Security Report

**Bounty:** #493 — RIP-201 False Positive Testing (100 RTC)  
**Target:** `fleet_immune_system.py` — fleet detection scoring  
**Goal:** Identify realistic scenarios where legitimate miners are incorrectly penalized

## Executive Summary

Testing 6 realistic scenarios found **5 produce false positives** where
genuinely independent miners receive fleet penalties. The most severe case
(cloud hosting) penalizes all 5 miners with scores up to 0.55, causing
~22% reward decay on legitimate operations.

## Scenarios Tested

### 🚨 Scenario 1: University Campus (6 students, 4 penalized)

**Setup:** 6 students mining from same university campus. Same /24 subnet
(campus WiFi routes all through one gateway). Different personal laptops,
attestation times cluster during evening study hours.

| Miner | Score | Penalized | Why |
|-------|-------|-----------|-----|
| student-0..5 | 0.30–0.42 | 4 of 6 | IP clustering (same /24) triggers 40% signal |

**Root cause:** IP clustering treats any /24 group with 4+ miners as fleet.
University networks routinely share /24 blocks across hundreds of independent users.

### 🚨 Scenario 2: Cloud Hosting (5 miners, ALL penalized)

**Setup:** 5 independent people each running a miner on their own AWS EC2
instance (c5.xlarge) in us-east-1. Same /24 allocation + similar instance
types = similar SIMD profiles and cache timing.

| Miner | Score | Why |
|-------|-------|-----|
| aws-0..4 | 0.49–0.55 | IP clustering + fingerprint similarity (same instance type) |

**Root cause:** This is the worst false positive — **two signals corroborate**
(IP + fingerprint), triggering the 1.3× boost. Score jumps from ~0.42 to ~0.55.
Completely independent miners receive MODERATE penalties.

### 🚨 Scenario 3: Coworking Space (4 freelancers, 3 penalized)

**Setup:** 4 independent freelancers mining from same coworking space WiFi.
Different personal machines but same /24 and work-hour attestation timing.

| Miner | Score | Why |
|-------|-------|-----|
| cowork-0..3 | 0.26–0.36 | IP clustering, borderline timing |

**Root cause:** 4 miners = exactly `FLEET_DETECTION_MINIMUM`. Barely crosses
the threshold. One more freelancer arrives and scores spike.

### ✅ Scenario 4: ISP CGNAT (8 homes, 0 penalized)

**Setup:** 8 independent households behind carrier-grade NAT. Same /24 visible
IP but completely different hardware and spread timing (2-hour evening window).

**Result:** All scores 0.22 (below 0.3). IP clustering fires but fingerprint
diversity + timing spread keep composite below threshold.

**Why it works:** Single signal (IP only) without corroboration stays manageable.

### 🚨 Scenario 5: Same Hardware Model (5 students, ALL penalized)

**Setup:** 5 students in different cities with identical MacBook M2. Different
ISPs (different /24 subnets), well-spread timing (4-hour window), but
IDENTICAL hardware fingerprints.

| Miner | Score | Why |
|-------|-------|-----|
| macbook-0..4 | 0.32 | Fingerprint similarity = 1.0 (all 4 hashes match) |

**Root cause:** `_compute_fingerprint_similarity()` counts matching hashes.
Same laptop model = same `cache_latency_hash`, `simd_bias_hash`,
`clock_drift_cv` bucket, and `thermal_signature`. 4/4 match = maximum
similarity score. Even with different IPs and timing, the 40% fingerprint
weight alone pushes past 0.3.

**This is particularly unfair:** Popular hardware models (MacBook M2,
ThinkPad T14, etc.) will inherently produce identical fingerprints across
thousands of independent users.

### 🚨 Scenario 6: Timezone Clustering (10 miners, 5 penalized)

**Setup:** 10 independent miners across a country. Different IPs, different
hardware. All run cron jobs at same local time → attestation timestamps
cluster within the 30-second detection window by coincidence.

| Miner | Score | Why |
|-------|-------|-----|
| tz-0..9 | 0.10–0.52 | Timing correlation fires when >60% attest within window |

**Root cause:** Fixed 30-second `FLEET_TIMING_WINDOW_S` is too narrow.
Real-world attestation patterns naturally cluster around clock boundaries
(`:00`, `:15`, `:30`, `:45` cron jobs are extremely common).

## Impact Assessment

| Scenario | Miners | Penalized | Max Score | Revenue Loss |
|----------|--------|-----------|-----------|-------------|
| University Campus | 6 | 4 (67%) | 0.42 | ~17% |
| Cloud Hosting | 5 | 5 (100%) | 0.55 | ~22% |
| Coworking Space | 4 | 3 (75%) | 0.36 | ~14% |
| ISP CGNAT | 8 | 0 (0%) | 0.22 | 0% |
| Same Hardware | 5 | 5 (100%) | 0.32 | ~13% |
| Timezone Cluster | 10 | 5 (50%) | 0.52 | ~21% |

**Total estimated affected miners in production:** Any miner on shared
infrastructure (university, cloud, corporate, mobile ISP) or with popular
hardware models is at risk.

## Recommended Mitigations

### 1. IP Clustering: Use ASN instead of /24

**Problem:** /24 subnet grouping catches unrelated users behind same gateway.
**Fix:** Group by BGP ASN (Autonomous System Number). A university is one ASN,
but its students aren't a fleet. Set minimum group size per-ASN higher
(e.g., 20 for known ISP ASNs vs 4 for datacenter ASNs).

### 2. Fingerprint Similarity: Normalize by hardware popularity

**Problem:** Popular hardware models produce identical fingerprints.
**Fix:** Weight fingerprint similarity by hardware rarity.
`adjusted_score = raw_score × (1 / log2(population_of_hardware_class))`.
Common hardware (M2, x86_64-avx2) gets lower weight. Exotic hardware
(POWER8, SPARC) retains full weight.

### 3. Timing Correlation: Use randomized jitter window

**Problem:** Fixed 30-second window catches cron scheduling coincidences.
**Fix:** (a) Expand window to 120s to reduce cron collisions.
(b) Server adds random per-miner jitter before comparing timestamps.
(c) Require sustained timing correlation across 3+ epochs before scoring.

### 4. Corroboration Boost: Require 3 signals, not 2

**Problem:** 2-signal corroboration (1.3× boost) is too aggressive.
IP + fingerprint = 80% of the composite score, and the boost pushes
borderline cases into penalty territory.
**Fix:** Only apply corroboration boost when all 3 signals exceed 0.3.
This eliminates the cloud hosting false positive entirely.

### 5. Graduated Minimum Threshold

**Problem:** `FLEET_DETECTION_MINIMUM = 4` is a hard cliff.
3 miners = score 0.0, 4 miners = immediate full scoring.
**Fix:** Gradual ramp: score × `min(1.0, (count - 3) / 5)`.
This means 4 miners get 20% of full score, 8 miners get full score.

### 6. Miner Identity Attestation (long-term)

**Problem:** All signals are environmental (IP, hardware, timing) — they
can't distinguish "same person" from "same environment."
**Fix:** Require miners to register a persistent identity key. Fleet
detection then first checks if miners share identity infrastructure
(same registration email domain, same payment wallet patterns, correlated
online/offline behavior) before applying environmental scoring.

---

**PoC scripts:**
- `tools/rip201_false_positive_report.py` — Full simulation (6 scenarios)
- `tests/test_false_positive_scenarios.py` — Automated verification (5 tests)

**Author:** B1tor  
**PAYOUT:** `RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`
