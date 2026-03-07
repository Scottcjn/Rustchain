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
  "pending_id": 123,
  "next_available": "2026-03-08T12:00:00Z"
}
```

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
