# RustChain Miner Setup Guide

**Complete step-by-step guide for mining RTC on all supported platforms**

**Bounty**: Documentation Sprint (#72) - Miner Setup Guide (20 RTC)  
**Author**: @dlin38  
**Date**: February 12, 2026  
**Version**: 1.0

---

## Table of Contents

1. [Introduction](#introduction)
2. [System Requirements](#system-requirements)
3. [Quick Start (Recommended)](#quick-start-recommended)
4. [Platform-Specific Setup](#platform-specific-setup)
   - [Linux (Ubuntu/Debian)](#linux-ubuntudebian)
   - [Linux (Fedora/RHEL)](#linux-fedorarhel)
   - [macOS (Intel)](#macos-intel)
   - [macOS (Apple Silicon)](#macos-apple-silicon)
   - [macOS (PowerPC)](#macos-powerpc)
   - [Windows (WSL)](#windows-wsl)
5. [Manual Installation](#manual-installation)
6. [Configuration](#configuration)
7. [Managing Your Miner](#managing-your-miner)
8. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
9. [Optimizing Rewards](#optimizing-rewards)
10. [FAQ](#faq)

---

## Introduction

RustChain uses **Proof-of-Antiquity (PoA)** consensus, where older hardware earns more rewards than newer hardware. This guide will help you set up a miner on any supported platform.

### What You'll Need

- **A computer** (the older, the better for rewards!)
- **Internet connection** (stable, always-on preferred)
- **5 minutes** for automated install, or 15 minutes for manual setup

### Rewards Overview

| Hardware | Era | Multiplier | Est. Daily RTC |
|----------|-----|------------|----------------|
| PowerPC G4 | 1999-2005 | 2.5× | ~43.2 RTC |
| PowerPC G5 | 2003-2006 | 2.0× | ~34.6 RTC |
| IBM POWER8 | 2014 | 1.5× | ~25.9 RTC |
| Core 2 Duo | 2006-2011 | 1.3× | ~18.7 RTC |
| Apple Silicon | 2020+ | 1.2× | ~17.3 RTC |
| Modern x86_64 | Current | 1.0× | ~14.4 RTC |

*Estimates based on 144 epochs/day, 1.5 RTC pool/epoch, 5 active miners*

---

## System Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| **CPU** | Any working CPU (vintage preferred!) |
| **RAM** | 256 MB minimum, 512 MB recommended |
| **Storage** | 100 MB free space |
| **Network** | Stable internet connection |
| **OS** | Ubuntu 20.04+, Debian 11+, Fedora 38+, macOS 12+, or WSL2 |

### Supported Architectures

✅ **x86_64** (Intel/AMD 64-bit)  
✅ **ARM64** (Apple Silicon, Raspberry Pi 64-bit)  
✅ **PowerPC** (G3, G4, G5, POWER8+)  
✅ **ppc64le** (IBM POWER8/POWER9)  
⚠️ **ARMv7** (32-bit ARM, partial support)

---

## Quick Start (Recommended)

The **one-line installer** automatically detects your platform and sets up everything.

### 1. Install with Default Wallet

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

The installer will:
- ✅ Detect your CPU architecture
- ✅ Install Python dependencies in isolated virtualenv
- ✅ Download the correct miner binary
- ✅ Generate a random wallet name
- ✅ Set up auto-start service (systemd/launchd)
- ✅ Start mining immediately

### 2. Install with Custom Wallet

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-custom-wallet-name
```

**Wallet naming rules**:
- Lowercase letters, numbers, hyphens, underscores only
- 3-32 characters
- Must start with a letter
- Examples: `vintage-g4`, `my-miner`, `powerbook-2005`

### 3. Verify Installation

```bash
# Check miner status
systemctl --user status rustchain-miner   # Linux
launchctl list | grep rustchain          # macOS

# Check your wallet balance
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**✅ If you see mining logs and a balance response, you're done!** Skip to [Managing Your Miner](#managing-your-miner).

---

## Platform-Specific Setup

Choose your platform below for detailed instructions.

### Linux (Ubuntu/Debian)

**Supported Versions**: Ubuntu 20.04+, Debian 11+, Linux Mint 20+

#### Prerequisites

```bash
# Update package lists
sudo apt update

# Install required packages
sudo apt install -y python3 python3-pip python3-venv curl git

# Verify Python 3.8+
python3 --version
```

#### Automated Install

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-wallet
```

#### Manual Install

```bash
# Clone repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start mining
python3 rustchain_universal_miner.py --wallet my-wallet
```

#### Service Setup (systemd)

Create service file: `~/.config/systemd/user/rustchain-miner.service`

```ini
[Unit]
Description=RustChain PoA Miner
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/Rustchain
ExecStart=%h/Rustchain/venv/bin/python3 rustchain_universal_miner.py --wallet YOUR_WALLET_NAME
Restart=always
RestartSec=10
StandardOutput=append:%h/.rustchain/miner.log
StandardError=append:%h/.rustchain/error.log

[Install]
WantedBy=default.target
```

Enable and start:

```bash
systemctl --user daemon-reload
systemctl --user enable rustchain-miner
systemctl --user start rustchain-miner
```

---

### Linux (Fedora/RHEL)

**Supported Versions**: Fedora 38+, RHEL 9+, Rocky Linux 9+

#### Prerequisites

```bash
# Install required packages
sudo dnf install -y python3 python3-pip python3-virtualenv curl git

# Verify Python
python3 --version
```

#### Installation

Same as Ubuntu/Debian above, but use `dnf` instead of `apt`.

---

### macOS (Intel)

**Supported Versions**: macOS 12 (Monterey) and newer

#### Prerequisites

```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3
brew install python3

# Verify Python
python3 --version
```

#### Automated Install

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-wallet
```

#### Service Setup (launchd)

Create plist: `~/Library/LaunchAgents/com.rustchain.miner.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rustchain.miner</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/YOUR_USERNAME/Rustchain/rustchain_universal_miner.py</string>
        <string>--wallet</string>
        <string>YOUR_WALLET_NAME</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/.rustchain/miner.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/.rustchain/error.log</string>
</dict>
</plist>
```

Load and start:

```bash
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist
launchctl start com.rustchain.miner
```

---

### macOS (Apple Silicon)

**Supported Models**: M1, M1 Pro, M1 Max, M2, M3 series

Same as macOS Intel, but note:
- Uses ARM64 miner binary
- Multiplier: 1.2× (newer hardware)
- Still profitable due to low power consumption

---

### macOS (PowerPC)

**Supported Models**: PowerBook G4, iBook G4, PowerMac G4/G5, iMac G4/G5

**Highest rewards!** PowerPC G4/G5 get 2.0-2.5× multipliers.

#### Prerequisites

**On PowerPC Mac (OS X 10.4/10.5 Tiger/Leopard)**:

```bash
# You'll need MacPorts or Fink for Python 3
# Alternatively, use a modern Linux distro like Debian PowerPC

# If using Debian PowerPC:
sudo apt-get update
sudo apt-get install python3 python3-pip git curl
```

#### Installation

```bash
# Clone repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Install dependencies
pip3 install -r requirements.txt

# Start mining
python3 rustchain_universal_miner.py --wallet vintage-g4
```

**💡 Pro tip**: PowerPC Macs often run best with Debian PowerPC or Ubuntu PowerPC rather than old macOS versions.

---

### Windows (WSL)

RustChain mining on Windows requires **Windows Subsystem for Linux (WSL)**.

#### Prerequisites

**1. Enable WSL**

Open PowerShell as Administrator:

```powershell
wsl --install
```

Restart your computer.

**2. Install Ubuntu**

```powershell
wsl --install -d Ubuntu-22.04
```

**3. Launch Ubuntu**

From Start menu, open "Ubuntu" and complete initial setup.

#### Installation

Inside WSL Ubuntu terminal:

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3 python3-pip python3-venv curl git

# Follow Ubuntu Linux instructions above
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-wallet
```

**⚠️ Note**: WSL may have lower multipliers due to virtualization detection. Native Linux on bare metal is preferred.

---

## Manual Installation

If the automated installer fails, or you want full control:

### Step 1: Clone Repository

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
```

### Step 2: Set Up Python Environment

```bash
# Create isolated virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Upgrade pip
pip install --upgrade pip
```

### Step 3: Install Dependencies

```bash
# If requirements.txt exists:
pip install -r requirements.txt

# If not, install manually:
pip install requests psutil cpuinfo
```

### Step 4: Configure Wallet

Edit `config.json` or pass wallet as argument:

```json
{
  "wallet": "my-wallet-name",
  "node_url": "https://50.28.86.131",
  "auto_restart": true,
  "log_level": "INFO"
}
```

### Step 5: Start Mining

```bash
python3 rustchain_universal_miner.py --wallet my-wallet-name
```

---

## Configuration

### Command-Line Options

```bash
python3 rustchain_universal_miner.py [OPTIONS]

Options:
  --wallet NAME          Set wallet name (required)
  --node URL             Set node URL (default: https://50.28.86.131)
  --log-level LEVEL      Set logging level (DEBUG, INFO, WARNING, ERROR)
  --no-auto-restart      Disable automatic restart on errors
  --benchmark            Run hardware benchmark only
  --version              Show miner version
```

### Environment Variables

```bash
export RUSTCHAIN_WALLET="my-wallet"
export RUSTCHAIN_NODE="https://50.28.86.131"
export RUSTCHAIN_LOG_LEVEL="INFO"

python3 rustchain_universal_miner.py
```

### Config File

Create `~/.rustchain/config.json`:

```json
{
  "wallet": "my-wallet-name",
  "node_url": "https://50.28.86.131",
  "auto_restart": true,
  "log_level": "INFO",
  "epoch_interval": 600,
  "max_retries": 10,
  "retry_delay": 30
}
```

---

## Managing Your Miner

### Checking Status

**Linux (systemd)**:

```bash
# Check if running
systemctl --user status rustchain-miner

# View live logs
journalctl --user -u rustchain-miner -f

# View recent logs
journalctl --user -u rustchain-miner -n 50
```

**macOS (launchd)**:

```bash
# Check if loaded
launchctl list | grep rustchain

# View logs
tail -f ~/.rustchain/miner.log

# View errors
tail -f ~/.rustchain/error.log
```

**Manual (any platform)**:

```bash
# Check if process is running
ps aux | grep rustchain

# View logs
tail -f ~/.rustchain/miner.log
```

### Starting/Stopping

**Linux**:

```bash
systemctl --user start rustchain-miner
systemctl --user stop rustchain-miner
systemctl --user restart rustchain-miner
```

**macOS**:

```bash
launchctl start com.rustchain.miner
launchctl stop com.rustchain.miner
launchctl unload ~/Library/LaunchAgents/com.rustchain.miner.plist
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist
```

**Manual**:

```bash
# Start (in background with screen/tmux)
screen -dmS rustchain python3 rustchain_universal_miner.py --wallet my-wallet

# Stop
pkill -f rustchain_universal_miner

# Restart
pkill -f rustchain_universal_miner && sleep 2 && screen -dmS rustchain python3 rustchain_universal_miner.py --wallet my-wallet
```

### Uninstalling

**Automated uninstaller**:

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

**Manual uninstall**:

```bash
# Stop service
systemctl --user stop rustchain-miner
systemctl --user disable rustchain-miner

# Remove service file
rm ~/.config/systemd/user/rustchain-miner.service

# Remove files
rm -rf ~/Rustchain
rm -rf ~/.rustchain
```

---

## Monitoring & Troubleshooting

### Checking Your Balance

```bash
# Check wallet balance
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET"

# Example response:
# {"miner_id": "my-wallet", "balance": 12.45, "last_payout": "2026-02-12T09:30:00Z"}
```

### List Active Miners

```bash
# See all active miners
curl -sk https://50.28.86.131/api/miners

# Check your miner's status
curl -sk "https://50.28.86.131/api/miners?miner_id=YOUR_WALLET"
```

### Check Node Health

```bash
# Node health check
curl -sk https://50.28.86.131/health

# Current epoch
curl -sk https://50.28.86.131/epoch

# Network stats
curl -sk https://50.28.86.131/api/stats
```

### Common Issues

#### 1. "Connection refused" or "Unable to reach node"

**Cause**: Node is down or firewall blocking

**Solution**:

```bash
# Test connectivity
ping 50.28.86.131
curl -sk https://50.28.86.131/health

# Check firewall (Linux)
sudo ufw status

# Allow HTTPS if blocked
sudo ufw allow 443/tcp
```

#### 2. "Miner not receiving rewards"

**Cause**: Wallet not registered, or mining inactive

**Solution**:

```bash
# Verify wallet is active
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET"

# Check miner logs for errors
journalctl --user -u rustchain-miner -n 100

# Restart miner
systemctl --user restart rustchain-miner
```

#### 3. "Hardware fingerprint failed"

**Cause**: Running in VM/emulator, or hardware detection issue

**Solution**:

- Use real hardware (not virtual machine) for best results
- VMs may have reduced multipliers
- PowerPC emulators (SheepShaver, QEMU) won't pass PoA checks

#### 4. "Python module not found"

**Cause**: Dependencies not installed properly

**Solution**:

```bash
# Activate virtual environment
source ~/Rustchain/venv/bin/activate

# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Or install manually
pip install requests psutil cpuinfo
```

#### 5. "Service won't start"

**Cause**: Incorrect paths, permissions, or config

**Solution**:

```bash
# Check service logs
journalctl --user -u rustchain-miner -xe

# Verify paths in service file
cat ~/.config/systemd/user/rustchain-miner.service

# Test miner manually first
cd ~/Rustchain
source venv/bin/activate
python3 rustchain_universal_miner.py --wallet test-wallet
```

---

## Optimizing Rewards

### 1. Use Vintage Hardware

| Hardware | Multiplier | Why It Matters |
|----------|-----------|----------------|
| PowerPC G4 (1999) | **2.5×** | Best rewards! |
| PowerPC G5 (2003) | **2.0×** | Excellent |
| Core 2 Duo (2006) | **1.3×** | Good |
| Modern CPU | **1.0×** | Base rate |

**💡 Strategy**: Mine on your oldest working computer for maximum RTC earnings.

### 2. Run Multiple Miners

- Each unique hardware device gets 1 vote
- Run miners on different physical machines
- Don't run multiple miners on same hardware (won't increase rewards)

### 3. Maintain Uptime

- Mining rewards are per epoch (10 minutes)
- Missing epochs = missed rewards
- Set up auto-start services for always-on mining

### 4. Check for Updates

```bash
# Update miner code
cd ~/Rustchain
git pull origin main

# Restart miner
systemctl --user restart rustchain-miner
```

### 5. Join the Community

- Discord: [RustChain Community](https://discord.gg/rustchain)
- GitHub: [github.com/Scottcjn/Rustchain](https://github.com/Scottcjn/Rustchain)
- Get help, share tips, track bounties

---

## FAQ

### How much RTC can I earn?

**It depends on**:
- Your hardware age (older = more)
- Number of active miners (more miners = smaller share)
- Uptime (epochs mined / total epochs)

**Example** (PowerPC G4, 2.5× multiplier, 5 active miners):
```
Base pool: 1.5 RTC per epoch
Your share: 1.5 ÷ 5 = 0.3 RTC
With multiplier: 0.3 × 2.5 = 0.75 RTC per epoch
Per day: 0.75 × 144 epochs = 108 RTC/day
Per month: ~3,240 RTC
```

### What if I don't have vintage hardware?

You can still mine! Modern hardware gets 1.0× multiplier (base rate). It's less than vintage, but still earns RTC.

### Can I mine on a Raspberry Pi?

Yes! Raspberry Pi 3/4/5 are supported (ARM64). They get ~1.2-1.3× multiplier depending on model.

### Can I mine on multiple computers?

Absolutely! Each unique hardware device can mine simultaneously. More devices = more RTC.

### Does mining use a lot of power?

No! RustChain uses minimal CPU (~5-10%). Power consumption is low, especially on older hardware.

### What is wRTC?

wRTC is the Solana SPL token version of RTC. You can:
- Bridge RTC → wRTC on BoTTube
- Trade wRTC on Raydium DEX
- Use wRTC to tip creators on BoTTube
- Bridge back wRTC → RTC

**Bridge**: https://bottube.ai/bridge/wrtc  
**Swap**: https://raydium.io/swap/?outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X

### How do I withdraw/transfer RTC?

Check the wallet API documentation for transfer endpoints. You'll need your wallet name and destination wallet.

### Is mining on Windows supported?

Via WSL (Windows Subsystem for Linux) - yes! Native Windows mining is not officially supported yet.

### Can I change my wallet name?

Once you start mining with a wallet name, stick with it. Create a new wallet if needed, but you'll start from zero balance.

### Where can I get help?

- GitHub Issues: https://github.com/Scottcjn/Rustchain/issues
- Discord Community: https://discord.gg/rustchain
- Email: support@rustchain.org

---

## Next Steps

✅ **Miner running?** Check your balance and monitor logs  
✅ **Want to optimize?** Join the community and share your setup  
✅ **Found a bug?** Report it and earn bug bounty RTC  
✅ **Have vintage hardware?** You're earning maximum rewards!

**Happy mining! 🪙⛏️**

---

*Guide version 1.0 - Last updated February 12, 2026*  
*For the latest version, visit: https://github.com/Scottcjn/Rustchain/docs/MINER_SETUP_GUIDE.md*
