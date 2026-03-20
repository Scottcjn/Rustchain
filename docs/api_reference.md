# RustChain API Reference

## Base URL

```
http://localhost:5000
```

## Authentication

RustChain uses a simple authentication token system. Include the `Authorization` header with your requests:

```
Authorization: Bearer <your_token>
```

## Response Format

All API responses follow a consistent JSON format:

```json
{
  "success": true,
  "data": {...},
  "message": "Optional message",
  "timestamp": 1640995200
}
```

Error responses:

```json
{
  "success": false,
  "error": "Error description",
  "code": "ERROR_CODE",
  "timestamp": 1640995200
}
```

## Error Codes

| Code | Description |
|------|-------------|
| `INVALID_REQUEST` | Malformed request or missing parameters |
| `UNAUTHORIZED` | Invalid or missing authentication token |
| `FORBIDDEN` | Insufficient permissions |
| `NOT_FOUND` | Resource not found |
| `RATE_LIMITED` | Too many requests |
| `INTERNAL_ERROR` | Server error |
| `CHAIN_ERROR` | Blockchain operation failed |
| `INSUFFICIENT_BALANCE` | Not enough RTC tokens |
| `INVALID_SIGNATURE` | Transaction signature verification failed |

## Endpoints

### Node Information

#### GET /api/node/info

Get basic node information and status.

**Request:**
```bash
curl -X GET http://localhost:5000/api/node/info \
  -H "Authorization: Bearer your_token_here"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "node_id": "node_8a2f9c1d",
    "version": "2.2.1",
    "network": "mainnet",
    "status": "active",
    "block_height": 15420,
    "peers": 12,
    "uptime": 86400,
    "last_block": "2024-01-15T10:30:00Z"
  }
}
```

**Python Example:**
```python
import requests

url = "http://localhost:5000/api/node/info"
headers = {"Authorization": "Bearer your_token_here"}

response = requests.get(url, headers=headers)
data = response.json()

print(f"Node ID: {data['data']['node_id']}")
print(f"Block Height: {data['data']['block_height']}")
```

#### GET /api/node/peers

List connected peers.

**Request:**
```bash
curl -X GET http://localhost:5000/api/node/peers \
  -H "Authorization: Bearer your_token_here"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "peers": [
      {
        "id": "peer_1a2b3c4d",
        "address": "192.168.1.100:8080",
        "connected_at": "2024-01-15T09:15:30Z",
        "last_seen": "2024-01-15T10:29:45Z",
        "version": "2.2.0"
      }
    ],
    "total": 1
  }
}
```

### Blockchain Operations

#### GET /api/chain/status

Get current blockchain status.

**Request:**
```bash
curl -X GET http://localhost:5000/api/chain/status
```

**Response:**
```json
{
  "success": true,
  "data": {
    "height": 15420,
    "hash": "00000a1b2c3d4e5f6789abcdef012345",
    "difficulty": 1024,
    "total_transactions": 87539,
    "circulation": 1000000.50,
    "last_block_time": "2024-01-15T10:30:00Z"
  }
}
```

#### GET /api/chain/block/{height}

Get block by height.

**Parameters:**
- `height` (integer): Block height

**Request:**
```bash
curl -X GET http://localhost:5000/api/chain/block/15420
```

**Response:**
```json
{
  "success": true,
  "data": {
    "height": 15420,
    "hash": "00000a1b2c3d4e5f6789abcdef012345",
    "prev_hash": "00000fedcba9876543210fedcba98765",
    "timestamp": "2024-01-15T10:30:00Z",
    "miner": "miner_5x9y2z8a",
    "difficulty": 1024,
    "nonce": 187456,
    "transactions": [
      {
        "hash": "tx_abc123def456",
        "from": "wallet_sender123",
        "to": "wallet_receiver456",
        "amount": 100.0,
        "fee": 0.01
      }
    ],
    "transaction_count": 1
  }
}
```

#### GET /api/chain/transaction/{hash}

Get transaction by hash.

**Parameters:**
- `hash` (string): Transaction hash

**Request:**
```bash
curl -X GET http://localhost:5000/api/chain/transaction/tx_abc123def456
```

**Response:**
```json
{
  "success": true,
  "data": {
    "hash": "tx_abc123def456",
    "from": "wallet_sender123",
    "to": "wallet_receiver456",
    "amount": 100.0,
    "fee": 0.01,
    "timestamp": "2024-01-15T10:29:30Z",
    "block_height": 15420,
    "confirmations": 5,
    "status": "confirmed",
    "signature": "304502210..."
  }
}
```

