# RustChain Native Rust Miner

A native Rust implementation of the RustChain Proof-of-Antiquity miner.

## Bounty #734 Phase-1

This implementation covers **Phase-1** of bounty #734:

- ✅ Native Rust CLI miner
- ✅ Hardware detection (CPU, RAM, platform, serial)
- ✅ Attestation loop with epoch enrollment
- ✅ Balance check command
- ✅ Dry-run mode
- ✅ Show-payload mode
- ✅ Test-only mode
- ✅ Node endpoint integration
- ✅ Clean documentation
- ✅ Unit tests

**Phase-2** (six RIP-PoA fingerprint checks) can be added incrementally in `src/hardware.rs`.

## Features

### Hardware Detection
- Auto-detects CPU family and architecture
- Supports PowerPC (G3/G4/G5), x86, x86_64, ARM, ARM64
- Detects CPU model, cores, RAM, platform, OS version
- Attempts to read hardware serial number

### Attestation
- Automatic epoch enrollment
- Configurable attestation interval
- Health check before each attestation
- Graceful error handling and retry

### CLI Modes
- **Normal mode**: Full mining with attestation loop
- **Dry-run**: Simulate without making API calls
- **Show-payload**: Print request payloads without sending
- **Test-only**: Local validation only

## Installation

### Prerequisites
- Rust 1.70+ (install via [rustup](https://rustup.rs))
- OpenSSL development libraries (for TLS)

### Build from Source

```bash
cd miners/rust
cargo build --release
```

The binary will be at `target/release/rustchain-miner`.

### Quick Install

```bash
# Clone and build
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/rust
cargo install --path .
```

## Usage

### Start Mining

```bash
# Basic usage with wallet
rustchain-miner --wallet my-miner-wallet

# With custom node
rustchain-miner --wallet my-wallet --node https://rustchain.org

# With custom attestation interval (in seconds)
rustchain-miner --wallet my-wallet --interval 600

# Verbose logging
rustchain-miner --wallet my-wallet --verbose
```

### Environment Variables

```bash
export RUSTCHAIN_WALLET=my-miner-wallet
export RUSTCHAIN_NODE=https://rustchain.org
rustchain-miner
```

### Dry-Run Mode

Test the miner without making actual API calls:

```bash
rustchain-miner mine --dry-run --wallet test-wallet
```

### Show Payload Mode

Print the enrollment request payload without sending:

```bash
rustchain-miner mine --show-payload --wallet test-wallet
```

### Test-Only Mode

Validate locally without network calls:

```bash
rustchain-miner mine --test-only --wallet test-wallet
```

### Single Attestation

Run one attestation cycle and exit:

```bash
rustchain-miner mine --once --wallet my-wallet
```

### Check Balance

```bash
# Check your wallet balance
rustchain-miner balance --wallet my-wallet

# Check another miner's balance
rustchain-miner balance --miner-id other-miner
```

### View Hardware Info

```bash
rustchain-miner hardware
```

Example output:
```
╔═══════════════════════════════════════════════════════════╗
║              Hardware Information                         ║
╠═══════════════════════════════════════════════════════════╣
║ CPU Model:  AMD Ryzen 9 7950X 16-Core Processor           ║
║ Family:     x86_64                                        ║
║ Arch:       ryzen                                         ║
║ Cores:      16                                            ║
║ RAM:        64 GB                                         ║
║ Platform:   linux                                         ║
║ OS:         Linux 6.5.0-15-generic                        ║
║ Serial:     N/A                                           ║
╠═══════════════════════════════════════════════════════════╣
║ Generated Miner ID:                                      ║
║ RTC_a1b2c3d4e5f67890                                     ║
╚═══════════════════════════════════════════════════════════╝
```

### List Active Miners

```bash
rustchain-miner miners
```

### Check Node Health

```bash
rustchain-miner health
```

## API Endpoints

The miner integrates with these RustChain node endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Check node health |
| `/epoch` | GET | Get current epoch info |
| `/epoch/enroll` | POST | Enroll in current epoch |
| `/wallet/balance` | GET | Get wallet balance |
| `/api/miners` | GET | List active miners |

## Configuration

### MinerConfig Structure

```rust
pub struct MinerConfig {
    pub node_url: String,                    // Node URL (default: https://rustchain.org)
    pub wallet: String,                      // Wallet identifier
    pub attestation_interval_secs: u64,      // Attestation interval (default: 300)
    pub verbose: bool,                       // Enable verbose logging
    pub dry_run: bool,                       // Dry-run mode
    pub show_payload: bool,                  // Show payload mode
    pub test_only: bool,                     // Test-only mode
    pub insecure_skip_verify: bool,          // Skip TLS verification
}
```

### HardwareInfo Structure

```rust
pub struct HardwareInfo {
    pub family: HardwareFamily,      // CPU family
    pub arch: HardwareArch,          // CPU architecture
    pub model: String,               // CPU model name
    pub cores: usize,                // Number of cores
    pub total_ram_bytes: u64,        // Total RAM in bytes
    pub serial: Option<String>,      // Hardware serial
    pub platform: String,            // Platform (linux/macos/windows)
    pub os_version: String,          // OS version
}
```

## Architecture

### Module Structure

```
src/
├── main.rs          # CLI entry point and commands
├── types.rs         # Core data types and config
├── hardware.rs      # Hardware detection (extend for phase-2)
├── api.rs           # Node API client
└── attestation.rs   # Attestation loop manager
```

### Phase-2 Extension Points

The code is designed for incremental Phase-2 implementation:

1. **`src/hardware.rs::validate_hardware()`** - Add 6 RIP-PoA checks:
   - Clock-Skew & Oscillator Drift
   - Cache Timing Fingerprint
   - SIMD Unit Identity
   - Thermal Drift Entropy
   - Instruction Path Jitter
   - Anti-Emulation Checks

2. **`src/types.rs::HardwareInfo`** - Add fingerprint fields

3. **`src/api.rs::enroll_epoch()`** - Include fingerprint data in enrollment

## Testing

```bash
# Run all tests
cargo test

# Run tests with output
cargo test -- --nocapture

# Run specific test
cargo test test_detect_hardware
```

## Development

### Build Debug Version

```bash
cargo build
```

### Build Release Version

```bash
cargo build --release
```

### Check Code

```bash
cargo clippy
cargo fmt --check
```

### Run with Logging

```bash
RUST_LOG=debug cargo run -- --wallet test --verbose
```

## Troubleshooting

### TLS Certificate Errors

If the node uses a self-signed certificate:

```bash
rustchain-miner --wallet my-wallet --insecure-skip-verify
```

### Hardware Detection Issues

View detected hardware:

```bash
rustchain-miner hardware --verbose
```

### Connection Errors

Check node health first:

```bash
rustchain-miner health --node https://rustchain.org
```

## License

MIT License - See [LICENSE](../../LICENSE) for details.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

## Related

- [RustChain Main Repository](https://github.com/Scottcjn/Rustchain)
- [Bounty #734](https://github.com/Scottcjn/Rustchain/issues/734)
- [Python Miner Reference](../linux/rustchain_linux_miner.py)
