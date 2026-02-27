# ARM64 Linux Miner Port (Raspberry Pi / ARM Servers)

This document validates RustChain Linux miner support on ARM64 (`aarch64`) hosts.

## What changed

- Linux miner now auto-detects architecture family from `platform.machine()`.
- ARM64 hosts are classified as:
  - `device.family = arm`
  - `device.arch = arm64`
- `miner_id` no longer hardcodes `ryzen5-*`; it now uses `<family>-<hostname>`.
- Model metadata uses detected CPU string instead of fixed Ryzen text.

## Quick setup (ARM64 Linux)

```bash
sudo apt update
sudo apt install -y python3 python3-pip
cd miners/linux
python3 rustchain_linux_miner.py --wallet YOUR_WALLET_ID
```

## Expected runtime signals

- Startup prints `Host Arch: aarch64`
- Attestation payload sends:
  - `device.family = arm`
  - `device.arch = arm64`
- Enrollment succeeds against `https://50.28.86.131`

## Notes

- Generic ARM hardware earns low multiplier by design (anti-sybil economics).
- This port focuses on compatibility and correct attestation metadata.
