# RustChain Wallet - Setup and Testing Guide

## Quick Start

### 1. Install Dependencies

```bash
cd react-native-wallet
npm install
```

### 2. Start Development Server

```bash
npm start
```

This will launch the Expo CLI and display a QR code.

### 3. Run on Your Platform

**iOS Simulator (macOS only):**
```bash
npm run ios
```

**Android Emulator:**
```bash
npm run android
```

**Web Browser:**
```bash
npm run web
```

**Physical Device:**
1. Install Expo Go from App Store or Play Store
2. Scan the QR code from the terminal

## Testing

### Run Unit Tests

```bash
npm test
```

### Run Tests with Coverage

```bash
npm test -- --coverage
```

### Run Specific Test File

```bash
npm test -- crypto.test.ts
```

### Run Tests in Watch Mode

```bash
npm test -- --watch
```

## Build for Production

### Prerequisites

1. Install EAS CLI:
```bash
npm install -g eas-cli
```

2. Login to Expo:
```bash
eas login
```

3. Configure EAS:
```bash
eas build:configure
```

### Build Commands

```bash
# Build for all platforms
npm run build

# Or use EAS directly
eas build --platform ios
eas build --platform android
```

## Manual Testing Checklist

### Wallet Creation
- [ ] Navigate to "Create New"
- [ ] Generate a new wallet
- [ ] Verify address is displayed
- [ ] Enter wallet name and password (min 8 chars)
- [ ] Create wallet successfully
- [ ] Verify wallet appears in home screen list

### Wallet Import
- [ ] Navigate to "Import"
- [ ] Select import method (hex or Base58)
- [ ] Enter a valid private key
- [ ] Click "Validate Key"
- [ ] Verify address is shown
- [ ] Enter wallet name and password
- [ ] Import successfully

### Balance Display
- [ ] Open a wallet from home screen
- [ ] Verify address is displayed
- [ ] Click refresh to load balance
- [ ] Verify balance is shown (may be 0 for new wallets)

### Send Transaction
- [ ] Unlock wallet with password
- [ ] Click "Send RTC"
- [ ] Enter recipient address
- [ ] Enter amount
- [ ] Run dry-run validation
- [ ] Verify validation passes
- [ ] Confirm transaction
- [ ] Verify transaction submitted message

### Security Features
- [ ] Wallet locks after closing details screen
- [ ] Password required to unlock
- [ ] Wrong password shows error
- [ ] Private keys never shown in plain text

## Troubleshooting

### Common Issues

**"Cannot find module" errors:**
```bash
rm -rf node_modules
npm install
```

**Metro bundler issues:**
```bash
npm start -- --clear
```

**iOS build issues:**
```bash
cd ios
pod install
cd ..
```

**Android build issues:**
```bash
cd android
./gradlew clean
cd ..
```

### Network Issues

If balance queries fail:
1. Check internet connectivity
2. Verify RustChain node is accessible: `curl https://rustchain.org/api/stats`
3. Check firewall/proxy settings

### Development Tips

**Hot Reload:** Press `r` in terminal to reload
**Clear Cache:** Press `Shift + C` in terminal
**Open Dev Menu:** Shake device or press `Cmd + D` (iOS) / `Cmd + M` (Android)

## API Endpoints

The wallet interacts with these RustChain API endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/wallet/balance?address={address}` | GET | Get wallet balance |
| `/api/stats` | GET | Get network info and fees |
| `/wallet/transfer/signed` | POST | Submit signed transaction |

### Testing API Directly

```bash
# Check balance
curl "https://rustchain.org/wallet/balance?address=YOUR_ADDRESS"

# Check network status
curl "https://rustchain.org/api/stats"
```

## Security Considerations

### For Development
- Never commit `.env.local` files
- Use testnet for development when possible
- Don't use mainnet wallets with significant funds for testing

### For Production
- Enable code obfuscation in build settings
- Use certificate pinning for API calls
- Implement biometric authentication
- Add transaction signing confirmations

## Performance Optimization

### Build Optimizations
```bash
# Production build with optimizations
eas build --profile production
```

### Runtime Optimizations
- Enable Hermes engine (already default in Expo 51)
- Use React.memo for expensive components
- Implement proper FlatList optimizations

## Contributing

When contributing to this project:
1. Write tests for new features
2. Run `npm test` before committing
3. Run `npm run lint` to check code style
4. Update README.md if adding new features

## License

MIT License - See LICENSE file for details
