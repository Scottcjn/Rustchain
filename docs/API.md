## GET /wallet/history

Returns transaction history for a wallet.

**Parameters:**
- `wallet` (string, required): Wallet address to query

**Response:**
```json
{
  "ok": true,
  "miner_id": "node123",
  "transactions": [
    {
      "tx_id": "abc123",
      "amount": 1.5,
      "timestamp": 1234567890,
      "direction": "in"
    }
  ],
  "total": 1
}
```

**Fields:**
- `ok`: Boolean indicating success
- `miner_id`: Node identifier
- `transactions`: Array of transaction objects
  - `tx_id`: Transaction hash
  - `amount`: Transaction amount
  - `timestamp`: Unix timestamp
  - `direction`: "in" or "out"
- `total`: Total number of transactions