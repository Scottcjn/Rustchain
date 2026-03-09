# RustChain API First Call Walkthrough

A practical guide for developers making their first RustChain API calls.

## Quick Start

### Prerequisites
- `curl` or any HTTP client
- Self-signed TLS certificate handling (`-k` flag for curl)

### Base URL
```
https://50.28.86.131
```

**Note**: This node uses a self-signed TLS certificate. Use `-k` flag with curl to skip verification.

---

## Your First API Call: Health Check

The simplest read-only endpoint to verify connectivity:

```bash
curl -k https://50.28.86.131/health
```

**Response:**
```json
{
  "backup_age_hours": 8.91,
  "db_rw": true,
  "ok": true,
  "tip_age_slots": 0,
  "uptime_s": 40560,
  "version": "2.2.1-rip200"
}
```

**Field Explanations:**
- `ok`: Boolean indicating node health
- `db_rw`: Database read/write status
- `uptime_s`: Node uptime in seconds
- `version`: RustChain version (includes RIP-200 support)
- `tip_age_slots`: How many slots behind the chain tip (0 = synced)

---

## Epoch Information

Get current epoch and network stats:

```bash
curl -k https://50.28.86.131/epoch
```

**Response:**
```json
{
  "blocks_per_epoch": 144,
  "enrolled_miners": 21,
  "epoch": 96,
  "epoch_pot": 1.5,
  "slot": 13919,
  "total_supply_rtc": 8388608
}
```

**Field Explanations:**
- `epoch`: Current epoch number
- `slot`: Current slot number (increments every ~10 minutes)
- `blocks_per_epoch`: Slots per epoch (144 = ~24 hours)
- `enrolled_miners`: Active miners in current epoch
- `epoch_pot`: RTC available for distribution this epoch
- `total_supply_rtc`: Total RTC ever minted

---

## Balance Lookup

Check wallet balance using miner ID:

```bash
curl -k "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_ID"
```

**Example:**
```bash
curl -k "https://50.28.86.131/wallet/balance?miner_id=first-butler"
```

**Response:**
```json
{
  "amount_i64": 0,
  "amount_rtc": 0.0,
  "miner_id": "first-butler"
}
```

**Field Explanations:**
- `miner_id`: RustChain wallet identifier (NOT an Ethereum/Solana address)
- `amount_rtc`: Balance in RTC (human-readable decimal)
- `amount_i64`: Balance in smallest unit (1 RTC = 1,000,000 units)

**Important**: RustChain wallet IDs are simple strings (e.g., `my-wallet`), not cryptographic addresses like Ethereum (`0x...`) or Solana (`base58...`).

---

## Signed Transfer Request

### Endpoint
```
POST https://50.28.86.131/wallet/transfer/signed
```

### Request Format

```bash
curl -k -X POST https://50.28.86.131/wallet/transfer/signed \
  -H "Content-Type: application/json" \
  -d '{
    "from_miner_id": "sender-wallet",
    "to_miner_id": "recipient-wallet",
    "amount_i64": 1000000,
    "nonce": 1,
    "signature": "base64_encoded_signature",
    "public_key": "base64_encoded_public_key"
  }'
```

### Field Explanations

| Field | Type | Description |
|-------|------|-------------|
| `from_miner_id` | string | Sender's RustChain wallet ID |
| `to_miner_id` | string | Recipient's RustChain wallet ID |
| `amount_i64` | integer | Transfer amount in smallest unit (1 RTC = 1,000,000) |
| `nonce` | integer | Transaction nonce (increments with each tx from this wallet) |
| `signature` | string | Ed25519 signature (base64) of the transfer payload |
| `public_key` | string | Sender's Ed25519 public key (base64) |

### Signature Generation

The signature is computed over the following payload:

```
from_miner_id|to_miner_id|amount_i64|nonce
```

**Example payload to sign:**
```
alice|bob|1000000|1
```

**Steps:**
1. Concatenate fields with `|` separator
2. Sign with Ed25519 private key
3. Base64-encode the signature
4. Include in request

### Example Response (Success)

```json
{
  "ok": true,
  "tx_hash": "abc123...",
  "new_balance_i64": 5000000
}
```

### Example Response (Error)

```json
{
  "error": "insufficient balance",
  "required": 1000000,
  "available": 500000
}
```

---

## Common Errors & Solutions

### 1. Self-Signed Certificate Error
```
curl: (60) SSL certificate problem: self signed certificate
```

**Solution**: Use `-k` flag to skip verification:
```bash
curl -k https://50.28.86.131/health
```

### 2. Wallet Not Found
```json
{"error": "wallet not found"}
```

**Solution**: Ensure the `miner_id` exists. New wallets are created when they first receive RTC or mine a block.

### 3. Invalid Signature
```json
{"error": "signature verification failed"}
```

**Solution**: 
- Verify payload format: `from|to|amount|nonce`
- Ensure Ed25519 signature algorithm
- Check base64 encoding

### 4. Nonce Mismatch
```json
{"error": "invalid nonce", "expected": 5, "provided": 1}
```

**Solution**: Query current nonce before signing:
```bash
curl -k "https://50.28.86.131/wallet/nonce?miner_id=YOUR_WALLET"
```

---

## Key Differences from Other Blockchains

| Feature | RustChain | Ethereum | Solana |
|---------|-----------|----------|--------|
| **Wallet ID** | Simple string (`alice`) | Hex address (`0x...`) | Base58 (`base58...`) |
| **Signature** | Ed25519 | ECDSA (secp256k1) | Ed25519 |
| **Amount Unit** | Integer (1 RTC = 1M units) | Wei (1 ETH = 10^18) | Lamports (1 SOL = 10^9) |
| **Nonce** | Per-wallet counter | Per-account counter | Recent blockhash |

---

## Next Steps

1. **Create a wallet**: Mine a block or receive RTC from another wallet
2. **Generate Ed25519 keypair**: Use `libsodium`, `tweetnacl`, or similar
3. **Build a transfer**: Sign and submit via `/wallet/transfer/signed`
4. **Monitor transactions**: Query balance to confirm

---

## Resources

- **Node**: https://50.28.86.131
- **GitHub**: https://github.com/Scottcjn/Rustchain
- **Discord**: https://discord.gg/VqVVS2CW9Q
- **Product Issue**: Scottcjn/Rustchain#701

---

**Tested**: 2026-03-09, RustChain v2.2.1-rip200
**Author**: first-butler
