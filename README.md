# RustChain Python SDK

Async Python SDK for the RustChain blockchain network, powered by `httpx` and `pydantic`.

## Features

- **Async-first** — All API calls use `httpx.AsyncClient`
- **Fully typed** — Type hints throughout with Pydantic models
- **Explorer client** — Browse blocks and transactions
- **WebSocket feed** — Real-time block notifications
- **CLI wrapper** — `rustchain balance <wallet>` from the terminal
- **Error handling** — Typed exceptions (`RustChainError`, `APIError`, `NetworkError`)

## Installation

```bash
pip install rustchain
```

Or install with CLI dependencies:

```bash
pip install rustchain[cli]
```

## Quickstart

```python
import asyncio
from rustchain import RustChainClient

async def main():
    async with RustChainClient() as client:
        # Check node health
        health = await client.health()
        print(f"Node status: {health.status}")

        # Get current epoch
        epoch = await client.epoch()
        print(f"Epoch {epoch.epoch}")

        # List active miners
        miners = await client.miners()
        print(f"Active miners: {miners.total}")

        # Check wallet balance
        balance = await client.balance("C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg")
        print(f"Balance: {balance.balance} RTC")

        # Browse blocks
        blocks = await client.explorer.blocks()
        for block in blocks.blocks[:5]:
            print(f"Block #{block.height}: {block.hash}")

        # Recent transactions
        txs = await client.explorer.transactions()
        for tx in txs.transactions[:5]:
            print(f"Tx {tx.tx_hash}: {tx.amount} RTC")

asyncio.run(main())
```

## API Reference

### RustChainClient

```python
client = RustChainClient(
    base_url="http://50.28.86.131:8099",  # default
    timeout=30.0,                           # default
)
```

| Method | Description |
|---|---|
| `client.health()` | Node health check → `HealthResponse` |
| `client.epoch()` | Current epoch info → `EpochInfo` |
| `client.miners(page=1, per_page=20)` | List active miners → `MinerListResponse` |
| `client.balance(wallet_id)` | Check RTC balance → `BalanceResponse` |
| `client.transfer(from, to, amount, signature)` | Signed transfer → `TransferResponse` |
| `client.attestation_status(miner_id)` | Miner attestation status → `AttestationStatus` |

### Explorer Sub-client

```python
client.explorer.blocks(page=1, per_page=20)       # Recent blocks
client.explorer.transactions(page=1, per_page=20) # Recent transactions
```

### WebSocket Feed (real-time blocks)

```python
from rustchain.websocket import WebSocketFeed

async def on_new_block(block):
    print(f"New block: #{block.height} {block.hash}")

async with WebSocketFeed() as feed:
    await feed.subscribe(on_new_block)
    await asyncio.sleep(60)  # listen for 60 seconds
```

### CLI

```bash
rustchain health
rustchain epoch
rustchain miners
rustchain balance C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg
rustchain blocks
rustchain transactions
rustchain transfer <from> <to> <amount> <signature_b64>
rustchain attestation <miner_id>
```

## Error Handling

```python
from rustchain import RustChainClient
from rustchain.exceptions import RustChainError, APIError, NetworkError, WalletError

async def safe_balance(wallet_id):
    try:
        async with RustChainClient() as client:
            return await client.balance(wallet_id)
    except NetworkError as e:
        print(f"Network error: {e.message}")
    except APIError as e:
        print(f"API error ({e.status_code}): {e.message}")
    except WalletError as e:
        print(f"Wallet error: {e.message}")
    except RustChainError as e:
        print(f"RustChain error: {e.message}")
```

## Models

All API responses are parsed into typed Pydantic models:

- `HealthResponse` — Node health status
- `EpochInfo` — Current epoch details
- `Miner` — Individual miner data
- `MinerListResponse` — Paginated miner list
- `BalanceResponse` — Wallet balance info
- `TransferRequest` / `TransferResponse` — Transfer data
- `AttestationStatus` — Miner attestation info
- `Block` — Individual block
- `BlockListResponse` — Paginated block list
- `Transaction` — Individual transaction
- `TransactionListResponse` — Paginated transaction list

## Publishing to PyPI

```bash
pip install build twine
python -m build
twine upload dist/*
```

## Bounty

Wallet address for bounty rewards: `C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg`
