# wRTC SPL Token Deployment Guide

Complete guide for deploying and managing **wRTC (Wrapped RustChain)** as a Solana SPL Token.

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment Steps](#deployment-steps)
- [Verification](#verification)
- [Bridge Integration](#bridge-integration)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

---

## Overview

**wRTC** is the Solana representation of RustChain's native **RTC** token, enabling:

- 🔄 Cross-chain bridging (RTC ↔ wRTC)
- 💱 DEX trading on Raydium, Jupiter, Orca
- 🏦 DeFi integration on Solana
- 💰 Miner reward distributions

**Track A Scope**: Core SPL token deployment with multi-sig governance.

---

## Prerequisites

### System Requirements

- Python 3.9+
- Solana CLI tools (v1.16+)
- Access to Solana RPC endpoint

### Install Dependencies

```bash
# Navigate to solana-spl directory
cd integrations/solana-spl

# Install Python dependencies
pip install -r requirements.txt

# Verify Solana CLI
solana --version

# Generate keypair (if you don't have one)
solana-keygen new -o ~/.config/solana/id.json
```

### Environment Setup

```bash
# Set Solana configuration
solana config set --url devnet
solana config set --keypair ~/.config/solana/id.json

# Verify configuration
solana config get
```

---

## Quick Start

### Testnet Deployment (Devnet)

```bash
# 1. Navigate to deployment directory
cd integrations/solana-spl

# 2. Run deployment (dry-run first)
python deploy.py --network devnet --config config/testnet-config.json --dry-run

# 3. Actual deployment
python deploy.py --network devnet --config config/testnet-config.json

# 4. Verify deployment
python deploy.py --verify --mint-address <YOUR_MINT_ADDRESS> --network devnet
```

### Mainnet Deployment

```bash
# ⚠️ WARNING: Mainnet deployment incurs real SOL fees

# 1. Review configuration
cat config/mainnet-config.json

# 2. Run verification first
python deploy.py --verify --mint-address 12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X --network mainnet

# 3. Deploy (requires --confirm flag)
python deploy.py --network mainnet --config config/mainnet-config.json --confirm
```

---

## Configuration

### Configuration Files

| File | Purpose |
|------|---------|
| `config/default-config.json` | Default configuration |
| `config/testnet-config.json` | Testnet/devnet settings |
| `config/mainnet-config.json` | Mainnet production settings |

### Configuration Structure

```json
{
  "token": {
    "name": "Wrapped RustChain",
    "symbol": "wRTC",
    "decimals": 9,
    "description": "...",
    "image_url": "https://...",
    "external_url": "https://..."
  },
  "multisig": {
    "signers": ["PubKey1", "PubKey2", ...],
    "threshold": 3
  },
  "escrow": {
    "daily_mint_cap": 100000000000000,
    "per_tx_limit": 10000000000000
  }
}
```

### Key Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `decimals` | Token decimal places | 9 |
| `threshold` | Multi-sig required signatures | 3 |
| `daily_mint_cap` | Max wRTC minted per day | 100,000 |
| `per_tx_limit` | Max wRTC per transaction | 10,000 |

---

## Deployment Steps

### Step 1: Create Multi-sig Wallet

Before deploying the token, set up the multi-sig governance:

```bash
# Using Solana CLI + spl-multisig
spl-multisig create 3 \
  Signer1PubKey \
  Signer2PubKey \
  Signer3PubKey \
  Signer4PubKey \
  Signer5PubKey
```

Record the multi-sig address for use as mint/freeze authority.

### Step 2: Deploy Token Mint

```bash
python deploy.py \
  --network devnet \
  --config config/testnet-config.json \
  --keypair ~/.config/solana/id.json
```

**Output:**
```
✅ Token deployed successfully!
   Mint Address: <MINT_ADDRESS>
   Escrow Account: <ESCROW_ACCOUNT>
```

### Step 3: Initialize Metadata

```bash
# Using SPL Token CLI
spl-token initialize-metadata \
  <MINT_ADDRESS> \
  "Wrapped RustChain" \
  "wRTC" \
  "https://rustchain.org/wrtc-logo.png"
```

### Step 4: Create Escrow Account

```bash
python -c "
from spl_deployment import SPLTokenDeployment, load_config_from_file
from solders.keypair import Keypair

deployment = SPLTokenDeployment('https://api.devnet.solana.com')
deployment.mint_address = Pubkey.from_string('<MINT_ADDRESS>')

# Create escrow
keypair = Keypair.from_json_file('~/.config/solana/id.json')
escrow = deployment.create_escrow_account(keypair, keypair.pubkey())
print(f'Escrow: {escrow}')
"
```

### Step 5: Verify Deployment

```bash
python deploy.py \
  --verify \
  --mint-address <MINT_ADDRESS> \
  --network devnet
```

---

## Verification

### Manual Verification Commands

```bash
# Check token supply
spl-token supply <MINT_ADDRESS>

# View mint info
spl-token account-info <MINT_ADDRESS>

# List token accounts
spl-token accounts <MINT_ADDRESS>

# Check transaction history
solana transaction-history <MINT_ADDRESS>
```

### Programmatic Verification

```python
from spl_deployment import SPLTokenDeployment

deployment = SPLTokenDeployment("https://api.devnet.solana.com")
deployment.mint_address = Pubkey.from_string("<MINT_ADDRESS>")

report = deployment.verify_deployment()
print(json.dumps(report, indent=2))
```

### Verification Checklist

- [ ] Mint account exists on-chain
- [ ] Decimals set correctly (9)
- [ ] Mint authority = multi-sig address
- [ ] Freeze authority = multi-sig address
- [ ] Metadata initialized (name, symbol, image)
- [ ] Escrow account created
- [ ] Test mint/burn successful (devnet only)

---

## Bridge Integration

### Bridge Flow Architecture

```
┌─────────────┐                    ┌─────────────┐
│  RustChain  │                    │   Solana    │
│   (RTC)     │                    │   (wRTC)    │
└──────┬──────┘                    └──────┬──────┘
       │                                  │
       │ 1. Lock RTC                      │
       │─────────────────────────────────>│
       │                                  │
       │ 2. Verify Lock                   │
       │<────────────────────────────────>│
       │                                  │
       │ 3. Mint wRTC                     │
       │─────────────────────────────────>│
       │                                  │
       │ 4. Confirm to User               │
       │<─────────────────────────────────│
```

### Using Bridge Integration

```python
from spl_deployment import BridgeIntegration, SPLTokenDeployment

# Initialize
spl = SPLTokenDeployment("https://api.mainnet-beta.solana.com")
bridge = BridgeIntegration(spl)

# Verify RTC lock on RustChain
verified = bridge.verify_rtc_lock("rustchain_tx_hash", 1000)

# Authorize wRTC mint
auth = bridge.authorize_mint(
    destination="SolanaUserAddress",
    amount=1000,
    rustchain_proof="rustchain_tx_hash"
)

# Check escrow balance
balance = bridge.get_escrow_balance("escrow_account_address")
```

---

## Security Considerations

### Multi-sig Governance

**Required for:**
- Minting new wRTC
- Freezing accounts (emergency only)
- Updating metadata
- Changing bridge parameters

**Signer Roles:**
1. Foundation Treasury
2. BoTTube Bridge Operator
3. Community Representative
4. Security Auditor (6-month term)
5. Core Developer Representative

### Circuit Breakers

| Control | Limit | Trigger |
|---------|-------|---------|
| Daily Mint Cap | 100,000 wRTC | Automatic |
| Per-Tx Limit | 10,000 wRTC | Automatic |
| Emergency Pause | 24 hours | Multi-sig (1 signer) |

### Audit Requirements

Before mainnet deployment:

- [ ] Smart contract audit (CertiK or equivalent)
- [ ] Bridge oracle security review
- [ ] Multi-sig key ceremony
- [ ] Testnet dry-run (minimum 1 week)
- [ ] Bug bounty program ($10k+ minimum)

---

## Troubleshooting

### Common Issues

#### "Keypair not found"

```bash
# Check keypair path
ls -la ~/.config/solana/id.json

# Or specify custom path
python deploy.py --keypair /path/to/keypair.json
```

#### "Insufficient funds for transaction"

```bash
# Check SOL balance
solana balance

# Request devnet SOL (testnet only)
solana airdrop 2
```

#### "Mint authority mismatch"

Verify mint authority matches expected multi-sig:

```bash
spl-token account-info <MINT_ADDRESS> | grep "Mint authority"
```

#### "Transaction failed: Blockhash not found"

Retry with recent blockhash:

```bash
solana config set --url devnet
python deploy.py --network devnet --config config/testnet-config.json
```

### Getting Help

- **Documentation**: `rips/docs/RIP-0305-solana-spl-token-deployment.md`
- **Issues**: GitHub Issues (bounty #1509)
- **Discord**: RustChain community server

---

## Appendix: Command Reference

### Deployment Commands

```bash
# Dry run
python deploy.py --dry-run --network devnet

# Deploy
python deploy.py --network devnet --config config/testnet-config.json

# Verify
python deploy.py --verify --mint-address <ADDRESS> --network devnet

# Report
python deploy.py --report --config config/mainnet-config.json
```

### SPL Token CLI

```bash
# Create token
spl-token create-token --decimals 9

# Create account
spl-token create-account <MINT_ADDRESS>

# Mint tokens
spl-token mint <MINT_ADDRESS> 1000 <RECIPIENT>

# Transfer
spl-token transfer <MINT_ADDRESS> 100 <RECIPIENT>

# Burn tokens
spl-token burn <MINT_ADDRESS> 100
```

---

**Last Updated**: March 9, 2026  
**Version**: 1.0.0 (Track A)  
**License**: Apache 2.0
