# RustChain Python SDK Tutorial

## Introduction

This tutorial will guide you through using RustChain's API with Python. RustChain is a Proof-of-Antiquity blockchain that rewards vintage hardware. The native token is RTC (RustChain Token).

## Prerequisites

- Python 3.8 or higher
- `pip` package manager
- Basic knowledge of Python and REST APIs

## Installation

First, install the required Python packages:

```bash
pip install requests
```

If you want to work with dates and times, you can also install:

```bash
pip install python-dateutil
```

## Getting Started

### Base URL

All RustChain API endpoints use the base URL:
```python
BASE_URL = "https://50.28.86.131"
```

**Note**: The node uses a self-signed certificate. For production use, you should verify the certificate properly. For testing, you can disable SSL verification (not recommended for production).

### Basic API Client

Here's a simple Python client for RustChain:

```python
import requests
import json
from typing import Optional, Dict, Any

class RustChainClient:
    def __init__(self, base_url: str = "https://50.28.86.131", verify_ssl: bool = False):
        self.base_url = base_url.rstrip('/')
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self.session.request(
                method, 
                url, 
                verify=self.verify_ssl,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error calling {url}: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            raise
    
    def health(self) -> Dict[str, Any]:
        """Check node health and status."""
        return self._request('GET', '/health')
    
    def epoch(self) -> Dict[str, Any]:
        """Get current epoch details."""
        return self._request('GET', '/epoch')
    
    def block(self, slot: Optional[int] = None) -> Dict[str, Any]:
        """Get block information for a specific slot or the latest block."""
        endpoint = f"/block/{slot}" if slot else "/block"
        return self._request('GET', endpoint)
    
    def balance(self, address: str) -> Dict[str, Any]:
        """Get RTC balance for a wallet address."""
        return self._request('GET', f'/balance/{address}')
    
    def miners(self, limit: int = 100) -> Dict[str, Any]:
        """Get active miner information."""
        return self._request('GET', f'/miners?limit={limit}')
    
    def send_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a signed transaction to the network."""
        return self._request('POST', '/tx', json=transaction_data)

# Create a client instance
client = RustChainClient()
```

## Usage Examples

### 1. Checking Node Health

```python
# Create client
client = RustChainClient()

# Check health
health_data = client.health()
print(f"Node version: {health_data.get('version')}")
print(f"Uptime: {health_data.get('uptime_s')} seconds")
print(f"Database writable: {health_data.get('db_rw')}")
print(f"Healthy: {health_data.get('ok')}")
```

### 2. Getting Current Epoch Information

```python
epoch_data = client.epoch()
print(f"Current epoch: {epoch_data.get('epoch_number')}")
print(f"Slots per epoch: {epoch_data.get('slots_per_epoch')}")
print(f"Current slot: {epoch_data.get('current_slot')}")
print(f"Time remaining: {epoch_data.get('seconds_remaining')} seconds")
```

### 3. Checking Wallet Balance

```python
# Replace with your wallet address
wallet_address = "9YxD8s792H7cLqmA2F1fDmvJBkvbXh5SBYtDimvdu1eJ"
balance_data = client.balance(wallet_address)
print(f"Balance: {balance_data.get('balance', 0)} RTC")
print(f"Pending: {balance_data.get('pending', 0)} RTC")
```

### 4. Viewing Active Miners

```python
miners_data = client.miners(limit=10)
print(f"Total miners: {miners_data.get('total', 0)}")
print(f"Active miners: {miners_data.get('active', 0)}")

if 'miners' in miners_data:
    for miner in miners_data['miners'][:5]:  # Show first 5 miners
        print(f"  - {miner.get('address', 'Unknown')}: {miner.get('hashrate', 0)} H/s")
```

### 5. Getting Block Information

```python
# Get latest block
latest_block = client.block()
print(f"Latest block slot: {latest_block.get('slot')}")
print(f"Block hash: {latest_block.get('hash', '')[:16]}...")

# Get specific block (if you know the slot number)
# block_1000 = client.block(slot=1000)
```

## Advanced Usage

### Error Handling

```python
import requests
from typing import Dict, Any

def safe_api_call(client: RustChainClient, endpoint: str) -> Optional[Dict[str, Any]]:
    try:
        if endpoint == 'health':
            return client.health()
        elif endpoint == 'epoch':
            return client.epoch()
        elif endpoint == 'miners':
            return client.miners()
        else:
            print(f"Unknown endpoint: {endpoint}")
            return None
    except requests.exceptions.ConnectionError:
        print("Connection error: Cannot connect to RustChain node")
        return None
    except requests.exceptions.Timeout:
        print("Timeout error: Request took too long")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {e.response.status_code} - {e.response.reason}")
        return None
    except json.JSONDecodeError:
        print("Error: Response is not valid JSON")
        return None

# Example usage
client = RustChainClient()
data = safe_api_call(client, 'health')
if data:
    print(f"Node is healthy: {data.get('ok', False)}")
```

