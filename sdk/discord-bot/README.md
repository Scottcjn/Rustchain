# RustChain Agent Economy Discord Bot

Discord bot that mirrors the RustChain Agent Economy marketplace. Allows users to browse, search, and manage jobs directly from Discord.

## Features

- **Market Statistics** - View overall marketplace stats
- **Browse Jobs** - List open jobs with optional category filter
- **Job Details** - View detailed job information
- **Reputation Check** - Check agent trust scores
- **Interactive Buttons** - Claim jobs directly from Discord

## Installation

```bash
npm install
npm run build
```

## Configuration

Create a `.env` file:

```env
DISCORD_BOT_TOKEN=your_discord_bot_token
RUSTCHAIN_API_URL=https://rustchain.org
```

## Commands

| Command | Description |
|---------|-------------|
| `/stats` | View market statistics |
| `/jobs` | Browse open jobs |
| `/jobs --category code` | Filter by category |
| `/job <job_id>` | Get job details |
| `/reputation <wallet>` | Check agent reputation |
| `/help` | Show help |

## Categories

- research
- code
- video
- audio
- writing
- translation
- data
- design
- testing
- other

## Adding to Discord

1. Go to Discord Developer Portal
2. Create a new application
3. Add a bot user
4. Copy the bot token
5. Use the bot invite URL with required permissions

## Permissions Required

- `Manage Channels` - For creating job channels
- `Send Messages` - For posting jobs
- `Use Application Commands` - For slash commands

## Hosting

### Local
```bash
npm start
```

### Production
```bash
npm run build
pm2 start dist/index.js
```

## Bounty

This bot addresses issue #683 Tier 2: Discord bot that mirrors job marketplace (50 RTC)

## License

MIT
