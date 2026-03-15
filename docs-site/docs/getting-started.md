# Getting Started

This guide walks you through installing the RustChain miner, creating a wallet, and verifying your first attestation.

## Requirements

- Python 3.6+ (Python 2.5+ for vintage PowerPC systems)
- `curl` or `wget`
- 50 MB disk space
- Internet connection

### Platform-Specific

- **Linux**: systemd (for auto-start), `python3-venv` or `virtualenv`
- **macOS**: Command Line Tools (installed automatically if needed)

## One-Line Install

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

The installer will:

1. Auto-detect your platform (Linux/macOS, x86_64/ARM/PowerPC)
2. Create an isolated Python virtualenv at `~/.rustchain/venv`
3. Download the correct miner for your hardware
4. Set up auto-start on boot (systemd or launchd)
5. Prompt for your wallet name (or auto-generate one)

### Install with a Specific Wallet

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-wallet-name
```

### Preview Without Installing

```bash
bash install-miner.sh --dry-run --wallet my-wallet-name
```

### Uninstall

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

## Manual Install

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
bash install-miner.sh --wallet YOUR_WALLET_NAME
```

## Supported Platforms

### Linux

| Distribution | Versions |
|---|---|
| Ubuntu | 20.04, 22.04, 24.04 |
| Debian | 11, 12 |
| Fedora | 38, 39, 40 |
| RHEL | 8, 9 |

Architectures: x86_64, ppc64le, ppc (PowerPC 32-bit)

### macOS

macOS 12 (Monterey) and later. Architectures: arm64 (Apple Silicon), x86_64 (Intel), powerpc (G3/G4/G5).

### Special Hardware

IBM POWER8 systems, PowerPC G4/G5 Macs, vintage x86 CPUs (Pentium 4, Core 2 Duo, etc.)

## Verify Your Setup

After installation, confirm the miner is running and connected:

```bash
# Check node health
curl -sk https://rustchain.org/health

# Check your wallet balance
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"

# List active miners
curl -sk https://rustchain.org/api/miners

# Get current epoch
curl -sk https://rustchain.org/epoch
```

## Managing the Miner Service

=== "Linux (systemd)"

    ```bash
    systemctl --user status rustchain-miner    # Check status
    systemctl --user stop rustchain-miner      # Stop mining
    systemctl --user start rustchain-miner     # Start mining
    journalctl --user -u rustchain-miner -f    # View logs
    ```

=== "macOS (launchd)"

    ```bash
    launchctl list | grep rustchain            # Check status
    launchctl stop com.rustchain.miner         # Stop mining
    launchctl start com.rustchain.miner        # Start mining
    tail -f ~/.rustchain/miner.log             # View logs
    ```

## Windows (via pip)

```powershell
pip install clawrtc
clawrtc mine --dry-run
```

## Directory Structure

After installation, the miner lives at `~/.rustchain/`:

```
~/.rustchain/
├── venv/                    # Isolated Python virtualenv
│   └── bin/python           # Virtualenv Python interpreter
├── miner.py                 # Miner script for your platform
├── miner.log                # Runtime logs
└── config.json              # Wallet and node configuration
```

## Troubleshooting

**Installer fails with permission errors**
:   Re-run using an account with write access to `~/.local`. Avoid running inside a system Python's global site-packages.

**Python version errors (`SyntaxError` / `ModuleNotFoundError`)**
:   Install Python 3.10+ and ensure `python3` points to that interpreter.

**`clawrtc wallet show` says "could not reach network"**
:   Verify the live node directly: `curl -sk https://rustchain.org/health`

**HTTPS certificate errors in `curl`**
:   The node may use a self-signed certificate. Use `curl -sk` (silent + insecure) for API calls.

**Miner exits immediately**
:   Verify your wallet exists and the service is running (`systemctl --user status rustchain-miner` or `launchctl list | grep rustchain`).

If an issue persists, open an issue on GitHub with logs, OS details, and the output of `install-miner.sh --dry-run`.

## Next Steps

- Read the [Mining Guide](mining.md) to understand reward mechanics and hardware multipliers
- Explore the [API Reference](api-reference.md) for programmatic access
- Check [open bounties](https://github.com/Scottcjn/rustchain-bounties/issues) to earn RTC by contributing
