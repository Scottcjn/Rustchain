# API Reference

RustChain exposes a REST API over HTTPS. The node uses a self-signed certificate, so pass `-sk` flags to `curl` or set `verify=False` in Python requests.

**Base URL**: `https://rustchain.org`

## Authentication

Most endpoints are public. Admin endpoints require the `X-Admin-Key` header:

```bash
curl -sk -H "X-Admin-Key: YOUR_ADMIN_KEY" https://rustchain.org/admin/...
```

---

## Health & Status

### GET /health

Check node health.

```bash
curl -sk https://rustchain.org/health
```

**Response:**

```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 4313,
  "db_rw": true,
  "backup_age_hours": 17.15,
  "tip_age_slots": 0
}
```

| Field | Type | Description |
|---|---|---|
| `ok` | boolean | Node is healthy |
| `version` | string | Node software version |
| `uptime_s` | integer | Seconds since node start |
| `db_rw` | boolean | Database is read/write |
| `backup_age_hours` | float | Hours since last backup |
| `tip_age_slots` | integer | Slots behind tip (0 = synced) |

### GET /ready

Kubernetes-style readiness probe.

```bash
curl -sk https://rustchain.org/ready
```

```json
{
  "ready": true
}
```

---

## Epoch Information

### GET /epoch

Get current epoch and slot information.

```bash
curl -sk https://rustchain.org/epoch
```

**Response:**

```json
{
  "epoch": 75,
  "slot": 10800,
  "blocks_per_epoch": 144,
  "epoch_pot": 1.5,
  "enrolled_miners": 10
}
```

| Field | Type | Description |
|---|---|---|
| `epoch` | integer | Current epoch number |
| `slot` | integer | Current slot within epoch |
| `blocks_per_epoch` | integer | Slots per epoch (144) |
| `epoch_pot` | float | RTC reward pool for this epoch |
| `enrolled_miners` | integer | Active miners this epoch |

---

## Miners

### GET /api/miners

List all active miners.

```bash
curl -sk https://rustchain.org/api/miners
```

**Response:**

```json
[
  {
    "miner_id": "abc123RTC",
    "hardware": "PowerPC G4",
    "multiplier": 2.5,
    "enrolled_epoch": 75
  }
]
```

---

## Wallets

### GET /wallet/balance

Check wallet balance.

| Parameter | Type | Description |
|---|---|---|
| `miner_id` | string | Wallet ID (query parameter) |

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET"
```

**Response:**

```json
{
  "amount_i64": 155000000,
  "amount_rtc": 155.0,
  "miner_id": "YOUR_WALLET"
}
```

!!! note
    RustChain uses its own wallet ID system (e.g., `Ivan-houzhiwen`), not Ethereum or Solana addresses. 1 RTC = 1,000,000 smallest units.

### POST /wallet/transfer/signed

Submit a signed transfer.

```bash
curl -sk -X POST https://rustchain.org/wallet/transfer/signed \
  -H 'Content-Type: application/json' \
  -d '{
    "from": "sender_wallet_id",
    "to": "recipient_wallet_id",
    "amount": 1000000,
    "fee": 1000,
    "signature": "hex_encoded_ed25519_signature",
    "timestamp": 1234567890
  }'
```

| Field | Type | Description |
|---|---|---|
| `from` | string | Sender's RustChain wallet ID |
| `to` | string | Recipient's RustChain wallet ID |
| `amount` | integer | Amount in smallest units (1 RTC = 1,000,000) |
| `fee` | float | Transaction fee |
| `signature` | hex string | Ed25519 signature of the transfer payload |
| `timestamp` | integer | Unix timestamp (replay protection) |

---

## Attestation

### POST /attest/submit

Submit a hardware attestation. Called automatically by the miner client.

```bash
curl -sk -X POST https://rustchain.org/attest/submit \
  -H 'Content-Type: application/json' \
  -d '{
    "miner_id": "abc123RTC",
    "timestamp": 1770112912,
    "fingerprint": { ... },
    "signature": "hex_signature"
  }'
```

**Success response:**

```json
{
  "enrolled": true,
  "multiplier": 2.5
}
```

**Failure response:**

```json
{
  "error": "VM_DETECTED"
}
```

---

## Governance

### POST /governance/propose

Create a governance proposal. The submitting wallet must hold more than 10 RTC.

```bash
curl -sk -X POST https://rustchain.org/governance/propose \
  -H 'Content-Type: application/json' \
  -d '{
    "wallet": "RTC...",
    "title": "Enable parameter X",
    "description": "Rationale and implementation details"
  }'
```

### GET /governance/proposals

List all governance proposals.

```bash
curl -sk https://rustchain.org/governance/proposals
```

### GET /governance/proposal/{id}

Get details of a specific proposal.

```bash
curl -sk https://rustchain.org/governance/proposal/1
```

### POST /governance/vote

Submit a signed vote. The voter must be an active miner.

```bash
curl -sk -X POST https://rustchain.org/governance/vote \
  -H 'Content-Type: application/json' \
  -d '{
    "proposal_id": 1,
    "wallet": "RTC...",
    "vote": "yes",
    "nonce": "1700000000",
    "public_key": "<ed25519_pubkey_hex>",
    "signature": "<ed25519_signature_hex>"
  }'
```

**Voting rules:**

- Proposal lifecycle: `Draft -> Active (7 days) -> Passed/Failed`
- Vote weight: 1 RTC = 1 base vote, multiplied by the miner's antiquity multiplier
- Pass condition: `yes_weight > no_weight` at close

---

## x402 Premium Endpoints

Machine-to-machine payment endpoints using the HTTP 402 protocol (currently free while proving the flow):

| Endpoint | Description |
|---|---|
| `GET /api/premium/videos` | Bulk video export (BoTTube) |
| `GET /api/premium/analytics/<agent>` | Deep agent analytics (BoTTube) |
| `GET /api/premium/reputation` | Full reputation export (Beacon Atlas) |
| `GET /wallet/swap-info` | USDC/wRTC swap guidance |

---

## Python Example

```python
import requests

# Check balance
response = requests.get(
    "https://rustchain.org/wallet/balance",
    params={"miner_id": "my-wallet"},
    verify=False
)
print(f"Balance: {response.json()['amount_rtc']} RTC")

# Transfer (requires Ed25519 signature)
transfer = {
    "from": "sender_wallet",
    "to": "recipient_wallet",
    "amount": 1000000,  # 1 RTC
    "fee": 1000,
    "signature": "...",
    "timestamp": 1234567890
}
response = requests.post(
    "https://rustchain.org/wallet/transfer/signed",
    json=transfer,
    verify=False
)
print(response.json())
```

---

## Reference

| Resource | URL |
|---|---|
| Live node | `https://rustchain.org` |
| Block explorer | `https://rustchain.org/explorer` |
| Health check | `https://rustchain.org/health` |
| Postman collection | [`RustChain_API.postman_collection.json`](https://github.com/Scottcjn/Rustchain/blob/main/RustChain_API.postman_collection.json) |
