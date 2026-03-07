# RustChain API Server - Deployment Guide

## Quick Start

```bash
cd api

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run server
python api_server.py
```

Access the dashboard at: http://localhost:8080/dashboard

## Production Deployment

### Option 1: Gunicorn (Recommended)

```bash
# Install gunicorn
pip install gunicorn

# Run with 4 workers
gunicorn -w 4 -b 0.0.0.0:8080 api_server:app

# Or with more tuning for production
gunicorn \
  --workers 4 \
  --threads 2 \
  --worker-class sync \
  --timeout 30 \
  --keep-alive 5 \
  --access-logfile access.log \
  --error-logfile error.log \
  --pid gunicorn.pid \
  -b 0.0.0.0:8080 \
  api_server:app
```

### Option 2: Docker

```bash
# Build image
docker build -t rustchain-api:latest .

# Run container
docker run -d \
  --name rustchain-api \
  -p 8080:8080 \
  -e RUSTCHAIN_API_BASE=https://rustchain.org \
  -e RATE_LIMIT_REQUESTS=100 \
  rustchain-api:latest

# Check logs
docker logs -f rustchain-api

# Stop container
docker stop rustchain-api
```

### Option 3: Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8080:8080"
    environment:
      - RUSTCHAIN_API_BASE=https://rustchain.org
      - RATE_LIMIT_REQUESTS=100
      - RATE_LIMIT_WINDOW=60
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8080/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Run:
```bash
docker-compose up -d
```

### Option 4: Systemd Service (Linux)

1. Create service file `/etc/systemd/system/rustchain-api.service`:

```ini
[Unit]
Description=RustChain API Server
After=network.target
Wants=network-online.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/rustchain/api
Environment="PATH=/opt/rustchain/api/.venv/bin"
EnvironmentFile=/opt/rustchain/api/.env
ExecStart=/opt/rustchain/api/.venv/bin/gunicorn -w 4 -b 127.0.0.1:8080 api_server:app
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rustchain-api

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

2. Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable rustchain-api
sudo systemctl start rustchain-api

# Check status
sudo systemctl status rustchain-api

# View logs
sudo journalctl -u rustchain-api -f
```

## Nginx Reverse Proxy

### Basic Configuration

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
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### With SSL (Let's Encrypt)

```nginx
server {
    listen 80;
    server_name api.rustchain.org;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.rustchain.org;

    ssl_certificate /etc/letsencrypt/live/api.rustchain.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.rustchain.org/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Rate limiting at Nginx level (optional, API has built-in limiting)
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://127.0.0.1:8080;
    }
}
```

Install SSL certificate:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d api.rustchain.org
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUSTCHAIN_API_BASE` | `https://rustchain.org` | Upstream node URL |
| `RUSTCHAIN_API_TIMEOUT` | `10` | Request timeout (seconds) |
| `PORT` | `8080` | Server port |
| `HOST` | `0.0.0.0` | Bind address |
| `FLASK_DEBUG` | `false` | Debug mode |
| `RATE_LIMIT_REQUESTS` | `100` | Max requests per window |
| `RATE_LIMIT_WINDOW` | `60` | Rate limit window (seconds) |
| `ADMIN_TOKEN` | (none) | Admin auth token |

## Health Checks

### Load Balancer Health Check

```bash
curl -f http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "uptime_seconds": 3600,
  "version": "1.0.0"
}
```

### Docker Health Check

Already configured in Dockerfile. View status:
```bash
docker inspect --format='{{.State.Health.Status}}' rustchain-api
```

### Kubernetes Readiness Probe

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

## Monitoring

### Log Format

```
2024-01-15 10:30:00 - rustchain-api - INFO - Starting RustChain API Server
2024-01-15 10:30:05 - rustchain-api - DEBUG - Upstream GET: https://rustchain.org/health
2024-01-15 10:30:10 - rustchain-api - WARNING - Rate limit exceeded for 192.168.1.100
```

