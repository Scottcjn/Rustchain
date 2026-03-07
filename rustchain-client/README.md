# rustchain-client

HTTP client library for RustChain blockchain API.

## Overview

`rustchain-client` provides a convenient Rust interface to the RustChain blockchain node API. Interact with health checks, epoch data, active miners, wallet balances, and governance proposals.

## Features

- Health check endpoints
- Epoch information retrieval
- Active miner listing
- Wallet balance queries
- Governance proposal browsing
- Support for custom node URLs

## Installation

Add this to your `Cargo.toml`:

```toml
[dependencies]
rustchain-client = "0.1"
```

Or use the latest from GitHub:

```toml
[dependencies]
rustchain-client = { git = "https://github.com/sososonia-cyber/rustchain-client" }
```

## Usage

```rust
use rustchain_client::RustChainClient;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = RustChainClient::new();
    
    // Check network health
    let health = client.health().await?;
    println!("Network status: {}", health.status);
    
    // Get current epoch
    let epoch = client.epoch().await?;
    println!("Current epoch: {}", epoch.epoch);
    
    // List active miners
    let miners = client.miners().await?;
    println!("Active miners: {}", miners.miners.len());
    
    // Check wallet balance
    let balance = client.balance("your_wallet_address").await?;
    println!("Balance: {} RTC", balance.balance);
    
    Ok(())
}
```

## CLI Usage

This crate also provides a command-line interface:

```bash
# Install CLI
cargo install rustchain-client

# Check health
rustchain-client health

# Get current epoch
rustchain-client epoch

# List miners
rustchain-client miners

# Check balance
rustchain-client balance <WALLET_ADDRESS>
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/health` | Network health status |
| `/epoch` | Current epoch information |
| `/api/miners` | List of active miners |
| `/wallet/balance` | Wallet balance |
| `/governance/proposals` | List governance proposals |

## License

MIT
