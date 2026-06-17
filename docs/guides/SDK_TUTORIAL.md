# Python SDK Tutorial

Get started with the RustChain Python SDK in 5 minutes.

## Installation

```bash
pip install git+https://github.com/cuentaprueba244w-dotcom/rustchain-sdk.git
```

## Basic Usage

```python
from rustchain_sdk import RustChainClient

client = RustChainClient()

# Check node health
health = client.get_health()
print(f"Node: {health.service} - {health.status}")

# Check wallet balance
balance = client.get_wallet_balance("my-wallet")
print(f"Balance: {balance.amount_rtc} RTC")

# List active miners
miners = client.get_miners()
for m in miners:
    print(f"{m.miner_id}: {m.multiplier}x ({m.hardware})")

# Current epoch
epoch = client.get_epoch()
print(f"Epoch {epoch.epoch}: {epoch.reward_pool} RTC pool")
```

## Submitting Attestations

```python
client.submit_attestation("my-wallet")
```

## Checking Payouts

```python
stats = client.get_payout_stats()
print(f"{stats.total_paid_rtc} RTC paid to {stats.unique_recipients} people")
```

## Async Usage

```python
import asyncio
from rustchain_sdk import AsyncRustChainClient

async def main():
    async with AsyncRustChainClient() as client:
        health = await client.get_health()
        miners = await client.get_miners()
        print(f"Node: {health.status}, Miners: {len(miners)}")

asyncio.run(main())
```

## Error Handling

```python
from rustchain_sdk import RustChainClient, NodeConnectionError

client = RustChainClient()
try:
    health = client.get_health()
except NodeConnectionError as e:
    print(f"Cannot connect: {e}")
```

## Custom Node

```python
client = RustChainClient(
    node_url="https://custom-node.example.com",
    verify_ssl=True,
    timeout=15,
    max_retries=5,
)
```
