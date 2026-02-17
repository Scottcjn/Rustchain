# RustChain Mining Pool Proxy

Aggregates attestations from multiple miners and distributes rewards proportionally.

## 🎯 Purpose

Small miners often earn tiny rewards individually. The pool proxy allows miners to:
- Combine their computing power
- Earn more consistent rewards
- Track their contributions
- View pool statistics in real-time

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements-pool.txt
```

### 2. Start the Pool Server

```bash
python3 pool_proxy.py --port 8080 --node-url http://50.28.86.131:8099
```

### 3. Connect Miners

Miners can connect using the `--pool` flag:

```bash
clawrtc --pool http://your-pool-url:8080
```

### 4. View Dashboard

Open your browser to:
```
http://localhost:8080
```

## 📊 Features

### Pool Dashboard
- Real-time miner statistics
- Per-miner contribution tracking
- Uptime and hardware scores
- Reward distribution history

### Server
- Accepts attestations from multiple miners
- Tracks miner contributions (uptime, hardware score)
- Calculates contribution weights
- Distributes rewards proportionally
- Configurable pool fee (default 1%)

### Hardware Score Calculation

Vintage hardware receives higher scores:
- PowerPC G4: 2.5x
- PowerPC G5: 2.0x
- PowerPC G3: 1.8x
- 68K: 3.0x
- SPARC: 2.0x
- Pentium: 1.8x
- 486: 2.5x
- Modern hardware: 1.0x

### Contribution Weight

```
weight = hardware_score × (uptime_bonus + attestation_bonus)
```

- **Uptime bonus**: Up to 2.0x after 100 hours
- **Attestation bonus**: Up to 1.5x after 200 attestations

## 🔧 Configuration

### Command-Line Options

```bash
python3 pool_proxy.py [OPTIONS]
```

| Option | Default | Description |
|---------|----------|-------------|
| `--port` | 8080 | Port to listen on |
| `--node-url` | http://50.28.86.131:8099 | RustChain node URL |
| `--pool-fee` | 0.01 | Pool fee (0.01 = 1%) |
| `--db-path` | ./pool_proxy.db | Database file path |

### Environment Variables

You can also use environment variables:

```bash
export POOL_PORT=8080
export POOL_NODE_URL=http://50.28.86.131:8099
export POOL_FEE=0.01
export POOL_DB_PATH=./pool_proxy.db

python3 pool_proxy.py
```

## 📡 API Endpoints

### Pool Statistics

```bash
GET http://localhost:8080/api/stats
```

Response:
```json
{
  "total_miners": 42,
  "active_miners": 15,
  "total_attestations": 12345,
  "total_rewards_distributed": 456.78,
  "pool_fee_collected": 4.57,
  "current_epoch": 73,
  "total_hash_power": 125.5
}
```

### Miner List

```bash
GET http://localhost:8080/api/miners
```

### Miner Details

```bash
GET http://localhost:8080/api/miner/<wallet_address>
```

### Submit Attestation

```bash
POST http://localhost:8080/api/attest
Content-Type: application/json

{
  "wallet": "0x123...",
  "device_id": "device-uuid",
  "device_arch": "PowerPC G4",
  "device_family": "PowerPC",
  "entropy_score": 75.5,
  "fingerprint": {
    "checks": {...}
  }
}
```

Response:
```json
{
  "status": "accepted",
  "attestation_id": "abc123...",
  "hardware_score": 2.5,
  "contribution_weight": 3.75
}
```

### Reward History

```bash
GET http://localhost:8080/api/rewards/history?limit=50
```

## 💰 Reward Distribution

### Calculation

1. Pool receives epoch reward from RustChain node
2. Pool fee is deducted (default 1%)
3. Remaining reward is distributed proportionally:
   ```
   miner_share = (miner_weight / total_pool_weight) × pool_reward
   ```

### Example

Pool receives 10.0 RTC for epoch 73:
- Pool fee (1%): 0.1 RTC
- Distributable: 9.9 RTC

Miner A (weight 3.75): (3.75 / 125.5) × 9.9 = 0.296 RTC
Miner B (weight 2.5): (2.5 / 125.5) × 9.9 = 0.197 RTC

## 🔒 Security

### Fingerprint Validation

All attestations are validated:
- Anti-emulation checks
- Clock drift verification
- Hardware signature verification
- VM detection

Same fingerprint checks as direct mining apply.

### Pool Fee Protection

Pool fee is configurable but recommended:
- Minimum: 0% (non-profit pool)
- Maximum: 5% (fair to miners)
- Default: 1% (standard industry rate)

## 📈 Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Miner 1   │     │  Miner 2   │     │  Miner 3   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            │
                   ┌────────▼────────┐
                   │  Pool Proxy    │
                   │  (This Server) │
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │ RustChain Node │
                   │  :8099         │
                   └─────────────────┘
```

