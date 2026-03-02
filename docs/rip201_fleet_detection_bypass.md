# RIP-201 Fleet Detection Bypass

## Summary

This report demonstrates a black-box bypass of the deployed RIP-201 fleet immune system:

1. The server trusts client-supplied `X-Forwarded-For` as the miner source IP.
2. The fleet scorer treats missing optional fingerprint dimensions as "no evidence" instead of suspicious absence.
3. Timing correlation can be avoided by spacing attestations outside the 30-second window.

With those three behaviors combined, a coordinated 5-miner fleet on shared infrastructure can remain at `fleet_score = 0.0` for consecutive epochs while keeping full reward weight.

## Technique

### 1. Spoof IP clustering

`client_ip_from_request()` prefers the left-most `X-Forwarded-For` value over `REMOTE_ADDR` without validating that the request actually came from a trusted reverse proxy. A client can therefore choose the IP written into:

- `miner_attest_recent.source_ip`
- `ip_rate_limit.client_ip`
- RIP-201 `fleet_signals.subnet_hash`

This lets one host appear to come from many different /24 subnets.

### 2. Keep fingerprint checks valid but sparse

`validate_fingerprint_data()` requires `anti_emulation` and `clock_drift` for modern hardware, but `record_fleet_signals_from_request()` only records four similarity dimensions:

- `clock_drift_cv`
- `cache_latency_hash`
- `thermal_signature`
- `simd_bias_hash`

The similarity engine only flags a pair when there are at least two comparable dimensions and at least two matches. Submitting only the minimum valid checks leaves just one comparable dimension (`clock_drift_cv`), so fingerprint similarity never fires.

### 3. Avoid timing correlation

Spacing attestations by more than 30 seconds keeps the timing ratio below the correlation threshold.

## Reproduction

Run:

```bash
python tools/rip201_fleet_detection_bypass_poc.py
```

The PoC prints:

- a baseline scenario where a same-subnet shared-fingerprint fleet is flagged
- a bypass scenario where five miners remain clean for three consecutive epochs

Run the tests:

```bash
python -m pytest tests/test_rip201_fleet_bypass.py -v
```

## Impact

- A single operator can present a coordinated fleet as five independent miners.
- The fleet can stay under the `0.3` clean threshold.
- Because the PoC keeps `fleet_score = 0.0`, the effective multiplier remains unchanged.

## Recommended Fixes

1. Only trust `X-Forwarded-For` when `REMOTE_ADDR` belongs to an allowlisted reverse proxy.
2. Record the actual peer IP separately from forwarded headers and use the trusted peer IP for fleet detection.
3. Treat missing fingerprint dimensions as suspicious for modern miners instead of neutral.
4. Require a minimum fingerprint feature set for fleet scoring, not just attestation acceptance.
