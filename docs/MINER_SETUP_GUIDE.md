# RustChain Miner Setup Guide

> **Step-by-step installation guide for RustChain mining on Ubuntu, macOS, and Raspberry Pi**

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Install (Recommended)](#quick-install-recommended)
- [Platform-Specific Guides](#platform-specific-guides)
  - [Ubuntu/Debian Linux](#ubuntudebian-linux)
  - [macOS (Intel & Apple Silicon)](#macos-intel--apple-silicon)
  - [Raspberry Pi](#raspberry-pi)
  - [Vintage PowerPC Macs](#vintage-powerpc-macs)
- [Verification](#verification)
- [Managing the Miner](#managing-the-miner)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

---

## Overview

RustChain uses **Proof-of-Antiquity (PoA)** consensus, which rewards older hardware with higher mining multipliers. Your vintage PowerPC G4 earns more than a modern Threadripper!

**Antiquity Multipliers:**

| Hardware | Era | Multiplier |
|----------|-----|------------|
| PowerPC G4 | 1999-2005 | **2.5×** |
| PowerPC G5 | 2003-2006 | **2.0×** |
| PowerPC G3 | 1997-2003 | **1.8×** |
| IBM POWER8 | 2014+ | **1.5×** |
| Apple Silicon M1 | 2020+ | **1.2×** |
| Modern x86_64 | Current | **1.0×** |

---

## Prerequisites

### System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| CPU | Any (vintage preferred!) | PowerPC G4/G5 for best rewards |
| RAM | 256 MB | 512 MB+ |
| Disk | 50 MB | 100 MB |
| Network | Internet connection | Stable broadband |
| Python | 3.6+ (2.5+ for vintage Macs) | Python 3.9+ |

### Software Requirements

- **curl** or **wget** for downloading
- **Python 3** with pip
- **systemd** (Linux) or **launchd** (macOS) for auto-start

---

## Quick Install (Recommended)

The one-liner installer works on most systems:

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install.sh | bash
```

**With a specific wallet name:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install.sh | bash -s -- --wallet my-mining-wallet
```

The installer will:
1. ✅ Auto-detect your platform (OS and architecture)
2. ✅ Create isolated Python virtualenv at `~/.rustchain/venv`
3. ✅ Install required dependencies
4. ✅ Download the correct miner for your hardware
5. ✅ Prompt for wallet name (or auto-generate)
6. ✅ Optionally set up auto-start on boot

---

## Platform-Specific Guides

### Ubuntu/Debian Linux

#### Step 1: Install Prerequisites

```bash
# Update package lists
sudo apt update

# Install Python and dependencies
sudo apt install -y python3 python3-pip python3-venv curl

# Verify Python version
python3 --version  # Should be 3.6+
```

#### Step 2: Run Installer

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install.sh | bash
```

Follow the prompts to:
- Enter a wallet name (e.g., `ubuntu-server-01`)
- Enable auto-start (recommended)

#### Step 3: Verify Installation

```bash
# Check miner status
systemctl --user status rustchain-miner

# View logs
journalctl --user -u rustchain-miner -f

# Check balance
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

#### Manual Installation (Alternative)

```bash
# Clone repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install requests

# Run miner
python3 miners/linux/rustchain_linux_miner.py --wallet my-wallet
```

---

### macOS (Intel & Apple Silicon)

#### Step 1: Install Prerequisites

```bash
# Install Xcode Command Line Tools (if not installed)
xcode-select --install

# Verify Python (macOS includes Python 3)
python3 --version
```

#### Step 2: Run Installer

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install.sh | bash
```

#### Step 3: Verify Installation

```bash
# Check if miner is running
launchctl list | grep rustchain

# View logs
tail -f ~/.rustchain/miner.log

# Check balance
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

#### Apple Silicon Notes

Apple Silicon Macs (M1/M2/M3/M4) receive a **1.2× - 1.05×** multiplier. While lower than vintage hardware, you still earn rewards for participating.

To check your chip:
```bash
sysctl -n machdep.cpu.brand_string
# Output: Apple M2 Pro (or similar)
```

---

### Raspberry Pi

RustChain supports Raspberry Pi (ARM architecture). While multipliers are modest (1.0×), Pis are great for low-power 24/7 mining.

#### Step 1: Prepare Your Pi

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3 python3-pip python3-venv curl

# Check architecture
uname -m  # Should show aarch64 or armv7l
```

#### Step 2: Install Miner

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install.sh | bash -s -- --wallet raspberry-pi-01
```

#### Step 3: Optimize for Low Power

Create a cron job for automatic restarts:

```bash
# Edit crontab
crontab -e

# Add restart on reboot
@reboot sleep 60 && systemctl --user start rustchain-miner
```

#### Raspberry Pi Best Practices

1. **Use a stable power supply** - Undervoltage causes crashes
2. **Use Ethernet over WiFi** - More reliable connection
3. **Keep cool** - Add heatsinks or a fan
4. **Use an SSD** - Reduces SD card wear

---

### Vintage PowerPC Macs

**This is where RustChain shines!** Vintage PowerPC Macs earn the highest multipliers.

#### Supported Machines

| Machine | CPU | Multiplier |
|---------|-----|------------|
| Power Mac G4 | PowerPC 7450 | **2.5×** |
| PowerBook G4 | PowerPC 7447 | **2.5×** |
| iMac G4 | PowerPC 7445 | **2.5×** |
| Power Mac G5 | PowerPC 970 | **2.0×** |
| iMac G5 | PowerPC 970 | **2.0×** |
| iBook G3/G4 | PowerPC 750/7447 | **1.8× - 2.5×** |

#### Step 1: Prepare Your Mac

**Recommended OS:** Mac OS X Tiger (10.4) or Leopard (10.5)

1. Install Python (comes with OS X, or install from MacPorts)
2. Ensure network connectivity
3. Set energy saver to "never sleep"

#### Step 2: Download Miner

```bash
# On your vintage Mac
cd ~/Desktop
curl -O https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/ppc/rustchain_powerpc_g4_miner_v2.2.2.py
```

#### Step 3: Run Miner

```bash
python rustchain_powerpc_g4_miner_v2.2.2.py --wallet vintage-g4-mac
```

#### Step 4: Auto-Start (Optional)

Create a LaunchAgent for automatic startup:

```bash
# Create plist file
cat > ~/Library/LaunchAgents/com.rustchain.miner.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rustchain.miner</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python</string>
        <string>/Users/YOUR_USERNAME/Desktop/rustchain_powerpc_g4_miner_v2.2.2.py</string>
        <string>--wallet</string>
        <string>vintage-g4-mac</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

# Load the agent
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist
```

---

## Verification

### Check Miner Status

**Linux (systemd):**
```bash
systemctl --user status rustchain-miner
```

**macOS (launchd):**
```bash
launchctl list | grep rustchain
```

### Check Wallet Balance

```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME" | jq .
```

Expected output:
```json
{
  "miner_id": "YOUR_WALLET_NAME",
  "amount_rtc": 12.456789,
  "amount_i64": 12456789
}
```

### Check Node Health

```bash
curl -sk https://50.28.86.131/health | jq .
```

### List Active Miners

```bash
curl -sk https://50.28.86.131/api/miners | jq .
```

Confirm your miner appears in the list!

### Check Current Epoch

```bash
curl -sk https://50.28.86.131/epoch | jq .
```

---

## Managing the Miner

### Linux (systemd)

```bash
# Start miner
systemctl --user start rustchain-miner

# Stop miner
systemctl --user stop rustchain-miner

# Restart miner
systemctl --user restart rustchain-miner

# Disable auto-start
systemctl --user disable rustchain-miner

# Enable auto-start
systemctl --user enable rustchain-miner

# View live logs
journalctl --user -u rustchain-miner -f

# View last 100 log lines
journalctl --user -u rustchain-miner -n 100
```

### macOS (launchd)

```bash
# Start miner
launchctl start com.rustchain.miner

# Stop miner
launchctl stop com.rustchain.miner

# Disable auto-start
launchctl unload ~/Library/LaunchAgents/com.rustchain.miner.plist

# Enable auto-start
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist

# View logs
tail -f ~/.rustchain/miner.log
```

### Manual Running

```bash
# Navigate to installation
cd ~/.rustchain

# Activate virtual environment
source venv/bin/activate

# Run miner manually
python rustchain_miner.py --wallet YOUR_WALLET

# Or use the start script
./start.sh
```

---

## Troubleshooting

### Common Issues

#### "Could not connect to node"

**Cause:** Network issue or node down

**Solution:**
```bash
# Test node connectivity
curl -sk https://50.28.86.131/health

# Check your internet
ping google.com

# Check firewall (Linux)
sudo ufw allow out 443
```

#### "Python virtualenv creation failed"

**Cause:** Missing python3-venv package

**Solution:**
```bash
# Ubuntu/Debian
sudo apt install python3-venv

# Fedora/RHEL
sudo dnf install python3-virtualenv

# macOS
pip3 install --user virtualenv
```

#### "Permission denied: /usr/local/bin/rustchain-mine"

**Cause:** Cannot create symlink (normal on restricted systems)

**Solution:** Use the start script instead:
```bash
~/.rustchain/start.sh
```

#### "Attestation failed: VM_DETECTED"

**Cause:** Running in a virtual machine or container

**Solution:** 
- Run on real hardware for full rewards
- VMs can still mine but earn minimal rewards (1 billionth of normal)
- Docker/Kubernetes containers are detected and penalized

#### "Miner not earning rewards"

**Check:**
1. Is miner running? `systemctl --user status rustchain-miner`
2. Is attestation passing? Check logs for "Attestation accepted"
3. Is miner enrolled? Check `curl -sk https://50.28.86.131/api/miners`
4. Wait for epoch end (rewards distributed at epoch boundaries)

#### Miner crashes repeatedly

**Check logs:**
```bash
# Linux
journalctl --user -u rustchain-miner -n 200

# macOS
cat ~/.rustchain/miner.log | tail -200
```

**Common fixes:**
- Ensure stable internet connection
- Check disk space (`df -h`)
- Restart the service

### Getting Help

- **GitHub Issues:** https://github.com/Scottcjn/Rustchain/issues
- **Documentation:** https://github.com/Scottcjn/Rustchain
- **Explorer:** http://50.28.86.131/explorer

---

## Uninstallation

### Automatic Uninstall

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install.sh | bash -s -- --uninstall
```

### Manual Uninstall

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

---

## Appendix: Directory Structure

After installation, you'll have:

```
~/.rustchain/
├── venv/                    # Python virtual environment
│   ├── bin/
│   │   ├── python          # Isolated Python interpreter
│   │   └── pip             # Isolated pip
│   └── lib/                # Installed packages
├── rustchain_miner.py      # Main miner script
├── fingerprint_checks.py   # Hardware attestation module
├── start.sh                # Convenience start script
└── miner.log               # Miner logs (if auto-start enabled)
```

---

## Appendix: Supported Platforms Matrix

| Platform | Architecture | Status | Notes |
|----------|--------------|--------|-------|
| Ubuntu 20.04+ | x86_64 | ✅ Full | Recommended for servers |
| Ubuntu 20.04+ | ppc64le | ✅ Full | IBM POWER systems |
| Debian 11+ | x86_64 | ✅ Full | |
| Fedora 38+ | x86_64 | ✅ Full | |
| macOS 12+ | arm64 | ✅ Full | Apple Silicon |
| macOS 12+ | x86_64 | ✅ Full | Intel Macs |
| Mac OS X 10.4-10.5 | ppc | ✅ Full | PowerPC G4/G5 |
| Raspberry Pi OS | aarch64 | ✅ Full | Pi 3/4/5 |
| Windows 10/11 | x86_64 | ✅ Full | Python 3.8+ |

---

*RustChain Miner Setup Guide v2.2*  
*Last updated: February 2026*
