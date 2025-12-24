# RustChain Miners

## Directory Structure
- `linux/` - Linux x86_64 miners with fingerprint attestation
- `macos/` - macOS miners for Apple Silicon and Intel
- `windows/` - Windows miners
- `ppc/` - PowerPC miners for G4/G5 Macs (legacy hardware bonus)

## Version 2.4.0 Features
- Hardware serial binding (v2)
- 6-point fingerprint attestation
- Anti-emulation checks
- Auto-recovery via systemd/launchd

## Quick Start
```bash
# Linux
python3 rustchain_linux_miner.py

# macOS
python3 rustchain_mac_miner_v2.4.py

# Windows
python rustchain_windows_miner.py
```
