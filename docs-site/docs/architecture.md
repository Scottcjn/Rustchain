# Architecture

RustChain is a memory-preservation blockchain that uses entropy benchmarks, hardware age, and artifact rarity to validate and score block creation.

## Consensus: Proof of Antiquity (RIP-200)

The consensus mechanism is defined in **RIP-200** (RustChain Iterative Protocol). Instead of hash-rate competition, RustChain uses round-robin consensus where each verified hardware device gets exactly one vote per epoch.

### Core Principles

- **1 CPU = 1 Vote** -- Each unique hardware device gets one vote per epoch, regardless of processing speed.
- **Antiquity Weighting** -- Rewards are multiplied by how old the hardware is.
- **Anti-Emulation** -- Six fingerprint checks ensure miners run on real silicon, not VMs.

### Attestation Flow

```
1. Miner starts a mining session
2. Client script runs 6 hardware fingerprint checks
3. POST /attest/submit sends fingerprint + signature to attestation node
4. Node validates fingerprint against known hardware profiles
5. Valid hardware -> enrolled in current epoch
6. At epoch boundary (slot 144) -> settlement
7. Reward pool distributed (equal split x antiquity multiplier)
8. Settlement hash anchored to Ergo blockchain
```

### Epoch Lifecycle

Each epoch lasts 10 minutes (600 seconds) and contains 144 slots. At the end of each epoch:

1. All enrolled miners receive their share of the 1.5 RTC reward pool.
2. Shares are scaled by each miner's antiquity multiplier.
3. A commitment hash of the epoch state is written to the Ergo blockchain (R4 register) for immutability.

## Hardware Fingerprinting

Six hardware checks form the fingerprint:

| # | Check | Measurement | Anti-Emulation |
|---|---|---|---|
| 1 | Clock Skew | Crystal oscillator drift in ppm, jitter in ns | VMs inherit host clock (too stable) |
| 2 | Cache Timing | L1/L2/L3 latency in ns | Emulators flatten the cache hierarchy |
| 3 | SIMD Identity | AltiVec/SSE/NEON execution bias | Timing differs under emulation |
| 4 | Thermal Entropy | CPU temperature curves under load | VMs report static temperatures |
| 5 | Instruction Jitter | Opcode execution variance in ns | Real silicon has unique nanosecond jitter |
| 6 | Behavioral Heuristics | Hypervisor detection signatures | Catches VMware, QEMU, SheepShaver |

### Fingerprint Payload

```json
{
  "miner_id": "abc123RTC",
  "timestamp": 1770112912,
  "fingerprint": {
    "clock_skew": { "drift_ppm": 12.5, "jitter_ns": 847 },
    "cache_timing": { "l1_latency_ns": 4, "l2_latency_ns": 12, "l3_latency_ns": 42 },
    "simd_identity": { "vector_unit": "AltiVec", "bias_score": 0.87 },
    "thermal_entropy": { "temp_c": 62.3, "variance": 1.2 },
    "instruction_jitter": { "mean_ns": 4.2, "stddev_ns": 0.8 },
    "behavioral": { "vm_detected": false, "confidence": 0.99 }
  },
  "signature": "ed25519_hex_signature"
}
```

## Block Structure

Each block contains:

- **Validator ID** -- Wallet address (Ergo backend)
- **BIOS Timestamp** -- Hardware age proof + entropy duration
- **NFT Unlocks** -- Badges earned (e.g., "Paw Paw" retro bonus)
- **Lore Metadata** -- Optional attached artifact data
- **Score Metadata** -- For leaderboard and faucet access

## Token Emission

- **Block reward**: 5 RTC per block to the validator
- **Epoch reward pool**: 1.5 RTC distributed among enrolled miners
- **Halving**: Every 2 years or at epoch milestones
- **NFT modifiers**: Certain badges alter payout (retro bonuses)

## Network Topology

### Live Nodes

| Node | Address | Role |
|---|---|---|
| Node 1 | 50.28.86.131 | Primary + Explorer |
| Node 2 | 50.28.86.153 | Ergo Anchor |
| Node 3 | 76.8.228.245 | Community Node |

### Ergo Anchoring

RustChain periodically writes a commitment hash to the Ergo blockchain:

```
RustChain Epoch -> Commitment Hash -> Ergo Transaction (R4 register)
```

This provides cryptographic proof that RustChain state existed at a specific point in time, giving the chain external immutability guarantees without running its own full PoW.

## External Integrations

- **ErgoTool CLI** -- Wallet creation and transaction signing
- **Ergo NFT Standards** -- Soulbound badge issuance for achievements
- **Solana Bridge** -- wRTC token on Solana via BoTTube Bridge
- **Base Bridge** -- wRTC on Base (Coinbase L2) at `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`
- **x402 Protocol** -- HTTP 402 machine-to-machine payments for premium API access
- **Coinbase Agent Wallets** -- Agents can own Base wallets for autonomous payments

## RIP System

RustChain uses a proposal system called **RIPs** (RustChain Iterative Protocols) for protocol changes:

| RIP | Title | Status |
|---|---|---|
| RIP-0001 | Proof of Antiquity | Active |
| RIP-0007 | Entropy Fingerprinting | Active |
| RIP-200 | 1 CPU = 1 Vote (Round Robin) | Active |
| RIP-201 | Fleet Immune System | Active |
| RIP-304 | Retro Console Mining | Draft |
| RIP-305 | Cross-Chain Airdrop | Draft |

## Design Goals

- Keep validator requirements low (Pentium III or older can participate)
- Preserve retro OS compatibility
- Limit chain bloat via badge logs and off-chain metadata anchors
- Reward hardware preservation over raw compute power
