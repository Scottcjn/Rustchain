# RustChain Python SDK Tutorial

> **Learn to interact with RustChain programmatically using Python**

---

## Table of Contents

- [Introduction](#introduction)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [API Reference](#api-reference)
  - [RustChainClient](#rustchainclient)
  - [Wallet Operations](#wallet-operations)
  - [Miner Operations](#miner-operations)
  - [Network Information](#network-information)
- [Examples](#examples)
  - [Basic Usage](#basic-usage)
  - [Monitor Your Miner](#monitor-your-miner)
  - [Build a Dashboard](#build-a-dashboard)
  - [Automated Alerting](#automated-alerting)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Introduction

The RustChain Python SDK provides a simple interface to interact with the RustChain blockchain. Use it to:

- 💰 Check wallet balances
- ⛏️ Monitor miner status
- 📊 Query network statistics
- 🔔 Build alerting and dashboards
- 🤖 Automate mining operations

---

## Installation

### Option 1: Install from Source

```bash
# Clone the repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Install dependencies
pip install requests
```

### Option 2: Create Your Own Client

The SDK is simple enough to include directly in your project:

```bash
pip install requests
```

Then create `rustchain_sdk.py` with the code from the [RustChainClient](#rustchainclient) section below.

---

## Quick Start

```python
import requests
import warnings

# Disable SSL warnings for self-signed certificates
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

NODE_URL = "https://50.28.86.131"

# Check node health
response = requests.get(f"{NODE_URL}/health", verify=False)
print(response.json())

# Get current epoch
response = requests.get(f"{NODE_URL}/epoch", verify=False)
print(response.json())

# Check wallet balance
wallet = "your-wallet-id"
response = requests.get(f"{NODE_URL}/wallet/balance", params={"miner_id": wallet}, verify=False)
print(response.json())
```

---

## Core Concepts

### Epochs

RustChain operates on **epochs** - time periods of approximately 24 hours (144 slots × 10 minutes). Miners must enroll each epoch to receive rewards.

### Attestation

Before mining, hardware must be **attested** - a process where the miner proves it's running on real hardware (not a VM or emulator) through 6 fingerprint checks.

### Antiquity Multipliers

Older hardware receives higher reward multipliers:
- PowerPC G4: **2.5×**
- PowerPC G5: **2.0×**  
- Modern x86: **1.0×**

### RTC Tokens

RustChain's native token. Balances are stored as:
- `amount_rtc`: Human-readable float (e.g., `12.345678`)
- `amount_i64`: Integer micro-RTC (e.g., `12345678`)

---

## API Reference

### RustChainClient

A complete Python client class:

```python
"""
RustChain Python SDK
A simple client for interacting with the RustChain blockchain.
"""

import requests
import warnings
from typing import Dict, List, Optional
from dataclasses import dataclass

# Disable SSL warnings for self-signed certificates
warnings.filterwarnings('ignore', message='Unverified HTTPS request')


@dataclass
class WalletBalance:
    """Wallet balance information"""
    miner_id: str
    amount_rtc: float
    amount_i64: int


@dataclass
class MinerInfo:
    """Miner information"""
    miner: str
    device_family: str
    device_arch: str
    hardware_type: str
    antiquity_multiplier: float
    entropy_score: float
    last_attest: int


@dataclass
class EpochInfo:
    """Current epoch information"""
    epoch: int
    slot: int
    blocks_per_epoch: int
    epoch_pot: float
    enrolled_miners: int


@dataclass
class NodeHealth:
    """Node health status"""
    ok: bool
    version: str
    uptime_s: int
    db_rw: bool
    backup_age_hours: float
    tip_age_slots: int


class RustChainClient:
    """
    RustChain Python SDK Client
    
    Usage:
        client = RustChainClient()
        health = client.get_health()
        balance = client.get_balance("my-wallet")
    """
    
    DEFAULT_NODE = "https://50.28.86.131"
    
    def __init__(self, node_url: str = None, timeout: int = 30):
        """
        Initialize the RustChain client.
        
        Args:
            node_url: RustChain node URL (default: https://50.28.86.131)
            timeout: Request timeout in seconds (default: 30)
        """
        self.node_url = node_url or self.DEFAULT_NODE
        self.timeout = timeout
    
    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make a GET request to the node."""
        url = f"{self.node_url}{endpoint}"
        response = requests.get(url, params=params, timeout=self.timeout, verify=False)
        response.raise_for_status()
        return response.json()
    
    def _post(self, endpoint: str, data: dict = None) -> dict:
        """Make a POST request to the node."""
        url = f"{self.node_url}{endpoint}"
        response = requests.post(url, json=data, timeout=self.timeout, verify=False)
        response.raise_for_status()
        return response.json()
    
    # ========== Health & Status ==========
    
    def get_health(self) -> NodeHealth:
        """
        Check node health status.
        
        Returns:
            NodeHealth: Node health information
            
        Example:
            >>> client = RustChainClient()
            >>> health = client.get_health()
            >>> print(f"Node OK: {health.ok}, Version: {health.version}")
        """
        data = self._get("/health")
        return NodeHealth(
            ok=data.get("ok", False),
            version=data.get("version", "unknown"),
            uptime_s=data.get("uptime_s", 0),
            db_rw=data.get("db_rw", False),
            backup_age_hours=data.get("backup_age_hours", 0),
            tip_age_slots=data.get("tip_age_slots", 0)
        )
    
    def is_healthy(self) -> bool:
        """
        Quick check if node is healthy.
        
        Returns:
            bool: True if node is healthy
        """
        try:
            health = self.get_health()
            return health.ok
        except:
            return False
    
    # ========== Epoch Information ==========
    
    def get_epoch(self) -> EpochInfo:
        """
        Get current epoch information.
        
        Returns:
            EpochInfo: Current epoch details
            
        Example:
            >>> epoch = client.get_epoch()
            >>> print(f"Epoch {epoch.epoch}, {epoch.enrolled_miners} miners enrolled")
        """
        data = self._get("/epoch")
        return EpochInfo(
            epoch=data.get("epoch", 0),
            slot=data.get("slot", 0),
            blocks_per_epoch=data.get("blocks_per_epoch", 144),
            epoch_pot=data.get("epoch_pot", 0),
            enrolled_miners=data.get("enrolled_miners", 0)
        )
    
    def get_epoch_progress(self) -> float:
        """
        Get epoch progress as a percentage.
        
        Returns:
            float: Progress percentage (0-100)
        """
        epoch = self.get_epoch()
        return (epoch.slot / epoch.blocks_per_epoch) * 100
    
    # ========== Miners ==========
    
    def get_miners(self) -> List[MinerInfo]:
        """
        Get all active/enrolled miners.
        
        Returns:
            List[MinerInfo]: List of active miners
            
        Example:
            >>> miners = client.get_miners()
            >>> for m in miners:
            ...     print(f"{m.miner}: {m.antiquity_multiplier}x")
        """
        data = self._get("/api/miners")
        return [
            MinerInfo(
                miner=m.get("miner", ""),
                device_family=m.get("device_family", ""),
                device_arch=m.get("device_arch", ""),
                hardware_type=m.get("hardware_type", ""),
                antiquity_multiplier=m.get("antiquity_multiplier", 1.0),
                entropy_score=m.get("entropy_score", 0),
                last_attest=m.get("last_attest", 0)
            )
            for m in data
        ]
    
    def get_miner(self, miner_id: str) -> Optional[MinerInfo]:
        """
        Get a specific miner by ID.
        
        Args:
            miner_id: The miner wallet ID
            
        Returns:
            MinerInfo or None if not found
        """
        miners = self.get_miners()
        for m in miners:
            if m.miner == miner_id:
                return m
        return None
    
    def is_miner_active(self, miner_id: str) -> bool:
        """
        Check if a miner is currently active.
        
        Args:
            miner_id: The miner wallet ID
            
        Returns:
            bool: True if miner is active
        """
        return self.get_miner(miner_id) is not None
    
    # ========== Wallet ==========
    
    def get_balance(self, miner_id: str) -> WalletBalance:
        """
        Get wallet balance.
        
        Args:
            miner_id: The wallet/miner ID
            
        Returns:
            WalletBalance: Balance information
            
        Example:
            >>> balance = client.get_balance("my-wallet")
            >>> print(f"Balance: {balance.amount_rtc} RTC")
        """
        data = self._get("/wallet/balance", params={"miner_id": miner_id})
        return WalletBalance(
            miner_id=data.get("miner_id", miner_id),
            amount_rtc=data.get("amount_rtc", 0.0),
            amount_i64=data.get("amount_i64", 0)
        )
    
    def get_balance_rtc(self, miner_id: str) -> float:
        """
        Get wallet balance as RTC float.
        
        Args:
            miner_id: The wallet/miner ID
            
        Returns:
            float: Balance in RTC
        """
        return self.get_balance(miner_id).amount_rtc


# Export for easy import
__all__ = ['RustChainClient', 'WalletBalance', 'MinerInfo', 'EpochInfo', 'NodeHealth']
```

### Wallet Operations

```python
from rustchain_sdk import RustChainClient

client = RustChainClient()

# Get full balance info
balance = client.get_balance("my-wallet")
print(f"Wallet: {balance.miner_id}")
print(f"Balance: {balance.amount_rtc} RTC")
print(f"Raw balance: {balance.amount_i64} micro-RTC")

# Quick balance check
rtc = client.get_balance_rtc("my-wallet")
print(f"You have {rtc} RTC")
```

### Miner Operations

```python
from rustchain_sdk import RustChainClient

client = RustChainClient()

# List all miners
miners = client.get_miners()
print(f"Total miners: {len(miners)}")

for miner in miners:
    print(f"\n{miner.miner}:")
    print(f"  Hardware: {miner.hardware_type}")
    print(f"  Family: {miner.device_family}")
    print(f"  Architecture: {miner.device_arch}")
    print(f"  Multiplier: {miner.antiquity_multiplier}x")

# Check if your miner is active
if client.is_miner_active("my-wallet"):
    print("Your miner is enrolled!")
else:
    print("Your miner is not active. Check logs.")

# Get your miner's details
my_miner = client.get_miner("my-wallet")
if my_miner:
    print(f"Your multiplier: {my_miner.antiquity_multiplier}x")
```

### Network Information

```python
from rustchain_sdk import RustChainClient

client = RustChainClient()

# Check node health
health = client.get_health()
print(f"Node healthy: {health.ok}")
print(f"Version: {health.version}")
print(f"Uptime: {health.uptime_s // 3600} hours")
print(f"Synced: {health.tip_age_slots == 0}")

# Get epoch info
epoch = client.get_epoch()
print(f"\nCurrent epoch: {epoch.epoch}")
print(f"Slot: {epoch.slot}/{epoch.blocks_per_epoch}")
print(f"Progress: {client.get_epoch_progress():.1f}%")
print(f"Reward pool: {epoch.epoch_pot} RTC")
print(f"Enrolled miners: {epoch.enrolled_miners}")
```

---

## Examples

### Basic Usage

```python
#!/usr/bin/env python3
"""Basic RustChain SDK usage example."""

from rustchain_sdk import RustChainClient

def main():
    # Create client
    client = RustChainClient()
    
    # Check if node is reachable
    if not client.is_healthy():
        print("Error: Cannot connect to RustChain node")
        return
    
    # Print network status
    health = client.get_health()
    print(f"RustChain Node v{health.version}")
    print(f"Uptime: {health.uptime_s // 3600}h {(health.uptime_s % 3600) // 60}m")
    
    # Print epoch info
    epoch = client.get_epoch()
    print(f"\n📅 Epoch {epoch.epoch}")
    print(f"   Progress: {client.get_epoch_progress():.1f}%")
    print(f"   Reward pool: {epoch.epoch_pot} RTC")
    print(f"   Active miners: {epoch.enrolled_miners}")
    
    # List top miners by multiplier
    print("\n⛏️ Active Miners:")
    miners = sorted(client.get_miners(), 
                    key=lambda m: m.antiquity_multiplier, 
                    reverse=True)
    
    for m in miners[:5]:
        print(f"   {m.miner[:20]}... {m.hardware_type} ({m.antiquity_multiplier}x)")

if __name__ == "__main__":
    main()
```

### Monitor Your Miner

```python
#!/usr/bin/env python3
"""Monitor your RustChain miner and balance."""

import time
from datetime import datetime
from rustchain_sdk import RustChainClient

WALLET = "your-wallet-id"  # Replace with your wallet
CHECK_INTERVAL = 300  # 5 minutes

def main():
    client = RustChainClient()
    last_balance = None
    
    print(f"🔍 Monitoring wallet: {WALLET}")
    print(f"   Checking every {CHECK_INTERVAL} seconds")
    print("-" * 50)
    
    while True:
        try:
            # Get current state
            health = client.get_health()
            epoch = client.get_epoch()
            balance = client.get_balance_rtc(WALLET)
            is_active = client.is_miner_active(WALLET)
            
            # Calculate changes
            balance_change = ""
            if last_balance is not None:
                diff = balance - last_balance
                if diff > 0:
                    balance_change = f" (+{diff:.6f})"
                elif diff < 0:
                    balance_change = f" ({diff:.6f})"
            last_balance = balance
            
            # Print status
            now = datetime.now().strftime("%H:%M:%S")
            status = "✅ ACTIVE" if is_active else "❌ INACTIVE"
            
            print(f"\n[{now}] Epoch {epoch.epoch} ({epoch.slot}/{epoch.blocks_per_epoch})")
            print(f"   Miner: {status}")
            print(f"   Balance: {balance:.6f} RTC{balance_change}")
            
            if not is_active:
                print("   ⚠️  WARNING: Miner not enrolled! Check if it's running.")
            
            if not health.ok:
                print("   ⚠️  WARNING: Node reports unhealthy status")
            
        except Exception as e:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")
```

### Build a Dashboard

```python
#!/usr/bin/env python3
"""Simple terminal dashboard for RustChain."""

import os
import time
from datetime import datetime
from rustchain_sdk import RustChainClient

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')

def format_uptime(seconds: int) -> str:
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    return f"{hours}h {minutes}m"

def progress_bar(percent: float, width: int = 30) -> str:
    filled = int(width * percent / 100)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}] {percent:.1f}%"

def main():
    client = RustChainClient()
    
    while True:
        try:
            clear_screen()
            
            # Get all data
            health = client.get_health()
            epoch = client.get_epoch()
            miners = client.get_miners()
            progress = client.get_epoch_progress()
            
            # Header
            print("╔══════════════════════════════════════════════════════════════╗")
            print("║               🔗 RUSTCHAIN NETWORK DASHBOARD                  ║")
            print("╠══════════════════════════════════════════════════════════════╣")
            
            # Node status
            status = "🟢 ONLINE" if health.ok else "🔴 OFFLINE"
            print(f"║  Node: {status:<20} Version: {health.version:<15}  ║")
            print(f"║  Uptime: {format_uptime(health.uptime_s):<15} Synced: {'Yes' if health.tip_age_slots == 0 else 'No':<10}        ║")
            
            print("╠══════════════════════════════════════════════════════════════╣")
            
            # Epoch info
            print(f"║  📅 EPOCH {epoch.epoch:<5}                                          ║")
            print(f"║  Slot: {epoch.slot}/{epoch.blocks_per_epoch} {progress_bar(progress):<30}  ║")
            print(f"║  Reward Pool: {epoch.epoch_pot} RTC                                    ║")
            print(f"║  Enrolled Miners: {epoch.enrolled_miners}                                         ║")
            
            print("╠══════════════════════════════════════════════════════════════╣")
            
            # Miners table
            print("║  ⛏️  ACTIVE MINERS                                             ║")
            print("║  ─────────────────────────────────────────────────────────── ║")
            
            # Sort by multiplier
            sorted_miners = sorted(miners, key=lambda m: m.antiquity_multiplier, reverse=True)
            
            for i, m in enumerate(sorted_miners[:8]):
                name = m.miner[:25]
                hw = m.hardware_type[:18]
                mult = f"{m.antiquity_multiplier}x"
                print(f"║  {i+1}. {name:<25} {hw:<18} {mult:>5} ║")
            
            if len(miners) > 8:
                print(f"║     ... and {len(miners) - 8} more miners                              ║")
            
            print("╠══════════════════════════════════════════════════════════════╣")
            
            # Footer
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"║  Last updated: {now}                            ║")
            print("║  Press Ctrl+C to exit                                        ║")
            print("╚══════════════════════════════════════════════════════════════╝")
            
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(30)  # Refresh every 30 seconds

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDashboard closed.")
```

### Automated Alerting

```python
#!/usr/bin/env python3
"""
Alert when miner goes offline or balance changes.
Integrate with your preferred notification system.
"""

import time
from datetime import datetime
from rustchain_sdk import RustChainClient

# Configuration
WALLET = "your-wallet-id"
CHECK_INTERVAL = 60  # seconds
ALERT_ON_OFFLINE = True
ALERT_ON_BALANCE_CHANGE = True

def send_alert(message: str):
    """
    Send alert notification.
    Customize this to integrate with:
    - Email (smtplib)
    - Slack (slack_sdk)
    - Discord (discord.py)
    - Telegram (python-telegram-bot)
    - SMS (twilio)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"🚨 ALERT [{timestamp}]: {message}")
    
    # Example: Send to Discord webhook
    # import requests
    # requests.post(DISCORD_WEBHOOK, json={"content": message})
    
    # Example: Send email
    # import smtplib
    # ... email sending code ...

def main():
    client = RustChainClient()
    
    # Track state
    was_online = None
    last_balance = None
    
    print(f"🔔 Starting alert monitor for {WALLET}")
    print(f"   Check interval: {CHECK_INTERVAL}s")
    print("-" * 50)
    
    while True:
        try:
            # Check miner status
            is_online = client.is_miner_active(WALLET)
            balance = client.get_balance_rtc(WALLET)
            
            # Alert on status change
            if was_online is not None and was_online != is_online:
                if ALERT_ON_OFFLINE:
                    if is_online:
                        send_alert(f"✅ Miner {WALLET} is back ONLINE")
                    else:
                        send_alert(f"❌ Miner {WALLET} went OFFLINE!")
            
            # Alert on balance change
            if last_balance is not None and balance != last_balance:
                if ALERT_ON_BALANCE_CHANGE:
                    diff = balance - last_balance
                    if diff > 0:
                        send_alert(f"💰 Received {diff:.6f} RTC! New balance: {balance:.6f} RTC")
            
            # Update state
            was_online = is_online
            last_balance = balance
            
            # Log status
            status = "✅" if is_online else "❌"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {status} Balance: {balance:.6f} RTC")
            
        except Exception as e:
            send_alert(f"⚠️ Monitor error: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAlert monitor stopped.")
```

---

## Best Practices

### 1. Handle Network Errors Gracefully

```python
from rustchain_sdk import RustChainClient
import requests

client = RustChainClient()

try:
    balance = client.get_balance("my-wallet")
except requests.exceptions.ConnectionError:
    print("Cannot connect to RustChain node")
except requests.exceptions.Timeout:
    print("Request timed out")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### 2. Use Appropriate Timeouts

```python
# For quick checks
client = RustChainClient(timeout=10)

# For slower networks
client = RustChainClient(timeout=60)
```

### 3. Cache Results When Appropriate

```python
import time
from functools import lru_cache

@lru_cache(maxsize=1)
def get_cached_miners(cache_time: int) -> list:
    """Cache miners list for performance."""
    return client.get_miners()

# Refresh every 5 minutes
cache_key = int(time.time()) // 300
miners = get_cached_miners(cache_key)
```

### 4. Respect Rate Limits

```python
import time

# Don't hammer the API
for wallet in wallets:
    balance = client.get_balance(wallet)
    time.sleep(0.5)  # Wait between requests
```

### 5. Validate Input

```python
def get_balance_safe(wallet: str) -> float:
    """Get balance with input validation."""
    if not wallet or len(wallet) > 100:
        raise ValueError("Invalid wallet address")
    
    # Sanitize wallet ID
    wallet = wallet.strip()
    
    return client.get_balance_rtc(wallet)
```

---

## Troubleshooting

### "SSL: CERTIFICATE_VERIFY_FAILED"

The RustChain node uses a self-signed certificate. The SDK disables verification by default, but if you're using raw requests:

```python
import requests
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Use verify=False
response = requests.get("https://50.28.86.131/health", verify=False)
```

### "Connection refused"

Check if the node is accessible:

```bash
curl -sk https://50.28.86.131/health
```

If this fails, the node may be down or your network may be blocking port 443.

### "Empty response"

The node might be syncing. Check the health endpoint:

```python
health = client.get_health()
if health.tip_age_slots > 0:
    print(f"Node is syncing, {health.tip_age_slots} slots behind")
```

### "Miner not found"

Your miner may not be enrolled for the current epoch:

1. Check if miner is running: `systemctl --user status rustchain-miner`
2. Check logs for errors: `journalctl --user -u rustchain-miner -n 50`
3. Verify attestation is passing

---

## Additional Resources

- **API Reference:** [docs/API_REFERENCE.md](./API_REFERENCE.md)
- **Miner Setup Guide:** [docs/MINER_SETUP_GUIDE.md](./MINER_SETUP_GUIDE.md)
- **GitHub Repository:** https://github.com/Scottcjn/Rustchain
- **Live Explorer:** http://50.28.86.131/explorer

---

*RustChain Python SDK Tutorial v1.0*  
*Last updated: February 2026*
