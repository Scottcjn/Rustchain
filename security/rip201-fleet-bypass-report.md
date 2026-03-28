# RIP-201 Fleet Detection Bypass — Security Report

**Bounty:** #491 (200 RTC)
**Target:** `rips/python/rustchain/fleet_immune_system.py`
**Severity:** High
**Researcher:** @B1tor
**RTC Wallet:** `RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`

---

## Executive Summary

RIP-201's fleet immune system can be completely defeated by a single attacker
operating 5+ miners on shared infrastructure. All three detection vectors
(IP clustering, fingerprint similarity, timing correlation) produce a score
of **0.0** when the attacker applies trivial evasion techniques described
below. The root cause is that `record_fleet_signals_from_request()` accepts
and stores all fingerprint fields exactly as the client supplies them, with
no server-side measurement or cross-validation.

A coordinated fleet of 5 miners operating in full bypass mode receives fleet
scores `< 0.3` (CLEAN) across 3+ consecutive epochs while drawing rewards
as if they were independent, organically diverse participants.

---

## Vulnerability Analysis

### Root Cause: Client-Side Fingerprint Trust

`record_fleet_signals_from_request()` in `fleet_immune_system.py` populates
the `fleet_signals` table entirely from request-submitted data:

```python
# fleet_immune_system.py  ─ lines ~160-200
clock_drift_cv = clock.get("cv")                          # ← client-supplied
cache_hash     = hashlib.sha256(cache_str.encode())...    # ← derived from client data
thermal_sig    = thermal.get("entropy", ...)              # ← client-supplied
simd_hash      = hashlib.sha256(simd_str.encode())...     # ← derived from client data
```

The server hashes whatever the client sends and stores the result. An attacker
who controls the client can supply arbitrary values — making every miner appear
to have a unique fingerprint regardless of the underlying hardware.

Additionally, the IP `subnet_hash` is derived from the IP address in the HTTP
request, which is trivially spoofable via `X-Forwarded-For` if the node trusts
proxy headers without strict validation.

---

## Bypass Techniques

### Technique 1: IP Subnet Diversification (Defeats 40% of composite score)

**Detection logic:**
```python
FLEET_SUBNET_THRESHOLD = 3   # 3+ miners on same /24 → signal
```

The `/24` subnet hash is computed with plain SHA-256 — no HMAC, no server
secret. Any miner reporting from a different `/24` contributes zero IP signal.

**Bypass:** Assign each fleet miner to a different `/24` subnet:
- Miner 0 → `10.0.0.x`
- Miner 1 → `10.0.1.x`
- Miner 2 → `10.0.2.x`
- Miner 3 → `10.0.3.x`
- Miner 4 → `10.0.4.x`

In cloud environments (AWS, GCP, Hetzner) this is trivially achieved with
per-instance public IPs. Behind a NAT or reverse proxy with configurable
`X-Forwarded-For`, it costs nothing at all.

**Result:** `ip_signal = 0.0` for every miner.

---

### Technique 2: Randomised Fingerprint Submission (Defeats 40% of composite score)

**Detection logic:**
```python
# _detect_fingerprint_similarity()  ─ requires 2+ matching hashes across miners
if total_hashes >= 2 and shared_hashes >= 2:
    matches += 1
```

Fingerprint similarity is computed by comparing:
1. `cache_latency_hash` — SHA-256 of `cache_timing.data` dict items
2. `simd_bias_hash`     — SHA-256 of `simd_identity.data` dict items
3. `clock_drift_cv`    — must be within 5% relative difference
4. `thermal_signature` — must be within 10% relative difference

All four values originate from the client's attestation payload. The server
never independently measures or re-derives them.

**Bypass:** Submit unique random values for every field on every attestation:

```python
import random, hashlib, time

def fake_fingerprint():
    return {
        "checks": {
            "clock_drift":   {"data": {"cv": random.uniform(0.01, 0.15)}},
            "cache_timing":  {"data": {str(random.random()): random.random()}},
            "thermal_drift": {"data": {"entropy": random.uniform(0.3, 0.9)}},
            "simd_identity": {"data": {str(random.random()): random.random()}},
        }
    }
```

Because every `cache_latency_hash` and `simd_bias_hash` is the SHA-256 of a
freshly generated random dict, the probability that any two miners share even
one hash is negligible. `clock_drift_cv` values drawn from a uniform
distribution are unlikely to fall within 5% of each other. The same is true
for `thermal_signature`.

**Result:** `fingerprint_signal = 0.0` for every miner.

---

### Technique 3: Staggered Attestation Timing (Defeats 20% of composite score)

**Detection logic:**
```python
FLEET_TIMING_WINDOW_S    = 30   # attestations within 30s = correlated
FLEET_TIMING_THRESHOLD   = 0.6  # 60%+ correlated = signal
```

