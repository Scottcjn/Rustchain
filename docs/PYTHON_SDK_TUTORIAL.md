# RustChain Python SDK Tutorial

Learn how to interact with RustChain programmatically using Python.

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [Wallet Operations](#wallet-operations)
- [Miner Operations](#miner-operations)
- [Attestation](#attestation)
- [Transactions](#transactions)
- [Advanced Usage](#advanced-usage)
- [Examples](#examples)

---

## Installation

### Prerequisites

- Python 3.6 or later
- pip package manager

### Install Dependencies

```bash
pip install requests urllib3 pynacl
```

**Package purposes**:
- `requests` - HTTP client for API calls
- `urllib3` - SSL/TLS handling
- `pynacl` - Ed25519 cryptographic signatures

### Clone RustChain Repository

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
```

---

## Quick Start

### Basic Balance Check

```python
import requests
import urllib3

# Disable SSL warnings for self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NODE_URL = "https://50.28.86.131"

def check_balance(miner_id):
    """Check RTC balance for a wallet."""
    response = requests.get(
        f"{NODE_URL}/wallet/balance",
        params={"miner_id": miner_id},
        verify=False  # Self-signed cert
    )
    return response.json()

# Example usage
balance = check_balance("powerbook_g4_RTC")
print(f"Balance: {balance['balance_rtc']} RTC")
```

**Output**:
```
Balance: 12.456789 RTC
```

---

## Core Concepts

### RustChain Client Class

Create a reusable client for all API operations:

```python
import requests
import urllib3
from typing import Dict, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class RustChainClient:
    """Client for interacting with RustChain nodes."""
    
    def __init__(self, node_url: str = "https://50.28.86.131", verify_ssl: bool = False):
        self.node_url = node_url.rstrip('/')
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
    
    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make GET request to node."""
        url = f"{self.node_url}{endpoint}"
        response = self.session.get(url, params=params, verify=self.verify_ssl)
        response.raise_for_status()
        return response.json()
    
    def _post(self, endpoint: str, data: Dict) -> Dict:
        """Make POST request to node."""
        url = f"{self.node_url}{endpoint}"
        response = self.session.post(url, json=data, verify=self.verify_ssl)
        response.raise_for_status()
        return response.json()
    
    def health(self) -> Dict:
        """Check node health."""
        return self._get("/health")
    
    def stats(self) -> Dict:
        """Get chain statistics."""
        return self._get("/api/stats")
    
    def epoch(self) -> Dict:
        """Get current epoch info."""
        return self._get("/epoch")

# Example usage
client = RustChainClient()
health = client.health()
print(f"Node version: {health['version']}")
print(f"Uptime: {health['uptime_s']} seconds")
```

---

## Wallet Operations

### Check Balance

```python
class RustChainClient:
    # ... (previous methods)
    
    def get_balance(self, miner_id: str) -> Dict:
        """Get wallet balance.
        
        Args:
            miner_id: Wallet identifier (e.g., "powerbook_g4_RTC")
        
        Returns:
            {
                "miner_id": str,
                "balance_rtc": float,
                "balance_urtc": int,
                "last_updated": str
            }
        """
        return self._get("/wallet/balance", params={"miner_id": miner_id})

# Example
client = RustChainClient()
balance = client.get_balance("powerbook_g4_RTC")
print(f"Balance: {balance['balance_rtc']} RTC")
print(f"Balance (micro-RTC): {balance['balance_urtc']} uRTC")
```

### Create Wallet

```python
from nacl.signing import SigningKey
import hashlib

def create_wallet(name: str) -> Dict:
    """Create a new wallet with Ed25519 keypair.
    
    Args:
        name: Wallet name (e.g., "my-miner")
    
    Returns:
        {
            "miner_id": str,
            "private_key": bytes,
            "public_key": bytes,
            "seed": bytes
        }
    """
    # Generate Ed25519 keypair
    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key
    
    # Create miner ID from public key
    pubkey_hash = hashlib.sha256(verify_key.encode()).hexdigest()[:40]
    miner_id = f"{name}_{pubkey_hash[:8]}_RTC"
    
    return {
        "miner_id": miner_id,
        "private_key": signing_key.encode(),
        "public_key": verify_key.encode(),
        "seed": signing_key.encode()  # Store securely!
    }

# Example
wallet = create_wallet("my-miner")
print(f"Wallet ID: {wallet['miner_id']}")
print(f"Public Key: {wallet['public_key'].hex()}")
print(f"⚠️  Save your seed securely!")
```

### Save/Load Wallet

```python
import json
from pathlib import Path
import base64

def save_wallet(wallet: Dict, password: str, filepath: str):
    """Save wallet to encrypted file.
    
    Args:
        wallet: Wallet dict from create_wallet()
        password: Encryption password
        filepath: Path to save wallet file
    """
    from nacl.secret import SecretBox
    from nacl.utils import random
    from nacl.hash import blake2b
    
    # Derive key from password
    key = blake2b(password.encode(), digest_size=32, encoder=base64.b64encode)
    box = SecretBox(base64.b64decode(key))
    
    # Encrypt wallet data
    wallet_json = json.dumps({
        "miner_id": wallet["miner_id"],
        "private_key": base64.b64encode(wallet["private_key"]).decode(),
        "public_key": base64.b64encode(wallet["public_key"]).decode()
    })
    
    encrypted = box.encrypt(wallet_json.encode())
    
    # Save to file
    Path(filepath).write_bytes(encrypted)
    print(f"✅ Wallet saved to {filepath}")

def load_wallet(filepath: str, password: str) -> Dict:
    """Load wallet from encrypted file.
    
    Args:
        filepath: Path to wallet file
        password: Decryption password
    
    Returns:
        Wallet dict
    """
    from nacl.secret import SecretBox
    from nacl.hash import blake2b
    
    # Derive key from password
    key = blake2b(password.encode(), digest_size=32, encoder=base64.b64encode)
    box = SecretBox(base64.b64decode(key))
    
    # Load and decrypt
    encrypted = Path(filepath).read_bytes()
    decrypted = box.decrypt(encrypted)
    
    wallet_data = json.loads(decrypted)
    
    return {
        "miner_id": wallet_data["miner_id"],
        "private_key": base64.b64decode(wallet_data["private_key"]),
        "public_key": base64.b64decode(wallet_data["public_key"])
    }

# Example
wallet = create_wallet("my-miner")
save_wallet(wallet, "my-secure-password", "~/.rustchain/my-wallet.enc")

# Later...
loaded_wallet = load_wallet("~/.rustchain/my-wallet.enc", "my-secure-password")
print(f"Loaded wallet: {loaded_wallet['miner_id']}")
```

---

## Miner Operations

### List All Miners

```python
class RustChainClient:
    # ... (previous methods)
    
    def list_miners(self, limit: int = 100, offset: int = 0, sort: str = "last_seen") -> Dict:
        """List active miners.
        
        Args:
            limit: Max results (default: 100)
            offset: Pagination offset (default: 0)
            sort: Sort by: multiplier, last_seen, balance (default: last_seen)
        
        Returns:
            {
                "miners": [
                    {
                        "miner_id": str,
                        "hardware": {...},
                        "multiplier": float,
                        "balance_rtc": float,
                        ...
                    }
                ],
                "total": int,
                "limit": int,
                "offset": int
            }
        """
        return self._get("/api/miners", params={
            "limit": limit,
            "offset": offset,
            "sort": sort
        })

# Example: Get top 10 miners by multiplier
client = RustChainClient()
miners = client.list_miners(limit=10, sort="multiplier")

print(f"Top 10 miners by multiplier:")
for miner in miners["miners"]:
    print(f"  {miner['miner_id']}: {miner['multiplier']}x ({miner['hardware']['cpu_model']})")
```

**Output**:
```
Top 10 miners by multiplier:
  powerbook_g4_1.5ghz_RTC: 2.5x (PowerPC G4 1.5GHz)
  powermac_g5_dual_RTC: 2.0x (PowerPC G5 Dual 2.0GHz)
  pentium4_northwood_RTC: 1.5x (Intel Pentium 4 2.4GHz)
  ...
```

### Get Miner Details

```python
class RustChainClient:
    # ... (previous methods)
    
    def get_miner(self, miner_id: str) -> Dict:
        """Get detailed miner information.
        
        Args:
            miner_id: Miner identifier
        
        Returns:
            Detailed miner info including hardware fingerprint
        """
        return self._get(f"/api/miner/{miner_id}")

# Example
client = RustChainClient()
miner = client.get_miner("powerbook_g4_RTC")

print(f"Miner: {miner['miner_id']}")
print(f"CPU: {miner['hardware']['cpu_model']}")
print(f"Architecture: {miner['hardware']['architecture']}")
print(f"Release Year: {miner['hardware']['release_year']}")
print(f"Tier: {miner['hardware']['tier']}")
print(f"Multiplier: {miner['multiplier']}x")
print(f"Balance: {miner['balance_rtc']} RTC")
print(f"Total Earned: {miner['total_earned_rtc']} RTC")
print(f"Epochs Enrolled: {miner['enrolled_epochs']}")
```

---

## Attestation

### Submit Hardware Attestation

```python
import time
import platform
import hashlib
from nacl.signing import SigningKey
import base64

class RustChainClient:
    # ... (previous methods)
    
    def submit_attestation(self, miner_id: str, hardware: Dict, 
                          fingerprint: Dict, private_key: bytes) -> Dict:
        """Submit hardware attestation for epoch enrollment.
        
        Args:
            miner_id: Wallet identifier
            hardware: Hardware info dict
            fingerprint: 6-point fingerprint dict
            private_key: Ed25519 private key for signing
        
        Returns:
            Attestation result
        """
        # Create attestation payload
        timestamp = int(time.time())
        payload = {
            "miner_id": miner_id,
            "timestamp": timestamp,
            "hardware": hardware,
            "fingerprint": fingerprint
        }
        
        # Sign payload
        signing_key = SigningKey(private_key)
        message = json.dumps(payload, sort_keys=True).encode()
        signature = signing_key.sign(message).signature
        
        payload["signature"] = base64.b64encode(signature).decode()
        
        return self._post("/attest/submit", payload)

# Example: Submit attestation
def get_hardware_info():
    """Collect hardware information."""
    return {
        "cpu_model": platform.processor(),
        "architecture": platform.machine(),
        "release_year": 2024,  # Determine from CPU model
        "serial": "HARDWARE_SERIAL_HERE"
    }

def get_fingerprint():
    """Collect 6-point hardware fingerprint."""
    # In production, use actual fingerprint_checks.py module
    return {
        "clock_skew": {"drift_ppm": 12.5, "jitter_ns": 847},
        "cache_timing": {"l1_latency_ns": 4, "l2_latency_ns": 12},
        "simd_identity": {"instruction_set": "SSE4.2", "pipeline_bias": 0.68},
        "thermal_entropy": {"idle_temp": 38.2, "load_temp": 67.8, "variance": 4.2},
        "instruction_jitter": {"mean_ns": 2.3, "stddev_ns": 0.8},
        "behavioral_heuristics": {
            "cpuid_clean": True,
            "mac_oui_valid": True,
            "no_hypervisor": True
        }
    }

# Submit attestation
client = RustChainClient()
wallet = load_wallet("~/.rustchain/my-wallet.enc", "password")

result = client.submit_attestation(
    miner_id=wallet["miner_id"],
    hardware=get_hardware_info(),
    fingerprint=get_fingerprint(),
    private_key=wallet["private_key"]
)

if result["ok"]:
    print(f"✅ Enrolled in epoch {result['epoch']}")
    print(f"Multiplier: {result['multiplier']}x")
    print(f"Fingerprint valid: {result['fingerprint_valid']}")
else:
    print(f"❌ Attestation failed: {result.get('error')}")
```

---

## Transactions

### Send RTC

```python
import time
from nacl.signing import SigningKey
import base64

class RustChainClient:
    # ... (previous methods)
    
    def send_rtc(self, from_wallet: Dict, to_address: str, amount_rtc: float) -> Dict:
        """Send RTC to another wallet.
        
        Args:
            from_wallet: Wallet dict with private_key
            to_address: Recipient wallet ID
            amount_rtc: Amount to send (in RTC)
        
        Returns:
            Transaction result
        """
        # Create transaction
        nonce = int(time.time())
        message = f"{from_wallet['miner_id']}{to_address}{amount_rtc}{nonce}"
        
        # Sign transaction
        signing_key = SigningKey(from_wallet["private_key"])
        signature = signing_key.sign(message.encode()).signature
        
        # Submit transaction
        payload = {
            "from_address": from_wallet["miner_id"],
            "to_address": to_address,
            "amount_rtc": amount_rtc,
            "nonce": nonce,
            "signature": base64.b64encode(signature).decode(),
            "public_key": base64.b64encode(from_wallet["public_key"]).decode()
        }
        
        return self._post("/wallet/transfer/signed", payload)

# Example: Send 5 RTC
client = RustChainClient()
wallet = load_wallet("~/.rustchain/my-wallet.enc", "password")

result = client.send_rtc(
    from_wallet=wallet,
    to_address="recipient_wallet_RTC",
    amount_rtc=5.0
)

if result["ok"]:
    print(f"✅ Transaction successful!")
    print(f"TX Hash: {result['tx_hash']}")
    print(f"New Balance: {result['new_balance_rtc']} RTC")
else:
    print(f"❌ Transaction failed: {result.get('error')}")
```

### Transaction History

```python
class RustChainClient:
    # ... (previous methods)
    
    def get_transactions(self, miner_id: str, limit: int = 50) -> Dict:
        """Get transaction history for a wallet.
        
        Args:
            miner_id: Wallet identifier
            limit: Max transactions to return
        
        Returns:
            List of transactions
        """
        return self._get(f"/wallet/transactions/{miner_id}", params={"limit": limit})

# Example
client = RustChainClient()
txs = client.get_transactions("powerbook_g4_RTC", limit=10)

print(f"Recent transactions:")
for tx in txs["transactions"]:
    print(f"  {tx['timestamp']}: {tx['type']} {tx['amount_rtc']} RTC")
    if tx['type'] == 'send':
        print(f"    To: {tx['to_address']}")
    elif tx['type'] == 'receive':
        print(f"    From: {tx['from_address']}")
```

---

## Advanced Usage

### Monitoring Miner Performance

```python
import time

def monitor_miner(client: RustChainClient, miner_id: str, interval: int = 60):
    """Monitor miner performance over time.
    
    Args:
        client: RustChainClient instance
        miner_id: Miner to monitor
        interval: Check interval in seconds
    """
    print(f"Monitoring {miner_id}...")
    
    last_balance = 0
    
    while True:
        try:
            # Get current state
            miner = client.get_miner(miner_id)
            balance = miner["balance_rtc"]
            
            # Calculate earnings
            if last_balance > 0:
                earned = balance - last_balance
                if earned > 0:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                          f"Earned {earned:.6f} RTC (Balance: {balance:.6f} RTC)")
            
            last_balance = balance
            
            # Display status
            print(f"  Multiplier: {miner['multiplier']}x")
            print(f"  Enrolled Epochs: {miner['enrolled_epochs']}")
            print(f"  Last Attestation: {miner['last_attestation']}")
            
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(interval)

# Example
client = RustChainClient()
monitor_miner(client, "powerbook_g4_RTC", interval=300)  # Check every 5 minutes
```

### Batch Operations

```python
def check_multiple_balances(client: RustChainClient, miner_ids: list) -> Dict:
    """Check balances for multiple wallets.
    
    Args:
        client: RustChainClient instance
        miner_ids: List of wallet IDs
    
    Returns:
        Dict mapping miner_id to balance
    """
    balances = {}
    
    for miner_id in miner_ids:
        try:
            result = client.get_balance(miner_id)
            balances[miner_id] = result["balance_rtc"]
        except Exception as e:
            balances[miner_id] = f"Error: {e}"
    
    return balances

# Example
client = RustChainClient()
wallets = ["powerbook_g4_RTC", "ryzen_5_RTC", "pentium4_RTC"]
balances = check_multiple_balances(client, wallets)

for wallet, balance in balances.items():
    print(f"{wallet}: {balance} RTC")
```

### Error Handling

```python
from requests.exceptions import RequestException, HTTPError

def safe_api_call(func, *args, **kwargs):
    """Wrapper for safe API calls with error handling."""
    try:
        return func(*args, **kwargs)
    except HTTPError as e:
        if e.response.status_code == 404:
            return {"error": "NOT_FOUND", "message": "Resource not found"}
        elif e.response.status_code == 401:
            return {"error": "UNAUTHORIZED", "message": "Invalid signature"}
        elif e.response.status_code == 429:
            return {"error": "RATE_LIMITED", "message": "Too many requests"}
        else:
            return {"error": "HTTP_ERROR", "message": str(e)}
    except RequestException as e:
        return {"error": "CONNECTION_ERROR", "message": str(e)}
    except Exception as e:
        return {"error": "UNKNOWN_ERROR", "message": str(e)}

# Example
client = RustChainClient()
result = safe_api_call(client.get_balance, "nonexistent_wallet_RTC")

if "error" in result:
    print(f"Error: {result['error']} - {result['message']}")
else:
    print(f"Balance: {result['balance_rtc']} RTC")
```

---

## Examples

### Complete Miner Script

```python
#!/usr/bin/env python3
"""
Simple RustChain miner using the SDK.
"""
import time
import sys
from rustchain_client import RustChainClient, create_wallet, save_wallet, load_wallet

def main():
    # Initialize client
    client = RustChainClient()
    
    # Load or create wallet
    wallet_path = "~/.rustchain/my-wallet.enc"
    password = "my-secure-password"
    
    try:
        wallet = load_wallet(wallet_path, password)
        print(f"Loaded wallet: {wallet['miner_id']}")
    except FileNotFoundError:
        print("Creating new wallet...")
        wallet = create_wallet("my-miner")
        save_wallet(wallet, password, wallet_path)
        print(f"Created wallet: {wallet['miner_id']}")
    
    # Check initial balance
    balance = client.get_balance(wallet["miner_id"])
    print(f"Current balance: {balance['balance_rtc']} RTC")
    
    # Mining loop
    print("Starting mining loop...")
    while True:
        try:
            # Submit attestation every epoch
            result = client.submit_attestation(
                miner_id=wallet["miner_id"],
                hardware=get_hardware_info(),
                fingerprint=get_fingerprint(),
                private_key=wallet["private_key"]
            )
            
            if result["ok"]:
                print(f"✅ Enrolled in epoch {result['epoch']} with {result['multiplier']}x multiplier")
            else:
                print(f"❌ Attestation failed: {result.get('error')}")
            
            # Wait for next epoch (24 hours)
            time.sleep(86400)
            
        except KeyboardInterrupt:
            print("\nStopping miner...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)  # Wait 1 minute before retry

if __name__ == "__main__":
    main()
```

### Wallet Manager

```python
#!/usr/bin/env python3
"""
Simple wallet manager for RustChain.
"""
from rustchain_client import RustChainClient, load_wallet

def main():
    client = RustChainClient()
    wallet = load_wallet("~/.rustchain/my-wallet.enc", "password")
    
    while True:
        print("\n=== RustChain Wallet ===")
        print("1. Check Balance")
        print("2. Send RTC")
        print("3. View Transactions")
        print("4. Exit")
        
        choice = input("\nChoice: ")
        
        if choice == "1":
            balance = client.get_balance(wallet["miner_id"])
            print(f"\nBalance: {balance['balance_rtc']} RTC")
        
        elif choice == "2":
            to_address = input("Recipient address: ")
            amount = float(input("Amount (RTC): "))
            
            result = client.send_rtc(wallet, to_address, amount)
            
            if result["ok"]:
                print(f"✅ Sent {amount} RTC to {to_address}")
                print(f"New balance: {result['new_balance_rtc']} RTC")
            else:
                print(f"❌ Transfer failed: {result.get('error')}")
        
        elif choice == "3":
            txs = client.get_transactions(wallet["miner_id"])
            print(f"\nRecent transactions:")
            for tx in txs["transactions"][:10]:
                print(f"  {tx['timestamp']}: {tx['type']} {tx['amount_rtc']} RTC")
        
        elif choice == "4":
            break

if __name__ == "__main__":
    main()
```

---

## Next Steps

- **Read API Reference**: `docs/API_REFERENCE.md`
- **Set up miner**: `docs/MINER_SETUP_GUIDE.md`
- **Explore protocol**: `docs/PROTOCOL.md`
- **Join community**: [GitHub Discussions](https://github.com/Scottcjn/Rustchain/discussions)

---

**Last Updated**: February 9, 2026  
**SDK Version**: 1.0
