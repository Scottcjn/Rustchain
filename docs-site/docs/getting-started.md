# Getting Started

This guide walks you through installing the RustChain miner, creating a wallet, and earning your first RTC.

---

## Prerequisites

- **Python 3.8+** (3.10+ recommended)
- **curl** (for installation and API access)
- A machine running Linux, macOS, or Windows
- Network access to `https://rustchain.org`

---

## One-Line Install (Recommended)

The fastest way to get mining:

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

The installer automatically:

- Detects your platform (Linux/macOS, x86_64/ARM/PowerPC)
- Creates an isolated Python virtualenv (no system pollution)
- Downloads the correct miner for your hardware
- Sets up auto-start on boot (systemd/launchd)
- Provides easy uninstall

### Install with a Specific Wallet

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner-wallet
```

### Dry Run (Preview Only)

```bash
bash install-miner.sh --dry-run --wallet YOUR_WALLET_NAME
```

### Uninstall

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

---

## Manual Install

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
bash install-miner.sh --wallet YOUR_WALLET_NAME
```

---

## Windows Install

```powershell
pip install clawrtc
clawrtc --wallet YOUR_NAME
```

Verify hardware detection works:

```powershell
clawrtc mine --dry-run
```

---

## Supported Platforms

| Platform | Architecture | Status | Notes |
|----------|--------------|--------|-------|
| Mac OS X Tiger | PowerPC G4/G5 | Full Support | Python 2.5 compatible miner |
| Mac OS X Leopard | PowerPC G4/G5 | Full Support | Recommended for vintage Macs |
| Ubuntu Linux | ppc64le/POWER8 | Full Support | Best performance |
| Ubuntu Linux | x86_64 | Full Support | Standard miner |
| macOS Sonoma+ | Apple Silicon | Full Support | M1/M2/M3/M4 chips |
| Windows 10/11 | x86_64 | Full Support | Python 3.8+ required |
| DOS | 8086/286/386 | Experimental | Badge rewards only |

---

## After Installation

### Check Node Health

```bash
curl -sk https://rustchain.org/health
```

### Check Your Wallet Balance

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

### List Active Miners

```bash
curl -sk https://rustchain.org/api/miners
```

### Get Current Epoch

```bash
curl -sk https://rustchain.org/epoch
```

---

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

---

## ARM64 Validation (Raspberry Pi 4/5)

```bash
pip install clawrtc
clawrtc mine --dry-run
```

All 6 hardware fingerprint checks should execute on native ARM64 without architecture fallback errors.

---

## Docker Install

Pull and run the miner container:

```bash
docker-compose -f docker-compose.miner.yml up -d
```

Or build from the provided Dockerfile:

```bash
docker build -f Dockerfile.miner -t rustchain-miner .
docker run -d --name miner rustchain-miner
```

See [DOCKER_DEPLOYMENT.md](https://github.com/Scottcjn/Rustchain/blob/main/DOCKER_DEPLOYMENT.md) for full Docker configuration options.

---

## Troubleshooting

!!! warning "Installer fails with permission errors"
    Re-run using an account with write access to `~/.local` and avoid running inside a system Python's global site-packages.

!!! warning "Python version errors (SyntaxError / ModuleNotFoundError)"
    Install with Python 3.10+ and set `python3` to that interpreter:
    ```bash
    python3 --version
    curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
    ```

!!! warning "Wallet shows 'could not reach network'"
    Verify the live node directly:
    ```bash
    curl -sk https://rustchain.org/health
    curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
    ```

!!! warning "HTTPS certificate errors"
    The node may use a self-signed certificate. Use the `-sk` flags with curl:
    ```bash
    curl -I https://rustchain.org
    ```

!!! warning "Miner exits immediately"
    Verify wallet exists and service is running:
    ```bash
    # Linux
    systemctl --user status rustchain-miner
    # macOS
    launchctl list | grep rustchain
    ```

If an issue persists, include logs and OS details in a [new issue](https://github.com/Scottcjn/Rustchain/issues) with exact error output and your `install-miner.sh --dry-run` result.

---

## Next Steps

- Read the [Mining Guide](mining.md) for hardware multipliers and reward mechanics
- Explore the [API Reference](api-reference.md) to integrate with RustChain
- Check [open bounties](https://github.com/Scottcjn/rustchain-bounties/issues) and start earning RTC for contributions
