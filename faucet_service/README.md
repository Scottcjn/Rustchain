# RustChain Testnet Faucet Service

A production-ready Flask-based faucet service for dispensing free test RTC tokens to developers building on RustChain.

## Features

- **Configurable Rate Limiting**: IP-based, wallet-based, or hybrid rate limiting with customizable windows
- **Request Validation**: Wallet address validation with blocklist/allowlist support
- **Multiple Backends**: SQLite for simple deployments, Redis for distributed setups
- **REST API**: Full JSON API for programmatic access
- **Web UI**: Modern, responsive HTML interface
- **Monitoring**: Health checks and Prometheus metrics support
- **Mock Mode**: Test without actual token transfers

## Quick Start

### Installation

```bash
# Navigate to faucet service directory
cd faucet_service

# Install dependencies
pip install -r requirements.txt

# Copy and customize configuration
cp faucet_config.yaml faucet_config.local.yaml
```

### Running the Faucet

```bash
# Run with default configuration
python faucet_service.py

# Run with custom configuration
python faucet_service.py --config faucet_config.local.yaml

# Run with command-line overrides
python faucet_service.py --host 0.0.0.0 --port 9000 --debug
```

The faucet will start at `http://localhost:8090/faucet`

## Configuration

Copy `faucet_config.yaml` and customize for your deployment:

```yaml
# Server settings
server:
  host: "0.0.0.0"
  port: 8090
  debug: false
  base_path: "/faucet"

# Rate limiting
rate_limit:
  enabled: true
  method: "ip"  # Options: "ip", "wallet", "hybrid"
  window_seconds: 86400  # 24 hours
  max_amount: 0.5  # RTC per request
  max_requests: 1  # Requests per window

# Wallet validation
validation:
  allowed_prefixes: ["RTC", "0x"]
  min_length: 10
  max_length: 66
  blocklist: []
  allowlist: []

# Distribution settings
distribution:
  amount: 0.5
  mock_mode: true  # Set to false for actual transfers
```

### Configuration Options

#### Server
| Option | Default | Description |
|--------|---------|-------------|
| `host` | `0.0.0.0` | Server bind address |
| `port` | `8090` | Server port |
| `debug` | `false` | Enable debug mode |
| `base_path` | `/faucet` | Base URL path |

#### Rate Limiting
| Option | Default | Description |
|--------|---------|-------------|
| `enabled` | `true` | Enable rate limiting |
| `method` | `ip` | Rate limit method (ip/wallet/hybrid) |
| `window_seconds` | `86400` | Time window in seconds |
| `max_amount` | `0.5` | Maximum RTC per request |
| `max_requests` | `1` | Maximum requests per window |

#### Validation
| Option | Default | Description |
|--------|---------|-------------|
| `allowed_prefixes` | `["RTC", "0x"]` | Accepted wallet prefixes |
| `min_length` | `10` | Minimum wallet length |
| `max_length` | `66` | Maximum wallet length |
| `blocklist` | `[]` | Blocked wallet addresses |
| `allowlist` | `[]` | Allowed wallet addresses (empty = all) |

## API Endpoints

### GET /faucet

Serves the faucet web interface.

### POST /faucet/drip

Request test tokens.

**Request:**
```json
{
  "wallet": "0x9683744B6b94F2b0966aBDb8C6BdD9805d207c6E"
}
```

**Response (Success):**
```json
{
  "ok": true,
  "amount": 0.5,
  "wallet": "0x9683744B6b94F2b0966aBDb8C6BdD9805d207c6E",
  "tx_hash": null,
  "next_available": "2026-03-13T14:20:00.000000"
}
```

**Response (Rate Limited):**
```json
{
  "ok": false,
  "error": "Rate limit exceeded",
  "next_available": "2026-03-13T14:20:00.000000"
}
```

**Response (Validation Error):**
```json
{
  "ok": false,
  "error": "Invalid wallet address"
}
```

### GET /faucet/status

Get faucet status and statistics.

**Response:**
```json
{
  "status": "operational",
  "network": "testnet",
  "mock_mode": true,
  "statistics": {
    "total_drips": 150,
    "total_amount": 75.0,
    "unique_wallets": 120,
    "unique_ips": 95,
    "drips_24h": 25,
    "amount_24h": 12.5
  },
  "rate_limit": {
    "max_amount": 0.5,
    "window_hours": 24.0
  }
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-12T14:20:00.000000",
  "version": "1.0.0"
}
```

