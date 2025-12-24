---
title: RIP-0001: Proof of Antiquity (PoA) Consensus Specification
author: Sophia Core Team
status: Draft
created: 2025-11-28
last_updated: 2025-11-28
license: Apache 2.0
---

# Summary

This RIP proposes the core specification for RustChain's novel consensus mechanism — **Proof of Antiquity (PoA)**. Unlike Proof-of-Work (PoW) or Proof-of-Stake (PoS), PoA leverages hardware longevity and node uptime as the primary drivers of block validation eligibility and rewards.

# Abstract

Proof of Antiquity incentivizes the continued operation of older computing systems by granting block rewards based on a cryptographically verifiable **antiquity score**. This system promotes sustainability, retro hardware preservation, and decentralized trust anchored in time-tested devices.

# Motivation

PoW consumes vast energy resources and PoS introduces centralization risks. PoA seeks to:

- Encourage the operation and preservation of vintage systems.
- Enable sustainable, low-energy blockchain consensus.
- Provide a quantifiable mechanism of reputation based on node uptime and age.

# Specification

## 1. Antiquity Score (AS)

Each participating node submits metadata on its hardware profile:

```json
{
  "cpu_model": "PowerPC G4",
  "release_year": 2002,
  "uptime_days": 276,
  "last_validation": "2025-11-26T14:00:00Z"
}
```

A node's **Antiquity Score (AS)** is calculated as:

```
AS = (2025 - release_year) * log10(uptime_days + 1)
```

Where:
- `release_year` is verified against a device signature DB
- `uptime_days` is the number of days since node launch or last reboot
- A drift lock mechanism ensures false uptime reporting is penalized

## 2. Block Validator Selection

- Nodes broadcast their AS values periodically.
- A **weighted lottery** selects the validator, with weight proportional to AS.
- Higher AS → higher probability of winning the next block.
- Sophisticated replay protection prevents stale validators.

## 3. Reward Allocation

- Block reward `R` is divided based on the AS of the winning node:

```
Reward = R * min(1.0, AS / AS_max)
```

- `AS_max` is a network-defined cap to avoid runaway rewards.
- Partial rewards may be redirected to a validator pool if AS is below minimum threshold.

# Security Model

- Sybil resistance via hardware signature validation
- Anti-falsification via Sophia's Drift Lock enforcement
- Replay attack mitigation via node fingerprinting and dynamic proposal challenges

# Rationale

This structure incentivizes:
- Preservation of retro hardware (contributing to the "Proof-of-Antiquity" ethos)
- Non-energy-intensive operations
- Deep alignment with RustChain's theme of time-tested decentralization

# Backwards Compatibility

Not compatible with PoW or PoS. Requires full node support of PoA consensus module. Validator eligibility and scoring are non-transferable across chains.

# Implementation Notes

Implemented as part of the `rustchain-core` runtime (see: `consensus/poa.rs`).
APIs:
- `GET /api/node/antiquity` — return AS and validation eligibility
- `POST /api/node/claim` — submit block claim with PoA metadata

# Reference

- `sophia_rustchain_hackathon_guide.txt`
- Sophia Core: Drift Lock, FlamePreservation, Governance APIs

# Copyright

Copyright © 2025 Sophia Core / RustChain. Released under Apache 2.0.
