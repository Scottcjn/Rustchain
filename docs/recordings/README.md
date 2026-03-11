# RustChain Installation Recordings

This directory contains visual installation guides for RustChain miner.

## Available Recordings

### Installation Demo (asciinema)
- **File**: `rustchain-install.cast`
- **Format**: asciinema recording
- **Duration**: ~12 seconds
- **Content**: Complete miner installation and first attestation workflow

## How to View

### View asciinema recording
```bash
asciinema play docs/recordings/rustchain-install.cast
```

### Convert to GIF (optional)
```bash
# Install agg (asciinema GIF generator)
cargo install --git https://github.com/asciinema/agg

# Generate GIF
agg docs/recordings/rustchain-install.cast docs/recordings/rustchain-install.gif
```

## Recording Details

The installation demo shows:
1. Repository cloning
2. Dependency installation with cargo
3. Release build compilation
4. First attestation execution
5. Successful completion confirmation

**Bounty**: #1615 - 2 RTC
**Created**: 2026-03-11
**Author**: Builder-Agent (OpenClaw)
