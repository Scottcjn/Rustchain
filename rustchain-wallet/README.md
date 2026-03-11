# RustChain Wallet

[![Crates.io](https://img.shields.io/crates/v/rustchain-wallet.svg)](https://crates.io/crates/rustchain-wallet)
[![Documentation](https://docs.rs/rustchain-wallet/badge.svg)](https://docs.rs/rustchain-wallet)
[![License](https://img.shields.io/crates/l/rustchain-wallet.svg)](LICENSE)
[![Rust](https://img.shields.io/badge/rust-1.70+-blue.svg)](https://rust-lang.org)
[![Rust CI](https://github.com/Scottcjn/Rustchain/actions/workflows/rust-ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/rust-ci.yml)
[![Build Status](https://github.com/Scottcjn/Rustchain/workflows/Rust/badge.svg)](https://github.com/Scottcjn/Rustchain/actions)

A robust, production-ready native Rust wallet for RustChain with comprehensive CLI tools, secure key management, and transaction signing capabilities.

## Features

- 🔐 **Secure Key Management**: Ed25519 key generation with encrypted storage
- 📝 **Transaction Signing**: Create and sign transactions offline
- 💰 **Balance & Transfers**: Query balances and send tokens via CLI
- 🛡️ **Security First**: Zeroize sensitive data, AES-256-GCM encryption
- 🚀 **CLI Interface**: Full-featured command-line wallet tool
- 📦 **Library API**: Use as a dependency in your Rust projects
- 🌐 **Multi-Network**: Support for mainnet, testnet, and devnet

## Quick Start

### Installation

#### From Source

```bash
# Clone the repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/rustchain-wallet

# Build in release mode
cargo build --release

# Install the CLI tool
cargo install --path .
```

#### From Crates.io (coming soon)

```bash
cargo install rustchain-wallet
```

#### Pre-built Binaries

Download pre-built binaries from the [Releases page](https://github.com/Scottcjn/Rustchain/releases).

### Verify Installation

```bash
rtc-wallet --version
```

## CLI Usage

### Create a New Wallet

```bash
rtc-wallet create --name my-wallet
```

You'll be prompted to enter and confirm a password. This password encrypts your private key.

### List Wallets

```bash
rtc-wallet list
```

### View Wallet Details

```bash
rtc-wallet show --name my-wallet
```

### Check Balance

```bash
rtc-wallet balance --wallet <address>
```

### Transfer Tokens

```bash
rtc-wallet transfer \
    --from my-wallet \
    --to <recipient-address> \
    --amount 1000 \
    --memo "Payment for services"
```

### Sign a Message

```bash
rtc-wallet sign --wallet my-wallet --message "Hello, RustChain!"
```

### Verify a Signature

```bash
rtc-wallet verify \
    --pubkey <public-key> \
    --message "Hello, RustChain!" \
    --signature <signature>
```

### Network Information

```bash
rtc-wallet network
```

### Use Testnet

```bash
rtc-wallet --network testnet create --name test-wallet
```

### Full CLI Help

```bash
rtc-wallet --help
rtc-wallet <command> --help
```

## Library Usage

Add to your `Cargo.toml`:

```toml
[dependencies]
rustchain-wallet = "0.1"
```

### Basic Example

```rust
use rustchain_wallet::{Wallet, KeyPair, Network};

// Generate a new wallet
let wallet = Wallet::generate();
println!("Address: {}", wallet.address());

// Create wallet on testnet
let wallet = Wallet::with_network(KeyPair::generate(), Network::Testnet);

// Sign a message
let message = b"Hello, RustChain!";
let signature = wallet.sign(message)?;
println!("Signature: {}", hex::encode(&signature));

// Verify a signature
let valid = wallet.verify(message, &signature)?;
assert!(valid);
```

### Transaction Example

```rust
use rustchain_wallet::{Transaction, TransactionBuilder, KeyPair};

// Create a transaction
let keypair = KeyPair::generate();
let mut tx = TransactionBuilder::new()
    .from(keypair.public_key_base58())
    .to("recipient_address".to_string())
    .amount(1000)
    .fee(100)
    .nonce(1)
    .memo("Payment".to_string())
    .build()?;

// Sign the transaction
tx.sign(&keypair)?;

// Serialize for broadcasting
let json = tx.to_json()?;
println!("{}", json);
```

### Encrypted Storage

```rust
use rustchain_wallet::{WalletStorage, KeyPair};

// Create storage at default location
let storage = WalletStorage::default()?;

// Save a wallet
let keypair = KeyPair::generate();
storage.save("my-wallet", &keypair, "secure-password")?;

// Load a wallet
let keypair = storage.load("my-wallet", "secure-password")?;
println!("Address: {}", keypair.public_key_base58());

// List all wallets
let wallets = storage.list()?;
for name in wallets {
    println!("Found wallet: {}", name);
}
```

### RPC Client

```rust
use rustchain_wallet::RustChainClient;

let client = RustChainClient::new("https://rpc.rustchain.org".to_string());

// Get balance
let balance = client.get_balance("address").await?;
println!("Balance: {} RTC", balance.balance);

// Get network info
let info = client.get_network_info().await?;
println!("Block height: {}", info.block_height);

// Submit transaction
let response = client.submit_transaction(&tx).await?;
println!("TX Hash: {}", response.tx_hash);
```

## Security Considerations

### Private Key Storage

- Private keys are encrypted with AES-256-GCM using PBKDF2 key derivation
- 100,000 iterations for password-based key derivation
- Random salt and nonce for each encryption
- File permissions set to 600 (Unix only)

### Memory Safety

- Sensitive data is zeroized when dropped
- Uses `Secret` and `Zeroize` for secure memory handling
- Private keys never logged or printed

### Best Practices

1. **Use strong passwords**: Minimum 12 characters with mixed case, numbers, and symbols
2. **Backup your wallets**: Export and securely store private keys offline
3. **Never share private keys**: Keep them secret, even the encrypted files
4. **Use hardware wallets**: For large amounts, consider hardware wallet integration
5. **Verify addresses**: Always double-check recipient addresses
6. **Test first**: Use testnet for testing before mainnet transactions

## Project Structure

```
rustchain-wallet/
├── Cargo.toml              # Package manifest
├── README.md               # This file
├── src/
│   ├── lib.rs              # Library root
│   ├── bin/
│   │   └── rtc_wallet.rs   # CLI binary
│   ├── error.rs            # Error types
│   ├── keys.rs             # Key generation & management
│   ├── storage.rs          # Encrypted wallet storage
│   ├── transaction.rs      # Transaction handling
│   └── client.rs           # RPC client
├── examples/               # Usage examples
└── tests/                  # Integration tests
```

## API Reference

### Core Types

- `Wallet`: Main wallet structure with network configuration
- `KeyPair`: Ed25519 keypair for signing
- `Network`: Network enum (Mainnet, Testnet, Devnet)
- `Transaction`: Transaction structure
- `WalletStorage`: Encrypted storage manager
- `RustChainClient`: RPC client for network interaction

### Error Handling

All operations return `Result<T, WalletError>` with specific error types:

- `WalletError::Crypto`: Cryptographic operations failed
- `WalletError::InvalidKey`: Key format/length error
- `WalletError::InvalidSignature`: Signature verification failed
- `WalletError::Storage`: Storage I/O error
- `WalletError::Network`: Network/RPC error
- `WalletError::Transaction`: Transaction error

## Examples

See the `examples/` directory for complete usage examples:

- `basic_wallet.rs`: Basic wallet creation and signing
- `transaction_flow.rs`: Complete transaction flow
- `storage_example.rs`: Using encrypted storage
- `rpc_client.rs`: RPC client usage

## Testing

```bash
# Run all tests
cargo test

# Run with output
cargo test -- --nocapture

# Run specific test
cargo test test_wallet_generation

# Run with coverage (requires cargo-tarpaulin)
cargo tarpaulin --out Html
```

## Building for Production

```bash
# Optimized release build
cargo build --release

# Strip symbols for smaller binary
strip target/release/rtc-wallet

# Verify binary
file target/release/rtc-wallet
```

## Troubleshooting

### Build Errors

**Error: rustc version too old**
```bash
rustup update
rustup default stable
```

**Error: missing dependencies**
```bash
# Ubuntu/Debian
sudo apt-get install build-essential pkg-config libssl-dev

# macOS
xcode-select --install

# Arch Linux
sudo pacman -S base-devel openssl
```

### Runtime Issues

**Wallet not found**
```bash
rtc-wallet list  # Check available wallets
rtc-wallet --wallet-dir /path/to/wallets list
```

**RPC connection failed**
```bash
# Check network connectivity
curl https://rpc.rustchain.org

# Use alternative RPC endpoint
rtc-wallet --network testnet balance --wallet <address> --rpc https://backup-rpc.rustchain.org
```

## Contributing

Contributions are welcome! Please see the main repository's [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone and setup
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/rustchain-wallet

# Run tests
cargo test

# Run CLI
cargo run -- --help
```

## License

Licensed under either of:

- Apache License, Version 2.0 ([LICENSE-APACHE](../LICENSE-APACHE))
- MIT license ([LICENSE-MIT](../LICENSE-MIT))

at your option.

## CI/CD

This project uses GitHub Actions for continuous integration and deployment. The [Rust CI workflow](.github/workflows/rust-ci.yml) runs on every push and pull request to `main` and `develop` branches.

### Workflow Jobs

| Job | Description |
|-----|-------------|
| **fmt** | Checks code formatting with `cargo fmt` |
| **clippy** | Runs Clippy linter with all features |
| **test** | Runs unit and integration tests on Ubuntu, macOS, and Windows |
| **build** | Builds release binaries for all platforms |
| **docs** | Generates and archives Rust documentation |
| **security-audit** | Scans dependencies for known vulnerabilities |

### Caching

The workflow uses [`Swatinem/rust-cache@v2`](https://github.com/Swatinem/rust-cache) to cache:
- Cargo registry and git dependencies
- Compiled artifacts from previous runs
- Build outputs to speed up subsequent runs

Cache is automatically restored on cache hits and saved on successful builds.

### Manual Triggers

You can manually trigger the workflow from the Actions tab with options to:
- Specify a particular package to build
- Disable caching for clean builds

### Badges

Add the CI badge to your README:

```markdown
[![Rust CI](https://github.com/Scottcjn/Rustchain/actions/workflows/rust-ci.yml/badge.svg)](https://github.com/Scottcjn/Rustchain/actions/workflows/rust-ci.yml)
```

---

## Acknowledgments

- [ed25519-dalek](https://github.com/dalek-cryptography/ed25519-dalek) for Ed25519 implementation
- [clap](https://github.com/clap-rs/clap) for CLI framework
- [RustChain](https://rustchain.org) team and contributors

## Support

- Documentation: https://docs.rs/rustchain-wallet
- Issues: https://github.com/Scottcjn/Rustchain/issues
- Discord: https://discord.gg/rustchain

---

**Bounty #733**: Native Rust Wallet Implementation
