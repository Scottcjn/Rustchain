# Discord Rich Presence for RustChain Miners

Show your mining status directly in your Discord profile!

## Features

- 💰 Current RTC balance
- ⛏️ Current hashrate
- 📝 Attestation count
- ⏱️ Miner uptime
- 🖥️ Hardware type (G4/G5/POWER8/etc)
- 📅 Current epoch

## Requirements

```bash
pip install pypresence requests
```

## Setup

1. **Create a Discord Application**:
   - Go to https://discord.com/developers/applications
   - Create a new application
   - Go to "Rich Presence" → "Art Assets"
   - Upload a 512x512 image (name it "rustchain_logo")
   - Copy the "Client ID"

2. **Install the script**:
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/tools/discord_rpc
pip install -r requirements.txt
```

## Usage

### Command Line:
```bash
python discord_rpc.py --wallet YOUR_WALLET --client-id YOUR_CLIENT_ID
```

### Environment Variables:
```bash
export RUSTCHAIN_WALLET=your_wallet
export DISCORD_CLIENT_ID=your_client_id
python discord_rpc.py
```

## Discord Setup

1. Open Discord
2. Click the gear icon next to your username
3. Enable "Developer Mode"
4. The presence will show under your username in servers that have the app installed

## Reward

This implements **Bounty #25** - Discord Rich Presence for Miners (50 RTC)

## License

MIT