### Wallet Operations

#### GET /api/wallet/{address}/balance

Get wallet balance.

**Parameters:**
- `address` (string): Wallet address

**Request:**
```bash
curl -X GET http://localhost:5000/api/wallet/wallet_123abc456def/balance \
  -H "Authorization: Bearer your_token_here"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "address": "wallet_123abc456def",
    "balance": 250.75,
    "pending": 10.0,
    "total_received": 500.25,
    "total_sent": 249.50,
    "transaction_count": 15
  }
}
```

#### GET /api/wallet/{address}/transactions

Get wallet transaction history.

**Parameters:**
- `address` (string): Wallet address
- `limit` (integer, optional): Number of transactions to return (default: 20)
- `offset` (integer, optional): Pagination offset (default: 0)

**Request:**
```bash
curl -X GET "http://localhost:5000/api/wallet/wallet_123abc456def/transactions?limit=10&offset=0" \
  -H "Authorization: Bearer your_token_here"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "transactions": [
      {
        "hash": "tx_def456abc123",
        "type": "received",
        "from": "wallet_sender789",
        "to": "wallet_123abc456def",
        "amount": 50.0,
        "fee": 0.01,
        "timestamp": "2024-01-15T09:45:20Z",
        "confirmations": 12
      }
    ],
    "total": 15,
    "limit": 10,
    "offset": 0
  }
}
```

#### POST /api/wallet/transaction/create

Create a new transaction.

**Request Body:**
```json
{
  "from": "wallet_sender123",
  "to": "wallet_receiver456",
  "amount": 25.50,
  "fee": 0.01,
  "private_key": "your_private_key_here"
}
```

**Request:**
```bash
curl -X POST http://localhost:5000/api/wallet/transaction/create \
  -H "Authorization: Bearer your_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "wallet_sender123",
    "to": "wallet_receiver456",
    "amount": 25.50,
    "fee": 0.01,
    "private_key": "your_private_key_here"
  }'
```

**Python Example:**
```python
import requests

url = "http://localhost:5000/api/wallet/transaction/create"
headers = {
    "Authorization": "Bearer your_token_here",
    "Content-Type": "application/json"
}
payload = {
    "from": "wallet_sender123",
    "to": "wallet_receiver456",
    "amount": 25.50,
    "fee": 0.01,
    "private_key": "your_private_key_here"
}

response = requests.post(url, headers=headers, json=payload)
result = response.json()

if result['success']:
    print(f"Transaction created: {result['data']['hash']}")
else:
    print(f"Error: {result['error']}")
```

**Response:**
```json
{
  "success": true,
  "data": {
    "hash": "tx_new789ghi012",
    "from": "wallet_sender123",
    "to": "wallet_receiver456",
    "amount": 25.50,
    "fee": 0.01,
    "timestamp": "2024-01-15T10:31:15Z",
    "status": "pending"
  }
}
```

### Mining Operations

#### GET /api/mining/status

Get mining status and statistics.

**Request:**
```bash
curl -X GET http://localhost:5000/api/mining/status \
  -H "Authorization: Bearer your_token_here"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "is_mining": true,
    "miner_id": "miner_5x9y2z8a",
    "hashrate": 1250000,
    "difficulty": 1024,
    "blocks_mined": 42,
    "total_rewards": 420.0,
    "last_block": "2024-01-15T10:30:00Z",
    "uptime": 3600
  }
}
```

#### POST /api/mining/start

Start mining operations.

**Request Body:**
```json
{
  "miner_address": "wallet_miner123abc",
  "threads": 4
}
```

**Request:**
```bash
curl -X POST http://localhost:5000/api/mining/start \
  -H "Authorization: Bearer your_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "miner_address": "wallet_miner123abc",
    "threads": 4
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "mining_started",
    "miner_id": "miner_5x9y2z8a",
    "threads": 4,
    "started_at": "2024-01-15T10:32:00Z"
  }
}
```

#### POST /api/mining/stop

Stop mining operations.

**Request:**
```bash
curl -X POST http://localhost:5000/api/mining/stop \
  -H "Authorization: Bearer your_token_here"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "mining_stopped",
    "stopped_at": "2024-01-15T10:33:00Z",
    "session_duration": 60,
    "blocks_mined": 0
  }
}
```

### Attestation Services

#### GET /api/attestation/status

Get attestation node status.

