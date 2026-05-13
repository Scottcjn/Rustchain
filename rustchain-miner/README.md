# RustChain Miner (Rust)

Production-ready Rust implementation of the RustChain miner with RIP-PoA (Proof of Antiquity) hardware attestation.

## Features

- **Hardware Attestation**: Complete challenge/response protocol with entropy collection
- **RIP-PoA Support**: Hardware fingerprint attestation for anti-emulation
- **Cross-Platform**: Linux, macOS, Windows support
- **Config/Env Support**: Flexible configuration via CLI args, environment variables, or `.env` file
- **Health Checks**: Node health probing and connectivity validation
- **Dry-Run Mode**: Preflight checks without network state modification
- **Logging**: Structured logging with configurable verbosity

## Requirements

- Rust 1.70 or later
- OpenSSL or rustls for HTTPS support
- Network access to RustChain node

## Installation

### From Source

```bash
# Clone the repository
cd rustchain-miner

# Build in release mode
cargo build --release

# The binary will be at:
# ./target/release/rustchain-miner
```

### Quick Install

```bash
# Build and install to ~/.cargo/bin
cargo install --path .
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RUSTCHAIN_NODE_URL` | Node URL (HTTPS) | `https://50.28.86.131` |
| `RUSTCHAIN_PROXY_URL` | HTTP proxy for legacy systems | (none) |
| `RUSTCHAIN_WALLET` | Wallet address | (auto-generated) |
| `RUSTCHAIN_MINER_ID` | Custom miner ID | (auto-generated) |
| `RUSTCHAIN_BLOCK_TIME` | Block time in seconds | `600` |
| `RUSTCHAIN_ATTESTATION_TTL` | Attestation TTL in seconds | `580` |
| `RUSTCHAIN_DRY_RUN` | Enable dry-run mode | `false` |
| `RUSTCHAIN_VERBOSE` | Enable verbose logging | `false` |
| `RUSTCHAIN_DEV_INSECURE_TLS` | Disable TLS cert validation (dev only) | `false` |

### .env File

Create a `.env` file in the project root:

```bash
RUSTCHAIN_NODE_URL=https://50.28.86.131
RUSTCHAIN_WALLET=my_wallet_RTC
RUSTCHAIN_VERBOSE=true
```

### CLI Arguments

```bash
rustchain-miner --help
```

| Argument | Short | Long | Env | Description |
|----------|-------|------|-----|-------------|
| `-w` | `--wallet` | `RUSTCHAIN_WALLET` | Wallet address |
| `-m` | `--miner-id` | `RUSTCHAIN_MINER_ID` | Custom miner ID |
| `-n` | `--node` | `RUSTCHAIN_NODE_URL` | Node URL |
| `-p` | `--proxy` | `RUSTCHAIN_PROXY_URL` | HTTP proxy |
| | `--dry-run` | `RUSTCHAIN_DRY_RUN` | Preflight checks only |
| `-v` | `--verbose` | `RUSTCHAIN_VERBOSE` | Verbose logging |
| | `--block-time` | `RUSTCHAIN_BLOCK_TIME` | Block time (seconds) |
| | `--attestation-ttl` | `RUSTCHAIN_ATTESTATION_TTL` | Attestation TTL |

## Usage

### Basic Mining

```bash
# Run with auto-generated wallet
./target/release/rustchain-miner

# Run with specific wallet
./target/release/rustchain-miner --wallet my_wallet_RTC
```

### Dry-Run Mode

Test your setup without attesting or mining. `--dry-run` runs the miner's
preflight checks, prints the detected hardware fingerprint information, and then
exits without submitting attestations or starting actual mining.

```bash
./target/release/rustchain-miner --dry-run --verbose
```

### Verbose Logging

```bash
./target/release/rustchain-miner --verbose
```

### With Custom Node

```bash
./target/release/rustchain-miner --node https://your-node.com
```

### With Proxy (Legacy Systems)

```bash
./target/release/rustchain-miner --proxy http://192.168.0.160:8089
```

