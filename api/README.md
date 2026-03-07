# RustChain API Server - Bounty #695 Rework

## Overview

This is a production-ready Flask-based API server providing real-time integration with the RustChain network. It serves as a proxy layer between frontend applications and the upstream RustChain node API, with proper error handling, input validation, and rate limiting.

**Key Features:**
- ✅ **Real API Integration** - No mock data, all endpoints proxy to live RustChain nodes
- ✅ **Robust Error Handling** - Comprehensive error handling with appropriate HTTP status codes
- ✅ **Input Validation** - Marshmallow-based schema validation for all inputs
- ✅ **Rate Limiting** - Built-in rate limiting to prevent abuse (100 req/min default)
- ✅ **Frontend Dashboard** - Modern, responsive network explorer UI
- ✅ **Production Ready** - Gunicorn support, proper logging, health checks

## Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│   Frontend UI   │────▶│  Flask API Server    │────▶│  RustChain Node │
│  (index.html)   │     │  (api_server.py)     │     │  (upstream)     │
└─────────────────┘     └──────────────────────┘     └─────────────────┘
                              │
                              ├─ Rate Limiter
                              ├─ Input Validation
                              └─ Error Handling
```

## Installation

### Prerequisites

- Python 3.9+
- pip (Python package manager)

### Quick Start

```bash
# Navigate to API directory
cd api

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export RUSTCHAIN_API_BASE="https://rustchain.org"
export RUSTCHAIN_API_TIMEOUT="10"
export PORT="8080"

# Run the server
python api_server.py
```

### Production Deployment (Gunicorn)

```bash
# Install gunicorn (already in requirements.txt)
pip install gunicorn

# Run with 4 workers
gunicorn -w 4 -b 0.0.0.0:8080 api_server:app

# Or with more tuning
gunicorn -w 4 \
  --threads 2 \
  --worker-class sync \
  --timeout 30 \
  --keep-alive 5 \
  -b 0.0.0.0:8080 \
  api_server:app
```

## Configuration

All configuration is done via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `RUSTCHAIN_API_BASE` | `https://rustchain.org` | Upstream RustChain node URL |
| `RUSTCHAIN_API_TIMEOUT` | `10` | Request timeout in seconds |
| `PORT` | `8080` | Server port |
| `HOST` | `0.0.0.0` | Server bind address |
| `FLASK_DEBUG` | `false` | Enable debug mode |
| `RATE_LIMIT_REQUESTS` | `100` | Max requests per window |
| `RATE_LIMIT_WINDOW` | `60` | Rate limit window (seconds) |
| `ADMIN_TOKEN` | (none) | Admin token for protected endpoints |

## API Endpoints

### Server Endpoints

