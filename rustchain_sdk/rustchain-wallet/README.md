# RustChain Wallet

[![License](https://img.shields.io/crates/l/rustchain-wallet.svg)](LICENSE)
[![Rust](https://img.shields.io/badge/rust-1.70+-blue.svg)](https://rust-lang.org)

A native Rust CLI wallet for RustChain with Ed25519 key management, RTC address derivation, and transaction signing.

## Features

- **Ed25519 Keypair Generation**: Secure key generation via `ed25519-dalek`
- **RTC Address Derivation**: `RTC` + `sha256(pubkey)[:40]` format
- **Encrypted Storage**: AES-256-GCM with PBKDF2 key derivation
- **Transaction Signing**: Ed25519 signatures on canonical JSON payloads
- **Balance Queries**: Query balance from `rustchain.org` API
- **Transaction Submission**: Sign and submit transfers via REST API
- **CLI Interface**: Full-featured `clap`-based command-line tool
- **Replay Protection**: Persistent nonce tracking

## Quick Start

### Build from Source

```bash
cd rustchain-wallet
cargo build --release
cargo install --path .
```

### Verify Installation

```bash
rtc-wallet --version
```

## CLI Commands

### Create a New Wallet

```bash
rtc-wallet create --name my-wallet
```

Generates an Ed25519 keypair, derives the RTC address, and saves the encrypted keystore.

### Import from Private Key

```bash
rtc-wallet import --name imported-wallet --key <hex-private-key>
```

Accepts hex or Base58 encoded Ed25519 secret keys.

### Check Balance

```bash
# By wallet name
rtc-wallet balance --wallet my-wallet

# By RTC address directly
rtc-wallet balance --wallet RTCabc123...
```

Queries `https://rustchain.org/wallet/balance?miner_id=<address>`.

### Send RTC

```bash
rtc-wallet send \
    --from my-wallet \
    --to RTCrecipientaddress... \
    --amount 1000 \
    --memo "Payment"
```

Signs the transaction with Ed25519 and submits to `https://rustchain.org/wallet/transfer/signed`.

### Receive (Show Address)

```bash
rtc-wallet receive --name my-wallet
```

Displays your RTC address for receiving funds.

### List Wallets

```bash
rtc-wallet list
```

### Show Wallet Details

```bash
rtc-wallet show --name my-wallet
```

### Export Private Key

```bash
rtc-wallet export --name my-wallet
```

### Sign / Verify Messages

```bash
rtc-wallet sign --wallet my-wallet --message "Hello, RustChain!"
rtc-wallet verify --pubkey <hex> --message "Hello" --signature <hex>
```

### Network Information

```bash
rtc-wallet network
```

### Use Testnet

```bash
rtc-wallet --network testnet balance --wallet <address>
```

## Address Format

RTC addresses are derived as:

```
address = "RTC" + hex(sha256(ed25519_public_key_bytes))[:40]
```

This matches the address format used by the Python `rustchain_crypto` module.

## Architecture

```
rustchain-wallet/
├── Cargo.toml
├── README.md
├── src/
│   ├── lib.rs              # Library root, Wallet struct
│   ├── bin/
│   │   └── rtc_wallet.rs   # CLI binary (clap)
│   ├── error.rs             # Error types (thiserror)
│   ├── keys.rs              # Ed25519 keypair, RTC address derivation
│   ├── storage.rs           # AES-256-GCM encrypted wallet files
│   ├── transaction.rs       # Transaction struct, signing, builder
│   ├── client.rs            # rustchain.org REST API client
│   └── nonce_store.rs       # Replay protection
├── examples/
└── tests/
```

## Security

- Private keys encrypted with AES-256-GCM (PBKDF2, 100k iterations)
- Random salt and nonce per encryption
- File permissions set to 600 on Unix
- Zeroize-capable key handling
- Ed25519 signatures on canonical JSON for tamper-proof transactions

## Dependencies

| Crate | Purpose |
|-------|---------|
| `ed25519-dalek` | Ed25519 signatures |
| `sha2` | SHA-256 for address derivation |
| `clap` | CLI argument parsing |
| `reqwest` | HTTP client for API calls |
| `serde_json` | JSON serialization |
| `aes-gcm` | Wallet encryption |
| `tokio` | Async runtime |

## Testing

```bash
cargo test
cargo test -- --nocapture
```

## License

Licensed under MIT OR Apache-2.0.

---

Bounty #733: Native Rust Wallet Implementation
