# RustChain MCP Server

[![MCP Server](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](../../../LICENSE)

**Model Context Protocol (MCP) server for RustChain blockchain** — Provides AI assistants with tools to interact with RustChain's core endpoints: health, epoch, balance, and queries.

## 🎯 Overview

This MCP server exposes four core tools for AI assistants to interact with RustChain:

| Tool | Description |
|------|-------------|
| `rustchain_health` | Check API health status and service availability |
| `rustchain_epoch` | Get current or specific epoch information |
| `rustchain_balance` | Get RTC wallet balance for a miner |
| `rustchain_query` | Execute generic queries (miners, blocks, transactions) |

## 📦 Installation

### From Source

```bash
cd integrations/rustchain-mcp
pip install -e .
```

### Dependencies

```bash
pip install aiohttp>=3.9.0 mcp>=1.0.0
```

## 🚀 Quick Start

### Run as Standalone Server

```bash
python -m rustchain_mcp.mcp_server
```

### Configure in MCP Client

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "rustchain": {
      "command": "python",
      "args": ["-m", "rustchain_mcp.mcp_server"],
      "env": {
        "RUSTCHAIN_API_BASE": "https://50.28.86.131"
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
    "args": ["-m", "rustchain_mcp.mcp_server"]
  }
}
```

## 🛠️ Tools

### rustchain_health

Check RustChain API health status.

**Input:** None

**Output:**
```json
{
  "status": "ok",
  "healthy": true,
  "timestamp": 1234567890,
  "service": "beacon-atlas-api",
  "version": "2.2.1",
  "uptime_s": 86400
}
```

### rustchain_epoch

Get epoch information.

**Input:**
```json
{
  "epoch": 95  // Optional, defaults to current
}
```

**Output:**
```json
{
  "epoch": 95,
  "slot": 12345,
  "height": 67890,
  "status": "active"
}
```

### rustchain_balance

Get wallet balance.

**Input:**
```json
{
  "miner_id": "scott"  // Required
}
```

**Output:**
```json
{
  "miner_id": "scott",
  "balance_rtc": 155.0,
  "balance_i64": 155000000,
  "total_rtc": 155.0,
  "pending": null,
  "staked": null
}
```

### rustchain_query

Execute generic query.

**Input:**
```json
{
  "query_type": "miners",  // Required
  "params": {"hardware_type": "PowerPC G4"},  // Optional
  "limit": 50  // Optional, default 50
}
```

**Output:**
```json
{
  "success": true,
  "query_type": "miners",
  "count": 10,
  "data": {...},
  "error": null
}
```

## 📖 Resources

### Static Resources

| URI | Description |
|-----|-------------|
| `rustchain://health` | Current health status |
| `rustchain://epoch/current` | Current epoch info |
| `rustchain://docs/api` | API documentation |

### Resource Templates

| URI Template | Description |
|--------------|-------------|
| `rustchain://epoch/{epoch_number}` | Specific epoch |
| `rustchain://wallet/{miner_id}` | Wallet balance |

## 💬 Prompts

### check_rustchain_status

Check network health and current epoch.

**Arguments:** None

### check_wallet_balance

Check RTC balance for a wallet.

**Arguments:**
- `miner_id` (required) — Miner ID or wallet name

### query_miners

Query miners with optional filters.

**Arguments:**
- `hardware_type` (optional) — Filter by hardware
- `min_score` (optional) — Minimum score threshold

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUSTCHAIN_API_BASE` | `https://50.28.86.131` | Base API URL |
| `RUSTCHAIN_NODE_URL` | `https://50.28.86.131:5000` | Node RPC URL |
| `RUSTCHAIN_TIMEOUT` | `30` | Request timeout (seconds) |
| `RUSTCHAIN_RETRY` | `2` | Retry count on failure |

## 🧪 Testing

### Install Dev Dependencies

```bash
pip install pytest pytest-asyncio aiohttp
```

### Run Tests

```bash
cd integrations/rustchain-mcp
pytest tests/ -v
```

### Expected Output

```
tests/test_schemas.py::TestHealthStatus::test_from_dict_minimal PASSED
tests/test_schemas.py::TestEpochInfo::test_from_dict_minimal PASSED
tests/test_schemas.py::TestWalletBalance::test_from_dict_minimal PASSED
tests/test_client.py::TestRustChainClient::test_health_success PASSED
tests/test_client.py::TestRustChainClient::test_epoch_current PASSED
tests/test_client.py::TestRustChainClient::test_balance_success PASSED
tests/test_mcp_server.py::TestRustChainMCP::test_tool_health PASSED
...
```

## 📐 Architecture

```
┌─────────────────┐         MCP Protocol         ┌─────────────────────────┐
│  AI Assistant   │ ◄──────────────────────────► │  RustChain MCP Server   │
│  (Claude, etc.) │                              │  - mcp_server.py        │
│                 │                              │                         │
│  - Check health │                              │  Tools:                 │
│  - Get epoch    │                              │  - rustchain_health     │
│  - Check balance│                              │  - rustchain_epoch      │
│  - Query data   │                              │  - rustchain_balance    │
│                 │                              │  - rustchain_query      │
└─────────────────┘                              │                         │
                                                 │  Resources:             │
                                                 │  - Health status        │
                                                 │  - Epoch info           │
                                                 │  - API docs             │
                                                 └───────────┬─────────────┘
                                                             │
                                                             ▼
                                                 ┌─────────────────────────┐
                                                 │  RustChain APIs         │
                                                 │  - /api/health          │
                                                 │  - /epoch               │
                                                 │  - /wallet/balance      │
                                                 │  - /api/query           │
                                                 └─────────────────────────┘
```

## 📝 Usage Examples

### Example 1: Check API Health

**User:** "Is the RustChain API healthy?"

**AI uses:** `rustchain_health`

**Response:**
```json
{
  "status": "ok",
  "healthy": true,
  "uptime_s": 86400
}
```

### Example 2: Get Current Epoch

**User:** "What epoch are we in?"

**AI uses:** `rustchain_epoch` with no arguments

**Response:**
```json
{
  "epoch": 95,
  "slot": 12345,
  "height": 67890
}
```

### Example 3: Check Wallet Balance

**User:** "What's the balance for miner 'scott'?"

**AI uses:** `rustchain_balance` with `miner_id="scott"`

**Response:**
```json
{
  "miner_id": "scott",
  "balance_rtc": 155.0,
  "balance_i64": 155000000
}
```

### Example 4: Query Miners

**User:** "Show me PowerPC G4 miners"

**AI uses:** `rustchain_query` with:
- `query_type="miners"`
- `params={"hardware_type": "PowerPC G4"}`
- `limit=10`

**Response:**
```json
{
  "success": true,
  "count": 3,
  "data": {"miners": [...]}
}
```

## 🔒 Security Notes

- **Self-signed certificates:** The RustChain API uses self-signed TLS certificates. The client disables SSL verification (`ssl=False`).
- **Read-only access:** All endpoints are read-only; no write operations are exposed.
- **Rate limiting:** Upstream API rate limits apply (30-60 requests/minute depending on endpoint).

## 📚 API Reference

For detailed API documentation, see:
- [API Walkthrough](../../../API_WALKTHROUGH.md)
- [API Reference](../../../docs/api-reference.md)

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](../../../CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License — See [LICENSE](../../../LICENSE) for details.

---

<div align="center">

**Built with 🔥 by the RustChain Community**

*Issue #1602 Implementation*

</div>
