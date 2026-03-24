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

---

## Agent Economy Commands (New in v0.2.0)

### ⚠️ Write Commands Require `--dry-run`

**Important:** This CLI is **read-only**. Write commands (`wallet create`, `agent register`, `bounty claim`, `x402 pay`) require the `--dry-run` flag for local simulation.

- **Without `--dry-run`**: Returns error with exit code 1 (no server call made)
- **With `--dry-run`**: Simulates locally with clear "SIMULATION ONLY" warnings

### Wallet Management
```bash
# Create a new wallet (SIMULATION ONLY - requires --dry-run)
rustchain-cli wallet create "My Wallet" --dry-run
rustchain-cli wallet create "BotAgent" --agent --dry-run

# Check wallet balance (read-only, no --dry-run needed)
rustchain-cli wallet balance rtc_mywallet_abc123
rustchain-cli wallet balance  # Uses RUSTCHAIN_WALLET env var

# List all wallets (read-only, no --dry-run needed)
rustchain-cli wallet list
```

### AI Agent Management
```bash
# List all registered agents (read-only)
rustchain-cli agent list

# Get agent details (read-only)
rustchain-cli agent info agent_abc123

# Register a new agent (SIMULATION ONLY - requires --dry-run)
rustchain-cli agent register "VideoBot" --wallet rtc_mywallet_abc123 --type bot --dry-run
rustchain-cli agent register "OracleService" --type oracle --dry-run
```

### Bounty System
```bash
# List available bounties (read-only)
rustchain-cli bounty list
rustchain-cli bounty list --status open

# Get bounty details (read-only)
rustchain-cli bounty info 42

# Claim a bounty (SIMULATION ONLY - requires --dry-run)
rustchain-cli bounty claim 42 --wallet rtc_mywallet_abc123 --dry-run
```

### x402 Protocol Payments
```bash
# Send machine-to-machine payment (SIMULATION ONLY - requires --dry-run)
rustchain-cli x402 pay rtc_recipient_xyz 10.5 --dry-run
rustchain-cli x402 pay agent_abc123 5.0 --wallet rtc_sender_123 --dry-run

# View payment history (read-only)
rustchain-cli x402 history
rustchain-cli x402 history --wallet rtc_mywallet_abc123

# Enable x402 for a wallet (read-only info)
rustchain-cli x402 enable --wallet rtc_mywallet_abc123 --dry-run
```

---

## Options

| Option | Description |
|--------|-------------|
| `--node URL` | Override node URL (default: https://rustchain.org) |
| `--json` | Output as JSON for scripting |
| `--no-color` | Disable color output |
| `--version` | Show version information |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `RUSTCHAIN_NODE` | Override default node URL |
| `RUSTCHAIN_WALLET` | Default wallet address for transactions |

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

### Create Agent Wallet
```bash
rustchain-cli wallet create "TradingBot" --agent --dry-run
```

### Register AI Agent
```bash
export RUSTCHAIN_WALLET=rtc_mywallet_abc123
rustchain-cli agent register "AnalysisBot" --type bot --dry-run
```

### Send x402 Payment
```bash
rustchain-cli x402 pay rtc_service_xyz 25.0 --dry-run
```

### Claim Bounty
```bash
rustchain-cli bounty claim 15 --wallet rtc_mywallet_abc123 --dry-run
```

## Verification Steps

### Quick Verification
```bash
# 1. Check CLI version
rustchain-cli --version

# 2. Test basic commands
rustchain-cli status --json | head -5
rustchain-cli miners --count

# 3. Test Agent Economy commands (dry-run mode required for write operations)
rustchain-cli wallet --json create "TestWallet" --dry-run
rustchain-cli agent --json register "TestAgent" --type service --wallet rtc_test_123 --dry-run
rustchain-cli x402 --json pay rtc_test 1.0 --wallet rtc_test_123 --dry-run

# 4. Test that write commands fail without --dry-run (exit code 1)
rustchain-cli wallet create "TestWallet"; echo "Exit code: $?"
```

### Full Integration Test
```bash
# 1. Create wallet and capture address (SIMULATION ONLY)
WALLET_JSON=$(rustchain-cli wallet --json create "IntegrationTest" --dry-run)
WALLET_ADDR=$(echo "$WALLET_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['address'])")

# 2. Register agent with that wallet (SIMULATION ONLY)
rustchain-cli agent --json register "IntegrationBot" --wallet "$WALLET_ADDR" --type bot --dry-run

# 3. Enable x402 payments (SIMULATION ONLY)
rustchain-cli x402 --json enable --wallet "$WALLET_ADDR" --dry-run

# 4. List bounties (may fail if node doesn't have endpoint)
rustchain-cli bounty --json list 2>&1 | head -20 || echo "Bounty endpoint not available"

echo "✓ All Agent Economy CLI commands working (write commands in --dry-run mode)"
```

## API Endpoints Used

### Core Endpoints
- `/health` - Node health check
- `/epoch` - Current epoch information
- `/api/miners` - List of active miners
- `/balance/<miner_id>` - Wallet balance
- `/api/hall_of_fame` - Hall of Fame leaderboard
- `/api/fee_pool` - Fee pool statistics

### Agent Economy Endpoints (New)
- `/api/wallets` - List all wallets
- `/api/wallet/<address>` - Get wallet details
- `/api/agents` - List registered AI agents
- `/api/agent/<agent_id>` - Get agent information
- `/api/bounties` - List available bounties
- `/api/bounty/<id>` - Get bounty details
- `/api/wallet/<address>/x402-history` - Payment history

## Requirements

- Python 3.8+
- No external dependencies (uses only stdlib)

## Version History

- **v0.2.0** - Added Agent Economy commands (wallet, agent, bounty, x402)
- **v0.1.0** - Initial release with basic network inspection

## License

MIT - Same as RustChain
