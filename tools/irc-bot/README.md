# RustChain IRC Bot

Lightweight IRC bot for monitoring RustChain network status directly from IRC.
Zero external dependencies — uses only the Python standard library.

## Commands

| Command             | Description                          |
|---------------------|--------------------------------------|
| `!status`           | Node health overview                 |
| `!balance <wallet>` | Check wallet balance                 |
| `!miners`           | Active miner count and details       |
| `!epoch`            | Current epoch information            |
| `!price`            | wRTC price from DexScreener          |
| `!help`             | List available commands              |

## Quick Start

```bash
python tools/irc-bot/bot.py
```

## Configuration

All settings are controlled via environment variables:

| Variable             | Default                  | Description              |
|----------------------|--------------------------|--------------------------|
| `IRC_SERVER`         | `irc.libera.chat`        | IRC server hostname      |
| `IRC_PORT`           | `6697`                   | IRC server port          |
| `IRC_USE_SSL`        | `true`                   | Enable TLS               |
| `IRC_NICK`           | `RustChainBot`           | Bot nickname             |
| `IRC_CHANNEL`        | `#rustchain`             | Channel to join          |
| `RUSTCHAIN_NODE_URL` | `https://rustchain.org`  | Node API base URL        |

### Example

```bash
export IRC_SERVER=irc.libera.chat
export IRC_PORT=6697
export IRC_NICK=RustChainBot
export IRC_CHANNEL="#rustchain"
export RUSTCHAIN_NODE_URL=https://rustchain.org
python tools/irc-bot/bot.py
```

## Features

- TLS support (enabled by default)
- Automatic reconnection on disconnect
- Per-command rate limiting (3s cooldown)
- Long message splitting for IRC line limits
- PING/PONG keepalive handling
- Queries the RustChain node API (`/health`, `/epoch`, `/api/miners`, `/api/balance/<addr>`, `/headers/tip`)
- Fetches wRTC price from the DexScreener public API

## Requirements

- Python 3.7+
- No third-party packages needed
