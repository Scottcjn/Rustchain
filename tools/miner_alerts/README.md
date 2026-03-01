# 🔔 RustChain Miner Alert System

**Bounty**: #28 - Email/SMS Alert System for Miners  
**Author**: @xiangshangsir (大龙虾 AI)  
**Wallet**: `0x76AD8c0bef0a99eEb761c3B20b590D60b20964Dc`  
**Reward**: 75 RTC

---

## Overview

Automated alert system for RustChain miners. Sends notifications when:

- ⚠️ **Miner goes offline** - No attestation for >1 hour
- 💰 **Rewards received** - Epoch rewards deposited
- 🚨 **Large transfers** - Wallet transfers above threshold
- ❌ **Attestation failures** - Hardware/software issues

### Supported Channels

- 📧 **Email** (SMTP - Gmail, Outlook, etc.)
- 📱 **SMS** (Twilio - optional)

---

## Quick Start

### 1. Install Dependencies

```bash
pip install twilio  # Optional, for SMS support
```

### 2. Configure Alerts

Create `alert_config.json`:

```bash
cp alert_config.example.json alert_config.json
```

Edit with your settings:

```json
{
  "email": {
    "enabled": true,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "your-email@gmail.com",
    "password": "your-app-password",
    "from_email": "RustChain Alerts <alerts@rustchain.org>"
  },
  "sms": {
    "enabled": false,
    "account_sid": "ACxxxxxxxx",
    "auth_token": "your-token",
    "from_number": "+1234567890"
  }
}
```

### 3. Run Alert System

```bash
# Continuous monitoring (recommended)
python miner_alert_system.py

# Or as a systemd service
sudo systemctl enable rustchain-alerts
sudo systemctl start rustchain-alerts

# Test run (single check)
python miner_alert_system.py --once
```

---

## API Endpoints

Miners can configure alerts via HTTP API.

### GET /api/alert/preferences

Get alert preferences for a miner.

**Query params:**
- `miner_id` (required)

**Response:**
```json
{
  "ok": true,
  "preferences": {
    "miner_id": "createkr",
    "email": "user@example.com",
    "phone": "+1234567890",
    "alert_types": ["offline", "reward"],
    "enabled": true
  }
}
```

### POST /api/alert/preferences

Configure alert preferences.

**Request:**
```json
{
  "miner_id": "createkr",
  "email": "user@example.com",
  "phone": "+1234567890",
  "alert_types": ["offline", "reward", "large_transfer"],
  "enabled": true
}
```

### GET /api/alert/history

Get alert history.

**Query params:**
- `miner_id` (required)
- `limit` (optional, default 50)
- `alert_type` (optional filter)

### POST /api/alert/test

Send test alert.

**Request:**
```json
{
  "miner_id": "createkr",
  "channel": "email"
}
```

### GET /api/alert/stats

Get alert statistics.

---

## Alert Types

| Type | Description | Default |
|------|-------------|---------|
| `offline` | Miner no attestation for >1h | ✅ |
| `reward` | Epoch rewards received | ✅ |
| `large_transfer` | Transfer >100 RTC | ✅ |
| `attestation_failure` | Hardware/software failure | ✅ |

