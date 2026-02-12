# RustChain Documentation

> **RustChain** is a Proof-of-Antiquity blockchain that rewards vintage hardware with higher mining multipliers. The network uses 6 hardware fingerprint checks to prevent VMs and emulators from earning rewards.

## Quick Links

| Document | Description |
|----------|-------------|
| [Protocol Specification](./PROTOCOL.md) | Full RIP-200 consensus protocol |
| [API Reference](./API.md) | Complete public endpoint index + curl examples |
| [OpenAPI Spec](./api/openapi.yaml) | Machine-readable API schema |
| [Glossary](./GLOSSARY.md) | Terms and definitions |
| [Tokenomics](./tokenomics_v1.md) | RTC supply and distribution |

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
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?    鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?    鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹? Vintage Miner  鈹傗攢鈹€鈹€鈹€鈻垛攤 Attestation Node 鈹傗攢鈹€鈹€鈹€鈻垛攤  Ergo Anchor    鈹?
鈹? (G4/G5/SPARC)  鈹?    鈹? (50.28.86.131)  鈹?    鈹?(Immutability)  鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?    鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?    鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
        鈹?                       鈹?
        鈹?Hardware Fingerprint   鈹?Epoch Settlement
        鈹?(6 checks)             鈹?Hash
        鈻?                       鈻?
   鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?             鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
   鈹?RTC     鈹?             鈹?Ergo    鈹?
   鈹?Rewards 鈹?             鈹?Chain   鈹?
   鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?             鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
```

## Getting Started

1. **Check if your hardware qualifies**: See [CPU Antiquity Guide](../CPU_ANTIQUITY_SYSTEM.md)
2. **Install the miner**: See [INSTALL.md](../INSTALL.md)
3. **Register your wallet**: Submit attestation to earn RTC

## Bounties

Active bounties: [github.com/Scottcjn/rustchain-bounties](https://github.com/Scottcjn/rustchain-bounties)

---
*Documentation maintained by the RustChain community.*

