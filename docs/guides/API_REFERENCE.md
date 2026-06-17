# RustChain API Reference

Complete reference for the RustChain node API. Base URL: `https://50.28.86.131`

## Health

**GET** `/health`

Returns node health status.

```bash
curl https://50.28.86.131/health
```

Response:
```json
{
  "status": "ok",
  "data": {
    "service": "rustchain-node",
    "uptime": 86400,
    "timestamp": "2026-06-17T00:00:00Z"
  }
}
```

## Epoch

**GET** `/epoch`

Current epoch number and reward pool.

```bash
curl https://50.28.86.131/epoch
```

Response:
```json
{
  "epoch": 1523,
  "reward_pool": 1.5,
  "block_time": 600
}
```

## Miners

**GET** `/api/miners`

List of active miners with hardware profiles.

```bash
curl https://50.28.86.131/api/miners
```

Response:
```json
{
  "miners": [
    {
      "miner_id": "g4-miner",
      "hardware": "PowerPC G4",
      "multiplier": 2.5,
      "attestations": 1440,
      "last_seen": "2026-06-17T00:00:00Z"
    }
  ]
}
```

## Wallet Balance

**GET** `/wallet/balance?miner_id=<id>`

Check wallet balance.

```bash
curl "https://50.28.86.131/wallet/balance?miner_id=my-wallet"
```

Response:
```json
{
  "miner_id": "my-wallet",
  "amount_rtc": 12.5,
  "amount_i64": 12500
}
```

## Attestation Submit

**POST** `/api/attest`

Submit hardware attestation for mining.

```bash
curl -X POST https://50.28.86.131/api/attest \
  -H "Content-Type: application/json" \
  -d '{"miner_id": "my-wallet", "fingerprint": {...}}'
```

## Lottery

**GET** `/api/lottery?miner_id=<id>`

Check lottery eligibility.

```bash
curl "https://50.28.86.131/api/lottery?miner_id=my-wallet"
```

## Payouts

**GET** `/payouts.json`

Global payout statistics.

```bash
curl https://50.28.86.131/payouts.json
```

Response:
```json
{
  "total_paid_rtc_exact": 66752.6,
  "transactions": 3340,
  "unique_recipients": 1073,
  "updated_at": "2026-06-17T17:07:01Z"
}
```

## Transfer

**POST** `/wallet/transfer`

Transfer RTC between wallets (requires admin key).

```bash
curl -X POST https://50.28.86.131/wallet/transfer \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin-key>" \
  -d '{"from_wallet": "fund", "to_wallet": "recipient", "amount": "5.0"}'
```

## Hall of Fame

**GET** `/api/hall-of-fame`

Top miners by contribution.

```bash
curl https://50.28.86.131/api/hall-of-fame
```

## Fee Pool

**GET** `/api/fee-pool`

Current fee pool balance.

```bash
curl https://50.28.86.131/api/fee-pool
```

## Tokenomics

**GET** `/api/tokenomics`

Current tokenomics data including reference rate.

```bash
curl https://50.28.86.131/api/tokenomics
```

## Error Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request - check your parameters |
| 401 | Unauthorized - admin key required for transfer |
| 404 | Wallet or resource not found |
| 500 | Internal node error |
