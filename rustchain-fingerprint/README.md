# rustchain-fingerprint

**RIP-PoA Hardware Fingerprint Suite** — High-tier continuation checks for bounty #734

[![Crates.io](https://img.shields.io/badge/crates.io-v0.1.0-orange)](https://crates.io/crates/rustchain-fingerprint)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Rust](https://img.shields.io/badge/rust-1.70+-orange)](https://rust-lang.org)

## Overview

This crate implements **6 core RIP-PoA fingerprint checks** for hardware attestation in the RustChain Proof-of-Antiquity consensus system. Each check validates unique physical characteristics of real hardware that cannot be easily emulated by VMs or containers.

### The 6 Fingerprint Checks

| # | Check | Purpose | What It Detects |
|---|-------|---------|-----------------|
| 1 | **Clock Drift** | Measures oscillator imperfections | Synthetic timing sources, perfect clocks |
| 2 | **Cache Timing** | Profiles L1/L2/L3 latency hierarchy | Flattened cache in emulators |
| 3 | **SIMD Identity** | Validates SIMD units (SSE/AVX/AltiVec/NEON) | Missing architecture-specific features |
| 4 | **Thermal Drift** | Measures performance change under heat load | No thermal variance in simulators |
| 5 | **Instruction Jitter** | Captures microarchitectural jitter | Deterministic scheduling in VMs |
| 6 | **Anti-Emulation** | Detects VM/hypervisor/cloud indicators | VMware, KVM, AWS, GCP, Azure, etc. |

**Bonus Check:** Device Age Oracle — Validates CPU model consistency and estimates release year.

## Installation

```bash
# Add to Cargo.toml
[dependencies]
rustchain-fingerprint = "0.1.0"

# Or build from source
cd rustchain-fingerprint
cargo build --release
```

## Quick Start

### Library Usage

```rust
use rustchain_fingerprint::{run_all_checks, validate_against_profile};

// Run all fingerprint checks
let report = run_all_checks();

// Check if all passed
if report.all_passed {
    println!("✅ Hardware attestation PASSED");
} else {
    println!("❌ {} / {} checks failed", 
             report.checks_total - report.checks_passed, 
             report.checks_total);
}

// Validate against reference profile
let valid = validate_against_profile(&report, "modern_x86");
```

### CLI Usage

```bash
# Run all checks with text output
./target/release/rustchain-fingerprint

# JSON output
./target/release/rustchain-fingerprint --format json

# Write JSON report to file
./target/release/rustchain-fingerprint --json-out fingerprint_report.json

# Compare against reference profile
./target/release/rustchain-fingerprint --compare modern_x86

# Redact sensitive information
./target/release/rustchain-fingerprint --json-out report.json --redact

# Verbose output
./target/release/rustchain-fingerprint --verbose
```

## Architecture-Specific Guards

The crate includes architecture-specific validation for:

### x86_64 (Intel/AMD)
- Expects SSE/SSE2 minimum
- AVX/AVX2 on modern CPUs
- Validates against x86-specific VM indicators

### aarch64 (ARM64/Apple Silicon)
- Expects NEON/ASIMD
- Detects Apple M1/M2/M3/M4 via sysctl
- ARM-specific cloud provider checks

### powerpc / powerpc64 (PowerPC G4/G5, POWER8+)
- Expects AltiVec/VMX/VSX
- Vintage CPU year estimation (1997-2006)
- PowerPC-specific DMI checks

## Cross-Compilation Guide

### Prerequisites

Install cross-compilation targets:

```bash
# x86_64 Linux (default on most systems)
rustup target add x86_64-unknown-linux-gnu

# aarch64 Linux (ARM64 servers, Raspberry Pi 4/5)
rustup target add aarch64-unknown-linux-gnu

# PowerPC 64-bit LE (POWER8+, Talos II)
rustup target add powerpc64le-unknown-linux-gnu

# PowerPC 32-bit (G4, AmigaOne)
rustup target add powerpc-unknown-linux-gnu
```

### Build Commands

```bash
# Native build (current architecture)
cargo build --release

# x86_64 Linux
cargo build --release --target x86_64-unknown-linux-gnu

# aarch64 Linux (ARM64)
cargo build --release --target aarch64-unknown-linux-gnu

# PowerPC 64-bit LE
cargo build --release --target powerpc64le-unknown-linux-gnu

# PowerPC 32-bit (vintage)
RUSTFLAGS="-C target-cpu=g4" cargo build --release --target powerpc-unknown-linux-gnu
```

### Cross-Compilation with Docker

```bash
# ARM64 cross-compile from x86_64
docker run --rm -v $(pwd):/workspace \
  messense/rust-musl-cross:aarch64-musl \
  cargo build --release --target aarch64-unknown-linux-musl

# PowerPC cross-compile
docker run --rm -v $(pwd):/workspace \
  messense/rust-musl-cross:powerpc64le-musl \
  cargo build --release --target powerpc64le-unknown-linux-musl
```

### Deployment Targets

| Target | Use Case | Notes |
|--------|----------|-------|
| `x86_64-unknown-linux-gnu` | Standard Linux servers | Most common |
| `aarch64-unknown-linux-gnu` | ARM servers, Pi, Apple Silicon (Linux) | Growing ecosystem |
| `powerpc64le-unknown-linux-gnu` | POWER8/9 servers, Talos II | Enterprise PowerPC |
| `powerpc-unknown-linux-gnu` | PowerMac G4, AmigaOne | Vintage mining |

## Reference Profiles

Built-in profiles for validation:

| Profile | Architecture | Expected Features |
|---------|--------------|-------------------|
| `modern_x86` | x86_64 | SSE, AVX (optional) |
| `vintage_ppc` | powerpc | AltiVec, 1997-2006 CPU |
| `arm64` | aarch64 | NEON, ASIMD |

```bash
# Validate against profile
./rustchain-fingerprint --compare modern_x86
```

## Output Format

### JSON Report Structure

```json
{
  "all_passed": true,
  "checks_passed": 7,
  "checks_total": 7,
  "results": [
    {
      "name": "clock_drift",
      "passed": true,
      "data": {
        "mean_ns": 1234567,
        "stdev_ns": 12345,
        "cv": 0.01,
        "drift_stdev": 5000
      }
    }
  ],
  "timestamp": 1709856000,
  "platform": {
    "architecture": "x86_64",
    "os": "linux",
    "cpu_model": "Intel(R) Core(TM) i7-8700K",
    "cpu_family": 6
  }
}
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All checks passed |
| `2` | One or more checks failed |

## Integration with RustChain Miner

```rust
use rustchain_fingerprint::{run_all_checks, FingerprintReport};
use rustchain_core::MiningProof;

fn create_attested_proof(wallet: &str) -> Result<MiningProof, &'static str> {
    // Run fingerprint checks
    let report = run_all_checks();
    
    // Require all checks to pass for reward eligibility
    if !report.all_passed {
        return Err("Hardware attestation failed");
    }
    
    // Generate fingerprint hash for proof
    let fingerprint_hash = generate_fingerprint_hash(&report);
    
    Ok(MiningProof {
        wallet: wallet.to_string(),
        fingerprint_hash,
        timestamp: report.timestamp,
        // ... other fields
    })
}

fn generate_fingerprint_hash(report: &FingerprintReport) -> [u8; 32] {
    use sha2::{Sha256, Digest};
    let json = serde_json::to_string(report).unwrap();
    let mut hasher = Sha256::new();
    hasher.update(json.as_bytes());
    hasher.finalize().into()
}
```

## Security Considerations

### What This Protects Against

- **VM/Container Mining** — Detects hypervisors and cloud providers
- **CPU Spoofing** — Validates CPU model matches architecture
- **Timing Manipulation** — Detects synthetic/perfect timing sources
- **Cache Emulation** — Identifies flattened cache hierarchies

### Limitations

- **Bare-metal VMs** — Sophisticated attackers with bare-metal access may bypass some checks
- **Hardware Diversity** — Some legitimate hardware may fail strict thresholds
- **Aging Hardware** — Very old CPUs may show different timing characteristics

### Best Practices

1. **Run in isolation** — Execute fingerprint checks without other load
2. **Multiple samples** — Consider running multiple times and averaging
3. **Combine with other signals** — Use alongside ROM fingerprint, network attestation
4. **Regular re-validation** — Re-run checks periodically during mining sessions

## Testing

```bash
# Run unit tests
cargo test

# Run with verbose output
cargo test -- --nocapture

# Run benchmarks
cargo bench
```

## Troubleshooting

### Common Failures

| Check | Failure | Likely Cause |
|-------|---------|--------------|
| Clock Drift | `synthetic_timing` | VM with stable clock source |
| Cache Timing | `no_cache_hierarchy` | Emulator with flat memory |
| SIMD Identity | `no_simd_detected` | Very old CPU or VM without passthrough |
| Thermal Drift | `no_thermal_variance` | Short test duration or active cooling |
| Instruction Jitter | `no_jitter` | Deterministic scheduler (VM) |
| Anti-Emulation | `vm_detected` | Running in VM/cloud/container |

### Debugging

```bash
# Verbose output to see all data
./rustchain-fingerprint --verbose

# JSON output for detailed analysis
./rustchain-fingerprint --format json | jq

# Skip specific checks for debugging
./rustchain-fingerprint --skip anti_emulation
```

## Contributing

Contributions welcome! Areas of interest:

- Additional architecture support (RISC-V, SPARC, MIPS)
- Improved timing thresholds based on real hardware data
- New anti-emulation heuristics
- Performance optimizations for vintage CPUs

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- Original Python implementation: `node/fingerprint_checks.py`
- RIP-PoA specification: RIP-002
- Bounty #734: High-tier fingerprint continuation

## Resources

- [RustChain Whitepaper](../docs/whitepaper/)
- [RIP-002: Proof of Antiquity](../rips/src/proof_of_antiquity.rs)
- [CPU Antiquity System](../CPU_ANTIQUITY_SYSTEM.md)
- [Bounty #734](https://github.com/Scottcjn/rustchain-bounties/issues/734)

---

*Built with ❤️ for vintage hardware preservation*