## Architecture

### Modules

- **`config`**: Configuration management with environment variable support
- **`hardware`**: Hardware information collection (CPU, memory, serial, MACs)
- **`transport`**: Node communication with HTTPS/proxy fallback
- **`attestation`**: Challenge/response protocol and entropy collection
- **`miner`**: Main mining loop with enrollment and health checks

### Attestation Flow

1. **Challenge**: Request nonce from node (`/attest/challenge`)
2. **Entropy Collection**: Measure CPU timing variance
3. **Commitment**: Build hash commitment with nonce + wallet + entropy
4. **Submit**: Send attestation report (`/attest/submit`)
5. **Enroll**: Join epoch with attested hardware (`/epoch/enroll`)
6. **Mine**: Wait for block time, repeat

### Hardware Fingerprint

The miner collects hardware information for RIP-PoA:

- CPU brand and architecture
- Core count
- Memory size
- Hardware serial (when available)
- MAC addresses
- Hostname

This data is used to:
- Generate unique miner ID
- Detect VMs/emulators (reduced rewards)
- Calculate Proof of Antiquity weight

## Comparison with Python Miner

| Feature | Python Miner | Rust Miner |
|---------|-------------|------------|
| Hardware Attestation | ✓ | ✓ |
| Challenge/Response | ✓ | ✓ |
| Epoch Enrollment | ✓ | ✓ |
| Entropy Collection | ✓ | ✓ |
| Config/Env Support | Partial | ✓ Full |
| Dry-Run Mode | ✓ | ✓ |
| Verbose Logging | Basic | ✓ Structured |
| Cross-Platform | ✓ | ✓ |
| Binary Distribution | PyInstaller | ✓ Native |
| Memory Safety | No | ✓ Yes |
| Performance | Good | ✓ Excellent |

## Building for Production

### Linux

```bash
cargo build --release
strip target/release/rustchain-miner
```

### macOS

```bash
# Universal binary (Intel + Apple Silicon)
rustup target add x86_64-apple-darwin
rustup target add aarch64-apple-darwin
cargo build --release --target x86_64-apple-darwin
cargo build --release --target aarch64-apple-darwin
lipo -create \
  target/x86_64-apple-darwin/release/rustchain-miner \
  target/aarch64-apple-darwin/release/rustchain-miner \
  -output target/release/rustchain-miner-universal
```

### Windows

```bash
cargo build --release
# Binary at: target\release\rustchain-miner.exe
```

## Troubleshooting

### TLS/SSL Errors

TLS certificate validation is **enabled by default**. If you encounter TLS errors
on legacy systems or local test servers with self-signed certificates, you have
two options:

1. **Use an HTTP proxy** (recommended for legacy systems):
   ```bash
   ./target/release/rustchain-miner --proxy http://192.168.0.160:8089
   ```

2. **Disable TLS validation** (development only — **INSECURE**):
   ```bash
   export RUSTCHAIN_DEV_INSECURE_TLS=1
   ./target/release/rustchain-miner
   ```
   **WARNING**: This disables TLS certificate validation and exposes the miner to
   **man-in-the-middle attacks**. Never use this in production.

### Attestation Failed

Ensure:
- Network connectivity to node
- System time is synchronized
- Hardware serial is accessible (some VMs don't provide this)

### Reduced Rewards

If you receive reduced rewards, your hardware fingerprint may indicate:
- Running in a VM or container
- Missing hardware serial
- Emulated hardware

Run on real hardware for full rewards.

## Development

### Run Tests

```bash
cargo test
```

### Run with Debug Logging

```bash
RUST_LOG=debug cargo run -- --dry-run
```

### Check Code

```bash
cargo clippy
cargo fmt --check
```

## License

MIT OR Apache-2.0

## Contributing

See the main [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## Support

- Documentation: [RustChain Docs](https://rustchain.org/docs)
- Issues: [GitHub Issues](https://github.com/Scottcjn/Rustchain/issues)
- Discord: [RustChain Discord](https://discord.gg/rustchain)
