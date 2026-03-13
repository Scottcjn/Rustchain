# RustChain Asciinema Recording Scripts

Scripts for creating and converting terminal recordings for documentation.

## Quick Start

### 1. Install Prerequisites

```bash
# Install asciinema
brew install asciinema  # macOS
pip install asciinema   # Linux/Windows

# Optional: Install svg-term for GIF/SVG conversion
npm install -g svg-term-cli
```

### 2. Record Installation

```bash
./record_miner_install.sh
```

This script will:
- Check for asciinema installation
- Guide you through recording the miner installation
- Save the recording to `docs/asciinema/miner_install.cast`

### 3. Record First Attestation

```bash
./record_first_attestation.sh
```

### 4. Convert to GIF/SVG

```bash
# Convert to SVG (recommended for web docs)
./convert_to_gif.sh docs/asciinema/miner_install.cast

# Specify custom output
./convert_to_gif.sh input.cast output.gif
```

## Scripts Reference

| Script | Purpose | Output |
|--------|---------|--------|
| `record_miner_install.sh` | Interactive recording of miner installation | `docs/asciinema/miner_install.cast` |
| `record_first_attestation.sh` | Interactive recording of first attestation | `docs/asciinema/first_attestation.cast` |
| `convert_to_gif.sh` | Convert .cast files to GIF/SVG | `*.gif` or `*.svg` |
| `demo_miner_install.sh` | Demo script (simulated output) | For use with `asciinema rec` |
| `demo_first_attestation.sh` | Demo script (simulated output) | For use with `asciinema rec` |

## Demo Scripts

Use demo scripts for consistent recordings without actual installation:

```bash
# Record demo installation
asciinema rec --command "bash demo_miner_install.sh" \
    ../../docs/asciinema/demo_install.cast

# Record demo attestation
asciinema rec --command "bash demo_first_attestation.sh" \
    ../../docs/asciinema/demo_attestation.cast
```

## Tips for Quality Recordings

1. **Terminal Size**: Set to 100x30 or smaller before recording
2. **Theme**: Use a high-contrast terminal theme
3. **Font**: Use a monospace font with good readability
4. **Pacing**: Speak clearly if adding voiceover
5. **Duration**: Keep under 60 seconds for optimal file size

## Troubleshooting

### asciinema not found
```bash
# macOS
brew install asciinema

# Linux/Windows
pip install asciinema

# Verify installation
asciinema --version
```

### Permission denied
```bash
chmod +x *.sh
```

### Conversion fails
```bash
# Install svg-term-cli
npm install -g svg-term-cli

# Verify installation
svg-term --version
```

## File Organization

```
scripts/asciinema/
├── README.md                      # This file
├── record_miner_install.sh        # Recording script
├── record_first_attestation.sh    # Recording script
├── convert_to_gif.sh              # Conversion utility
├── demo_miner_install.sh          # Demo script
└── demo_first_attestation.sh      # Demo script

docs/asciinema/
├── README.md                      # Asciinema docs
├── miner_install.cast             # Installation recording
└── first_attestation.cast         # Attestation recording
```

## License

Same as RustChain project (Apache License 2.0)
