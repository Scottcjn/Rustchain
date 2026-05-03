# rustchainnode

> **pip-installable RustChain attestation node** — one command to start mining.

```bash
pip install rustchainnode
rustchainnode init --wallet my-wallet-name
rustchainnode start
```

## Features

- 🚀 **One-command install** — `pip install rustchainnode`
- 🔧 **Auto-configuration** — detects CPU architecture, thread count, antiquity multiplier
- 🖥️ **Dashboard** — `rustchainnode dashboard` shows TUI with epoch, miners, balance
- ⚙️ **Service install** — `rustchainnode install-service` generates systemd (Linux) or launchd (macOS)
- 🌐 **Cross-platform** — Linux x86_64, aarch64, macOS (x86/Apple Silicon), PowerPC
- 🧪 **Testnet support** — `--testnet` flag for local development

## Quick Start

```bash
# Install
pip install rustchainnode

# Initialize (auto-detects your hardware)
rustchainnode init --wallet your-wallet-name

# Start
rustchainnode start

# Check status
rustchainnode status

# TUI dashboard
rustchainnode dashboard
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `rustchainnode init --wallet <name>` | Initialize config + hardware detection |
| `rustchainnode start` | Start the attestation node |
| `rustchainnode stop` | Stop a running daemon |
| `rustchainnode status` | Node status + epoch info |
| `rustchainnode config` | Show current configuration |
| `rustchainnode dashboard` | TUI health dashboard |
| `rustchainnode install-service` | Install systemd/launchd service |

### Options

```
init:
  --wallet NAME    RTC wallet name
  --port PORT      Local port (default: 8099)
  --testnet        Use local testnet

start:
  --wallet NAME    Override wallet
  --port PORT      Override port
  --testnet        Use local testnet

install-service:
  --wallet NAME    Wallet for service config
```

## Programmatic API

```python
from rustchainnode import RustChainNode

# Create a node instance
node = RustChainNode(wallet="my-wallet", port=8099)
node.start()

# Check status
print(node.health())   # {"ok": true, "version": "2.2.1-rip200", ...}
print(node.epoch())    # {"epoch": 94, "slot": 13580, ...}
print(node.config())   # {"wallet": "my-wallet", "arch_type": "modern_x86", ...}

# Stop
node.stop()
```

## Auto-Configuration

`rustchainnode init` automatically detects your hardware:

| Architecture | Antiquity Multiplier |
|--------------|---------------------|
| PowerPC (G4/G5) | 2.5x |
| PowerPC 64-bit | 2.0x |
| x86 32-bit | 1.5x |
| ARM64 / x86_64 | 1.0x |

Vintage hardware earns more RTC per epoch!

## Service Installation

### Linux (systemd)

```bash
rustchainnode install-service --wallet my-wallet
systemctl --user daemon-reload
systemctl --user enable rustchainnode
systemctl --user start rustchainnode
```

### macOS (launchd)

```bash
rustchainnode install-service --wallet my-wallet
launchctl load ~/Library/LaunchAgents/ai.elyan.rustchainnode.plist
```

## Configuration

Config is stored at `~/.rustchainnode/config.json`:

```json
{
  "wallet": "my-wallet",
  "port": 8099,
  "threads": 4,
  "arch_type": "modern_x86",
  "antiquity_multiplier": 1.0,
  "node_url": "https://rustchain.org",
  "testnet": false,
  "auto_configured": true
}
```

## Cross-Platform Support

- ✅ Linux x86_64
- ✅ Linux aarch64 (ARM64)
- ✅ Linux ppc64 / ppc64le (PowerPC)
- ✅ macOS x86_64
- ✅ macOS arm64 (Apple Silicon M1/M2)
- ✅ Python 3.9+

## License

MIT — © Elyan Labs
