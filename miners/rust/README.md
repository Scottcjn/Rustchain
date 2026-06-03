# RustChain Native Rust Miner

A native Rust implementation of the RustChain Proof-of-Antiquity (PoA) attestation client. This miner collects hardware fingerprints from the local machine and submits them to a RustChain node for scoring.

## What It Does

The miner runs a continuous attestation loop:

1. **Fingerprint collection** — samples CPU model, core count, cache sizes, clock-drift coefficient of variation, cache-access timing curves, thermal drift, and SIMD feature identity
2. **Payload construction** — wraps fingerprint data in a signed JSON attestation payload with a SHA-256 integrity hash
3. **Submission** — POSTs the payload to `/attest/submit` on the configured node, with exponential back-off retries
4. **Sleep** — waits for the configured interval, then repeats

Higher PoA scores are awarded to older / more unusual hardware (high clock jitter, distinctive cache timing curves, rare architectures).

## Supported Architectures

| Architecture | Status |
|---|---|
| x86_64 | ✅ Full (SIMD probing) |
| x86 (32-bit) | ✅ Basic |
| aarch64 | ✅ Full (NEON/SVE detection) |
| arm (32-bit) | ✅ Basic |
| powerpc / powerpc64 | ✅ Basic |
| riscv32 / riscv64 | ✅ Basic |
| mips / mips64 | ✅ Basic |
| s390x | ✅ Basic |
| sparc64 | ✅ Basic |

## Prerequisites

- **Rust 1.70+** — install from [rustup.rs](https://rustup.rs/)
- **Internet / LAN access** to a RustChain node

```bash
# Install Rust (if needed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

## Building

```bash
# Clone the repo (if you haven't already)
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/rust

# Debug build (faster compile, slower binary)
cargo build

# Release build (recommended for production)
cargo build --release
```

The binary is placed at:
- `target/debug/rustchain-miner` (debug)
- `target/release/rustchain-miner` (release)

## Running

### Basic usage

```bash
./target/release/rustchain-miner \
    --node-url http://localhost:8333 \
    --miner-id my-rig-hostname \
    --interval 60
```

### All options

```
Options:
  --node-url <URL>           RustChain node URL [default: http://localhost:8333]
  --miner-id <ID>            Unique miner identifier (hostname, wallet address, etc.)
                             [default: default-miner]
  --interval <SECONDS>       Seconds between attestation submissions [default: 60]
  --max-retries <N>          Retry attempts per cycle on failure [default: 3]
  --retry-backoff-ms <MS>    Initial back-off between retries, doubles each attempt
                             [default: 1000]
  -h, --help                 Print help
  -V, --version              Print version
```

### Example — high-frequency mining on a local testnet

```bash
./target/release/rustchain-miner \
    --node-url http://127.0.0.1:8333 \
    --miner-id "power8-box-01" \
    --interval 30 \
    --max-retries 5 \
    --retry-backoff-ms 500
```

### Running as a systemd service

```ini
# /etc/systemd/system/rustchain-miner.service
[Unit]
Description=RustChain Native Rust Miner
After=network.target

[Service]
ExecStart=/usr/local/bin/rustchain-miner \
    --node-url http://localhost:8333 \
    --miner-id %H \
    --interval 60
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rustchain-miner
journalctl -fu rustchain-miner
```

## Attestation Payload Format

```json
{
  "miner": "my-rig-01",
  "timestamp": "2026-03-28T12:00:00Z",
  "device": {
    "arch": "x86_64",
    "cores": 4,
    "model": "Intel(R) Pentium(R) III 700 MHz"
  },
  "fingerprint": {
    "clock_drift_cv": 0.042,
    "cache_timing": [2.1, 8.4, 45.7, 210.3],
    "thermal_drift": 0.003,
    "simd_identity": "a3f8c1e200b94d71"
  },
  "integrity_hash": "sha256:<hex>"
}
```

## Development

```bash
# Run tests
cargo test

# Check without compiling
cargo check

# Format code
cargo fmt

# Lint
cargo clippy
```

## Contributing

See the main [CONTRIBUTING.md](../../CONTRIBUTING.md) and the open bounty issue [#1601](https://github.com/Scottcjn/Rustchain/issues/1601) for context on this implementation.

## License

MIT — see [LICENSE](../../LICENSE).
