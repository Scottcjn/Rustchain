# RustChain Miner Setup Guide

Complete step-by-step guide for setting up RustChain miners on all supported platforms.

---

## Table of Contents

- [Quick Start](#quick-start)
- [System Requirements](#system-requirements)
- [Installation Methods](#installation-methods)
  - [One-Line Installer (Recommended)](#one-line-installer-recommended)
  - [Manual Installation](#manual-installation)
- [Platform-Specific Setup](#platform-specific-setup)
  - [Linux (Ubuntu/Debian/Fedora)](#linux-ubuntudebianfedora)
  - [macOS (Intel/Apple Silicon)](#macos-intelapple-silicon)
  - [PowerPC Macs (G3/G4/G5)](#powerpc-macs-g3g4g5)
  - [Windows](#windows)
  - [IBM POWER8](#ibm-power8)
- [Configuration](#configuration)
- [Running the Miner](#running-the-miner)
- [Auto-Start on Boot](#auto-start-on-boot)
- [Monitoring & Troubleshooting](#monitoring--troubleshooting)
- [Upgrading](#upgrading)
- [Uninstallation](#uninstallation)

---

## Quick Start

**For most users, this is all you need:**

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

The installer will:
1. ✅ Auto-detect your platform (OS and CPU architecture)
2. ✅ Create an isolated Python virtualenv
3. ✅ Install dependencies
4. ✅ Download the correct miner for your hardware
5. ✅ Generate or prompt for wallet name
6. ✅ Optionally set up auto-start on boot
7. ✅ Display balance check commands

**Installation time**: 2-5 minutes

---

## System Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| **CPU** | Any x86, x86_64, ARM, or PowerPC processor |
| **RAM** | 128 MB (yes, really!) |
| **Disk Space** | 50 MB |
| **OS** | Linux 2.6+, macOS 10.4+, Windows 7+ |
| **Python** | Python 3.6+ (or Python 2.5+ for vintage PowerPC) |
| **Network** | Internet connection (HTTPS access to 50.28.86.131) |

### Supported Platforms

#### Linux
- ✅ Ubuntu 20.04, 22.04, 24.04
- ✅ Debian 11, 12
- ✅ Fedora 38, 39, 40
- ✅ RHEL 8, 9
- ✅ Other systemd-based distributions

**Architectures**: x86_64, ppc64le, ppc, i686

#### macOS
- ✅ macOS 12 (Monterey) and later
- ✅ macOS 11 (Big Sur)
- ✅ macOS 10.4+ (Tiger) for PowerPC

**Architectures**: arm64 (Apple Silicon), x86_64 (Intel), powerpc (G3/G4/G5)

#### Windows
- ✅ Windows 10, 11
- ✅ Windows 7, 8.1 (with Python 3.6+)

**Architectures**: x86_64, x86

#### Special Hardware
- ✅ IBM POWER8 systems (ppc64le)
- ✅ Raspberry Pi (ARM)
- ✅ Vintage x86 CPUs (Pentium 4, Core 2 Duo, etc.)

---

## Installation Methods

### One-Line Installer (Recommended)

The automated installer handles everything for you.

#### Default Installation
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

#### Installation with Specific Wallet
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner-wallet
```

#### What the Installer Does

1. **Platform Detection**
   ```
   Detecting platform...
   OS: Linux
   Architecture: x86_64
   Python: 3.10.12
   ```

2. **Virtualenv Creation**
   ```
   Creating Python virtualenv at ~/.rustchain/venv...
   Installing dependencies (requests)...
   ```

3. **Miner Download**
   ```
   Downloading rustchain_linux_miner.py...
   Downloading fingerprint_checks.py...
   ```

4. **Wallet Setup**
   ```
   Enter wallet name (or press Enter to auto-generate): powerbook_g4
   Wallet: powerbook_g4_RTC
   ```

5. **Auto-Start Configuration**
   ```
   Set up auto-start on boot? (y/n): y
   Creating systemd service...
   Service enabled: rustchain-miner.service
   ```

6. **Installation Complete**
   ```
   ✅ RustChain miner installed successfully!
   
   Installation directory: ~/.rustchain/
   Wallet: powerbook_g4_RTC
   
   Check balance:
   curl -sk "https://50.28.86.131/wallet/balance?miner_id=powerbook_g4_RTC"
   
   View logs:
   journalctl --user -u rustchain-miner -f
   ```

---

### Manual Installation

For advanced users or unsupported platforms.

#### Step 1: Install Python

**Linux (Debian/Ubuntu)**:
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

**Linux (Fedora/RHEL)**:
```bash
sudo dnf install python3 python3-pip
```

**macOS**:
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python3
```

**Windows**:
Download and install Python from [python.org](https://www.python.org/downloads/)

#### Step 2: Clone Repository

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
```

#### Step 3: Create Virtualenv

```bash
python3 -m venv ~/.rustchain/venv
source ~/.rustchain/venv/bin/activate  # Linux/macOS
# OR
~/.rustchain/venv/Scripts/activate  # Windows
```

#### Step 4: Install Dependencies

```bash
pip install requests urllib3
```

#### Step 5: Copy Miner Files

**Linux**:
```bash
cp miners/linux/rustchain_linux_miner.py ~/.rustchain/
cp miners/linux/fingerprint_checks.py ~/.rustchain/
```

**macOS**:
```bash
cp miners/macos/rustchain_mac_miner_v2.4.py ~/.rustchain/
cp miners/linux/fingerprint_checks.py ~/.rustchain/
```

**Windows**:
```bash
copy miners\windows\rustchain_windows_miner.py %USERPROFILE%\.rustchain\
```

#### Step 6: Run Miner

```bash
cd ~/.rustchain
source venv/bin/activate
python rustchain_linux_miner.py --wallet my-wallet-name
```

---

## Platform-Specific Setup

### Linux (Ubuntu/Debian/Fedora)

#### Prerequisites
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv curl

# Fedora/RHEL
sudo dnf install python3 python3-pip curl
```

#### Installation
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

#### Service Management (systemd)
```bash
# Check status
systemctl --user status rustchain-miner

# Start miner
systemctl --user start rustchain-miner

# Stop miner
systemctl --user stop rustchain-miner

# Restart miner
systemctl --user restart rustchain-miner

# Enable auto-start on boot
systemctl --user enable rustchain-miner

# Disable auto-start
systemctl --user disable rustchain-miner

# View logs
journalctl --user -u rustchain-miner -f
```

#### Manual Run
```bash
cd ~/.rustchain
source venv/bin/activate
python rustchain_linux_miner.py --wallet my-wallet
```

---

### macOS (Intel/Apple Silicon)

#### Prerequisites
```bash
# Install Xcode Command Line Tools (if not already installed)
xcode-select --install

# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python3
```

#### Installation
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

#### Service Management (launchd)
```bash
# Check status
launchctl list | grep rustchain

# Start miner
launchctl start com.rustchain.miner

# Stop miner
launchctl stop com.rustchain.miner

# Enable auto-start on boot
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist

# Disable auto-start
launchctl unload ~/Library/LaunchAgents/com.rustchain.miner.plist

# View logs
tail -f ~/.rustchain/miner.log
```

#### Manual Run
```bash
cd ~/.rustchain
source venv/bin/activate
python rustchain_mac_miner_v2.4.py --wallet my-wallet
```

---

### PowerPC Macs (G3/G4/G5)

**Special considerations for vintage PowerPC hardware:**

#### Prerequisites
- macOS 10.4 (Tiger) or later
- Python 2.5+ (usually pre-installed)
- Internet connection

#### Installation

**Option 1: Automated (if curl available)**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

**Option 2: Manual**
```bash
# Download miner
mkdir -p ~/.rustchain
cd ~/.rustchain

# Use wget if curl not available
wget https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/ppc/rustchain_powerpc_g4_miner_v2.2.2.py

# Run miner
python rustchain_powerpc_g4_miner_v2.2.2.py --wallet powerbook_g4
```

#### Why PowerPC Gets Higher Rewards

PowerPC G4/G5 systems receive **2.0x - 2.5x multipliers** because:
- Hardware is 20+ years old (Vintage tier)
- Difficult to emulate accurately
- Preserves computing history
- Limited supply of working units

**Example earnings**:
- PowerPC G4 (2005): **0.30 RTC/epoch** (2.5x multiplier)
- Modern x86_64: **0.12 RTC/epoch** (1.0x multiplier)

---

### Windows

#### Prerequisites
1. Download Python from [python.org](https://www.python.org/downloads/)
2. During installation, check "Add Python to PATH"
3. Open Command Prompt or PowerShell

#### Installation

**Option 1: PowerShell**
```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh" -OutFile "install-miner.sh"
bash install-miner.sh
```

**Option 2: Manual**
```cmd
# Create directory
mkdir %USERPROFILE%\.rustchain
cd %USERPROFILE%\.rustchain

# Create virtualenv
python -m venv venv

# Activate virtualenv
venv\Scripts\activate

# Install dependencies
pip install requests urllib3

# Download miner
curl -o rustchain_windows_miner.py https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/windows/rustchain_windows_miner.py

# Run miner
python rustchain_windows_miner.py --wallet my-wallet
```

#### Auto-Start on Boot (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Name: "RustChain Miner"
4. Trigger: "When I log on"
5. Action: "Start a program"
6. Program: `C:\Users\YourName\.rustchain\venv\Scripts\python.exe`
7. Arguments: `C:\Users\YourName\.rustchain\rustchain_windows_miner.py --wallet my-wallet`
8. Finish

---

### IBM POWER8

#### Prerequisites
```bash
# RHEL/CentOS
sudo yum install python3 python3-pip

# Ubuntu (ppc64le)
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

#### Installation
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

#### Manual Run
```bash
cd ~/.rustchain
source venv/bin/activate
python rustchain_power8_miner.py --wallet power8-server
```

**POWER8 Multiplier**: 1.5x (released 2014, Classic tier)

---

## Configuration

### Wallet Name

Your wallet name is your identity on the network. Choose wisely!

**Format**: `<name>_RTC` (suffix added automatically)

**Examples**:
- `powerbook_g4_RTC`
- `ryzen_5_8645hs_RTC`
- `pentium4_northwood_RTC`

**Best Practices**:
- Include hardware model for easy identification
- Use lowercase and underscores
- Avoid special characters
- Keep it under 50 characters

### Node URL

Default: `https://50.28.86.131`

To use a different node, set environment variable:
```bash
export RUSTCHAIN_NODE="https://your-node-url"
```

### Block Time

Default: 600 seconds (10 minutes)

Miners automatically sync with node's block time.

---

## Running the Miner

### First Run

```bash
cd ~/.rustchain
source venv/bin/activate  # Linux/macOS
python rustchain_linux_miner.py --wallet my-wallet
```

**Expected output**:
```
======================================================================
RustChain Local Miner - HP Victus Ryzen 5 8645HS
RIP-PoA Hardware Fingerprint + Serial Binding v2.0
======================================================================
Node: https://50.28.86.131
Wallet: ryzen_5_8645hs_RTC
Serial: 1234567890ABCDEF
======================================================================

[FINGERPRINT] Running 6 hardware fingerprint checks...
[✓] Clock Skew: drift_ppm=12.5, jitter_ns=847
[✓] Cache Timing: L1=4ns, L2=12ns, L3=42ns
[✓] SIMD Identity: SSE4.2, pipeline_bias=0.68
[✓] Thermal Entropy: idle=38.2°C, load=67.8°C, variance=4.2
[✓] Instruction Jitter: mean=2.3ns, stddev=0.8ns
[✓] Behavioral Heuristics: no_hypervisor=true

[FINGERPRINT] ✅ All 6 checks passed!

[ATTEST] Submitting attestation to node...
[ATTEST] ✅ Enrolled in epoch 61 with multiplier 1.0x

[MINING] Waiting for next epoch settlement...
[MINING] Next settlement in 3600 seconds (1.0 hours)
```

### Command-Line Options

```bash
python rustchain_linux_miner.py [OPTIONS]
```

**Options**:
- `--wallet <name>` - Wallet name (required)
- `--node <url>` - Node URL (default: https://50.28.86.131)
- `--verbose` - Enable verbose logging
- `--no-fingerprint` - Skip fingerprint checks (not recommended)
- `--daemon` - Run in background mode

**Examples**:
```bash
# Basic usage
python rustchain_linux_miner.py --wallet my-wallet

# Custom node
python rustchain_linux_miner.py --wallet my-wallet --node https://custom-node.com

# Verbose logging
python rustchain_linux_miner.py --wallet my-wallet --verbose

# Background mode
python rustchain_linux_miner.py --wallet my-wallet --daemon
```

---

## Auto-Start on Boot

### Linux (systemd)

**Service file location**: `~/.config/systemd/user/rustchain-miner.service`

**Enable auto-start**:
```bash
systemctl --user enable rustchain-miner
systemctl --user start rustchain-miner
```

**Disable auto-start**:
```bash
systemctl --user disable rustchain-miner
systemctl --user stop rustchain-miner
```

**View logs**:
```bash
journalctl --user -u rustchain-miner -f
```

### macOS (launchd)

**Plist file location**: `~/Library/LaunchAgents/com.rustchain.miner.plist`

**Enable auto-start**:
```bash
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist
```

**Disable auto-start**:
```bash
launchctl unload ~/Library/LaunchAgents/com.rustchain.miner.plist
```

**View logs**:
```bash
tail -f ~/.rustchain/miner.log
```

### Windows (Task Scheduler)

See [Windows section](#windows) above for Task Scheduler setup.

---

## Monitoring & Troubleshooting

### Check Balance

```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**Example**:
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=powerbook_g4_RTC"
```

**Response**:
```json
{
  "miner_id": "powerbook_g4_RTC",
  "balance_rtc": 12.456789,
  "balance_urtc": 12456789,
  "last_updated": "2026-02-09T14:23:45Z"
}
```

### Check Miner Status

```bash
curl -sk "https://50.28.86.131/api/miner/YOUR_WALLET_NAME"
```

### View Logs

**Linux (systemd)**:
```bash
journalctl --user -u rustchain-miner -f
```

**macOS (launchd)**:
```bash
tail -f ~/.rustchain/miner.log
```

**Manual run**:
Logs print to console

### Common Issues

#### Issue: "VM_DETECTED" Error

**Cause**: Hardware fingerprint indicates virtual machine or emulator

**Solution**:
- Run on real hardware (not VM)
- VMs receive 0.0000000025x multiplier (essentially zero rewards)
- This is intentional to prevent cheating

#### Issue: "HARDWARE_BOUND" Error

**Cause**: Hardware serial already bound to different wallet

**Solution**:
- Use the original wallet name
- Or contact support to unbind hardware (requires proof of ownership)

#### Issue: "Connection refused" or "SSL error"

**Cause**: Cannot connect to node

**Solution**:
```bash
# Test node connectivity
curl -sk https://50.28.86.131/health

# Check firewall settings
# Ensure port 443 (HTTPS) is not blocked
```

#### Issue: Fingerprint checks failing

**Cause**: Hardware not supported or driver issues

**Solution**:
```bash
# Run with verbose logging
python rustchain_linux_miner.py --wallet my-wallet --verbose

# Check which specific check is failing
# Contact support with log output
```

#### Issue: Low or zero rewards

**Possible causes**:
1. **Modern hardware**: Recent CPUs get lower multipliers (1.0x or less)
2. **VM detection**: VMs get near-zero rewards
3. **Not enrolled**: Check if attestation succeeded
4. **Epoch not settled**: Rewards distributed at epoch end (~24 hours)

**Check multiplier**:
```bash
curl -sk "https://50.28.86.131/api/miner/YOUR_WALLET_NAME" | grep multiplier
```

---

## Upgrading

### Automatic Upgrade

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

The installer detects existing installation and upgrades in place.

### Manual Upgrade

```bash
cd ~/.rustchain
source venv/bin/activate

# Backup current miner
cp rustchain_linux_miner.py rustchain_linux_miner.py.backup

# Download latest version
curl -o rustchain_linux_miner.py https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/linux/rustchain_linux_miner.py

# Restart miner
systemctl --user restart rustchain-miner  # Linux
# OR
launchctl stop com.rustchain.miner && launchctl start com.rustchain.miner  # macOS
```

---

## Uninstallation

### Automated Uninstall

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

### Manual Uninstall

**Linux**:
```bash
# Stop and disable service
systemctl --user stop rustchain-miner
systemctl --user disable rustchain-miner

# Remove service file
rm ~/.config/systemd/user/rustchain-miner.service

# Remove installation directory
rm -rf ~/.rustchain
```

**macOS**:
```bash
# Stop and unload service
launchctl unload ~/Library/LaunchAgents/com.rustchain.miner.plist

# Remove plist file
rm ~/Library/LaunchAgents/com.rustchain.miner.plist

# Remove installation directory
rm -rf ~/.rustchain
```

**Windows**:
```cmd
# Remove Task Scheduler task (if created)
# Open Task Scheduler and delete "RustChain Miner" task

# Remove installation directory
rmdir /s %USERPROFILE%\.rustchain
```

---

## Next Steps

- **Check your balance**: `curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET"`
- **View all miners**: `curl -sk https://50.28.86.131/api/miners`
- **Read API docs**: `docs/API_REFERENCE.md`
- **Set up wallet GUI**: `docs/WALLET_USER_GUIDE.md`
- **Join community**: [GitHub Discussions](https://github.com/Scottcjn/Rustchain/discussions)

---

**Last Updated**: February 9, 2026  
**Guide Version**: 1.0
