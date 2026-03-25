# SPDX-License-Identifier: MIT
# Red Team: Hardware Fingerprint Replay Attack Defense

Bounty #2276 — 150 RTC

## Overview

An attacker captures a legitimate G4 PowerBook fingerprint attestation and replays it from a modern x86 machine to fraudulently claim the 2.5x antiquity bonus.

This package contains both the **attack** and the **defense**.

## Files

| File | Purpose |
|---|---|
| `replay_attack_poc.py` | Attack: capture and replay fingerprint data |
| `replay_defense.py` | Defense: nonce-binding, freshness, cross-check, dedup |
| `test_replay_defense.py` | Tests proving the defense works |

## Attack Vector

Current `fingerprint_checks.py` validates that fingerprint data is within expected ranges, but does **not** check:
- Is this data from a previous session? (no replay detection)
- Was this data generated right now? (no freshness)
- Does the sender match the claimed hardware? (no cross-check)

**Cost to attacker:** near zero — one captured payload reused indefinitely.

## Defense Layers

1. **Nonce-binding**: Server issues a single-use cryptographic nonce. The miner must include an HMAC proving the fingerprint was generated AFTER receiving the nonce.
2. **Temporal correlation**: `attestation_time` must be within 5 minutes. `validate_fingerprint_freshness()` rejects stale data.
3. **Connection cross-check**: SIMD identity must match architecture. TLS fingerprint and IP stability are verified.
4. **Deduplication**: SHA-256 hash of hardware data. Same measurements → rejected within 24h window.

## Running Tests

```bash
cd security/redteam/
pip install pytest
pytest test_replay_defense.py -v
```

## Test Coverage

| Test | Assertion |
|---|---|
| Fresh fingerprint | ✅ ACCEPTED |
| Replayed fingerprint | ❌ REJECTED (dedup) |
| Modified replay (changed nonce, kept old data) | ❌ REJECTED (HMAC mismatch) |
| Stale fingerprint (2h old) | ❌ REJECTED (freshness) |
| No nonce | ❌ REJECTED (invalid nonce) |
| PowerPC with SSE | ❌ REJECTED (SIMD mismatch) |
| x86 with AltiVec | ❌ REJECTED (SIMD mismatch) |
| TLS 1.3 from pre-2010 hardware | ❌ REJECTED (TLS mismatch) |
| IP instability (15+ unique IPs) | ❌ REJECTED |

## Integration

To integrate `replay_defense.py` into the existing attestation pipeline:

```python
from replay_defense import NonceStore, FingerprintDedup, validate_attestation

nonce_store = NonceStore()
dedup_store = FingerprintDedup()

# Before attestation: issue nonce
nonce = nonce_store.issue(miner_id)

# On attestation submit: validate
result = validate_attestation(
    fingerprint=payload,
    nonce=nonce,
    claimed_hmac=payload["nonce_hmac"],
    nonce_store=nonce_store,
    dedup_store=dedup_store,
    connection_ip=request.remote_addr,
)
if not result.accepted:
    return {"error": result.summary()}, 403
```

Existing legitimate miners only need to:
1. Request a nonce before collecting fingerprint
2. Include `HMAC(nonce || drift_hash || cache_hash || jitter_hash)` in payload
3. Submit within 5 minutes of collection
