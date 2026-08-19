# RustChain Testnet Faucet

This adds a standalone Flask faucet service for the bounty task:
- `GET /faucet` (simple HTML form)
- `POST /faucet/drip`

## Request

```json
{
  "wallet": "my-test-wallet",
  "github_username": "myuser"
}
```

## Response

```json
{
  "ok": true,
  "amount": 1.0,
  "claim_id": 123,
  "chain_pending_id": "p-4821",
  "status": "pending_confirmation",
  "next_available": "2026-03-08T12:00:00Z"
}
```

- `claim_id` — this faucet's local SQLite row id. **Not** a chain reference.
  (It was previously returned as `pending_id`, which invited exactly that
  misreading.)
- `chain_pending_id` — the node's pending-transfer id, or `null` if the node
  did not return one (always `null` under `FAUCET_DRY_RUN=1`).
- `status` — `pending_confirmation`, or `dry_run` when no transfer was made.
  RustChain transfers are two-phase: `ok: true` means the node **accepted**
  the drip into the pending ledger, not that the balance has moved. It
  settles when the confirmer runs (~24h void window).

A drip the node declines returns HTTP 502 with
`{"ok": false, "error": "transfer_failed", "details": {...}}` and does **not**
consume the caller's 24h quota. Declines include the node answering HTTP 200
with `{"ok": false}` (e.g. an empty faucet pool), a non-JSON 200 (an nginx
error page), and an unreachable node.

## Rate limits (24h)

- No auth (IP only): 0.5 RTC
- GitHub user: 1.0 RTC
- GitHub account older than 1 year: 2.0 RTC

## Run

```bash
pip install flask requests
python tools/testnet_faucet.py
```

Then open: `http://127.0.0.1:8090/faucet`

## Config

Environment variables:
- `FAUCET_DB_PATH` (default: `faucet.db`)
- `FAUCET_DRY_RUN` (`1`/`0`, default `1`)
- `FAUCET_ADMIN_TRANSFER_URL`
- `FAUCET_ADMIN_API_TOKEN`
- `FAUCET_POOL_WALLET`
- `GITHUB_TOKEN` (optional, for account-age check)

## Tests

```bash
pytest tests/test_faucet.py -q
```
