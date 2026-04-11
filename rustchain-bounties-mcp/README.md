# RustChain Bounties MCP Server

[![MCP](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](../LICENSE)

**One-line install + Claude Code config** for an MCP server that gives AI assistants 7 tools to interact with the RustChain blockchain.

## Quick Install

```bash
pip install "mcp>=1.0.0" aiohttp>=3.9.0
```

Then clone or copy this directory — no build step needed.

## Claude Code Configuration

Add to your Claude Code MCP config (or Cursor / VS Code Copilot MCP config):

```json
{
  "mcpServers": {
    "rustchain-bounties": {
      "command": "python",
      "args": ["-m", "rustchain_bounties_mcp.mcp_server"],
      "env": {
        "RUSTCHAIN_NODE_URL": "https://50.28.86.131"
      }
    }
  }
}
```

**Cursor** (`.cursor/mcp.json`):

```json
{
  "rustchain-bounties": {
    "command": "python",
    "args": ["-m", "rustchain_bounties_mcp.mcp_server"],
    "env": {
      "RUSTCHAIN_NODE_URL": "https://50.28.86.131"
    }
  }
}
```

**VS Code Copilot** — add the same JSON to your MCP server configuration file.

## Tools

| Tool | Description | Required Args | Endpoint |
|------|-------------|---------------|----------|
| `rustchain_health` | Node health probe (ok, version, uptime, db status) | none | `GET /health` |
| `rustchain_balance` | Get RTC wallet balance | `miner_id` | `GET /wallet/balance` |
| `rustchain_miners` | List active miners with filters | none | `GET /api/miners` |
| `rustchain_epoch` | Current epoch info | none | `GET /epoch` |
| `rustchain_verify_wallet` | Heuristic wallet check (non-zero balance only) | `miner_id` | `GET /wallet/balance` |
| `rustchain_attest_challenge` | Fetch attestation nonce for enrollment | none | `POST /attest/challenge` |
| `rustchain_submit_attestation` | Submit hardware attestation (nonce required) | `miner_id`, `device`, `nonce` | `POST /attest/submit` |
| `rustchain_bounties` | List open bounties (via GitHub API) | none | GitHub Issues API |

### Tool Details

#### rustchain_health

Check if the RustChain node is healthy, DB is read/write, and chain tip is recent.

**Input:** `{}`

**Output:**
```json
{
  "ok": true,
  "healthy": true,
  "version": "2.2.1",
  "uptime_s": 86400,
  "db_rw": true,
  "backup_age_hours": 12.5,
  "tip_age_slots": 3
}
```

#### rustchain_balance

Get the RTC balance for a miner by ID.

**Input:** `{"miner_id": "scott"}`

**Output:**
```json
{
  "miner_id": "scott",
  "amount_rtc": 155.0,
  "amount_i64": 155000000
}
```

#### rustchain_miners

List active miners. Supports optional `hardware_type` filter and `limit`.

**Input:** `{"hardware_type": "PowerPC", "limit": 20}`

**Output:**
```json
{
  "total_count": 42,
  "limit": 20,
  "offset": 0,
  "miners": [
    {
      "miner": "alice",
      "hardware_type": "PowerPC G4 (Vintage)",
      "device_family": "PowerPC",
      "device_arch": "g4",
      "antiquity_multiplier": 2.0,
      "entropy_score": 0.95,
      "last_attest": 1700000000,
      "epochs_mined": 10
    }
  ]
}
```

#### rustchain_epoch

Get current epoch information.

**Input:** `{}`

**Output:**
```json
{
  "epoch": 95,
  "slot": 12345,
  "epoch_pot": 1000.0,
  "enrolled_miners": 42,
  "blocks_per_epoch": 100,
  "total_supply_rtc": 21000000.0
}
```

#### rustchain_verify_wallet

Heuristically verify whether a wallet exists for a given miner_id. The live
`/wallet/balance` endpoint returns HTTP 200 with a zero balance for **any**
miner_id (including nonsense strings), so a 200 response does **not** prove
wallet existence. This tool uses a conservative heuristic: `exists=True` only
when the queried miner_id shows a **non-zero** balance, indicating observed
on-chain activity.

**Input:** `{"miner_id": "scott"}`

**Output (non-zero balance):**
```json
{
  "wallet_address": "scott",
  "exists": true,
  "balance_rtc": 155.0,
  "message": "Observed wallet activity for scott with balance 155.0 RTC"
}
```

**Output (zero / unknown):**
```json
{
  "wallet_address": "unknown_id",
  "exists": false,
  "balance_rtc": 0.0,
  "message": "Balance endpoint returned a zero-balance row; this does not prove wallet existence on the live API"
}
```

#### rustchain_attest_challenge

Fetch a fresh attestation nonce from the node. This nonce **must** be included
in the subsequent `rustchain_submit_attestation` call — the live endpoint
rejects submissions without a valid nonce (`MISSING_NONCE`).

**Input:** `{}`

**Output:**
```json
{
  "nonce": "da0cd8aafb29b4ccab3ce182d2679015da621919a2b7fd2d804bda890ac53e",
  "expires_at": 1775911361,
  "server_time": 1775911061
}
```

#### rustchain_submit_attestation

Submit a hardware attestation for miner enrollment.

**Input:**
```json
{
  "miner_id": "new_miner",
  "device": {
    "device_model": "PowerBook G4",
    "device_arch": "g4",
    "cores": 1
  },
  "signature": "ed25519_sig_hex (optional)",
  "public_key": "ed25519_pubkey_hex (optional)"
}
```

**Output:**
```json
{
  "ok": true,
  "message": "enrolled",
  "miner_id": "new_miner",
  "enrolled_epoch": 96
}
```

#### rustchain_bounties

List RustChain bounties. Defaults to open bounties.

**Data source (intentional):** The live RustChain node does **not** expose a
native `/api/bounties` endpoint (it returns HTTP 404). Bounties are fetched
from the GitHub Issues API at `Scottcjn/rustchain-bounties`. Reward amounts are
parsed from issue labels (e.g. `"bounty: 500 RTC"`) and titles (e.g.
`"Bounty: MCP Server (500 RTC)"`). This is the authoritative source for bounty
data and is by design — the bounty workflow is managed through GitHub Issues.

**Input:** `{"status": "open", "limit": 20}`

**Output:**
```json
{
  "count": 1,
  "source": "github:Scottcjn/rustchain-bounties",
  "bounties": [
    {
      "issue_number": 2859,
      "title": "MCP Server",
      "reward_rtc": 500.0,
      "status": "open",
      "difficulty": "medium",
      "tags": ["python", "mcp"]
    }
  ]
}
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `RUSTCHAIN_NODE_URL` | `https://50.28.86.131` | RustChain node base URL |
| `RUSTCHAIN_TIMEOUT` | `30` | HTTP request timeout (seconds) |
| `RUSTCHAIN_RETRY` | `2` | Number of retries on failure |

## Running

### As a module

```bash
python -m rustchain_bounties_mcp.mcp_server
```

### As a console script (after `pip install -e .`)

```bash
rustchain-bounties-mcp
```

### With custom node URL

```bash
RUSTCHAIN_NODE_URL=https://my-node.example.com python -m rustchain_bounties_mcp.mcp_server
```

## Architecture

```
┌──────────────────┐       MCP stdio        ┌──────────────────────────┐
│  AI Assistant    │ ◄────────────────────► │  rustchain-bounties-mcp  │
│  (Claude/Cursor) │                        │                          │
│                  │                        │  Tools:                    │
│  - health        │                        │  - rustchain_health        │
│  - balance       │                        │  - rustchain_balance       │
│  - miners        │                        │  - rustchain_miners        │
│  - epoch         │                        │  - rustchain_epoch         │
│  - verify_wallet │                        │  - rustchain_verify_wallet │
│  - attestation   │                        │  - rustchain_submit_attest │
│  - bounties      │                        │  - rustchain_bounties      │
└──────────────────┘                        └───────────┬──────────────┘
                                              ┌─────────┴──────────────┐
                                              │                        │
                                         HTTPS│                   HTTPS│
                                         (node)│              (GitHub)  │
                                              ▼                        ▼
                                  ┌──────────────────┐   ┌──────────────────────────┐
                                  │ RustChain Node   │   │ GitHub Issues API        │
                                  │ (Flask)          │   │ Scottcjn/rustchain-      │
                                  │ GET  /health     │   │ bounties                 │
                                  │ GET  /epoch      │   │                          │
                                  │ GET  /wallet/    │   │ (bounties only)          │
                                  │   balance        │   └──────────────────────────┘
                                  │ GET  /api/miners │
                                  │ POST /attest/    │
                                  │   submit         │
                                  └──────────────────┘
```

## Testing

```bash
cd rustchain-bounties-mcp
pip install -e ".[dev]"
pytest tests/ -v
```

## Packaging (PyPI / npm)

### PyPI (local)

```bash
pip install build
python -m build
# Produces dist/rustchain_bounties_mcp-0.1.0-py3-none-any.whl
pip install dist/rustchain_bounties_mcp-0.1.0-py3-none-any.whl
```

To publish to PyPI: `twine upload dist/*` (requires PyPI credentials).

### npm (wrapper)

For npm distribution, create a thin wrapper `package.json`:

```json
{
  "name": "rustchain-bounties-mcp",
  "version": "0.1.0",
  "bin": {
    "rustchain-bounties-mcp": "run.py"
  },
  "scripts": {
    "postinstall": "pip install -t node_modules/.bin/rustchain-bounties-mcp_venv ."
  }
}
```

Or use [`pipx`](https://github.com/pypa/pipx) for user-level installs.

## Security Notes

- **Self-signed TLS certificate:** The live RustChain node at `50.28.86.131`
  uses a self-signed TLS certificate. The client disables certificate
  verification (`ssl=False`) to connect. In production you should either:
  - Pin the node's certificate fingerprint, or
  - Deploy the node behind a properly signed certificate (e.g. Let's Encrypt), or
  - Use a trusted internal CA.
  To pin the cert, set `RUSTCHAIN_NODE_URL` to an `https://` URL and modify
  `client.py` to pass an `ssl.SSLContext` with `load_verify_locations()`.
- **Read-only tools:** `health`, `balance`, `miners`, `epoch`, `verify_wallet`, `bounties`, `attest_challenge` are read-only.
- **State-changing tools:** `submit_attestation` modifies node state. Use with appropriate access controls.
- **No secrets in MCP output:** The server never logs or returns private keys or signing material.
- **GitHub API rate limits:** Unauthenticated GitHub API calls are limited to 60/hour. For heavy usage, set a `GITHUB_TOKEN` environment variable (the client can be extended to support auth headers).
- **Attestation nonce expiry:** Nonces returned by `rustchain_attest_challenge` have a short TTL (typically ~5 minutes). Call `rustchain_attest_challenge` immediately before `rustchain_submit_attestation`.

## License

MIT