### Metrics to Monitor

- Request rate per endpoint
- Error rate (4xx, 5xx)
- Upstream response time
- Rate limit hits
- Memory usage

### Prometheus Metrics (Optional)

Add `prometheus-flask-exporter`:

```bash
pip install prometheus-flask-exporter
```

```python
from prometheus_flask_exporter import PrometheusMetrics

metrics = PrometheusMetrics(app)
metrics.register_endpoint('/metrics')
```

## Security Hardening

### 1. Run as Non-Root User

Dockerfile already creates `appuser`. For systemd, use `User=www-data`.

### 2. Enable Firewall

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 3. Set Admin Token

```bash
# Generate secure token
python -c "import secrets; print(secrets.token_hex(32))"

# Add to .env
ADMIN_TOKEN=your_secure_token_here
```

### 4. Rate Limiting

Already enabled by default. Adjust as needed:
```bash
RATE_LIMIT_REQUESTS=50
RATE_LIMIT_WINDOW=60
```

### 5. SSL/TLS

Always use HTTPS in production. Terminate SSL at Nginx or load balancer.

## Troubleshooting

### Server Won't Start

```bash
# Check if port is in use
lsof -i :8080

# Check logs
journalctl -u rustchain-api -n 50

# Test configuration
python -c "import api_server; api_server.create_app()"
```

### Cannot Connect to Upstream

```bash
# Test upstream connectivity
curl -I https://rustchain.org/health

# Check environment variable
echo $RUSTCHAIN_API_BASE

# Test with timeout
curl --max-time 10 $RUSTCHAIN_API_BASE/health
```

### High Memory Usage

```bash
# Reduce worker count
gunicorn -w 2 -b 0.0.0.0:8080 api_server:app

# Add memory limits (Docker)
docker run --memory="512m" --memory-swap="512m" ...
```

### Rate Limit Issues

```bash
# Check current limits
curl -s http://localhost:8080/health | jq '.rate_limit'

# Reset rate limits (requires admin token)
curl -X POST http://localhost:8080/admin/rate-limit/reset \
  -H "X-Admin-Token: your_token"
```

## Backup and Restore

### Configuration Backup

```bash
# Backup environment and configs
tar -czf rustchain-api-backup.tar.gz \
  .env \
  nginx.conf \
  rustchain-api.service
```

### Restore

```bash
# Extract backup
tar -xzf rustchain-api-backup.tar.gz

# Restore permissions
chmod 600 .env
chown www-data:www-data .env

# Restart service
sudo systemctl restart rustchain-api
```

## Scaling

### Horizontal Scaling

Run multiple instances behind a load balancer:

```yaml
# docker-compose.scale.yml
version: '3.8'
services:
  api:
    build: .
    deploy:
      replicas: 3
    environment:
      - RUSTCHAIN_API_BASE=https://rustchain.org
```

### Load Balancer Configuration

```nginx
upstream rustchain_api {
    least_conn;
    server 127.0.0.1:8081;
    server 127.0.0.1:8082;
    server 127.0.0.1:8083;
}

server {
    location / {
        proxy_pass http://rustchain_api;
    }
}
```

## Performance Tuning

### Gunicorn Tuning

```bash
# For CPU-bound workloads
gunicorn -w $(nproc) -b 0.0.0.0:8080 api_server:app

# For I/O-bound workloads (like API proxying)
gunicorn -w 4 --threads 4 -b 0.0.0.0:8080 api_server:app
```

### System Tuning

```bash
# Increase file descriptor limit
ulimit -n 65536

# Tune TCP settings
sysctl -w net.ipv4.tcp_tw_reuse=1
sysctl -w net.core.somaxconn=65535
```

## Support

For issues and questions:
1. Check logs: `journalctl -u rustchain-api -f`
2. Test endpoints: `curl http://localhost:8080/health`
3. Run tests: `python test_api.py`
4. Review documentation: README.md
