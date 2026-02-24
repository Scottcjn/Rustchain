# RustChain Miner Alert System

Alerts miners on:
- offline/online transitions
- rewards received (balance increase)
- large balance transfers
- stale attestation windows

## Setup
```bash
pip install -r requirements-alerts.txt
```

Create `miner_watchlist.json`:
```json
{
  "miners": [
    {"miner_id": "createker02140054RTC", "email": "you@example.com", "phone": "+1234567890"}
  ]
}
```

## SMTP env vars
- `SMTP_SERVER`
- `SMTP_PORT` (default 587)
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`

## Twilio env vars (optional)
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`

## Run
```bash
python3 miner_alerts.py --once
python3 miner_alerts.py --interval 300
```

## Tuning
- `--transfer-threshold` (default 50 RTC)
- `--attestation-stale-seconds` (default 18000 = 5h)
