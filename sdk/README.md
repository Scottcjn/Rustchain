# RustChain Python SDK

Official Python client for the [RustChain](https://github.com/Scottcjn/Rustchain) Proof-of-Antiquity network.

## Installation

```bash
pip install rustchain-sdk
```

## Quick Start

```python
from rustchain_sdk import RustChainClient

# Connect to the live node
client = RustChainClient("https://50.28.86.131", verify_ssl=False)

# Check health
status = client.health()
print(f"Node Version: {status.version}")

# Get miner info
miners = client.miners()
for m in miners:
    print(f"Miner: {m.miner} | Multiplier: {m.antiquity_multiplier}")

# Check balance
balance = client.balance("your_miner_id")
print(f"Balance: {balance.amount_rtc} RTC")
```

## Features

- **Node Health**: Check version and uptime.
- **Epoch Info**: Track slots and reward pots.
- **Miner List**: Discover active hardware on the network.
- **Wallet Management**: Query balances and perform signed transfers.
- **Attestation**: Submit hardware fingerprints for enrollment.

## License

MIT
