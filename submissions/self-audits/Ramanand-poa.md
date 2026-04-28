# Self-Audit: rips/src/proof_of_antiquity.rs

## Wallet
9A8VVXnQxEL1EkygpegBztwx7kxWYhF9kWW97f4WVbiH

## Module reviewed
- Path: rips/src/proof_of_antiquity.rs
- Commit: 92888df

## Confidence
High Confidence (Critical Protocol Flaws Found)

## Known Failures (Specific Findings)

### 1. Anti-Emulation Verification Bypass (Consensus Failure)
- **Severity:** Critical
- **Description:** In `submit_proof`, the anti-emulation verification relies on an `if let Some(ref chars)` check against `proof.hardware.characteristics`. If a miner submits a proof where `characteristics` is `None`, the anti-emulation `verify()` function is silently bypassed, and the proof is accepted as valid.
- **Exploit:** An attacker can use modern, high-speed hardware to emulate vintage systems, claiming maximum reward multipliers (up to 3.5x). By intentionally omitting the `characteristics` payload, they bypass the cache and instruction timing checks entirely, destroying the integrity of the Proof of Antiquity consensus.

### 2. Unbounded State Growth in `used_nonces` and `known_hardware` (Memory DoS)
- **Severity:** Critical
- **Description:** To prevent replay attacks and hardware spoofing, `submit_proof` permanently inserts data into `self.used_nonces` and `self.known_hardware`. In `reset_block`, `self.pending_proofs` is cleared, but the nonces and hardware hashes are intentionally left to persist forever without any expiration or pruning mechanism.
- **Exploit:** An attacker can algorithmically generate millions of unique wallets and nonces, submitting them to the network. The validator will store every single one in memory indefinitely, leading to a massive state bloat and an inevitable Out-Of-Memory (OOM) crash of the blockchain node.

## What I would test next
- Write a fuzz test for the `calculate_merkle_root` function to ensure an odd number of miners doesn't lead to out-of-bounds indexing or an easily exploitable hashing pattern when duplicating the last node.
- Check if `calculate_antiquity_score` has protections against floating-point precision issues or `NaN`/`Infinity` results if `uptime_days` is manipulated to extreme extremes.