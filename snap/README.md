# RustChain MetaMask Snap

Enable MetaMask to interact with the RustChain blockchain by providing native RTC account management and transaction signing.

## What is a Snap?

Snaps are an open system that allows developers to extend the functionality of MetaMask. This snap enables MetaMask users to interact with RustChain without needing a separate wallet extension.

## Features

- **RustChain Accounts**: Create and manage RTC addresses within MetaMask
- **Transaction Signing**: Sign and send RTC transactions with user confirmation
- **Message Signing**: Sign messages for dApp authentication with approval dialog
- **Balance Queries**: Check RTC balance directly in MetaMask
- **dApp Compatibility**: EIP-1193 compatible interface
- **User Confirmation**: All sensitive operations require explicit user approval

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

4. Load in MetaMask Flask:
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
| `rustchain_getTransactionHistory` | Get tx history | `[address]` | `Transaction[]` |
| `eth_requestAccounts` | Request access (EIP-1193) | - | `string[]` |
| `eth_accounts` | Get accounts (EIP-1193) | - | `string[]` |
| `eth_chainId` | Get chain ID | - | `string` |
| `eth_sendTransaction` | Send transaction (EIP-1193) | `[tx]` | `{ txHash }` |
| `personal_sign` | Sign message (EIP-1193) | `[message, address]` | `{ signature }` |

## Architecture

```
snap/
├── snap.manifest.json     # Snap manifest with permissions
├── package.json           # npm package config
├── src/
│   └── index.js          # Main snap logic with RPC handlers
├── images/
│   └── icon.svg          # Snap icon
├── scripts/
│   └── build.js          # Build script (bundles + checksums)
├── dist/
│   └── bundle.js         # Built snap (generated)
└── tests/
    ├── snap.test.js      # Unit tests
    └── snap-integration.test.js  # Integration tests
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

### Expected Output

```
==================================================
SNAP INTEGRATION TEST SUMMARY
==================================================
Total: 16
✅ Passed: 16
❌ Failed: 0
==================================================
🎉 ALL SNAP TESTS PASSED!
```

### Watching for Changes

```bash
npm run watch
```

### Serving Locally

```bash
npm run serve
```

## Testing

### Run All Tests

```bash
cd snap
npm test
# or
node --test tests/*.test.js
```

### Test Coverage

- **Account Management**: Create, list, retrieve accounts
- **Balance Query**: Network fetch, error handling
- **Send Transaction**: Validation, confirmation, submission
- **Sign Message**: User approval, signature generation
- **EIP-1193 Compatibility**: eth_* method handlers
- **Error Handling**: Unknown methods, user rejection, network errors

### Verification Commands

```bash
# 1. Run tests
node --test tests/*.test.js

# 2. Build snap
npm run build

# 3. Verify manifest
cat snap.manifest.json | python3 -m json.tool

# 4. Check bundle exists
ls -la dist/bundle.js

# 5. Verify shasum matches manifest
sha256sum dist/bundle.js
```

### End-to-End Verification

```bash
# 1. Build the snap
npm run build

# 2. Load in MetaMask Flask debugger
# 3. Create account via rustchain_createAccount
# 4. Verify address ends with "RTC"
# 5. Send transaction - verify confirmation dialog appears
# 6. Sign message - verify approval dialog appears
# 7. Test eth_* methods for dApp compatibility
```

## Security Considerations

**MVP Implementation Notes:**

1. **Key Storage**: Currently uses simplified encryption. Production should implement:
   - Proper AES-GCM encryption
   - User password derivation with PBKDF2
   - Secure key storage using Snap's state management

2. **Transaction Signing**: MVP returns transaction hash. Production should:
   - Implement proper cryptographic signatures (Ed25519)
   - Add transaction simulation
   - Include gas/fee estimation

3. **Network Communication**: Currently uses placeholder URLs. Production should:
   - Implement proper RPC client
   - Add retry logic and timeouts
   - Support multiple network endpoints

4. **User Confirmation**: All sensitive operations show confirmation dialogs:
   - Transaction send: Shows recipient, amount, memo
   - Message signing: Shows message content
   - Account access: Shows dApp connection request

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

### Dialog not appearing
- Ensure snap has required permissions
- Check MetaMask notification settings
- Verify snap is installed and enabled

## Publishing to npm

1. Update version in `package.json` and `snap.manifest.json`
2. Build the snap: `npm run build`
3. Verify manifest shasum matches bundle
4. Publish: `npm publish`

## License

MIT - See LICENSE file

## Resources

- [MetaMask Snaps Documentation](https://docs.metamask.io/snaps/)
- [Snap API Reference](https://docs.metamask.io/snaps/reference/snaps-api/)
- [RustChain Documentation](https://rustchain.org)

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## Related

- [Wallet Extension](../extension/README.md) - Browser extension alternative
- [RustChain Node](../node/) - Backend node implementation
