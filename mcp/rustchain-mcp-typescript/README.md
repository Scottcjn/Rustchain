# RustChain MCP Server

Query the RustChain blockchain directly from Claude Code using the Model Context Protocol (MCP).

## Installation

### Prerequisites

- Node.js 18+
- Claude Code

### Step 1: Clone and Build

```bash
git clone https://github.com/sososonia-cyber/Rustchain.git
cd Rustchain/rustchain-mcp-server
npm install
npm run build
```

### Step 2: Add to Claude Code

```bash
claude mcp add rustchain-mcp node /path/to/rustchain-mcp-server/dist/index.js
```

Or add via JSON config (~/.claude/mcp.json):

```json
{
  "mcpServers": {
    "rustchain-mcp": {
      "command": "node",
      "args": ["/path/to/rustchain-mcp-server/dist/index.js"]
    }
  }
}
```

## Available Tools

### Required Tools (75 RTC)

| Tool | Description |
|------|-------------|
| `rustchain_balance` | Check RTC balance for any wallet |
| `rustchain_miners` | List active miners and their architectures |
| `rustchain_epoch` | Get current epoch info (slot, height, rewards) |
| `rustchain_health` | Check node health across all 3 attestation nodes |
| `rustchain_transfer` | Send RTC (requires wallet private key) |

### Bonus Tools (for 100 RTC)

| Tool | Description |
|------|-------------|
| `rustchain_ledger` | Query transaction history |
| `rustchain_register_wallet` | Create a new wallet |
| `rustchain_bounties` | List open bounties with rewards |

## Usage Examples

### Check Balance

```
rustchain_balance { "miner_id": "your-wallet-name" }
```

### List Miners

```
rustchain_miners { "limit": 10 }
```

### Get Epoch Info

```
rustchain_epoch {}
```

### Check Node Health

```
rustchain_health {}
```

### Transfer RTC

```
rustchain_transfer {
  "from_private_key": "your-private-key",
  "to_miner_id": "recipient-wallet",
  "amount": 10
}
```

### Register Wallet

```
rustchain_register_wallet { "miner_id": "my-new-wallet" }
```

### List Bounties

```
rustchain_bounties { "limit": 10 }
```

## API Endpoints

The MCP server automatically handles failover across 3 attestation nodes:

- Primary: https://50.28.86.131
- Node 2: https://50.28.87.10
- Node 3: https://50.28.87.75

## License

MIT
