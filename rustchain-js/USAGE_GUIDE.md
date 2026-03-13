# RustChain SDK Usage Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Core Concepts](#core-concepts)
5. [API Reference](#api-reference)
6. [Examples](#examples)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

## Introduction

RustChain SDK provides official Python and JavaScript clients for interacting with the RustChain blockchain. The SDK allows you to:

- Query wallet balances and information
- Send RTC transactions
- Access network and epoch data
- Monitor node health
- Check lottery eligibility

### Supported Languages

- **Python** (3.8+) - `rustchain-py`
- **JavaScript/TypeScript** (Node.js 14+) - `rustchain-js`

### Key Features

- Simple, intuitive API
- Comprehensive error handling
- Type hints (Python) and JSDoc (JavaScript)
- Admin operations support
- Active community support

## Installation

### Python

```bash
# Install from PyPI
pip install rustchain-py

# Or install from source
git clone https://github.com/Scottcjn/rustchain-py.git
cd rustchain-py
pip install -e .
```

### JavaScript

```bash
# Install from npm
npm install rustchain-js

# Or install from source
git clone https://github.com/Scottcjn/rustchain-js.git
cd rustchain-js
npm install
```

## Quick Start

### Python Example

```python
from rustchain import RustChainClient

# Initialize client
client = RustChainClient(node_url="https://50.28.86.131")

# Query balance
balance = client.get_balance("my-wallet")
print(f"Balance: {balance.get('balance_rtc', 0)} RTC")

# Check wallet existence
exists = client.check_wallet_exists("my-wallet")
print(f"Wallet exists: {exists}")
```

### JavaScript Example

```javascript
import { RustChainClient } from 'rustchain-js';

// Initialize client
const client = new RustChainClient({
  nodeUrl: 'https://50.28.86.131'
});

// Query balance
const balance = await client.getBalance('my-wallet');
console.log(`Balance: ${balance.balance_rtc} RTC`);

// Check wallet existence
const exists = await client.checkWalletExists('my-wallet');
console.log(`Wallet exists: ${exists}`);
```

## Core Concepts

### Wallet Names

RustChain wallet names must follow these rules:
- 3 to 64 characters long
- Lowercase letters, digits, and hyphens only
- Must start and end with a letter or digit
- Examples: `my-wallet`, `wallet123`, `test-wallet-01`

### RTC Token

RTC (RustChain Token) is the native utility token:
- 1 RTC = $0.10 USD (reference rate)
- Used for bounties, rewards, and transactions
- Minimum transfer amount: 0.001 RTC

### Admin Key

Certain operations require an admin key:
- Transferring RTC between wallets
- Viewing all wallet holders
- Accessing holder statistics

Admin keys are provided by RustChain administrators.

## API Reference

### RustChainClient (Python) / RustChainClient (JavaScript)

#### Constructor

**Python:**
```python
client = RustChainClient(
    node_url="https://50.28.86.131",  # Optional
    admin_key="your-key",              # Optional
    timeout=10                         # Optional, seconds
)
```

**JavaScript:**
```javascript
const client = new RustChainClient({
  nodeUrl: 'https://50.28.86.131',  // Optional
  adminKey: 'your-key',             // Optional
  timeout: 10000                    // Optional, milliseconds
});
```

#### Wallet Operations

| Method | Python | JavaScript | Description |
|--------|--------|------------|-------------|
| Get Balance | `get_balance(miner_id)` | `getBalance(minerId)` | Query wallet balance |
| Check Exists | `check_wallet_exists(miner_id)` | `checkWalletExists(minerId)` | Check if wallet exists |
| Get Pending | `get_pending_transfers(miner_id)` | `getPendingTransfers(minerId)` | Get pending transfers |
| Transfer | `transfer_rtc(from, to, amount)` | `transferRtc(from, to, amount)` | Send RTC (admin) |

#### Network Operations

| Method | Python | JavaScript | Description |
|--------|--------|------------|-------------|
| Epoch Info | `get_epoch_info()` | `getEpochInfo()` | Get current epoch |
| Active Miners | `get_active_miners()` | `getActiveMiners()` | List active miners |
| All Holders | `get_all_holders(admin_key)` | `getAllHolders(adminKey)` | All wallets (admin) |
| Holder Stats | `get_holder_stats(admin_key)` | `getHolderStats(adminKey)` | Statistics (admin) |

#### Utility Operations

| Method | Python | JavaScript | Description |
|--------|--------|------------|-------------|
| Health Check | `health_check()` | `healthCheck()` | Node health status |
| Node Info | `get_node_info()` | `getNodeInfo()` | Node information |
| Eligibility | `check_eligibility(miner_id)` | `checkEligibility(minerId)` | Lottery eligibility |

## Examples

### Python Examples

See `rustchain-py/examples/` for complete examples:
- `basic_usage.py` - Basic operations
- `wallet_management.py` - Wallet operations
- `transactions.py` - Transaction examples

### JavaScript Examples

See `rustchain-js/examples/` for complete examples:
- `basic_usage.js` - Basic operations
- `wallet_management.js` - Wallet operations
- `transactions.js` - Transaction examples

## Best Practices

### Error Handling

Always wrap API calls in try-catch blocks:

**Python:**
```python
from rustchain.exceptions import NetworkError, RustChainError

try:
    balance = client.get_balance("my-wallet")
except NetworkError as e:
    print(f"Connection failed: {e}")
except RustChainError as e:
    print(f"API error: {e}")
```

**JavaScript:**
```javascript
import { NetworkError, RustChainError } from 'rustchain-js';

try {
  const balance = await client.getBalance('my-wallet');
} catch (error) {
  if (error instanceof NetworkError) {
    console.error(`Connection failed: ${error.message}`);
  } else if (error instanceof RustChainError) {
    console.error(`API error: ${error.message}`);
  }
}
```

### Security

- Never commit admin keys to version control
- Use environment variables for sensitive data
- Validate wallet names before use
- Double-check transaction amounts before sending

### Rate Limiting

The RustChain node may rate-limit requests. Implement exponential backoff:

**Python:**
```python
import time
from functools import wraps

def retry_with_backoff(max_retries=3, backoff_factor=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except NetworkError:
                    if i == max_retries - 1:
                        raise
                    time.sleep(backoff_factor ** i)
        return wrapper
    return decorator
```

## Troubleshooting

### Common Issues

#### "Could not connect to node"

**Cause:** Network connectivity issue or incorrect node URL

**Solution:**
1. Check your internet connection
2. Verify the node URL is correct
3. Try increasing the timeout value
4. Check if the node is online: `curl https://50.28.86.131/health`

#### "Admin key required"

**Cause:** Attempting privileged operation without admin key

**Solution:**
1. Obtain admin key from RustChain administrators
2. Pass admin key to client constructor
3. Or pass as parameter to specific methods

#### "Wallet does not exist"

**Cause:** Wallet name is invalid or not registered

**Solution:**
1. Validate wallet name format
2. Check for typos in wallet name
3. Register wallet via bounty claim or GUI

### Getting Help

- **Documentation:** https://github.com/Scottcjn/bounty-concierge
- **GitHub Issues:** https://github.com/Scottcjn/rustchain-py/issues or https://github.com/Scottcjn/rustchain-js/issues
- **Discord:** https://discord.gg/VqVVS2CW9Q
- **Twitter:** [@RustchainPOA](https://twitter.com/RustchainPOA)

## Contributing

Contributions are welcome! See the CONTRIBUTING.md files in each SDK repository for guidelines.

## License

Both SDKs are licensed under the MIT License. See LICENSE files for details.
