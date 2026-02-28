# RustChain Miner Installation Guide

This guide covers installation and setup of the RustChain miner on Linux and macOS systems.

## Quick Install (Recommended)

### Default Installation
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

The installer will:
1. Auto-detect your platform (OS and architecture)
2. Create an isolated Python virtualenv at `~/.rustchain/venv`
3. Install required dependencies (requests) in the virtualenv
4. Download the appropriate miner for your hardware
5. Prompt for your wallet name (or auto-generate one)
6. Ask if you want to set up auto-start on boot
7. Display wallet balance check commands

### Installation with Specific Wallet
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner-wallet
```

This skips the interactive wallet prompt and uses the specified wallet name.

## Supported Platforms

### Linux
- ✅ Ubuntu 20.04, 22.04, 24.04
- ✅ Debian 11, 12
- ✅ Fedora 38, 39, 40
- ✅ RHEL 8, 9
- ✅ Other systemd-based distributions

**Architectures:**
- x86_64 (Intel/AMD 64-bit)
- ppc64le (PowerPC 64-bit Little-Endian)
- ppc (PowerPC 32-bit)

### macOS
- ✅ macOS 12 (Monterey) and later
- ✅ macOS 11 (Big Sur) with limitations

**Architectures:**
- arm64 (Apple Silicon M1/M2/M3)
- x86_64 (Intel Mac)
- powerpc (PowerPC G3/G4/G5)

### Special Hardware
- ✅ IBM POWER8 systems
- ✅ PowerPC G4/G5 Macs
- ✅ Vintage x86 CPUs (Pentium 4, Core 2 Duo, etc.)

## Requirements

### System Requirements
- Python 3.6+ (or Python 2.5+ for vintage PowerPC systems)
- curl or wget
- 50 MB disk space
- Internet connection

### Linux-Specific
- systemd (for auto-start feature)
- python3-venv or virtualenv package

### macOS-Specific
- Command Line Tools (installed automatically if needed)
- launchd (built into macOS)

## Installation Directory Structure

After installation, you'll have the following structure at `~/.rustchain/`:

```
~/.rustchain/
├── venv/                    # Isolated Python virtualenv
│   ├── bin/
│   │   ├── python          # Virtualenv Python interpreter
│   │   └── pip             # Virtualenv pip
│   └── lib/                # Installed packages (requests, etc.)
├── rustchain_miner.py      # Main miner script
├── fingerprint_checks.py   # Hardware attestation module
├── start.sh                # Convenience start script
└── miner.log               # Miner logs (if auto-start enabled)
```

## Auto-Start Configuration

### Linux (systemd)

The installer creates a user service at:
```
~/.config/systemd/user/rustchain-miner.service
```

**Service Management Commands:**
```bash
# Check miner status
systemctl --user status rustchain-miner

# Start mining
systemctl --user start rustchain-miner

# Stop mining
systemctl --user stop rustchain-miner

# Restart mining
systemctl --user restart rustchain-miner

# Disable auto-start
systemctl --user disable rustchain-miner

# Enable auto-start
systemctl --user enable rustchain-miner

# View logs
journalctl --user -u rustchain-miner -f
```

### macOS (launchd)

The installer creates a launch agent at:
```
~/Library/LaunchAgents/com.rustchain.miner.plist
```

**Service Management Commands:**
```bash
# Check if miner is running
launchctl list | grep rustchain

# Start mining
launchctl start com.rustchain.miner

# Stop mining
launchctl stop com.rustchain.miner

# Disable auto-start
launchctl unload ~/Library/LaunchAgents/com.rustchain.miner.plist

# Enable auto-start
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist

# View logs
tail -f ~/.rustchain/miner.log
```

## Checking Your Wallet

### Balance Check
```bash
# Note: Using -k flag because node may use self-signed SSL certificate
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

Example output:
```json
{
  "miner_id": "my-miner-wallet",
  "amount_rtc": 12.456,
  "amount_i64": 12456000
}
```

### Active Miners
```bash
curl -sk https://50.28.86.131/api/miners
```

### Node Health
```bash
curl -sk https://50.28.86.131/health
```

### Current Epoch
```bash
curl -sk https://50.28.86.131/epoch
```

## Manual Operation

If you chose not to set up auto-start, you can run the miner manually:

### Using the Start Script
```bash
cd ~/.rustchain && ./start.sh
```

### Direct Python Execution
```bash
cd ~/.rustchain
./venv/bin/python rustchain_miner.py --wallet YOUR_WALLET_NAME
```

### Using Convenience Command (if available)
```bash
rustchain-mine
```