### GET /metrics

Prometheus metrics endpoint (when enabled).

**Response:**
```
# HELP faucet_drips_total Total number of drips
# TYPE faucet_drips_total counter
faucet_drips_total 150

# HELP faucet_amount_total Total amount distributed
# TYPE faucet_amount_total counter
faucet_amount_total 75.0

# HELP faucet_up Faucet service status
# TYPE faucet_up gauge
faucet_up 1
```

## Rate Limiting

The faucet supports three rate limiting methods:

### IP-based (Default)
Rate limits based on client IP address. Simple but may affect users behind NAT.

```yaml
rate_limit:
  method: "ip"
```

### Wallet-based
Rate limits based on wallet address. Allows multiple requests from same IP to different wallets.

```yaml
rate_limit:
  method: "wallet"
```

### Hybrid
Rate limits based on combination of IP and wallet. Most restrictive.

```yaml
rate_limit:
  method: "hybrid"
```

### Distributed Rate Limiting (Redis)

For multi-instance deployments, enable Redis:

```yaml
rate_limit:
  redis:
    enabled: true
    host: "localhost"
    port: 6379
    db: 0
    password: null
    key_prefix: "rustchain_faucet:"
```

## Testing

Run the test suite:

```bash
# Using pytest
pytest test_faucet_service.py -v

# Using unittest
python test_faucet_service.py
```

### Test Coverage

- Configuration loading and merging
- Wallet validation (prefix, length, blocklist, allowlist)
- Rate limiting (IP, wallet, hybrid methods)
- Database operations
- API endpoints (drip, status, health)
- Integration flows

## Production Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY faucet_service.py .
COPY faucet_config.yaml .

EXPOSE 8090
CMD ["python", "faucet_service.py"]
```

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name faucet.rustchain.org;

    location /faucet {
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Systemd Service

```ini
[Unit]
Description=RustChain Testnet Faucet
After=network.target

[Service]
Type=simple
User=faucet
WorkingDirectory=/opt/rustchain/faucet_service
ExecStart=/opt/rustchain/venv/bin/python faucet_service.py --config faucet_config.yaml
Restart=always

[Install]
WantedBy=multi-user.target
```

## Security Considerations

### Mock Mode

By default, the faucet runs in mock mode (no actual token transfers). For production:

```yaml
distribution:
  mock_mode: false
  node_rpc: "https://testnet-rpc.rustchain.org"
  wallet_key: "your-faucet-wallet-key"  # Use environment variable!
```

**Never commit wallet keys to version control!** Use environment variables:

```bash
export FAUCET_WALLET_KEY="your-secret-key"
```

### CORS

Configure allowed origins:

```yaml
security:
  cors_origins:
    - "https://rustchain.org"
    - "https://rustchain.org/docs"
```

### Rate Limiting

Adjust rate limits based on your token supply:

```yaml
rate_limit:
  window_seconds: 86400  # 24 hours
  max_amount: 0.5        # RTC per request
  max_requests: 1        # Requests per window
```

## Monitoring

### Logging

Logs are written to `faucet.log` with rotation:

```yaml
logging:
  level: "INFO"
  file: "faucet.log"
  max_size_mb: 10
  backup_count: 5
```

### Health Checks

Configure health check endpoint for load balancers:

```yaml
monitoring:
  health_enabled: true
  health_path: "/health"
```

### Prometheus Metrics

Enable metrics endpoint:

```yaml
monitoring:
  metrics_enabled: true
  metrics_path: "/metrics"
```

## Troubleshooting

### Common Issues

**Port already in use:**
```bash
# Check what's using the port
lsof -i :8090

# Use a different port
python faucet_service.py --port 9000
```

**Database locked:**
```bash
# Check for zombie processes
ps aux | grep faucet

# Remove lock file
rm faucet.db-shm faucet.db-wal
```

**Rate limiting not working:**
```bash
# Check Redis connection (if using Redis)
redis-cli ping

# Check database
sqlite3 faucet.db "SELECT * FROM drip_requests LIMIT 5;"
```

### Debug Mode

Enable debug mode for detailed logging:

```bash
python faucet_service.py --debug
```

## License

Apache License 2.0 - See LICENSE file in RustChain root.

## Contributing

See CONTRIBUTING.md for contribution guidelines.

## Support

- Documentation: https://rustchain.org/docs/faucet
- Issues: https://github.com/Scottcjn/rustchain-bounties/issues
- Discord: https://discord.gg/rustchain
