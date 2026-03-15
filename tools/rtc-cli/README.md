# rtc — Unified RustChain CLI

A comprehensive command-line tool that combines all RustChain node operations into a single interface. Think `bitcoin-cli` but for RustChain.

## Installation

```bash
# Clone and navigate
cd tools/rtc-cli

# Install optional dependencies (for wallet create/send)
pip install mnemonic cryptography

# Make executable (Linux/macOS)
chmod +x rtc.py

# Run
python rtc.py status
```

## Commands

### `rtc status`
Full node health dashboard — health check, epoch info, network stats, chain tip, and active miner count.

```bash
python rtc.py status
python rtc.py status --json
python rtc.py status --node https://50.28.86.131
```

### `rtc wallet`
Wallet management with Ed25519 key derivation, encrypted keystores, and signed transfers.

```bash
# Create a new 24-word mnemonic wallet
python rtc.py wallet create --name my-wallet

# Check balance
python rtc.py wallet balance Ivan-houzhiwen

# Send RTC (requires local keystore)
python rtc.py wallet send RTCrecipient123 10.0 --from my-wallet --memo "payment"

# Transaction history
python rtc.py wallet history Ivan-houzhiwen --limit 20
```

### `rtc blocks`
Block and chain inspection.

```bash
# List recent blocks / chain tip
python rtc.py blocks list

# Get block/epoch details by slot number
python rtc.py blocks get 95
```

### `rtc miners`
Query active miners and their attestation details.

```bash
# List all active miners with hardware type and multiplier
python rtc.py miners list

# Detailed info for a specific miner
python rtc.py miners info Ivan-houzhiwen
```

### `rtc config`
Configuration validation.

```bash
python rtc.py config validate
```

### `rtc backup`
Backup and restore local wallets and configuration.

```bash
# Create backup archive
python rtc.py backup create
python rtc.py backup create --output /path/to/backup

# Restore from backup
python rtc.py backup restore rtc-backup-20250101_120000.tar.gz
```

## Configuration

Create `~/.rtc/config.yaml` to persist settings:

```yaml
# RustChain CLI configuration
node_url: https://rustchain.org
verify_ssl: false
# wallet_dir: ~/.rtc/wallets
# backup_dir: ~/.rtc/backups
```

### Node URL Resolution Order
1. `--node` CLI flag
2. `RUSTCHAIN_NODE_URL` or `RUSTCHAIN_NODE` environment variable
3. `node_url` in `~/.rtc/config.yaml`
4. Auto-discover from default node list

## Environment Variables

| Variable | Description |
|----------|-------------|
| `RUSTCHAIN_NODE_URL` | Override node URL |
| `RUSTCHAIN_NODE` | Alternative env var for node URL |
| `RUSTCHAIN_VERIFY_SSL` | Set to `1` to enable SSL verification |
| `RUSTCHAIN_WALLET_PASSWORD` | Wallet password (avoid in production) |
| `NO_COLOR` | Disable colored output |

## Features

- **Zero mandatory dependencies** — stdlib-only for read operations (`status`, `blocks`, `miners`)
- **Colored output** — ANSI colors with Windows 10+ support, respects `NO_COLOR`
- **Auto-discovery** — probes default nodes to find a reachable endpoint
- **Config file** — persistent settings in `~/.rtc/config.yaml`
- **Encrypted keystores** — AES-256-GCM with PBKDF2 key derivation
- **Backup/restore** — archive wallets and config as `.tar.gz` or `.zip`
- **JSON mode** — `--json` flag for machine-readable output on any command

## File Structure

```
~/.rtc/
├── config.yaml          # CLI configuration
├── wallets/             # Encrypted keystore files
│   ├── my-wallet.json
│   └── ...
└── backups/             # Backup archives
    └── rtc-backup-*.tar.gz
```

## API Endpoints Used

| Endpoint | Command |
|----------|---------|
| `GET /health` | `status` |
| `GET /epoch` | `status`, `blocks list` |
| `GET /api/stats` | `status` |
| `GET /headers/tip` | `status`, `blocks list/get` |
| `GET /api/miners` | `status`, `miners list/info` |
| `GET /wallet/balance` | `wallet balance`, `miners info` |
| `GET /wallet/history` | `wallet history` |
| `GET /wallet/ledger` | `wallet history` (fallback) |
| `POST /wallet/transfer/signed` | `wallet send` |
| `GET /rewards/epoch/<n>` | `blocks get` |
