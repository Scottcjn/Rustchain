# RustChain Python SDK

A pip-installable Python SDK for interacting with the RustChain blockchain network.

## What is RustChain?

RustChain is a Proof-of-Antiquity blockchain that rewards vintage hardware (PowerPC G4/G5, 68K Macs, SPARC, etc.) with higher mining multipliers than modern machines.

## Installation

### From GitHub (Recommended for development)
```bash
pip install git+https://github.com/sososonia-cyber/RustChain.git
```

### From PyPI (coming soon)
```bash
pip install rustchain-sdk
```

### For async support
```bash
pip install rustchain-sdk[async]
```

## Quick Start

```python
from rustchain_sdk import RustChainClient

# Create client (self-signed SSL certs handled automatically)
client = RustChainClient("https://50.28.86.131")

# Check node health
health = client.health()
print(f"Node OK: {health['ok']}")
print(f"Version: {health['version']}")

# Get active miners
miners = client.get_miners()
print(f"Active miners: {len(miners)}")

# Check epoch info
epoch = client.get_epoch()
print(f"Current epoch: {epoch['epoch']}")

# Check lottery eligibility
eligibility = client.check_eligibility("my-wallet")
print(f"Eligible: {eligibility['eligible']}")
```

## API Reference

### Client Configuration

```python
# Default configuration
client = RustChainClient()

# Custom configuration
client = RustChainClient(
    base_url="https://50.28.86.131",  # Node URL
    verify_ssl=False,    # Set True to verify SSL (for production)
    timeout=30,         # Request timeout in seconds
    retry_count=3,     # Number of retries on failure
    retry_delay=1.0    # Delay between retries
)
```

### Available Methods

| Method | Description |
|--------|-------------|
| `client.health()` | Get node health status |
| `client.get_miners()` | Get list of active miners |
| `client.get_balance(miner_id)` | Get wallet balance |
| `client.get_epoch()` | Get current epoch info |
| `client.check_eligibility(miner_id)` | Check lottery eligibility |
| `client.submit_attestation(payload)` | Submit attestation |
| `client.transfer(from, to, amount, private_key)` | Transfer RTC |

### Async Support

```python
import asyncio
from rustchain_sdk import RustChainClient

async def main():
    client = RustChainClient()
    
    # Use async methods
    health = await client.async_health()
    miners = await client.async_get_miners()
    
    print(f"Miners: {len(miners)}")

asyncio.run(main())
```

## Command Line Interface

```bash
# Check node health
rustchain-cli health

# List miners
rustchain-cli miners

# Check balance
rustchain-cli balance my-wallet

# Check epoch
rustchain-cli epoch
```

## Requirements

- Python 3.8+
- requests >= 2.28.0
- aiohttp >= 3.8.0 (optional, for async support)

## License

MIT License

## Author

Built by Atlas (AI Agent) for RustChain Bounty #36
