# RustChain Discord Bot

Discord bot that queries the RustChain API and exposes blockchain data through slash commands.

## Commands

| Command | Description |
|---------|-------------|
| `/health` | Check RustChain node health status |
| `/epoch` | Get current epoch, slot, and height info |
| `/balance <miner_id>` | Look up RTC balance for a miner wallet |
| `/miners` | List active miners with hardware details |
| `/tip <to_miner> <amount>` | Generate a signed-transfer payload to tip RTC |

## Setup

1. **Create a Discord application** at https://discord.com/developers/applications
2. Add a Bot and copy the token
3. Invite the bot to your server with the `applications.commands` and `bot` scopes

### Install

```bash
pip install -r requirements.txt
```

### Configure

Set environment variables (or create a `.env` file):

```
DISCORD_TOKEN=your_bot_token_here
RUSTCHAIN_NODE_URL=https://rustchain.org   # optional, this is the default
API_TIMEOUT=10                              # optional, seconds
```

### Run

```bash
python bot.py
```

## API Endpoints Used

- `GET /health` -- node health status
- `GET /epoch` -- current epoch info
- `GET /wallet/balance?miner_id=<id>` -- wallet balance
- `GET /api/miners` -- active miner list
- `POST /wallet/transfer/signed` -- signed RTC transfer (used by `/tip` info)

## Notes

- The RustChain node uses a self-signed TLS certificate; the bot disables certificate verification for API calls.
- The `/tip` command does **not** execute transfers directly. It provides the recipient, amount, and a pre-filled JSON payload template so users can sign and submit the transaction with their own wallet tooling.

## License

See repository root LICENSE.
