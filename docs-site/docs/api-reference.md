# API Reference

RustChain exposes a REST API for querying network state, managing wallets, submitting attestations, and participating in governance.

**Base URL**: `https://rustchain.org`

!!! note "SSL Certificates"
    The node may use a self-signed SSL certificate. Use `curl -sk` or `verify=False` in Python requests.

---

## Health and Status

### Health Check

Check if the node is online and responsive.

```
GET /health
```

```bash
curl -sk https://rustchain.org/health
```

**Response:**

```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 200000
}
```

### Current Epoch

Get the current epoch, slot, and block height.

```
GET /epoch
```

```bash
curl -sk https://rustchain.org/epoch
```

**Response:**

```json
{
  "epoch": 95,
  "slot": 12345,
  "height": 67890
}
```

---

## Miners

### List Active Miners

Returns all currently active miners on the network.

```
GET /api/miners
```

```bash
curl -sk https://rustchain.org/api/miners
```

---

## Wallet

### Check Balance

Query the balance for a specific wallet.

```
GET /wallet/balance?miner_id={wallet_id}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `miner_id` | string | The RustChain wallet identifier |

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**Response:**

```json
{
  "amount_i64": 155000000,
  "amount_rtc": 155.0,
  "miner_id": "Ivan-houzhiwen"
}
```

### Signed Transfer

Submit a signed RTC transfer between wallets.

```
POST /wallet/transfer/signed
```

**Request Body:**

```json
{
  "from": "sender_wallet_id",
  "to": "recipient_wallet_id",
  "amount": 10,
  "fee": 0.001,
  "signature": "hex_encoded_signature",
  "timestamp": 1234567890
}
```

| Field | Type | Description |
|-------|------|-------------|
| `from` | string | Sender's RustChain wallet ID |
| `to` | string | Recipient's RustChain wallet ID |
| `amount` | integer | Amount in RTC (smallest unit: 1 RTC = 1,000,000 units) |
| `fee` | float | Transaction fee |
| `signature` | hex string | Ed25519 signature of the transfer payload |
| `timestamp` | integer | Unix timestamp for replay protection |

!!! important "Wallet IDs"
    RustChain uses its own wallet system (e.g., `Ivan-houzhiwen`), not Ethereum or Solana addresses.

---

## Governance

### Create Proposal

Submit a governance proposal. The wallet must hold more than 10 RTC.

```
POST /governance/propose
```

```bash
curl -sk -X POST https://rustchain.org/governance/propose \
  -H 'Content-Type: application/json' \
  -d '{
    "wallet": "RTC...",
    "title": "Enable parameter X",
    "description": "Rationale and implementation details"
  }'
```

### List Proposals

```
GET /governance/proposals
```

```bash
curl -sk https://rustchain.org/governance/proposals
```

### Get Proposal Detail

```
GET /governance/proposal/{id}
```

```bash
curl -sk https://rustchain.org/governance/proposal/1
```

### Submit Vote

Votes require an Ed25519 signature. The voter must be an active miner (attested).

```
POST /governance/vote
```

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

**Governance Rules:**

- Proposal lifecycle: `Draft -> Active (7 days) -> Passed/Failed`
- Proposal creation requires wallet balance > 10 RTC
- Voting eligibility: voter must be an active miner
- Vote weight: `1 RTC = 1 base vote`, multiplied by the miner's antiquity multiplier
- Pass condition: `yes_weight > no_weight` at close

### Governance Web UI

A lightweight web interface is available at:

```
GET /governance/ui
```

---

## Block Explorer

The block explorer is available as a web interface:

```
GET /explorer
```

Open [https://rustchain.org/explorer](https://rustchain.org/explorer) in a browser.

---

## x402 Premium Endpoints

Machine-to-machine payment endpoints via the x402 protocol (currently free while proving the flow):

| Endpoint | Description |
|----------|-------------|
| `GET /api/premium/videos` | Bulk video export (BoTTube) |
| `GET /api/premium/analytics/<agent>` | Deep agent analytics (BoTTube) |
| `GET /api/premium/reputation` | Full reputation export (Beacon Atlas) |
| `GET /wallet/swap-info` | USDC/wRTC swap guidance |

---

## Agent Wallets (Coinbase Base)

Create and manage Coinbase Base wallets for agent-to-agent payments:

```bash
# Install with Coinbase support
pip install clawrtc[coinbase]

# Create a Coinbase wallet
clawrtc wallet coinbase create

# Check swap info
clawrtc wallet coinbase swap-info

# Link existing Base address
clawrtc wallet coinbase link 0xYourBaseAddress
```

| Resource | Details |
|----------|---------|
| wRTC on Base | `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6` |
| Swap USDC to wRTC | [Aerodrome DEX](https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6) |
| Base Bridge | [bottube.ai/bridge/base](https://bottube.ai/bridge/base) |

---

## Python Example

```python
import requests

# Check balance
response = requests.get(
    "https://rustchain.org/wallet/balance",
    params={"miner_id": "Ivan-houzhiwen"},
    verify=False
)
print(f"Balance: {response.json()['amount_rtc']} RTC")

# Signed transfer
transfer_data = {
    "from": "sender_wallet",
    "to": "recipient_wallet",
    "amount": 1000000,  # 1 RTC
    "fee": 1000,
    "signature": "...",
    "timestamp": 1234567890
}
response = requests.post(
    "https://rustchain.org/wallet/transfer/signed",
    json=transfer_data,
    verify=False
)
print(response.json())
```

---

## Postman Collection

A full Postman collection is available in the repository:
[RustChain_API.postman_collection.json](https://github.com/Scottcjn/Rustchain/blob/main/RustChain_API.postman_collection.json)

---

## Live Infrastructure

| Endpoint | URL |
|----------|-----|
| Node Health | `https://rustchain.org/health` |
| Active Miners | `https://rustchain.org/api/miners` |
| Current Epoch | `https://rustchain.org/epoch` |
| Block Explorer | `https://rustchain.org/explorer` |
| wRTC Bridge | `https://bottube.ai/bridge` |

| Node | IP | Role |
|------|----|------|
| Node 1 | 50.28.86.131 | Primary + Explorer |
| Node 2 | 50.28.86.153 | Ergo Anchor |
| Node 3 | 76.8.228.245 | Community Node |
