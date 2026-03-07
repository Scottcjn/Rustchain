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

### Wallet Management
```bash
# Create a new wallet
rustchain-cli wallet create "My Wallet"
rustchain-cli wallet create "BotAgent" --agent

# Check wallet balance
rustchain-cli wallet balance rtc_mywallet_abc123
rustchain-cli wallet balance  # Uses RUSTCHAIN_WALLET env var

# List all wallets
rustchain-cli wallet list
```

### AI Agent Management
```bash
# List all registered agents
rustchain-cli agent list

# Get agent details
rustchain-cli agent info agent_abc123

# Register a new agent
rustchain-cli agent register "VideoBot" --wallet rtc_mywallet_abc123 --type bot
rustchain-cli agent register "OracleService" --type oracle
```

### Bounty System
```bash
# List available bounties
rustchain-cli bounty list
rustchain-cli bounty list --status open

# Get bounty details
rustchain-cli bounty info 42

# Claim a bounty
rustchain-cli bounty claim 42 --wallet rtc_mywallet_abc123
```

### x402 Protocol Payments
```bash
# Send machine-to-machine payment
rustchain-cli x402 pay rtc_recipient_xyz 10.5
rustchain-cli x402 pay agent_abc123 5.0 --wallet rtc_sender_123

# View payment history
rustchain-cli x402 history
rustchain-cli x402 history --wallet rtc_mywallet_abc123

# Enable x402 for a wallet
rustchain-cli x402 enable --wallet rtc_mywallet_abc123
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
rustchain-cli wallet create "TradingBot" --agent
```

### Register AI Agent
```bash
export RUSTCHAIN_WALLET=rtc_mywallet_abc123
rustchain-cli agent register "AnalysisBot" --type bot
```

### Send x402 Payment
```bash
rustchain-cli x402 pay rtc_service_xyz 25.0
```

### Claim Bounty
```bash
rustchain-cli bounty claim 15 --wallet rtc_mywallet_abc123
```

## Verification Steps

### Quick Verification
```bash
# 1. Check CLI version
rustchain-cli --version

# 2. Test basic commands
rustchain-cli status --json | head -5
rustchain-cli miners --count

# 3. Test Agent Economy commands (dry-run mode)
rustchain-cli wallet --json create "TestWallet"
rustchain-cli agent --json register "TestAgent" --type service --wallet rtc_test_123
rustchain-cli x402 --json pay rtc_test 1.0 --wallet rtc_test_123
```

### Full Integration Test
```bash
# 1. Create wallet and capture address
WALLET_JSON=$(rustchain-cli wallet --json create "IntegrationTest")
WALLET_ADDR=$(echo "$WALLET_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['address'])")

# 2. Register agent with that wallet
rustchain-cli agent --json register "IntegrationBot" --wallet "$WALLET_ADDR" --type bot

# 3. Enable x402 payments
rustchain-cli x402 --json enable --wallet "$WALLET_ADDR"

# 4. List bounties (may fail if node doesn't have endpoint)
rustchain-cli bounty --json list 2>&1 | head -20 || echo "Bounty endpoint not available"

echo "✓ All Agent Economy CLI commands working"
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
