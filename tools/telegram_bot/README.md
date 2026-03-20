# RustChain Telegram Community Bot

A comprehensive Telegram bot for RustChain community management with real-time data from RustChain nodes.

## Features

### Core Commands
- `/price` - Current wRTC price from Raydium DEX
- `/miners` - Active miner count and network status
- `/epoch` - Current epoch information and progress
- `/balance <wallet>` - Check RTC balance for any wallet address
- `/health` - Node health status and uptime

### Bonus Features
- **Mining Alerts** - Notifications when new miners join the network
- **Price Alerts** - Alerts when wRTC price moves >5%
- **Inline Queries** - Quick access to data via `@botname query`

## Requirements

### Dependencies
```
python-telegram-bot==20.7
requests==2.31.0
aiohttp==3.9.1
asyncio-throttle==1.0.2
python-dotenv==1.0.0
```

### System Requirements
- Python 3.8+
- Internet connection for API access
- Telegram Bot API token

## Installation & Setup

### 1. Create Telegram Bot
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Use `/newbot` command
3. Choose bot name: `RustChain Community Bot`
4. Choose username: `@rustchain_bot` (or similar)
5. Save the bot token provided

### 2. Clone & Install
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/tools/telegram_bot
pip install -r requirements.txt
```

### 3. Configuration
Create `.env` file:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
RUSTCHAIN_NODE_URL=http://50.28.86.131:8000
RAYDIUM_API_URL=https://api.raydium.io/v2/sdk/token/price
WRTC_TOKEN_ADDRESS=your_wrtc_token_address
PRICE_ALERT_THRESHOLD=5.0
MINING_ALERTS_ENABLED=true
PRICE_ALERTS_ENABLED=true
ADMIN_CHAT_ID=your_admin_chat_id
```

### 4. Start Bot
```bash
python rustchain_bot.py
```

For production deployment:
```bash
nohup python rustchain_bot.py > bot.log 2>&1 &
```

## Usage Examples

### Basic Commands
```
/price
> 💰 wRTC Price: $0.0245 (+3.2%)
> 24h Volume: $12,450
> Last updated: 2 minutes ago

/miners
> ⛏️ Active Miners: 42
> Network Hashrate: 1.2 TH/s
> Difficulty: 145,234

/epoch
> 📊 Epoch #1,234
> Progress: 87% (435/500 blocks)
> Time remaining: ~2.3 hours
> Next reward: 25 RTC

/balance RTC1a2b3c4d5e6f...
> 💳 Balance: 150.75 RTC
> Wallet: RTC1a2b...f7g8h9
> Last transaction: 3 hours ago

/health
> ✅ Node Status: Healthy
> Uptime: 15 days, 6 hours
> Sync: 100% (Latest block: #45,678)
> Peers: 23 connected
```

### Inline Queries
Users can type `@rustchain_bot price` in any chat for quick price data.

### Alert Examples
```
🚨 Mining Alert
New miner joined the network!
Total active miners: 43 (+1)

📈 Price Alert
wRTC price increased by 7.3%!
Current price: $0.0263
```

## Deployment Options

### Option 1: Local Development
```bash
python rustchain_bot.py
```

### Option 2: Docker Deployment
```bash
docker build -t rustchain-bot .
docker run -d --env-file .env rustchain-bot
```

### Option 3: Cloud Deployment (Heroku)
1. Install Heroku CLI
2. Create `Procfile`:
   ```
   worker: python rustchain_bot.py
   ```
3. Deploy:
   ```bash
   heroku create rustchain-telegram-bot
   heroku config:set TELEGRAM_BOT_TOKEN=your_token
   git push heroku main
   ```

### Option 4: VPS Deployment
```bash
# Install dependencies
sudo apt update
sudo apt install python3-pip python3-venv

# Setup service
sudo cp rustchain-bot.service /etc/systemd/system/
sudo systemctl enable rustchain-bot
sudo systemctl start rustchain-bot
```

## API Endpoints Used

### RustChain Node (50.28.86.131)
- `GET /api/miners` - Active miner data
- `GET /epoch` - Current epoch information
- `GET /balance/{address}` - Wallet balance lookup
- `GET /health` - Node health status

### Raydium API
- `GET /v2/sdk/token/price` - wRTC price data

## File Structure
```
tools/telegram_bot/
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── rustchain_bot.py       # Main bot implementation
├── config.py             # Configuration management
├── handlers/             # Command handlers
│   ├── __init__.py
│   ├── basic.py         # Basic commands
│   ├── alerts.py        # Alert system
│   └── inline.py        # Inline queries
├── utils/               # Utility functions
│   ├── __init__.py
│   ├── api.py          # API client
│   └── formatting.py   # Message formatting
├── .env.example         # Environment template
├── Dockerfile          # Docker configuration
├── rustchain-bot.service # Systemd service
└── bot.log             # Runtime logs
```

## Troubleshooting

### Common Issues
1. **Bot Token Invalid**: Verify token from BotFather
2. **API Connection Failed**: Check RustChain node status
3. **Permission Denied**: Ensure bot is added to target groups
4. **Rate Limiting**: Implement proper delays between requests

### Debug Mode
Set environment variable:
```bash
export DEBUG=true
python rustchain_bot.py
```

### Logs Location
- Development: Console output
- Production: `bot.log` file
- Docker: `docker logs container_name`
- Systemd: `journalctl -u rustchain-bot`

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b telegram-bot-feature`
3. Implement changes in `tools/telegram_bot/`
4. Test with real RustChain node
5. Submit pull request with detailed description

## Testing

The bot connects to live RustChain infrastructure (50.28.86.131) for testing. Ensure:
- Commands return real data
- Alerts trigger correctly
- Error handling works properly
- Performance is acceptable

## License

SPDX-License-Identifier: MIT
