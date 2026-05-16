# RustChain Developer Tutorial: Build on the Proof-of-Antiquity Blockchain

> **A comprehensive guide for developers** — From zero to mining RTC tokens on vintage hardware.

**Last updated:** March 2026  
**Network:** Mainnet (`https://rustchain.org`)  
**Token:** RTC (native), wRTC (Solana wrapped)

---

## Table of Contents

1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Quick Start (5 Minutes)](#quick-start-5-minutes)
4. [Understanding Proof-of-Antiquity](#understanding-proof-of-antiquity)
5. [Setup Deep Dive](#setup-deep-dive)
6. [Your First Mining Session](#your-first-mining-session)
7. [Making Transactions](#making-transactions)
8. [Practical Examples](#practical-examples)
9. [Troubleshooting](#troubleshooting)
10. [Advanced Topics](#advanced-topics)
11. [Next Steps](#next-steps)

---

## Introduction

**RustChain** is the first blockchain that rewards vintage hardware for being old, not fast. Unlike traditional proof-of-work chains that favor the latest GPUs, RustChain's **Proof-of-Antiquity (PoA)** consensus gives higher mining multipliers to older CPUs.

### Why RustChain?

| Feature | Traditional PoW | RustChain PoA |
|---------|-----------------|---------------|
| Hardware bias | Newest = best | Oldest = best |
| Energy efficiency | High consumption | Minimal (vintage CPUs sip power) |
| Accessibility | GPU arms race | Any working vintage machine |
| Environmental impact | High | Low (reuses existing hardware) |

### What You'll Build

By the end of this tutorial, you will:

- ✅ Have a running RustChain miner
- ✅ Understand the 6 hardware fingerprint checks
- ✅ Earn RTC tokens from vintage hardware
- ✅ Query the blockchain API
- ✅ Bridge RTC ↔ wRTC on Solana

### Who This Is For

- **Vintage hardware enthusiasts** with PowerPC G3/G4/G5, old x86, or SPARC machines
- **Blockchain developers** exploring alternative consensus mechanisms
- **Hobbyists** who want to earn crypto from hardware collecting dust
- **Researchers** studying hardware fingerprinting and attestation

---

## Prerequisites

### Hardware Requirements

Your hardware determines your mining multiplier. RustChain rewards older CPUs:

| CPU Era | Example Models | Base Multiplier |
|---------|---------------|-----------------|
| PowerPC G3 | Macintosh G3, PowerBook G3 | ×4.0 |
| PowerPC G4 | PowerMac G4, iBook G4 | ×3.5 |
| PowerPC G5 | PowerMac G5 (970FX) | ×3.0 |
| Early x86-64 | Core 2 Duo, Pentium 4 | ×2.0 |
| Modern x86-64 | Ryzen, Intel 10th+ gen | ×1.0 |

> 💡 **Tip:** Check your CPU's eligibility before proceeding. See [`CPU_ANTIQUITY_SYSTEM.md`](../CPU_ANTIQUITY_SYSTEM.md) for the complete multiplier table.

### Software Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.6+ | 3.9+ |
| curl | Any version | Latest |
| Disk space | 50 MB | 100 MB |
| RAM | 256 MB | 512 MB |
| OS | Linux/macOS | Ubuntu 22.04+, macOS 12+ |

### Network Requirements

- Stable internet connection
- Outbound HTTPS (port 443) to `rustchain.org`
- No special port forwarding needed (miner initiates connections)

### Verify Your Environment

```bash
# Check Python version
python3 --version
# Expected: Python 3.6.0 or higher

# Check curl availability
curl --version
# Expected: curl X.Y.Z with SSL support

# Test network connectivity to RustChain node
curl -sk https://rustchain.org/health
# Expected: {"status": "ok", ...}
```

---

## Quick Start (5 Minutes)

For developers who want to get mining immediately, here's the fastest path:

### Step 1: Run the Installer

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

The installer will:
1. Create an isolated Python virtualenv at `~/.rustchain/venv`
2. Install dependencies (`requests`)
3. Download the appropriate miner binary for your architecture
4. Prompt for a wallet name (or auto-generate one)
5. Optionally configure auto-start on boot

### Step 2: Start Mining

```bash
# Navigate to the installation directory
cd ~/.rustchain

# Start the miner
./start.sh
```

### Step 3: Verify It's Working

In a new terminal:

```bash
# Check miner logs
tail -f ~/.rustchain/miner.log

# Verify your miner is visible on the network
curl -sk https://rustchain.org/api/miners | jq '.[] | select(.miner_id contains "YOUR_WALLET_NAME")'

# Check your balance (after a few minutes of mining)
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME" | jq .
```

### Expected Output

```json
{
  "miner_id": "YOUR_WALLET_NAME",
  "balance": 12.5,
  "pending_rewards": 0.75,
  "last_heartbeat": "2026-03-13T10:30:00Z",
  "cpu_multiplier": 3.5
}
```

> 🎉 **Congratulations!** You're now mining RustChain. Continue reading for a deeper understanding.

---

## Understanding Proof-of-Antiquity

### The Core Concept

Proof-of-Antiquity flips traditional mining economics:

```
Traditional PoW:  Reward ∝ Hash Rate
RustChain PoA:    Reward ∝ Hardware Age × Attestation Score
```

### The 6 Hardware Fingerprint Checks

RustChain prevents VMs and emulators from earning rewards through 6 independent checks:

| # | Check | What It Tests | VM Evasion Difficulty |
|---|-------|---------------|----------------------|
| 1 | **CPUID Leaf Analysis** | Raw CPUID instruction responses | High (requires CPU passthrough) |
| 2 | **Cache Topology** | L1/L2/L3 cache structure | Very High (timing-based) |
| 3 | **Instruction Timing** | Cycle counts for specific ops | Extreme (nanosecond precision) |
| 4 | **Memory Latency** | RAM access patterns | High (hardware-dependent) |
| 5 | **Serial Port Detection** | Legacy hardware presence | Medium (emulatable but detectable) |
| 6 | **PCI Device Enumeration** | Real hardware device tree | High (requires passthrough) |

### How Rewards Are Calculated

```python
# Simplified reward formula
base_reward = 1.0  # RTC per epoch
cpu_multiplier = get_multiplier_for_cpu()  # 1.0 - 4.0
attestation_score = run_fingerprint_checks()  # 0.0 - 1.0
uptime_factor = min(1.0, hours_online / 24)  # Caps at 24 hours

epoch_reward = base_reward * cpu_multiplier * attestation_score * uptime_factor
```

### Example: PowerPC G4 Mining

```
CPU: PowerPC G4 @ 1.25 GHz (PowerMac G5, 2005)
Multiplier: ×3.5
Attestation: 100% (all 6 checks pass)
Uptime: 12 hours (factor = 0.5)

Reward = 1.0 × 3.5 × 1.0 × 0.5 = 1.75 RTC
```

---

## Setup Deep Dive

### Manual Installation (Alternative to Script)

If you prefer manual control or the script fails:

#### Step 1: Create Directory Structure

```bash
mkdir -p ~/.rustchain
cd ~/.rustchain
```

#### Step 2: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows
```

#### Step 3: Install Dependencies

```bash
pip install requests
```

#### Step 4: Download Miner

```bash
# Detect your architecture
ARCH=$(uname -m)
OS=$(uname -s | tr '[:upper:]' '[:lower:]')

# Download appropriate binary
curl -sSL "https://github.com/Scottcjn/Rustchain/releases/latest/download/rustchain_miner_${OS}_${ARCH}" \
  -o rustchain_miner.py

chmod +x rustchain_miner.py
```

#### Step 5: Configure Wallet

Create `~/.rustchain/config.json`:

```json
{
  "wallet_name": "my-vintage-miner",
  "node_url": "https://rustchain.org",
  "mining_interval_seconds": 60,
  "log_level": "INFO"
}
```

#### Step 6: Download Fingerprint Module

```bash
curl -sSL "https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/linux/fingerprint_checks.py" \
  -o fingerprint_checks.py
```

### Installation Verification

Run these checks to ensure everything is set up correctly:

```bash
# 1. Verify Python environment
source ~/.rustchain/venv/bin/activate
python --version  # Should show your Python version

# 2. Verify dependencies
python -c "import requests; print(requests.__version__)"

# 3. Test fingerprint module
python -c "import fingerprint_checks; print('OK')"

# 4. Test network connectivity
curl -sk https://rustchain.org/health | jq .status
# Expected: "ok"
```

### File Structure After Setup

```
~/.rustchain/
├── venv/                    # Python virtual environment
│   ├── bin/
│   │   ├── python          # Virtualenv Python
│   │   ├── pip             # Virtualenv pip
│   │   └── activate        # Activation script
│   └── lib/
│       └── python3.X/
│           └── site-packages/
│               ├── requests/
│               └── ...
├── rustchain_miner.py      # Main miner script
├── fingerprint_checks.py   # Hardware attestation
├── config.json             # Your configuration
├── start.sh                # Convenience launcher
└── miner.log               # Runtime logs
```

---

## Your First Mining Session

### Starting the Miner

```bash
cd ~/.rustchain
source venv/bin/activate
python rustchain_miner.py --config config.json
```

Or use the convenience script:

```bash
./start.sh
```

### Understanding Miner Output

```
[2026-03-13 10:30:00] INFO  RustChain Miner v2.1.0 starting...
[2026-03-13 10:30:01] INFO  Wallet: my-vintage-miner
[2026-03-13 10:30:01] INFO  Node: https://rustchain.org
[2026-03-13 10:30:02] INFO  Running hardware fingerprint checks...
[2026-03-13 10:30:03] INFO  ✓ CPUID Leaf Analysis: PASS
[2026-03-13 10:30:03] INFO  ✓ Cache Topology: PASS
[2026-03-13 10:30:04] INFO  ✓ Instruction Timing: PASS
[2026-03-13 10:30:04] INFO  ✓ Memory Latency: PASS
[2026-03-13 10:30:05] INFO  ✓ Serial Port Detection: PASS
[2026-03-13 10:30:05] INFO  ✓ PCI Device Enumeration: PASS
[2026-03-13 10:30:05] INFO  Attestation score: 100%
[2026-03-13 10:30:05] INFO  CPU Multiplier: ×3.5 (PowerPC G4)
[2026-03-13 10:30:06] INFO  Registered with node. Mining started.
[2026-03-13 10:31:06] INFO  Heartbeat sent. Uptime: 1m
[2026-03-13 10:32:06] INFO  Heartbeat sent. Uptime: 2m
[2026-03-13 10:33:06] INFO  Pending rewards: 0.05 RTC
```

### Monitoring Your Miner

#### Real-time Logs

```bash
# Follow logs in real-time
tail -f ~/.rustchain/miner.log

# Filter for errors only
tail -f ~/.rustchain/miner.log | grep ERROR

# Filter for reward updates
tail -f ~/.rustchain/miner.log | grep "rewards"
```

#### Query Network Status

```bash
# Check if your miner is registered
curl -sk https://rustchain.org/api/miners | jq \
  '.[] | select(.miner_id == "my-vintage-miner")'

# View all active miners
curl -sk https://rustchain.org/api/miners | jq 'length'

# Check current epoch
curl -sk https://rustchain.org/epoch | jq .
```

#### Check Your Balance

```bash
# Current balance
curl -sk "https://rustchain.org/wallet/balance?miner_id=my-vintage-miner" | jq .

# Expected response:
# {
#   "miner_id": "my-vintage-miner",
#   "balance": 12.5,
#   "pending_rewards": 0.75,
#   "last_heartbeat": "2026-03-13T10:30:00Z",
#   "cpu_multiplier": 3.5
# }
```

### Stopping the Miner

```bash
# Graceful shutdown (sends final heartbeat)
pkill -SIGINT -f rustchain_miner.py

# Or if running in foreground: Ctrl+C
```

---

## Making Transactions

### Understanding RustChain Transactions

RustChain transactions are simple value transfers between wallets:

```json
{
  "from": "sender-wallet",
  "to": "recipient-wallet",
  "amount": 10.0,
  "timestamp": "2026-03-13T10:30:00Z",
  "signature": "base64-encoded-signature"
}
```

### Sending RTC via API

```bash
# Send 5 RTC to another wallet
curl -sk -X POST https://rustchain.org/api/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "from": "my-vintage-miner",
    "to": "recipient-wallet",
    "amount": 5.0
  }' | jq .
```

### Transaction Status

```bash
# Check transaction by ID
curl -sk "https://rustchain.org/api/transaction/TX_ID" | jq .

# List transactions for a wallet
curl -sk "https://rustchain.org/api/wallet/my-vintage-miner/transactions" | jq .
```

### Using the CLI Helper

RustChain provides `clawrtc` for command-line operations:

```bash
# Install
pip install clawrtc

# Check balance
clawrtc balance my-vintage-miner

# Send RTC
clawrtc send --from my-vintage-miner --to recipient-wallet --amount 5.0

# View transaction history
clawrtc history my-vintage-miner
```

---

## Practical Examples

### Example 1: Multi-Miner Setup

Run miners on multiple vintage machines, all reporting to one wallet:

```bash
# Machine 1: PowerPC G4
# config.json: {"wallet_name": "vintage-farm", ...}

# Machine 2: Pentium 4
# config.json: {"wallet_name": "vintage-farm", ...}

# Machine 3: Core 2 Duo
# config.json: {"wallet_name": "vintage-farm", ...}

# All rewards accumulate to "vintage-farm" wallet
curl -sk "https://rustchain.org/wallet/balance?miner_id=vintage-farm" | jq .
```

### Example 2: Automated Monitoring Script

Create `monitor_miner.sh`:

```bash
#!/bin/bash

WALLET="my-vintage-miner"
NODE="https://rustchain.org"

check_miner() {
    # Check node health
    HEALTH=$(curl -sk "$NODE/health" | jq -r '.status')
    if [ "$HEALTH" != "ok" ]; then
        echo "❌ Node unhealthy"
        return 1
    fi
    
    # Check miner visibility
    MINER=$(curl -sk "$NODE/api/miners" | jq -r \
        ".[] | select(.miner_id == \"$WALLET\") | .miner_id")
    if [ -z "$MINER" ]; then
        echo "❌ Miner not visible on network"
        return 1
    fi
    
    # Check balance
    BALANCE=$(curl -sk "$NODE/wallet/balance?miner_id=$WALLET" | jq -r '.balance')
    PENDING=$(curl -sk "$NODE/wallet/balance?miner_id=$WALLET" | jq -r '.pending_rewards')
    
    echo "✅ Miner online | Balance: $BALANCE RTC | Pending: $PENDING RTC"
    return 0
}

# Run check
check_miner
exit $?
```

Usage:

```bash
chmod +x monitor_miner.sh
./monitor_miner.sh

# Add to crontab for hourly checks
crontab -e
# 0 * * * * /path/to/monitor_miner.sh >> /var/log/miner_monitor.log 2>&1
```

### Example 3: Auto-Restart on Failure

Create `watchdog.sh`:

```bash
#!/bin/bash

MINER_DIR="$HOME/.rustchain"
LOG_FILE="$MINER_DIR/watchdog.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

while true; do
    # Check if miner process is running
    if ! pgrep -f "rustchain_miner.py" > /dev/null; then
        log "⚠️  Miner not running. Restarting..."
        cd "$MINER_DIR"
        source venv/bin/activate
        nohup python rustchain_miner.py --config config.json >> miner.log 2>&1 &
        log "✅ Miner restarted (PID: $!)"
    fi
    
    sleep 60  # Check every minute
done
```

### Example 4: Mining Dashboard (Python)

Create `dashboard.py`:

```python
#!/usr/bin/env python3
"""Simple terminal dashboard for monitoring RustChain mining."""

import requests
import time
import os
from datetime import datetime

NODE = "https://rustchain.org"
WALLET = os.environ.get("RUSTCHAIN_WALLET", "my-vintage-miner")

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')

def get_miner_data():
    try:
        balance_resp = requests.get(
            f"{NODE}/wallet/balance?miner_id={WALLET}",
            verify=False, timeout=5
        )
        miners_resp = requests.get(
            f"{NODE}/api/miners",
            verify=False, timeout=5
        )
        epoch_resp = requests.get(
            f"{NODE}/epoch",
            verify=False, timeout=5
        )
        
        return {
            'balance': balance_resp.json(),
            'total_miners': len(miners_resp.json()),
            'epoch': epoch_resp.json()
        }
    except Exception as e:
        return {'error': str(e)}

def render_dashboard(data):
    clear_screen()
    print("=" * 60)
    print("           RUSTCHAIN MINING DASHBOARD")
    print("=" * 60)
    print(f"\nWallet: {WALLET}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if 'error' in data:
        print(f"\n❌ Error: {data['error']}")
        return
    
    balance = data['balance']
    print(f"\n💰 Balance: {balance.get('balance', 'N/A')} RTC")
    print(f"⏳ Pending: {balance.get('pending_rewards', 'N/A')} RTC")
    print(f"📊 Multiplier: ×{balance.get('cpu_multiplier', 'N/A')}")
    
    print(f"\n🌐 Network:")
    print(f"   Active Miners: {data['total_miners']}")
    print(f"   Current Epoch: {data['epoch'].get('epoch', 'N/A')}")
    print(f"   Epoch Ends: {data['epoch'].get('ends_at', 'N/A')}")
    
    print("\n" + "=" * 60)
    print("Press Ctrl+C to exit")

def main():
    try:
        while True:
            data = get_miner_data()
            render_dashboard(data)
            time.sleep(10)  # Refresh every 10 seconds
    except KeyboardInterrupt:
        print("\nDashboard stopped.")

if __name__ == "__main__":
    main()
```

Usage:

```bash
export RUSTCHAIN_WALLET="my-vintage-miner"
python dashboard.py
```

### Example 5: Bridge RTC ↔ wRTC Programmatically

```python
#!/usr/bin/env python3
"""
Example: Bridge RTC to wRTC using the BoTTube Bridge API.

Note: This is a conceptual example. Always use the official
bridge UI at https://bottube.ai/bridge for production use.
"""

import requests

BRIDGE_API = "https://bottube.ai/api/bridge"
WRTC_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"

def bridge_rtc_to_wrtc(amount, rtc_wallet, sol_wallet):
    """
    Bridge RTC from RustChain to wRTC on Solana.
    
    Args:
        amount: Amount of RTC to bridge
        rtc_wallet: RustChain wallet address
        sol_wallet: Solana wallet address (recipient)
    
    Returns:
        Transaction ID or error message
    """
    payload = {
        "direction": "rtc_to_wrtc",
        "amount": amount,
        "source_wallet": rtc_wallet,
        "destination_wallet": sol_wallet,
        "wrtc_mint": WRTC_MINT
    }
    
    response = requests.post(
        f"{BRIDGE_API}/initiate",
        json=payload
    )
    
    if response.status_code == 200:
        tx_data = response.json()
        print(f"✅ Bridge initiated: {tx_data['transaction_id']}")
        print(f"   Amount: {tx_data['amount']} RTC → {tx_data['expected_output']} wRTC")
        print(f"   Status URL: {tx_data['status_url']}")
        return tx_data['transaction_id']
    else:
        print(f"❌ Bridge failed: {response.text}")
        return None

def check_bridge_status(tx_id):
    """Check the status of a bridge transaction."""
    response = requests.get(f"{BRIDGE_API}/status/{tx_id}")
    if response.status_code == 200:
        status = response.json()
        print(f"Bridge Status: {status['status']}")
        print(f"  Confirmations: {status['confirmations']}/{status['required_confirmations']}")
        return status
    return None

# Example usage
if __name__ == "__main__":
    tx_id = bridge_rtc_to_wrtc(
        amount=10.0,
        rtc_wallet="my-vintage-miner",
        sol_wallet="YourSolanaWalletAddress"
    )
    
    if tx_id:
        status = check_bridge_status(tx_id)
```

---

## Troubleshooting

### Common Issues and Solutions

#### Issue: Miner Fails to Start

**Symptoms:**
```
Error: Unable to connect to node
```

**Diagnosis:**
```bash
# Test network connectivity
curl -sk https://rustchain.org/health

# Check if Python can reach the node
python3 -c "import requests; print(requests.get('https://rustchain.org/health', verify=False).json())"
```

**Solutions:**
1. Check firewall rules (allow outbound HTTPS)
2. Verify no proxy is blocking the connection
3. Try alternative DNS: `echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf`
4. Check system time (large clock skew can cause SSL issues)

#### Issue: Attestation Checks Fail

**Symptoms:**
```
✗ CPUID Leaf Analysis: FAIL
Attestation score: 0%
```

**Diagnosis:**
```bash
# Run fingerprint checks manually
cd ~/.rustchain
source venv/bin/activate
python -c "import fingerprint_checks; print(fingerprint_checks.run_all_checks())"
```

**Solutions:**
1. **Running in a VM?** RustChain intentionally blocks VMs. Use bare metal.
2. **CPU too modern?** Some checks may fail on very new CPUs. Check compatibility.
3. **Missing permissions?** Run miner with appropriate user privileges.
4. **Vintage hardware quirk?** Some very old CPUs may need kernel parameters.

#### Issue: No Rewards Accumulating

**Symptoms:**
```
Pending rewards: 0.00 RTC (after hours of mining)
```

**Diagnosis:**
```bash
# Verify miner is visible on network
curl -sk https://rustchain.org/api/miners | jq '.[] | select(.miner_id == "YOUR_WALLET")'

# Check epoch settlement status
curl -sk https://rustchain.org/epoch | jq .
```

**Solutions:**
1. **Wait for epoch settlement:** Rewards settle at epoch boundaries (check `/epoch`)
2. **Verify uptime:** Minimum 1 hour of continuous mining for partial rewards
3. **Check attestation:** Failed checks = 0 rewards
4. **Confirm wallet name:** Ensure you're querying the correct wallet

#### Issue: SSL/Certificate Errors

**Symptoms:**
```
curl: (60) SSL certificate problem: unable to get local issuer certificate
```

**Solutions:**
1. Use `-k` flag (expected for self-signed certs):
   ```bash
   curl -sk https://rustchain.org/health
   ```
2. Or update CA certificates:
   ```bash
   # Ubuntu/Debian
   sudo apt-get update && sudo apt-get install --reinstall ca-certificates
   
   # macOS
   sudo security find-certificate -a -p /System/Library/Keychains/SystemRootCertificates.keychain | \
     sudo tee /etc/ssl/certs/ca-certificates.crt
   ```

#### Issue: Python Virtual Environment Problems

**Symptoms:**
```
ModuleNotFoundError: No module named 'requests'
```

**Solutions:**
```bash
# Activate virtualenv properly
cd ~/.rustchain
source venv/bin/activate

# Verify activation (should show venv path)
which python

# Reinstall dependencies if needed
pip install --upgrade pip
pip install -r requirements.txt  # if exists
pip install requests
```

#### Issue: Auto-Start Service Fails

**Linux (systemd):**
```bash
# Check service status
systemctl --user status rustchain-miner

# View service logs
journalctl --user -u rustchain-miner -f

# Reload systemd config after changes
systemctl --user daemon-reload

# Enable service
systemctl --user enable rustchain-miner
```

**macOS (launchd):**
```bash
# Load the launch agent
launchctl load ~/Library/LaunchAgents/com.rustchain.miner.plist

# Check status
launchctl list | grep rustchain

# View logs
log show --predicate 'process == "Python"' --last 1h
```

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Edit config.json
{
  "wallet_name": "my-vintage-miner",
  "node_url": "https://rustchain.org",
  "mining_interval_seconds": 60,
  "log_level": "DEBUG"  # Change from INFO to DEBUG
}

# Restart miner and check detailed logs
tail -f ~/.rustchain/miner.log
```

### Getting Help

1. **Check existing docs:** [`FAQ_TROUBLESHOOTING.md`](./FAQ_TROUBLESHOOTING.md)
2. **GitHub Issues:** [rustchain-bounties/issues](https://github.com/Scottcjn/rustchain-bounties/issues)
3. **Community channels:** Check README.md for Discord/Telegram links
4. **Include in bug reports:**
   - OS and version
   - Python version
   - CPU model
   - Miner logs (last 50 lines)
   - Network connectivity test results

---

## Advanced Topics

### Running a Full Node

For developers who want to run a full RustChain node:

```bash
# Clone the repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Install node dependencies
pip install -r requirements.txt

# Initialize node data directory
mkdir -p ~/.rustchain-node/data
cp config/node.example.json ~/.rustchain-node/config.json

# Start the node
python node/integrated_node.py --config ~/.rustchain-node/config.json
```

See [`DOCKER_DEPLOYMENT.md`](../DOCKER_DEPLOYMENT.md) for containerized deployment.

### Custom Mining Strategies

#### Dynamic Interval Adjustment

Adjust mining frequency based on network conditions:

```python
import requests
import time

NODE = "https://rustchain.org"
WALLET = "my-vintage-miner"

def get_optimal_interval():
    """Adjust mining interval based on network congestion."""
    epoch_data = requests.get(f"{NODE}/epoch", verify=False).json()
    miners_count = len(requests.get(f"{NODE}/api/miners", verify=False).json())
    
    # More miners = longer intervals to reduce load
    if miners_count > 100:
        return 120  # 2 minutes
    elif miners_count > 50:
        return 90   # 1.5 minutes
    else:
        return 60   # 1 minute (default)

# Use in your miner loop
interval = get_optimal_interval()
time.sleep(interval)
```

### Building on RustChain

#### Integrating RustChain Payments

```python
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
NODE = "https://rustchain.org"

@app.route('/pay', methods=['POST'])
def pay():
    """Accept RTC payments."""
    data = request.json
    from_wallet = data['from']
    to_wallet = data['to']
    amount = data['amount']
    
    # Verify sender has sufficient balance
    balance_resp = requests.get(
        f"{NODE}/wallet/balance?miner_id={from_wallet}",
        verify=False
    )
    balance = balance_resp.json().get('balance', 0)
    
    if balance < amount:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    # Process transaction
    tx_resp = requests.post(
        f"{NODE}/api/transaction",
        json={'from': from_wallet, 'to': to_wallet, 'amount': amount},
        verify=False
    )
    
    return jsonify(tx_resp.json())

if __name__ == '__main__':
    app.run(port=5000)
```

### Security Considerations

1. **Never share wallet credentials** or private keys
2. **Use environment variables** for sensitive config:
   ```bash
   export RUSTCHAIN_WALLET="my-wallet"
   ```
3. **Run miners as non-root** user
4. **Monitor for unusual activity:**
   ```bash
   # Alert on large balance changes
   curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET" | \
     jq 'if .balance < 10 then "⚠️ Low balance alert" else "OK" end'
   ```

---

## Next Steps

### Continue Your Journey

1. **Join the community:**
   - GitHub Discussions: [Scottcjn/Rustchain/discussions](https://github.com/Scottcjn/Rustchain/discussions)
   - Open bounties: [rustchain-bounties/issues](https://github.com/Scottcjn/rustchain-bounties/issues)

2. **Contribute and earn:**
   - Fix bugs, add features, improve docs
   - Every contribution earns RTC tokens
   - See [`CONTRIBUTING.md`](../CONTRIBUTING.md)

3. **Explore advanced topics:**
   - [Protocol Specification](./PROTOCOL.md)
   - [Hardware Fingerprinting Deep Dive](./hardware-fingerprinting.md)
   - [Token Economics](./tokenomics_v1.md)
   - [Cross-Chain Bridge Guide](./bridge-api.md)

4. **Build something:**
   - Create a mining pool
   - Build a wallet UI
   - Develop monitoring tools
   - Write integrations

### Quick Reference

```bash
# Health check
curl -sk https://rustchain.org/health | jq .

# List miners
curl -sk https://rustchain.org/api/miners | jq .

# Check balance
curl -sk "https://rustchain.org/wallet/balance?miner_id=WALLET_NAME" | jq .

# Current epoch
curl -sk https://rustchain.org/epoch | jq .

# Send transaction
curl -sk -X POST https://rustchain.org/api/transaction \
  -H "Content-Type: application/json" \
  -d '{"from":"SENDER","to":"RECIPIENT","amount":10}' | jq .
```

### Related Documentation

| Document | Purpose |
|----------|---------|
| [`INSTALL.md`](../INSTALL.md) | Detailed installation guide |
| [`FAQ_TROUBLESHOOTING.md`](./FAQ_TROUBLESHOOTING.md) | Common issues and fixes |
| [`CPU_ANTIQUITY_SYSTEM.md`](../CPU_ANTIQUITY_SYSTEM.md) | CPU multiplier reference |
| [`PROTOCOL.md`](./PROTOCOL.md) | Full protocol specification |
| [`API_REFERENCE.md`](./api/REFERENCE.md) | Complete API documentation |
| [`WALLET_USER_GUIDE.md`](./WALLET_USER_GUIDE.md) | Wallet management |
| [`wrtc.md`](./wrtc.md) | wRTC on Solana guide |

---

## Appendix A: Supported Hardware Reference

### PowerPC Systems

| Model | CPU | Year | Multiplier |
|-------|-----|------|------------|
| PowerBook G3 | PowerPC 750 | 1998-2001 | ×4.0 |
| PowerMac G4 | PowerPC 7400/7450 | 1999-2004 | ×3.5 |
| PowerMac G5 | PowerPC 970/FX | 2003-2006 | ×3.0 |
| iBook G4 | PowerPC 7447 | 2003-2006 | ×3.5 |

### x86 Systems

| Model | CPU | Year | Multiplier |
|-------|-----|------|------------|
| Pentium 4 | Netburst | 2000-2008 | ×2.0 |
| Core 2 Duo | Conroe/Merom | 2006-2008 | ×2.0 |
| First-gen Core i | Nehalem | 2008-2010 | ×1.5 |
| Modern CPUs | Sandy Bridge+ | 2011+ | ×1.0 |

### Other Architectures

| Architecture | Examples | Multiplier |
|--------------|----------|------------|
| SPARC V9 | UltraSPARC | ×2.5 |
| MIPS | SGI systems | ×2.0 |
| ARM (early) | ARM9, ARM11 | ×3.0 |

---

## Appendix B: API Quick Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Node health check |
| GET | `/epoch` | Current epoch info |
| GET | `/api/miners` | List active miners |
| GET | `/wallet/balance?miner_id=X` | Get wallet balance |
| POST | `/api/transaction` | Send RTC |
| GET | `/api/transaction/ID` | Get transaction details |
| GET | `/api/wallet/ID/transactions` | Wallet transaction history |

### Example Responses

```json
// GET /health
{
  "status": "ok",
  "version": "2.1.0",
  "uptime_seconds": 86400,
  "connected_miners": 47
}

// GET /epoch
{
  "epoch": 1523,
  "started_at": "2026-03-13T00:00:00Z",
  "ends_at": "2026-03-14T00:00:00Z",
  "total_rewards_distributed": 1250.5
}

// GET /wallet/balance?miner_id=my-wallet
{
  "miner_id": "my-wallet",
  "balance": 125.75,
  "pending_rewards": 2.5,
  "last_heartbeat": "2026-03-13T10:30:00Z",
  "cpu_multiplier": 3.5
}
```

---

*This tutorial is maintained by the RustChain community. Found an issue? Submit a PR or claim a bounty at [rustchain-bounties](https://github.com/Scottcjn/rustchain-bounties).*

**Happy mining! ⛏️🔧**
