# mcp.so Submission — RustChain MCP Server

## Registry Info
- **URL**: https://mcp.so/
- **Submission**: Click "Submit" button in navbar, or create GitHub issue
- **Type**: Community-driven third-party MCP marketplace (18,905+ servers listed)

## Submission Process

1. Go to https://mcp.so/
2. Click the **"Submit"** button in the navigation bar
3. Fill out the server information form
4. Alternatively: visit their GitHub issues page and create a new issue with server details

## Required Fields

| Field | Our Answer |
|-------|-----------|
| **Name** | RustChain + BoTTube MCP Server |
| **Description** | AI agent access to the RustChain Proof-of-Antiquity blockchain and BoTTube AI-native video platform. 14 tools + 3 resources for querying miners, balances, epochs, bounties, videos, and network health. Supports Claude Code, Claude Desktop, and any MCP-compatible client. |
| **GitHub URL** | https://github.com/Scottcjn/rustchain-mcp |
| **Author** | Scottcjn (Elyan Labs) |
| **Category/Tags** | Blockchain, Web3, DePIN, Video, Mining, AI Agents |
| **Features** | 14 tools (network health, epoch info, miner list, balances, bounties, transactions, Ergo anchors, BoTTube videos/agents/search), 3 resources (network overview, tokenomics, platform stats) |
| **Connection Info** | stdio transport; install via `pip install rustchain-mcp` or clone from GitHub |
| **Avatar/Logo URL** | (need to provide — host logo on GitHub or rustchain.org) |

## Prepared GitHub Issue (if using issue method)

```markdown
## New MCP Server Submission: RustChain + BoTTube

**Server Name**: RustChain + BoTTube MCP Server
**Author**: Scottcjn (Elyan Labs)
**GitHub**: https://github.com/Scottcjn/rustchain-mcp
**License**: MIT

### Description
AI agent access to the RustChain Proof-of-Antiquity blockchain and BoTTube
AI-native video platform. 14 tools + 3 resources for querying miners,
balances, epochs, bounties, videos, and network health.

### Tools (14)
- `get_network_health` — Check RustChain node health
- `get_epoch_info` — Current epoch and settlement info
- `get_miner_list` — Active miners with architectures
- `get_miner_details` — Detailed miner info
- `get_balance` — RTC balance lookup
- `get_top_balances` — Top RTC holders
- `get_bounties` — Open GitHub bounties with RTC rewards
- `get_bounty_details` — Specific bounty details
- `get_recent_transactions` — Recent RTC ledger entries
- `get_anchors` — Ergo cross-chain anchor records
- `bottube_get_videos` — BoTTube video listings
- `bottube_get_video_details` — Video metadata
- `bottube_get_agents` — AI agent directory
- `bottube_search` — Content search

### Resources (3)
- `rustchain://network/overview`
- `rustchain://tokenomics/summary`
- `bottube://platform/stats`

### Configuration
```json
{
  "mcpServers": {
    "rustchain": {
      "command": "python",
      "args": ["-m", "rustchain_mcp"],
      "env": {
        "RUSTCHAIN_NODE_URL": "https://rustchain.org",
        "BOTTUBE_API_URL": "https://50.28.86.153"
      }
    }
  }
}
```

### Tags
blockchain, web3, depin, video, mining, proof-of-antiquity, ergo, hardware
```

## Blockers / Requirements

1. **Logo**: Need a hosted logo URL for the listing avatar.
2. **None significant**: mcp.so is community-driven with low barrier to entry.

## Priority: HIGH
- Largest third-party MCP marketplace (18,905+ servers)
- Easy submission process (just a form or GitHub issue)
- High visibility for MCP-compatible AI agents
- No gatekeeping — community-driven
