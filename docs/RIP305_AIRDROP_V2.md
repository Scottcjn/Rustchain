# RIP-305: Cross-Chain Airdrop Implementation

**Issue:** [#1149](https://github.com/Scottcjn/rustchain-bounties/issues/1149)  
**Status:** Implemented  
**Reward:** 100-200 RTC (staged payments)

## Overview

This implementation provides cross-chain airdrop infrastructure for distributing **50,000 wrapped RTC (wRTC)** on Solana and Base L2.

## Implementation Status

| Track | Description | Status | Reward |
|-------|-------------|--------|--------|
| **A** | Solana SPL Token (wRTC) | ✅ Infrastructure Ready | 75 RTC |
| **B** | Base ERC-20 Token (wRTC) | ✅ Infrastructure Ready | 75 RTC |
| **C** | Bridge API | ✅ Implemented | 50 RTC |
| **D** | Claim Page | 🔄 Frontend Required | 50 RTC |

## Files Added

```
node/
├── airdrop_v2.py          # Core airdrop infrastructure
└── test_airdrop_v2.py     # Comprehensive test suite
```

## Architecture

### Core Components

1. **AirdropV2 Class** (`airdrop_v2.py`)
   - Eligibility checking with anti-Sybil measures
   - Tier determination based on GitHub activity
   - Claim processing and tracking
   - Bridge lock/release operations
   - Allocation management

2. **Database Schema**
   - `airdrop_claims` - Track all airdrop claims
   - `bridge_locks` - Bridge transaction ledger
   - `sybil_cache` - Anti-Sybil check cache
   - `airdrop_allocation` - Per-chain allocation tracking

3. **API Endpoints** (Flask integration)
   - `/api/airdrop/eligibility` - Check eligibility
   - `/api/airdrop/claim` - Submit claim
   - `/api/airdrop/claim/<id>` - Get claim status
   - `/api/airdrop/stats` - Get statistics
   - `/api/bridge/lock` - Create bridge lock
   - `/api/bridge/lock/<id>/confirm` - Confirm lock
   - `/api/bridge/lock/<id>/release` - Release lock
   - `/api/bridge/lock/<id>` - Get lock status

## Eligibility Tiers

| Tier | Requirement | wRTC Reward |
|------|-------------|-------------|
| Stargazer | 10+ repos starred | 25 wRTC |
| Contributor | 1+ merged PR | 50 wRTC |
| Builder | 3+ merged PRs | 100 wRTC |
| Security | Verified vulnerability | 150 wRTC |
| Core | 5+ merged PRs / Star King | 200 wRTC |
| Miner | Active attestation | 100 wRTC |

## Anti-Sybil Measures

| Check | Purpose | Threshold |
|-------|---------|-----------|
| Wallet balance | Filters empty wallet farms | 0.1 SOL / 0.01 ETH |
| Wallet age | Blocks fresh wallets | > 7 days |
| GitHub account | Blocks new bot accounts | > 30 days |
| One claim per GitHub/wallet | Prevents double-dipping | - |

## Allocation

| Chain | Total Allocation |
|-------|-----------------|
| Solana | 30,000 wRTC |
| Base | 20,000 wRTC |

## Usage

### Python API

```python
from airdrop_v2 import AirdropV2

# Initialize
airdrop = AirdropV2(db_path="airdrop.db")

# Check eligibility
result = airdrop.check_eligibility(
    github_username="username",
    wallet_address="RTC1234567890123456789012345678901234567890",
    chain="base",
    github_token="optional_github_token",
)

if result.eligible:
    print(f"Eligible for {result.reward_wrtc} wRTC ({result.tier})")
    
    # Submit claim
    success, message, claim = airdrop.claim_airdrop(
        github_username="username",
        wallet_address="RTC1234567890123456789012345678901234567890",
        chain="base",
        tier=result.tier,
    )
    
    if success:
        print(f"Claim created: {claim.claim_id}")
        
        # After token transfer, finalize claim
        airdrop.finalize_claim(
            claim_id=claim.claim_id,
            tx_signature="0x..."
        )
```

### REST API

#### Check Eligibility

```bash
curl -X POST https://rustchain.org/api/airdrop/eligibility \
  -H "Content-Type: application/json" \
  -d '{
    "github_username": "username",
    "wallet_address": "RTC1234567890123456789012345678901234567890",
    "chain": "base"
  }'
```

Response:
```json
{
  "ok": true,
  "eligible": true,
  "tier": "contributor",
  "reward_uwrtc": 50000000,
  "reward_wrtc": 50.0,
  "reason": "Eligible for 1+ merged PR",
  "checks": {
    "github_valid": true,
    "wallet_valid": true
  }
}
```

#### Submit Claim

```bash
curl -X POST https://rustchain.org/api/airdrop/claim \
  -H "Content-Type: application/json" \
  -d '{
    "github_username": "username",
    "wallet_address": "RTC1234567890123456789012345678901234567890",
    "chain": "base",
    "tier": "contributor"
  }'
```

#### Create Bridge Lock

```bash
curl -X POST https://rustchain.org/api/bridge/lock \
  -H "Content-Type: application/json" \
  -d '{
    "from_address": "RTC1234567890123456789012345678901234567890",
    "to_address": "0x1234567890123456789012345678901234567890",
    "from_chain": "rustchain",
    "to_chain": "base",
    "amount_wrtc": 100
  }'
```

#### Get Statistics

```bash
curl https://rustchain.org/api/airdrop/stats
```

Response:
```json
{
  "ok": true,
  "stats": {
    "total_claims": 42,
    "by_tier": {
      "contributor": {"count": 20, "total_wrtc": 1000},
      "builder": {"count": 15, "total_wrtc": 1500}
    },
    "by_chain": {
      "base": {"count": 25, "total_wrtc": 1250},
      "solana": {"count": 17, "total_wrtc": 850}
    },
    "allocation": {
      "base": {
        "total_wrtc": 20000,
        "claimed_wrtc": 1250,
        "remaining_wrtc": 18750,
        "percent_claimed": 6.25
      },
      "solana": {
        "total_wrtc": 30000,
        "claimed_wrtc": 850,
        "remaining_wrtc": 29150,
        "percent_claimed": 2.83
      }
    }
  }
}
```

## Integration with RustChain Node

To integrate airdrop routes into the main node:

```python
# In rustchain_v2_integrated_v2.2.1_rip200.py or similar

from airdrop_v2 import AirdropV2, init_airdrop_routes

# Initialize airdrop system
AIRDROP_DB_PATH = os.path.join(DATA_DIR, "airdrop.db")
airdrop = AirdropV2(db_path=AIRDROP_DB_PATH)

# Register API routes
init_airdrop_routes(app, airdrop, AIRDROP_DB_PATH)
```

## Testing

Run the test suite:

```bash
cd node
python -m pytest test_airdrop_v2.py -v
```

Or run directly:

```bash
cd node
python test_airdrop_v2.py
```

### Test Coverage

- ✅ Eligibility tier definitions
- ✅ Database initialization
- ✅ Allocation tracking
- ✅ Eligibility checks (with mocked GitHub API)
- ✅ Duplicate claim prevention
- ✅ Claim creation and finalization
- ✅ Bridge lock operations (create, confirm, release)
- ✅ Statistics and reporting
- ✅ Record serialization

## Configuration

Set environment variables for production:

```bash
# Token contracts (after deployment)
export SOLANA_WRTC_MINT="..."
export BASE_WRTC_CONTRACT="0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6"

# Network configuration
export SOLANA_NETWORK="mainnet-beta"
export BASE_RPC_URL="https://mainnet.base.org"
export SOLANA_RPC_URL="https://api.mainnet-beta.solana.com"

# GitHub API token (for higher rate limits)
export GITHUB_TOKEN="..."
```

## Security Considerations

1. **Rate Limiting**: Implement IP-based rate limiting on claim endpoints
2. **Signature Verification**: Verify transaction signatures before finalizing claims
3. **Database Backups**: Regular backups of airdrop database
4. **Audit Trail**: All claims and bridge operations are logged
5. **Multi-sig**: Consider multi-sig for token mint authority

## Deployment Checklist

- [ ] Deploy wRTC SPL token on Solana (devnet → mainnet)
- [ ] Deploy wRTC ERC-20 on Base (testnet → mainnet)
- [ ] Configure token mint authorities
- [ ] Set up monitoring for airdrop claims
- [ ] Enable rate limiting on API endpoints
- [ ] Test with small allocation first
- [ ] Audit smart contracts
- [ ] Document claim process for users

## Future Enhancements

1. **Frontend Claim Page** (Track D)
   - GitHub OAuth integration
   - Wallet connection (Phantom, MetaMask)
   - Real-time eligibility checking
   - Claim status dashboard

2. **Advanced Anti-Sybil**
   - GitCoin Passport integration
   - Proof of Humanity
   - Social graph analysis

3. **Analytics Dashboard**
   - Real-time claim statistics
   - Geographic distribution
   - Tier breakdown visualization

## References

- [Issue #1149](https://github.com/Scottcjn/rustchain-bounties/issues/1149)
- [RustChain Node Architecture](node/README.md)
- [x402 Integration](node/x402_config.py)
- [Wallet Integration](wallet/rustchain_wallet_secure.py)

## Payout Information

**Wallet:** `RTC1d48d848a5aa5ecf2c5f01aa5fb64837daaf2f35` (split createkr-wallet)

---

*Implementation Date: March 9, 2026*  
*Version: 1.0.0*
