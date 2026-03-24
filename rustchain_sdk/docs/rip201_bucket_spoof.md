# RIP-201 Bucket Normalization Gaming

## Summary

This PoC demonstrates that a modern x86 host can be accepted by the server as a `G4` / `PowerPC` miner and routed into the `vintage_powerpc` reward bucket.

The core weakness is that the attestation path trusts `device_family` and `device_arch` enough to:

1. mark the attestation as valid,
2. enroll the miner with `G4` weight (`2.5`), and
3. let RIP-201 classify the miner into the `vintage_powerpc` bucket.

## Attack Path

### 1. Spoof the claimed hardware class

Submit:

- `device_family = "PowerPC"`
- `device_arch = "G4"`
- `cpu = "Intel Xeon Platinum"`

The `cpu` string is inconsistent with the claimed architecture, but the attestation flow does not reject it.

### 2. Provide only minimum fingerprint evidence

For vintage claims, `validate_fingerprint_data()` relaxes the required checks down to `anti_emulation` only. It does not require:

- PowerPC SIMD evidence
- cache timing profile
- thermal profile
- cross-check that the CPU claim is actually PowerPC-compatible

As a result, a sparse fingerprint with only `anti_emulation` passes.

### 3. Collect vintage bucket rewards

Once accepted:

- `miner_attest_recent.device_arch = G4`
- `epoch_enroll.weight = 2.5`
- `classify_miner_bucket("g4") = vintage_powerpc`

That is enough for RIP-201 equal-split rewards to treat the miner as a scarce vintage bucket participant.

## Reproduction

Run:

```bash
python -m pytest tests/test_rip201_bucket_spoof.py -v
python tools/rip201_bucket_spoof_poc.py
```

## Current Local Result

The PoC shows:

- the spoofed `Intel Xeon` / claimed `G4` attestation is accepted,
- the spoofed miner is enrolled with weight `2.5`,
- the spoofed miner lands in `vintage_powerpc`,
- in a 2-bucket epoch with 10 honest modern miners, the spoofed miner receives `550000 uRTC` while each honest modern miner receives `55000 uRTC`.

That is a **10x** per-miner reward advantage from bucket spoofing alone.

## Live Black-Box Validation

The same technique was also validated against the live node at `https://50.28.86.131`.

### Request sent

`POST /attest/submit` with:

- `device_family = "PowerPC"`
- `device_arch = "G4"`
- `cpu = "Intel Xeon Platinum"`
- fingerprint containing only the minimal `anti_emulation` check

### Observed live response

The server returned `200 OK` and accepted the contradictory claim:

```json
{
  "device": {
    "arch": "G4",
    "cpu": "Intel Xeon Platinum",
    "device_arch": "G4",
    "device_family": "PowerPC"
  },
  "fingerprint_passed": true,
  "ok": true,
  "status": "accepted"
}
```

### Public follow-up evidence

After the attestation, public endpoints reflected the spoofed vintage classification:

- `GET /api/badge/bucket-spoof-live-492a` returned `Active (2.5x)`
- `GET /api/miners` listed `bucket-spoof-live-492a` as:
  - `device_family = "PowerPC"`
  - `device_arch = "G4"`
  - `hardware_type = "PowerPC G4 (Vintage)"`
  - `antiquity_multiplier = 2.5`

That is black-box evidence that the deployed server accepts the false hardware class and exposes the spoofed vintage multiplier through public API surfaces.

## Recommended Fixes

1. Treat claimed legacy architectures as untrusted until the fingerprint proves architecture-specific traits.
2. Require `simd_identity` or equivalent PowerPC evidence for `g3/g4/g5` claims.
3. Reject obvious `cpu` / `device_arch` contradictions such as `Intel Xeon` + `G4`.
4. Classify miners into reward buckets from verified server-side features, not raw client-reported architecture strings.
