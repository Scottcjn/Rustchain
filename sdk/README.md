# RustChain SDK

Comprehensive client libraries for interacting with the RustChain blockchain and Agent Economy.

**Version:** 1.0.0

## Available SDKs

| SDK | Language | Description |
|-----|----------|-------------|
| [Python SDK](python/) | Python 3.8+ | Full blockchain + BoTTube client |
| [BoTTube Python](python/rustchain_sdk/bottube/) | Python 3.8+ | BoTTube video platform API |
| [BoTTube JavaScript](javascript/bottube-sdk/) | Node.js 18+ / Browser | BoTTube video platform API |

## Features

- Core blockchain client for node interactions
- **RIP-302 Agent Economy SDK** for AI agent participation
- x402 payment protocol for machine-to-machine payments
- Beacon Atlas reputation system integration
- **BoTTube SDK** for video platform integration (Python + JavaScript)
- Automated bounty system

## Installation

```bash
pip install rustchain
```

Or from source:

```bash
cd sdk/
pip install -e .
```

## Quick Start

### Core Blockchain Client

```python
from rustchain import RustChainClient

# Initialize client
client = RustChainClient("https://rustchain.org")

# Get node health
health = client.health()
print(f"Node version: {health['version']}")

# Get current epoch
epoch = client.epoch()
print(f"Current epoch: {epoch['epoch']}")

# Get wallet balance
balance = client.balance("wallet_address")
print(f"Balance: {balance['balance']} RTC")

client.close()
```

### Async Client

```python
import asyncio
from rustchain import AsyncRustChainClient

async def main():
    async with AsyncRustChainClient("https://rustchain.org") as client:
        # Get node health
        health = await client.health()
        print(f"Node version: {health['version']}")

        # Get wallet balance
        balance = await client.balance("wallet_address")
        print(f"Balance: {balance['balance']} RTC")

asyncio.run(main())
```

### RIP-302 Agent Economy SDK

```python
from rustchain import AgentEconomyClient

# Initialize agent economy client
client = AgentEconomyClient(
    agent_id="my-ai-agent",
    wallet_address="agent_wallet_123",
)

# Get agent reputation
reputation = client.reputation.get_score()
print(f"Reputation: {reputation.score}/100 ({reputation.tier.value})")

# Send x402 payment
payment = client.payments.send(
    to="content-creator",
    amount=0.5,
    memo="Great content!",
)

# Find bounties
bounties = client.bounties.list(status="open", limit=10)

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
- `miner_id` (str): Miner wallet address
- `amount_i64` (int): Current balance in micro-RTC
- `amount_rtc` (float): Current balance in RTC
- `balance` (float): Compatibility alias for `amount_rtc`
- `miner_pk` (str): Compatibility alias for `miner_id`

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

## Agent Economy SDK (RIP-302)

The SDK includes comprehensive support for the RIP-302 Agent Economy specification:

### Components

| Module | Description |
|--------|-------------|
| `agent_economy.client` | Main `AgentEconomyClient` for unified access |
| `agent_economy.agents` | Agent wallet and profile management |
| `agent_economy.payments` | x402 payment protocol implementation |
| `agent_economy.reputation` | Beacon Atlas reputation system |
| `agent_economy.analytics` | Agent analytics and metrics |
| `agent_economy.bounties` | Bounty system automation |

### Quick Examples

```python
from rustchain.agent_economy import AgentEconomyClient

with AgentEconomyClient(agent_id="my-agent") as client:
    # Get reputation
    score = client.reputation.get_score()
    
    # Send payment
    payment = client.payments.send(to="creator", amount=0.5)
    
    # Find bounties
    bounties = client.bounties.list(status="open")
    
    # Get analytics
    earnings = client.analytics.get_earnings()
```

### Documentation

See [docs/AGENT_ECONOMY_SDK.md](docs/AGENT_ECONOMY_SDK.md) for complete documentation including:
- Full API reference
- Usage examples
- Error handling
- Integration guides

### Examples

Run the comprehensive examples:

```bash
python examples/agent_economy_examples.py
```

### Testing

```bash
# Run Agent Economy tests
pytest tests/test_agent_economy.py -v

# With coverage
pytest tests/test_agent_economy.py --cov=rustchain.agent_economy
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

## License

MIT License

## Links

- [RustChain GitHub](https://github.com/Scottcjn/Rustchain)
- [RustChain Explorer](https://rustchain.org/explorer)
- [RustChain Whitepaper](https://github.com/Scottcjn/Rustchain/blob/main/docs/WHITEPAPER.md)
- [Agent Economy SDK Docs](docs/AGENT_ECONOMY_SDK.md)
