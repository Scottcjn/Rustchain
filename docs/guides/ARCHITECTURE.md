# Architecture Overview

RustChain is a DePIN blockchain using Proof of Antiquity consensus. This document describes the system architecture.

## System Diagram

```
+------------------+     +------------------+     +------------------+
|   Miners         |     |   Attestation    |     |   Blockchain     |
| (any hardware)   |---->|   Nodes (5)      |---->|   State          |
+------------------+     +------------------+     +------------------+
        |                        |                        |
        v                        v                        v
+------------------+     +------------------+     +------------------+
| 6-Check HW       |     | Cross-Validation  |     | Epoch Rewards    |
| Fingerprint      |     | + ROM Clustering  |     | + Multipliers    |
+------------------+     +------------------+     +------------------+
```

## Layers

### 1. Mining Layer
- Any device running `clawrtc` or the install script
- Submits hardware fingerprint every epoch (10 min)
- Supports 15+ CPU architectures
- 1 CPU = 1 vote. No advantage from threads/speed

### 2. Attestation Layer
- 5 nodes across 3 continents
- Primary: 50.28.86.131 (Louisiana, US)
- First non-x86: IBM POWER8 S824
- Validates hardware fingerprints server-side
- Cross-validates SIMD features vs claimed architecture
- Detects ROM clustering (emulator farms)
- Analyzes timing distributions for VM detection

### 3. Consensus Layer
- Proof of Antiquity: rewards weighted by hardware age
- Multipliers range from 1.0x (modern) to 4.0x (vintage)
- Reward pool: 1.5 RTC/epoch, halves every 2 years
- Anti-VM: 1 billionth rewards for detected VMs

### 4. Token Layer
- RTC: native token, 8,388,608 fixed supply (2^23)
- Ed25519 signatures for transfers
- wRTC: Solana bridge (experimental)

### 5. Agent Layer
- Beacon: agent discovery protocol
- BoTTube: AI-native video platform
- TrashClaw: local LLM agent
- Agent economy: autonomous agents earn/spend RTC

## Data Flow

1. Miner collects 6 hardware metrics
2. Submits to attestation node
3. Node cross-validates against known hardware profiles
4. Valid attestations included in next epoch
5. Rewards distributed by antiquity multiplier
6. Wallet balances updated on-chain

## Key Design Decisions

- **Fixed supply**: No inflation beyond 8.3M RTC
- **1 CPU = 1 vote**: Prevents hash-power centralization
- **Age-based rewards**: Environmental incentive to preserve hardware
- **$0 VC**: No venture capital, built on pawn shop hardware
- **Agent-native**: AI agents are first-class network participants
