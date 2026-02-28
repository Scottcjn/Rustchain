# RustChain Python SDK Tutorial

## Installation

```bash
pip install clawrtc
```

## Basic Usage

### Create Wallet

```python
from clawrtc import Wallet

wallet = Wallet.create("my_miner")
print(wallet.address)
```

### Check Balance

```python
from clawrtc import Client

client = Client()
balance = client.get_balance("my_miner")
print(f"Balance: {balance} RTC")
```

### Start Mining

```python
from clawrtc import Miner

miner = Miner(wallet="my_miner")
miner.start()
```

## Advanced

### Custom Node

```python
client = Client(node_url="https://your-node:port")
```

### Get Epoch Info

```python
epoch = client.get_epoch()
print(f"Epoch: {epoch.number}")
print(f"Progress: {epoch.progress}%")
```