#### `GET /health`
Health check for this API server.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "uptime_seconds": 3600,
  "version": "1.0.0",
  "upstream_base": "https://rustchain.org"
}
```

#### `GET /dashboard`
Serves the network explorer frontend dashboard.

### Proxy Endpoints

#### `GET /api/health`
Proxy to upstream node health endpoint.

**Response:**
```json
{
  "success": true,
  "data": {
    "ok": true,
    "uptime_s": 86400,
    "version": "2.2.1-rip200"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### `GET /api/epoch`
Get current epoch information.

**Response:**
```json
{
  "success": true,
  "data": {
    "epoch": 42,
    "slot": 72,
    "blocks_per_epoch": 144,
    "enrolled_miners": 156,
    "epoch_pot": 125.5,
    "progress_percent": 50.0
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### `GET /api/miners`
Get list of active miners.

**Query Parameters:**
- `limit` (int, 1-1000): Maximum miners to return (default: 50)
- `offset` (int, >=0): Offset for pagination (default: 0)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "miner_id": "abc123...",
      "antiquity_multiplier": 2.5,
      "hardware_type": "PowerPC G4",
      "device_arch": "G4",
      "last_attest": 1705312200,
      "score": 100,
      "multiplier": 2.5
    }
  ],
  "count": 1,
  "pagination": {
    "limit": 50,
    "offset": 0
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### `GET /api/miner/<miner_id>`
Get details for a specific miner.

**Path Parameters:**
- `miner_id`: Miner wallet address or ID

**Response:**
```json
{
  "success": true,
  "data": {
    "miner_id": "abc123...",
    "balance": 150.5,
    "epoch_rewards": 12.3
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### `GET /api/balance`
Get wallet balance for a miner.

**Query Parameters:**
- `address` (string, required): Wallet address to look up

**Response:**
```json
{
  "success": true,
  "data": {
    "address": "abc123...",
    "balance": 150.5,
    "epoch_rewards": 12.3,
    "total_earned": 500.0,
    "pending": 5.0
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### `GET /api/transactions`
Get recent transactions.

**Query Parameters:**
- `limit` (int, 1-1000): Maximum transactions to return (default: 50)
- `offset` (int, >=0): Offset for pagination (default: 0)
- `address` (string, optional): Filter by wallet address

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "tx_id": "tx123...",
      "from_addr": "sender...",
      "to_addr": "receiver...",
      "amount": 10.5,
      "timestamp": 1705312200,
      "status": "confirmed",
      "fee": 0.01,
      "block_height": 12345
    }
  ],
  "count": 1,
  "pagination": {
    "limit": 50,
    "offset": 0,
    "address_filter": null
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### `GET /api/stats`
Get aggregated network statistics.

**Response:**
```json
{
  "success": true,
  "data": {
    "total_miners": 156,
    "current_epoch": 42,
    "network_status": "healthy",
    "node_version": "2.2.1-rip200"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Admin Endpoints

#### `POST /admin/rate-limit/reset`
Reset rate limits (requires admin token).

**Headers:**
- `X-Admin-Token`: Admin authentication token

**Query Parameters:**
- `ip` (optional): IP address to reset (resets all if not provided)

## Error Handling

The API uses standard HTTP status codes:

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request succeeded |
| 400 | Bad Request | Invalid input parameters |
| 401 | Unauthorized | Missing or invalid admin token |
| 404 | Not Found | Resource not found |
| 405 | Method Not Allowed | HTTP method not supported |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected server error |
| 502 | Bad Gateway | Upstream server error |
| 504 | Gateway Timeout | Upstream timeout |

### Error Response Format

```json
{
  "success": false,
  "error": "Error message",
  "details": {}  // Optional validation details
}
```

## Rate Limiting

The API implements rate limiting to prevent abuse:

- **Default Limit:** 100 requests per 60 seconds per IP
- **Headers:** Rate limit info included in response headers:
  - `X-RateLimit-Limit`: Maximum requests allowed
  - `X-RateLimit-Remaining`: Requests remaining
  - `X-RateLimit-Reset`: Unix timestamp when limit resets

### Rate Limit Exceeded Response

```json
{
  "error": "Rate limit exceeded",
  "message": "Maximum 100 requests per 60 seconds",
  "retry_after": 45
}
```

**HTTP 429** status code is returned when rate limit is exceeded.

## Input Validation

All inputs are validated using Marshmallow schemas:

### Miner ID Validation
- Must be 1-128 characters
- Only alphanumeric, underscore, and hyphen allowed

### Wallet Address Validation
- Must be 1-256 characters

### Pagination Validation
- `limit`: 1-1000
- `offset`: >= 0

### Validation Error Response

```json
{
  "success": false,
  "error": "Invalid parameters",
  "details": {
    "limit": ["Limit must be 1-1000"]
  }
}
```

## Testing

### Manual Testing with curl

```bash
# Health check
curl http://localhost:8080/health

# Get epoch info
curl http://localhost:8080/api/epoch

# Get miners list
curl "http://localhost:8080/api/miners?limit=10"

# Get wallet balance
curl "http://localhost:8080/api/balance?address=test_wallet"

# Get transactions
curl "http://localhost:8080/api/transactions?limit=20"

# Test rate limiting (run multiple times)
for i in {1..105}; do curl -s http://localhost:8080/api/health | head -1; done
```

### Automated Testing

Create a test script `test_api.py`:

```python
#!/usr/bin/env python3
"""API integration tests"""

import requests
import pytest

BASE_URL = "http://localhost:8080"

def test_health():
    """Test health endpoint"""
    resp = requests.get(f"{BASE_URL}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data

def test_api_health():
    """Test upstream health proxy"""
    resp = requests.get(f"{BASE_URL}/api/health")
    assert resp.status_code in [200, 502]  # 502 if upstream unavailable
    data = resp.json()
    assert "success" in data

def test_epoch():
    """Test epoch endpoint"""
    resp = requests.get(f"{BASE_URL}/api/epoch")
    assert resp.status_code in [200, 502]
    if resp.status_code == 200:
        data = resp.json()
        assert data["success"] == True
        assert "epoch" in data["data"]

def test_miners():
    """Test miners endpoint"""
    resp = requests.get(f"{BASE_URL}/api/miners?limit=5")
    assert resp.status_code in [200, 502]
    if resp.status_code == 200:
        data = resp.json()
        assert data["success"] == True
        assert isinstance(data["data"], list)

def test_invalid_miner_id():
    """Test miner ID validation"""
    resp = requests.get(f"{BASE_URL}/api/miner/invalid@id!")
    assert resp.status_code == 400

def test_rate_limit_headers():
    """Test rate limit headers present"""
    resp = requests.get(f"{BASE_URL}/health")
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

Run tests:
```bash
pip install pytest requests
python -m pytest test_api.py -v
```

## Deployment Options

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api_server.py index.html ./

EXPOSE 8080

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "api_server:app"]
```

Build and run:
```bash
docker build -t rustchain-api .
docker run -p 8080:8080 -e RUSTCHAIN_API_BASE=https://rustchain.org rustchain-api
```

### Systemd Service (Linux)

Create `/etc/systemd/system/rustchain-api.service`:

```ini
[Unit]
Description=RustChain API Server
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/path/to/api
Environment="PATH=/path/to/api/.venv/bin"
Environment="RUSTCHAIN_API_BASE=https://rustchain.org"
ExecStart=/path/to/api/.venv/bin/gunicorn -w 4 -b 127.0.0.1:8080 api_server:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable rustchain-api
sudo systemctl start rustchain-api
```

### Nginx Reverse Proxy

Configure Nginx to proxy to the API server:

```nginx
server {
    listen 80;
    server_name api.rustchain.org;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Rate limiting at Nginx level (optional)
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://127.0.0.1:8080;
    }
}
```

## Monitoring

### Health Check Endpoint

Use `/health` for load balancer health checks:
```bash
curl -f http://localhost:8080/health || exit 1
```

### Logging

Logs are output to stdout in JSON-compatible format:
```
2024-01-15 10:30:00 - rustchain-api - INFO - Starting RustChain API Server
2024-01-15 10:30:05 - rustchain-api - DEBUG - Upstream GET: https://rustchain.org/health
2024-01-15 10:30:10 - rustchain-api - WARNING - Rate limit exceeded for 192.168.1.100
```

### Metrics to Monitor

- Request rate per endpoint
- Error rate (4xx, 5xx responses)
- Upstream response time
- Rate limit hits

## Security Considerations

1. **Rate Limiting**: Enabled by default to prevent DoS
2. **Input Validation**: All inputs validated before processing
3. **Error Messages**: Generic error messages to prevent information leakage
4. **Admin Token**: Protect admin endpoints with `ADMIN_TOKEN` env var
5. **SSL/TLS**: Use HTTPS in production (terminate at Nginx or load balancer)

## Troubleshooting

### Cannot connect to upstream

```
Error: Cannot connect to upstream
```

**Solution:** Check `RUSTCHAIN_API_BASE` environment variable and network connectivity.

### Rate limit exceeded

```
HTTP 429: Rate limit exceeded
```

**Solution:** Reduce request frequency or increase `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW`.

### Validation errors

```
HTTP 400: Invalid parameters
```

**Solution:** Check input parameters against validation rules in API documentation.

## License

Part of RustChain project. See main repository LICENSE file.

## Support

For issues and feature requests, please open an issue on the RustChain GitHub repository.
