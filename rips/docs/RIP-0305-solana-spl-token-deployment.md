---
title: RIP-0305: Solana SPL Token Deployment for wRTC Bridge
author: RustChain Core Team
status: Draft
created: 2026-03-09
last_updated: 2026-03-09
license: Apache 2.0
track: A
---

# RIP-0305: Solana SPL Token Deployment for wRTC Bridge

## Summary

This RIP defines the specification and implementation for deploying and managing **wrapped RTC (wRTC)** as a Solana SPL Token, enabling seamless cross-chain bridging between RustChain and Solana ecosystems via the BoTTube Bridge infrastructure.

**Track A**: Core SPL token deployment, minting authority, and integration-ready artifacts.

---

## Abstract

RustChain's native token **RTC** requires a Solana representation (**wRTC**) to enable:
- DEX trading on Raydium, Orca, Jupiter
- Integration with Solana DeFi protocols
- Cross-chain bridge operations via BoTTube
- Community token distributions and airdrops

This specification covers:
1. SPL Token mint deployment with proper authority structure
2. Multi-sig governance for mint and freeze authorities
3. Bridge escrow account architecture
4. Integration hooks for RustChain node settlement
5. Security controls and upgrade paths

---

## Motivation

### Current State
- wRTC exists on Solana (mint: `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`)
- Trading live on Raydium and DexScreener
- BoTTube Bridge operational

### Problems to Solve
1. **Authority centralization**: Single key controls mint/freeze
2. **Bridge transparency**: Escrow accounting not publicly auditable
3. **Integration friction**: No SDK for third-party bridges/exchanges
4. **Governance gap**: No multi-sig or timelock on critical operations

### Solution
Deploy production-ready SPL token infrastructure with:
- Multi-sig governance (3-of-5 trusted signers)
- Program-derived escrow accounts for bridge custody
- Open-source deployment scripts and verification
- Integration SDK for exchanges and wallets

---

## Specification

### 1. Token Mint Configuration

```yaml
token_name: "Wrapped RustChain"
token_symbol: "wRTC"
decimals: 9
mint_authority: Multi-sig (3-of-5)
freeze_authority: Multi-sig (3-of-5)
supply_model: "Bridge-backed (1:1 with RTC)"
```

### 2. Authority Structure

**Multi-sig Signers** (5 initial, 3 required):
1. RustChain Foundation Treasury
2. BoTTube Bridge Operator
3. Community-elected representative
4. Security auditor (temporary, 6-month term)
5. Core developer representative

**Powers**:
- `mint_authority`: Mint new wRTC (only against locked RTC)
- `freeze_authority`: Freeze malicious accounts (governance-approved)
- `metadata_authority`: Update token metadata
- `close_authority`: Close empty token accounts (user-initiated)

### 3. Bridge Escrow Architecture

