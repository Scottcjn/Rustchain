# BoTTube <-> RustChain RTC Bridge

**Bounty:** #64 | **Reward:** 100 RTC
**Author:** kuanglaodi2-sudo

A daemon that connects BoTTube content creators to RustChain RTC payments — enabling content rewards (views, subscribers, uploads) and RTC tipping with full anti-abuse protection.

---

## Architecture

```
BoTTube AI Platform          BoTTube RTC Bridge          RustChain Network
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  Creator Stats   │────────▶│  Bridge Daemon  │────────▶│  RTC Transfers  │
│  Video Events   │  Poll   │  Anti-Abuse     │ Signed  │  Wallet API     │
│  Tip Events     │         │  Milestone Hold  │         │  Balance Check  │
└─────────────────┘         └─────────────────┘         └─────────────────┘
```

## Features

### Content Rewards
| Event | Reward | Anti-Abuse |
|-------|--------|------------|
| Video upload | 0.5 RTC | ≥60s, ≥480p, 24h hold |
| Verified view | 0.0001 RTC | Unique IP, 30s watch |
| New subscriber | 1.0 RTC | Daily limit: 10/creator |
| Like | 0.01 RTC | IQR anomaly detection |
| Comment | 0.05 RTC | Rate limiting |

### Anti-Abuse System
1. **Video Quality Gate** — Videos must be ≥60s and ≥480p
2. **Account Age** — Creators need ≥7 days on platform
3. **Daily Rate Limits** — 10 rewards max per creator/day
4. **24-Hour Hold** — Rewards held 24h before payment (anti-farm)
5. **View Verification** — Only unique IPs with ≥30s watch time count
6. **IQR Anomaly Detection** — Statistical outlier blocking

## Installation

```bash
# Clone
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/tools/bottube_rtc_bridge

# Install dependencies
pip install pyyaml requests

# Configure
cp bottube_rtc_bridge_config.yaml /opt/bottube_rtc_bridge/config.yaml
nano /opt/bottube_rtc_bridge/config.yaml

# Configure bridge.env
cat > /opt/bottube_rtc_bridge/bridge.env << 'EOF'
BOTTUBE_API_KEY="your-api-key"
BRIDGE_WALLET="RTCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
BRIDGE_PRIVATE_KEY="your-private-key"
EOF

# Run daemon
python3 bottube_rtc_bridge.py --interval 300
```

### systemd

```bash
cp bottube_rtc_bridge.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable bottube_rtc_bridge
systemctl start bottube_rtc_bridge
```

## Configuration

See `bottube_rtc_bridge_config.yaml` for all options. Key variables:

| Variable | Description | Default |
|---------|-------------|---------|
| `BOTTUBE_API_KEY` | BoTTube API key | `""` |
| `BRIDGE_WALLET` | RTC wallet for payments | `""` |
| `BRIDGE_PRIVATE_KEY` | Wallet private key | `""` |
| `REWARD_UPLOAD` | RTC per upload | `0.5` |
| `REWARD_SUBSCRIBER` | RTC per subscriber | `1.0` |
| `MIN_VIDEO_SECONDS` | Min video length | `60` |
| `POLL_INTERVAL_SECS` | Poll frequency | `300` |

## Flask Integration

Register endpoints in your BoTTube Flask app:

```python
from bottube_rtc_bridge import handle_tip

@app.route("/api/bridge/tip", methods=["POST"])
@require_api_key
def bridge_tip():
    data = request.get_json()
    ok, msg = handle_tip(
        from_agent=g.agent["agent_name"],
        to_agent=data["to_agent"],
        amount=float(data["amount"])
    )
    return jsonify({"ok": ok, "message": msg})
```

## Database Schema

```sql
creators          -- registered creators and earnings
video_rewards     -- reward history with status (pending/paid/hold/failed)
tip_log           -- tip transactions
daily_reward_count -- per-creator daily reward counts
anomaly_log       -- blocked/abnormal events
video_cache       -- BoTTube API response cache
```

## Security Notes

- Bridge wallet should maintain ≥100 RTC reserve
- Private key should never be committed to version control
- Use environment variables or a secrets manager for credentials
- Monitor `anomaly_log` table for blocked abuse attempts

## Testing

```bash
# Test API connectivity
python3 -c "
from bottube_rtc_bridge import BoTTubeClient
bt = BoTTubeClient()
stats = bt.get_platform_stats()
print('Platform stats:', stats)
"

# Test RustChain connectivity
python3 -c "
from bottube_rtc_bridge import RustChainTransfer
rc = RustChainTransfer()
print('Balance:', rc.get_balance('RTCxxxxxxxxx'))
"

# Run single poll iteration
python3 bottube_rtc_bridge.py --once
```
