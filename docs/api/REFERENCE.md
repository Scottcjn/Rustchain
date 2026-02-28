# RustChain API Reference

**Base URL:** `https://rustchain.org` (Primary Node)  
**Authentication:** Read-only endpoints are public. Writes require Ed25519 signatures or an Admin Key.  
**Certificate Note:** The node uses a self-signed TLS certificate. Use the `-k` flag with `curl` or disable certificate verification in your client.

---

## 🟢 Public Endpoints

### 1. Node Health
Check the status of the node, database, and sync state.

- **Endpoint:** `GET /health`
- **Response:**
  ```json
  {
    "ok": true,
    "version": "2.2.1-rip200",
    "uptime_s": 97300,
    "db_rw": true,
    "tip_age_slots": 0,
    "backup_age_hours": 16.58
  }
  ```

---

### 2. Epoch Information
Get details about the current mining epoch, slot progress, and rewards.

- **Endpoint:** `GET /epoch`
- **Response:**
  ```json
  {
    "epoch": 75,
    "slot": 10800,
    "blocks_per_epoch": 144,
    "epoch_pot": 1.5,
    "enrolled_miners": 10
  }
  ```

---

### 3. Active Miners
List all miners currently participating in the network with their hardware details.

- **Endpoint:** `GET /api/miners`
- **Response (Array):**
  ```json
  [
    {
      "miner": "wallet_id_string",
      "device_arch": "G4",
      "device_family": "PowerPC",
      "hardware_type": "PowerPC G4 (Vintage)",
      "antiquity_multiplier": 2.5,
      "last_attest": 1771187406
    }
  ]
  ```

---

### 4. Wallet Balance
Query the RTC balance for any valid miner ID.

- **Endpoint:** `GET /wallet/balance?miner_id={NAME}`
- **Example:** `curl -sk 'https://rustchain.org/wallet/balance?miner_id=scott'`
- **Response:**
  ```json
  {
    "ok": true,
    "miner_id": "scott",
    "amount_rtc": 42.5,
    "amount_i64": 42500000
  }
  ```

---

## 🔵 Signed Transactions (Public Write)

### Submit Signed Transfer
Transfer RTC between wallets without requiring an admin key.

- **Endpoint:** `POST /wallet/transfer/signed`
- **Payload:**
  ```json
  {
    "from_address": "RTC...",
    "to_address": "RTC...",
    "amount_rtc": 1.5,
    "nonce": 1771187406,
    "signature": "hex_encoded_signature",
    "public_key": "hex_encoded_pubkey"
  }
  ```
- **Process:** 
  1. Construct JSON payload: `{"from": "...", "to": "...", "amount": 1.5, "nonce": "...", "memo": "..."}`
  2. Sort keys and sign with Ed25519 private key.
  3. Submit with hex-encoded signature.

---

## 🔴 Authenticated Endpoints (Admin Only)

**Required Header:** `X-Admin-Key: {YOUR_ADMIN_KEY}`

### 1. Internal Admin Transfer
Move funds between any two wallets (requires admin authority).

- **Endpoint:** `POST /wallet/transfer`
- **Payload:** `{"from_miner": "A", "to_miner": "B", "amount_rtc": 10.0}`

### 2. Manual Settlement
Manually trigger the epoch settlement process.

- **Endpoint:** `POST /rewards/settle`

---

## ⚠️ Implementation Notes & Common Mistakes

### Field Name Precision
The RustChain API is strict about field names. Common errors include:
- ❌ `miner_id` instead of **`miner`** (in miner object)
- ❌ `current_slot` instead of **`slot`** (in epoch info)
- ❌ `total_miners` instead of **`enrolled_miners`**

### Wallet Formats
Wallets are **simple UTF-8 strings** (1-256 chars).  
- ✅ `my-wallet-name`
- ❌ `0x...` (Ethereum addresses are not native RTC wallets)
- ❌ `4TR...` (Solana addresses must be bridged via BoTTube)

### Certificate Errors
If using `curl`, always include `-k` to bypass the self-signed certificate warning.

---
*Last Updated: February 2026*
