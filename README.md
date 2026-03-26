# rustchain — Python SDK for RustChain

> Python SDK for the [RustChain](https://rustchain.org) Proof-of-Antiquity blockchain.
> Installable via `pip install rustchain`.

[![PyPI version](https://img.shields.io/pypi/v/rustchain.svg)](https://pypi.org/project/rustchain/)
[![Python](https://img.shields.io/pypi/pyversions/rustchain.svg)](https://pypi.org/project/rustchain/)

## What is RustChain?

RustChain is a Proof-of-Antiquity blockchain that rewards vintage and exotic hardware.
Older architectures (PowerPC G4, SPARC, MIPS, 68K) earn **higher antiquity multipliers**
than modern x86 — a 2.5x multiplier for G4 hardware, 3.5x for Motorola 68K.

## Install

```bash
pip install rustchain
```

For async features (`AsyncRustChainClient`):

```bash
pip install rustchain[aiohttp]
```

For Ed25519 signing support:

```bash
pip install rustchain[crypto]   # uses cryptography.io
# or
pip install rustchain[ed25519]   # uses ed25519-blake2b
```

For development:

```bash
pip install rustchain[dev]
pytest tests/
```

## Quickstart

### Sync Client

```python
from rustchain import RustChainClient

client = RustChainClient()

# Node health
health = client.health()
print(f"Node {health['version']} — uptime: {health['uptime_s']}s")

# Current epoch
epoch = client.epoch()
print(f"Epoch {epoch['epoch']}, slot {epoch['slot']}")

# Active miners
miners = client.miners()
for m in miners[:5]:
    print(f"  {m['miner']} — antiquity ×{m['antiquity_multiplier']}")

# Wallet balance
balance = client.balance("Ivan-houzhiwen")
print(f"Balance: {balance['amount_rtc']} RTC")

# Attestation status
status = client.attestation_status("g4-powerbook-001")
print(f"Verified: {status['verified']}, score: {status['antiquity_score']}")
```

### Explorer — Blocks & Transactions

```python
# Recent blocks
blocks = client.explorer.blocks(limit=20)
for b in blocks["blocks"]:
    print(f"  Block {b['height']} — hash {b['hash'][:16]}...")

# Recent transactions
txs = client.explorer.transactions(limit=50)
for tx in txs["transactions"]:
    print(f"  {tx['hash'][:16]}... {tx['from']} → {tx['to']} : {tx['amount']}")

# Transactions for a specific wallet
wallet_txs = client.explorer.transactions(wallet_id="my-wallet", limit=100)

# Single block by height or hash
block = client.explorer.block_by_height(1234)
tx   = client.explorer.transaction_by_hash("0xdeadbeef...")
```

### Signed Transfer

```python
from rustchain import RustChainClient
from rustchain.crypto import SigningKey

client = RustChainClient()
key = SigningKey.generate()          # generate a key
# or: key = SigningKey.from_seed(b"my BIP39 seed phrase")

# Transfer 1 RTC (1_000_000 smallest units) from alice to bob
result = client.transfer_signed(
    from_wallet="alice",
    to_wallet="bob",
    amount=1_000_000,
    signing_key=key,
    fee=1000,
)
print(result)
```

### Async Client

```python
import asyncio
from rustchain import AsyncRustChainClient

async def main():
    client = AsyncRustChainClient()
    health, epoch, miners = await asyncio.gather(
        client.health(),
        client.epoch(),
        client.miners(),
    )
    print(f"Epoch {epoch['epoch']}: {len(miners)} miners online")

asyncio.run(main())
```

## CLI

```bash
# Check node health
rustchain health

# Get wallet balance
rustchain balance Ivan-houzhiwen

# Get current epoch
rustchain epoch

# List active miners
rustchain miners

# Generate a new wallet
rustchain wallet generate
rustchain wallet generate --seed "my secret seed phrase"

# Sign a transfer payload
rustchain wallet sign alice bob 1000000 --fee 1000 --seed "seed"

# Submit a signed transfer
rustchain transfer alice bob 1000000 --fee 1000 --sig <signature_hex>
```

## API Reference

### `RustChainClient`

| Method | Returns | Description |
|--------|---------|-------------|
| `client.health()` | `dict` | Node health & version |
| `client.epoch()` | `dict` | Current epoch info |
| `client.miners()` | `list[dict]` | All active miners |
| `client.balance(wallet_id)` | `dict` | RTC balance for wallet |
| `client.transfer(from, to, amount, signature, ...)` | `dict` | Submit signed transfer |
| `client.transfer_signed(from, to, amount, signing_key, ...)` | `dict` | Sign & submit in one call |
| `client.attestation_status(miner_id)` | `dict` | Attestation verification status |

### `Explorer`

| Method | Returns | Description |
|--------|---------|-------------|
| `client.explorer.blocks(limit=20)` | `dict` | Recent blocks |
| `client.explorer.block_by_height(n)` | `dict` | Single block |
| `client.explorer.block_by_hash(hash)` | `dict` | Single block |
| `client.explorer.transactions(limit=50)` | `dict` | Recent transactions |
| `client.explorer.transaction_by_hash(hash)` | `dict` | Single transaction |

### Exceptions

All exceptions inherit from `RustChainError`:

- `APIError` — non-2xx response (has `.status_code`)
- `ConnectionError` — cannot reach node
- `TimeoutError` — request timed out
- `ValidationError` — bad input (empty wallet ID, negative amount)
- `WalletError` — wallet operation failed
- `SigningError` — Ed25519 signing failed

## WebSocket Feed (Real-time)

For real-time block updates via WebSocket:

```python
import asyncio
from rustchain.websocket_feed import BlockFeed

async def on_block(block):
    print(f"New block: {block['height']}")

feed = BlockFeed()
asyncio.run(feed.subscribe(on_block))
```

## Node Endpoints

Default node: `https://50.28.86.131`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Node health check |
| `/epoch` | GET | Current epoch info |
| `/api/miners` | GET | Active miners list |
| `/wallet/balance` | GET | Wallet balance |
| `/wallet/transfer/signed` | POST | Signed transfer |
| `/attest/status/<miner_id>` | GET | Attestation status |
| `/blocks` | GET | Recent blocks |
| `/api/transactions` | GET | Recent transactions |

## Testing

```bash
pip install rustchain[dev]
pytest tests/ -v
```

## License

MIT
