# Cross-Compilation Guide for rustchain-fingerprint

## Supported Targets

| Target | Architecture | Use Case | Status |
|--------|--------------|----------|--------|
| `x86_64-unknown-linux-gnu` | x86_64 | Standard Linux servers | ✅ Native |
| `aarch64-unknown-linux-gnu` | ARM64 | ARM servers, Raspberry Pi, Apple Silicon (Linux) | ✅ Tested |
| `powerpc64le-unknown-linux-gnu` | PPC64 LE | POWER8/9 servers, Talos II | ✅ Supported |
| `powerpc-unknown-linux-gnu` | PPC32 | PowerMac G4, AmigaOne | ✅ Supported |

## Prerequisites

### Install Rust Toolchain

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
rustup update
```

### Add Cross-Compilation Targets

```bash
# x86_64 (usually default)
rustup target add x86_64-unknown-linux-gnu

# aarch64 (ARM64)
rustup target add aarch64-unknown-linux-gnu

# PowerPC 64-bit LE (POWER8+)
rustup target add powerpc64le-unknown-linux-gnu

# PowerPC 32-bit (G4, vintage)
rustup target add powerpc-unknown-linux-gnu
```

## Native Builds

```bash
cd rustchain-fingerprint

# Build for current architecture
cargo build --release

# Run tests
cargo test

# Run CLI
./target/release/rustchain-fingerprint
```

## Cross-Compilation

### Method 1: Direct Cross-Compilation

```bash
# ARM64 Linux
cargo build --release --target aarch64-unknown-linux-gnu

# PowerPC 64-bit LE
cargo build --release --target powerpc64le-unknown-linux-gnu

# PowerPC 32-bit (with G4 optimizations)
RUSTFLAGS="-C target-cpu=g4" cargo build --release --target powerpc-unknown-linux-gnu
```

### Method 2: Cross-RS (Recommended)

Install cross:

```bash
cargo install cross
```

Build with cross:

```bash
# ARM64
cross build --release --target aarch64-unknown-linux-gnu

# PowerPC 64-bit LE
cross build --release --target powerpc64le-unknown-linux-gnu

# PowerPC 32-bit
cross build --release --target powerpc-unknown-linux-gnu
```

### Method 3: Docker Cross-Compilation

```bash
# ARM64 with musl (static linking)
docker run --rm -v $(pwd):/workspace \
  messense/rust-musl-cross:aarch64-musl \
  cargo build --release --target aarch64-unknown-linux-musl

# PowerPC 64-bit LE with musl
docker run --rm -v $(pwd):/workspace \
  messense/rust-musl-cross:powerpc64le-musl \
  cargo build --release --target powerpc64le-unknown-linux-musl
```

## Architecture-Specific Notes

### x86_64 (Intel/AMD)

**Features:**
- SSE/SSE2 always available
- AVX/AVX2 on modern CPUs
- Full anti-emulation support

**Build:**
```bash
cargo build --release --target x86_64-unknown-linux-gnu
```

**Optimizations:**
```bash
# For modern Intel (Skylake+)
RUSTFLAGS="-C target-cpu=skylake" cargo build --release

# For modern AMD (Zen 2+)
RUSTFLAGS="-C target-cpu=znver2" cargo build --release

# Generic x86_64 (maximum compatibility)
RUSTFLAGS="-C target-cpu=x86-64" cargo build --release
```

### aarch64 (ARM64/Apple Silicon)

**Features:**
- NEON/ASIMD always available
- macOS: Rosetta 2 compatibility for x86_64 binaries
- Linux: Native ARM64 support

**Build:**
```bash
# Linux ARM64
cargo build --release --target aarch64-unknown-linux-gnu

# macOS (native ARM64)
cargo build --release

# macOS (universal binary)
cargo build --release --target aarch64-apple-darwin
cargo build --release --target x86_64-apple-darwin
lipo -create target/aarch64-apple-darwin/release/rustchain-fingerprint \
       target/x86_64-apple-darwin/release/rustchain-fingerprint \
       -output target/release/rustchain-fingerprint-universal
```

**Optimizations:**
```bash
# Apple M1/M2
RUSTFLAGS="-C target-cpu=apple-m1" cargo build --release

# Generic ARMv8-A
RUSTFLAGS="-C target-cpu=generic-armv8-a" cargo build --release
```

### powerpc (PowerPC G4/G5)

**Features:**
- AltiVec/VMX support
- Vintage hardware (1997-2006)
- Big-endian (powerpc) or little-endian (powerpc64le)

**Build:**
```bash
# PowerPC 32-bit (G4)
RUSTFLAGS="-C target-cpu=g4" cargo build --release --target powerpc-unknown-linux-gnu

# PowerPC 64-bit LE (POWER8+)
cargo build --release --target powerpc64le-unknown-linux-gnu