Timing correlation is measured as the fraction of other miners whose
attestation falls within ±30 seconds of each miner's timestamp.

**Bypass:** Space each attestation more than 30 seconds apart:

```python
base_ts = int(time.time())
for i, miner in enumerate(fleet_miners):
    submit_attestation(miner, attest_ts=base_ts + i * 35)  # 35s gap
```

With 5 miners staggered at 35-second intervals, no two miners share a 30s
window. Every miner sees 0 correlated peers → ratio = 0.0.

**Result:** `timing_signal = 0.0` for every miner.

---

### Bonus: Minimum Miner Floor

```python
FLEET_DETECTION_MINIMUM = 4
```

Any epoch with fewer than 4 total miners short-circuits ALL detection:

```python
if not rows or len(rows) < FLEET_DETECTION_MINIMUM:
    return {row[0]: 0.0 for row in rows}
```

An attacker with only 3 miners (or who times epochs when total participation
is low) receives `fleet_score = 0.0` unconditionally — the detection
algorithms never even run.

---

## Combined Score Impact

| Technique              | Weight | Signal (with bypass) | Signal (no bypass) |
|------------------------|--------|----------------------|--------------------|
| IP Clustering          | 40%    | 0.0                  | 0.30–1.0           |
| Fingerprint Similarity | 40%    | 0.0                  | 0.35–1.0           |
| Timing Correlation     | 20%    | 0.0                  | 0.60–1.0           |
| **Composite Score**    | —      | **0.0000 (CLEAN)**   | **0.70+ (FLEET)**  |

No corroboration boost fires because no individual signal exceeds 0.3.

---

## Proof of Concept

See `security/rip201-fleet-bypass-poc.py` for a fully executable demonstration.

The PoC:
1. Creates an in-memory SQLite database with the real `ensure_schema()`.
2. Inserts 5 fleet miners **without** evasion — scores all `> 0.7`.
3. Inserts the same 5 miners **with** all three bypass techniques — scores
   all `< 0.05`.
4. Calls the real `compute_fleet_scores()` from the production module each time.

---

## Mitigations

### Fix 1: Server-Side Fingerprint Generation (Required)

Never accept fingerprint hashes from the client. Instead, issue a hardware
challenge at attestation time and compute the fingerprint server-side (or
verify a signed, challenge-bound measurement):

```python
# BEFORE (vulnerable)
cache_hash = hashlib.sha256(str(sorted(cache.items())).encode()).hexdigest()[:16]

# AFTER (server-side challenge binding)
challenge = generate_server_challenge(miner, epoch)
expected_hash = verify_signed_cache_measurement(payload, challenge)
if expected_hash is None:
    raise AttestationError("fingerprint binding failed")
cache_hash = expected_hash
```

See `rips/python/rustchain/rip201_server_patch.py` for an existing partial
implementation that moves in this direction.

### Fix 2: IP Verification via Connection Metadata (Required)

Never derive `subnet_hash` from HTTP headers. Use the socket-level remote
address:

```python
# BEFORE (spoofable)
ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)

# AFTER (connection-bound)
ip_address = request.environ.get("REMOTE_ADDR")   # or TCP socket peer address
```

If the node operates behind a trusted reverse proxy, pin the proxy IP and
extract the real client IP from a signed header with a shared secret.

### Fix 3: Stricter Minimum Threshold (Low effort)

Lower `FLEET_DETECTION_MINIMUM` from 4 to 2. A two-miner comparison is
sufficient to detect obvious clones. The current value of 4 creates an
undetected zone that collapses the entire immune system for small epochs.

```python
# BEFORE
FLEET_DETECTION_MINIMUM = 4

# AFTER
FLEET_DETECTION_MINIMUM = 2
```

### Fix 4: Attestation-Scoped Timing Nonces (Defense-in-depth)

Issue per-miner epoch nonces with a server-controlled timestamp embedded.
This prevents the attacker from choosing arbitrary `attest_ts` values to
avoid the timing correlation window.

### Fix 5: Cross-Epoch Fingerprint Consistency Checks (Defense-in-depth)

Track each miner's fingerprint hashes across epochs. A miner whose
`cache_latency_hash` changes every single epoch while its device arch stays
constant is a strong anomaly signal. Real hardware does not regenerate its
cache timing profile randomly between attestations.

---

## Disclosure Timeline

- **2026-03-28**: Discovered and reported via bounty #491
- **Coordinated disclosure** — full details shared with maintainers before
  public release

---

## References

- `rips/python/rustchain/fleet_immune_system.py` — vulnerable file
- `rips/docs/RIP-0201-fleet-immune-system.md` — specification
- `rips/python/rustchain/rip201_server_patch.py` — existing partial fix
- `tests/test_rip201_fleet_bypass.py` — existing test coverage
