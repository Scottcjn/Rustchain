# RustChain MCP Server

A Model Context Protocol (MCP) server for interacting with RustChain blockchain from Claude Code and other MCP clients.

## Installation

```bash
# Install dependencies
pip install -e .

# Add to Claude Code
claude mcp add rustchain-server python /path/to/rustchain_mcp.py
```

## Available Tools

- `rustchain_balance` - Check RTC balance for any wallet
- `rustchain_miners` - List active miners and their architectures  
- `rustchain_epoch` - Get current epoch info (slot, height, rewards)
- `rustchain_health` - Check node health across all 3 attestation nodes
- `rustchain_transfer` - Send RTC (requires wallet key)

## API Endpoints

The server connects to:
- Primary: https://50.28.86.131
- Fallback: Node 2/3 if primary is down

## License

MIT
