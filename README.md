# RustChain Python SDK

`pip install rustchain`

A Python SDK for interacting with the RustChain blockchain node API.

## Features

- Async-first design using `httpx`
- Full type hints and docstrings
- CLI tool for quick node interaction
- Context manager support for proper resource cleanup
- Self-signed certificate support

## Installation

```bash
pip install rustchain
```

## Quick Start

```python
import asyncio
from rustchain import RustChainClient

async def main():
    async with RustChainClient() as client:
        # Check node health
        health = await client.get_health()
        print(f"Node version: {health.version}")

        # Get current epoch
        epoch = await client.get_epoch()
        print(f"Epoch {epoch.epoch}, Slot {epoch.slot}")

        # List miners
        miners = await client.get_miners()
        print(f"Active miners: {len(miners)}")

        # Check balance
        bal = await client.get_balance("my_miner")
        print(f"Balance: {bal.amount_rtc} RTC")

asyncio.run(main())
```

## CLI Usage

```bash
# Node health
rustchain health

# Current epoch
rustchain epoch

# List miners
rustchain miners

# Check balance
rustchain balance my_miner

# Submit signed transfer
rustchain transfer-signed \
    --from 0xabc \
    --to 0xdef \
    --amount 100.0 \
    --nonce 1 \
    --signature 0xsig \
    --pubkey 0xpub

# Admin transfer
rustchain admin-transfer \
    --admin-key YOUR_ADMIN_KEY \
    --from miner_a \
    --to miner_b \
    --amount 500.0

# Settle rewards
rustchain settle --admin-key YOUR_ADMIN_KEY
```

## API Reference

### `RustChainClient`

Main async client.

- `get_health()` → `NodeHealth`
- `get_epoch()` → `EpochInfo`
- `get_miners()` → `list[MinerInfo]`
- `get_balance(miner_id)` → `BalanceInfo`
- `submit_transfer_signed(tx)` → `dict`
- `admin_transfer(admin_key, from_miner, to_miner, amount_rtc)` → `dict`
- `settle_rewards(admin_key)` → `dict`

### Models

- `NodeHealth` — ok, version, uptime_s, db_rw, tip_age_slots, backup_age_hours
- `EpochInfo` — epoch, slot, blocks_per_epoch, epoch_pot, enrolled_miners
- `MinerInfo` — miner, device_arch, device_family, hardware_type, antiquity_multiplier, last_attest
- `BalanceInfo` — ok, miner_id, amount_rtc, amount_i64
- `SignedTransfer` — from_address, to_address, amount_rtc, nonce, signature, public_key

### Exceptions

- `RustChainError` — base exception
- `APIError` — HTTP errors (includes status_code)
- `ValidationError` — bad request / 400
- `AuthenticationError` — admin auth failure / 401/403
