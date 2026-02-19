# RustChain Mechanism Spec + Falsification Matrix

Last updated: 2026-02-19  
Scope: RIP-200 / Proof-of-Antiquity operational claims

This is the minimal, testable mechanism spec for RustChain. The goal is not "trust us"; the goal is clear claims that can be falsified.

## 1) Minimal Mechanism Spec

### Actors
- Miner: submits work and hardware attestations.
- Validator/Node: verifies attestation/work, tracks balances, enforces transfer safety.
- Client/Wallet: reads state and submits signed transfers.

### Capabilities
- Deterministic state endpoints: `GET /health`, `GET /epoch`, `GET /api/miners`, `GET /api/stats`.
- Signed value transfer path: `POST /wallet/transfer/signed` with nonce + signature validation.
- Per-epoch mining/attestation accounting with antiquity multipliers visible in `GET /api/miners`.

### Invariants
- I1: One-CPU-one-vote semantics per epoch (no hash-power weighting).
- I2: Replayed signed transfer payloads do not execute twice.
- I3: Miner state is observable and auditable through public endpoints.
- I4: Antiquity multipliers are explicit and bounded by configured policy.

### Main Failure Modes
- F1: Sybil/emulation attempts to inflate voting/reward share.
- F2: Replay of signed transfer payloads (nonce reuse).
- F3: Cross-node/API divergence that breaks deterministic client reads.
- F4: Invalid signatures accepted for transfer or attestation paths.

## 2) Falsification Matrix

If any "Fail condition" occurs, the corresponding claim is falsified.

| Claim | Mechanism Under Test | How to Test | Pass Condition | Fail Condition |
|---|---|---|---|---|
| C1: Node health/status is deterministic and machine-readable | Health endpoint | `curl -sk https://50.28.86.131/health \| jq .` | JSON response with `ok=true`, `version`, and runtime fields | Endpoint missing, malformed, or non-deterministic health state |
| C2: Epoch state is explicit and observable | Epoch endpoint | `curl -sk https://50.28.86.131/epoch \| jq .` | Returns epoch/slot/pot fields and advances over time | No epoch data or inconsistent epoch progression |
| C3: Miner enrollment + multipliers are transparent | Miner list endpoint | `curl -sk https://50.28.86.131/api/miners \| jq .` | Active miners listed with hardware fields and `antiquity_multiplier` | Missing/opaque miner state or absent multiplier disclosure |
| C4: Signed transfer replay is blocked | Nonce replay protection | Send the same signed payload (same nonce/signature) to `/wallet/transfer/signed` twice | First request accepted; second request rejected as replay/duplicate | Same signed payload executes twice |
| C5: Signature checks are enforced | Signature verification | Submit intentionally invalid signature to `/wallet/transfer/signed` | Transfer rejected with validation error | Invalid signature accepted and state mutates |
| C6: Cross-node reads can be compared for drift | API consistency | Compare `/health`, `/epoch`, `/api/miners` across live nodes (131, 153, 245) | Differences stay within expected propagation window and reconcile | Persistent divergence with no reconciliation |

## 3) One-Page Test Run Template

Use this exact template for public challenge/verification reports.

```text
Test ID:
Date (UTC):
Tester:
Node(s):

Claim tested:
Input payload / command:
Observed output:
Pass/Fail:
Notes:
```

## 4) Challenge Statement

Break-tests are welcome. Reproducible failures with commands/payloads and timestamps are valid security findings and are bounty-eligible under the RustChain policy.