## 🔧 Database

The pool uses SQLite for data persistence:

**Tables:**
- `miners` - Miner information and statistics
- `attestations` - Attestation history
- `rewards` - Reward distribution history
- `pool_config` - Pool configuration

**Location:** `./pool_proxy.db` (configurable)

## 🚦 Monitoring

### Dashboard

Real-time dashboard available at:
```
http://localhost:8080
```

Shows:
- Total and active miners
- Total attestations
- Rewards distributed
- Pool fee collected
- Miner list with details
- Recent rewards

### Logs

Pool server logs to stdout:
```
python3 pool_proxy.py 2>&1 | tee pool.log
```

## 🧪 Testing

### Test Connection

```bash
curl http://localhost:8080/api/stats
```

### Test Attestation Submission

```bash
curl -X POST http://localhost:8080/api/attest \
  -H "Content-Type: application/json" \
  -d '{
    "wallet": "test-wallet",
    "device_id": "test-device",
    "device_arch": "PowerPC G4",
    "device_family": "PowerPC",
    "entropy_score": 75.0
  }'
```

## 🔧 Troubleshooting

### Port Already in Use

```bash
# Find what's using the port
lsof -i :8080

# Use a different port
python3 pool_proxy.py --port 8081
```

### Database Locked

```bash
# Stop the server
pkill -f pool_proxy.py

# Check for lock files
ls -la *.db*

# Remove lock files (be careful!)
rm *.db-*

# Restart
python3 pool_proxy.py
```

### Miner Cannot Connect

- Check firewall allows port 8080
- Verify pool server is running: `curl http://localhost:8080/api/stats`
- Check miner uses correct pool URL
- Verify `--pool` flag is supported in miner client

## 📦 Production Deployment

### Systemd Service

Create `/etc/systemd/system/rustchain-pool.service`:

```ini
[Unit]
Description=RustChain Mining Pool Proxy
After=network.target

[Service]
Type=simple
User=rustchain
WorkingDirectory=/opt/rustchain-pool
ExecStart=/usr/bin/python3 /opt/rustchain-pool/pool_proxy.py \
    --port 8080 \
    --node-url http://50.28.86.131:8099 \
    --pool-fee 0.01 \
    --db-path /opt/rustchain-pool/pool_proxy.db
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable rustchain-pool
sudo systemctl start rustchain-pool
sudo systemctl status rustchain-pool
```

### Nginx Reverse Proxy

Add to nginx configuration:

```nginx
server {
    listen 80;
    server_name pool.rustchain.org;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### SSL/TLS

Use Let's Encrypt:
```bash
sudo certbot --nginx -d pool.rustchain.org
```

## 🤝 Contributing

Contributions welcome! Areas of improvement:
- Reward distribution optimization
- Advanced pool statistics
- Miner authentication
- Payout automation
- Multi-pool support

## 📄 License

Same as RustChain project.

## 📞 Support

- GitHub Issues: https://github.com/Scottcjn/Rustchain/issues
- Discord: [RustChain Discord Server]
- Documentation: https://docs.rustchain.org
