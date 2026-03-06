# RustChain CLI

Command-line network inspector for RustChain. Like `bitcoin-cli` but for RustChain.

## Quick Start

```bash
# Run directly
python3 rustchain_cli.py status
python3 rustchain_cli.py miners
python3 rustchain_cli.py balance --all

# Or make it executable
chmod +x rustchain_cli.py
./rustchain_cli.py status
```

## Commands

### Node Status
```bash
rustchain-cli status
```

Show node health, version, uptime, and database status.

### Miners
```bash
rustchain-cli miners           # List active miners (top 20)
rustchain-cli miners --count   # Show total count only
```

### Balance
```bash
rustchain-cli balance <miner_id>   # Check specific miner balance
rustchain-cli balance --all        # Show top 10 balances
```

### Epoch
```bash
rustchain-cli epoch            # Current epoch info
rustchain-cli epoch --history  # Epoch history (coming soon)
```

### Hall of Fame
```bash
rustchain-cli hall                     # Top 5 machines
rustchain-cli hall --category exotic   # Exotic architectures only
```

### Fee Pool
```bash
rustchain-cli fees   # RIP-301 fee pool statistics
```

## Options

| Option | Description |
|--------|-------------|
| `--node URL` | Override node URL (default: https://rustchain.org) |
| `--json` | Output as JSON for scripting |
| `--no-color` | Disable color output |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `RUSTCHAIN_NODE` | Override default node URL |

## Examples

### JSON Output for Scripting
```bash
# Get miner count as JSON
rustchain-cli miners --count --json
# Output: {"count": 22}

# Get full status as JSON
rustchain-cli status --json
```

### Custom Node
```bash
rustchain-cli status --node https://testnet.rustchain.org
```

### Check Your Balance
```bash
rustchain-cli balance your-miner-id-here
```

## API Endpoints Used

- `/health` - Node health check
- `/epoch` - Current epoch information
- `/api/miners` - List of active miners
- `/balance/<miner_id>` - Wallet balance
- `/api/hall_of_fame` - Hall of Fame leaderboard
- `/api/fee_pool` - Fee pool statistics

## Requirements

- Python 3.8+
- No external dependencies (uses only stdlib)

## License

MIT - Same as RustChain
