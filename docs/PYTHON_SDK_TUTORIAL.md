# RustChain Python SDK Tutorial

A comprehensive guide to using Python to interact with the RustChain API and manage your mining operations.

## Table of Contents

- [Overview](#overview)
- [Setup](#setup)
- [Authentication](#authentication)
- [Basic Concepts](#basic-concepts)
- [Wallet Operations](#wallet-operations)
- [Mining Status & Monitoring](#mining-status--monitoring)
- [Example Scripts](#example-scripts)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)

---

## Overview

The RustChain Python SDK allows you to:

- **Monitor** your mining status and rewards
- **Manage** wallet balances
- **Query** miner information from the network
- **Automate** reward claims and transfers
- **Track** your hardware's antiquity multiplier

### RustChain API Basics

- **Base URL:** `https://50.28.86.131`
- **Protocol:** HTTPS (REST API)
- **SSL Certificate:** Self-signed (use `verify=False` in requests)
- **Response Format:** JSON
- **Rate Limit:** 100 requests/minute per IP

---

## Setup

### Prerequisites

- Python 3.6+
- `requests` library
- Internet connection to RustChain node
- Your miner wallet name

### Installation

Install the required dependencies:

```bash
pip install requests
```

For enhanced security features (optional):
```bash
pip install requests cryptography
```

### Verify Connection

Test your connection to the RustChain node:

```python
import requests
import warnings
warnings.filterwarnings('ignore')

# Test basic connectivity
response = requests.get("https://50.28.86.131/health", verify=False)
print(response.json())
```

Expected output:
```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 18728,
  "db_rw": true,
  "tip_age_slots": 0,
  "backup_age_hours": 6.75
}
```

---

## Authentication

### Public Endpoints (No Auth Required)

Most endpoints are public and don't require authentication:

```python
import requests
import warnings
warnings.filterwarnings('ignore')

NODE_URL = "https://50.28.86.131"

# Get node health (public)
response = requests.get(f"{NODE_URL}/health", verify=False)
print(response.json())

# Get active miners (public)
response = requests.get(f"{NODE_URL}/api/miners", verify=False)
print(response.json())
```

### Wallet-Specific Operations

To check your wallet balance, use your wallet name as a parameter:

```python
WALLET_NAME = "my-mining-wallet"

# Check balance (public)
response = requests.get(
    f"{NODE_URL}/wallet/balance",
    params={"miner_id": WALLET_NAME},
    verify=False
)
balance_data = response.json()
print(f"Balance: {balance_data['amount_rtc']} RTC")
```

### Signed Transactions (Coming Soon)

For future features like reward transfers, you'll sign transactions with Ed25519:

```python
import json
import base64
from cryptography.hazmat.primitives.asymmetric import ed25519

# Generate keys (do this once and store securely)
private_key = ed25519.Ed25519PrivateKey.generate()
public_key = private_key.public_key()

# Create and sign a transaction
transaction = {
    "from": "my-wallet",
    "to": "recipient-wallet",
    "amount_i64": 100000000,  # In micro-RTC (6 decimals)
    "nonce": 1
}

message = json.dumps(transaction, sort_keys=True).encode()
signature = private_key.sign(message)
signature_b64 = base64.b64encode(signature).decode()

transaction["signature"] = signature_b64
print(json.dumps(transaction, indent=2))
```

---

## Basic Concepts

### Wallet Address Format

RustChain wallet addresses typically follow the format:
```
username-unique-suffix
my-miner-wallet
g5-selena-179
```

Your wallet is created automatically during miner installation.

### Amount Units

RustChain uses two unit systems:

| Unit | Format | Decimal Places | Usage |
|------|--------|---|---|
| **RTC** | Float | 6 decimals | Human-readable (1.5 RTC) |
| **micro-RTC** (i64) | Integer | 6 decimals (1 RTC = 1,000,000 µRTC) | API transactions (1500000) |

```python
# Conversion examples
rtc_amount = 1.5
micro_rtc = int(rtc_amount * 1_000_000)  # 1500000

micro_rtc = 1500000
rtc_amount = micro_rtc / 1_000_000  # 1.5
```

### Epochs

RustChain operates in 24-hour epochs:

```python
response = requests.get(f"{NODE_URL}/epoch", verify=False)
epoch_data = response.json()

print(f"Current Epoch: {epoch_data['epoch']}")
print(f"Blocks per epoch: {epoch_data['blocks_per_epoch']}")  # Usually 144
print(f"Enrolled miners: {epoch_data['enrolled_miners']}")
print(f"Epoch rewards pool: {epoch_data['epoch_pot']} RTC")
```

### Antiquity Multiplier

Your rewards are multiplied based on your hardware's age:

```python
response = requests.get(f"{NODE_URL}/api/miners", verify=False)
miners = response.json()

for miner in miners:
    print(f"Miner: {miner['miner']}")
    print(f"  Hardware: {miner['hardware_type']}")
    print(f"  Multiplier: {miner['antiquity_multiplier']}x")
```

Typical multipliers:
- PowerPC G4: 2.5x (most valuable)
- PowerPC G5: 2.0x
- x86_64 (older): 1.5x
- x86_64 (modern): 1.0x

---

## Wallet Operations

### Check Wallet Balance

```python
def get_wallet_balance(wallet_name):
    """Get current wallet balance"""
    response = requests.get(
        f"{NODE_URL}/wallet/balance",
        params={"miner_id": wallet_name},
        verify=False
    )
    
    if response.status_code == 200:
        data = response.json()
        return {
            "wallet": data['miner_id'],
            "rtc": data['amount_rtc'],
            "micro_rtc": data['amount_i64']
        }
    else:
        raise Exception(f"Error: {response.status_code} - {response.text}")

# Usage
wallet = "my-mining-wallet"
balance = get_wallet_balance(wallet)
print(f"Wallet: {balance['wallet']}")
print(f"Balance: {balance['rtc']} RTC")
```

### Check Wallet History

```python
def get_miner_details(wallet_name):
    """Get detailed miner information"""
    response = requests.get(
        f"{NODE_URL}/api/miners",
        verify=False
    )
    
    if response.status_code == 200:
        miners = response.json()
        for miner in miners:
            if miner['miner'] == wallet_name:
                return miner
    return None

# Usage
miner_info = get_miner_details("my-mining-wallet")
if miner_info:
    print(f"Hardware: {miner_info['hardware_type']}")
    print(f"Antiquity Multiplier: {miner_info['antiquity_multiplier']}x")
    print(f"Last Attestation: {miner_info['last_attest']}")
    print(f"Entropy Score: {miner_info['entropy_score']}")
```

### Monitor Multiple Wallets

```python
def monitor_wallets(wallet_list):
    """Monitor multiple wallets simultaneously"""
    total_balance = 0
    
    print("="*60)
    print("Wallet Balance Report")
    print("="*60)
    
    for wallet in wallet_list:
        try:
            balance = get_wallet_balance(wallet)
            total_balance += balance['rtc']
            print(f"{wallet:30} {balance['rtc']:>15.6f} RTC")
        except Exception as e:
            print(f"{wallet:30} ERROR: {str(e)}")
    
    print("="*60)
    print(f"{'Total Balance':30} {total_balance:>15.6f} RTC")
    print("="*60)

# Usage
wallets = ["miner1", "miner2", "miner3"]
monitor_wallets(wallets)
```

---

## Mining Status & Monitoring

### Check Node Health

```python
def check_node_health():
    """Check RustChain node status"""
    response = requests.get(
        f"{NODE_URL}/health",
        verify=False
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": "Node unreachable"}

# Usage
health = check_node_health()
print(f"Node Status: {'ONLINE' if health.get('ok') else 'OFFLINE'}")
print(f"Version: {health.get('version')}")
print(f"Uptime: {health.get('uptime_s')} seconds")
print(f"Database: {'RW' if health.get('db_rw') else 'Read-Only'}")
print(f"Backup Age: {health.get('backup_age_hours')} hours")
```

### Monitor Mining Status

```python
def get_mining_status(wallet_name):
    """Get current mining status for a wallet"""
    # Get node epoch info
    epoch_resp = requests.get(f"{NODE_URL}/epoch", verify=False)
    epoch_data = epoch_resp.json()
    
    # Get wallet balance
    balance_resp = requests.get(
        f"{NODE_URL}/wallet/balance",
        params={"miner_id": wallet_name},
        verify=False
    )
    balance_data = balance_resp.json()
    
    # Get miner info
    miners_resp = requests.get(f"{NODE_URL}/api/miners", verify=False)
    miners = miners_resp.json()
    
    miner_info = None
    for miner in miners:
        if miner['miner'] == wallet_name:
            miner_info = miner
            break
    
    return {
        "wallet": wallet_name,
        "balance_rtc": balance_data['amount_rtc'],
        "current_epoch": epoch_data['epoch'],
        "enrolled_miners": epoch_data['enrolled_miners'],
        "miner_enrolled": miner_info is not None,
        "hardware": miner_info['hardware_type'] if miner_info else None,
        "multiplier": miner_info['antiquity_multiplier'] if miner_info else None,
        "last_attestation": miner_info['last_attest'] if miner_info else None
    }

# Usage
status = get_mining_status("my-mining-wallet")
print(f"Wallet: {status['wallet']}")
print(f"Balance: {status['balance_rtc']} RTC")
print(f"Enrolled: {status['miner_enrolled']}")
print(f"Hardware: {status['hardware']}")
print(f"Multiplier: {status['multiplier']}x")
print(f"Current Epoch: {status['current_epoch']}")
```

### Estimate Earnings

```python
def estimate_daily_earnings(wallet_name):
    """
    Estimate daily RTC earnings.
    Note: This is a rough estimate based on current network state.
    """
    status = get_mining_status(wallet_name)
    
    if not status['miner_enrolled']:
        return {"error": "Miner not enrolled", "estimated_daily": 0}
    
    # Get current epoch info
    epoch_resp = requests.get(f"{NODE_URL}/epoch", verify=False)
    epoch = epoch_resp.json()
    
    if epoch['enrolled_miners'] == 0:
        return {"error": "No miners enrolled", "estimated_daily": 0}
    
    # Rough estimate: epoch_pot / enrolled_miners * multiplier
    base_reward = epoch['epoch_pot'] / epoch['enrolled_miners']
    adjusted_reward = base_reward * status['multiplier']
    
    return {
        "wallet": wallet_name,
        "hardware": status['hardware'],
        "multiplier": status['multiplier'],
        "epoch_pot": epoch['epoch_pot'],
        "enrolled_miners": epoch['enrolled_miners'],
        "estimated_daily_base": base_reward,
        "estimated_daily_adjusted": adjusted_reward,
        "estimated_monthly": adjusted_reward * 30
    }

# Usage
earnings = estimate_daily_earnings("my-mining-wallet")
if "error" not in earnings:
    print(f"Estimated Daily Earnings: {earnings['estimated_daily_adjusted']:.6f} RTC")
    print(f"Estimated Monthly Earnings: {earnings['estimated_monthly']:.6f} RTC")
else:
    print(f"Cannot estimate: {earnings['error']}")
```

### List Active Miners

```python
def list_active_miners(sort_by='multiplier'):
    """List all active miners with details"""
    response = requests.get(f"{NODE_URL}/api/miners", verify=False)
    miners = response.json()
    
    # Sort by requested field
    if sort_by == 'multiplier':
        miners = sorted(miners, key=lambda x: x['antiquity_multiplier'], reverse=True)
    elif sort_by == 'hardware':
        miners = sorted(miners, key=lambda x: x['device_family'])
    
    print(f"{'Miner ID':40} {'Hardware':20} {'Multiplier':10}")
    print("="*70)
    
    for miner in miners:
        print(f"{miner['miner']:40} {miner['hardware_type']:20} {miner['antiquity_multiplier']:>8}x")

# Usage
list_active_miners()
```

---

## Example Scripts

### Complete Monitoring Dashboard

```python
#!/usr/bin/env python3
"""
RustChain Mining Dashboard
Real-time monitoring of your mining operations
"""

import requests
import warnings
from datetime import datetime
import time

warnings.filterwarnings('ignore')
NODE_URL = "https://50.28.86.131"

class RustChainDashboard:
    def __init__(self, wallet_names):
        self.wallet_names = wallet_names
        self.NODE_URL = NODE_URL
    
    def update(self):
        """Update all dashboard data"""
        clear_screen()
        print(f"RustChain Mining Dashboard - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # Node health
        self._show_node_health()
        
        # Epoch info
        self._show_epoch_info()
        
        # Wallet balances
        self._show_balances()
        
        print("="*80)
        print("Press Ctrl+C to exit")
    
    def _show_node_health(self):
        """Display node health"""
        try:
            response = requests.get(f"{self.NODE_URL}/health", verify=False)
            health = response.json()
            status = "🟢 ONLINE" if health.get('ok') else "🔴 OFFLINE"
            print(f"\nNode Status: {status}")
            print(f"  Version: {health.get('version')}")
            print(f"  Uptime: {health.get('uptime_s', 0) // 3600}h")
            print(f"  Database: {'RW' if health.get('db_rw') else 'RO'}")
        except:
            print("\nNode Status: 🔴 UNREACHABLE")
    
    def _show_epoch_info(self):
        """Display epoch information"""
        try:
            response = requests.get(f"{self.NODE_URL}/epoch", verify=False)
            epoch = response.json()
            print(f"\nEpoch Information:")
            print(f"  Current Epoch: {epoch['epoch']}")
            print(f"  Active Miners: {epoch['enrolled_miners']}")
            print(f"  Epoch Rewards Pool: {epoch['epoch_pot']} RTC")
            print(f"  Per-Miner Base: {epoch['epoch_pot']/epoch['enrolled_miners']:.6f} RTC")
        except:
            print("\nEpoch Information: ERROR")
    
    def _show_balances(self):
        """Display wallet balances"""
        print(f"\nWallet Balances:")
        print(f"{'Wallet':35} {'Balance':15} {'Hardware':15}")
        print("-"*80)
        
        total = 0
        for wallet in self.wallet_names:
            try:
                # Get balance
                bal_resp = requests.get(
                    f"{self.NODE_URL}/wallet/balance",
                    params={"miner_id": wallet},
                    verify=False
                )
                balance = bal_resp.json()['amount_rtc']
                
                # Get miner info
                min_resp = requests.get(f"{self.NODE_URL}/api/miners", verify=False)
                miners = min_resp.json()
                hardware = next(
                    (m['hardware_type'] for m in miners if m['miner'] == wallet),
                    "Unknown"
                )
                
                print(f"{wallet:35} {balance:>14.6f} {hardware:15}")
                total += balance
            except:
                print(f"{wallet:35} {'ERROR':>14} {'ERROR':15}")
        
        print("-"*80)
        print(f"{'TOTAL':35} {total:>14.6f}")

def clear_screen():
    import os
    os.system('clear' if os.name == 'posix' else 'cls')

# Main loop
if __name__ == "__main__":
    wallets = ["my-miner-1", "my-miner-2"]
    dashboard = RustChainDashboard(wallets)
    
    try:
        while True:
            dashboard.update()
            time.sleep(30)  # Update every 30 seconds
    except KeyboardInterrupt:
        print("\n\nDashboard closed.")
```

Save as `dashboard.py` and run:
```bash
python3 dashboard.py
```

### Periodic Reward Tracker

```python
#!/usr/bin/env python3
"""
Track cumulative rewards over time
"""

import requests
import json
from datetime import datetime

NODE_URL = "https://50.28.86.131"

class RewardTracker:
    def __init__(self, wallet, log_file="rewards.log"):
        self.wallet = wallet
        self.log_file = log_file
    
    def record_balance(self):
        """Record current balance to log file"""
        try:
            response = requests.get(
                f"{NODE_URL}/wallet/balance",
                params={"miner_id": self.wallet},
                verify=False
            )
            balance = response.json()['amount_rtc']
            
            timestamp = datetime.now().isoformat()
            record = {
                "timestamp": timestamp,
                "balance": balance
            }
            
            # Append to log
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(record) + "\n")
            
            print(f"[{timestamp}] Recorded balance: {balance} RTC")
            return balance
        except Exception as e:
            print(f"Error recording balance: {e}")
            return None
    
    def analyze_earnings(self):
        """Analyze earnings rate"""
        try:
            with open(self.log_file, 'r') as f:
                records = [json.loads(line) for line in f]
            
            if len(records) < 2:
                print("Need at least 2 records for analysis")
                return None
            
            first = records[0]
            last = records[-1]
            
            # Time difference in hours
            from datetime import datetime
            t1 = datetime.fromisoformat(first['timestamp'])
            t2 = datetime.fromisoformat(last['timestamp'])
            hours = (t2 - t1).total_seconds() / 3600
            
            # Calculate earnings
            earnings = last['balance'] - first['balance']
            hourly_rate = earnings / hours if hours > 0 else 0
            daily_rate = hourly_rate * 24
            
            print(f"\nEarnings Analysis for {self.wallet}:")
            print(f"  Period: {first['timestamp']} to {last['timestamp']}")
            print(f"  Duration: {hours:.1f} hours")
            print(f"  Starting Balance: {first['balance']:.6f} RTC")
            print(f"  Current Balance: {last['balance']:.6f} RTC")
            print(f"  Total Earned: {earnings:.6f} RTC")
            print(f"  Hourly Rate: {hourly_rate:.6f} RTC/h")
            print(f"  Estimated Daily: {daily_rate:.6f} RTC/day")
            print(f"  Estimated Monthly: {daily_rate*30:.6f} RTC/month")
            
        except Exception as e:
            print(f"Error analyzing earnings: {e}")

# Usage
if __name__ == "__main__":
    tracker = RewardTracker("my-mining-wallet")
    
    # Record balance
    tracker.record_balance()
    
    # Later, analyze earnings
    # tracker.analyze_earnings()
```

Save as `track_rewards.py`:
```bash
# Record balance once
python3 track_rewards.py

# Set up cron job to run daily
# crontab -e
# Add: 0 12 * * * cd /path && python3 track_rewards.py
```

### Network Statistics Collector

```python
#!/usr/bin/env python3
"""
Collect and display network statistics
"""

import requests
import json
from datetime import datetime

NODE_URL = "https://50.28.86.131"

class NetworkStats:
    @staticmethod
    def get_stats():
        """Collect comprehensive network statistics"""
        try:
            # Get health
            health = requests.get(f"{NODE_URL}/health", verify=False).json()
            
            # Get epoch
            epoch = requests.get(f"{NODE_URL}/epoch", verify=False).json()
            
            # Get miners
            miners_resp = requests.get(f"{NODE_URL}/api/miners", verify=False)
            miners = miners_resp.json()
            
            # Aggregate miner stats
            multipliers = [m['antiquity_multiplier'] for m in miners]
            hardware_types = {}
            total_balance = 0
            
            for miner in miners:
                hw = miner['device_family']
                hardware_types[hw] = hardware_types.get(hw, 0) + 1
                
                # Try to get balance
                try:
                    bal = requests.get(
                        f"{NODE_URL}/wallet/balance",
                        params={"miner_id": miner['miner']},
                        verify=False
                    ).json()
                    total_balance += bal['amount_rtc']
                except:
                    pass
            
            stats = {
                "timestamp": datetime.now().isoformat(),
                "node_version": health.get('version'),
                "node_uptime_hours": health.get('uptime_s', 0) // 3600,
                "current_epoch": epoch['epoch'],
                "enrolled_miners": epoch['enrolled_miners'],
                "epoch_pot_rtc": epoch['epoch_pot'],
                "total_miners_ever": len(miners),
                "hardware_distribution": hardware_types,
                "avg_multiplier": sum(multipliers) / len(multipliers) if multipliers else 0,
                "total_balance_rtc": total_balance
            }
            
            return stats
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def print_stats(stats):
        """Pretty print statistics"""
        if "error" in stats:
            print(f"Error: {stats['error']}")
            return
        
        print(f"\n{'='*60}")
        print(f"RustChain Network Statistics")
        print(f"Timestamp: {stats['timestamp']}")
        print(f"{'='*60}")
        
        print(f"\nNode Status:")
        print(f"  Version: {stats['node_version']}")
        print(f"  Uptime: {stats['node_uptime_hours']} hours")
        
        print(f"\nNetwork State:")
        print(f"  Current Epoch: {stats['current_epoch']}")
        print(f"  Active Miners: {stats['enrolled_miners']}")
        print(f"  Total Miners: {stats['total_miners_ever']}")
        print(f"  Epoch Rewards Pool: {stats['epoch_pot_rtc']} RTC")
        print(f"  Average Multiplier: {stats['avg_multiplier']:.2f}x")
        
        print(f"\nHardware Distribution:")
        for hw, count in stats['hardware_distribution'].items():
            pct = (count / stats['total_miners_ever'] * 100) if stats['total_miners_ever'] > 0 else 0
            print(f"  {hw:20} {count:>3} miners ({pct:>5.1f}%)")
        
        print(f"\nEconomics:")
        print(f"  Total Balance: {stats['total_balance_rtc']:.2f} RTC")
        print(f"{'='*60}\n")

# Usage
if __name__ == "__main__":
    stats = NetworkStats.get_stats()
    NetworkStats.print_stats(stats)
    
    # Save to file
    with open("network_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print("Stats saved to network_stats.json")
```

Run it:
```bash
python3 network_stats.py
```

---

## Error Handling

### Handle Connection Errors

```python
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

def safe_api_call(endpoint, params=None):
    """Make API call with error handling"""
    try:
        response = requests.get(
            f"{NODE_URL}{endpoint}",
            params=params,
            verify=False,
            timeout=10
        )
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        elif response.status_code == 404:
            return {"success": False, "error": "Resource not found"}
        elif response.status_code == 429:
            return {"success": False, "error": "Rate limited - wait before retrying"}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}
    
    except Timeout:
        return {"success": False, "error": "Request timeout - node may be slow"}
    except ConnectionError:
        return {"success": False, "error": "Cannot connect to node - check network"}
    except RequestException as e:
        return {"success": False, "error": f"Request error: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

# Usage
result = safe_api_call("/epoch")
if result['success']:
    print(f"Epoch: {result['data']['epoch']}")
else:
    print(f"Error: {result['error']}")
```

### Implement Retry Logic

```python
import time
import random

def api_call_with_retry(endpoint, params=None, max_retries=3, backoff_factor=2):
    """Make API call with exponential backoff retry"""
    for attempt in range(max_retries):
        try:
            response = requests.get(
                f"{NODE_URL}{endpoint}",
                params=params,
                verify=False,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                # Rate limited - wait longer
                wait_time = 60 * (attempt + 1)
                print(f"Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"HTTP {response.status_code}: {response.text}")
                return None
        
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Final attempt failed: {e}")
                return None
            
            wait_time = backoff_factor ** attempt + random.uniform(0, 1)
            print(f"Attempt {attempt+1} failed. Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)
    
    return None

# Usage
data = api_call_with_retry("/epoch")
if data:
    print(f"Epoch: {data['epoch']}")
```

---

## Best Practices

### 1. Handle SSL Certificate Warning

Always suppress the SSL warning when using self-signed certificates:

```python
import requests
import urllib3

# Disable SSL warnings (only for self-signed certs you trust)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Now requests with verify=False won't warn
response = requests.get("https://50.28.86.131/health", verify=False)
```

### 2. Rate Limiting

Respect the API rate limits:

```python
import time

def rate_limited_request(endpoint, delay=0.1):
    """Make request with rate limiting"""
    response = requests.get(
        f"{NODE_URL}{endpoint}",
        verify=False
    )
    time.sleep(delay)  # Wait between requests
    return response.json()

# Safe: space out requests
for wallet in wallets:
    data = rate_limited_request(f"/wallet/balance?miner_id={wallet}")
    time.sleep(0.5)  # 500ms between requests
```

### 3. Cache Results

Avoid repeated API calls for the same data:

```python
import time
from functools import wraps

def cached(ttl=300):
    """Cache decorator with TTL (in seconds)"""
    def decorator(func):
        cache = {}
        last_update = [0]
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            if now - last_update[0] > ttl:
                cache['result'] = func(*args, **kwargs)
                last_update[0] = now
            return cache['result']
        
        return wrapper
    return decorator

@cached(ttl=60)
def get_epoch():
    """Get epoch info (cached for 60 seconds)"""
    return requests.get(f"{NODE_URL}/epoch", verify=False).json()

# Fast: uses cached result
for i in range(10):
    epoch = get_epoch()  # Only makes 1 API call
```

### 4. Validate Input

Always validate user input:

```python
import re

def validate_wallet_name(wallet):
    """Validate wallet name format"""
    if not isinstance(wallet, str):
        raise ValueError("Wallet must be a string")
    
    if len(wallet) < 3:
        raise ValueError("Wallet name too short")
    
    if len(wallet) > 50:
        raise ValueError("Wallet name too long")
    
    # Alphanumeric and hyphens only
    if not re.match(r'^[a-zA-Z0-9_-]+$', wallet):
        raise ValueError("Invalid wallet name characters")
    
    return wallet

# Usage
try:
    wallet = validate_wallet_name("my-wallet-123")
    print(f"Valid: {wallet}")
except ValueError as e:
    print(f"Invalid: {e}")
```

### 5. Log API Requests

Track your API usage for debugging:

```python
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    filename='rustchain_api.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def logged_request(endpoint, params=None):
    """Make request with logging"""
    try:
        response = requests.get(
            f"{NODE_URL}{endpoint}",
            params=params,
            verify=False
        )
        logging.info(f"GET {endpoint} -> {response.status_code}")
        return response.json()
    except Exception as e:
        logging.error(f"GET {endpoint} failed: {e}")
        raise

# Usage
result = logged_request("/epoch")
```

### 6. Secure Wallet Operations

Never hardcode wallet names or secrets:

```python
import os
from dotenv import load_dotenv

# Load from .env file
load_dotenv()

WALLET = os.getenv("RUSTCHAIN_WALLET")
if not WALLET:
    raise ValueError("Set RUSTCHAIN_WALLET environment variable")

# Use wallet safely
balance = get_wallet_balance(WALLET)
```

Create `.env` file:
```
RUSTCHAIN_WALLET=my-wallet-name
RUSTCHAIN_NODE=https://50.28.86.131
```

---

## Troubleshooting

### "SSL: CERTIFICATE_VERIFY_FAILED"

**Solution:** Use `verify=False` (you've already trusted the self-signed cert):

```python
response = requests.get("https://50.28.86.131/health", verify=False)
```

### "ConnectionError: Cannot connect"

**Check:**
1. Your internet connection
2. Firewall rules (HTTPS port 443)
3. Node status: `curl -sk https://50.28.86.131/health`

### "404: Resource not found"

**Check:**
1. Wallet name spelling
2. Endpoint syntax
3. Node version compatibility

### "429: Too Many Requests"

**Solution:** Add delays between requests:

```python
import time
time.sleep(0.1)  # Wait 100ms between requests
```

---

## Next Steps

- Build a monitoring web dashboard with Flask
- Set up automated reward claims
- Create price tracking integrations
- Connect to exchange APIs for trading
- Develop mobile apps for monitoring

---

## Resources

- **GitHub:** https://github.com/Scottcjn/Rustchain
- **API Docs:** `/docs/api-reference.md`
- **Explorer:** https://50.28.86.131/explorer
- **Community:** https://github.com/Scottcjn/rustchain-bounties

---

**Version:** 1.0  
**Last Updated:** February 2026  
**License:** MIT
