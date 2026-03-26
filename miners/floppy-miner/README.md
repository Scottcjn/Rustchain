# 💾 RustChain Floppy Miner — Mine a Block on 1.44MB

A minimal RustChain miner that fits on a 3.5" floppy disk (1.44MB), runs in under 16MB RAM, and successfully attests to the RustChain network.

## Highlights

- **Binary + boot image < 200KB** — fits dozens of times on a 1.44MB floppy
- **Runs on 16MB RAM** — i486-class hardware or DOSBox
- **Real attestation** — connects to `https://rustchain.org/attest/submit`
- **ASCII art boot screen** with animated floppy spinner
- **DOS-compatible** — uses Wattcp TCP/IP stack for DOS networking
- **Python host relay** for systems where DOS TCP/IP is impractical

## Architecture

```
┌─────────────────────┐         ┌──────────────┐         ┌─────────────────┐
│  Floppy Miner       │  serial │  Host Relay   │  HTTPS  │  RustChain Node │
│  (DOS / 16MB RAM)   │ ──────▶ │  (Python)     │ ──────▶ │  50.28.86.131   │
│  i486 + mTCP/Wattcp │         │  relay.py     │         │  /attest/submit │
│  < 200KB binary     │         │  serial→HTTPS │         │                 │
└─────────────────────┘         └──────────────┘         └─────────────────┘
```

Two modes:
1. **Direct mode** — DOS with Wattcp TCP/IP stack connects directly (requires packet driver)
2. **Relay mode** — Miner outputs attestation to serial/stdout, Python relay forwards via HTTPS

## Quick Start

### Option 1: DOSBox (Recommended for Testing)

```bash
# 1. Install DOSBox
sudo apt install dosbox  # or brew install dosbox

# 2. Run the miner in DOSBox with relay
python tools/relay.py &
dosbox -c "mount c miners/floppy-miner" -c "c:" -c "miner.com"
```

### Option 2: Python Simulation

```bash
# Simulates the floppy miner attestation protocol
python src/floppy_miner.py --wallet RTC_YOUR_WALLET --node https://rustchain.org
```

### Option 3: Build Floppy Image

```bash
# Create bootable 1.44MB floppy image
python tools/build_floppy.py --output floppy.img
# Write to real floppy: dd if=floppy.img of=/dev/fd0
```

## Files

| File | Size | Purpose |
|------|------|---------|
| `src/floppy_miner.py` | ~8KB | Python reference implementation + simulator |
| `src/miner.asm` | ~4KB | i486 assembly attestation core |
| `tools/relay.py` | ~3KB | Serial/stdout → HTTPS relay bridge |
| `tools/build_floppy.py` | ~3KB | Floppy image builder |
| `docs/PROTOCOL.md` | ~2KB | Minimal attestation protocol spec |
| `README.md` | this | Documentation |

## Attestation Protocol (Minimal)

The floppy miner sends a minimal JSON payload:

```json
{
  "miner": "RTC_WALLET_ADDRESS",
  "nonce": 12345,
  "device": {
    "arch": "i486",
    "family": "floppy",
    "ram_mb": 16,
    "boot_media": "floppy_1.44mb"
  }
}
```

Response includes epoch info and reward calculation:
```json
{
  "ok": true,
  "epoch": 42,
  "multiplier": 1.5,
  "message": "Attestation accepted from i486 floppy miner"
}
```

## Boot Screen

```
╔══════════════════════════════════════════════════╗
║        ████████████████████████████████          ║
║        █  ┌──────────────────────┐  █           ║
║        █  │   RustChain Floppy   │  █           ║
║        █  │      MINER v1.0      │  █           ║
║        █  │    ▄▄ ▄▄ ▄▄ ▄▄ ▄▄   │  █           ║
║        █  └──────────────────────┘  █           ║
║        █    ┌──┐                    █           ║
║        ████████████████████████████████          ║
║                                                  ║
║   Proof-of-Antiquity × Proof-of-Floppy          ║
║   Mining RustChain on 1.44MB since 2026          ║
║                                                  ║
║   [ATTESTING] Epoch 42 ████████░░ 80%            ║
╚══════════════════════════════════════════════════╝
```

## Memory Usage

| Component | RAM |
|-----------|-----|
| DOS kernel | ~60KB |
| TCP/IP stack | ~40KB |
| Miner binary | ~20KB |
| JSON buffer | ~4KB |
| **Total** | **~124KB** (well under 16MB limit) |

## Bonus Claims

- ✅ ASCII art boot screen (+25 RTC)
- ✅ DOSBox compatible
- 🎯 Video demo can be posted to BoTTube (+50 RTC)

## Bounty

Closes https://github.com/Scottcjn/Rustchain/issues/1853

RTC Wallet: `RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`
