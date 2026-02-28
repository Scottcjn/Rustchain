# RustChain Protocol Documentation

## Overview

RustChain is a **Proof-of-Antiquity** blockchain that rewards vintage hardware with higher mining multipliers.

## Key Concepts

### Hardware Multipliers

| Hardware | Multiplier |
|----------|------------|
| PowerPC G3 | 1.8x |
| PowerPC G4 | 2.5x |
| PowerPC G5 | 2.0x |
| IBM POWER8 | 2.5x |
| Modern x86 | 1.0x |

### RIP-200 Consensus

RustChain uses RIP-200 (Proof-of-Attestation) consensus.

### Epoch System

- Epoch length: 144 blocks (~24 hours)
- Reward pot: 1.5 RTC per epoch

## Getting Started

### Install Miner

```bash
pip install clawrtc
clawrtc start --wallet your_wallet
```

### Check Status

```bash
curl -sk https://50.28.86.131/health
curl -sk https://50.28.86.131/api/miners
```

## Architecture

- **Miners**: Submit attestations with hardware fingerprints
- **Attestation Nodes**: Validate fingerprints, record attestations
- **Epoch Settlement**: Calculate and distribute rewards

## Hardware Fingerprinting

6+1 fingerprint checks prevent VM/emulator cheating.
