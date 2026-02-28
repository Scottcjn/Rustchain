# Discord Leaderboard Bot

File: `tools/discord_leaderboard_bot.py`

This script posts a RustChain leaderboard message to a Discord webhook.

## Features

- Top N miners by current balance
- Current epoch summary
- Architecture distribution
- Optional current-epoch top earners from `/rewards/epoch/<epoch>`
- One-shot mode and scheduled loop mode

## Quick Start

```bash
python3 tools/discord_leaderboard_bot.py \
  --node https://rustchain.org \
  --webhook-url "https://discord.com/api/webhooks/xxx/yyy"
```

If you prefer env vars:

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/xxx/yyy"
python3 tools/discord_leaderboard_bot.py --node https://rustchain.org
```

## Dry Run

```bash
python3 tools/discord_leaderboard_bot.py --dry-run
```

## Schedule Mode

Post every hour:

```bash
python3 tools/discord_leaderboard_bot.py --schedule-seconds 3600
```

## Useful Flags

- `--top-n 10`
- `--timeout 10`
- `--title-prefix "RustChain daily leaderboard"`

## Notes

- The node may use a self-signed certificate. The script allows that intentionally for this endpoint.
- Missing per-miner balance responses are handled without crashing the run.