**Request:**
```bash
curl -X GET http://localhost:5000/api/attestation/status \
  -H "Authorization: Bearer your_token_here"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "is_active": true,
    "attestations_processed": 1523,
    "last_attestation": "2024-01-15T10:30:45Z",
    "reputation_score": 95.5,
    "node_id": "attestor_9z8y7x6w",
    "uptime": 43200
  }
}
```

#### POST /api/attestation/create

Create new attestation.

**Request Body:**
```json
{
  "data_hash": "sha256_hash_here",
  "attestor_id": "attestor_9z8y7x6w",
  "metadata": {
    "type": "document",
    "timestamp": "2024-01-15T10:32:00Z"
  }
}
```

**Request:**
```bash
curl -X POST http://localhost:5000/api/attestation/create \
  -H "Authorization: Bearer your_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "data_hash": "sha256_hash_here",
    "attestor_id": "attestor_9z8y7x6w",
    "metadata": {
      "type": "document",
      "timestamp": "2024-01-15T10:32:00Z"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "attestation_id": "attest_abc123def456",
    "data_hash": "sha256_hash_here",
    "attestor_id": "attestor_9z8y7x6w",
    "created_at": "2024-01-15T10:32:00Z",
    "status": "active"
  }
}
```

## Rate Limiting

API requests are limited to:
- 100 requests per minute for general endpoints
- 10 requests per minute for transaction creation
- 5 requests per minute for mining operations

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995260
```

## SDK Examples

### Python SDK

```python
import requests
import json
from datetime import datetime

class RustChainAPI:
    def __init__(self, base_url="http://localhost:5000", token=None):
        self.base_url = base_url
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    def get_node_info(self):
        response = requests.get(f"{self.base_url}/api/node/info", headers=self.headers)
        return response.json()

    def get_balance(self, address):
        response = requests.get(f"{self.base_url}/api/wallet/{address}/balance", headers=self.headers)
        return response.json()

    def create_transaction(self, from_addr, to_addr, amount, fee, private_key):
        payload = {
            "from": from_addr,
            "to": to_addr,
            "amount": amount,
            "fee": fee,
            "private_key": private_key
        }
        headers = {**self.headers, "Content-Type": "application/json"}
        response = requests.post(f"{self.base_url}/api/wallet/transaction/create",
                               headers=headers, json=payload)
        return response.json()

# Usage
api = RustChainAPI(token="your_token_here")
node_info = api.get_node_info()
print(f"Connected to node {node_info['data']['node_id']}")

balance = api.get_balance("wallet_123abc456def")
print(f"Balance: {balance['data']['balance']} RTC")
```

### JavaScript/Node.js SDK

```javascript
const axios = require('axios');

class RustChainAPI {
    constructor(baseUrl = 'http://localhost:5000', token = null) {
        this.baseUrl = baseUrl;
        this.token = token;
        this.headers = token ? { 'Authorization': `Bearer ${token}` } : {};
    }

    async getNodeInfo() {
        const response = await axios.get(`${this.baseUrl}/api/node/info`, { headers: this.headers });
        return response.data;
    }

    async getBalance(address) {
        const response = await axios.get(`${this.baseUrl}/api/wallet/${address}/balance`, { headers: this.headers });
        return response.data;
    }

    async createTransaction(from, to, amount, fee, privateKey) {
        const payload = { from, to, amount, fee, private_key: privateKey };
        const headers = { ...this.headers, 'Content-Type': 'application/json' };
        const response = await axios.post(`${this.baseUrl}/api/wallet/transaction/create`, payload, { headers });
        return response.data;
    }
}

// Usage
const api = new RustChainAPI('http://localhost:5000', 'your_token_here');

api.getNodeInfo().then(info => {
    console.log(`Connected to node ${info.data.node_id}`);
});
```

## Testing

Test API endpoints using the provided examples. Ensure your node is running and accessible before making requests.

For development, you can disable authentication by setting `AUTH_REQUIRED=false` in your environment variables.

## WebSocket API

RustChain also provides real-time updates via WebSocket connections:

```javascript
const ws = new WebSocket('ws://localhost:5000/ws');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    if (data.type === 'new_block') {
        console.log('New block mined:', data.block);
    }
};

// Subscribe to events
ws.send(JSON.stringify({
    action: 'subscribe',
    events: ['new_block', 'new_transaction']
}));
```

## Support

For API support and questions:
- GitHub Issues: [github.com/Scottcjn/Rustchain/issues](https://github.com/Scottcjn/Rustchain/issues)
- Documentation: [docs/](../docs/)
- Community: RustChain Discord
