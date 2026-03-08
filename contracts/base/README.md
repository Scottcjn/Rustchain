# RIP-305: wRTC ERC-20 on Base L2

## Overview

Wrapped RTC (wRTC) ERC-20 token implementing [RIP-305](../docs/RIP-305-cross-chain-airdrop.md) for the Base L2 network.

## Contract: WrappedRTC.sol

- **Network**: Base (mainnet, chainId 8453) + Base Sepolia (testnet, chainId 84532)
- **Standard**: ERC-20 with mint/burn (OpenZeppelin v5)
- **Decimals**: 6 (matches native RTC precision)
- **Max Supply**: 20,000 wRTC (20,000,000,000 in 6-decimal units)
- **Roles**: Owner + Bridge (admin-controlled in Phase 1)

## Features

- `mint(address to, uint256 amount)` — Bridge or owner mints wRTC when RTC locked on RustChain
- `burnFrom(address from, uint256 amount)` — Bridge burns wRTC when user redeems to RustChain  
- `setBridge(address bridge)` — Owner sets authorized bridge address
- `remainingSupply()` — View remaining mintable supply
- MAX_SUPPLY enforced — cannot exceed 20,000 wRTC total

## Deployment

### Prerequisites

```bash
npm install
cp .env.example .env
# Add PRIVATE_KEY and BASESCAN_API_KEY to .env
```

### Deploy to Base Sepolia (testnet)

```bash
PRIVATE_KEY=0x... BASESCAN_API_KEY=... npx hardhat run scripts/deploy.js --network base-sepolia
```

### Verify on BaseScan

```bash
npx hardhat verify --network base-sepolia <CONTRACT_ADDRESS> <OWNER_ADDRESS>
```

### Deploy to Base Mainnet

```bash
PRIVATE_KEY=0x... BASESCAN_API_KEY=... npx hardhat run scripts/deploy.js --network base
```

## Security Notes

- Phase 1: Admin-controlled bridge (owner can set bridge address)
- Phase 2 (future): Trustless bridge via cross-chain message verification
- MAX_SUPPLY cap prevents unbounded inflation
- onlyBridgeOrOwner modifier on mint/burn functions

## RIP-305 Airdrop Eligibility Tiers

| Tier | Requirement | wRTC Claim |
|------|------------|------------|
| Stargazer | 10+ repos starred | 25 wRTC |
| Contributor | 1+ merged PR | 50 wRTC |
| Builder | 3+ merged PRs | 100 wRTC |
| Security | Verified vulnerability | 150 wRTC |
| Core | 5+ merged PRs / Star King | 200 wRTC |
| Miner | Active attestation | 100 wRTC |

## Status

- [x] Contract written + tested locally
- [x] Compiles with Hardhat (Solidity 0.8.20, Paris EVM)
- [ ] Deployed to Base Sepolia (pending testnet ETH)
- [ ] Verified on BaseScan
- [ ] Deployed to Base Mainnet

