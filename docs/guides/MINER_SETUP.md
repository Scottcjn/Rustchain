# Miner Setup Guide

Step-by-step guide to set up the RustChain miner on any platform.

## Quick Start (All Platforms)

```bash
pip install clawrtc
clawrtc mine --wallet YOUR_WALLET_NAME --dry-run  # Test first
clawrtc mine --wallet YOUR_WALLET_NAME            # Start mining
```

## Linux

```bash
# One-line install
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash

# With custom wallet
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner

# Manage with systemd
systemctl --user status rustchain-miner
journalctl --user -u rustchain-miner -f

# Logs
tail -f ~/.rustchain/miner.log
```

## macOS

```bash
# One-line install
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash

# Manage with launchd
launchctl list | grep rustchain
tail -f ~/.rustchain/miner.log
```

## Windows

```bash
pip install clawrtc
clawrtc mine --wallet YOUR_WALLET_NAME
```

The miner runs as a scheduled task or background process.

## Raspberry Pi / ARM

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

ARM devices earn a 1.4x exotic multiplier. Ensure Python 3.8+ is installed.

## Check Your Balance

```bash
curl "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

## Verify You're Mining

```bash
curl -s https://50.28.86.131/api/miners | python3 -m json.tool | grep YOUR_WALLET_NAME
```

## Hardware Multipliers

| Architecture | Example | Multiplier |
|-------------|---------|------------|
| DEC VAX | VAX-11/780 (1977) | 3.5x |
| Acorn ARM | ARM2 (1987) | 4.0x |
| Motorola 68000 | Amiga, Atari ST | 3.0x |
| Sun SPARC | SPARCstation (1987) | 2.9x |
| SGI MIPS | R4000 (1991) | 2.7x |
| PowerPC G4 | PowerBook G4 (2003) | 2.5x |
| Cell BE | PS3 (2006) | 2.2x |
| RISC-V | (2014+) | 1.4x |
| Apple Silicon | M1 (2020) | 1.2x |
| x86_64 | Modern PC | 1.0x |

## Troubleshooting

**Miner not attesting:** Check `curl https://50.28.86.131/health` - node may be down.

**VM/emulator detected:** Run on real hardware. VMs get 1 billionth rewards.

**SSL errors:** Use the `--verify-ssl false` flag or equivalent.
