# RustChain Block Explorer REST API

Lightweight Flask API that aggregates data from a RustChain node into
explorer-friendly endpoints with built-in caching and CORS support.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/blocks` | Paginated block list (`?page=1&limit=20`) |
| GET | `/api/blocks/:height` | Block detail by height |
| GET | `/api/transactions` | Recent network transactions |
| GET | `/api/address/:addr` | Address balance + transaction history |
| GET | `/api/search?q=` | Search blocks, addresses, epochs |
| GET | `/api/stats` | Aggregated network statistics |
| GET | `/api/health` | Explorer health check |

## Quick Start

```bash
pip install -r requirements.txt

# Point at your RustChain node
export RUSTCHAIN_NODE_URL=http://localhost:5000

python api.py
# → listening on http://localhost:6100
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `RUSTCHAIN_NODE_URL` | `http://localhost:5000` | Upstream node base URL |
| `EXPLORER_PORT` | `6100` | Port to bind |
| `CACHE_TTL` | `15` | Response cache lifetime (seconds) |
| `REQUEST_TIMEOUT` | `10` | Upstream request timeout (seconds) |

## Examples

```bash
# Latest blocks
curl http://localhost:6100/api/blocks?page=1&limit=10

# Block detail
curl http://localhost:6100/api/blocks/42

# Address lookup
curl http://localhost:6100/api/address/miner_abc123

# Search
curl http://localhost:6100/api/search?q=100

# Network stats
curl http://localhost:6100/api/stats
```

## Architecture

The API acts as a read-only aggregation layer in front of the RustChain node.
All data is fetched from the node's existing HTTP endpoints (`/headers/tip`,
`/epoch`, `/health`, `/balance/<id>`, `/wallet/history`, `/api/stats`, etc.)
and merged into a consistent explorer schema.

Responses are cached in-memory with a configurable TTL to reduce load on the
upstream node. The cache is thread-safe and keyed by endpoint + query string.
