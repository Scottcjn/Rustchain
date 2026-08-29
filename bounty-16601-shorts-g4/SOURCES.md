# Sources and Claim Map

## Source 1 — RustChain Unified API Reference
https://github.com/Scottcjn/Rustchain/blob/main/docs/API_REFERENCE.md

Used for:
- RustChain exposes `GET /api/miners` with miner hardware details.
- The documented example includes a PowerPC G4 miner.
- The example lists `antiquity_multiplier: 2.5` for that G4.
- The API reference identifies attestation as a first-class API area.

## Source 2 — RustChain project
https://github.com/Scottcjn/Rustchain

Used for:
- Project identity and canonical source-code link.
- Public implementation context for Proof of Antiquity / attestation.

## Source 3 — RustChain public site
https://rustchain.org

Used for:
- Final CTA and canonical public project destination.

## Claim boundaries
This package deliberately does **not** claim:
- that a G4 is faster than a modern CPU;
- that any machine is guaranteed to earn a particular amount of RTC;
- that the 2.5x figure is a performance benchmark;
- that hardware attestation is impossible to spoof.

The 2.5x value is presented only as the antiquity multiplier in the current public API-reference example.
