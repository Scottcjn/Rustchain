# Homebrew Installation Guide - RustChain Miner

> **Issue #1612**: Create a Homebrew formula for RustChain miner with install/test instructions and practical caveats.

## Overview

This Homebrew formula provides a production-safe, minimal installation method for the RustChain Proof-of-Antiquity Miner on macOS.

---

## Prerequisites

- **macOS** 10.15 (Catalina) or later
- **Homebrew** installed: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
- **Network access** to `rustchain.org`

---

## Installation

### Option A: Install from Tap (Recommended)

```bash
# Add the RustChain bounties tap
brew tap rustchain-bounties/rustchain-bounties

# Install the miner
brew install rustchain-miner
```

### Option B: Install from Local Formula

```bash
# Clone or navigate to the repository
cd /path/to/rustchain-bounties

# Install from formula file
brew install ./homebrew/rustchain-miner.rb
```

### Option C: Install from Raw URL

```bash
brew install https://raw.githubusercontent.com/Scottcjn/Rustchain/main/homebrew/rustchain-miner.rb
```

---

## Usage

### Basic Mining

```bash
# Run with auto-generated wallet
rustchain-miner

# Run with specific wallet ID
rustchain-miner --wallet YOUR_WALLET_ID

# Run headless (no GUI, suitable for background)
rustchain-miner --headless --wallet YOUR_WALLET_ID

# Specify custom node URL
rustchain-miner --wallet YOUR_WALLET_ID --node https://rustchain.org
```

### Check Status

```bash
# View miner help
rustchain-miner --help

# Check if miner is running
ps aux | grep rustchain_miner
```

---

## Auto-Start (launchd)

The miner does **NOT** auto-start by default for security reasons. Enable it manually:

### Using brew services (Recommended)

```bash
# Start with wallet ID
brew services start rustchain-miner -- --wallet YOUR_WALLET_ID

# Stop
brew services stop rustchain-miner

# Check status
brew services list
```

### Manual launchd Setup

```bash
# Copy plist to LaunchAgents
cp $(brew --prefix)/opt/rustchain-miner/homebrew.mxcl.rustchain-miner.plist ~/Library/LaunchAgents/

# Edit the plist to add your wallet ID
nano ~/Library/LaunchAgents/homebrew.mxcl.rustchain-miner.plist

# Load the service
launchctl load ~/Library/LaunchAgents/homebrew.mxcl.rustchain-miner.plist

# Verify it's running
launchctl list | grep rustchain
```

---

## Testing

### Post-Installation Test

```bash
# Verify installation
brew test rustchain-miner

# Verify miner connectivity
rustchain-miner --help

# Test node connectivity (manual)
python3 -c "
import requests
try:
    r = requests.get('https://rustchain.org/health', verify=False, timeout=5)
    print('Node: ONLINE' if r.status_code == 200 else 'Node: OFFLINE')
except Exception as e:
    print(f'Error: {e}')
"
```

### Formula Validation (For Maintainers)

```bash
# Audit formula for issues
brew audit --strict rustchain-miner

# Check formula style
brew style rustchain-miner

# Run formula tests
brew test rustchain-miner

# Verify checksums (before release)
curl -sSL https://github.com/Scottcjn/Rustchain/archive/refs/tags/v2.5.0.tar.gz | sha256sum
```

---

## Uninstallation

```bash
# Stop any running services
brew services stop rustchain-miner

# Unload launchd service (if manually installed)
launchctl unload ~/Library/LaunchAgents/homebrew.mxcl.rustchain-miner.plist 2>/dev/null || true

# Remove formula
brew uninstall rustchain-miner

# Remove tap (optional)
brew untap rustchain-bounties/rustchain-bounties

# Clean up residual files (optional)
rm -rf ~/.rustchain
rm -f ~/Library/LaunchAgents/homebrew.mxcl.rustchain-miner.plist
```

---

## Practical Caveats

### ⚠️ Security

| Concern | Mitigation |
|---------|------------|
| Wallet ID exposure | Never share your wallet ID; it's your payout address |
| Network traffic | Miner uses HTTPS with TLS verification disabled (common in mining) |
| Privilege escalation | Miner runs as your user; no root/sudo required |
| Code integrity | Formula uses SHA256 checksums; verify before production use |

### ⚠️ Performance

| Hardware | Multiplier | Notes |
|----------|------------|-------|
| PowerPC G4 | 2.5x | Native C miner in `miners/ppc/` recommended |
| PowerPC G5 | 2.0x | Native C miner in `miners/ppc/` recommended |
| Apple Silicon (M1/M2/M3) | 0.8x | This Python miner works fine |
| Intel Mac | 0.8x | This Python miner works fine |

### ⚠️ Network

- **Firewall**: Allow outbound connections to `rustchain.org:443`
- **Proxy**: Auto-discovers proxy on LAN (192.168.0.160:8089) for legacy TLS fallback
- **Sleep/Wake**: Miner re-attests automatically after system wake

### ⚠️ Production Deployment

1. **Checksum Verification**: Before deploying, compute and update the SHA256 in the formula:
   ```bash
   curl -sSL https://github.com/Scottcjn/Rustchain/archive/refs/tags/v2.5.0.tar.gz | sha256sum
   ```

2. **Version Pinning**: For production, pin to a specific version:
   ```ruby
   url "https://github.com/Scottcjn/Rustchain/archive/refs/tags/v2.5.0.tar.gz"
   version "2.5.0"
   ```

3. **Monitoring**: Set up log monitoring for miner health:
   ```bash
   # Tail miner logs (if using launchd)
   tail -f ~/Library/Logs/homebrew.mxcl.rustchain-miner.log
   ```

4. **Resource Limits**: Consider setting CPU/memory limits in launchd plist for shared systems.

### ⚠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| `requests` module not found | Run `pip3 install requests --user` |
| Connection refused | Check firewall; verify `rustchain.org` is reachable |
| Miner exits immediately | Run with `--help` to verify args; check wallet ID format |
| launchd fails to load | Check plist syntax; ensure paths are absolute |
| Checksum mismatch | Update SHA256 in formula; verify archive URL |

---

## Formula Maintenance

### Updating the Formula

```bash
# 1. Download new release archive
curl -sSL https://github.com/Scottcjn/Rustchain/archive/refs/tags/vX.Y.Z.tar.gz -o release.tar.gz

# 2. Compute new SHA256
sha256sum release.tar.gz

# 3. Update formula with new version and checksum
# Edit homebrew/rustchain-miner.rb

# 4. Test locally
brew install ./homebrew/rustchain-miner.rb
brew test rustchain-miner

# 5. Commit (do NOT push without approval)
git add homebrew/rustchain-miner.rb
git commit -m "feat(homebrew): update rustchain-miner to vX.Y.Z"
```

### Formula Structure

```
homebrew/
└── rustchain-miner.rb    # Homebrew formula
miners/
├── macos/
│   ├── rustchain_mac_miner_v2.5.py  # Main miner script
│   ├── color_logs.py     # Color output helper
│   └── requirements-miner.txt  # Python dependencies
└── fingerprint_checks.py # Hardware attestation
```

---

## References

- [Homebrew Formula Cookbook](https://docs.brew.sh/Formula-Cookbook)
- [RustChain Repository](https://github.com/Scottcjn/Rustchain)
- [RustChain Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)
- [Issue #1612](https://github.com/rustchain-bounties/rustchain-bounties/issues/1612)

---

*Last updated: March 2026 | Formula version: 2.5.0*
