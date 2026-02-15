# RustChain Python SDK

<p align="center">
    <a href="https://pypi.org/project/rustchain-sdk/">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/rustchain-sdk.svg">
    </a>
    <a href="https://python.org">
        <img alt="Python" src="https://img.shields.io/pypi/pyversions/rustchain-sdk">
    </a>
    <a href="https://github.com/dunyuzoush-ch/rustchain-sdk/actions">
        <img alt="Tests" src="https://github.com/dunyuzoush-ch/rustchain-sdk/workflows/Tests/badge.svg">
    </a>
</p>

Python SDK for RustChain blockchain. Zero required dependencies beyond `requests`.

## Quick Start

```bash
pip install rustchain-sdk
```

```python
from rustchain import RustChainClient

client = RustChainClient(base_url="https://50.28.86.131", verify_ssl=False)

# Node info
health = client.health()
epoch = client.get_epoch()
miners = client.get_miners()

# Wallet operations
balance = client.get_balance("wallet_address")
```

## Installation

```bash
# From PyPI
pip install rustchain-sdk

# From source
git clone https://github.com/dunyuzoush-ch/rustchain-sdk.git
cd rustchain-sdk
pip install -e .
```

## Documentation

See [README.md](https://github.com/dunyuzoush-ch/rustchain-sdk/blob/main/README.md) for full documentation.

## License

MIT