### Working with Transactions

Creating and sending transactions requires proper signing. Here's an example structure:

```python
# Transaction structure (needs to be signed with private key)
transaction_example = {
    "sender": "9YxD8s792H7cLqmA2F1fDmvJBkvbXh5SBYtDimvdu1eJ",
    "receiver": "ANOTHER_WALLET_ADDRESS",
    "amount": 100,  # RTC amount
    "nonce": 1,  # Transaction nonce (should be sequential)
    "signature": "SIGNATURE_HERE",  # Ed25519 signature
    "timestamp": 1672531200  # Unix timestamp
}

# Note: In production, you should use a proper wallet library to sign transactions
# This example shows the structure only
```

### Rate Limiting and Best Practices

```python
import time

class RateLimitedRustChainClient(RustChainClient):
    def __init__(self, *args, requests_per_minute: int = 60, **kwargs):
        super().__init__(*args, **kwargs)
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute
        self.last_request_time = 0
        
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        # Implement rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            time.sleep(sleep_time)
        
        result = super()._request(method, endpoint, **kwargs)
        self.last_request_time = time.time()
        return result

# Use rate-limited client for frequent requests
rate_limited_client = RateLimitedRustChainClient(requests_per_minute=30)
```

## Complete Example Script

Here's a complete script that demonstrates multiple API calls:

```python
#!/usr/bin/env python3
"""
RustChain API Example Script
Demonstrates various API calls and error handling
"""

import sys
from typing import Dict, Any

def main():
    # Import the client class (assuming it's in the same directory or installed)
    try:
        client = RustChainClient()
    except Exception as e:
        print(f"Failed to initialize client: {e}")
        sys.exit(1)
    
    print("=== RustChain API Demo ===\n")
    
    # 1. Check node health
    print("1. Checking node health...")
    try:
        health = client.health()
        print(f"   ✓ Node version: {health.get('version')}")
        print(f"   ✓ Uptime: {health.get('uptime_s')} seconds")
        print(f"   ✓ Healthy: {health.get('ok', False)}\n")
    except Exception as e:
        print(f"   ✗ Health check failed: {e}\n")
    
    # 2. Get epoch info
    print("2. Getting epoch information...")
    try:
        epoch = client.epoch()
        print(f"   ✓ Current epoch: {epoch.get('epoch_number')}")
        print(f"   ✓ Current slot: {epoch.get('current_slot')}")
        print(f"   ✓ Slots remaining: {epoch.get('slots_remaining')}\n")
    except Exception as e:
        print(f"   ✗ Epoch info failed: {e}\n")
    
    # 3. Get miner info
    print("3. Checking miner activity...")
    try:
        miners = client.miners(limit=5)
        total = miners.get('total', 0)
        active = miners.get('active', 0)
        print(f"   ✓ Total miners: {total}")
        print(f"   ✓ Active miners: {active}")
        
        if 'miners' in miners and miners['miners']:
            print("   ✓ Top miners:")
            for i, miner in enumerate(miners['miners'][:3], 1):
                addr = miner.get('address', 'Unknown')
                hashrate = miner.get('hashrate', 0)
                print(f"     {i}. {addr[:8]}...: {hashrate} H/s")
        print()
    except Exception as e:
        print(f"   ✗ Miner info failed: {e}\n")
    
    print("=== Demo Complete ===")

if __name__ == "__main__":
    main()
```

## Next Steps

1. **Explore More Endpoints**: Check the full API documentation for additional endpoints like `/rewards`, `/validators`, and `/nfts`.

2. **Implement Transaction Signing**: Use the `ed25519` library to properly sign transactions before sending.

3. **Build a Wallet Interface**: Create a simple command-line wallet for checking balances and sending transactions.

4. **Monitor Node Health**: Build a monitoring script that alerts you if the node goes down.

5. **Contribute to the Project**: Consider contributing improvements to the RustChain ecosystem.

## Troubleshooting

### Common Issues

1. **SSL Certificate Errors**: If you get SSL errors, you can temporarily disable verification by setting `verify_ssl=False` when creating the client. For production, obtain the proper certificate.

2. **Connection Refused**: Make sure the RustChain node is running and accessible at the base URL.

3. **Rate Limiting**: If you get rate-limited, reduce the frequency of your requests or use the rate-limited client example.

4. **Invalid JSON Response**: Some endpoints might return non-JSON responses for errors. Check the response content before parsing.

### Getting Help

- Check the official RustChain documentation
- Join the RustChain community on Discord
- Report issues on the GitHub repository

## Conclusion

This tutorial provides a foundation for interacting with RustChain using Python. With the basic client and examples provided, you can start building applications, monitoring tools, or automated systems that interact with the RustChain blockchain.

Remember to follow best practices for security, especially when handling private keys and signing transactions.