# Hardware Fingerprinting (RIP-PoA Anti-VM System)

## Abstract

RustChain is designed to reward real, physical hardware and to discount or reject virtualized environments that can cheaply scale without corresponding physical cost. To support Proof-of-Antiquity (PoA) rewards and the 1CPU=1Vote model, RustChain uses a hardware fingerprinting system that combines client-side measurements with server-side validation. This section describes the goals, threat model, signal pipeline, validation strategy, and limitations of the fingerprint subsystem.

## Goals

- Prevent virtual machines and emulators from earning the same rewards as real hardware.
- Make it expensive to spoof older or rarer architectures (PowerPC G4/G5, SPARC, etc.).
- Provide a verifiable basis for antiquity multipliers.
- Preserve decentralization: checks should run on commodity OS installs and not depend on proprietary hardware attestation.

## Threat Model

We consider an adversary who can:

- Run miners in VMs/containers and manipulate user-space output.
- Spoof device identifiers (e.g., serial numbers, model strings).
- Replay or synthesize fingerprint payloads.
- Attempt multi-wallet strategies to earn more than one wallet on the same host.

We assume an adversary cannot:

- Easily alter kernel-level behavior without incurring detectable artifacts in timing, device enumeration, or platform-specific signals.
- Persistently maintain strong spoofing across multiple independent checks without increasing operational cost.

## Fingerprint Data Model

Miners submit a `fingerprint` object containing a set of checks. The server supports two formats:

1. Structured format (preferred):

```json
{
  "checks": {
    "anti_emulation": {"passed": true, "data": {"paths_checked": [...], "vm_indicators": [...]}},
    "clock_drift": {"passed": true, "data": {"samples": 1000, "cv": 0.0123}},
    "simd_identity": {"passed": true, "data": {"x86_features": [], "altivec": true}},
    "rom_fingerprint": {"passed": true, "data": {"emulator_detected": false}}
  },
  "all_passed": true
}
```

2. Legacy boolean format (accepted with reduced confidence):

```json
{"checks": {"clock_drift": true, "anti_emulation": true}, "all_passed": true}
```

## Server-Side Validation Strategy

RustChain does not trust a client-reported `passed: true` without evidence. The node performs server-side validation over the raw data submitted for critical checks.

### Phase 1: Require Evidence for Critical Checks

Two checks are treated as high-signal:

- **Anti-emulation**: requires evidence such as scanned indicators, checked paths, or detected CPU flags.
- **Clock drift / timing variability**: requires a non-trivial sample count and variability statistics.

If these checks claim success without evidence, the node rejects the fingerprint.

### Phase 2: Cross-Validate Device Claims

The node cross-validates claimed device architecture against signals derived from fingerprint data. For example:

- A miner claiming **PowerPC** should not present **x86 SIMD features**.
- Vintage hardware is expected to exhibit higher timing drift than modern hosts.

These cross-checks are intended to raise the cost of spoofing by forcing an attacker to emulate multiple independent hardware characteristics.

### Phase 3: ROM Fingerprint (Retro Platforms)

When provided, a ROM fingerprint check can identify known emulator ROM signatures. If emulator detection triggers, the fingerprint fails.

### Phase 4: Hard vs Soft Failures

Some checks are treated as "soft" warnings (e.g., performance/timing heuristics that may vary across real hardware). Hard failures cause rejection; soft failures can reduce confidence or multiplier without hard rejection.

## Anti Multi-Wallet Strategy: Hardware Binding

Beyond fingerprint validation, RustChain includes a hardware binding mechanism that attempts to ensure **one physical machine corresponds to one miner wallet**. The binding logic constructs a `hardware_id` from:

- Source IP (as observed by the server)
- Device model/arch/family
- Core count
- Optional MAC list (when reported)
- Optional serial-like entropy (not trusted as the primary key)

This approach is designed to limit multi-wallet attacks from a single host. NAT environments can cause IP sharing; the system treats this as an acceptable tradeoff for home networks, and it can be tuned as the network grows.

## Security and Operational Considerations

- **Replay resistance**: fingerprints should be tied to fresh challenges/nonces where possible.
- **Rate limiting**: endpoints that create DB state must be rate-limited to mitigate spam/DoS.
- **Privacy**: avoid collecting raw identifiers unnecessarily; prefer hashed or epoch-scoped derivations.

## Limitations

- No purely software-based system can perfectly distinguish real hardware from sophisticated emulation.
- Timing-based checks can be noisy and may vary across OS versions and power states.
- IP-based binding can misclassify miners behind a shared NAT.

RustChain mitigates these limits by combining multiple checks, requiring evidence for high-signal checks, and by continuously updating validation rules as new bypass techniques appear.

## References

- RustChain node implementation: `node/rustchain_v2_integrated_v2.2.1_rip200.py`
- Fingerprint design notes: `node/README_FINGERPRINT_PREFLIGHT.md`
- Reference profiles: `node/fingerprint_reference_profiles/*`
