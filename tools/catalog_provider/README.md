# RustChain Service Catalog Provider Daemon (`tools/catalog_provider`)

Unattended provider agent for the non-custodial RustChain `/catalog` marketplace ([`docs/SERVICE_CATALOG.md`](../../docs/SERVICE_CATALOG.md)).

It reuses [`tools/catalog_cli.py`](../catalog_cli.py) (`AgentKey`, `CatalogClient`, `CatalogError`, `urllib_transport`, `sha256_file`) so Beacon Ed25519 request signing and identity loading stay identical to the CLI.

## Features

1. **Unattended Order Fulfillment (`ProviderDaemon`)**
   - Polls `GET /catalog/orders?role=provider&status=requested` for a configured listing (`--listing-id`) or category (`--category review|docs|testing|...`).
   - Runs a pluggable `Worker` (`CodeReviewWorker` or `DocsLintWorker`), writes the deliverable artifact to `<state-dir>/deliverables/<order_id>/`, computes its SHA-256 digest, and calls `POST /catalog/orders/<id>/deliver`.
   - Persists state atomically to `<state-dir>/state.json` before and after delivery so restarts never double-deliver a live order. If the server reports `409 Conflict` or an already-transitioned order after an interrupted run, the daemon reconciles from `GET /catalog/orders/<id>`.
2. **Payment Watching & `status.json`**
   - Polls `GET /catalog/orders/<id>` for delivered and accepted orders until `payment.state == "confirmed"` on the node's ledger (`pending_ledger` transfer with memo `svc:<order_id>`).
   - Writes `<state-dir>/status.json` with **work counts only** (`orders_delivered`, `orders_accepted`, `orders_paid`, `distinct_buyers_delivered`, `distinct_buyers_accepted`, `distinct_buyers_paid`) and **zero RTC volume totals**, matching the catalog's "work, not volume" rule.
3. **Safety Controls**
   - **Kill Switch**: if `<state-dir>/KILL` (or `--kill-switch PATH`) exists, the daemon halts immediately (`exit code 2`) before polling or delivering.
   - **Concurrency Cap**: `--max-concurrent N` limits how many orders are fulfilled in a single cycle.
   - **Rate Limit**: `--rate-limit M` bounds order deliveries per minute with a sliding 60-second window.
   - **Key Hygiene**: loads the Beacon identity via `catalog_cli.AgentKey.load()`, never prints or logs private key material, and attaches a log filter that redacts any 64-hex string.

## Quick Start

```bash
# 1. Post a listing (once) using catalog_cli.py
python tools/catalog_cli.py --node https://50.28.86.131 --insecure offer \
  --title "Automated repo code review & docs lint (file and line references)" \
  --category review --price-rtc 0.5 --unit "per repo" --turnaround-hours 1

# 2. Run one poll/fulfill/payment-watch cycle
python -m tools.catalog_provider \
  --node https://50.28.86.131 --insecure \
  --listing-id lst_48e9f81b4e0e9880 \
  --category review --worker review \
  --state-dir ~/.rustchain/catalog_provider \
  --once

# 3. Run unattended as a continuous daemon
python -m tools.catalog_provider \
  --node https://50.28.86.131 --insecure \
  --listing-id lst_48e9f81b4e0e9880 \
  --category review --worker review \
  --state-dir ~/.rustchain/catalog_provider \
  --interval 15
```

## Emergency Stop (Kill Switch)

```bash
touch ~/.rustchain/catalog_provider/KILL
```

## Running Tests

```bash
pytest tests/test_catalog_provider.py -v
```
