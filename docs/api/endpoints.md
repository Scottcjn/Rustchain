# RustChain API Reference

Comprehensive guide to all public endpoints for the RustChain attestation network.

## Base URL
`https://50.28.86.131`

---

## 🔐 Attestation & Consensus

### `POST /attest/challenge`
Request a new nonce for hardware attestation.
- **Request:** `{}`
- **Response:** `{"nonce": "string"}`

### `POST /attest/submit`
Submit hardware fingerprint and entropy for validation.
- **Payload:**
```json
{
  "miner": "RTC...",
  "nonce": "nonce_from_challenge",
  "device": { "arch": "modern", "cores": 8 },
  "fingerprint": { "checks": { ... } }
}
```
- **Response:** `{"ok": true, "status": "accepted"}`

---

## 💰 Wallet & Ledger

### `GET /balance/<address>`
Check the confirmed RTC balance of a wallet.
- **Response:** `{"balance_rtc": 12.5, "miner_id": "RTC..."}`

### `GET /wallet/balance?miner_id=<id>`
Alternative balance check using Miner ID.
- **Response:** `{"amount_rtc": 12.5}`

### `GET /wallet/ledger?miner_id=<id>`
Fetch the transaction history for a specific wallet.
- **Response:** `{"transactions": [...]}`

### `POST /wallet/transfer/signed`
Submit a signed Ed25519 transaction.
- **Payload:**
```json
{
  "from_address": "RTC...",
  "to_address": "RTC...",
  "amount_rtc": 1.0,
  "nonce": 123456789,
  "signature": "hex_sig",
  "public_key": "hex_pubkey"
}
```

---

## ⛏️ Network & Epochs

### `GET /epoch`
Current network state and reward pot.
- **Response:** `{"epoch": 69, "slot": 9980, "epoch_pot": 1.5}`

### `GET /api/miners`
List of all currently attesting miners and their multipliers.
- **Response:** `[{"miner": "ID", "antiquity_multiplier": 2.5}, ...]`

### `GET /health`
Verify node uptime and sync status.
- **Response:** `{"status": "online", "sync": true}`