# PowerPC 64-bit BE (POWER8+ big-endian)
cargo build --release --target powerpc64-unknown-linux-gnu
```

**Vintage CPU Optimizations:**
```bash
# PowerMac G4 (7450/7447)
RUSTFLAGS="-C target-cpu=g4 -C opt-level=2" cargo build --release --target powerpc-unknown-linux-gnu

# PowerMac G5 (970)
RUSTFLAGS="-C target-cpu=g5 -C opt-level=2" cargo build --release --target powerpc64-unknown-linux-gnu

# AmigaOne (SAM440/460)
RUSTFLAGS="-C target-cpu=440ep -C opt-level=2" cargo build --release --target powerpc-unknown-linux-gnu
```

**Notes:**
- Rust 1.70+ required for powerpc targets
- Some older PowerPC systems may need musl libc
- Consider static linking for portability

### powerpc64le (POWER8/9 Little-Endian)

**Features:**
- VSX/VMX support
- Modern PowerPC servers (Talos II)
- Little-endian ABI

**Build:**
```bash
cargo build --release --target powerpc64le-unknown-linux-gnu
```

**Optimizations:**
```bash
# POWER8
RUSTFLAGS="-C target-cpu=pwr8" cargo build --release --target powerpc64le-unknown-linux-gnu

# POWER9
RUSTFLAGS="-C target-cpu=pwr9" cargo build --release --target powerpc64le-unknown-linux-gnu
```

## Testing Cross-Compiled Binaries

### QEMU User-Mode Emulation

```bash
# Install QEMU
sudo apt-get install qemu-user-static

# Run ARM64 binary on x86_64
qemu-aarch64-static target/aarch64-unknown-linux-gnu/release/rustchain-fingerprint

# Run PowerPC binary on x86_64
qemu-ppc64le-static target/powerpc64le-unknown-linux-gnu/release/rustchain-fingerprint
```

### Remote Testing

```bash
# Copy to target system
scp target/aarch64-unknown-linux-gnu/release/rustchain-fingerprint user@arm-server:/usr/local/bin/

# Run on target
ssh user@arm-server rustchain-fingerprint --format json
```

## Deployment

### Static Linking (Recommended for Portability)

```bash
# Use musl for static binaries
cargo build --release --target x86_64-unknown-linux-musl
cargo build --release --target aarch64-unknown-linux-musl
```

### Dynamic Linking (Smaller Binaries)

```bash
# Standard glibc linking
cargo build --release --target x86_64-unknown-linux-gnu
```

## Troubleshooting

### Linker Errors

```bash
# Install cross-compilation toolchain
# Ubuntu/Debian
sudo apt-get install gcc-aarch64-linux-gnu gcc-powerpc64le-linux-gnu

# For PowerPC 32-bit
sudo apt-get install gcc-powerpc-linux-gnu

# macOS (with Homebrew)
brew install aarch64-unknown-linux-gnu
brew install ppc64le-unknown-linux-gnu
```

### Missing Target

```bash
# List available targets
rustup target list

# Add missing target
rustup target add <target-triple>
```

### Runtime Errors

```bash
# Check binary architecture
file target/<target-triple>/release/rustchain-fingerprint

# Check dynamic dependencies
ldd target/<target-triple>/release/rustchain-fingerprint

# For musl binaries (no dynamic dependencies expected)
ldd target/<target-triple>/release/rustchain-fingerprint
# Should show: "not a dynamic executable"
```

## Performance Comparison

| Target | Binary Size | Startup Time | Fingerprint Time |
|--------|-------------|--------------|------------------|
| x86_64 (native) | ~800KB | ~5ms | ~10s |
| aarch64 (native) | ~750KB | ~5ms | ~12s |
| powerpc64le | ~850KB | ~10ms | ~15s |
| powerpc (G4) | ~900KB | ~20ms | ~25s |

*Times are approximate and vary by hardware.*

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Cross-Compile

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        target:
          - x86_64-unknown-linux-gnu
          - aarch64-unknown-linux-gnu
          - powerpc64le-unknown-linux-gnu
          - powerpc-unknown-linux-gnu

    steps:
      - uses: actions/checkout@v4
      
      - name: Install Rust
        uses: dtolnay/rust-action@stable
        with:
          targets: ${{ matrix.target }}
      
      - name: Install cross
        run: cargo install cross
      
      - name: Build
        run: cross build --release --target ${{ matrix.target }}
      
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: rustchain-fingerprint-${{ matrix.target }}
          path: target/${{ matrix.target }}/release/rustchain-fingerprint
```

## Resources

- [Rust Cross-Compilation Guide](https://rust-lang.github.io/rustup/cross-compilation.html)
- [Cross-RS](https://github.com/cross-rs/cross)
- [Musl Cross-Compile Docker Images](https://github.com/messense/rust-musl-cross)
- [PowerPC Rust Support](https://rust-lang.github.io/rustup/platform-support/powerpc-unknown-linux-gnu.html)

---

*Last updated: 2026-03-07*
*For bounty #734: High-tier RIP-PoA fingerprint continuation*
