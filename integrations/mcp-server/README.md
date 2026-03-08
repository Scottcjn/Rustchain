# RustChain MCP Server

[![MCP Server](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](../../LICENSE)

**Model Context Protocol (MCP) server for RustChain blockchain** — Connect AI assistants to RustChain's blockchain data, mining tools, and agent economy.

## 🎯 What is this?

This MCP server allows AI assistants (Claude, ChatGPT, Cursor, etc.) to:
- Query RustChain blockchain data (blocks, epochs, miners)
- Check wallet balances and transaction history
- Discover open bounties
- Verify hardware compatibility for mining
- Calculate estimated mining rewards
- Access agent information from the Beacon Protocol

Think of it as a **USB-C port for AI applications** to connect to RustChain.

---

## 📦 Installation

### Option 1: Install from source

```bash
cd integrations/mcp-server
pip install -e .
```

### Option 2: Install dependencies only

```bash
pip install mcp aiohttp
```

---

## 🚀 Quick Start

### Run as standalone server

```bash
python mcp_server.py
```

### Run via npx (for MCP clients)

```bash
npx -y @modelcontextprotocol/server-python rustchain-mcp
```

### Configure in MCP client

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "rustchain": {
      "command": "python",
      "args": ["/path/to/RustChain/integrations/mcp-server/mcp_server.py"],
      "env": {
        "RUSTCHAIN_API_BASE": "https://50.28.86.131",
        "RUSTCHAIN_NODE_URL": "https://50.28.86.131:5000",
        "BEACON_URL": "https://50.28.86.131:5001"
      }
    }
  }
}
```

**Cursor** (`.cursor/mcp.json`):

```json
{
  "rustchain": {
    "command": "python",
    "args": ["/path/to/RustChain/integrations/mcp-server/mcp_server.py"]
  }
}
```

---

## 🛠️ Available Tools

### Blockchain Data

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_miner_info` | Get information about a miner | `miner_id` (required) |
| `get_block_info` | Get block by epoch or hash | `block_id` (required) |
| `get_epoch_info` | Get current or specific epoch | `epoch` (optional) |
| `get_network_stats` | Get network statistics | — |
| `get_active_miners` | List active miners | `limit`, `hardware_type`, `min_score` |
| `get_wallet_balance` | Get wallet balance | `wallet` (required) |

### Agent Economy

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_agent_info` | Get AI agent information | `agent_id` (required) |
| `get_bounty_info` | Get open bounties | `issue_number`, `min_reward` |

### Mining Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `verify_hardware` | Check hardware compatibility | `cpu_model`, `architecture`, `is_vm` |
| `calculate_mining_rewards` | Estimate mining rewards | `hardware_type`, `epochs`, `uptime_percent` |

---

## 📖 Available Resources

Resources are read-only data endpoints that AI assistants can access:

| Resource URI | Description |
|--------------|-------------|
| `rustchain://network/stats` | Real-time network statistics |
| `rustchain://miners/active` | List of active miners |
| `rustchain://epochs/current` | Current epoch information |
| `rustchain://bounties/open` | Open bounties list |
| `rustchain://docs/quickstart` | Quickstart guide |

### Resource Templates

Dynamic resources (replace `{variable}` with actual values):

- `rustchain://miner/{miner_id}` — Specific miner info
- `rustchain://block/{epoch_or_hash}` — Specific block info
- `rustchain://wallet/{address}` — Wallet balance and history
- `rustchain://epoch/{epoch_number}` — Specific epoch info
- `rustchain://bounty/{issue_number}` — Specific bounty details

---

## 💬 Available Prompts

Pre-built prompts for common tasks:

### `analyze_miner_performance`

Analyze a miner's performance and get optimization suggestions.

**Arguments:**
- `miner_id` (required) — Miner ID to analyze

**Example:**
```
Use analyze_miner_performance to check miner_abc123
```

### `bounty_recommendations`

Get personalized bounty recommendations.

**Arguments:**
- `skill_level` (optional) — beginner, intermediate, advanced
- `interest_area` (optional) — blockchain, AI, hardware, web

**Example:**
```
Use bounty_recommendations with skill_level=intermediate, interest_area=blockchain
```

### `hardware_compatibility_check`

Check if vintage hardware is compatible with RustChain mining.

**Arguments:**
- `hardware_description` (required) — e.g., "PowerBook G4 1.5GHz"

**Example:**
```
Use hardware_compatibility_check for "Power Mac G5 2.0GHz Dual Core"
```

---

## 📝 Usage Examples

### Example 1: Check miner status

**User:** "What's the status of miner_12345?"

**AI uses:** `get_miner_info` with `miner_id="miner_12345"`

**Response:**
```json
{
  "found": true,
  "miner": {
    "miner_id": "miner_12345",
    "wallet": "wallet_xyz",
    "hardware": "PowerPC G4",
    "score": 245.8,
    "epochs_mined": 1250,
    "status": "active"
  }
}
```

