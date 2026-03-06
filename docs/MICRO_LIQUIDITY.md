# Micro Liquidity Workflow (Bounty #692)

> **Practical tooling for verifying, claiming, and proving liquidity provision in the RustChain ecosystem.**

This document describes the complete workflow for providing micro liquidity to wRTC pools, verifying claims, generating reproducible proof, and safely managing liquidity positions.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Safety First](#safety-first)
- [Liquidity Workflow](#liquidity-workflow)
- [Verification Evidence Flow](#verification-evidence-flow)
- [Claim Proof Generation](#claim-proof-generation)
- [Tools & Scripts](#tools--scripts)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)

---

## Overview

**Micro Liquidity** refers to small-scale liquidity provision (typically $10-$1000) to wRTC trading pairs on Solana DEXs (Raydium, Orca, etc.).

### Why Micro Liquidity?

1. **Accessible Entry Point** - Anyone can participate with minimal capital
2. **Fee Earnings** - Earn trading fees proportional to your share
3. **Ecosystem Support** - Improve wRTC market depth and reduce slippage
4. **Proof-of-Participation** - Documented contributions to the ecosystem

### Supported Pools

| Pool | Pair | DexScreener |
|------|------|-------------|
| **wRTC/SOL** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` / `So111D1r32v1NvGaTQeXj5Xh9VxNf6` | [View](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| **wRTC/USDC** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` / `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` | [View](https://dexscreener.com/solana) |

---

## Safety First

### ⚠️ Critical Safety Checks

**Before providing liquidity:**

1. **Verify Token Mint Addresses**
   ```bash
   # wRTC mint (MUST match exactly)
   12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X
   
   # SOL mint (native)
   So111D1r32v1NvGaTQeXj5Xh9VxNf6
   
   # USDC mint
   EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
   ```

2. **Check Pool Authenticity**
   - Verify pool address matches official DexScreener link
   - Check liquidity depth (avoid pools with <$1000 TVL)
   - Review transaction history for suspicious patterns

3. **Impermanent Loss Awareness**
   - IL occurs when token prices diverge
   - Micro positions may not earn enough fees to offset IL
   - Use the `liquidity_safety_checks.py` tool before committing

4. **Smart Contract Risks**
   - Raydium/Orca are audited but not risk-free
   - Never approve unlimited token allowances
   - Monitor your positions regularly

### Safety Checklist

```markdown
- [ ] Verified token mint addresses character-by-character
- [ ] Confirmed pool authenticity via DexScreener
- [ ] Run safety checks script (`liquidity_safety_checks.py`)
- [ ] Understand impermanent loss risks
- [ ] Have SOL for transaction fees (~0.005 SOL recommended)
- [ ] Starting with small test amount (<$50)
- [ ] Bookmark official URLs (never click DM links)
```

---

## Liquidity Workflow

### Step 1: Prepare Wallet

```bash
# Install Solana CLI tools (optional but recommended)
sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)"

# Verify wallet setup
solana-keygen pubkey  # Should show your wallet address
```

**Wallet Requirements:**
- Solana wallet (Phantom, Solflare, Backpack)
- SOL for fees (0.005-0.01 SOL recommended)
- wRTC tokens (or SOL to swap)

### Step 2: Verify Pool Status

```bash
# Run the verification tool
python tools/verify_liquidity.py --pool 8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb

# Output example:
# ✅ Pool: 8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb
# ✅ Pair: wRTC/SOL
# ✅ TVL: $12,450
# ✅ 24h Volume: $3,200
# ✅ 24h Fees: $9.60
# ✅ Your Share (est.): 0.08%
```

### Step 3: Add Liquidity via Raydium

1. Navigate to **Raydium Liquidity**:
   ```
   https://raydium.io/liquidity/?pool=8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb
   ```

2. **Connect Wallet** - Click "Connect Wallet" and approve

3. **Select "Add Liquidity"** tab

4. **Enter Amounts**:
   - Input SOL amount (e.g., 0.1 SOL)
   - wRTC amount auto-calculates (50/50 ratio)
   - Review the exchange rate

5. **Review Position**:
   - Pool share percentage
   - Estimated APY from fees
   - Impermanent loss risk indicator

6. **Approve Tokens** (first time only):
   - Click "Approve wRTC"
   - Sign wallet transaction

7. **Add Liquidity**:
   - Click "Add" or "Deposit"
   - Sign the transaction
   - Wait for confirmation (~5-10 seconds)

### Step 4: Verify LP Token Receipt

After adding liquidity, you receive **LP tokens** representing your pool share.

```bash
# Check LP token balance in wallet
# Or use the verification tool:
python tools/verify_liquidity.py --check-lp --wallet YOUR_WALLET_ADDRESS
```

**LP Token Details:**
- **wRTC/SOL LP**: Represents your share of the pool
- **Non-transferable** (some LP tokens, check Raydium docs)
- **Required for claiming fees or removing liquidity**

---

## Verification Evidence Flow

### Purpose

Document your liquidity provision for:
- **Bounty claims** (proof of ecosystem participation)
- **Reward eligibility** (future liquidity mining programs)
- **Personal records** (track positions across wallets)
- **Community verification** (transparent contributions)

### Evidence Collection

The `verify_liquidity.py` tool automatically collects:

1. **Pool State Snapshot**
   - Current TVL and reserves
   - Your LP token balance
   - Pool share percentage
   - Timestamp of verification

2. **Transaction Proof**
   - Add liquidity transaction signature
   - Block height and timestamp
   - Token amounts deposited

3. **Historical Data** (optional)
   - Fee earnings over time
   - Position value changes
   - Impermanent loss calculation

### Generating Evidence Report

```bash
# Generate comprehensive evidence report
python tools/verify_liquidity.py \
  --wallet YOUR_WALLET_ADDRESS \
  --pool 8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb \
  --output evidence_report.json \
  --include-history

# Output: JSON file with all verification data
```

**Evidence Report Structure:**
```json
{
  "verification_id": "liq_692_abc123...",
  "timestamp": "2026-03-07T10:30:00Z",
  "wallet": "7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN",
  "pool": {
    "address": "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb",
    "pair": "wRTC/SOL",
    "tvl_usd": 12450.00
  },
  "position": {
    "lp_tokens": "1234567890",
    "share_percent": 0.08,
    "value_usd": 9.96
  },
  "transactions": [
    {
      "signature": "5xKjH8...",
      "type": "add_liquidity",
      "timestamp": "2026-03-07T10:25:00Z",
      "sol_deposited": 0.1,
      "wrtc_deposited": 125.5
    }
  ],
  "proof_hash": "QmX7Y8Z9..."
}
```

---

## Claim Proof Generation

### Purpose

Generate **reproducible, verifiable proof** of liquidity provision for:
- Bounty #692 completion claims
- Community reward programs
- Ecosystem contribution tracking

### Using the Claim Proof Generator

```bash
# Generate claim proof
python tools/claim_proof_generator.py \
  --wallet YOUR_WALLET_ADDRESS \
  --bounty 692 \
  --output claim_proof_692.json
```

### Claim Proof Structure

```json
{
  "claim_type": "micro_liquidity_bounty_692",
  "claimant": "7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN",
  "claim_date": "2026-03-07T10:30:00Z",
  "evidence": {
    "verification_id": "liq_692_abc123...",
    "pool_address": "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb",
    "position_value_usd": 9.96,
    "duration_days": 7,
    "fees_earned_usd": 0.42
  },
  "attestation": {
    "method": "solana_transaction_signature",
    "signature": "5xKjH8...",
    "verifier": "rustchain_liquidity_tool_v1.0"
  },
  "reproducibility": {
    "tool_version": "1.0.0",
    "command": "python tools/claim_proof_generator.py --wallet ...",
    "verification_url": "https://solscan.io/account/7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN"
  }
}
```

### Submitting Your Claim

1. **Generate Proof**: Run `claim_proof_generator.py`
2. **Review Evidence**: Verify all data is accurate
3. **Create GitHub Issue**:
   - Title: `Bounty #692 Claim - [Your Wallet Address]`
   - Attach: `claim_proof_692.json`
   - Include: Brief description of your contribution
4. **Community Verification**: Others can reproduce your proof using the public tool

---

## Tools & Scripts

### verify_liquidity.py

**Purpose**: Verify pool status and your liquidity position

```bash
# Basic pool verification
python tools/verify_liquidity.py --pool POOL_ADDRESS

# Check your LP position
python tools/verify_liquidity.py --wallet YOUR_WALLET --check-lp

# Generate evidence report
python tools/verify_liquidity.py \
  --wallet YOUR_WALLET \
  --pool POOL_ADDRESS \
  --output report.json \
  --include-history

# Safety checks before adding liquidity
python tools/verify_liquidity.py --pool POOL_ADDRESS --safety-check
```

**Options:**
- `--pool`: Pool address to verify
- `--wallet`: Your wallet address (optional)
- `--check-lp`: Check LP token balance
- `--output`: Output file for report (JSON)
- `--include-history`: Include historical data
- `--safety-check`: Run safety checks only

### claim_proof_generator.py

**Purpose**: Generate reproducible claim proof for bounty submissions

```bash
# Generate standard claim proof
python tools/claim_proof_generator.py \
  --wallet YOUR_WALLET \
  --bounty 692

# Generate with custom metadata
python tools/claim_proof_generator.py \
  --wallet YOUR_WALLET \
  --bounty 692 \
  --metadata '{"duration_days": 14, "notes": "Early liquidity provider"}' \
  --output custom_claim.json
```

**Options:**
- `--wallet`: Your wallet address (required)
- `--bounty`: Bounty ID (default: 692)
- `--metadata`: Additional JSON metadata (optional)
- `--output`: Output file (default: `claim_proof_<bounty>.json`)

### liquidity_safety_checks.py

**Purpose**: Comprehensive safety analysis before providing liquidity

```bash
# Run all safety checks
python tools/liquidity_safety_checks.py \
  --pool POOL_ADDRESS \
  --wallet YOUR_WALLET

# Check specific risks
python tools/liquidity_safety_checks.py --pool POOL_ADDRESS --check impermanent_loss
python tools/liquidity_safety_checks.py --pool POOL_ADDRESS --check rug_pull
python tools/liquidity_safety_checks.py --pool POOL_ADDRESS --check contract_risk
```

**Safety Checks Performed:**
1. **Token Authenticity**: Verify mint addresses
2. **Pool Health**: TVL, volume, age analysis
3. **Impermanent Loss Risk**: Price volatility assessment
4. **Rug Pull Indicators**: Liquidity lock, owner controls
5. **Contract Risk**: Audit status, known vulnerabilities
6. **Wallet Security**: Approval limits, transaction history

### liquidity_dashboard.html

**Purpose**: Web-based dashboard for monitoring liquidity positions

**Features:**
- Real-time position value tracking
- Fee earnings visualization
- Impermanent loss calculator
- Historical performance charts
- Multi-wallet support

**Usage:**
1. Open `tools/liquidity_dashboard.html` in browser
2. Enter your wallet address
3. View all liquidity positions
4. Export reports as PDF/JSON

---

## API Reference

### Solana RPC (for direct integration)

```bash
# Get account info (LP token balance)
curl -X POST "https://api.mainnet-beta.solana.com" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "getTokenAccountsByOwner",
    "params": [
      "YOUR_WALLET_ADDRESS",
      {
        "mint": "LP_TOKEN_MINT_ADDRESS"
      },
      {
        "encoding": "jsonParsed"
      }
    ]
  }'

# Get transaction details
curl -X POST "https://api.mainnet-beta.solana.com" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "getTransaction",
    "params": [
      "TRANSACTION_SIGNATURE",
      {
        "encoding": "jsonParsed"
      }
    ]
  }'
```

### Raydium API (unofficial, use with caution)

```bash
# Get pool info
curl "https://api.raydium.io/v2/sdk/liquidity/mainnet?id=POOL_ADDRESS"

# Get TVL and volume
curl "https://api.raydium.io/v2/ammV3/pools?poolIds=POOL_ADDRESS"
```

### DexScreener API

```bash
# Get pool data
curl "https://api.dexscreener.com/latest/dex/pairs/solana/POOL_ADDRESS"

# Get token info
curl "https://api.dexscreener.com/latest/dex/tokens/12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
```

---

## Troubleshooting

### Common Issues

#### Issue: "LP tokens not showing in wallet"

**Solution:**
- Manually add LP token to wallet using mint address
- Check transaction on Solscan to confirm completion
- Some wallets don't auto-display LP tokens

#### Issue: "Transaction failed: Insufficient funds"

**Solution:**
- Ensure you have enough SOL for both tokens + fees
- Add 0.005 SOL buffer for transaction fees
- Check for pending transactions consuming balance

#### Issue: "Cannot verify pool - API error"

**Solution:**
- Check pool address is correct (44 characters, base58)
- Verify pool exists on DexScreener
- Try alternative data source (Raydium direct)
- Network congestion - retry in a few minutes

#### Issue: "Claim proof generation failed"

**Solution:**
- Verify wallet address format (Solana base58)
- Ensure you have at least one liquidity transaction
- Check tool dependencies: `pip install -r requirements.txt`
- Run with `--verbose` flag for detailed error output

#### Issue: "Impermanent loss seems too high"

**Solution:**
- IL is unrealized until you withdraw
- Price divergence causes IL; convergence reduces it
- Use IL calculator in dashboard to model scenarios
- Consider stable pairs (wRTC/USDC) for lower IL risk

### Emergency Actions

#### Remove Liquidity Quickly

1. Go to Raydium Liquidity page
2. Connect wallet
3. Find your position
4. Click "Remove" or "Withdraw"
5. Select amount (100% for full removal)
6. Confirm transaction

#### Revoke Token Approvals

If you suspect compromised approvals:

1. Go to [Solana Revoke](https://solrevoke.com) or similar tool
2. Connect wallet
3. Review all token approvals
4. Revoke suspicious or unused approvals
5. Confirm transaction

### Support Resources

| Resource | Link |
|----------|------|
| **GitHub Issues** | [Scottcjn/Rustchain](https://github.com/Scottcjn/Rustchain/issues) |
| **Raydium Docs** | [docs.raydium.io](https://docs.raydium.io) |
| **Solana Docs** | [docs.solana.com](https://docs.solana.com) |
| **DexScreener** | [dexscreener.com](https://dexscreener.com) |
| **Solscan Explorer** | [solscan.io](https://solscan.io) |

---

## Appendix: Reproducible Claim Proof Example

### Step-by-Step Reproduction

Anyone can verify a claim proof by following these steps:

1. **Obtain Claim Proof File**
   ```bash
   # Download from GitHub issue
   curl -O "https://github.com/Scottcjn/Rustchain/files/.../claim_proof_692.json"
   ```

2. **Verify on Solana**
   ```bash
   # Extract wallet and transaction from proof
   python tools/verify_liquidity.py \
     --wallet $(jq -r '.claimant' claim_proof_692.json) \
     --verify-tx $(jq -r '.attestation.signature' claim_proof_692.json)
   ```

3. **Cross-Check on Solscan**
   ```
   Navigate to: https://solscan.io/account/<claimant_wallet>
   Verify LP token balance matches proof
   Verify transaction history shows liquidity addition
   ```

4. **Validate Pool State**
   ```bash
   # Current pool state may differ, but historical data should align
   python tools/verify_liquidity.py \
     --pool $(jq -r '.evidence.pool_address' claim_proof_692.json)
   ```

### Claim Proof Verification Checklist

```markdown
- [ ] Claimant wallet address is valid Solana format
- [ ] Transaction signature exists and is valid
- [ ] Transaction type is "add_liquidity" or similar
- [ ] LP tokens were received by claimant wallet
- [ ] Pool address matches official wRTC pool
- [ ] Timestamp is within acceptable claim window
- [ ] Tool version is current (reproducibility check)
```

---

<div align="center">

**Bounty #692**: Micro Liquidity Workflow

*Provide liquidity, verify claims, earn rewards.*

[GitHub Issues](https://github.com/Scottcjn/Rustchain/issues) • [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) • [Raydium](https://raydium.io)

</div>
