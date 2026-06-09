# RustChain Wallet CLI

Command-line wallet management for [RustChain](https://github.com/Scottcjn/RustChain) — a Proof-of-Antiquity blockchain.

## Features

- **Create** wallets with BIP39 seed phrases (12 or 24 words)
- **Check balance** of any RTC address
- **Send** RTC transfers (Ed25519 signed)
- **Import/Export** wallets via seed phrase
- **Encrypted keystore** — AES-256-GCM with PBKDF2 key derivation
- **Network info** — miners, epoch, transaction history
- **Stdlib-only core** — no external dependencies for crypto operations
- **Compatible** with existing `rustchain_crypto.py` wallet format

## Install

```bash
# From PyPI (when published)
pip install rustchain-wallet-cli

# From source
git clone https://github.com/jasontodd0877-cloud/rustchain-dialup.git
cd rustchain-dialup
pip install -e rustchain-wallet-cli/
```

### Optional dependencies (for better crypto performance):

```bash
pip install PyNaCl        # Fast Ed25519
pip install cryptography  # AES-256-GCM
```

Without these, the CLI uses pure-Python fallback implementations.

## Quick Start

```bash
# Create a new wallet
rustchain-wallet create

# Create with 24 words
rustchain-wallet create --words 24

# Check balance
rustchain-wallet balance RTCabc123...

# Send RTC
rustchain-wallet send RTCxyz789... 10 --from default

# Import from seed phrase
rustchain-wallet import --words "abandon ability able about above absent absorb abstract absurd abuse access accident"

# List wallets
rustchain-wallet list

# Export keystore JSON
rustchain-wallet export default
```

## Keystore

Wallets are stored encrypted at `~/.rustchain/wallets/`:

```
~/.rustchain/wallets/
├── default.json
├── backup.json
└── agent.json
```

Each file is AES-256-GCM encrypted with PBKDF2 key derivation (100,000 iterations).

## Network Commands

```bash
# Active miners
rustchain-wallet miners

# Epoch info
rustchain-wallet epoch

# Transaction history
rustchain-wallet history RTCabc123...

# Custom node URL
rustchain-wallet balance RTCabc... --node https://50.28.86.131
```

## Security

- Private keys are **never stored in plaintext**
- Keystore uses **AES-256-GCM** (authenticated encryption)
- Key derivation: **PBKDF2-SHA256** with 100,000 iterations and random salt
- Password prompt does **not echo** to terminal
- All API calls use **HTTPS with TLS verification**
- URL scheme is validated — only `https://` allowed

## Address Format

RTC addresses are derived from the public key:
```
RTC + SHA256(public_key)[:40]
```

## Compatibility

- Compatible with `rustchain_crypto.py` wallet format
- Same BIP39 derivation as the GUI wallet
- Same Ed25519 signing as `RustChainWallet` class
- Keystore files can be shared between CLI and GUI

## License

Apache 2.0
