# RustChain Wallet CLI

Command-line wallet tool for managing RustChain (RTC) tokens. Perfect for headless servers, SSH-only machines, and AI agents.

## Features

✅ **BIP39 Seed Phrases** - Industry-standard 24-word mnemonic backup  
✅ **Ed25519 Signatures** - Fast, secure transaction signing  
✅ **AES-256-GCM Encryption** - Password-protected keystores  
✅ **Compatible Format** - Works with existing GUI wallet keystores  
✅ **Network Queries** - Check miners, epochs, and balances  

## Installation

```bash
cd wallet
pip install -r requirements.txt

# Make executable (Unix/Linux/macOS)
chmod +x rustchain-wallet

# Add to PATH (optional)
sudo ln -s $(pwd)/rustchain-wallet /usr/local/bin/rustchain-wallet
```

## Quick Start

### Create a New Wallet

```bash
./rustchain-wallet create my-wallet
```

**⚠️ IMPORTANT:** Write down your 24-word seed phrase and store it securely!

### Check Balance

```bash
./rustchain-wallet balance my-wallet
```

### Send RTC

```bash
./rustchain-wallet send RTC1234abcd... 10.5 --from my-wallet
```

### Import Existing Wallet

```bash
./rustchain-wallet import restored-wallet "word1 word2 word3 ... word24"
```

## All Commands

### `create <wallet-name>`

Create a new wallet with BIP39 seed phrase.

**Example:**
```bash
./rustchain-wallet create alice-wallet
```

**Output:**
- Wallet name and address
- 24-word seed phrase (SAVE THIS!)
- Encrypted keystore location

**Options:**
- `--password` - Set wallet password (will prompt if not provided)

---

### `balance <wallet-id>`

Check RTC balance for any wallet address or miner ID.

**Example:**
```bash
./rustchain-wallet balance my-miner
./rustchain-wallet balance RTC1234abcd5678ef...
```

**Output:**
- Current RTC balance

---

### `send <to-address> <amount>`

Send RTC to another address with Ed25519 signature.

**Example:**
```bash
./rustchain-wallet send RTC9876fedcba... 25.0 --from alice-wallet
```

**Required:**
- `--from <wallet-name>` - Wallet to send from
- `--password` - Wallet password (will prompt if not provided)

**Output:**
- Transaction confirmation
- TX hash (if available)

---

### `import <wallet-name> <seed-phrase>`

Restore wallet from 24-word BIP39 seed phrase.

**Example:**
```bash
./rustchain-wallet import backup-wallet "abandon abandon abandon ... art"
```

**Options:**
- `--password` - Set new encryption password

**Note:** Seed phrase must be quoted if passed as argument.

---

### `export <wallet-name>`

Export wallet keystore or seed phrase.

**Example:**
```bash
# Show encrypted keystore JSON
./rustchain-wallet export alice-wallet

# Show seed phrase (DANGEROUS!)
./rustchain-wallet export alice-wallet --show-seed
```

**Options:**
- `--show-seed` - Decrypt and display seed phrase (requires password)
- `--password` - Wallet password

---

### `list`

List all wallets in keystore directory.

**Example:**
```bash
./rustchain-wallet list
```

**Output:**
- Wallet names
- Addresses
- Keystore file locations

---

### `miners`

List active miners on the RustChain network.

**Example:**
```bash
./rustchain-wallet miners
```

**Output:**
- Miner IDs
- Balances
- Hardware information

---

### `epoch`

Show current epoch information.

**Example:**
```bash
./rustchain-wallet epoch
```

**Output:**
- Current epoch number
- Block height
- Timestamp

---

## Keystore Format

Wallets are stored as encrypted JSON files in `~/.rustchain/wallets/`.

**Security features:**
- AES-256-GCM encryption
- PBKDF2 key derivation (100,000 iterations)
- Ed25519 signing keys
- 600 (owner read/write only) file permissions

**Example keystore structure:**
```json
{
  "version": 1,
  "wallet_name": "alice-wallet",
  "address": "RTC1234abcd...",
  "crypto": {
    "cipher": "aes-256-gcm",
    "kdf": "pbkdf2",
    "kdf_params": {
      "iterations": 100000,
      "salt": "hex..."
    },
    "nonce": "hex...",
    "ciphertext": "hex..."
  }
}
```

