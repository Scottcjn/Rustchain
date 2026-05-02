<!-- SPDX-License-Identifier: MIT -->
# Floppy Witness Kit

**Epoch proofs on 1.44MB media** — Bounty #2313 Implementation

A Rust CLI tool for writing, reading, and verifying RustChain epoch witnesses on floppy disks and compatible media.

## Features

- ✅ **Compact Witnesses**: <100KB per epoch (typically ~500 bytes)
- ✅ **High Capacity**: ~14,700 epochs per 1.44MB floppy
- ✅ **Multi-Format**: Raw .img, FAT filesystem, QR codes
- ✅ **Air-gapped**: Offline verification support
- ✅ **ASCII Art**: Retro terminal-style disk label
- ✅ **100% Rust**: Safe, fast, portable

## Quick Start

```bash
# Build
cargo build --release

# Write epoch to floppy
./target/release/rustchain-witness write --epoch 500 --device ./floppy.img

# Read witnesses
./target/release/rustchain-witness read --device ./floppy.img

# Verify witness
./target/release/rustchain-witness verify ./epoch_500.witness

# Check capacity
./target/release/rustchain-witness capacity
```

## Commands

| Command | Description |
|---------|-------------|
| `write` | Write epoch witness to device |
| `read` | Read witness from device |
| `verify` | Verify witness against node |
| `qr-export` | Export as QR code |
| `capacity` | Calculate floppy capacity |

## Documentation

See BOUNTY_2313_IMPLEMENTATION.md (in docs/) for complete documentation.

## Tests

```bash
cargo test
```

All 15 tests passing ✅

## License

MIT
