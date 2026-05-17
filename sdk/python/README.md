# RustChain Python SDK

> Official Python SDK for the RustChain blockchain network — async-capable, BIP39 wallet support, full RPC coverage.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8+-green.svg)](https://www.python.org/)

## Install

```bash
pip install rustchain
```

For development:
```bash
pip install -e ".[dev]"
```

## Quick Start

```python
import asyncio
from rustchain_sdk import RustChainClient, RustChainWallet

async def main():
    # Connect to a RustChain node
    client = RustChainClient("https://50.28.86.131")

    async with client:
        # Check node health
        health = await client.health()
        print("Node status:", health)

        # Check wallet balance
        balance = await client.get_balance("C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg")
        print("Balance:", balance)

        # Create a new wallet
        wallet = RustChainWallet.create()
        print("New wallet address:", wallet.address)
        print("Seed phrase:", " ".join(wallet.seed_phrase))

        # Send a transfer
        result = await client.wallet_transfer_with_wallet(
            wallet,
            to_address="RTCrecipient...",
            amount=10.5,  # RTC
            fee=0,
        )
        print("TX result:", result)

asyncio.run(main())
```

## CLI

```bash
# Create a new wallet
rustchain wallet create

# Check balance
rustchain wallet balance RTC1a2b3c4d5e6f...

# Send RTC
rustchain wallet send <from> <to> <amount> --seed "word1 word2 ..."

# Node status
rustchain node status

# Current epoch
rustchain epoch info

# List miners
rustchain miners list

# Attest a miner
rustchain attest <wallet_address> --seed "word1 word2 ..."
```

## API Reference

### RustChainClient

| Method | Description |
|--------|-------------|
| `health()` | Node health check |
| `get_epoch()` | Current epoch info |
| `get_miners()` | List active miners |
| `get_balance(address)` | Wallet balance |
| `get_wallet_history(address, limit)` | Transaction history |
| `transfer_signed(...)` | Submit signed transfer |
| `attest_challenge(miner_public_key)` | Request attestation challenge |
| `attest_submit(...)` | Submit attestation |
| `beacon_submit(envelope)` | Submit beacon envelope |
| `governance_propose(...)` | Submit governance proposal |
| `governance_vote(...)` | Cast governance vote |
| `explorer_blocks(limit)` | Recent blocks |
| `explorer_transactions(address, limit)` | Transactions |
| `get_epoch_rewards(epoch)` | Epoch rewards |
| `wallet_transfer_with_wallet(wallet, ...)` | Sign & send with wallet |

### RustChainWallet

```python
# Create wallet
wallet = RustChainWallet.create()           # 12 words by default
wallet = RustChainWallet.create(strength=256)  # 24 words

# From seed phrase
wallet = RustChainWallet.from_seed_phrase(["abandon", "ability", ...])

# Sign transfer
transfer = wallet.sign_transfer(to_address, amount, fee)

# Export/Import
data = wallet.export()
restored = RustChainWallet.import_(data)

# Properties
wallet.address       # RTC address
wallet.public_key_hex
wallet.seed_phrase   # Keep secret!
```

## Exceptions

All exceptions inherit from `RustChainError`:

- `ConnectionError` — Node unreachable or SSL error
- `APIError` — RPC returned an error (non-2xx status)
- `ValidationError` — Invalid input parameters
- `WalletError` — Wallet operation failed
- `AttestationError` — Attestation flow error
- `GovernanceError` — Governance operation failed

## Requirements

- Python 3.8+
- `httpx>=0.25.0` (async HTTP)
- `click>=8.0.0` (CLI)

Optional:
- `cryptography>=41.0.0` (for real Ed25519 signatures)

## License

MIT — kuanglaodi2-sudo
