# RustChain Telegram Bot

A lightweight Telegram bot for the RustChain community.

## Features

- `/price` - Current wRTC price from Raydium
- `/miners` - Active miner count from `/api/miners`
- `/epoch` - Current epoch info
- `/balance <wallet>` - Check RTC balance
- `/health` - Node health status

## Requirements

```bash
pip install python-telegram-bot requests
```

## Installation

1. Clone this repository:
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/tools/telegram_bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a Telegram bot:
   - Message @BotFather on Telegram
   - Use `/newbot` to create a new bot
   - Copy the bot token

## Usage

### With environment variables:
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
python telegram_bot.py
```

### With command-line arguments:
```bash
python telegram_bot.py --token "your_bot_token_here"
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show help |
| `/price` | Get wRTC price |
| `/miners` | Get active miner count |
| `/epoch` | Get current epoch |
| `/balance <wallet>` | Check wallet balance |
| `/health` | Check node health |

## Deployment

### Systemd Service (Linux)

Create `/etc/systemd/system/rustchain-bot.service`:

```ini
[Unit]
Description=RustChain Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/path/to/Rustchain/tools/telegram_bot
ExecStart=/usr/bin/python3 telegram_bot.py --token YOUR_TOKEN
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable rustchain-bot
sudo systemctl start rustchain-bot
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY telegram_bot.py .
CMD ["python", "telegram_bot.py"]
```

Build and run:
```bash
docker build -t rustchain-bot .
docker run -d -e TELEGRAM_BOT_TOKEN=your_token rustchain-bot
```

## Bonus Features (Not Implemented)

- Mining alerts (new miner joins, epoch settles)
- Price alerts (wRTC moves >5%)
- Inline query support
- Tip functionality via `/tip @user 5`

## License

MIT
