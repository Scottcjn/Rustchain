# RustChain Leaderboard Bot

Automated Discord bot that posts RTC mining leaderboards showing top miners, network stats, and hardware distribution.

## Features

- 🏆 **Top Miners Leaderboard** - Rankings by RTC balance
- 📊 **Network Statistics** - Total miners, epoch info, total RTC distributed
- 🖥️ **Hardware Distribution** - Visual breakdown by architecture (PowerPC, ARM, x86_64)
- ⭐ **Rising Star** - Tracks biggest balance gains between updates
- 📈 **Historical Tracking** - Caches data to show trends over time
- ⚙️ **Configurable** - Webhook URL, update frequency, top-N count

## Requirements

- Python 3.6+
- `requests` library

## Installation

1. **Install dependencies:**
   ```bash
   pip install requests
   ```

2. **Create configuration file:**
   ```bash
   python3 leaderboard-bot.py
   ```
   
   This will create `leaderboard-config.json` with default settings.

3. **Edit configuration:**
   ```bash
   nano leaderboard-config.json
   ```
   
   Set your Discord webhook URL (required):
   ```json
   {
     "node_url": "https://50.28.86.131",
     "discord_webhook": "https://discord.com/api/webhooks/YOUR_WEBHOOK_URL",
     "top_n": 10,
     "frequency_hours": 24,
     "cache_file": "leaderboard-cache.json"
   }
   ```

## Usage

### Manual Run

```bash
python3 leaderboard-bot.py
```

### Dry Run (Test Without Posting)

```bash
python3 leaderboard-bot.py --dry-run
```

This will fetch data and print the formatted message without sending it to Discord.

### Scheduled Execution

#### Using cron (Linux/macOS)

Edit crontab:
```bash
crontab -e
```

Add entry for daily updates at 12:00 UTC:
```cron
0 12 * * * cd /path/to/Rustchain && python3 leaderboard-bot.py >> leaderboard.log 2>&1
```

For every 6 hours:
```cron
0 */6 * * * cd /path/to/Rustchain && python3 leaderboard-bot.py >> leaderboard.log 2>&1
```

#### Using systemd (Linux)

Create service file `/etc/systemd/system/rustchain-leaderboard.service`:
```ini
[Unit]
Description=RustChain Leaderboard Bot
After=network.target

[Service]
Type=oneshot
User=rustchain
WorkingDirectory=/home/rustchain/Rustchain
ExecStart=/usr/bin/python3 /home/rustchain/Rustchain/leaderboard-bot.py
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Create timer file `/etc/systemd/system/rustchain-leaderboard.timer`:
```ini
[Unit]
Description=RustChain Leaderboard Bot Timer
Requires=rustchain-leaderboard.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=24h

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl enable rustchain-leaderboard.timer
sudo systemctl start rustchain-leaderboard.timer
sudo systemctl status rustchain-leaderboard.timer
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `node_url` | string | `https://50.28.86.131` | RustChain node API URL |
| `discord_webhook` | string | _(required)_ | Discord webhook URL |
| `top_n` | integer | `10` | Number of top miners to display |
| `frequency_hours` | integer | `24` | Update frequency (for display only) |
| `cache_file` | string | `leaderboard-cache.json` | Historical data cache file |

## Discord Webhook Setup

1. Go to your Discord server settings
2. Navigate to **Integrations** → **Webhooks**
3. Click **New Webhook**
4. Name it "RustChain Leaderboard" (optional)
5. Select the channel where leaderboards should be posted
6. Copy the webhook URL
7. Paste it into `leaderboard-config.json`

## Output Example

```
# ⛏️ RustChain Mining Leaderboard

📊 Network Statistics
• Active Miners: 12
• Current Epoch: 1547
• Block Height: 45283
• Total RTC Distributed: 1,234.5678

🏆 Top 10 Miners
Rank  Miner ID             Balance      Hardware       
─────────────────────────────────────────────────────────────────
🥇    miner_abc123...      125.4500     PowerPC G5     
🥈    miner_def456...      98.3200      PowerPC G4     
🥉    miner_ghi789...      67.1000      x86_64         
4.    miner_jkl012...      45.8900      ARM64          
...

🖥️ Hardware Distribution
PowerPC: ████████████████░░░░ 75.0% (9 miners)
x86_64:  ████░░░░░░░░░░░░░░░░ 16.7% (2 miners)
ARM:     ██░░░░░░░░░░░░░░░░░░ 8.3% (1 miner)

⭐ Rising Star
miner_xyz987 gained +12.3456 RTC since last update!
Current balance: 67.1000 RTC

---
Updated: 2026-02-11 12:00 UTC
Next update in 24 hours
```

## Troubleshooting

### "Error: Discord webhook URL not configured"

Edit `leaderboard-config.json` and add your webhook URL.

### "Error fetching miners: ..."

- Check that the node URL is correct
- Verify the node is online: `curl -sk https://50.28.86.131/health`
- Check firewall/network connectivity

### "SSL certificate verify failed"

The bot disables SSL verification for self-signed certificates (`verify=False`). This is expected for the RustChain node.

### Rate Limiting

The bot includes a 0.1 second delay between balance fetches to avoid overwhelming the node. For 10+ miners, this adds ~1-2 seconds to execution time.

## Files

- `leaderboard-bot.py` - Main bot script
- `leaderboard-config.json` - Configuration (created on first run)
- `leaderboard-cache.json` - Historical data cache (auto-generated)
- `leaderboard.log` - Execution log (if using cron redirect)

## Security Notes

- **Webhook URL is sensitive** - Anyone with your webhook URL can post to your Discord channel
- Store `leaderboard-config.json` with restricted permissions: `chmod 600 leaderboard-config.json`
- Don't commit the config file to public repositories

## License

Apache 2.0 (same as RustChain)

## Contributing

Issues and PRs welcome! Follow the RustChain [CONTRIBUTING.md](CONTRIBUTING.md) guidelines.

## Credits

Built for RustChain bounty #45 (25 RTC)

## Links

- [RustChain GitHub](https://github.com/Scottcjn/Rustchain)
- [Discord Community](https://discord.gg/VqVVS2CW9Q)
- [Block Explorer](https://50.28.86.131/explorer)