### Example 2: Calculate mining rewards

**User:** "How much would I earn mining on a PowerPC G4 for 7 days?"

**AI uses:** `calculate_mining_rewards` with:
- `hardware_type="PowerPC G4"`
- `epochs=1008` (7 days × 144 epochs/day)
- `uptime_percent=90`

**Response:**
```json
{
  "hardware_type": "PowerPC G4",
  "multiplier": 2.5,
  "epochs": 1008,
  "estimated_rewards_rtc": 252.0,
  "breakdown": {
    "base": 100.8,
    "hardware_bonus": 151.2
  }
}
```

### Example 3: Find high-value bounties

**User:** "Show me open bounties worth at least 50 RTC"

**AI uses:** `get_bounty_info` with `min_reward=50`

**Response:**
```json
{
  "count": 3,
  "bounties": [
    {
      "issue_number": 23,
      "title": "🔗 BOUNTY: ERGO MAINNET BRIDGE (150 RTC)",
      "reward_rtc": 150,
      "url": "https://github.com/Scottcjn/RustChain/issues/23"
    }
  ]
}
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUSTCHAIN_API_BASE` | `https://50.28.86.131` | Base URL for RustChain API |
| `RUSTCHAIN_NODE_URL` | `https://50.28.86.131:5000` | RustChain node RPC URL |
| `BEACON_URL` | `https://50.28.86.131:5001` | Beacon Protocol API URL |

### Custom API Endpoints

If running a local RustChain node:

```bash
export RUSTCHAIN_API_BASE="http://localhost:5000"
export RUSTCHAIN_NODE_URL="http://localhost:5000"
export BEACON_URL="http://localhost:5001"
python mcp_server.py
```

---

## 🧪 Testing

### Install dev dependencies

```bash
pip install -e ".[dev]"
```

### Run tests

```bash
pytest tests/ -v --cov=mcp_server
```

### Run linters

```bash
black mcp_server.py --check
ruff check mcp_server.py
```

---

## 🏗️ Architecture

```
┌─────────────────┐         MCP Protocol         ┌─────────────────────────┐
│  AI Assistant   │ ◄──────────────────────────► │  RustChain MCP Server   │
│  (Claude, etc.) │                              │  - mcp_server.py        │
│                 │                              │                         │
│  - Ask questions│                              │  Tools:                 │
│  - Request data │                              │  - get_miner_info       │
│  - Get insights │                              │  - get_block_info       │
│                 │                              │  - calculate_rewards    │
└─────────────────┘                              │  - verify_hardware      │
                                                 │                         │
                                                 │  Resources:             │
                                                 │  - Network stats        │
                                                 │  - Active miners        │
                                                 │  - Epoch info           │
                                                 └───────────┬─────────────┘
                                                             │
                                                             ▼
                                                 ┌─────────────────────────┐
                                                 │  RustChain APIs         │
                                                 │  - /api/miners          │
                                                 │  - /api/epochs          │
                                                 │  - /api/stats           │
                                                 │  - /api/wallets         │
                                                 └─────────────────────────┘
```

---

## 🎓 Hardware Multipliers

RustChain rewards vintage hardware with multipliers:

| Hardware | Multiplier | Bonus |
|----------|------------|-------|
| PowerPC G4 | 2.5x | +150% |
| PowerPC G5 | 2.0x | +100% |
| PowerPC G3 | 1.8x | +80% |
| IBM POWER8+ | 2.0x | +100% |
| Apple Silicon (M1/M2/M3) | 1.15x | +15% |
| Modern x86/x64 | 1.0x | Base |
| Raspberry Pi | 1.0x | Base |

**Note:** VMs receive ~1% of normal rewards to prevent farming.

---

## 📚 Additional Resources

- [RustChain Main Repository](https://github.com/Scottcjn/RustChain)
- [RustChain Whitepaper](../../docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)
- [Open Bounties](https://github.com/Scottcjn/rustchain-bounties/issues)
- [Live Explorer](https://rustchain.org/explorer)
- [Model Context Protocol Docs](https://modelcontextprotocol.io)
- [MCP SDK](https://github.com/modelcontextprotocol/python-sdk)

---

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

### Development workflow

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Submit a PR

---

## 📄 License

MIT License — See [LICENSE](../../LICENSE) for details.

---

## 💰 Bounty

This MCP server implementation is submitted for the **RustChain MCP Server bounty** (75-100 RTC tier).

**Wallet Address:** `RTC1d48d848a5aa5ecf2c5f01aa5fb64837daaf2f35` (split: createkr-wallet)

---

## 🆘 Support

- **Issues:** [GitHub Issues](https://github.com/Scottcjn/RustChain/issues)
- **Discord:** [RustChain Discord](https://discord.gg/rustchain)
- **Twitter:** [@RustChain](https://twitter.com/RustChain)

---

<div align="center">

**Built with 🔥 by the RustChain Community**

*Your PowerPC G4 earns more than a modern Threadripper. That's the point.*

</div>
