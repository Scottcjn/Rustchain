# RustChain Miner Setup Guide

A comprehensive guide for setting up and running a RustChain miner on Windows, macOS, and Linux.

## Table of Contents

- [Overview](#overview)
- [System Requirements](#system-requirements)
- [Platform-Specific Prerequisites](#platform-specific-prerequisites)
- [Installation Guide](#installation-guide)
- [Configuration](#configuration)
- [Hardware Attestation](#hardware-attestation)
- [Testing Your Miner](#testing-your-miner)
- [Management](#management)
- [Troubleshooting](#troubleshooting)
- [Advanced Topics](#advanced-topics)

---

## Overview

RustChain is a Proof-of-Antiquity blockchain that rewards older hardware for being vintage. Instead of competing on computational power, miners are rewarded based on the age and authenticity of their hardware.

### Key Concepts

- **Proof-of-Antiquity (PoA)**: Consensus mechanism that values hardware age
- **Hardware Attestation**: Cryptographic proof that your hardware is genuine and not virtualized
- **Antiquity Multiplier**: Your reward multiplier based on CPU age (ranges from 1.0x to 2.5x)
- **RustChain Token (RTC)**: Native currency, also available as wRTC on Solana

### What You'll Earn

Rewards vary based on:
- Your hardware's age (PowerPC G4/G5 earn more than modern x86)
- Attestation validity (must pass hardware fingerprint checks)
- Network difficulty (divided among active miners)
- Epochs (24-hour reward distribution cycles)

---

## System Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| **OS** | Linux, macOS 12+, Windows 10+ |
| **Python** | 3.6+ (3.8+ recommended) |
| **RAM** | 512 MB minimum, 1GB recommended |
| **Storage** | 50 MB free space |
| **Network** | Stable internet connection (HTTPS/443) |
| **Processor** | Any x86_64, ARM64, PowerPC, or POWER8 |

### Supported Architectures

| Architecture | Supported | Examples |
|-------------|-----------|----------|
| **x86_64** | ✅ | Intel Core i5/i7, AMD Ryzen |
| **ARM64** | ✅ | Raspberry Pi 4+, Apple M1/M2/M3 |
| **PowerPC** | ✅ | Apple G4/G5 Macs, IBM POWER8 |
| **ppc64le** | ✅ | IBM POWER8, POWER9 systems |

### Network Requirements

- Outbound HTTPS (port 443) to node: `https://50.28.86.131`
- No inbound ports required
- Firewall must allow HTTPS connections
- Minimum 100 Kbps upload/download

---

## Platform-Specific Prerequisites

### Linux (Ubuntu, Debian, Fedora, RHEL)

**Install Python and dependencies:**

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip curl

# Fedora/RHEL
sudo dnf install python3 python3-venv python3-pip curl

# Verify Python version
python3 --version  # Should be 3.6+
```

### macOS (12 Monterey+)

**Install Command Line Tools (if not already installed):**

```bash
# This will prompt you to install if needed
git --version

# Or explicitly:
xcode-select --install
```

**Verify Python:**

```bash
python3 --version  # Should be 3.8+
```

Homebrew is optional but recommended:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Windows 10/11

**Install Python:**

1. Download from [python.org](https://www.python.org/downloads/windows/)
2. Run the installer
3. **IMPORTANT**: Check "Add Python to PATH" during installation
4. Verify installation:
   ```bash
   python --version  # Should be 3.8+
   ```

**Install curl (if not available):**

Windows 10+ includes `curl` by default in PowerShell. Verify:
```powershell
curl --version
```

---

## Installation Guide

### Method 1: One-Line Install (Recommended)

The quickest and most reliable way to install RustChain miner:

#### Linux/macOS:
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

#### Windows (PowerShell):
```powershell
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iwr https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh -OutFile install.sh
bash install.sh
```

**The installer will:**
- ✅ Auto-detect your OS and CPU architecture
- ✅ Create an isolated Python virtualenv at `~/.rustchain/`
- ✅ Install required dependencies (requests library)
- ✅ Download the correct miner binary for your hardware
- ✅ Prompt for a wallet name (or auto-generate one)
- ✅ Set up auto-start on system boot (optional)

### Installation Options

**With a specific wallet name:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-miner-wallet
```

**Dry-run (preview without making changes):**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --dry-run
```

**Skip auto-start service setup:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --skip-service
```

### Installation Directory Structure

After successful installation, you'll have:

```
~/.rustchain/
├── venv/                          # Isolated Python environment
│   ├── bin/
│   │   ├── python               # Python interpreter
│   │   └── pip                  # Package manager
│   └── lib/
│       └── python3.x/
│           └── site-packages/   # Dependencies (requests, etc.)
├── rustchain_miner.py           # Main miner script
├── fingerprint_checks.py         # Hardware attestation module
├── start.sh                      # Convenience startup script
└── miner.log                     # Log file (created when running)
```

**Linux/macOS:** `~/.config/systemd/user/` or `~/Library/LaunchAgents/` (service config)
**Windows:** `%APPDATA%\RustChain\` (alternative install path)

---

## Configuration

### Wallet Configuration

Your wallet is automatically created during installation. It's a unique identifier for your miner.

**View your wallet:**
```bash
# On Linux/macOS
cat ~/.rustchain/start.sh | grep wallet

# Check wallet balance
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

**Using a different wallet:**

To switch wallets, reinstall with a new wallet name:
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet new-wallet-name
```

### Hardware Configuration

Most configuration is automatic. If you need to customize:

**Edit miner parameters (advanced):**

```bash
# Linux/macOS: Edit the start script
nano ~/.rustchain/start.sh

# Change wallet or add flags
$VENV_DIR/bin/python rustchain_miner.py --wallet your-wallet [--verbose] [--no-attest]
```

### Service Configuration

#### Linux (systemd)

Service location: `~/.config/systemd/user/rustchain-miner.service`

**View the service:**
```bash
cat ~/.config/systemd/user/rustchain-miner.service
```

**Edit the service:**
```bash
systemctl --user edit rustchain-miner
systemctl --user daemon-reload
```

#### macOS (launchd)

Service location: `~/Library/LaunchAgents/com.rustchain.miner.plist`

**View the plist:**
```bash
cat ~/Library/LaunchAgents/com.rustchain.miner.plist
```

**Edit the plist (use proper XML formatting):**
```bash
nano ~/Library/LaunchAgents/com.rustchain.miner.plist
# Reload after editing:
launchctl unload ~/Library/LaunchAgents/com.rustchain.miner.plist
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist
```

---

## Hardware Attestation

Hardware attestation is how RustChain verifies you're running on genuine hardware (not a virtual machine).

### How Attestation Works

The miner performs a 6-point hardware fingerprint check:

1. **Clock Skew Detection** - Detects hypervisor timing artifacts
2. **Cache Timing Analysis** - Measures CPU cache behavior (unique per processor)
3. **SIMD Identity** - Detects virtualization via SIMD instructions
4. **Thermal Entropy** - Measures thermal sensor noise patterns
5. **Instruction Jitter** - Analyzes CPU instruction timing variability
6. **Behavioral Heuristics** - Detects VM-specific behaviors in CPUID

### Attestation Requirements

- Must pass **all 6 checks** for full rewards
- Attestation is submitted **once per epoch** (24 hours)
- Rewards are **reduced or zero** if attestation fails
- Hardware serial number is bound to your wallet

### Running Attestation

Attestation runs automatically when the miner starts:

```bash
# View attestation results in logs
journalctl --user -u rustchain-miner -f  # Linux
tail -f ~/.rustchain/miner.log            # macOS/Windows

# Look for output like:
# [ATTESTATION] Running 6 hardware fingerprint checks...
# [ATTESTATION] All checks PASSED - eligible for full rewards
```

### Troubleshooting Attestation Failures

**If you see "VM_DETECTED":**
- Ensure you're running on real hardware, not a VM
- Update your BIOS/firmware
- Disable any hypervisor features
- Some corporate security software can interfere

**If you see "INVALID_SIGNATURE":**
- Wallet or signature is corrupted
- Try reinstalling the miner

**If specific checks fail:**
- This may be normal for vintage hardware
- You'll still earn reduced rewards
- Contact the community for assistance

---

## Testing Your Miner

### Quick Test: Check Node Connectivity

```bash
# Test node health
curl -sk https://50.28.86.131/health

# Expected response:
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 18728,
  "db_rw": true,
  "tip_age_slots": 0,
  "backup_age_hours": 6.75
}
```

### Check Network Epoch

```bash
curl -sk https://50.28.86.131/epoch

# Expected response:
{
  "epoch": 62,
  "slot": 9010,
  "blocks_per_epoch": 144,
  "epoch_pot": 1.5,
  "enrolled_miners": 2
}
```

### Check Your Wallet Balance

```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"

# Expected response:
{
  "miner_id": "your-wallet",
  "amount_rtc": 12.456,
  "amount_i64": 12456000
}
```

### Manual Miner Test

Run the miner manually (not via service) to see detailed output:

```bash
# Navigate to install directory
cd ~/.rustchain

# Run with Python directly
./venv/bin/python rustchain_miner.py --wallet YOUR_WALLET_NAME
```

Watch for:
- ✅ `[ATTESTATION] All checks PASSED`
- ✅ `[NODE] Connected to https://50.28.86.131`
- ✅ `[ENROLLED] Successfully enrolled for epoch X`

The miner should show status updates every 60-120 seconds.

---

## Management

### Starting/Stopping the Miner

#### Linux (systemd)

```bash
# Check status
systemctl --user status rustchain-miner

# Start
systemctl --user start rustchain-miner

# Stop
systemctl --user stop rustchain-miner

# Restart
systemctl --user restart rustchain-miner

# View logs
journalctl --user -u rustchain-miner -f  # Follow (streaming)
journalctl --user -u rustchain-miner -n 100  # Last 100 lines
```

#### macOS (launchd)

```bash
# Check status
launchctl list | grep rustchain

# Start
launchctl start com.rustchain.miner

# Stop
launchctl stop com.rustchain.miner

# View logs
tail -f ~/.rustchain/miner.log
log show --predicate 'eventMessage contains "rustchain"' --last 1h  # System logs
```

#### Windows (Manual)

```powershell
# Navigate to install directory
cd $env:USERPROFILE\.rustchain

# Run manually
.\venv\Scripts\python.exe rustchain_miner.py --wallet YOUR_WALLET_NAME
```

### Auto-Start on Boot

#### Enable Auto-Start

**Linux:**
```bash
systemctl --user enable rustchain-miner
systemctl --user start rustchain-miner
```

**macOS:**
```bash
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist
```

#### Disable Auto-Start

**Linux:**
```bash
systemctl --user disable rustchain-miner
systemctl --user stop rustchain-miner
```

**macOS:**
```bash
launchctl unload ~/Library/LaunchAgents/com.rustchain.miner.plist
```

### Monitoring Miner Health

**Check process is running:**
```bash
# Linux/macOS
ps aux | grep rustchain_miner

# Windows PowerShell
Get-Process python | Where-Object {$_.ProcessName -like "*rustchain*"}
```

**Monitor resource usage:**
```bash
# Linux
watch -n 5 'ps aux | grep rustchain'

# macOS
top -p $(pgrep -f rustchain_miner.py)

# Windows PowerShell
Get-Process python | Select-Object Name, Handles, WorkingSet
```

**Check recent logs:**
```bash
# Show last hour of logs
journalctl --user -u rustchain-miner --since "1 hour ago"

# Show only errors
journalctl --user -u rustchain-miner -p err
```

---

## Troubleshooting

### Installation Issues

#### "Python 3 not found"

**Linux:**
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip
```

**macOS:**
```bash
brew install python3
# Or download from https://python.org/downloads
```

**Windows:**
Download and reinstall from [python.org](https://www.python.org/downloads/windows/) with "Add Python to PATH" checked.

#### "Permission denied when creating symlink"

This is normal and not a problem. The installer continues and you can still run the miner with:
```bash
~/.rustchain/start.sh
```

#### "Virtual environment creation failed"

**Ubuntu/Debian:**
```bash
sudo apt-get install python3-venv
```

**Fedora/RHEL:**
```bash
sudo dnf install python3-virtualenv
```

**macOS (if pip install doesn't work):**
```bash
pip3 install --user virtualenv
python3 -m virtualenv ~/.rustchain/venv
```

### Service Issues

#### Service fails to start (Linux)

**Check the error:**
```bash
journalctl --user -u rustchain-miner -n 50
```

**Common solutions:**

1. **Network not available at boot**: Service retries automatically, this is normal
2. **Python path incorrect**: Reinstall the miner
3. **Wallet name with special characters**: Use alphanumeric names only
4. **Permission issues**: Run `systemctl --user daemon-reload`

```bash
systemctl --user daemon-reload
systemctl --user restart rustchain-miner
```

#### Service not loading (macOS)

**Check if loaded:**
```bash
launchctl list | grep rustchain
```

**Reload:**
```bash
launchctl unload ~/Library/LaunchAgents/com.rustchain.miner.plist
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist
```

**Check the plist is valid XML:**
```bash
plutil -lint ~/Library/LaunchAgents/com.rustchain.miner.plist
```

### Runtime Issues

#### "Could not connect to node"

**Verify node is online:**
```bash
curl -sk https://50.28.86.131/health
```

**Check firewall:**
```bash
# Test connectivity
curl -v https://50.28.86.131/health

# Ensure HTTPS port 443 is open
# Check your firewall rules
```

**Common causes:**
- Network connection dropped
- ISP blocking port 443 (rare)
- Corporate firewall/proxy
- Node temporarily offline

#### "Miner not earning rewards"

**Verify miner is running:**
```bash
# Linux
systemctl --user status rustchain-miner

# macOS
launchctl list | grep rustchain

# Check logs for errors
journalctl --user -u rustchain-miner -f
```

**Check attestation status:**

Look in the logs for:
- `[ATTESTATION] All checks PASSED` - Good, eligible for full rewards
- `[ATTESTATION] FAILED checks` - Missing some rewards
- `[ATTESTATION] Error` - Investigation needed

**Verify you're enrolled:**
```bash
curl -sk https://50.28.86.131/api/miners | grep YOUR_WALLET_NAME
```

**Check wallet balance:**
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

If balance is 0:
- Miner may not be enrolled yet (wait 24-48 hours for first epoch)
- Attestation may be failing (check logs)
- Network may have few active miners (rewards divided among fewer participants)

#### "Hardware attestation failed"

**VM_DETECTED:**
- You're running in a virtual machine
- RustChain requires authentic hardware
- Solution: Run on real hardware

**INVALID_SIGNATURE:**
- Cryptographic validation failed
- Try reinstalling the miner

**Individual check failures:**
- Normal for some vintage hardware
- You'll still earn reduced rewards
- Check miner logs for details

#### Excessive CPU usage

**Normal behavior:**
- Miner uses ~20-30% CPU on 1 core
- This is expected for PoA validation

**If higher:**
```bash
# Check what's running
ps aux | grep rustchain

# Reduce process priority (Linux)
renice +10 -p $(pgrep -f rustchain_miner.py)

# Reduce process priority (macOS)
renice +10 -p $(pgrep -f rustchain_miner.py)
```

#### High memory usage

**Check memory:**
```bash
# Linux
ps aux | grep rustchain | grep -v grep

# macOS
ps aux | grep rustchain | grep -v grep
```

**Normal usage:** < 100 MB

**If higher:** There may be a memory leak. Restart the miner:
```bash
systemctl --user restart rustchain-miner
```

#### Miner crashes and restarts frequently

**Check logs for error patterns:**
```bash
journalctl --user -u rustchain-miner | tail -100
```

**Common causes:**
1. **Out of memory** - Check with `free -m` or `vm_stat`
2. **Disk full** - Check with `df -h`
3. **Network flaky** - Internet connection issues
4. **Hardware problems** - Overheating, failing disk

---

## Advanced Topics

### Running Multiple Miners

To mine on multiple machines:

1. **Install on each machine separately:**
   ```bash
   curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet miner1
   ```

2. **Use different wallet names:**
   Each machine gets a unique wallet for independent tracking

3. **Monitor multiple miners:**
   ```bash
   # Create a script to check all wallets
   for wallet in miner1 miner2 miner3; do
     echo "=== $wallet ==="
     curl -sk "https://50.28.86.131/wallet/balance?miner_id=$wallet"
   done
   ```

### Updating the Miner

**Update to latest version:**

```bash
# Uninstall old version
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall

# Install new version
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet YOUR_WALLET_NAME
```

Your wallet name is preserved, so your rewards continue with the same identity.

### Custom Installation

**For advanced users who want manual control:**

```bash
# 1. Create directory
mkdir -p ~/.rustchain && cd ~/.rustchain

# 2. Create virtualenv
python3 -m venv venv

# 3. Install dependencies
venv/bin/pip install requests

# 4. Download miner (choose appropriate for your platform)
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/linux/rustchain_linux_miner.py -o rustchain_miner.py

# 5. Download fingerprint checks
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/node/fingerprint_checks.py -o fingerprint_checks.py

# 6. Make executable
chmod +x rustchain_miner.py

# 7. Run
venv/bin/python rustchain_miner.py --wallet my-wallet
```

### Hardware Binding

The miner uses hardware serial numbers to bind your rewards to your specific hardware:

```bash
# Check your hardware serial (Linux)
cat /sys/class/dmi/id/product_serial

# Check your hardware serial (macOS)
system_profiler SPHardwareDataType | grep Serial

# Check your hardware serial (Windows PowerShell)
Get-WmiObject Win32_BIOS | Select-Object SerialNumber
```

This serial is cryptographically included in your attestation, making it harder to spoof rewards.

### Uninstallation

**Complete removal:**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

**Manual removal:**

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

## Performance and Optimization

### Optimal Configuration for Different Hardware

**Modern x86_64 (Intel/AMD):**
- Highest reward diversity
- Works best with 4+ cores
- Expects modern CPU instruction sets

**Apple Silicon (M1/M2/M3):**
- Excellent performance
- Low power consumption
- Optimal for mining on laptops

**PowerPC Vintage (G4/G5):**
- Highest antiquity multipliers (2.5x)
- Limited by CPU speed
- May take longer to accumulate rewards

**Raspberry Pi (ARM64):**
- Good for always-on mining
- Low power consumption
- Slower than desktop hardware but still profitable

### Resource Management

**Limit CPU usage (if needed):**
```bash
# Linux: Limit to 1 core
taskset -c 1 ~/.rustchain/venv/bin/python ~/.rustchain/rustchain_miner.py --wallet YOUR_WALLET

# macOS: Lower priority
renice +5 -p $(pgrep -f rustchain_miner)
```

**Run on schedule (e.g., only during off-peak hours):**
```bash
# Linux: Use cron
crontab -e
# Add: 0 22 * * * systemctl --user start rustchain-miner
# Add: 0 9 * * * systemctl --user stop rustchain-miner
```

---

## Security Notes

### SSL Certificate Warning

The RustChain node may use a self-signed SSL certificate. This is expected.

- The `-k` flag in curl bypasses certificate verification
- This is safe for RustChain's public node
- In a production environment, you'd verify the certificate manually

### Wallet Security

Your wallet is identified by a name, not a private key. Keys are stored securely:

- Rewards are sent to your wallet
- To transfer rewards, you need to sign transactions
- Keys are derived from your hardware serial number
- Never expose your wallet name to untrusted sources

### Hardware Security

The miner:
- Runs as your regular user (not root)
- Uses an isolated Python virtualenv
- Doesn't require sudo for normal operation
- Stores all data in your home directory
- Doesn't make outbound connections except to the RustChain node

---

## Support and Community

### Getting Help

- **GitHub Issues**: [Scottcjn/Rustchain/issues](https://github.com/Scottcjn/Rustchain/issues)
- **Explorer**: [https://rustchain.org/explorer](https://rustchain.org/explorer)
- **Bounties**: [RustChain Bounties](https://github.com/Scottcjn/rustchain-bounties)

### Reporting Issues

When reporting a problem, include:
1. Your OS and architecture (`uname -a`)
2. Python version (`python3 --version`)
3. Last 50 lines of miner log
4. Steps to reproduce

### Contributing Improvements

Found a bug or have a feature request?

1. Fork [Scottcjn/Rustchain](https://github.com/Scottcjn/Rustchain)
2. Create a branch: `git checkout -b fix/issue-name`
3. Make changes and test
4. Submit a pull request

---

## Appendix: Command Reference

### Quick Command Reference

| Task | Command |
|------|---------|
| Check node health | `curl -sk https://50.28.86.131/health` |
| Check wallet balance | `curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET"` |
| View active miners | `curl -sk https://50.28.86.131/api/miners` |
| Check current epoch | `curl -sk https://50.28.86.131/epoch` |
| Start miner (Linux) | `systemctl --user start rustchain-miner` |
| Stop miner (Linux) | `systemctl --user stop rustchain-miner` |
| View logs (Linux) | `journalctl --user -u rustchain-miner -f` |
| Start miner (macOS) | `launchctl start com.rustchain.miner` |
| Stop miner (macOS) | `launchctl stop com.rustchain.miner` |
| View logs (macOS) | `tail -f ~/.rustchain/miner.log` |
| Run manually | `~/.rustchain/start.sh` |
| Uninstall | `curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh \| bash -s -- --uninstall` |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Feb 2026 | Initial comprehensive guide |

---

**Last Updated:** February 2026  
**RustChain Version:** 2.2.1-rip200  
**License:** MIT
