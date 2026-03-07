# RustChain Rust Miner Components

Native Rust miner implementation for RustChain's Proof-of-Antiquity consensus mechanism.

## Overview

This crate provides:
- **Miner Client**: High-level API for interacting with RustChain node endpoints
- **Hardware Fingerprinting**: 6-point attestation system for anti-emulation
- **CLI Miner**: Ready-to-use command-line miner binary
- **Deep Entropy Verification**: Statistical hardware verification

## Quick Start

### Installation

```bash
cd rips
cargo build --release
```

The miner binary will be available at `target/release/rustchain-miner`.

### Basic Usage

```bash
# Mine with a specific wallet
./target/release/rustchain-miner --wallet my-vintage-mac

# Specify node URL (default: https://rustchain.org)
./target/release/rustchain-miner --wallet my-wallet --node https://rustchain.org

# Dry run to validate configuration
./target/release/rustchain-miner --wallet my-wallet --dry-run

# Verbose logging
./target/release/rustchain-miner --wallet my-wallet --verbose

# Generate a new wallet name
./target/release/rustchain-miner --create-wallet
```

### CLI Options

```
RustChain Miner - Proof of Antiquity

USAGE:
    rustchain-miner [OPTIONS]

OPTIONS:
    -w, --wallet <WALLET>        Wallet address/name for receiving rewards
    -n, --node <NODE>            Node URL [default: https://rustchain.org]
    -h, --hardware <HARDWARE>    Hardware model description [default: Auto-detect]
    -g, --generation <GENERATION> Hardware generation/family [default: Auto-detect]
    -a, --age <AGE>              Hardware age in years (overrides auto-detection)
    -i, --interval <INTERVAL>    Mining interval in seconds [default: 600]
    -v, --verbose                Enable verbose logging
        --dry-run                Dry run - validate config without submitting
        --create-wallet          Create a new wallet
```

## Architecture

### Miner Client (`miner_client.rs`)

The `MinerClient` provides a high-level async API for:

```rust
use rustchain::{HardwareInfo, miner_client::MinerClient};

// Create miner client
let hardware = HardwareInfo::new(
    "PowerPC G4".to_string(),
    "G4".to_string(),
    22  // years old
);

let mut client = MinerClient::with_default_node("my-wallet", hardware)?;

// Enroll with node
let enrollment = client.enroll().await?;
println!("Enrolled: epoch={}, multiplier={}", enrollment.epoch, enrollment.multiplier);

// Submit mining proof
let result = client.submit_proof().await?;
println!("Reward: {} RTC", result.reward_rtc);

// Check balance
let balance = client.get_balance().await?;
println!("Balance: {} RTC", balance);
```

### API Endpoints Integration

The miner integrates with these RustChain node endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Node health check |
| `/epoch` | GET | Current epoch info |
| `/api/miner/enroll` | POST | Enroll miner |
| `/api/miner/submit` | POST | Submit mining proof |
| `/wallet/balance` | GET | Check wallet balance |

### Hardware Fingerprint Attestation

The 6-check fingerprint system:

1. **Cache Timing** - Measures L1/L2/L3 cache latencies
2. **CPU Flags** - Detects instruction set capabilities
3. **SIMD Identity** - Verifies AltiVec/SSE/NEON presence
4. **Thermal Profile** - Measures thermal characteristics
5. **Hardware Serial** - Binds to physical hardware ID
6. **Anti-Emulation** - Detects VM/emulator signatures

```rust
use rustchain::miner_client::FingerprintAttestation;

// Generate attestation
let fp = FingerprintAttestation::generate()?;

// Validate against expected hardware tier
let validation = fp.validate(HardwareTier::Vintage)?;

println!("Cache valid: {}", validation.cache_valid);
println!("CPU valid: {}", validation.cpu_valid);
println!("Emulation detected: {}", validation.emulation_detected);
println!("Attestation fresh: {}", validation.is_fresh);
```

### Deep Entropy Verification

Statistical verification of hardware entropy:

```rust
use rustchain::deep_entropy::{DeepEntropyVerifier, ChallengeType};

let mut verifier = DeepEntropyVerifier::new();

// Generate challenge
let challenge = verifier.generate_challenge(ChallengeType::CacheTiming);

// Measure entropy
let proof = DeepEntropyVerifier::measure_cache_timing(1000);

// Verify
let result = verifier.verify(&proof, "G4");
println!("Confidence: {:.2}", result.confidence);
println!("Emulation probability: {:.2}", result.emulation_probability);
```

## Hardware Detection

The miner auto-detects hardware characteristics:

### Supported Architectures

- **x86_64** - Intel/AMD CPUs (486, Pentium, Core, Ryzen, etc.)
- **aarch64** - ARM/Apple Silicon (M1, M2, M3)
- **powerpc64** - PowerPC G3/G4/G5, POWER8

### Auto-Detection Examples

