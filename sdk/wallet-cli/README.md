# RustChain Wallet CLI

Command-line wallet tool for managing RTC tokens on the RustChain blockchain.

## Installation

```bash
pip install git+https://github.com/sososonia-cyber/RustChain.git
```

Or for development:

```bash
git clone https://github.com/sososonia-cyber/RustChain.git
cd RustChain/sdk/wallet-cli
pip install -e .
```

## Usage

### Create a new wallet

```bash
rustchain-wallet create --name mywallet
```

### List wallets

```bash
rustchain-wallet list
# or
rustchain-wallet ls
```

### Check balance

```bash
rustchain-wallet balance RTCxxxxxxxxxxxxxxxxxxxx
```

### Import wallet from mnemonic

```bash
rustchain-wallet import "your 12 word mnemonic phrase"
```

### Export wallet info

```bash
rustchain-wallet export mywallet
```

## Requirements

- Python 3.8+
- requests

## License

MIT

## Author

Built by Atlas (AI Agent) for RustChain Bounty #39
