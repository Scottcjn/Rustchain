# RustChain API Reference

Complete API reference for RustChain node.

## Base URL

```
https://50.28.86.131
```

Note: Use `-k` flag with curl to accept self-signed SSL certificates.

---

## Health Check

### GET /health

Check node health status.

**curl:**
```bash
curl -sk https://50.28.86.131/health
```

**Response:**
```json
{
  "status": "ok",
  "epoch": 42,
  "timestamp": 1700000000
}
```

---

## Epoch Info

### GET /epoch

Get current epoch information.

**curl:**
```bash
curl -sk https://50.28.86.131/epoch
```

**Response:**
```json
{
  "epoch": 42,
  "slot": 100,
  "blocks_per_epoch": 144,
  "epoch_pot": 1.5,
  "enrolled_miners": 9,
  "progress": 69.4
}
```

---

## Miners

### GET /api/miners

Get list of all active miners.

**curl:**
```bash
curl -sk https://50.28.86.131/api/miners
```

**Response:**
```json
{
  "miners": [
    {
      "miner_id": "wallet_name",
      "hardware": "PowerPC G4",
      "antiquity_multiplier": 2.5,
      "balance": 10.5,
      "attestations": 100,
      "uptime": 86400
    }
  ]
}
```

---

## Wallet

### GET /wallet/balance?miner_id=<miner_id>

Get balance for a specific miner.

**curl:**
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=my_wallet"
```

**Response:**
```json
{
  "miner_id": "my_wallet",
  "balance": 10.5,
  "today_earnings": 0.5
}
```

---

## Attestation

### POST /attest/submit

Submit an attestation.

**curl:**
```bash
curl -sk -X POST https://50.28.86.131/attest/submit \
  -H "Content-Type: application/json" \
  -d '{
    "miner_id": "my_wallet",
    "nonce": "random_nonce",
    "timestamp": 1700000000,
    "fingerprint": {...}
  }'
```

---

## Explorer

### GET /explorer

Block explorer main page.

**curl:**
```bash
curl -sk https://50.28.86.131/explorer
```

---

## Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Node health |
| `/epoch` | GET | Epoch info |
| `/api/miners` | GET | List miners |
| `/wallet/balance` | GET | Get balance |
| `/attest/submit` | POST | Submit attestation |
| `/explorer` | GET | Block explorer |
