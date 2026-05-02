# Self-Audit Report: arch_cross_validation.py

**File:** `node/arch_cross_validation.py`
**Lines:** 572
**Commit:** cabf0c4
**Author:** BossChaos
**Wallet:** RTC6d1f27d28961279f1034d9561c2403697eb55602

---

## Vulnerability Summary

| # | Severity | Vulnerability | Location | CVSS 3.1 |
|---|----------|---------------|----------|----------|
| 1 | 🔴 HIGH | No Enforcement — Validation is Security Theater | Lines 435-506 | 9.1 |
| 2 | 🔴 HIGH | Score Manipulation via Feature Omission | Lines 230-249, 336-343, 400-404 | 7.6 |
| 3 | 🟠 MEDIUM | Permissive Substring Architecture Matching | Lines 207-209 | 6.5 |
| 4 | 🟠 MEDIUM | Cache Latency Self-Report Bypass | Lines 237-248 | 6.1 |
| 5 | 🟡 LOW | No Anti-Emulation Enforcement | Lines 296-323 | 4.3 |

---

## Finding #1: No Enforcement — Validation is Security Theater (HIGH)

**Location:** `validate_arch_consistency()` — Lines 435-506

**Description:**

The `validate_arch_consistency()` function performs extensive cross-validation analysis and returns a numeric score (0.0-1.0) with detailed issue lists. However, **this function never rejects or penalizes miners** — it only returns a score. There is no enforcement logic anywhere in the file that:

1. Blocks miners scoring below a threshold
2. Reduces their rewards based on the validation score
3. Triggers any penalty mechanism when spoofing is detected
4. Logs violations for administrative review

```python
def validate_arch_consistency(...) -> Tuple[float, Dict[str, Any]]:
    # ... extensive scoring logic ...
    return overall_score, details  # Returns score, takes no action
```

The scoring thresholds (lines 488-505) define interpretations like "CONFIRMED_SPOOFED" and "LIKELY_SPOOFED" but these are purely advisory labels with no downstream consequences. The function is called, a score is computed, and nothing happens with the result.

**Impact:** The entire arch_cross_validation module is effectively dead security code. Even when a miner is detected as "CONFIRMED_SPOOFED" (score < 0.3), they still receive full rewards because no enforcement action is taken. This creates a false sense of security — the project believes it has architecture spoofing protection, but in reality, the validation is never enforced.

**Remediation:**
- Integrate `validate_arch_consistency()` into the reward distribution pipeline (`anti_double_mining.py`)
- Reject miners scoring below 0.5 (SUSPICIOUS threshold)
- Scale rewards proportionally to the validation score for miners between 0.5-0.8
- Log all scores below 0.7 to an audit table for manual review

---

## Finding #2: Score Manipulation via Strategic Feature Omission (HIGH)

**Location:** `extract_cache_features()` — Lines 230-249, `score_cache_consistency()` — Lines 336-343, `score_thermal_consistency()` — Lines 400-404

**Description:**

The scoring system penalizes missing or anomalous data with fixed deductions (-0.2 to -0.4 per dimension), but an attacker can strategically omit entire check categories to control their score. The weighted scoring formula (lines 483-486) combines five dimensions:

| Dimension | Weight | Penalty for Missing |
|-----------|--------|---------------------|
| SIMD consistency | 0.30 | -0.5 per issue |
| Cache consistency | 0.25 | -0.3 per issue |
| Clock consistency | 0.20 | -0.4 if CV=0 |
| Thermal consistency | 0.15 | -0.2 if drift too low |
| CPU brand consistency | 0.10 | -0.3 if mismatch |

**Attack Vector:** An attacker can omit `thermal_drift` and `cpu_brand` from their fingerprint entirely:
- Missing thermal → drift_pct defaults to 0 → penalty = -0.2 → thermal_score = 0.8
- Missing brand → no expected brands → brand_score = 1.0 (line 417-418)

Combined with fabricated SIMD and cache data matching the claimed profile:
- SIMD: 1.0 × 0.30 = 0.30
- Cache: 1.0 × 0.25 = 0.25
- Clock: 0.6 × 0.20 = 0.12 (slightly off to avoid detection)
- Thermal: 0.8 × 0.15 = 0.12
- Brand: 1.0 × 0.10 = 0.10
- **Total: 0.89 → "GOOD: minor anomalies within tolerance"**

An attacker claiming any architecture can achieve a "GOOD" rating by providing matching SIMD/cache data and omitting thermal/brand data.

**Impact:** Any miner can achieve a passing validation score by controlling which fingerprint features they report, bypassing the cross-validation entirely.

**Remediation:**
- Require ALL five dimensions to be present; reject if any are missing
- Penalize missing dimensions with score = 0.0, not partial deductions
- Set a minimum dimension count (e.g., 4/5) before computing the weighted average

---

## Finding #3: Permissive Substring Architecture Matching (MEDIUM)

**Location:** `normalize_arch()` — Lines 207-209

**Description:**

```python
for key in ARCHITECTURE_PROFILES:
    if key in arch_lower or arch_lower in key:
        return key
```

The fallback architecture matching uses bidirectional substring matching, which creates false positive mappings:

