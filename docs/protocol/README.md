# RustChain Protocol Documentation

This is the focused entry point for the RustChain protocol documentation requested by bounty #8. It keeps one canonical source for each subject instead of copying protocol facts into multiple files.

## Scope and status

RustChain is a Proof-of-Antiquity network. The documents below describe the current RIP-200 implementation, its attestation and reward lifecycle, and the public interfaces used by miners and operators.

When a summary and an implementation/API contract differ, prefer the implementation-linked reference (`docs/api/openapi.yaml`, `docs/READ_ONLY_API_CONTRACT.md`, and the node code) and open an issue before changing protocol behavior.

## Topic map

| Topic | Canonical reference | What it covers |
| --- | --- | --- |
| Protocol overview | [Protocol specification](../PROTOCOL.md) | RIP-200 scope, trust model, network roles, security, and API orientation |
| Consensus | [RIP-200 consensus](../PROTOCOL.md#2-rip-200-consensus) and [invariant harness](../CONSENSUS_INVARIANT_ATTRACTOR.md) | one-CPU participation, eligibility, weight calculation, settlement, and deterministic invariants |
| Attestation | [Attestation API](../API.md#attestation) and [protocol attestation flow](../PROTOCOL.md#3-attestation-flow) | challenge/report fields, validation gates, signatures, enrollment, and rejection codes |
| Epochs | [Epoch settlement](../epoch-settlement.md) and [epoch API](../API.md#epoch-information) | slots, enrollment windows, epoch close, reward allocation, and settlement evidence |
| Hardware fingerprinting | [Hardware fingerprinting](../hardware-fingerprinting.md) | six behavioral checks, anti-emulation signals, scoring, and platform classification |
| Tokenomics | [Token economics](../token-economics.md) and [tokenomics v1](../tokenomics_v1.md) | supply, epoch emissions, multipliers, reward formula, decay, fees, and bridge notes |
| Public API | [API reference](../API.md), [API walkthrough](../API_WALKTHROUGH.md), and [OpenAPI](../api/openapi.yaml) | health, epoch, miner, attestation, wallet, ledger, rewards, and error contracts |
| Glossary | [RustChain glossary](../GLOSSARY.md) | shared protocol terminology and multiplier reference |
| Diagrams | [Protocol diagrams](./diagrams.md) | consensus/attestation flow and epoch settlement diagrams |

## Recommended reading order

1. [Protocol specification](../PROTOCOL.md)
2. [Hardware fingerprinting](../hardware-fingerprinting.md)
3. [API reference](../API.md)
4. [Epoch settlement](../epoch-settlement.md)
5. [Token economics](../token-economics.md)
6. [Glossary](../GLOSSARY.md)

## Contract boundaries

- **Public read paths** include health, epoch, miner, node, balance, history, pending-ledger integrity, rewards, and explorer endpoints.
- **Attestation writes** are authenticated/validated enrollment inputs; examples must not be treated as credentials or proof by themselves.
- **Settlement** is an epoch-scoped accounting operation. The reward formula is proportional to eligible weight; the exact live response and node implementation remain authoritative.
- **Hardware evidence** is anti-emulation input, not an absolute physical guarantee. Multiple signals are combined and failed checks must be interpreted with the node's current policy.
- **Token figures** in explanatory documents are versioned project facts and should be checked against the live epoch/API data before making economic claims.

## Validation

From the repository root:

```bash
python tools/check_relative_links.py
python -m compatibility_lab ci
```

The first command checks repository-owned relative links. The compatibility-lab command runs the read-only API and documentation contract checks used by CI.
