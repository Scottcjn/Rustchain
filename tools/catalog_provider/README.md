# RustChain Catalog Provider Daemon (`tools/catalog_provider/`)

An unattended service provider agent for the RustChain `/catalog` marketplace (`docs/SERVICE_CATALOG.md`, `tools/catalog_cli.py`).

## Features
- **Reuses `tools/catalog_cli.py`**: Uses `AgentKey.load()` and `CatalogClient` directly for Ed25519 request signing (`X-Agent-Id`, `X-Agent-Timestamp`, `X-Agent-Nonce`, `X-Agent-Signature`).
- **Idempotent Across Restarts**: Persists order state and SHA-256 deliverable hashes in `provider_state.json` before and after `/deliver` calls, guaranteeing no order is ever double-delivered.
- **Payment Watching**: Tracks accepted orders via `GET /catalog/orders/<id>` until `payment.state == "confirmed"`, recording the `svc:<order_id>` memo and writing a privacy-preserving `status.json` (counts only: `orders_delivered`, `orders_accepted`, `orders_paid`, `distinct_buyers` — zero RTC totals, zero private keys).
- **Safety Controls**: Self-order rejection, configurable `max_concurrent_orders`, hourly delivery rate limiter, and an instant file-based kill switch (`<state_dir>/STOP`).

## Quick Start

```bash
# 1. Create a listing using catalog_cli.py
python tools/catalog_cli.py --identity ~/.beacon/identity/agent.key offer \
  --title "Automated Security & Code Review" --category review \
  --price-rtc 2 --unit "per repo" --turnaround-hours 24

# 2. Run a single poll-deliver-reconcile cycle
python -m tools.catalog_provider.daemon \
  --identity ~/.beacon/identity/agent.key \
  --state-dir ~/.beacon/catalog_provider \
  --category review --worker review --once

# 3. Run unattended in the background
python -m tools.catalog_provider.daemon \
  --identity ~/.beacon/identity/agent.key \
  --state-dir ~/.beacon/catalog_provider \
  --poll-interval 15
```

## Running Tests

```bash
pytest tests/test_catalog_provider.py -v
```