```bash
# PowerPC G4 (1999-2005)
Hardware: PowerPC G4 1.25GHz
Generation: G4
Age: 22 years | Tier: Vintage | Multiplier: 2.5×

# Intel 486 (1992)
Hardware: Intel 486 DX2-66
Generation: 486
Age: 33 years | Tier: Ancient | Multiplier: 3.5×

# Apple M1 (2020)
Hardware: Apple M1
Generation: M1
Age: 5 years | Tier: Modern | Multiplier: 1.0×
```

### Manual Override

```bash
# Override auto-detection
./rustchain-miner \
  --wallet my-miner \
  --hardware "PowerPC G4" \
  --generation "G4" \
  --age 22
```

## Compilation for Vintage Hardware

### PowerPC G4 (macOS Tiger/Leopard)

```bash
# Cross-compile for PowerPC
RUSTFLAGS="-C target-cpu=g4" \
  cargo build --release --target powerpc-apple-darwin
```

### POWER8 (Linux)

```bash
# Native compile on POWER8
cargo build --release --target ppc64le-unknown-linux-gnu
```

### Raspberry Pi (ARM64)

```bash
# Cross-compile for ARM64
cargo build --release --target aarch64-unknown-linux-gnu
```

## Configuration

### Environment Variables

```bash
# Node URL (overrides CLI --node)
export RUSTCHAIN_NODE=https://rustchain.org

# Wallet name (overrides CLI --wallet)
export RUSTCHAIN_WALLET=my-miner

# Log level
export RUST_LOG=debug
```

### Mining Intervals

Default epoch duration is 600 seconds (10 minutes). Adjust with `--interval`:

```bash
# Faster iterations (testing)
./rustchain-miner --wallet test --interval 60

# Standard epoch mining
./rustchain-miner --wallet production --interval 600
```

## Error Handling

### Common Errors

**Connection Failed**
```
Error: Connection failed: error trying to connect: ...
```
- Check node URL is correct
- Verify network connectivity
- Node may be offline

**Enrollment Failed**
```
Error: Enrollment failed: HTTP 400
```
- Wallet name may be invalid
- Hardware info may be malformed
- Check node logs

**Fingerprint Error**
```
Error: Fingerprint error: Emulation detected
```
- Running in VM/emulator
- Hardware signatures don't match expected profile
- Attestation expired

### Retry Logic

The miner automatically:
- Retries failed submissions
- Refreshes expired attestations
- Recovers from transient network errors

## Testing

### Unit Tests

```bash
cargo test --lib
```

### Integration Tests

```bash
# Test against local node
cargo test --test integration -- --nocapture
```

### Dry Run

```bash
# Validate configuration without submitting
./rustchain-miner --wallet test --dry-run --verbose
```

## Performance

### Resource Usage

- **Memory**: ~50MB RSS
- **CPU**: <1% (idle between epochs)
- **Network**: ~1KB per epoch submission

### Optimization

Release builds include:
- LTO (Link-Time Optimization)
- Codegen units = 1
- Strip symbols
- Opt-level 3

## Security

### Anti-Emulation

The miner implements multiple anti-emulation checks:
- Cache timing variance analysis
- CPU flag verification
- Thermal entropy measurement
- Hardware serial binding

### Self-Signed Certificates

The node uses self-signed TLS certificates. The client accepts these with:
```rust
.danger_accept_invalid_certs(true)
```

For production, consider:
- Using Let's Encrypt certificates
- Implementing certificate pinning
- mTLS authentication

## Integration with Python Miners

The Rust miner can coexist with Python miners:

```bash
# Run Rust miner alongside Python miner
./rustchain-miner --wallet rust-miner &
python3 miners/linux/rustchain_linux_miner.py --wallet python-miner
```

Both will:
- Share the same node endpoints
- Use the same fingerprint database
- Receive rewards to respective wallets

## Future Enhancements

- [ ] GPU mining support
- [ ] Mining pool protocol
- [ ] Hardware temperature monitoring
- [ ] Automatic overclock detection
- [ ] Performance benchmarking mode
- [ ] Web dashboard integration

## Troubleshooting

### Build Errors

**Missing dependencies**
```bash
# Install system dependencies
# Ubuntu/Debian
sudo apt install build-essential pkg-config libssl-dev

# macOS
xcode-select --install
brew install openssl
```

**Target not found**
```bash
# Install cross-compilation target
rustup target add powerpc-apple-darwin
```

### Runtime Errors

**Permission denied**
```bash
# Run without sudo (don't run as root)
./rustchain-miner --wallet my-wallet
```

**Wallet not found**
```bash
# Create wallet first
./rustchain-miner --create-wallet
```

## License

MIT License - see LICENSE file in repository root.

## Support

- Documentation: `docs/` directory
- API Reference: `docs/api/REFERENCE.md`
- Issues: GitHub issue tracker
- Discussions: GitHub Discussions

---

*RustChain - Proof of Antiquity. Every vintage computer has historical potential.*
