# RustChain CLI Wallet

A command-line wallet for the RustChain blockchain network.

## Features

- 🔐 **Secure Key Management**: Generate and manage cryptographic keys
- 💰 **Balance Checking**: Check your RTC token balance
- 📤 **Send Transactions**: Send RTC tokens to other addresses
- 📨 **Receive Tokens**: Display your address for receiving payments
- ✅ **Address Validation**: Validate RustChain addresses

## Installation

```bash
cd tools/cli-wallet
cargo build --release
```

The binary will be available at `target/release/rustchain-wallet`.

## Usage

### Generate a New Wallet

```bash
./rustchain-wallet generate
```

This creates a new wallet file (`wallet.json`) containing your private key, public key, and address.

**⚠️ Important**: Keep your `wallet.json` file secure and make backups. Anyone with access to this file can spend your RTC tokens.

### Check Balance

```bash
./rustchain-wallet balance
```

Check the balance of your default wallet, or specify a custom wallet file:

```bash
./rustchain-wallet balance --wallet my-wallet.json
```

### Send RTC Tokens

```bash
./rustchain-wallet send --to RTC1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa --amount 100
```

Send 100 RTC tokens to the specified address.

### Receive Tokens

```bash
./rustchain-wallet receive
```

Displays your wallet address for receiving RTC tokens.

### Validate an Address

```bash
./rustchain-wallet validate RTC1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
```

Checks if the given address is a valid RustChain address.

## Configuration

### Custom Node URL

By default, the wallet connects to `http://localhost:8080`. You can specify a different node:

```bash
./rustchain-wallet balance --node http://rustchain-node.example.com:8080
```

### Custom Wallet File

Specify a different wallet file:

```bash
./rustchain-wallet generate --output my-wallet.json
./rustchain-wallet balance --wallet my-wallet.json
```

## Wallet File Format

The wallet is stored as a JSON file:

```json
{
  "address": "RTC1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
  "private_key": "a1b2c3d4e5f6...",
  "public_key": "04a1b2c3d4e5f6..."
}
```

## Security Best Practices

1. **Backup Your Wallet**: Always keep secure backups of your `wallet.json` file
2. **File Permissions**: Set restrictive permissions on wallet files: `chmod 600 wallet.json`
3. **Secure Storage**: Store wallet files in encrypted storage
4. **Network Security**: Only connect to trusted RustChain nodes
5. **Verify Addresses**: Always double-check recipient addresses before sending

## Development Mode

When the RustChain node is not available, the wallet operates in development mode with:
- Mock balance of 1000 RTC
- Simulated successful transactions
- Local address validation

This allows testing wallet functionality without a running blockchain node.

## API Endpoints

The wallet expects the following RustChain node API endpoints:

- `GET /api/balance/{address}` - Get account balance
- `POST /api/transaction` - Submit transaction

## Error Handling

Common errors and solutions:

- **"Wallet file not found"**: Generate a new wallet with `generate` command
- **"Invalid address"**: Check that the address starts with "RTC" and is properly formatted
- **"Insufficient balance"**: Check your balance before sending
- **"Connection refused"**: Verify the RustChain node is running and accessible

## Testing

Run the test suite:

```bash
cargo test
```

## Contributing

Contributions are welcome! Please ensure:

1. All code includes proper error handling
2. Tests are added for new functionality
3. Documentation is updated
4. Code follows Rust best practices

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- Check the RustChain documentation
- Open an issue on the RustChain repository
- Join the RustChain community discussions
