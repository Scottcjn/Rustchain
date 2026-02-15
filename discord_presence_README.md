# RustChain Discord Rich Presence

Show your RustChain mining status in Discord profile!

## Features

- ✅ Display hardware type (PowerPC G4/G5, POWER8, Apple Silicon, etc.)
- ✅ Show antiquity multiplier (2.5x for G4, 2.0x for G5, etc.)
- ✅ Real-time RTC balance
- ✅ Track RTC earned today
- ✅ Miner online status (based on last attestation)
- ✅ Current epoch and slot number
- ✅ Node health information

## Prerequisites

1. **Python 3.7+** installed
2. **Discord account** with Discord running
3. **Discord Application** for Rich Presence
4. **Active RustChain miner** enrolled in the network

## Step 1: Create Discord Application

1. Go to https://discord.com/developers/applications
2. Click "New Application"
3. Name it "RustChain Miner" (or any name you like)
4. Click "Create"
5. Copy the **Application ID** (you'll need this as `--client-id`)
6. Go to "Rich Presence" > "Art Assets"
7. Upload images (optional):
   - Large image: RustChain logo
   - Small image: Mining icon
8. Enable Rich Presence

## Step 2: Install Dependencies

```bash
pip install -r discord_requirements.txt
```

Or manually:

```bash
pip install pypresence requests
```

## Step 3: Run the Script

Replace `YOUR_MINER_ID` with your wallet/miner address and `YOUR_CLIENT_ID` with your Discord Application ID:

```bash
python3 discord_rich_presence.py \
  --miner-id YOUR_MINER_ID \
  --client-id YOUR_CLIENT_ID
```

Example:

```bash
python3 discord_rich_presence.py \
  --miner-id eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC \
  --client-id 123456789012345678
```

## Optional Arguments

- `--interval SECONDS` - Update interval (default: 60 seconds)
- `--miner-id ID` - Your miner wallet address (required)
- `--client-id ID` - Discord Application ID (required for Discord connection)

## Finding Your Miner ID

### Option 1: From Miner Output

When your miner runs, it displays your miner ID (wallet address):

```
[2026-02-13 12:34:56] Miner enrolled: eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC
```

### Option 2: From API

List all active miners:

```bash
curl -sk https://50.28.86.131/api/miners | jq '.[].miner'
```

### Option 3: From Wallet

If you have your wallet address, use that.

## Discord Rich Presence Display

When running, your Discord profile will show:

**Top line (state):**
```
🍎 PowerPC G4 2.5x · Online
```

**Bottom line (details):**
```
Balance: 118.35 RTC
```

**Hover on large image:**
```
PowerPC G4 (Vintage) (2.5x reward)
```

**Hover on small image:**
```
E62 · S9010
```

## Troubleshooting

### "No --client-id provided"

You must create a Discord Application to use Discord Rich Presence:

1. Go to https://discord.com/developers/applications
2. Create a new application
3. Copy the Application ID
4. Pass it as `--client-id YOUR_ID`

### "Failed to connect to Discord"

1. Make sure Discord is running on your computer
2. Make sure you're logged in to Discord
3. Check that you're not in "Invisible" status (appear "Online" or "Idle")
4. Try restarting Discord

### "Miner not found in active miners list"

Your miner must be:
1. Running and actively submitting attestations
2. Enrolled in the current epoch
3. Visible in the miners list API

Check your miner status:

```bash
curl -sk https://50.28.86.131/api/miners | jq '.[] | select(.miner=="YOUR_MINER_ID")'
```

### Balance shows 0.0 or "Error getting balance"

1. Verify your miner ID is correct
2. Make sure you're using the full wallet address (including "RTC" suffix if applicable)
3. Check network connectivity: `curl -sk https://50.28.86.131/health`

## Advanced Usage

### Run as Background Service

**Linux (systemd):**

Create `/etc/systemd/user/rustchain-discord.service`:

```ini
[Unit]
Description=RustChain Discord Rich Presence
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/Rustchain
ExecStart=/usr/bin/python3 /path/to/Rustchain/discord_rich_presence.py \
  --miner-id YOUR_MINER_ID \
  --client-id YOUR_CLIENT_ID
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

Enable and start:

```bash
systemctl --user enable rustchain-discord
systemctl --user start rustchain-discord
systemctl --user status rustchain-discord
```

**macOS (launchd):**

Create `~/Library/LaunchAgents/com.rustchain.discord.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rustchain.discord</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/Rustchain/discord_rich_presence.py</string>
        <string>--miner-id</string>
        <string>YOUR_MINER_ID</string>
        <string>--client-id</string>
        <string>YOUR_CLIENT_ID</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Load and start:

```bash
launchctl load ~/Library/LaunchAgents/com.rustchain.discord.plist
launchctl start com.rustchain.discord
```

## Privacy & Data

This script:
- ✅ Only reads public API data (miner list, balance, epoch info)
- ✅ Does NOT access your private key or seed phrase
- ✅ Does NOT store any sensitive information
- ✅ Tracks local state for earnings calculation (stored in `~/.rustchain_discord_state.json`)

## License

MIT License - Same as RustChain repository.

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify your miner is actively running
3. Test API endpoints manually with curl
4. Open an issue on GitHub: https://github.com/Scottcjn/Rustchain/issues

---

**Happy Mining! 🍎**