```
┌─────────────────────────────────────────────────────┐
│              BoTTube Bridge Program                 │
├─────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────┐   │
│  │         wRTC Escrow Vault (PDA)              │   │
│  │  - Holds wRTC backing locked RTC             │   │
│  │  - Mint: 12TAdKXxcGf6oCv4rqDz2NkgxjHq6HQKoxKZYGf5i4X │
│  │  - Authority: Bridge Program                 │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │         RTC Lock Vault (RustChain)           │   │
│  │  - Holds native RTC                          │   │
│  │  - 1:1 backing verification                  │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### 4. Minting/Burning Flow

**Mint (RTC → wRTC)**:
1. User sends RTC to RustChain lock vault
2. RustChain node verifies lock (epoch settlement)
3. Bridge oracle signs mint authorization
4. Multi-sig threshold reached (3-of-5)
5. wRTC minted to user's Solana address
6. Event emitted for tracking

**Burn (wRTC → RTC)**:
1. User sends wRTC to burn address
2. Bridge verifies burn transaction
3. Multi-sig approves release
4. RTC released from RustChain vault
5. Event emitted for tracking

### 5. Security Controls

**Minting Limits**:
- Daily mint cap: 100,000 wRTC (emergency circuit breaker)
- Per-transaction limit: 10,000 wRTC
- Total supply cap: Equal to circulating RTC supply (audited monthly)

**Freeze Conditions** (governance-only):
- Confirmed exploit or hack
- Court order / legal requirement
- User-requested (with proof of loss)

**Upgrade Path**:
- v1: Current single-key deployment (legacy)
- v2: Multi-sig governance (this RIP)
- v3: Programmatic governance (future, SPL Governance DAO)

---

## Rationale

### Why 9 Decimals?
- Matches Solana standard (SOL, most SPL tokens)
- Enables micro-transactions for miner rewards
- Compatible with Jupiter aggregator routing

### Why Multi-sig vs. DAO?
- Faster deployment (weeks vs. months)
- Lower gas overhead for operations
- Clear accountability for bridge operations
- Upgrade path to full DAO governance later

### Why Freeze Authority?
- Regulatory compliance requirement for CEX listings
- Protection against confirmed exploits
- Governance-controlled with strict conditions

---

## Backwards Compatibility

### Legacy wRTC Holders
- Existing wRTC (single-key mint) remains valid
- Optional migration to v2 mint (governance-controlled)
- Bridge supports both versions during transition

### API Compatibility
- All existing Raydium/Jupiter pools continue working
- No changes required for DEX integrations
- Bridge API maintains v1 endpoints

---

## Implementation Notes

### Deployment Steps

1. **Create Multi-sig Wallet**
   ```bash
   solana-keygen new -o multisig-keypair.json
   # Repeat for 5 signers
   ```

2. **Deploy SPL Token Mint**
   ```bash
   spl-token create-token \
     --enable-metadata \
     --freeze-authority MULTISIG_PUBKEY \
     --mint-authority MULTISIG_PUBKEY
   ```

3. **Initialize Metadata**
   ```bash
   spl-token initialize-metadata \
     wRTC_MINT_ADDRESS \
     "Wrapped RustChain" \
     "wRTC" \
     "https://rustchain.org/wrtc-logo.png"
   ```

4. **Create Bridge Escrow**
   ```bash
   spl-token create-account wRTC_MINT_ADDRESS \
     --owner BRIDGE_PROGRAM_PDA
   ```

5. **Verify Deployment**
   ```bash
   spl-token supply wRTC_MINT_ADDRESS
   spl-token account-info wRTC_MINT_ADDRESS
   ```

### Integration SDK

Python SDK provided in `integrations/solana-spl/`:
- `deploy.py`: Automated deployment script
- `bridge.py`: Bridge integration helpers
- `verify.py`: Deployment verification tools
- `sdk.py`: Client SDK for third parties

---

## Reference Implementation

See:
- `integrations/solana-spl/` - Deployment scripts and SDK
- `integrations/solana-spl/tests/` - Test suite
- `docs/solana-spl-deployment.md` - Operator guide
- `schemas/spl-token-config.json` - Configuration schema

---

## Governance

### Proposal Requirements
Changes to this RIP require:
- 7-day discussion period
- 3-of-5 multi-sig approval
- Public announcement 48 hours before execution

### Emergency Actions
Single signer may execute in emergency (exploit active):
- Freeze specific account
- Pause minting (24-hour max)
- Must be ratified by 3-of-5 within 48 hours

---

## Audit Requirements

Before mainnet deployment:
1. [ ] Smart contract audit (CertiK or equivalent)
2. [ ] Bridge oracle security review
3. [ ] Multi-sig signer key ceremony
4. [ ] Testnet dry-run (devnet)
5. [ ] Bug bounty program launch ($10k min)

---

## Timeline

| Phase | Milestone | Target |
|-------|-----------|--------|
| 1 | Testnet deployment | Week 1 |
| 2 | Security audit | Week 2-3 |
| 3 | Multi-sig setup | Week 4 |
| 4 | Mainnet deployment | Week 5 |
| 5 | Migration period | Week 6-8 |
| 6 | Legacy deprecation | Week 12 |

---

## Appendix A: Token Metadata

```json
{
  "name": "Wrapped RustChain",
  "symbol": "wRTC",
  "description": "Solana-wrapped version of RustChain (RTC) token, backed 1:1 by locked RTC on RustChain.",
  "image": "https://rustchain.org/wrtc-logo.png",
  "external_url": "https://rustchain.org",
  "attributes": [
    {"trait_type": "Chain", "value": "Solana"},
    {"trait_type": "Standard", "value": "SPL Token"},
    {"trait_type": "Backing", "value": "1:1 RTC"},
    {"trait_type": "Bridge", "value": "BoTTube"}
  ]
}
```

---

## Appendix B: Multi-sig Signer Addresses (Testnet)

| Signer | Role | Address |
|--------|------|---------|
| 1 | Foundation | `TODO` |
| 2 | BoTTube | `TODO` |
| 3 | Community | `TODO` |
| 4 | Auditor | `TODO` |
| 5 | Core Dev | `TODO` |

---

© 2026 RustChain Foundation — Apache 2.0 License
