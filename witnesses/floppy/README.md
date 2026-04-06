# SPDX-License-Identifier: MIT

# Floppy Witness Kit

Compact RustChain epoch witness format for sneakernet transport on vintage media.

## Usage

```bash
# Write 100 epoch witnesses starting from epoch 500
python encoder.py write --epoch 500 --count 100 --device witness.img

# Read back
python encoder.py read --device witness.img

# Verify integrity
python encoder.py verify witness.img

# Print disk label
python encoder.py label
```

## Supported Formats
- **Raw floppy image** (`.img`) — write directly to `/dev/fd0`
- **FAT file** — standard file on any FAT-formatted media (ZIP disks, USB)
- **QR code** — compact base85 encoding for single-epoch witnesses

## Capacity
A full 1.44MB floppy holds ~14,000 epoch witnesses.

## Tests
```bash
cd witnesses/floppy && pytest test_encoder.py -v
```
