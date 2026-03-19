# RustChain CLI — Wallet & Utilities

A command-line tool for interacting with the RustChain blockchain. Generate wallets, check balances, query miners, and monitor the network — all from the terminal.

## Features

- **Wallet Generation** — Create Ed25519 key pairs, derive RTC addresses
- **Address Validation** — Verify any RTC address (base58check + Ed25519 checksum)
- **Balance Queries** — Check RTC wallet balance from any address
- **Miner Monitoring** — List active miners, query individual miner stats
- **Network Stats** — Epoch info, total supply, active miner count
- **Health Checks** — Monitor RustChain node health and uptime
- **Epoch Rewards** — Estimate epoch rewards based on stake and antiquity

## Installation

### From Source (requires Rust 1.70+)

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/tools/rustchain-cli
cargo build --release
./target/release/rustchain --help
```

### Using `cargo install`

```bash
cargo install --path tools/rustchain-cli
rustchain --help
```

## Quick Start

```bash
# Set the RPC endpoint (optional — defaults to https://explorer.rustchain.org)
export RUSTCHAIN_RPC_URL=https://explorer.rustchain.org

# Generate a new wallet
rustchain wallet generate

# Check balance
rustchain balance --wallet C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg

# List active miners
rustchain miners list --limit 10

# Network stats
rustchain network stats

# Health check
rustchain health

# Epoch info
rustchain epoch --detailed
```

## Command Reference

### Wallet

```bash
# Generate a new random wallet
rustchain wallet generate

# Derive address from a base58 seed
rustchain wallet from-seed <seed>

# Derive address from a hex private key
rustchain wallet from-hex <private_key>

# Convert Ed25519 public key to RTC address
rustchain wallet pubkey-to-address <pubkey>
```

### Address

```bash
# Validate an RTC address
rustchain address <address>
```

### Balance

```bash
rustchain balance --wallet <address>
```

### Network

```bash
# Show network overview
rustchain network

# Detailed stats
rustchain network stats

# List all nodes
rustchain network nodes
```

### Miners

```bash
# List active miners (default: 20)
rustchain miners list --limit 50

# Details for a specific miner
rustchain miners info <miner_id>

# Miner count
rustchain miners count
```

### Epoch

```bash
# Current epoch summary
rustchain epoch

# Detailed epoch info
rustchain epoch --detailed
```

### Health

```bash
rustchain health
```

### Rewards

```bash
# Estimate rewards for a wallet
rustchain rewards --wallet <address>

# With specific stake amount
rustchain rewards --wallet <address> --stake 1000
```

## Address Format

RTC addresses are derived from Ed25519 public keys using base58check encoding:

```
[1 byte version] + [32 bytes Ed25519 pubkey] + [4 bytes checksum]  →  base58
```

- **Version byte**: `0x00` (mainnet)
- **Checksum**: `SHA256(SHA256(version || pubkey))[0:4]`
- **Encoding**: Base58 (no ambiguous characters: 0, O, I, l)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUSTCHAIN_RPC_URL` | `https://explorer.rustchain.org` | RustChain API endpoint |

## Building

```bash
# Debug build
cargo build

# Release build
cargo build --release

# Run tests
cargo test

# Format code
cargo fmt

# Lint
cargo clippy
```

## Architecture

```
src/
├── main.rs       # CLI entry point, argument parsing, command dispatch
├── lib.rs        # Library exports
├── address.rs    # Ed25519 RTC address generation & validation
├── api.rs        # HTTP client for RustChain REST API
└── wallet.rs     # Wallet management, key derivation, signing
```

## Security Notes

- Secret keys are never written to wallet files (only the address is stored)
- Secret key files are saved with `0o600` (owner-read-only) permissions on Unix
- All API communication uses HTTPS by default
- Ed25519 signatures are used for all transaction signing

## License

MIT OR Apache-2.0

---

Built with 🦀 for RustChain — Proof-of-Antiquity blockchain
