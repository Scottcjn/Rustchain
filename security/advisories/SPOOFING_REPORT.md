# Security Advisory: Bypass of Anti-Double-Mining Enforcement via Hardware Fingerprint Spoofing

## Severity: High/Critical
## Component: `node/anti_double_mining.py` and `/attest/submit` endpoint

### Description
The Anti-Double-Mining system (Issue #1449) is designed to ensure that "one physical machine = one reward per epoch". It achieves this by computing a `machine_identity_hash` based on hardware characteristics (CPU serial, clock drift, thermal variance, etc.).

However, these hardware characteristics are provided by the client in the `/attest/submit` POST request. The server does not verify the authenticity of these metrics (e.g., via a signed hardware report or TEE attestation). Consequently, a malicious actor can spoof these values by sending randomized fingerprints for each miner ID they control.

This allows a single physical machine to appear as multiple distinct machines, completely bypassing the anti-double-mining logic and claiming multiple rewards per epoch.

### Vulnerable Code Path
1. **Data Entry**: `node/rustchain_v2_integrated_v2.2.1_rip200.py` receives the `fingerprint` object from the client and stores it in the database without verification.
2. **Identity Computation**: `node/anti_double_mining.py` -> `compute_machine_identity_hash()` (Line 47) uses these untrusted values to generate the identity hash.
3. **Reward Selection**: `detect_duplicate_identities()` (Line 137) groups miners by this spoofable hash.

### Proof of Concept (Logic)
A script can send multiple `/attest/submit` requests with:
- Different `miner_id`s.
- Randomized `cpu_serial`.
- Slightly varied `clock_cv`, `thermal_var`, and `cache_ratio`.

Since the server trusts these values, each request creates a unique `machine_identity_hash`, and the system treats them as separate physical machines.

### Recommended Fix
1. **Hardware-Signed Attestations**: Require the hardware fingerprint to be signed by a Trusted Execution Environment (TEE) or a secure chip (e.g., TPM).
2. **Server-Side Verification**: Instead of trusting client-provided metrics, the server should perform its own challenges (e.g., timing-based challenges) to verify hardware characteristics.
3. **Stricter OUI Enforcement**: Use strict MAC address validation combined with network-level analysis to detect multiple IDs from a single network interface.
