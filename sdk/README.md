# RustChain Python SDK

A Python client library for interacting with the RustChain blockchain.

## Installation

```bash
pip install rustchain-sdk
```

## Quick Start

```python
from rustchain import RustChainClient

# Initialize client
client = RustChainClient("https://rustchain.org", verify_ssl=False)

# Get node health
health = client.health()
print(f"Node version: {health['version']}")
print(f"Uptime: {health['uptime_s']}s")

# Get current epoch
epoch = client.epoch()
print(f"Current epoch: {epoch['epoch']}")
print(f"Slot: {epoch['slot']}")

# Get all miners
miners = client.miners()
print(f"Total miners: {len(miners)}")

# Get wallet balance
balance = client.balance("wallet_address")
print(f"Balance: {balance['balance']} RTC")

# Close client
client.close()
```

## API Reference

### RustChainClient

Main client for interacting with RustChain node API.

#### Constructor

```python
RustChainClient(
    base_url: str,
    verify_ssl: bool = True,
    timeout: int = 30
)
```

**Parameters:**
- `base_url`: Base URL of RustChain node (e.g., "https://rustchain.org")
- `verify_ssl`: Whether to verify SSL certificates (default: True)
- `timeout`: Request timeout in seconds (default: 30)

#### Methods

##### health()

Get node health status.

```python
health = client.health()
```

**Returns:**
- `ok` (bool): Node is healthy
- `uptime_s` (int): Uptime in seconds
- `version` (str): Node version
- `db_rw` (bool): Database read/write status

##### epoch()

Get current epoch information.

```python
epoch = client.epoch()
```

**Returns:**
- `epoch` (int): Current epoch number
- `slot` (int): Current slot
- `blocks_per_epoch` (int): Blocks per epoch
- `enrolled_miners` (int): Number of enrolled miners
- `epoch_pot` (float): Current epoch PoT

##### miners()

Get list of all miners.

```python
miners = client.miners()
```

**Returns:** List of miner dicts with:
- `miner` (str): Miner wallet address
- `antiquity_multiplier` (float): Hardware antiquity multiplier
- `hardware_type` (str): Hardware type description
- `device_arch` (str): Device architecture
- `last_attest` (int): Last attestation timestamp

##### balance(miner_id)

Get wallet balance for a miner.

```python
balance = client.balance("wallet_address")
```

**Parameters:**
- `miner_id`: Miner wallet address

**Returns:**
- `miner_pk` (str): Wallet address
- `balance` (float): Current balance in RTC
- `epoch_rewards` (float): Rewards in current epoch
- `total_earned` (float): Total RTC earned

##### transfer(from_addr, to_addr, amount, signature=None, fee=0.01)

Transfer RTC from one wallet to another.

```python
result = client.transfer(
    from_addr="wallet1",
    to_addr="wallet2",
    amount=10.0
)
```

**Parameters:**
- `from_addr`: Source wallet address
- `to_addr`: Destination wallet address
- `amount`: Amount to transfer (in RTC)
- `signature`: Transaction signature (if signed offline)
- `fee`: Transfer fee (default: 0.01 RTC)

**Returns:**
- `success` (bool): Transfer succeeded
- `tx_id` (str): Transaction ID
- `fee` (float): Fee deducted
- `new_balance` (float): New balance after transfer

##### transfer_history(miner_id, limit=50)

Get transfer history for a wallet.

```python
history = client.transfer_history("wallet_address", limit=10)
```

**Parameters:**
- `miner_id`: Wallet address
- `limit`: Maximum number of records (default: 50)

**Returns:** List of transfer dicts with:
- `tx_id` (str): Transaction ID
- `from_addr` (str): Source address
- `to_addr` (str): Destination address
- `amount` (float): Amount transferred
- `timestamp` (int): Unix timestamp
- `status` (str): Transaction status

##### submit_attestation(payload)

Submit hardware attestation to the node.

```python
attestation = {
    "miner_id": "wallet_address",
    "device": {"arch": "G4", "cores": 1},
    "fingerprint": {"checks": {...}},
    "nonce": "unique_nonce"
}

result = client.submit_attestation(attestation)
```

**Parameters:**
- `payload`: Attestation payload containing:
    - `miner_id` (str): Miner wallet address
    - `device` (dict): Device information
    - `fingerprint` (dict): Fingerprint check results
    - `nonce` (str): Unique nonce for replay protection

**Returns:**
- `success` (bool): Attestation accepted
- `epoch` (int): Epoch number
- `slot` (int): Slot number
- `multiplier` (float): Applied antiquity multiplier

##### enroll_miner(miner_id)

Enroll a new miner in the network.

```python
result = client.enroll_miner("wallet_address")
```

**Parameters:**
- `miner_id`: Wallet address to enroll

**Returns:**
- `success` (bool): Enrollment succeeded
- `miner_id` (str): Enrolled wallet address
- `enrolled_at` (int): Unix timestamp

## Context Manager

The client supports context manager for automatic cleanup:

```python
with RustChainClient("https://rustchain.org") as client:
    health = client.health()
    print(health)
# Session automatically closed
```

## Error Handling

The SDK defines custom exceptions:

```python
from rustchain import RustChainClient
from rustchain.exceptions import (
    ConnectionError,
    ValidationError,
    APIError,
    AttestationError,
    TransferError,
)

client = RustChainClient("https://rustchain.org")

try:
    balance = client.balance("wallet_address")
    print(f"Balance: {balance['balance']} RTC")
except ConnectionError:
    print("Failed to connect to node")
except ValidationError as e:
    print(f"Invalid input: {e}")
except APIError as e:
    print(f"API error: {e}")
finally:
    client.close()
```

## Testing

Run tests:

```bash
# Unit tests (with mocks)
pytest tests/ -m "not integration"

# Integration tests (against live node)
pytest tests/ -m integration

# All tests with coverage
pytest tests/ --cov=rustchain --cov-report=html
```

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run type checking
mypy rustchain/

# Format code
black rustchain/
```

## Requirements

- Python 3.8+
- requests >= 2.28.0

## License

MIT License

## Links

- [RustChain GitHub](https://github.com/Scottcjn/Rustchain)
- [RustChain Explorer](https://rustchain.org/explorer)
- [RustChain Whitepaper](https://github.com/Scottcjn/Rustchain/blob/main/docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)
