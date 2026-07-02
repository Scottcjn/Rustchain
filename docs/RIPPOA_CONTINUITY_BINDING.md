# RIP-PoA Continuity Binding Contract

This note turns the finding from #7105 into a narrow integration contract:
the raw crystal-rate signal can be used as a same-box continuity check, but
must not be treated as a per-unit identity signal.

## Non-Goals

- Do not replace `_compute_hardware_id`, serial numbers, MACs, or
  `IOPlatformUUID`.
- Do not claim that two same-model commodity machines can be separated by
  crystal ppm alone.
- Do not use kernel-calibrated clocks such as `mach_absolute_time` as evidence.

## Evidence Shape

`hardware_binding.continuity` should be a versioned optional object:

```json
{
  "version": 1,
  "arch": "x86_64",
  "probe": "rdtsc_raw",
  "ppm": -40.125,
  "temperature_c": 43.2,
  "duration_minutes": 45.0,
  "samples": 240,
  "source": "macbookair7,2-lab"
}
```

The assigned hardware ID remains authoritative. The continuity evidence is a
secondary guard that asks whether a later attestation is consistent with the
same enrolled board.

## Acceptance Rules

- Enrollment baselines must use `rdtsc_raw`.
- Baselines shorter than 30 minutes are invalid.
- Baselines with fewer than 120 samples are invalid.
- Candidates must match architecture and probe.
- A default delta of `<= 0.30 ppm` is treated as same-box continuity.
- Larger deltas should be reported as `possible_hardware_swap`, not as fraud by
  themselves. Thermal state, measurement bugs, and platform support still need
  operator review.

## Reference Helper

`tools/rippoa_continuity_binding.py` is a non-production reference helper. It
provides:

- `canonical_reading(...)` for stable serialization.
- `continuity_commitment(...)` for audit logs.
- `evaluate_continuity(...)` for pass/fail reasoning.
- `hardware_binding_continuity_evidence(...)` for the proposed extension shape.

The tests in `tests/test_rippoa_continuity_binding.py` lock the important
properties: raw `rdtsc` only, no per-unit identity claim, minimum baseline
quality, and stable commitments.

## Rollout Guidance

Treat this as an additive, opt-in extension:

1. Store continuity baselines only after an assigned hardware ID has already
   been established.
2. Keep old miners valid when the field is absent.
3. Version every schema change.
4. Start with observability-only warnings before enforcing any penalty.
5. Keep per-architecture policy separate; commodity x86 results do not imply
   G4, G5, POWER8, ARM, or server PPIN behavior.
