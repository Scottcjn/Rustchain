# rtc-types

Shared types for RustChain API responses.

## Description

This crate provides Serde-serializable types for interacting with the RustChain blockchain API, including:
- Node information and health checks
- Wallet operations (balance, transfer, nonce)
- Proof-of-Antiquity epoch data
- Badge/NFT types

## Usage

```rust
use rtc_types::{NodeInfo, Balance, Epoch};
use serde_json::json;

fn main() {
    // Deserialize node info
    let node_json = json!({
        "version": "2.2.1",
        "chain_id": "rustchain-mainnet",
        "current_epoch": 1337,
        "peers": 42,
        "uptimeSeconds": 86400
    });
    
    let node_info: NodeInfo = serde_json::from_value(node_json).unwrap();
    println!("Node version: {}", node_info.version);
}
```

## Modules

- `node` - Node information, blocks, transactions, network stats
- `wallet` - Wallet operations, balances, transfers
- `epoch` - Proof-of-Antiquity epoch data, attestations
- `badges` - Badge and NFT types

## License

MIT