| Claimed Value | Maps To | Problem |
|---------------|---------|---------|
| "x86" | "modern_x86" or "vintage_x86" | First match in dict iteration order |
| "arm" | "arm64" | "arm" in "arm64" |
| "power" | "power8" | "power" in "power8" |
| "sparc" | "sparc" | Exact match (ok) |
| "apple" | "apple_silicon" | "apple" in "apple_silicon" |

This means an attacker claiming a vague architecture like "x86" could get mapped to different profiles depending on dictionary iteration order, potentially landing on a profile with wider acceptable ranges (e.g., "vintage_x86" has `cv_range: 0.0001-0.015` vs "modern_x86" with `cv_range: 0.0001-0.008`).

**Impact:** Non-deterministic architecture mapping allows attackers to benefit from whichever profile has the most permissive validation thresholds, especially for vague or partial architecture strings.

**Remediation:**
- Remove the substring matching fallback (lines 207-209)
- Return `None` for unrecognized architectures, forcing the caller to reject them
- If substring matching is needed for backward compatibility, require a minimum match confidence (e.g., >80% string overlap)

---

## Finding #4: Cache Latency Self-Report Bypass (MEDIUM)

**Location:** `extract_cache_features()` — Lines 237-248

**Description:**

The cache consistency validation relies entirely on miner-provided latency data:

```python
latencies = data.get("latencies", {})
if isinstance(latencies, dict):
    for level in ["4KB", "32KB", "256KB", "1024KB", "4096KB", "16384KB"]:
        key = f"{level}_present"
        features[key] = level in latencies and "error" not in latencies.get(level, {})
```

There is no actual cache timing measurement in this module. The code only validates that the **reported** latency values fall within expected ranges for the claimed architecture. An attacker running on any hardware (including an emulator or VM) can simply report latency values that match the target profile's expected ranges:

```json
{
  "cache_timing": {
    "data": {
      "latencies": {
        "4KB": {"random_ns": 1.0},
        "32KB": {"random_ns": 2.0},
        "256KB": {"random_ns": 5.0},
        "1024KB": {"random_ns": 10.0}
      },
      "tone_ratios": [2.0, 2.5, 2.0]
    }
  }
}
```

These values would pass validation for multiple architecture profiles because:
- The tone ratios fall within most profiles' `cache_tone_min`/`cache_tone_max` ranges
- The latency structure matches the expected cache hierarchy
- No actual timing measurement is performed to verify the reported values

**Impact:** Cache timing validation provides zero real security — it only validates self-reported data. An attacker on any hardware can pass cache consistency checks by reporting fabricated but plausible latency values.

**Remediation:**
- Perform actual cache timing measurements on the server side (challenge-response timing tests)
- Compare reported latencies against server-measured latencies for the same miner session
- Flag miners whose reported latencies are too precise (suggesting fabrication)
- Add statistical analysis: real cache latencies have variance; fabricated ones tend to be too clean

---

## Finding #5: No Anti-Emulation Enforcement (LOW)

**Location:** `score_simd_consistency()` — Lines 296-323

**Description:**

The architecture profiles define `disqualifying_features` that should catch emulators (e.g., a PowerPC emulator running on x86 would report both `has_altivec: True` and `has_sse2: True`). However, the score penalty for having a disqualifying feature is only -0.5 per feature (line 308):

```python
for feat in disqualifying:
    if simd_features.get(feat, False):
        issues.append(f"disqualifying_feature:{feat}")
        score -= 0.5
```

This means an emulator with 1-2 disqualifying features gets a SIMD score of 0.0-0.5, but the overall weighted score can still pass if other dimensions score well:
- SIMD: 0.5 × 0.30 = 0.15
- Cache: 1.0 × 0.25 = 0.25
- Clock: 1.0 × 0.20 = 0.20
- Thermal: 1.0 × 0.15 = 0.15
- Brand: 1.0 × 0.10 = 0.10
- **Total: 0.85 → "GOOD"**

Furthermore, there is no check for the `anti_emulation` feature in `extract_all_features()` — it's listed in the recognized check names (line 284) but never processed or validated.

**Impact:** Emulators running on modern hardware can pass architecture cross-validation with acceptable scores, defeating the purpose of architecture-based mining fairness.

**Remediation:**
- Process `anti_emulation` check data and reject miners failing emulation detection
- Make disqualifying SIMD features a hard rejection (score = 0) rather than a soft penalty
- Add emulator detection heuristics: check for impossible feature combinations (e.g., Altivec + AVX512 simultaneously)

---

## Conclusion

The `arch_cross_validation.py` module implements a comprehensive scoring framework for detecting architecture spoofing, but has a critical design flaw: **it never enforces its findings**. The validation results are computed but never acted upon, making the entire module effectively security theater. Additionally, the scoring system can be gamed through strategic feature omission and self-reported data fabrication, allowing determined attackers to achieve passing scores even on mismatched hardware.

Priority fix order:
1. **Integrate enforcement** — Connect validation scores to the reward distribution pipeline (Finding #1)
2. **Require all dimensions** — Reject fingerprints missing any validation dimension (Finding #2)
3. **Implement server-side cache timing** — Stop trusting self-reported latency data (Finding #4)
4. **Fix architecture matching** — Remove permissive substring fallback (Finding #3)
5. **Process anti-emulation** — Add emulation detection to the validation pipeline (Finding #5)
