# rustchain-miner

Native Rust miner for [RustChain](https://github.com/Scottcjn/Rustchain) — a Proof-of-Antiquity blockchain where vintage hardware earns higher mining rewards.

## Features

- **Single binary** — no Python, pip, or venv needed
- **Full RIP-PoA fingerprinting** — all 6 hardware fingerprint checks in native Rust
- **Inline assembly** — `rdtsc` (x86_64) / `mftb` (PowerPC) for precise timing
- **Cross-platform** — x86_64, aarch64, PowerPC, RISC-V (riscv64gc) targets
- **Self-signed TLS** — works with the RustChain node out of the box

## Quick Start

```bash
# Build
cargo build --release

# Start mining
./target/release/rustchain-miner --wallet YOUR_WALLET_NAME

# Run fingerprint checks only
./target/release/rustchain-miner --test-only

# Show the attestation payload (without submitting)
./target/release/rustchain-miner --wallet YOUR_WALLET --show-payload

# Dry run (build + display payload, no submission)
./target/release/rustchain-miner --wallet YOUR_WALLET --dry-run

# Use a custom node
./target/release/rustchain-miner --wallet YOUR_WALLET --node https://your-node:port
```

## RIP-PoA Fingerprint Checks

| # | Check | What It Measures |
|---|-------|-----------------|
| 1 | Clock-Skew & Oscillator Drift | Timing variance from `rdtsc`/`mftb` |
| 2 | Cache Timing Fingerprint | L1/L2/L3 latency sweep across buffer sizes |
| 3 | SIMD Unit Identity | SSE/AVX/AltiVec/NEON instruction timing |
| 4 | Thermal Drift Entropy | Entropy quality across thermal states |
| 5 | Instruction Path Jitter | Cycle-level jitter across int/FP/branch units |
| 6 | Anti-Emulation | VM/hypervisor detection |

## Architecture Detection

| CPU Pattern | Family | Arch | Multiplier |
|------------|--------|------|-----------|
| PowerPC 7450/7447/7455 | PowerPC | g4 | 2.5x |
| PowerPC 970 | PowerPC | g5 | 2.0x |
| PowerPC 750 | PowerPC | g3 | 1.8x |
| Apple M1/M2/M3 | ARM | apple_silicon | 1.2x |
| Core 2 | x86_64 | core2duo | 1.3x |
| StarFive JH7110 | RISC-V | starfive_jh7110 | 1.1x |
| SiFive Unmatched (FU740) | RISC-V | sifive_unmatched | 1.0x |
| Milk-V Pioneer (SG2380) | RISC-V | milkv_pioneer | 0.9x |
| Generic RISC-V 64-bit | RISC-V | riscv_modern | 0.95x |
| Everything else | x86_64 | modern | 1.0x |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Node health check |
| `/epoch` | GET | Current epoch info |
| `/attest/challenge` | POST | Request attestation nonce |
| `/attest/submit` | POST | Submit attestation payload |
| `/epoch/enroll` | POST | Enroll in current epoch |
| `/wallet/balance` | GET | Check RTC balance |

Default node: `https://50.28.86.131` (self-signed cert)

## Cross-Compilation

```bash
# Install cross
cargo install cross

# Build for targets
cross build --release --target x86_64-unknown-linux-musl
cross build --release --target aarch64-unknown-linux-musl
cross build --release --target powerpc64-unknown-linux-gnu
cross build --release --target riscv64gc-unknown-linux-gnu
```

## Running as a Service (Linux)

A sample systemd unit file is included in `contrib/rustchain-miner.service`:

```bash
# Install the binary
sudo cp target/release/rustchain-miner /usr/local/bin/

# Install the service file (edit YOUR_USERNAME and YOUR_MINER_ID first)
sudo cp contrib/rustchain-miner.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rustchain-miner

# Check status
sudo systemctl status rustchain-miner
journalctl -u rustchain-miner -f
```

## Logging & Log Rotation

The miner logs to stderr via `env_logger`. Control verbosity with `RUST_LOG`:

```bash
RUST_LOG=debug ./rustchain-miner --wallet my-wallet   # Verbose
RUST_LOG=warn  ./rustchain-miner --wallet my-wallet   # Quiet
```

When running as a systemd service, logs go to journald (auto-rotated). For manual runs, pipe to a file with rotation:

```bash
# Using logrotate (create /etc/logrotate.d/rustchain-miner):
/var/log/rustchain-miner.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}

# Then run with:
./rustchain-miner --wallet my-wallet 2>&1 | tee -a /var/log/rustchain-miner.log
```

## TLS Certificate

The node at `50.28.86.131` uses a self-signed certificate. By default the miner accepts it (matching the Python miner's `verify=False`). For stricter security, you can pin the node's certificate:

```bash
# Download the node's cert
openssl s_client -connect 50.28.86.131:443 </dev/null 2>/dev/null | \
  openssl x509 -outform PEM > rustchain-node.pem
```

Certificate pinning support via a `--tls-cert` flag is planned for a future release.

## License

MIT
