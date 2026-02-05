# RustChain Python SDK 🦀

A clean, pip-installable Python SDK for the [RustChain](https://github.com/Scottcjn/Rustchain) Proof-of-Antiquity blockchain.

## Installation

```bash
# From GitHub
pip install git+https://github.com/Scottcjn/Rustchain.git#subdirectory=sdk

# Or clone and install locally
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/sdk
pip install -e .
```

## Quick Start

```python
from rustchain_sdk import RustChainClient

# Connect to the RustChain network
client = RustChainClient()

# Check node health
health = client.health()
print(f"Node OK: {health['ok']}, Version: {health['version']}")

# Get current epoch info
epoch = client.get_epoch()
print(f"Epoch {epoch.epoch}, Pot: {epoch.epoch_pot} RTC, Miners: {epoch.enrolled_miners}")

# List active miners
miners = client.get_miners()
for miner in miners:
    print(f"{miner.hardware_type}: {miner.antiquity_multiplier}x multiplier")

# Check wallet balance
balance = client.get_balance("my-wallet-id")
print(f"Balance: {balance.amount_rtc} RTC")
```

## Async Support

```python
import asyncio
from rustchain_sdk import AsyncRustChainClient

async def main():
    async with AsyncRustChainClient() as client:
        miners = await client.get_miners()
        for m in miners:
            print(f"{m.miner_id}: {m.hardware_type}")

asyncio.run(main())
```

## API Reference

### `RustChainClient(base_url, verify_ssl, timeout, max_retries, retry_delay)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | str | `https://50.28.86.131` | Node URL |
| `verify_ssl` | bool | `False` | Verify SSL (node uses self-signed cert) |
| `timeout` | float | `30.0` | Request timeout in seconds |
| `max_retries` | int | `3` | Max retry attempts |
| `retry_delay` | float | `1.0` | Initial retry delay (exponential backoff) |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `health()` | `dict` | Node health status |
| `get_epoch()` | `EpochInfo` | Current epoch details |
| `get_miners()` | `List[Miner]` | All active miners |
| `get_balance(miner_id)` | `Balance` | Wallet balance |
| `check_eligibility(miner_id)` | `dict` | Lottery eligibility |
| `submit_attestation(payload)` | `dict` | Submit hardware attestation |
| `transfer(from, to, amount, sig, nonce)` | `TransferResult` | Signed RTC transfer |

### Data Classes

```python
@dataclass
class Miner:
    miner_id: str
    device_family: str
    device_arch: str
    hardware_type: str
    antiquity_multiplier: float
    entropy_score: float
    last_attest: int

@dataclass
class EpochInfo:
    epoch: int
    slot: int
    blocks_per_epoch: int
    epoch_pot: float
    enrolled_miners: int

@dataclass
class Balance:
    miner_id: str
    amount_rtc: float
    amount_i64: int

@dataclass
class TransferResult:
    success: bool
    tx_hash: Optional[str]
    new_balance: Optional[int]
    error: Optional[str]
```

## Signed Transfers

To execute a signed transfer, you need to:

1. Create the message: `"{from}:{to}:{amount_i64}:{nonce}"`
2. Sign with Ed25519
3. Base64-encode the signature

```python
from nacl.signing import SigningKey
from nacl.encoding import Base64Encoder

# Your Ed25519 signing key
signing_key = SigningKey(seed_bytes)

# Create message
amount_i64 = int(amount_rtc * 1_000_000)
message = f"{from_wallet}:{to_wallet}:{amount_i64}:{nonce}".encode()

# Sign
signed = signing_key.sign(message)
signature = Base64Encoder.encode(signed.signature).decode()

# Transfer
result = client.transfer(
    from_wallet=from_wallet,
    to_wallet=to_wallet,
    amount_rtc=amount_rtc,
    signature=signature,
    nonce=nonce
)
```

## Error Handling

```python
from rustchain_sdk import RustChainClient, RustChainError, ConnectionError, APIError

try:
    client = RustChainClient()
    balance = client.get_balance("wallet-id")
except ConnectionError as e:
    print(f"Could not connect to node: {e}")
except APIError as e:
    print(f"API returned error: {e}")
except RustChainError as e:
    print(f"SDK error: {e}")
```

## Contributing

PRs welcome! See [rustchain-bounties](https://github.com/Scottcjn/rustchain-bounties) for active bounties.

## License

MIT

---

Built by [darkflobi](https://twitter.com/darkflobi) 🤖
