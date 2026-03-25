# rustchain — Python SDK for RustChain

[![PyPI](https://img.shields.io/pypi/v/rustchain)](https://pypi.org/project/rustchain/)
[![Python](https://img.shields.io/pypi/pyversions/rustchain)](https://pypi.org/project/rustchain/)

A typed Python SDK for interacting with [RustChain](https://github.com/Scottcjn/Rustchain) Proof-of-Antiquity nodes. Sync and async support, CLI included.

## Install

```bash
pip install rustchain
```

## Quick Start

```python
from rustchain import RustChainClient

with RustChainClient("https://50.28.86.131") as client:
    # Node health
    health = client.health()
    print(f"Status: {health.status}, Version: {health.version}")

    # Current epoch
    epoch = client.epoch()
    print(f"Epoch {epoch.epoch}, {epoch.miners_active} active miners")

    # List miners
    for miner in client.miners():
        print(f"  {miner.id}: score={miner.score}, status={miner.status}")

    # Check balance
    balance = client.balance("my-wallet-id")
    print(f"Balance: {balance.balance} {balance.currency}")

    # Attestation status
    att = client.attestation_status("miner-123")
    print(f"Attested: {att.attested}, Epoch: {att.epoch}")

    # Explorer — recent blocks & transactions
    for block in client.explorer.blocks(limit=5):
        print(f"Block #{block.height}: {block.tx_count} txs by {block.miner}")

    for tx in client.explorer.transactions(limit=5):
        print(f"Tx {tx.tx_hash[:16]}... {tx.amount} RTC")
```

## Async Usage

```python
import asyncio
from rustchain import AsyncRustChainClient

async def main():
    async with AsyncRustChainClient() as client:
        health = await client.health()
        miners = await client.miners()
        print(f"{health.status} — {len(miners)} miners")

asyncio.run(main())
```

## CLI

```bash
rustchain health
rustchain epoch
rustchain miners
rustchain balance <wallet-id>
rustchain attestation <miner-id>
rustchain blocks --limit 5
rustchain transactions --limit 10
```

Use `--node <url>` to point at a different node.

## Error Handling

```python
from rustchain import RustChainClient
from rustchain.exceptions import APIError, ConnectionError, TimeoutError, ValidationError

try:
    client = RustChainClient()
    client.balance("")
except ValidationError as e:
    print(f"Bad input: {e}")
except ConnectionError as e:
    print(f"Can't reach node: {e}")
except APIError as e:
    print(f"Node error {e.status_code}: {e.message}")
```

## API Reference

### `RustChainClient(node_url, timeout)`
| Method | Returns | Description |
|--------|---------|-------------|
| `health()` | `HealthStatus` | Node status, uptime, version |
| `epoch()` | `EpochInfo` | Current epoch, active miners |
| `miners()` | `list[Miner]` | All miners with scores |
| `balance(wallet_id)` | `Balance` | RTC balance for wallet |
| `transfer(from, to, amount, sig)` | `TransferResult` | Signed transfer |
| `attestation_status(miner_id)` | `AttestationStatus` | Miner attestation info |
| `explorer.blocks(limit)` | `list[Block]` | Recent blocks |
| `explorer.transactions(limit)` | `list[Transaction]` | Recent transactions |

`AsyncRustChainClient` has the same methods, all `async`.

## License

MIT
