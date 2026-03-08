# RustChain MCP Server

MCP Server for interacting with RustChain from Claude Code.

## Installation

```bash
# Install dependencies
pip install mcp httpx

# Add to Claude Code
claude mcp add rustchain python /path/to/mcp-server/main.py
```

## Tools

### Required Tools (75 RTC)

- `rustchain_balance` - Check RTC balance for any wallet
- `rustchain_miners` - List active miners and their architectures
- `rustchain_epoch` - Get current epoch info (slot, height, rewards)
- `rustchain_health` - Check node health across all 3 attestation nodes
- `rustchain_transfer` - Send RTC (requires wallet key)

### Bonus Tools (100 RTC)

- `rustchain_ledger` - Query transaction history
- `rustchain_register_wallet` - Create a new wallet
- `rustchain_bounties` - List open bounties with rewards

## API Endpoints

- Primary Node: https://50.28.86.131
- Fallback: Node 2/3 (to be implemented)

## Usage

Once installed, you can use these commands in Claude Code:

```
What's my RTC balance?
Who are the top miners?
What's the current epoch?
Is the network healthy?
```
