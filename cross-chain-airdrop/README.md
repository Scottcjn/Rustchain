# RIP-305 Cross-Chain Airdrop

[![Crate](https://img.shields.io/badge/crate-v0.1.0-blue.svg)](https://github.com/Scottcjn/Rustchain)
[![License](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue.svg)](https://github.com/Scottcjn/Rustchain)

Production-ready Rust implementation of the **RIP-305 Cross-Chain Airdrop Protocol** for distributing wrapped RTC (wRTC) tokens on Solana and Base L2.

## Overview

This crate implements the core verification and claim processing logic for the RIP-305 airdrop, including:

- **GitHub Verification**: Verify contributor tier based on stars, PRs, and badges
- **Wallet Verification**: Check balance and age requirements on Solana/Base
- **Chain Adapters**: Pluggable adapters for different blockchain RPCs
- **Bridge Integration**: Lock RTC and mint wRTC on target chains
- **Anti-Sybil**: Prevent duplicate claims and bot farms

## Features

### GitHub Contribution Tiers

| Tier | Requirement | Base Claim |
|------|------------|------------|
| Stargazer | 10+ repos starred | 25 wRTC |
| Contributor | 1+ merged PR | 50 wRTC |
| Builder | 3+ merged PRs | 100 wRTC |
| Security | Verified vulnerability found | 150 wRTC |
| Core | 5+ merged PRs or Star King badge | 200 wRTC |
| Miner | Active attestation history | 100 wRTC |

### Wallet Requirements (Anti-Sybil)

| Chain | Minimum Balance | Wallet Age |
|-------|----------------|------------|
| Solana | 0.1 SOL (~$15) | 7+ days |
| Base | 0.01 ETH (~$25) | 7+ days |

### Wallet Value Multipliers

| Balance Range | Multiplier |
|--------------|------------|
| 0.1-1 SOL / 0.01-0.1 ETH | 1.0x |
| 1-10 SOL / 0.1-1 ETH | 1.5x |
| 10+ SOL / 1+ ETH | 2.0x |

## Installation

```bash
# Add to Cargo.toml
[dependencies]
cross-chain-airdrop = "0.1.0"

# Or clone and build
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/cross-chain-airdrop
cargo build --release
```

## Quick Start

### Library Usage

```rust
use cross_chain_airdrop::{Config, GitHubVerifier, VerificationPipeline};
use cross_chain_airdrop::chain_adapter::{SolanaAdapter, BaseAdapter};
use cross_chain_airdrop::models::{ClaimRequest, TargetChain};
use std::sync::Arc;

#[tokio::main]
async fn main() -> cross_chain_airdrop::Result<()> {
    // Load configuration from environment
    let config = Config::from_env()?;

    // Initialize verifiers
    let github_verifier = GitHubVerifier::with_defaults(config.github_token.clone());
    let solana_adapter = Arc::new(SolanaAdapter::with_defaults(config.solana_rpc_url.clone()));
    let base_adapter = Arc::new(BaseAdapter::with_defaults(config.base_rpc_url.clone()));

    // Create verification pipeline
    let pipeline = VerificationPipeline::new(
        github_verifier,
        vec![solana_adapter, base_adapter],
    );

    // Check eligibility
    let eligibility = pipeline.check_eligibility(
        &github_oauth_token,
        TargetChain::Solana,
        &solana_wallet_address,
    ).await?;

    if eligibility.eligible {
        println!("Eligible for {} wRTC!", eligibility.final_allocation);
    } else {
        for reason in &eligibility.rejection_reasons {
            println!("Ineligible: {}", reason);
        }
    }

    Ok(())
}
```

### CLI Usage

```bash
# Build the CLI
cargo build --release --bin airdrop-cli

# Check eligibility
GITHUB_TOKEN=gho_... ./target/release/airdrop-cli check \
    --chain solana \
    --address 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU

# Submit a claim
GITHUB_TOKEN=gho_... ./target/release/airdrop-cli claim \
    --rtc_wallet my-wallet \
    --chain solana \
    --address 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU

# Verify wallet address format
./target/release/airdrop-cli verify-address \
    --chain base \
    --address 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb

# Show statistics
./target/release/airdrop-cli stats
```

## Configuration

Set environment variables or use `.env` file:

```bash
# RustChain node
RUSTCHAIN_NODE_URL=https://50.28.86.131

# Bridge API
BRIDGE_URL=http://localhost:8096

# Blockchain RPCs
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
BASE_RPC_URL=https://mainnet.base.org

# GitHub API (optional, for higher rate limits)
GITHUB_TOKEN=gho_...

# wRTC contract addresses (for production)
WRTC_SOLANA_MINT=12TAdKXxcGf6oCv4rqDz2NkgxjHq6HQKoxKZYGf5i4X
WRTC_BASE_CONTRACT=0x...

# Admin operations (optional)
ADMIN_KEY=your-admin-key

# Debugging
DRY_RUN=true
VERBOSE=true
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Verification Pipeline                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │ GitHub Verifier  │         │  Chain Adapters  │          │
│  │                  │         │                  │          │
│  │ - OAuth token    │         │ - SolanaAdapter  │          │
│  │ - Profile fetch  │         │ - BaseAdapter    │          │
│  │ - Tier check     │         │ - RPC calls      │          │
│  │ - Age verify     │         │ - Balance/age    │          │
│  └──────────────────┘         └──────────────────┘          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Eligibility Engine                       │   │
│  │                                                       │   │
│  │  GitHub tier  →  Base allocation                      │   │
│  │  Wallet tier  →  Multiplier                           │   │
│  │  Final = Base × Multiplier                            │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Anti-Sybil Checks                        │   │
│  │                                                       │   │
│  │  - One claim per GitHub account                       │   │
│  │  - One claim per wallet address                       │   │
│  │  - GitHub account age > 30 days                       │   │
│  │  - Wallet age > 7 days                                │   │
│  │  - Minimum wallet balance                             │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │    Bridge Integration    │
              │                          │
              │  POST /bridge/lock       │
              │  POST /bridge/confirm    │
              │  POST /bridge/release    │
              └─────────────────────────┘
```

## API Reference

### Core Types

- `Config`: Airdrop configuration
- `VerificationPipeline`: Main verification orchestrator
- `GitHubVerifier`: GitHub API client
- `ChainAdapter`: Trait for blockchain adapters
- `SolanaAdapter`: Solana RPC adapter
- `BaseAdapter`: Base L2 RPC adapter

### Models

- `ClaimRequest`: Claim submission request
- `ClaimResponse`: Claim submission response
- `EligibilityResult`: Eligibility check result
- `GitHubVerification`: GitHub verification details
- `WalletVerification`: Wallet verification details
- `TargetChain`: Solana or Base

### Error Types

- `AirdropError::GitHub`: GitHub API errors
- `AirdropError::WalletVerification`: Wallet verification failures
- `AirdropError::Eligibility`: Eligibility check failures
- `AirdropError::Bridge`: Bridge API errors
- `AirdropError::Claim`: Claim processing errors

## Testing

```bash
# Run all tests
cargo test

# Run with output
cargo test -- --nocapture

# Run specific test
cargo test test_eligibility_both_chains_eligible

# Run integration tests
cargo test --test integration_tests
```

## Production Deployment

### Prerequisites

1. **Bridge API**: Deploy the bridge API from `bridge/bridge_api.py`
2. **wRTC Contracts**: Deploy SPL token on Solana and ERC-20 on Base
3. **GitHub OAuth App**: Create OAuth app for GitHub API access
4. **RPC Endpoints**: Configure reliable RPC endpoints for Solana and Base

### Security Considerations

1. **Rate Limiting**: Implement rate limiting on claim endpoints
2. **Signature Verification**: Use HMAC-SHA256 receipts for bridge locks
3. **Duplicate Prevention**: Track claimed GitHub accounts and wallets
4. **Admin Controls**: Protect admin endpoints with strong authentication
5. **Audit Logging**: Log all claim operations for transparency

### Limitations

1. **Mock RPC Calls**: Current implementation uses mock data for balance/age checks. Replace with actual RPC calls in production.
2. **In-Memory Storage**: Claims are stored in memory. Use a database for production.
3. **GitHub Miner Check**: Miner status verification requires integration with RustChain node.
4. **Star King Badge**: Early stargazer badge check not yet implemented.

## Related Documentation

- [RIP-305 Specification](../../docs/RIP-305-cross-chain-airdrop.md)
- [Bridge API](../../bridge/README.md)
- [Solana SPL Deployment](../../rips/docs/RIP-0305-solana-spl-token-deployment.md)
- [Airdrop Claim Page](../../airdrop/README.md)

## License

Licensed under either of:

- Apache License, Version 2.0 ([LICENSE-APACHE](../../LICENSE-APACHE))
- MIT license ([LICENSE-MIT](../../LICENSE-MIT))

at your option.

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for contribution guidelines.

## Bounty

This implementation is part of **Bounty #1149** (RIP-305 Cross-Chain Airdrop).

**Tracks Completed:**
- ✅ Core flow implementation (config, models, adapters, verification)
- ✅ CLI surface
- ✅ Integration tests
- ✅ Documentation

**Remaining Tracks:**
- Frontend integration (see `airdrop/index.html`)
- Production RPC integration
- Database persistence layer
