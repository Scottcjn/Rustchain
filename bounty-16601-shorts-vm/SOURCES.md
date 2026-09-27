# Sources and Claim Map

Primary source:
- RustChain Unified API Reference: https://github.com/Scottcjn/Rustchain/blob/main/docs/API_REFERENCE.md

Claim map:

1. **RustChain exposes `POST /attest/submit`.**
   - Source: API Reference, section `POST /attest/submit`.

2. **The endpoint submits a hardware fingerprint for epoch enrollment.**
   - Source: API Reference, `POST /attest/submit` description.

3. **The attestation validates that the miner is running on genuine physical hardware rather than a VM.**
   - Source: API Reference, same endpoint description.

4. **Signed evidence is part of attestation.**
   - Source: API Reference authentication field for `POST /attest/submit`, documented as Ed25519 signature.

5. **Miner records expose hardware metadata including `device_arch`, `hardware_type`, and `antiquity_multiplier`.**
   - Source: API Reference, `GET /api/miners` response and field table.

Editorial guardrails used in this package:
- No statement that VM detection is perfect or impossible to bypass.
- No unsupported benchmark, hashrate, profit, or earnings claim.
- No claim that antiquity multiplier equals raw performance.
- No third-party visual assets are required.
