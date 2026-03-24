# RIP-305: Cross-Chain Airdrop Protocol

**Status**: Draft
**Author**: Scott (Flameholder), Elyan Labs
**Created**: 2026-03-07
**Allocation**: 50,000 RTC (0.6% of total supply)

---

## Abstract

RIP-305 defines a cross-chain airdrop mechanism for distributing wrapped RTC (wRTC) tokens on Solana and Base L2. The protocol incentivizes ecosystem participation while implementing anti-Sybil measures including minimum wallet balance requirements, GitHub contribution verification, and wallet age checks.

## Motivation

RustChain's contributor base is growing (214+ recipients, 2,948+ stars) but remains concentrated on GitHub. Cross-chain airdrops on Solana and Base expose RTC to established DeFi/Web3 communities, creating liquidity pathways and broader awareness.

The airdrop uses a fee recycling flywheel: distributed RTC generates transaction fees (RIP-303 gas), which flow back to the community fund for subsequent airdrop stages.

## Specification

### 1. Token Contracts

#### Solana (SPL Token)
- **Symbol**: wRTC
- **Decimals**: 6 (matches RTC internal precision)
- **Mint Authority**: Elyan Labs multisig (upgradeable to DAO)
- **Allocation**: 30,000 wRTC

#### Base (ERC-20)
- **Symbol**: wRTC
- **Decimals**: 6
- **Contract**: OpenZeppelin ERC-20 with mint/burn + Ownable
- **Allocation**: 20,000 wRTC

### 2. Bridge Mechanism

Phase 1 (Admin Bridge):
```
Lock:    POST /bridge/lock    {wallet, amount, target_chain, target_address}
         -> Locks RTC on RustChain, returns lock_id
         -> Admin mints equivalent wRTC on target chain

Release: POST /bridge/release {lock_id, burn_tx_hash}
         -> Verifies burn on target chain
         -> Releases RTC on RustChain
```

Phase 2 (Trustless Bridge):
- Ergo anchor commitments serve as cross-chain proofs
- Lock/mint verified by attestation node consensus (2-of-3)

### 3. Eligibility Requirements

Claimants must satisfy BOTH GitHub contribution AND wallet requirements:

#### GitHub Contribution (any one):
| Tier | Requirement | Base Claim |
|------|------------|------------|
| Stargazer | 10+ Scottcjn repos starred | 25 wRTC |
| Contributor | 1+ merged PR | 50 wRTC |
| Builder | 3+ merged PRs | 100 wRTC |
| Security | Verified vulnerability found | 150 wRTC |
| Core | 5+ merged PRs or Star King badge | 200 wRTC |
| Miner | Active attestation history | 100 wRTC |

#### Wallet Requirements (anti-Sybil):
| Chain | Minimum Balance | Wallet Age |
|-------|----------------|------------|
| Solana | 0.1 SOL (~$15) | 7+ days |
| Base | 0.01 ETH (~$25) | 7+ days |

#### Wallet Value Multiplier:
| Solana Balance | Base Balance | Multiplier |
|---------------|-------------|------------|
| 0.1-1 SOL | 0.01-0.1 ETH | 1.0x |
| 1-10 SOL | 0.1-1 ETH | 1.5x |
| 10+ SOL | 1+ ETH | 2.0x |

### 4. Anti-Sybil Stack

| Check | Blocks |
|-------|--------|
| Minimum wallet balance | Empty wallet farms |
| Wallet age > 7 days | Just-created wallets |
| GitHub account age > 30 days | Fresh bot accounts |
| GitHub OAuth (unique) | Multi-claim from same account |
| One claim per GitHub account | Double-dipping across chains |
| One claim per wallet address | Wallet recycling |
| RustChain wallet binding | Links on-chain identity |

### 5. Staged Distribution

```
Stage 1 (Seed):      50,000 RTC allocated
  - Solana:           30,000 wRTC
  - Base:             20,000 wRTC

Stage 2 (Recycle):    Fees from RTC transactions (RIP-303 gas)
  - Community fund receives fee revenue
  - Portion allocated to next airdrop round
  - Minimum 30-day cycle between stages

Stage 3 (Organic):    Community governance decides allocation
  - RIP-0002 governance votes on subsequent airdrops
  - Fee pool sustains ongoing distribution
```

### 6. Claim Flow

```
1. User visits airdrop.rustchain.org
2. Connects GitHub (OAuth) -> verifies contribution tier
3. Generates or enters RustChain wallet name
4. Connects Solana (Phantom) or Base (MetaMask) wallet
5. System checks:
   a. GitHub eligibility (stars, PRs, mining)
   b. Wallet minimum balance
   c. Wallet age
   d. No previous claim
6. If eligible: RTC locked on RustChain, wRTC minted to target wallet
7. Claim receipt stored on-chain with tx hashes
```

### 7. Claim API Endpoints

```
GET  /airdrop/eligibility?github={username}
     -> Returns tier, base_claim, requirements_met

POST /airdrop/claim
     {
       github_token: "oauth_token",
       rtc_wallet: "my-wallet-name",
       target_chain: "solana" | "base",
       target_address: "wallet_address"
     }
     -> Validates eligibility + anti-Sybil
     -> Locks RTC, returns mint instructions

GET  /airdrop/status
     -> Total distributed, remaining, claims by chain

GET  /airdrop/leaderboard
     -> Top claimants by tier
```

### 8. Token Metadata

#### Solana
```json
{
  "name": "Wrapped RustChain Token",
  "symbol": "wRTC",
  "description": "Wrapped RTC from RustChain Proof-of-Antiquity blockchain. 1 wRTC = 1 RTC locked on RustChain.",
  "image": "https://rustchain.org/assets/wrtc-logo.png",
  "external_url": "https://rustchain.org",
  "attributes": [
    {"trait_type": "Bridge", "value": "RustChain Native Bridge"},
    {"trait_type": "Backing", "value": "1:1 RTC locked"}
  ]
}
```

#### Base (ERC-20)
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract WrappedRTC is ERC20, Ownable {
    constructor() ERC20("Wrapped RustChain Token", "wRTC") Ownable(msg.sender) {}

    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }

    function burn(uint256 amount) external {
        _burn(msg.sender, amount);
    }

    function decimals() public pure override returns (uint8) {
        return 6;
    }
}
```

## Security Considerations

1. **Bridge risk**: Phase 1 admin bridge is centralized. Mitigated by transparent lock ledger and small initial allocation.
2. **Sybil attacks**: Multi-layer checks (wallet balance + age + GitHub OAuth + claim limits) make farming uneconomical.
3. **Price manipulation**: wRTC is backed 1:1 by locked RTC. No fractional reserve.
4. **Smart contract risk**: Base ERC-20 uses audited OpenZeppelin contracts. Solana SPL is standard token program.

## Backwards Compatibility

RIP-305 is additive. Existing RTC balances, mining, and RIP-303 gas are unaffected. The bridge creates a new distribution channel without modifying core protocol.

## References

- RIP-303: RTC Gas for Beacon (fee mechanism)
- RIP-302: Agent Economy (job marketplace)
- RIP-0002: Governance System
- BOUNTY_LEDGER.md: Payment transparency
