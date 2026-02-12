# RustChain Documentation

> **RustChain** is a Proof-of-Antiquity blockchain that rewards vintage hardware with higher mining multipliers. The network uses 6 hardware fingerprint checks to prevent VMs and emulators from earning rewards.

## Quick Links

| Document | Description |
|----------|-------------|
| [Protocol Specification](./PROTOCOL.md) | Full RIP-200 consensus protocol |
| [API Reference](./API.md) | All endpoints with curl examples |
| [Glossary](./GLOSSARY.md) | Terms and definitions |
| [Tokenomics](./tokenomics_v1.md) | RTC supply and distribution |
| [FAQ & Troubleshooting](./FAQ_TROUBLESHOOTING.md) | Common setup/runtime issues and recovery steps |
| [Wallet User Guide](./WALLET_USER_GUIDE.md) | Wallet basics, balance checks, and safe operations |
| [Contributing Guide](./CONTRIBUTING.md) | Contribution workflow, PR checklist, and bounty submission notes |
| [Reward Analytics Dashboard](./REWARD_ANALYTICS_DASHBOARD.md) | Charts and API for RTC reward transparency |
| [Cross-Node Sync Validator](./CROSS_NODE_SYNC_VALIDATOR.md) | Multi-node consistency checks and discrepancy reports |

## Live Network

- **Primary Node**: `https://50.28.86.131`
- **Explorer**: `https://50.28.86.131/explorer`
- **Health Check**: `curl -sk https://50.28.86.131/health`

## Current Stats

```bash
# Check node health
curl -sk https://50.28.86.131/health | jq .

# List active miners
curl -sk https://50.28.86.131/api/miners | jq .

# Current epoch info
curl -sk https://50.28.86.131/epoch | jq .
```

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Vintage Miner  │────▶│ Attestation Node │────▶│  Ergo Anchor    │
│  (G4/G5/SPARC)  │     │  (50.28.86.131)  │     │ (Immutability)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │
        │ Hardware Fingerprint   │ Epoch Settlement
        │ (6 checks)             │ Hash
        ▼                        ▼
   ┌─────────┐              ┌─────────┐
   │ RTC     │              │ Ergo    │
   │ Rewards │              │ Chain   │
   └─────────┘              └─────────┘
```

## Getting Started

1. **Check if your hardware qualifies**: See [CPU Antiquity Guide](../CPU_ANTIQUITY_SYSTEM.md)
2. **Install the miner**: See [INSTALL.md](../INSTALL.md)
3. **Register your wallet**: Submit attestation to earn RTC

## Bounties

Active bounties: [github.com/Scottcjn/rustchain-bounties](https://github.com/Scottcjn/rustchain-bounties)

---
*Documentation maintained by the RustChain community.*
