# PowerPC Native Support

## Overview

The `rustchain-miner` is designed to compile and run natively on PowerPC hardware including Apple G4/G5 Macs running Mac OS X or Linux.

## Architecture Detection

The miner automatically detects PowerPC variants:

| CPU | Pattern Match | `device_arch` | Multiplier |
|-----|---------------|---------------|------------|
| G3 (750) | "750" in brand | `g3` | 1.8x |
| G4 (7450/7447/7455) | "7450"/"7447"/"7455" in brand | `g4` | 2.5x |
| G5 (970) | "970" in brand | `g5` | 2.0x |

## Timing: `mftb` (Move From Time Base)

On PowerPC, `rdtsc` does not exist. Instead, we use the **Time Base Register (TBR)** via the `mftb` instruction:

```rust
#[cfg(any(target_arch = "powerpc", target_arch = "powerpc64"))]
#[inline(always)]
fn read_timestamp() -> u64 {
    let val: u64;
    unsafe {
        core::arch::asm!(
            "mftb {0}",
            out(reg) val,
            options(nostack, nomem),
        );
    }
    val
}
```

The TBR increments at a fixed frequency (typically 24.576 MHz on G4/G5 Macs), providing stable, high-resolution timing for all fingerprint checks.

## SIMD: AltiVec/VMX Detection

On PowerPC, SIMD is provided by **AltiVec** (also known as VMX or Velocity Engine). Detection checks `/proc/cpuinfo` on Linux for the `altivec` flag:

```rust
#[cfg(any(target_arch = "powerpc", target_arch = "powerpc64"))]
{
    if let Ok(cpuinfo) = std::fs::read_to_string("/proc/cpuinfo") {
        if cpuinfo.to_lowercase().contains("altivec") {
            features.push("AltiVec".to_string());
        }
    }
}
```

## Big-Endian Correctness

PowerPC is a **big-endian** architecture. All byte-level operations in the miner handle endianness correctly:

- **JSON/HTTP**: All network I/O uses UTF-8 text (endian-neutral)
- **Serde**: Serialization/deserialization is endian-safe
- **Timing**: `u64` values from `mftb` are native-endian, used only for arithmetic (no byte reinterpretation)
- **Hashing**: `sha2` crate handles endianness internally
- **Hex encoding**: `hex::encode()` operates on byte slices (endian-neutral)

No byte-swapping is needed because the miner never performs raw byte reinterpretation of multi-byte values across an endianness boundary.

## Cross-Compiling for PowerPC

### From x86_64 Linux (using `cross`)

```bash
cargo install cross --locked
cross build --release --target powerpc64-unknown-linux-gnu
```

This produces a big-endian PPC64 ELF binary. Transfer to the target:

```bash
scp target/powerpc64-unknown-linux-gnu/release/rustchain-miner user@g5-mac:~/
ssh user@g5-mac './rustchain-miner --wallet your-wallet'
```

### From macOS (targeting PPC Mac OS X)

For Mac OS X on G4/G5, you need the `powerpc-apple-darwin` target. This requires:

1. A PowerPC cross-compilation toolchain (e.g., from MacPorts or legacy Xcode)
2. The Rust target: `rustup target add powerpc-apple-darwin` (available on nightly)

```bash
rustup override set nightly
rustup target add powerpc-apple-darwin
cargo build --release --target powerpc-apple-darwin
```

### Running on Real PowerPC Hardware

```bash
# On a G4/G5 Mac running Linux (Debian/Ubuntu PPC):
./rustchain-miner --test-only
# Should detect: PowerPC G4 (7450) / g4 / 2.5x multiplier

# Start mining:
./rustchain-miner --wallet my-g4-wallet
```

## Known Limitations

1. **Inline `asm!` on PowerPC**: Stable Rust supports `asm!` on x86_64 and aarch64. PowerPC `asm!` may require nightly Rust. The miner includes a fallback that uses `std::time::Instant` if inline asm is unavailable.

2. **Mac OS X (classic)**: The `powerpc-apple-darwin` target is Tier 3 in Rust. It may require additional build flags or patches. Linux on PowerPC (Debian PPC, Void Linux) is the recommended environment.

3. **32-bit PowerPC**: G3/G4 Macs are 32-bit (`powerpc`). The `mftb` instruction works the same on 32-bit, but some crate dependencies may not support 32-bit targets. Test with `powerpc-unknown-linux-gnu`.
