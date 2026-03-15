# RustChain MCP Server

Model Context Protocol server that exposes the RustChain node API as MCP tools.
Built for Claude Code and other MCP-compatible clients.

## Tools

| Tool | Description |
|------|-------------|
| `get_health` | Node health status, version, uptime, DB status |
| `get_epoch` | Current epoch, slot, enrolled miners, reward pot |
| `get_balance` | Wallet balance for a miner ID |
| `get_miners` | List all active miners with hardware info |
| `get_chain_tip` | Latest slot, producing miner, tip age |
| `get_block` | Retrieve a block at a given height |

## Setup

### 1. Install dependencies

```bash
pip install -r tools/mcp-server/requirements.txt
```

### 2. Register with Claude Code

Add the following to your Claude Code MCP config (`~/.claude/claude_desktop_config.json`
or the project's `.mcp.json`):

```json
{
  "mcpServers": {
    "rustchain": {
      "command": "python",
      "args": ["tools/mcp-server/server.py"]
    }
  }
}
```

### 3. Verify

Once registered, Claude Code will have access to all six RustChain tools.
Ask Claude to "check rustchain health" or "get the current epoch" to confirm.

## API Reference

All tools call the public RustChain node at `https://rustchain.org`.
No authentication is required for read-only endpoints.

## Run Standalone

```bash
python tools/mcp-server/server.py
```

The server communicates over stdio using the MCP protocol.
