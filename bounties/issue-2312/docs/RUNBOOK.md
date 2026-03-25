# Rent-a-Relic Market - Operational Runbook

## Quick Reference

| Item | Value |
|------|-------|
| Service Name | relic-market |
| Default Port | 5000 |
| Health Endpoint | `/health` |
| Log Location | stdout/stderr |
| Process Name | `python relic_market_api.py` |

---

## Starting the Service

### Development

```bash
cd bounties/issue-2312/src
python relic_market_api.py --debug
```

### Production

```bash
cd bounties/issue-2312/src

# Using gunicorn (recommended)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 relic_market_api:app

# Or with systemd
sudo systemctl start relic-market
```

### Docker

```bash
cd bounties/issue-2312/src
docker build -t relic-market .
docker run -d -p 5000:5000 relic-market
```

---

## Health Checks

### Manual

```bash
curl http://localhost:5000/health
```

### Expected Response

```json
{
  "ok": true,
  "service": "relic-market",
  "version": "1.0.0",
  "machines_registered": 5,
  "active_reservations": 0
}
```

### Automated (cron)

```bash
# Add to crontab
*/5 * * * * curl -sf http://localhost:5000/health || systemctl restart relic-market
```

---

## Monitoring

### Key Metrics

1. **Machines Registered**: Should be >= 5
2. **Active Reservations**: Monitor for unusual spikes
3. **API Response Time**: Should be < 500ms
4. **Error Rate**: Should be < 1%

### Log Analysis

```bash
# View recent errors
journalctl -u relic-market -p err -n 50

# Search for specific errors
journalctl -u relic-market | grep -i "error\|fail\|exception"
```

---

## Common Issues

### Issue: Machine not available

**Symptoms**: Booking fails with "Machine not available"

**Resolution**:
```bash
# Check machine status
curl http://localhost:5000/relic/vm-001

# Verify availability in registry
# Check if machine is marked as unavailable
```

### Issue: Escrow not releasing

**Symptoms**: Session completed but funds not released

**Resolution**:
1. Check reservation status: `GET /relic/reservation/<id>`
2. Verify session was started: status should be "active" before completion
3. Check receipt generation logs
4. Manually release if needed (admin function)

### Issue: Signature verification fails

**Symptoms**: Receipt shows "signature_valid": false

**Resolution**:
1. Verify machine key exists in ReceiptSigner
2. Check machine_id matches between receipt and signer
3. Ensure canonical JSON format for signing
4. Regenerate receipt if needed

### Issue: High API latency

**Symptoms**: Requests taking > 1 second

**Resolution**:
```bash
# Check server load
top -p $(pgrep -f relic_market_api)

# Check database locks (if using SQLite)
lsof | grep relic

# Scale horizontally
gunicorn -w 8 -b 0.0.0.0:5000 relic_market_api:app
```

---

## Backup & Recovery

### Database Backup

The MVP uses in-memory storage. For production with persistence:

```bash
# Export machine registry
curl http://localhost:5000/relic/available > backup_machines.json

# Export reservations
# (Implement export endpoint if needed)
```

### Recovery

```bash
# Restore from backup
# (Implement import endpoint if needed)

# Restart service
systemctl restart relic-market
```

---

## Security

### TLS Configuration

For production, always use HTTPS:

```bash
# With nginx reverse proxy
server {
    listen 443 ssl;
    server_name relic.rustchain.org;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:5000;
    }
}
```

### Rate Limiting

Implement rate limiting in production:

```bash
# With nginx
location / {
    limit_req zone=general burst=10;
    proxy_pass http://localhost:5000;
}
```

### Firewall Rules

```bash
# Allow only necessary ports
sudo ufw allow 5000/tcp
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

---

## Scaling

### Horizontal Scaling

```bash
# Run multiple instances behind load balancer
gunicorn -w 4 -b 0.0.0.0:5001 relic_market_api:app &
gunicorn -w 4 -b 0.0.0.0:5002 relic_market_api:app &
gunicorn -w 4 -b 0.0.0.0:5003 relic_market_api:app &
```

### Load Balancer Configuration

```nginx
upstream relic_market {
    server localhost:5001;
    server localhost:5002;
    server localhost:5003;
}

server {
    listen 80;
    location / {
        proxy_pass http://relic_market;
    }
}
```

---

## Maintenance

### Adding New Machines

Edit `MachineRegistry._initialize_sample_machines()` in `relic_market_api.py`:

```python
VintageMachine(
    machine_id="vm-new",
    name="New Machine",
    ...
)
```

Then restart the service.

### Updating Machine Rates

```python
# Via API (if implemented)
PATCH /relic/<machine_id>/rate
{"hourly_rate_rtc": 25.0}

# Or directly in code and restart
```

### Clearing Old Reservations

```python
# Implement cleanup script
import time
from relic_market_api import reservation_manager

cutoff = time.time() - (30 * 24 * 3600)  # 30 days
for res_id, res in reservation_manager.reservations.items():
    if res.completed_at and res.completed_at < cutoff:
        # Archive or delete
        pass
```

---

## Troubleshooting

### Enable Debug Logging

```bash
# Start with debug flag
python relic_market_api.py --debug

# Or set environment variable
export FLASK_DEBUG=1
python relic_market_api.py
```

### Test Endpoints Manually

```bash
# Test reservation flow
RES=$(curl -X POST http://localhost:5000/relic/reserve \
  -H "Content-Type: application/json" \
  -d '{"machine_id":"vm-001","agent_id":"test","duration_hours":1,"payment_rtc":50}')

RES_ID=$(echo $RES | jq -r '.reservation.reservation_id')

# Start session
curl -X POST http://localhost:5000/relic/reservation/$RES_ID/start

# Complete session
curl -X POST http://localhost:5000/relic/reservation/$RES_ID/complete \
  -H "Content-Type: application/json" \
  -d '{"compute_hash":"abc123","hardware_attestation":{}}'

# Get receipt
curl http://localhost:5000/relic/receipt/$RES_ID
```

### Check Dependencies

```bash
# Verify Python packages
pip list | grep -E "Flask|PyNaCl"

# Reinstall if needed
pip install -r requirements.txt --force-reinstall
```

---

## Contact & Support

- **GitHub Issues**: https://github.com/Scottcjn/rustchain-bounties/issues/2312
- **Documentation**: See README.md and API_REFERENCE.md
- **Tests**: Run `python tests/test_relic_market.py` for validation

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-22 | Initial release |

---

**Last Updated**: 2026-03-22  
**Maintained By**: RustChain Core Team
