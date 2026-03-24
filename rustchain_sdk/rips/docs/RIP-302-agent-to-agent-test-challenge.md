---
title: "RIP-302: Reproducible Agent-to-Agent Transaction Test Challenge"
author: RustChain Core Team
status: Draft
created: 2026-03-06
last_updated: 2026-03-06
license: Apache 2.0
tags: [beacon, grazer, agent-to-agent, testing, reproducibility, rip-302]
---

# RIP-302: Reproducible Agent-to-Agent Transaction Test Challenge

## Summary

This RustChain Improvement Proposal (RIP) defines a **reproducible test challenge** for verifying Agent-to-Agent (A2A) transactions across the Beacon Protocol, Grazer skill discovery, and x402 payment rails. The challenge provides deterministic artifacts, verifiable evidence flow, and automated validation scripts to ensure interoperability between autonomous agents.

## Abstract

As RustChain's agent ecosystem grows, ensuring reliable Agent-to-Agent communication and value transfer becomes critical. RIP-302 establishes:

1. **Test Challenge Framework**: A reproducible suite of scenarios testing A2A transaction flows
2. **Evidence Collection**: Structured logging and cryptographic proof of transaction completion
3. **Verification Pipeline**: Automated scripts to validate challenge completion
4. **Beacon + Grazer Integration**: End-to-end testing of agent discovery, negotiation, and settlement

This RIP enables bounty hunters, auditors, and developers to independently verify A2A transaction integrity.

## Motivation

### Problem Statement

Current agent testing lacks:
- **Reproducibility**: Tests depend on network conditions and external state
- **Verifiable Evidence**: No standardized proof of transaction completion
- **Cross-Component Integration**: Beacon, Grazer, and payment systems tested in isolation
- **Bounty Validation**: Difficulty verifying bounty submissions for A2A features

### Goals

1. **Deterministic Testing**: Create reproducible test scenarios with fixed seeds and mockable dependencies
2. **Evidence Chain**: Generate cryptographic proofs (hashes, signatures) for each transaction step
3. **Integration Coverage**: Test full A2A flow: discovery → negotiation → payment → settlement
4. **Bounty Support**: Provide clear pass/fail criteria for bounty #684 and related submissions

## Specification

### 1. Test Challenge Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Agent Alpha   │────▶│  Beacon Protocol │────▶│   Agent Beta    │
│   (Initiator)   │     │  (Discovery)     │     │   (Responder)   │
└────────┬────────┘     └──────────────────┘     └────────┬────────┘
         │                                                │
         │              ┌──────────────────┐              │
         │─────────────▶│   Grazer Skill   │◀─────────────│
         │              │   (Discovery)    │              │
         │              └──────────────────┘              │
         │                                                │
         │              ┌──────────────────┐              │
         │─────────────▶│   x402 Payment   │◀─────────────│
         │              │   (Settlement)   │              │
         │              └──────────────────┘              │
         │                                                │
         ▼                                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Evidence Collection Layer                     │
│  - Envelope signatures  - Transaction hashes  - Timestamps      │
│  - State proofs         - Contract events    - Logs             │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Test Scenarios

#### Scenario 1: Basic A2A Heartbeat Exchange
- **Objective**: Two agents exchange signed heartbeat envelopes via Beacon
- **Success Criteria**:
  - Both agents generate valid v2 envelopes
  - Envelopes verified with correct pubkeys
  - Heartbeats anchored to Beacon table
- **Evidence**: Envelope JSON, signature verification result, DB row IDs

#### Scenario 2: Skill Discovery via Grazer
- **Objective**: Agent Alpha discovers Agent Beta's capabilities via Grazer
- **Success Criteria**:
  - Grazer returns agent capabilities
  - Capability hashes match advertised specs
  - Discovery logged with timestamps
- **Evidence**: Grazer query response, capability hash, discovery log

#### Scenario 3: Contract Negotiation & Settlement
- **Objective**: Full contract lifecycle between two agents
- **Success Criteria**:
  - Contract listed with terms
  - Offer made and accepted
  - Escrow funded and activated
  - Settlement completed
- **Evidence**: Contract state transitions, escrow tx refs, settlement proof

#### Scenario 4: x402 Payment Flow
- **Objective**: Agent-to-Agent payment via x402 on Base
- **Success Criteria**:
  - Payment intent created
  - X-PAYMENT header validated
  - USDC transferred on Base
  - Payment recorded in both agents' ledgers
- **Evidence**: Payment hash, tx hash, ledger entries

### 3. Evidence Schema

Each test scenario produces evidence following this schema:

