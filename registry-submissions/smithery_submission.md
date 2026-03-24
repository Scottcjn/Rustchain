# Smithery.ai Submission — RustChain MCP Server

## Registry Info
- **URL**: https://smithery.ai/
- **Submission URL**: https://smithery.ai/new
- **Docs**: https://smithery.ai/docs/build/publish
- **GitHub**: https://github.com/Scottcjn/rustchain-mcp

## Submission Process

### Method 1: URL Publishing (Recommended if we deploy Streamable HTTP)

1. Go to https://smithery.ai/new
2. Sign in (GitHub auth)
3. Provide the server's public HTTPS URL
4. Smithery auto-scans for metadata (tools, prompts, resources)
5. Published with analytics and discovery

**Requirement**: Server must support **Streamable HTTP** transport. Our current MCP server uses stdio transport, so this method requires deploying a Streamable HTTP wrapper.

### Method 2: CLI Publishing

```bash
# Install Smithery CLI
npm install -g @anthropic-ai/smithery-cli

# Publish (requires Smithery API key from account)
smithery mcp publish "https://your-server-url/mcp" -n @Scottcjn/rustchain-mcp
```

### Method 3: GitHub Repo Publishing

If Smithery supports repo-based publishing, point it at:
```
https://github.com/Scottcjn/rustchain-mcp
```

## Server Metadata

### smithery.yaml (if required)

```yaml
name: rustchain-mcp
description: >
  RustChain + BoTTube MCP Server — gives AI agents access to the RustChain
  Proof-of-Antiquity blockchain and BoTTube AI-native video platform.
  14 tools + 3 resources for querying miners, balances, epochs, bounties,
  videos, and network health.
version: "1.0.0"
author: Scottcjn
license: MIT
repository: https://github.com/Scottcjn/rustchain-mcp
transport: stdio
tags:
  - blockchain
  - depin
  - web3
  - video
  - mining
tools:
  - get_network_health
  - get_epoch_info
  - get_miner_list
  - get_miner_details
  - get_balance
  - get_top_balances
  - get_bounties
  - get_bounty_details
  - get_recent_transactions
  - get_anchors
  - bottube_get_videos
  - bottube_get_video_details
  - bottube_get_agents
  - bottube_search
resources:
  - rustchain://network/overview
  - rustchain://tokenomics/summary
  - bottube://platform/stats
```

### .well-known/mcp/server-card.json (for static metadata)

```json
{
  "name": "RustChain + BoTTube MCP Server",
  "version": "1.0.0",
  "description": "AI agent access to RustChain Proof-of-Antiquity blockchain and BoTTube video platform. 14 tools + 3 resources.",
  "author": {
    "name": "Scottcjn",
    "url": "https://github.com/Scottcjn"
  },
  "repository": "https://github.com/Scottcjn/rustchain-mcp",
  "license": "MIT",
  "transport": ["stdio"],
  "tools": [
    {"name": "get_network_health", "description": "Check RustChain node health and uptime"},
    {"name": "get_epoch_info", "description": "Get current epoch, slot, and settlement info"},
    {"name": "get_miner_list", "description": "List active miners with architectures and multipliers"},
    {"name": "get_miner_details", "description": "Get detailed info about a specific miner"},
    {"name": "get_balance", "description": "Check RTC balance for a miner/wallet"},
    {"name": "get_top_balances", "description": "Get top RTC holders"},
    {"name": "get_bounties", "description": "List open GitHub bounties with RTC rewards"},
    {"name": "get_bounty_details", "description": "Get details of a specific bounty"},
    {"name": "get_recent_transactions", "description": "List recent RTC transactions"},
    {"name": "get_anchors", "description": "Get Ergo cross-chain anchor records"},
    {"name": "bottube_get_videos", "description": "List BoTTube videos"},
    {"name": "bottube_get_video_details", "description": "Get video details"},
    {"name": "bottube_get_agents", "description": "List BoTTube AI agents"},
    {"name": "bottube_search", "description": "Search BoTTube content"}
  ]
}
```

## Blockers / Requirements

1. **Streamable HTTP**: Smithery's primary discovery path requires Streamable HTTP transport. Our server currently uses stdio. **Options**:
   - Deploy a thin HTTP wrapper around the stdio server
   - Use the CLI/repo publish method instead
   - Add Streamable HTTP support to the MCP server itself
2. **Smithery Account**: Need to create account at smithery.ai (GitHub login)
3. **API Key**: Required for CLI publishing

## Priority: HIGH
- Smithery is one of the top MCP server registries
- Direct discoverability by AI agents using MCP clients
- Analytics on tool usage
- Already have glama.json and well-known/agent.json — adding Smithery increases reach
