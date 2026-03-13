# RustChain Python SDK (rustchain-py)

[![PyPI version](https://badge.fury.io/py/rustchain-py.svg)](https://badge.fury.io/py/rustchain-py)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

Official Python SDK for the RustChain blockchain. Query wallets, send transactions, and interact with the RustChain network.

## Features

- ✅ **Wallet Queries** - Check balances, verify wallet existence, view pending transfers
- ✅ **Transaction Sending** - Transfer RTC between wallets (requires admin key)
- ✅ **Network Information** - Get epoch info, active miners, holder statistics
- ✅ **Lottery Eligibility** - Check wallet eligibility for epoch rewards
- ✅ **Health Monitoring** - Node health checks and status information
- ✅ **Type Hints** - Full type annotations for better IDE support
- ✅ **Error Handling** - Comprehensive exception hierarchy

## Installation

### From PyPI (recommended)

```bash
pip install rustchain-py
```

### From source

```bash
git clone https://github.com/Scottcjn/rustchain-py.git
cd rustchain-py
pip install -e .
```

### Development installation

```bash
pip install -e ".[dev]"
```

## Quick Start

```python
from rustchain import RustChainClient

# Initialize client
client = RustChainClient(node_url="https://50.28.86.131")

# Check wallet balance
balance = client.get_balance("my-wallet")
print(f"Balance: {balance.get('balance_rtc', 0)} RTC")

# Check if wallet exists
exists = client.check_wallet_exists("my-wallet")
print(f"Wallet exists: {exists}")

# Get epoch information
epoch = client.get_epoch_info()
print(f"Current epoch: {epoch.get('epoch')}")
```

## Advanced Usage

### Wallet Operations

```python
from rustchain import Wallet

client = RustChainClient()
wallet = Wallet(client)

# Validate wallet name
is_valid, msg = wallet.validate_name("my-wallet")
if is_valid:
    print("✓ Valid wallet name")
else:
    print(f"✗ {msg}")

# Get wallet balance
balance = wallet.get_balance("my-wallet")
print(f"Balance: {balance} RTC")

# Check pending transfers
pending = wallet.get_pending("my-wallet")
for transfer in pending:
    print(f"Pending: {transfer.get('amount_rtc')} RTC")

# Get registration guide
guide = wallet.registration_guide("new-wallet")
print(guide)
```

### Transaction Operations

```python
from rustchain import Transaction

# Initialize with admin key
client = RustChainClient(admin_key="your-admin-key")
tx = Transaction(client)

# Validate transaction
is_valid, msg = tx.validate_transfer("wallet1", "wallet2", 10.0)
if is_valid:
    # Send transaction
    result = tx.send("wallet1", "wallet2", 10.0)
    print(f"Transaction ID: {result.get('pending_id')}")
else:
    print(f"Invalid transaction: {msg}")
```

### Network Information

```python
from rustchain import RustChainClient

client = RustChainClient()

# Get active miners
miners = client.get_active_miners()
print(f"Active miners: {len(miners)}")

# Get all holders (admin only)
client_admin = RustChainClient(admin_key="your-admin-key")
holders = client_admin.get_all_holders()
for holder in holders[:10]:
    print(f"{holder['miner_id']}: {holder['amount_rtc']} RTC")

# Get holder statistics
stats = client_admin.get_holder_stats()
print(f"Total wallets: {stats['total_wallets']}")
print(f"Total RTC: {stats['total_rtc']}")
```

### Error Handling

```python
from rustchain import RustChainClient
from rustchain.exceptions import (
    RustChainError,
    WalletError,
    TransactionError,
    NetworkError,
    AuthenticationError
)

client = RustChainClient()

try:
    balance = client.get_balance("my-wallet")
except NetworkError as e:
    print(f"Connection failed: {e}")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except RustChainError as e:
    print(f"API error: {e}")
```

## Configuration

### Environment Variables

You can configure the SDK using environment variables:

```bash
export RUSTCHAIN_NODE_URL="https://50.28.86.131"
export RUSTCHAIN_ADMIN_KEY="your-admin-key"
export RUSTCHAIN_TIMEOUT="10"
```

### Custom Configuration

```python
client = RustChainClient(
    node_url="https://50.28.86.131",  # RustChain node URL
    admin_key="your-admin-key",        # Admin key for privileged operations
    timeout=10                         # Request timeout in seconds
)
```

## API Reference

### RustChainClient

#### `__init__(node_url, admin_key, timeout)`
Initialize the RustChain client.

#### `get_balance(miner_id)`
Get wallet balance for a miner/wallet ID.

**Returns:** Dictionary with `miner_id` and `balance_rtc`

#### `check_wallet_exists(miner_id)`
Check if a wallet exists on the network.

**Returns:** Boolean

#### `get_pending_transfers(miner_id)`
Get pending transfers for a wallet.

**Returns:** List of pending transfer dictionaries

#### `transfer_rtc(from_wallet, to_wallet, amount_rtc, admin_key)`
Transfer RTC between wallets.

**Returns:** Transaction result with `pending_id`

#### `get_epoch_info()`
Get current epoch and slot information.

**Returns:** Dictionary with epoch, slot, and enrolled miners

#### `get_active_miners()`
Get list of currently attesting miners.

**Returns:** List of miner dictionaries

#### `get_all_holders(admin_key)`
Get all wallet balances (admin only).

**Returns:** List of wallet dictionaries

#### `get_holder_stats(admin_key)`
Get aggregated statistics (admin only).

**Returns:** Dictionary with aggregate statistics

#### `check_eligibility(miner_id)`
Check lottery/epoch eligibility.

**Returns:** Eligibility information dictionary

#### `health_check()`
Check node health status.

**Returns:** Health status dictionary

#### `get_node_info()`
Get node information and version.

**Returns:** Node information dictionary

### Wallet

High-level wallet operations wrapper.

### Transaction

High-level transaction operations wrapper.

## Examples

See the `examples/` directory for complete working examples:

- `examples/basic_usage.py` - Basic client usage
- `examples/wallet_management.py` - Wallet operations
- `examples/transactions.py` - Transaction examples
- `examples/network_info.py` - Network queries
- `examples/error_handling.py` - Error handling patterns

## Testing

Run the test suite:

```bash
pytest tests/
```

Run with coverage:

```bash
pytest --cov=rustchain tests/
```

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation:** https://github.com/Scottcjn/bounty-concierge
- **Issues:** https://github.com/Scottcjn/rustchain-py/issues
- **Discord:** https://discord.gg/VqVVS2CW9Q
- **Twitter:** [@RustchainPOA](https://twitter.com/RustchainPOA)

## Acknowledgments

- RustChain Team for the blockchain infrastructure
- All contributors and bounty hunters
- The PowerPC and retro computing community
