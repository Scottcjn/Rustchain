# RustChain Wallet Extension

Official browser extension for managing RTC tokens and interacting with RustChain dApps.

## Features

- **Wallet Management**: Create and manage multiple RustChain wallets
- **Send/Receive RTC**: Transfer tokens with memo support
- **Message Signing**: Sign messages for dApp authentication
- **dApp Integration**: Injected provider for seamless dApp interaction
- **Transaction History**: View your transaction activity
- **Secure Storage**: Encrypted key storage in browser
- **MetaMask Snap Fallback**: Integrated path to use MetaMask Snap when available

## Installation

### Development

1. Clone the repository:
```bash
git clone https://github.com/Scottcjn/rustchain-bounties.git
cd rustchain-bounties/extension
```

2. Load in Chrome/Brave:
   - Open `chrome://extensions/`
   - Enable "Developer mode"
   - Click "Load unpacked"
   - Select the `extension` directory

3. The extension icon should appear in your browser toolbar

### Firefox

1. Open `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on"
3. Select `manifest.json` from the extension directory

## Usage

### Creating a Wallet

1. Click the RustChain extension icon
2. Click "+ New" to create a new wallet
3. Your wallet address will be displayed (ends with `RTC`)

### Sending RTC

1. Click "Send" button
2. Enter recipient address (must end with `RTC`)
3. Enter amount
4. Optionally add a memo
5. Click "Send" to submit transaction

### Receiving RTC

1. Click "Receive" button
2. Copy your address or share the QR code
3. Send only RTC tokens to this address

### Signing Messages

1. Click "Sign" button
2. Enter the message to sign
3. Click "Sign" to generate signature
4. Copy the signature for use in dApps

### Connecting to dApps

The extension automatically injects a `window.rustchain` provider for dApps to use:

```javascript
// Check if RustChain is available
if (window.rustchain) {
  // Request account access
  const accounts = await window.rustchain.request({
    method: 'rustchain_requestAccounts'
  });

  // Get balance
  const balance = await window.rustchain.request({
    method: 'rustchain_getBalance',
    params: [accounts[0]]
  });

  // Send transaction
  const tx = await window.rustchain.request({
    method: 'rustchain_sendTransaction',
    params: [{
      from: accounts[0],
      to: 'recipient123...RTC',
      value: '10.0'
    }]
  });
}
```

## Architecture

```
extension/
├── manifest.json          # Extension manifest (MV3)
├── icons/                 # Extension icons
├── src/
│   ├── background/        # Service worker
│   │   └── background.js  # Wallet state, transactions, Snap fallback
│   ├── content/           # Content scripts
│   │   ├── content.js     # Provider injection
│   │   └── injected.js    # window.rustchain API
│   ├── popup/             # Popup UI
│   │   ├── popup.html
│   │   ├── popup.js       # UI logic with Snap detection
│   │   └── popup.css
│   └── utils/             # Utility functions
│       └── validation.js  # Address/transaction validation
└── tests/
    ├── extension.test.js  # Unit tests
    └── send-sign-flow.test.js  # End-to-end flow tests
```

## API Reference

### Background Messages

| Message Type | Payload | Response |
|-------------|---------|----------|
| `CREATE_WALLET` | - | `{ address, publicKey }` |
| `GET_WALLETS` | - | `{ wallets: [...] }` |
| `SET_ACTIVE_WALLET` | `{ address }` | `{ success }` |
| `GET_BALANCE` | `{ address }` | `{ balance }` |
| `CREATE_TRANSACTION` | `{ from, to, amount, memo }` | `{ txHash }` |
| `SIGN_MESSAGE` | `{ address, message }` | `{ signature }` |
| `CONNECT_SITE` | `{ origin }` | `{ success }` |
| `IS_CONNECTED` | `{ origin }` | `{ connected }` |

### Injected Provider Methods

```typescript
interface RustChainProvider {
  isRustChain: true;
  chainId: string;
  selectedAddress: string | null;

  request(args: {
    method: string;
    params?: any[];
  }): Promise<any>;

  enable(): Promise<string[]>;

  send(method: string, params?: any[]): Promise<any>;
  send(payload: object): Promise<any>;

  sendAsync(payload: object): Promise<any>;

  on(event: string, callback: Function): void;
  removeListener(event: string, callback: Function): void;
}
```

## Testing

### Run All Tests

```bash
cd extension
node --test tests/*.test.js
```

### Expected Output

```
==================================================
TEST SUMMARY
==================================================
Total: 30
✅ Passed: 30
❌ Failed: 0
==================================================
🎉 ALL TESTS PASSED!
```

### Test Coverage

- **Address Validation**: Format, suffix, length checks
- **Transaction Validation**: Required fields, balance, recipient
- **Message Validation**: String type, empty check, length limit
- **Send Flow**: Transaction creation, signing, submission
- **Sign Flow**: Message hashing, signature generation
- **Snap Integration**: Detection, send via Snap, sign via Snap
- **Fallback Behavior**: Extension-first, Snap-first modes

## MetaMask Snap Integration

The extension includes integrated fallback to MetaMask Snap:

1. **Snap Detection**: Automatically detects if MetaMask Snap is available
2. **Fallback Modes**:
   - `extension-first` (default): Use extension, fallback to Snap
   - `snap-first`: Try Snap first, fallback to extension
3. **Unified API**: Same methods work regardless of path

### Snap Fallback Flow

```
User Action → Check Snap Available?
              ├─ Yes → Try Snap
              │        ├─ Success → Return result
              │        └─ Fail → Fallback to Extension
              └─ No → Use Extension
```

## Security

- Private keys are encrypted before storage
- Keys never leave the browser unencrypted
- Transaction confirmation required for all sends
- Site connections require user approval

**Important**: This is an MVP implementation. For production use:
- Implement proper AES-GCM encryption with user password
- Add hardware wallet support
- Implement secure key derivation (BIP39/BIP44)
- Add transaction simulation and warnings

## Development

### Building Icons

```bash
cd extension/icons
python3 generate_icons.py
```

### Debugging

1. Open `chrome://extensions/`
2. Find RustChain Wallet
3. Click "Inspect views: service worker" for background
4. Right-click extension popup → "Inspect" for UI

## Troubleshooting

### Extension not loading
- Ensure you're in Developer mode
- Check console for manifest errors

### Transactions failing
- Verify recipient address ends with `RTC`
- Ensure sufficient balance
- Check network connectivity

### dApp not detecting wallet
- Refresh the page after loading extension
- Check console for injection errors

### Snap not detected
- Ensure MetaMask Flask is installed
- Verify RustChain Snap is installed in MetaMask
- Check browser console for detection logs

## Verification Commands

### Quick Verification

```bash
# 1. Run tests
cd extension
node --test tests/*.test.js

# 2. Verify manifest
cat manifest.json | python3 -m json.tool

# 3. Check file structure
find src -type f -name "*.js" | sort
```

### End-to-End Verification

```bash
# 1. Load extension in Chrome
# 2. Create wallet via "+ New" button
# 3. Verify address ends with "RTC"
# 4. Click "Send" and verify validation works
# 5. Click "Sign" and verify message signing
# 6. Install MetaMask Flask + RustChain Snap
# 7. Verify Snap detection in console
```

## License

MIT - See LICENSE file

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## Related

- [MetaMask Snap](../snap/README.md) - MetaMask integration
- [RustChain Documentation](https://rustchain.org)
