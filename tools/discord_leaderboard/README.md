# RustChain Weekly Miner Leaderboard Bot

Posts weekly/daily mining leaderboards to Discord.

## Features

- 🏆 Top 10 miners by RTC balance
- 📊 Architecture distribution (% G4, % G5, % modern)
- 📈 Network stats (total miners, total RTC)
- ⏰ Scheduled posting (daily/epoch-based)

## Requirements

```bash
pip install requests discord-webhook
```

## Usage

### Command Line:
```bash
python leaderboard_bot.py --webhook "YOUR_DISCORD_WEBHOOK_URL"
```

### With cron (daily):
```bash
# Add to crontab
0 0 * * * /path/to/leaderboard_bot.py --webhook YOUR_URL >> /var/log/rustchain-leaderboard.log 2>&1
```

### Docker:
```bash
docker build -t rustchain-leaderboard .
docker run -d -e DISCORD_WEBHOOK=your_url rustchain-leaderboard
```

## Reward

This implements **Bounty #45** - Weekly Miner Leaderboard Bot for Discord (25 RTC)

## License

MIT