Note: The convenience command is only available if `/usr/local/bin` was writable during installation.

## Uninstallation

### Complete Uninstall
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

This will:
1. Stop and remove the systemd/launchd service
2. Remove the entire `~/.rustchain` directory (including virtualenv)
3. Remove the convenience symlink (if it exists)
4. Clean up all configuration files

### Manual Uninstall

If the automated uninstall doesn't work, you can manually remove:

**Linux:**
```bash
# Stop and disable service
systemctl --user stop rustchain-miner
systemctl --user disable rustchain-miner
rm ~/.config/systemd/user/rustchain-miner.service
systemctl --user daemon-reload

# Remove files
rm -rf ~/.rustchain
rm -f /usr/local/bin/rustchain-mine
```

**macOS:**
```bash
# Stop and remove service
launchctl unload ~/Library/LaunchAgents/com.rustchain.miner.plist
rm ~/Library/LaunchAgents/com.rustchain.miner.plist

# Remove files
rm -rf ~/.rustchain
rm -f /usr/local/bin/rustchain-mine
```

## Troubleshooting

### Python virtualenv creation fails

**Error:** `Could not create virtual environment`

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install python3-venv

# Fedora/RHEL
sudo dnf install python3-virtualenv

# macOS
pip3 install --user virtualenv
```

### Permission denied when creating symlink

**Error:** `ln: /usr/local/bin/rustchain-mine: Permission denied`

This is normal. The installer will continue without the convenience command. You can still use the start script:
```bash
~/.rustchain/start.sh
```

### systemd service fails to start

**Check the logs:**
```bash
journalctl --user -u rustchain-miner -n 50
```

Common issues:
- Network not available at boot: The service will retry automatically
- Python path incorrect: Reinstall the miner
- Wallet name with special characters: Use alphanumeric characters only

### launchd service not loading on macOS

**Check if it's loaded:**
```bash
launchctl list | grep rustchain
```

**Reload manually:**
```bash
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist
```

**Check the logs:**
```bash
cat ~/.rustchain/miner.log
```

### Connection to node fails

**Error:** `Could not connect to node`

**Check:**
1. Internet connection is working
2. Node is accessible: `curl -sk https://50.28.86.131/health`
3. Firewall isn't blocking HTTPS (port 443)

### Miner not earning rewards

**Check:**
1. Miner is actually running: `systemctl --user status rustchain-miner` or `launchctl list | grep rustchain`
2. Wallet balance: `curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"`
3. Miner logs for errors: `journalctl --user -u rustchain-miner -f` or `tail -f ~/.rustchain/miner.log`
4. Hardware attestation passes: Look for "fingerprint validation" messages in logs

### Running Multiple Miners

To run multiple miners on different hardware:

1. Install on each machine separately
2. Use different wallet names for each miner
3. Each miner will be independently tracked by the network

### Updating the Miner

To update to the latest version:
```bash
# Uninstall old version
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall

# Install new version
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet YOUR_WALLET_NAME
```

## Getting Help

- **Documentation:** https://github.com/Scottcjn/Rustchain
- **Issues:** https://github.com/Scottcjn/Rustchain/issues
- **Explorer:** https://50.28.86.131/explorer
- **Bounties:** https://github.com/Scottcjn/rustchain-bounties

## Security Notes

1. The installer uses HTTPS to download files from GitHub
2. Python dependencies are installed in an isolated virtualenv (no system pollution)
3. The miner runs as your user (not root)
4. Services are user-level (systemd --user, ~/Library/LaunchAgents)
5. All logs are stored in your home directory
6. **SSL Certificate:** The RustChain node (50.28.86.131) may use a self-signed SSL certificate. The `-k` flag in curl commands bypasses certificate verification. This is a known limitation of the current infrastructure. In production, you should verify the node's identity through other means (community consensus, explorer verification, etc.).

To view the certificate SHA-256 fingerprint:

```bash
openssl s_client -connect 50.28.86.131:443 < /dev/null 2>/dev/null | openssl x509 -fingerprint -sha256 -noout
```

If you want to avoid using `-k`, you can save the certificate locally and pin it:

```bash
# Save the cert once (overwrite if it changes)
openssl s_client -connect 50.28.86.131:443 < /dev/null 2>/dev/null | openssl x509 > ~/.rustchain/rustchain-cert.pem

# Then use it instead of -k
curl --cacert ~/.rustchain/rustchain-cert.pem "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

## Contributing

Found a bug or want to improve the installer? Submit a PR to:
https://github.com/Scottcjn/Rustchain

## License

RustChain is licensed under the MIT License. See LICENSE file for details.