## Address Format

RustChain addresses use the format:
```
RTC + first 40 characters of SHA256(public_key)
```

**Example:**
```
RTC1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9
```

## Transaction Signing

Transactions are signed with Ed25519:

1. Create canonical JSON (sorted keys, no whitespace)
2. Sign with Ed25519 private key
3. Attach signature + public key to transaction
4. Submit to `/wallet/transfer/signed` endpoint

**Transaction format:**
```json
{
  "from_addr": "RTCabc...",
  "to_addr": "RTCdef...",
  "amount": 10.5,
  "timestamp": "2026-02-11T12:34:56",
  "signature": "hex...",
  "public_key": "hex..."
}
```

## Compatibility

### With GUI Wallet

The CLI wallet is fully compatible with the RustChain GUI wallet:

- ✅ Keystores can be used by both CLI and GUI
- ✅ Same address derivation
- ✅ Same signing algorithm
- ✅ Same encryption format

### Platform Support

- ✅ Linux (Ubuntu, Debian, Fedora, etc.)
- ✅ macOS (Intel, Apple Silicon)
- ✅ Any Unix-like system with Python 3.6+

## Security Best Practices

### Password Security
- Use strong, unique passwords for each wallet
- Never reuse passwords from other services
- Consider using a password manager

### Seed Phrase Backup
- Write down your 24-word seed phrase
- Store it in a secure, offline location
- Never store it digitally (no photos, no cloud)
- Consider using a metal backup for fire/water resistance

### Keystore Protection
- Keystores are stored in `~/.rustchain/wallets/`
- Files have 600 permissions (owner-only access)
- Back up keystore files separately from passwords

### Network Security
- CLI connects to `https://50.28.86.131` (RustChain node)
- SSL verification is disabled for self-signed certs
- Consider using SSH tunnel for remote connections

## Troubleshooting

### "Wallet not found" error

Check that the keystore file exists:
```bash
ls ~/.rustchain/wallets/
```

### "Invalid password" error

Password incorrect or keystore corrupted. Try:
```bash
./rustchain-wallet export wallet-name
```

If keystore JSON is readable, password is wrong.

### "Connection refused" error

RustChain node may be temporarily unavailable:
```bash
curl -sk https://50.28.86.131/health
```

### Import fails with "Invalid seed phrase"

Ensure:
- Exactly 24 words
- Words from BIP39 wordlist
- Correct word order
- Quote the seed phrase: `"word1 word2 ..."`

## Development

### Project Structure
```
wallet/
├── rustchain-wallet          # CLI executable
├── rustchain_crypto.py       # Crypto module
├── requirements.txt          # Python dependencies
└── README_CLI.md            # This file
```

### Dependencies
- **click** - Command-line interface framework
- **requests** - HTTP client for node API
- **cryptography** - AES-256-GCM encryption
- **mnemonic** - BIP39 seed phrase generation
- **PyNaCl** - Ed25519 signing

### Running Tests

```bash
# Create test wallet
./rustchain-wallet create test-wallet

# Check balance
./rustchain-wallet balance test-wallet

# List wallets
./rustchain-wallet list

# Export (without seed)
./rustchain-wallet export test-wallet
```

## API Endpoints Used

- `GET /wallet/balance?miner_id=<id>` - Check balance
- `POST /wallet/transfer/signed` - Submit signed transaction
- `GET /api/miners` - List active miners
- `GET /epoch` - Current epoch info
- `GET /health` - Node health check

## Contributing

Found a bug or want to add a feature? See [CONTRIBUTING.md](../CONTRIBUTING.md).

## License

MIT License - See [LICENSE](../LICENSE) for details.

## Support

- **Discord:** https://discord.gg/VqVVS2CW9Q
- **GitHub Issues:** https://github.com/Scottcjn/Rustchain/issues
- **Documentation:** https://github.com/Scottcjn/Rustchain/tree/main/docs

---

**Built for RustChain Bounty #39** | **50 RTC** | Wallet: dlin38
