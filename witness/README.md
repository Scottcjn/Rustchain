# SPDX-License-Identifier: MIT
# RustChain Floppy Witness Kit

Epoch proofs on 1.44MB media. Block proofs carried by sneakernet into
air-gapped or museum-grade machines.

## Quickstart

```bash
# Write witnesses to floppy image
python witness_cli.py write --epoch 500 --output witness.img

# Read witnesses from image
python witness_cli.py read --input witness.img

# Verify a witness
python witness_cli.py verify witness.json --node https://rustchain.org

# Show capacity info
python witness_cli.py info
```

## Format

Each epoch witness contains:
- Epoch number, timestamp
- Miner lineup (IDs + architectures + multipliers)
- Settlement hash
- Ergo anchor TX ID
- Commitment hash
- Minimal Merkle proof

Target: **<100KB per epoch**. A 1.44MB floppy holds **~14,000+** witnesses.

## Supported Media

| Media | Size | Witnesses |
|---|---|---|
| 1.44MB Floppy | 1,474,560 bytes | ~14,000+ |
| 100MB ZIP Disk | 100,000,000 bytes | ~950,000+ |

## Disk Image Format

```
[512 bytes] Header: RWTK magic + version + count + label length
[variable]  ASCII art label
[8 * N]     Index table (offset + length per witness)
[variable]  Compressed witness data (zlib level 9)
[padding]   Zero-filled to disk size
```
