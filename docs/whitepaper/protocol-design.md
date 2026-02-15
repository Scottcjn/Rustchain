# Protocol Design (RIP-200 Proof-of-Attestation)

## Overview

RustChain is a Proof-of-Antiquity chain that replaces hashpower with **hardware identity** and **attestation**. The consensus family is referred to as **RIP-200**, and the design goal is simple:

- **1 CPU = 1 vote**, not 1 GPU farm = 1 vote
- Votes are **weighted by antiquity** (real vintage hardware earns higher multipliers)
- The network runs in **epochs**, and rewards are settled at epoch boundaries

Where traditional PoW chains treat energy expenditure as the scarce resource, RustChain treats *verifiable physical hardware* as the scarce resource.

## Attestations as the Core Signal

Miners periodically submit attestations to the node:

1. The miner requests a fresh challenge (`/attest/challenge`) and receives a nonce with an expiry.
2. The miner submits an attestation (`/attest/submit`) that includes device metadata, optional signals, and a `fingerprint` payload.
3. The node validates the submission (nonce validity, rate limits, blocked-wallet checks, hardware binding rules, fingerprint evidence).

The core principle is that miners do not win by solving a global puzzle; they win by repeatedly proving their hardware presence and passing anti-virtualization gates.

## Epochs and Reward Settlement

RustChain batches accounting into epochs. The node maintains an epoch state table and settles rewards for an epoch once:

- Determine the epoch number (often by converting a slot/block index to epoch).
- Compute eligible miners and their weights.
- Distribute the epoch reward pot proportionally.
- Record ledger deltas and mark the epoch as settled.

The rewards implementation (`node/rewards_implementation_rip200.py`) follows a defensive pattern:

- Settlement is **idempotent** (re-settling an already-settled epoch returns `already_settled`).
- Writes are wrapped in a DB transaction to reduce race conditions.

This gives the chain predictable payout cadence and makes auditing easier (epoch-by-epoch ledgers).

## Weighting: Antiquity and Time-Aging

RIP-200 weights are intended to encode two things:

1. **Antiquity multiplier**: vintage architectures receive a higher multiplier (e.g., PowerPC G4/G5).
2. **Participation/time-aging**: miners with consistent attestations over time should not be trivially displaced by bursty identities.

In practice, weight is derived from node-observed fields like:

- Device family/arch
- Fingerprint validation status
- Recent attestation history

The exact weighting schedule is implementation-defined and can be revised without changing the high-level protocol shape.

## Anti-Sybil Controls in the Protocol

RustChain’s sybil resistance is not based on capital (stake) or pure compute; it is based on making identity replication expensive.

Key controls:

- **Hardware fingerprinting**: multiple checks must pass with evidence; “passed=true” is not trusted without raw data for critical checks.
- **Hardware binding**: the node derives a `hardware_id` from server-observed traits (notably source IP) plus device traits to reduce multi-wallet extraction from one host.
- **Per-IP rate limiting**: limits the ability to spam the attestation plane and to create unbounded DB growth.
- **Admin-gated control plane**: privileged operations (settlement/internal transfers/exports) require an admin key, keeping high-impact state mutations off the public path.

These controls are intentionally pragmatic: they aim to defeat the common, cheap attack (VM farms) rather than solve an impossible “perfect remote attestation” problem.

## Deterministic Producer Selection (Round-Robin Framing)

RIP-200 is often described as **round-robin** in the project documentation: rather than probabilistic leader election, miner participation is tracked over an epoch and the network can deterministically compute distribution and/or ordering from enrolled identities.

Even when the exact block production mechanics evolve, the invariant remains:

- **Uniqueness of hardware identity matters more than raw throughput.**

## Cross-Node Considerations

As the network grows to multiple nodes, the protocol requires that:

- Nodes agree on epoch boundaries and settlement status.
- Read endpoints stay consistent enough for explorers and clients.
- Any cross-node synchronization logic prevents inconsistent settlement (double-apply) or forked accounting.

Operationally, this pushes the system toward:

- Strong idempotency in settlement and transfers
- Explicit audit logs for state transitions
- Defensive API design (bounded queries, strict validation)

## Practical Notes

- The public data plane should remain usable without privileged secrets (miners can attest, users can submit signed transfers).
- The control plane should remain narrow and explicitly gated.
- Validation must be server-side, because miners are adversarial in the threat model.

## References (In-Repo)

- `docs/PROTOCOL.md` and `docs/PROTOCOL_v1.1.md`
- `docs/WHITEPAPER.md` (existing whitepaper draft)
- `node/rustchain_v2_integrated_v2.2.1_rip200.py` (production node)
- `node/rewards_implementation_rip200.py` (epoch reward settlement)

