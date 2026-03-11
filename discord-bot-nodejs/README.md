# 🤖 RustChain Discord Bot

A Discord bot that provides real-time RustChain blockchain information and tipping functionality.

## 🎯 Features

| Command | Description | Bounty Value |
|---------|-------------|--------------|
| `/balance` | Check RTC balance by wallet address | Part of 10 RTC |
| `/miners` | View top miners or specific miner info | Part of 10 RTC |
| `/epoch` | Current epoch status and progress | Part of 10 RTC |
| `/health` | Network and node health status | Part of 10 RTC |
| `/tip` | Tip other users with RTC | **+5 RTC Bonus** |

**Total Bounty: 15 RTC** (10 + 5 bonus)

## 🚀 Quick Start

### Prerequisites

- Node.js >= 16.0.0
- Discord Bot Token
- RustChain API access

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd rustchain-discord-bot

# Install dependencies
npm install

# Configure environment
cp .env.example .env

# Edit .env and add your Discord bot token
# DISCORD_TOKEN=your_token_here
# DISCORD_CLIENT_ID=your_client_id_here
```

### Running the Bot

```bash
# Production
npm start

# Development (with auto-reload)
npm run dev
```

## 📋 Commands Usage

### `/balance [address]`
Check your RustChain balance.
```
/balance address:0x1234567890abcdef
```

### `/miners [limit] [address]`
View top miners or specific miner info.
```
/miners limit:10
/miners address:0x1234567890abcdef
```

### `/epoch [epoch_number]`
View current or specific epoch information.
```
/epoch
/epoch epoch:12345
```

### `/health`
Check network health status.
```
/health
```

### `/tip @user amount [message]`
Tip another user with RTC.
```
/tip @friend 5.0 message:Great work!
```

## 🔧 Configuration

### Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section and create a bot
4. Copy the bot token to `.env`
5. Enable "Message Content Intent"
6. Invite bot to your server:
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=274878024768&scope=bot%20applications.commands
   ```

### RustChain API

The bot connects to `https://api.rustchain.org` by default. Modify `RUSTCHAIN_API_URL` in `.env` if needed.

## 📁 Project Structure

```
rustchain-discord-bot/
├── index.js              # Main entry point
├── commands/
│   ├── balance.js        # Balance query command
│   ├── miners.js         # Miner information command
│   ├── epoch.js          # Epoch status command
│   ├── health.js         # Health check command
│   └── tip.js            # Tipping command (bonus)
├── .env.example          # Environment template
├── .gitignore
├── package.json
└── README.md
```

## 🎬 Demo

![Demo GIF](./demo.gif)

## 📝 License

MIT License - See LICENSE file for details.

## 🙋 Bounty Claim

This bot was created for the RustChain bounty program.

**Issue:** [#1596](https://github.com/Scottcjn/rustchain-bounties/issues/1596)
**Claim:** `/claim #1596`

---

Built with ❤️ for the RustChain ecosystem
