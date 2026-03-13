# 🤖 RustChain Discord Bot V2

A Discord bot that provides real-time RustChain blockchain information with **real API integration**.

## ✅ What's New in V2

**V1 Issues (Fixed in V2):**
- ❌ Wrong API endpoint (`api.rustchain.org` → `50.28.86.131`)
- ❌ Wrong data models (fake fields → real PoA fields)
- ❌ Fake /tip (random hash → real Ed25519 signing)
- ❌ Chinese demo files → English documentation

**V2 Improvements:**
- ✅ **Real API Integration** - Uses actual RustChain node at `https://50.28.86.131`
- ✅ **Correct Data Models** - `device_arch`, `device_family`, `antiquity_multiplier`
- ✅ **Real Wallet Signing** - Ed25519 signatures for /tip command
- ✅ **English Documentation** - All files in English

## 🚀 Features

| Command | Description | API Endpoint |
|---------|-------------|--------------|
| `/health` | Check node health status | `/health` |
| `/epoch` | Current epoch info | `/epoch` |
| `/balance <miner_id>` | Check RTC balance | `/wallet/balance` |
| `/miners [limit] [address]` | View top miners | `/api/miners` |
| `/tip <recipient> <amount>` | Send RTC tip | `/wallet/transfer/signed` |

## 📦 Installation

```bash
# Install dependencies
npm install

# Configure environment
cp .env.example .env

# Edit .env and add your Discord bot token
# Optional: Add wallet keys for /tip command
```

## 🎮 Usage

```bash
# Start the bot
npm start

# Development mode (auto-reload)
npm run dev
```

## 🔑 Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section and create a bot
4. Copy the bot token to `.env`
5. Enable "Message Content Intent"
6. Invite bot to your server:
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=274878024768&scope=bot%20applications.commands
   ```

## 💰 Wallet Setup (for /tip)

Generate Ed25519 keypair:

```bash
node -e "const nacl=require('tweetnacl'); const kp=nacl.sign.keyPair(); console.log('Public:', Buffer.from(kp.publicKey).toString('base64')); console.log('Secret:', Buffer.from(kp.secretKey).toString('base64'));"
```

Add to `.env`:
```
WALLET_PUBLIC_KEY=your_base64_public_key
WALLET_SECRET_KEY=your_base64_secret_key
```

**⚠️ Security:** Never commit `.env` file! Keep your secret key private.

## 📊 Example Output

### `/health`
```
🏥 RustChain Node Health
Status: ✅ Online
Version: 2.2.1-rip200
Database: ✅ Read/Write
Uptime: 1d 2h 15m
Backup Age: 20.01 hours
```

### `/epoch`
```
📅 RustChain Epoch Info
Epoch: #99
Slot: 14,273
Blocks/Epoch: 144
Enrolled Miners: 21
Epoch POT: 1.5
Total Supply: 8,388,608 RTC
```

### `/balance`
```
💰 RustChain Balance
Miner ID: RTC1d48d848a5aa5ecf2c5f01aa5fb64837daaf2f35
Balance: 2,985.815034 RTC
Amount (i64): 2,985,815,034
```

### `/miners`
```
⛏️ Top RustChain Miners
1. RTCb0d52c2191707db1ce586efff64275fc91ff346c
   Hardware: x86-64 (Modern) | Multiplier: 1.0x

2. RTC1d48d848a5aa5ecf2c5f01aa5fb64837daaf2f35
   Hardware: Apple Silicon (Modern) | Multiplier: 1.2x
```

## 🛠️ Project Structure

```
discord-bot-nodejs-v2/
├── index.js              # Main entry point
├── package.json          # Dependencies
├── .env.example          # Environment template
├── README.md             # This file
└── commands/
    ├── health.js         # Health check command
    ├── epoch.js          # Epoch info command
    ├── balance.js        # Balance query command
    ├── miners.js         # Miner list command
    └── tip.js            # Tipping command (with Ed25519 signing)
```

## 🎯 Bounty Claim

**Issue:** [#1596](https://github.com/Scottcjn/rustchain-bounties/issues/1596)

**Total Bounty:** 15 RTC (10 base + 5 tip bonus)

/claim #1596

## 📝 API Reference

All commands use the real RustChain API:

- **Base URL:** `https://50.28.86.131`
- **Health:** `GET /health`
- **Epoch:** `GET /epoch`
- **Miners:** `GET /api/miners`
- **Balance:** `GET /wallet/balance?miner_id=<address>`
- **Transfer:** `POST /wallet/transfer/signed`

See `tmp/rustchain-api-reference.md` for full API documentation.

## 📄 License

MIT License

---

**V2 - Built with ❤️ for the RustChain ecosystem**
