# RustChain MetaMask Snap

Enable MetaMask to interact with the RustChain blockchain by providing native RTC account management and transaction signing.

## What is a Snap?

Snaps are an open system that allows developers to extend the functionality of MetaMask. This snap enables MetaMask users to interact with RustChain without needing a separate wallet extension.

## Features

- **RustChain Accounts**: Create and manage RTC addresses within MetaMask
- **Transaction Signing**: Sign and send RTC transactions
- **Message Signing**: Sign messages for dApp authentication
- **Balance Queries**: Check RTC balance directly in MetaMask
- **dApp Compatibility**: EIP-1193 compatible interface

## Installation

### From npm (Recommended)

```bash
npm install rustchain-snap
```

### Development Installation

1. Clone the repository:
```bash
git clone https://github.com/Scottcjn/rustchain-bounties.git
cd rustchain-bounties/snap
```

2. Install dependencies:
```bash
npm install
```

3. Build the snap:
```bash
npm run build
```

4. Load in MetaMask:
   - Open MetaMask Flask (required for Snaps)
   - Go to Settings → Experimental → Snaps
   - Use the Snap debugger to load from `dist/bundle.js`

## Usage

### In MetaMask Flask

1. Install the snap via the MetaMask Snap interface
2. The snap will add RustChain account management to your MetaMask
3. Switch between Ethereum and RustChain accounts as needed

### For dApp Developers

Integrate RustChain support in your dApp:

```javascript
// Request RustChain account access
const accounts = await window.ethereum.request({
  method: 'rustchain_requestAccounts'
});

// Get balance
const balance = await window.ethereum.request({
  method: 'rustchain_getBalance',
  params: [accounts[0]]
});

// Send transaction
const txHash = await window.ethereum.request({
  method: 'rustchain_sendTransaction',
  params: [{
    from: accounts[0],
    to: 'recipient123...RTC',
    value: '10.0'
  }]
});

// Sign message
const signature = await window.ethereum.request({
  method: 'rustchain_signMessage',
  params: [{
    address: accounts[0],
    message: 'Hello, RustChain!'
  }]
});
```

### RPC Methods

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `rustchain_createAccount` | Create new RTC account | - | `{ address, publicKey }` |
| `rustchain_getAccounts` | Get all accounts | - | `string[]` |
| `rustchain_getBalance` | Get balance | `[address]` | `{ balance, address }` |
| `rustchain_sendTransaction` | Send RTC | `[{ from, to, value, memo }]` | `{ txHash, status }` |
| `rustchain_signMessage` | Sign message | `[{ address, message }]` | `{ signature, signedMessage }` |
| `rustchain_signTransaction` | Sign transaction | `[tx]` | `string` (signature) |
| `eth_requestAccounts` | Request access (EIP-1193) | - | `string[]` |
| `eth_accounts` | Get accounts (EIP-1193) | - | `string[]` |
| `eth_chainId` | Get chain ID | - | `string` |
| `eth_sendTransaction` | Send transaction (EIP-1193) | `[tx]` | `{ txHash }` |
| `personal_sign` | Sign message (EIP-1193) | `[message, address]` | `{ signature }` |

## Architecture

```
snap/
├── snap.manifest.json     # Snap manifest
├── package.json           # npm package config
├── src/
│   └── index.js          # Main snap logic
├── images/
│   └── icon.svg          # Snap icon
├── scripts/
│   └── build.js          # Build script
├── dist/
│   └── bundle.js         # Built snap (generated)
└── tests/
    └── snap.test.js      # Unit tests
```

## Configuration

Edit `snap.manifest.json` to configure:

- `version`: Snap version
- `proposedName`: Display name in MetaMask
- `initialPermissions`: Required permissions
- `source.location`: npm package info for distribution

### Required Permissions

```json
{
  "endowment:rpc": {
    "dapps": true,
    "snaps": true
  },
  "endowment:network-access": {},
  "snap_manageState": {},
  "snap_notify": {}
}
```

## Development

### Building

```bash
npm run build
```

This creates `dist/bundle.js` and updates the manifest with the SHA-256 checksum.

### Testing

```bash
npm test
```

### Watching for Changes

```bash
npm run watch
```

### Serving Locally

```bash
npm run serve
```

## Security Considerations

**MVP Implementation Notes:**

1. **Key Storage**: Currently uses simplified encryption. Production should implement:
   - Proper AES-GCM encryption
   - User password derivation with PBKDF2
   - Secure key storage using Snap's state management

2. **Transaction Signing**: MVP returns transaction hash. Production should:
   - Implement proper cryptographic signatures
   - Add transaction simulation
   - Include gas/fee estimation

3. **Network Communication**: Currently uses placeholder URLs. Production should:
   - Implement proper RPC client
   - Add retry logic and timeouts
   - Support multiple network endpoints

## Troubleshooting

### Snap not loading
- Ensure you're using MetaMask Flask (Snaps not in main MetaMask)
- Check MetaMask console for errors
- Verify `snap.manifest.json` is valid

### Transactions failing
- Verify recipient address format (ends with `RTC`)
- Check network connectivity to RustChain node
- Ensure sufficient balance

### dApp not connecting
- Refresh the dApp page after installing snap
- Check browser console for errors
- Verify snap permissions in MetaMask

## Publishing to npm

1. Update version in `package.json` and `snap.manifest.json`
2. Build the snap: `npm run build`
3. Publish: `npm publish`

## License

MIT - See LICENSE file

## Resources

- [MetaMask Snaps Documentation](https://docs.metamask.io/snaps/)
- [Snap API Reference](https://docs.metamask.io/snaps/reference/snaps-api/)
- [RustChain Documentation](https://rustchain.org)

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.