```json
{
  "challenge_id": "a2a_rip302_<scenario>",
  "run_id": "<uuid>",
  "timestamp": "<iso8601>",
  "agents": {
    "initiator": {
      "agent_id": "bcn_xxx",
      "pubkey": "0x...",
      "wallet": "0x..."
    },
    "responder": {
      "agent_id": "bcn_yyy",
      "pubkey": "0x...",
      "wallet": "0x..."
    }
  },
  "steps": [
    {
      "step": 1,
      "action": "heartbeat_sent",
      "evidence_hash": "blake2b(...)",
      "payload": {...},
      "verified": true,
      "timestamp": "<iso8601>"
    }
  ],
  "final_state": {
    "status": "completed|failed",
    "evidence_digest": "blake2b(...)",
    "proof_file": "evidence/proof.json"
  }
}
```

### 4. Reproducibility Requirements

To ensure tests are reproducible:

1. **Fixed Seeds**: All random values (nonces, keys) use deterministic seeds
2. **Mockable Dependencies**: Network calls, DB access, and external APIs must be mockable
3. **State Isolation**: Each test run uses isolated DB and file state
4. **Timestamp Control**: Tests can use fixed or simulated timestamps
5. **Environment Capture**: Record Python version, dependencies, OS details

### 5. Verification Pipeline

The verification script performs:

1. **Evidence Integrity**: Verify all hashes match payloads
2. **Signature Validation**: Re-verify all envelope signatures
3. **State Consistency**: Check DB state matches reported outcomes
4. **Completeness**: Ensure all required steps executed
5. **Reproducibility**: Re-run test and compare evidence digests

## Rationale

### Why Beacon + Grazer + RIP-302?

- **Beacon**: Provides agent identity, heartbeat, and envelope signing
- **Grazer**: Enables skill/capability discovery between agents
- **RIP-302**: Defines the test challenge framework tying them together

### Why Blake2b for Hashes?

- Faster than SHA-256
- Secure and widely adopted
- Already used in beacon_anchor.py

### Why Isolated State?

- Prevents test pollution
- Enables parallel test execution
- Simplifies CI/CD integration

## Backwards Compatibility

This RIP introduces new test infrastructure without modifying existing protocols. All existing Beacon, Grazer, and x402 endpoints remain unchanged.

## Implementation Notes

### Directory Structure

```
bounties/issue-684/
├── README.md                 # Challenge overview and quickstart
├── docs/
│   ├── RIP-302.md           # This specification
│   ├── CHALLENGE_GUIDE.md   # Detailed challenge instructions
│   └── EVIDENCE_SCHEMA.md   # Evidence format documentation
├── scripts/
│   ├── run_challenge.py     # Main challenge runner
│   ├── verify_evidence.py   # Evidence verification script
│   ├── collect_proof.py     # Proof collection utility
│   └── ci_validate.sh       # CI/CD integration script
├── fixtures/
│   ├── agent_alpha.json     # Test agent Alpha config
│   ├── agent_beta.json      # Test agent Beta config
│   └── expected_state.json  # Expected final state
└── evidence/
    └── .gitkeep             # Evidence output directory
```

### Dependencies

- Python 3.10+
- beacon-skill (for agent identity and envelopes)
- grazer-skill (for capability discovery)
- pytest (for test framework)
- blake2b (for hashing)

### Example Usage

```bash
# Run the full challenge suite
python scripts/run_challenge.py --all

# Run a specific scenario
python scripts/run_challenge.py --scenario contract_negotiation

# Verify evidence from a previous run
python scripts/verify_evidence.py --evidence-dir evidence/

# Generate proof for bounty submission
python scripts/collect_proof.py --output proof.json
```

## Reference Implementation

The reference implementation is provided in the `bounties/issue-684/` directory of this repository.

## Security Considerations

1. **Key Management**: Test keys are deterministic and should NOT be used in production
2. **State Isolation**: Ensure test DB is separate from production DB
3. **Evidence Tampering**: Use cryptographic hashes to detect tampering
4. **Replay Attacks**: Include nonces and timestamps in all envelopes

## Future Work

1. **Cross-Chain Testing**: Extend to multi-chain A2A transactions
2. **Performance Benchmarks**: Add latency and throughput metrics
3. **Fuzz Testing**: Integrate with attestation fuzz testing framework
4. **Visual Reports**: Generate HTML reports for bounty submissions

## Acknowledgments

This RIP builds upon:
- Beacon Protocol v2 (agent envelopes)
- Grazer skill discovery framework
- x402 payment protocol on Base
- RustChain bounty program infrastructure

---

© 2026 RustChain Core Team — Apache 2.0 License
