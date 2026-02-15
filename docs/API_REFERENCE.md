# RustChain API Reference

Complete API documentation for RustChain blockchain.

## Base URL

```
https://50.28.86.131
```

**Note:** SSL verification is disabled by default.

---

## Node Endpoints

### GET /health

Check node health status.

**Request:**
```bash
curl -sk https://50.28.86.131/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-16T03:00:00Z"
}
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| status | string | Node status (healthy, degraded, unhealthy) |
| timestamp | string | ISO 8601 timestamp |

---

### GET /ready

Check if node is ready to accept requests.

**Request:**
```bash
curl -sk https://50.28.86.131/ready
```

**Response:**
```json
{
  "ready": true,
  "components": {
    "database": "ok",
    "network": "ok",
    "storage": "ok"
  }
}
```

---

### GET /epoch

Get current epoch information.

**Request:**
```bash
curl -sk https://50.28.86.131/epoch
```

**Response:**
```json
{
  "epoch": 177,
  "start_time": "2026-02-16T00:00:00Z",
  "end_time": "2026-02-16T01:00:00Z",
  "total_attestations": 1500,
  "rewards_distributed": 4500.75
}
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| epoch | integer | Current epoch number |
| start_time | string | Epoch start time (ISO 8601) |
| end_time | string | Epoch end time (ISO 8601) |
| total_attestations | integer | Number of attestations this epoch |
| rewards_distributed | number | Total RTC distributed |

---

## Miner Endpoints

### GET /api/miners

Get list of active miners.

**Request:**
```bash
curl -sk https://50.28.86.131/api/miners
```

**Response:**
```json
[
  {
    "miner": "eafc6f14abc123...",
    "device_arch": "G4",
    "device_family": "PowerPC",
    "antiquity_multiplier": 2.5,
    "last_attest": 1771013121,
    "epochs_active": 1200
  },
  {
    "miner": "g5selenaabc123...",
    "device_arch": "G5",
    "device_family": "PowerPC",
    "antiquity_multiplier": 2.0,
    "last_attest": 1771013100,
    "epochs_active": 1100
  }
]
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| miner | string | Miner wallet address |
| device_arch | string | CPU architecture (G4, G5, x86_64, etc.) |
| device_family | string | Device family name |
| antiquity_multiplier | number | PoA multiplier based on hardware age |
| last_attest | integer | Unix timestamp of last attestation |
| epochs_active | integer | Number of epochs participated |

---

## Wallet Endpoints

### GET /wallet/balance

Get wallet balance.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| miner_id | string | Yes | Wallet address to check |

**Request:**
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=0x1234..."
```

**Response:**
```json
{
  "miner_id": "0x1234...",
  "balance": 150.75,
  "pending_rewards": 5.25,
  "total_earned": 156.0
}
```

---

### POST /wallet/transfer/signed

Transfer RTC tokens (requires Ed25519 signature).

**Request Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "from": "0xsender...",
  "to": "0xreceiver...",
  "amount": 10.5,
  "signature": "base64-encoded-signature",
  "public_key": "base64-encoded-public-key"
}
```

**Response:**
```json
{
  "tx_hash": "0xabc123...",
  "status": "pending",
  "timestamp": "2026-02-16T03:00:00Z"
}
```

**Error Response (400):**
```json
{
  "error": "invalid_signature",
  "message": "Signature verification failed"
}
```

---

## Attestation Endpoints

### POST /attest/submit

Submit attestation proof.

**Request Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "miner_id": "0x1234...",
  "block_hash": "0xabc...",
  "signature": "base64-encoded-signature",
  "timestamp": 1771013121
}
```

**Response:**
```json
{
  "attestation_id": "att_12345",
  "status": "accepted",
  "epoch": 177,
  "rewards": 2.5
}
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad request - Invalid parameters |
| 401 | Unauthorized - Missing or invalid signature |
| 403 | Forbidden - Signature verification failed |
| 404 | Not found - Resource doesn't exist |
| 429 | Rate limited - Too many requests |
| 500 | Internal server error |
| 503 | Service unavailable |

---

## Rate Limits

| Endpoint | Rate Limit |
|----------|------------|
| /health | 100 req/min |
| /epoch | 60 req/min |
| /api/miners | 30 req/min |
| /wallet/* | 20 req/min |
| /attest/* | 10 req/min |

---

## Example: Complete Python Client

```python
import requests

class RustChainClient:
    def __init__(self, base_url="https://50.28.86.131", verify_ssl=False):
        self.base_url = base_url
        self.verify_ssl = verify_ssl
    
    def health(self):
        return requests.get(f"{self.base_url}/health", verify=self.verify_ssl).json()
    
    def epoch(self):
        return requests.get(f"{self.base_url}/epoch", verify=self.verify_ssl).json()
    
    def miners(self):
        return requests.get(f"{self.base_url}/api/miners", verify=self.verify_ssl).json()
    
    def balance(self, miner_id):
        return requests.get(
            f"{self.base_url}/wallet/balance",
            params={"miner_id": miner_id},
            verify=self.verify_ssl
        ).json()
```

---

*Document Version: 1.0*  
*Last Updated: 2026-02-16*  
*Contributors: @dunyuzoush-ch*
