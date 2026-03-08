# RIP-305 Track A: wRTC SPL Token on Solana

**Bounty:** #1149 (RIP-305 Cross-Chain Airdrop)  
**Track:** A — Solana SPL Token (75 RTC)  
**Agent:** nox-ventures | **GitHub:** @noxxxxybot-sketch

---

## Overview

Deploys `wRTC` as a Solana SPL Token using `@solana/web3.js` + `@solana/spl-token`.

- **Symbol:** wRTC
- **Decimals:** 6 (matches RTC internal precision)
- **Allocation:** 30,000 wRTC for Solana pool (RIP-305 spec)
- **Mint authority:** Configurable (admin-controlled Phase 1, upgradeable to DAO)

## Quick Start

```bash
npm install
# Deploy to devnet (default)
node deploy-wrtc.js

# Deploy to mainnet
SOLANA_NETWORK=mainnet-beta node deploy-wrtc.js
```

## Requirements

- Node.js 18+
- Funded Solana wallet (devnet: use faucet, mainnet: ~0.05 SOL)

## Files

| File | Purpose |
|------|---------|
| `deploy-wrtc.js` | Main deployment script — creates mint, mints 30,000 wRTC |
| `transfer-authority.js` | Transfers mint authority to multisig (Phase 1 → Phase 2) |
| `wrtc-metadata.json` | Token metadata for Metaplex |
| `package.json` | Dependencies |

## Deployment Steps

### 1. Devnet (Testing)

```bash
# Get devnet SOL from faucet
# https://faucet.solana.com or https://faucet.quicknode.com/solana/devnet

node deploy-wrtc.js
# Output: wrtc-deployment.json with mint address, tx signatures, explorer links
```

### 2. Mainnet (Production)

```bash
# Fund wallet: send 0.1 SOL to printed deploy authority address
SOLANA_NETWORK=mainnet-beta KEYPAIR_PATH=./prod-keypair.json node deploy-wrtc.js
```

### 3. Transfer Mint Authority (Phase 1 → Phase 2)

After deployment, transfer mint authority to Elyan Labs multisig:
```bash
MINT_ADDRESS=<deployed_mint> MULTISIG=<multisig_pubkey> node transfer-authority.js
```

## Token Metadata (Metaplex)

Token metadata follows Metaplex Fungible Token standard:

```json
{
  "name": "Wrapped RTC",
  "symbol": "wRTC",
  "description": "Wrapped RustChain Token on Solana — cross-chain bridge asset",
  "image": "https://rustchain.org/assets/wrtc-logo.png",
  "external_url": "https://rustchain.org",
  "attributes": [
    { "trait_type": "Protocol", "value": "RIP-305" },
    { "trait_type": "Chain", "value": "Solana" },
    { "trait_type": "Decimals", "value": "6" }
  ]
}
```

## Integration with Bridge

wRTC minting/burning controlled by bridge admin (Phase 1):

```
RustChain RTC → Lock → Admin mints wRTC on Solana
Solana wRTC → Burn → Admin releases RTC on RustChain
```

Bridge endpoints defined in RIP-305 spec:
- `POST /bridge/lock` — Lock RTC, mint wRTC
- `POST /bridge/release` — Burn wRTC, release RTC

## Anti-Sybil Requirements

wRTC airdrop eligibility (RIP-305 §3):
- Minimum 0.1 SOL wallet balance
- Wallet age > 7 days
- GitHub OAuth verification (stars + PRs)

## Dependencies

```json
{
  "@solana/web3.js": "^1.95.0",
  "@solana/spl-token": "^0.4.9"
}
```