---

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUSTCHAIN_DB` | `/root/rustchain/rustchain_v2.db` | Database path |
| `ALERT_CONFIG` | `alert_config.json` | Config file path |
| `CHECK_INTERVAL` | `300` | Check interval (seconds) |
| `OFFLINE_THRESHOLD` | `3600` | Offline threshold (seconds) |
| `LARGE_TRANSFER_THRESHOLD` | `100` | Large transfer threshold (RTC) |

### Config File Settings

```json
{
  "alert_settings": {
    "check_interval_seconds": 300,
    "offline_threshold_hours": 1,
    "large_transfer_threshold_rtc": 100,
    "rate_limit_per_24h": 10
  }
}
```

---

## Database Schema

### `alert_preferences` Table

Stores miner alert configurations.

| Column | Type | Description |
|--------|------|-------------|
| `miner_id` | TEXT | Primary key |
| `email` | TEXT | Email address |
| `phone` | TEXT | Phone number (SMS) |
| `alert_types` | TEXT | JSON array of alert types |
| `enabled` | INTEGER | Enabled flag |
| `created_at` | INTEGER | Creation timestamp |

### `alert_history` Table

Audit trail of all sent alerts.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `miner_id` | TEXT | Miner identifier |
| `alert_type` | TEXT | Type of alert |
| `message` | TEXT | Alert message |
| `sent_at` | INTEGER | Timestamp |
| `channel` | TEXT | `email` or `sms` |
| `status` | TEXT | `sent` or `failed` |
| `error` | TEXT | Error message (if failed) |

### `alert_rate_limit` Table

Prevents alert spam.

| Column | Type | Description |
|--------|------|-------------|
| `miner_id` | TEXT | Miner identifier |
| `alert_type` | TEXT | Alert type |
| `last_sent` | INTEGER | Last sent timestamp |
| `count_24h` | INTEGER | Count in last 24h |

---

## Systemd Service

Create `/etc/systemd/system/rustchain-alerts.service`:

```ini
[Unit]
Description=RustChain Miner Alert System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/rustchain/tools/miner_alerts
Environment=RUSTCHAIN_DB=/root/rustchain/rustchain_v2.db
Environment=ALERT_CONFIG=/root/rustchain/tools/miner_alerts/alert_config.json
ExecStart=/usr/bin/python3 /root/rustchain/tools/miner_alerts/miner_alert_system.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable rustchain-alerts
sudo systemctl start rustchain-alerts
sudo systemctl status rustchain-alerts
```

---

## Example Usage

### Python Client

```python
import requests

API_BASE = "https://rustchain.org"

# Configure alerts
response = requests.post(f"{API_BASE}/api/alert/preferences", json={
    "miner_id": "createkr",
    "email": "user@example.com",
    "phone": "+1234567890",
    "alert_types": ["offline", "reward"],
    "enabled": True,
})
print(response.json())

# Get history
response = requests.get(
    f"{API_BASE}/api/alert/history",
    params={"miner_id": "createkr", "limit": 10}
)
print(response.json())
```

### cURL

```bash
# Configure alerts
curl -X POST https://rustchain.org/api/alert/preferences \
  -H "Content-Type: application/json" \
  -d '{
    "miner_id": "createkr",
    "email": "user@example.com",
    "alert_types": ["offline", "reward"]
  }'

# Get history
curl "https://rustchain.org/api/alert/history?miner_id=createkr&limit=10"

# Send test alert
curl -X POST https://rustchain.org/api/alert/test \
  -H "Content-Type: application/json" \
  -d '{"miner_id": "createkr", "channel": "email"}'
```

---

## Security

- **Rate Limiting**: Max 10 alerts per type per 24h per miner
- **Email Passwords**: Use app-specific passwords, never main password
- **SMS Tokens**: Store Twilio credentials securely
- **Database**: SQLite with proper connection handling

---

## Troubleshooting

### Email not sending

1. Check SMTP credentials in config
2. For Gmail, use [App Password](https://support.google.com/accounts/answer/185833)
3. Check firewall (port 587 for SMTP)

### SMS not sending

1. Install Twilio: `pip install twilio`
2. Verify Account SID and Auth Token
3. Check phone number format (+1234567890)

### High alert volume

Increase thresholds in config:
```json
{
  "alert_settings": {
    "offline_threshold_hours": 2,
    "large_transfer_threshold_rtc": 500,
    "rate_limit_per_24h": 5
  }
}
```

---

## Files

- `miner_alert_system.py` - Main alert monitoring daemon
- `alert_config.example.json` - Configuration template
- `../../node/alert_endpoints.py` - API endpoints for preferences
- `../../node/migrations/add_alert_tables.sql` - Database schema

---

## License

SPDX-License-Identifier: MIT
