# RustChain Wallet - React Native

A practical mobile wallet application for RustChain (RTC) built with React Native and Expo.

## Features

- ✅ **Create New Wallet** - Generate Ed25519 key pairs with secure password encryption
- ✅ **Import Wallet** - Import existing wallets using hex or Base58-encoded private keys
- ✅ **View Balance** - Real-time balance queries from RustChain mainnet
- ✅ **Send Transactions** - Transfer RTC with dry-run validation
- ✅ **Transaction History** - View sent and received transactions
- ✅ **Secure Storage** - AES-256-GCM encrypted local key storage using Expo SecureStore

## Prerequisites

- Node.js 18+ and npm/yarn
- Expo CLI (`npm install -g expo-cli`)
- iOS Simulator (macOS) or Android Emulator, or physical device with Expo Go

## Installation

```bash
cd react-native-wallet

# Install dependencies
npm install

# Start Expo development server
npm start
```

## Running the App

### iOS Simulator (macOS only)
```bash
npm run ios
```

### Android Emulator
```bash
npm run android
```

### Web Browser
```bash
npm run web
```

### Physical Device
1. Install Expo Go from App Store (iOS) or Play Store (Android)
2. Scan the QR code shown in terminal after `npm start`

## Project Structure

```
react-native-wallet/
├── app/                      # Expo Router pages
│   ├── _layout.tsx          # Root navigation layout
│   ├── index.tsx            # Home screen (wallet list)
│   ├── send.tsx             # Send transaction screen
│   ├── history.tsx          # Transaction history
│   └── wallet/
│       ├── create.tsx       # Create new wallet
│       ├── import.tsx       # Import existing wallet
│       └── [name].tsx       # Wallet details screen
├── src/
│   ├── api/
│   │   └── rustchain.ts     # RustChain API client
│   ├── utils/
│   │   └── crypto.ts        # Ed25519 crypto utilities
│   └── storage/
│       └── secure.ts        # Encrypted wallet storage
├── package.json
├── app.json                 # Expo configuration
└── tsconfig.json           # TypeScript configuration
```

## Security Features

### Key Storage
- Private keys are encrypted with AES-256-GCM using PBKDF2-derived keys
- Password must be at least 8 characters
- Encrypted data stored in Expo SecureStore (iOS Keychain / Android Keystore)

### Transaction Safety
- **Dry-run validation** before submitting transactions
- Checks for:
  - Valid recipient address format
  - Sufficient balance (amount + fee)
  - Network connectivity
- Clear confirmation dialog before broadcast

### Replay Protection
- Nonce tracking prevents transaction replay
- Nonces persisted in secure storage

## API Integration

The app connects to the RustChain mainnet API:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/wallet/balance?miner_id={address}` | GET | Get wallet balance |
| `/api/stats` | GET | Get network info |
| `/api/transaction` | POST | Submit transaction |

### Balance Response
```json
{
  "miner": "RTC_ADDRESS",
  "balance": 100000000,
  "unlocked": 100000000,
  "locked": 0
}
```

## Testing

```bash
# Run unit tests
npm test

# Lint code
npm run lint
```

## Building for Production

```bash
# Install EAS CLI
npm install -g eas-cli

# Configure EAS
eas build:configure

# Build for all platforms
npm run build
```

## Development Commands

| Command | Description |
|---------|-------------|
| `npm start` | Start Expo dev server |
| `npm run ios` | Run on iOS simulator |
| `npm run android` | Run on Android emulator |
| `npm run web` | Run in web browser |
| `npm test` | Run tests |
| `npm run lint` | Lint code |
| `npm run build` | Build for production |

## Wallet Operations

### Create Wallet
1. Navigate to "Create New"
2. Generate a new key pair
3. Enter wallet name and password
4. Wallet is encrypted and saved locally

### Import Wallet
1. Navigate to "Import"
2. Select import method (hex or Base58)
3. Enter private key and validate
4. Set wallet name and password

### Send RTC
1. Open wallet details
2. Unlock with password
3. Tap "Send RTC"
4. Enter recipient address and amount
5. Run dry-run validation (recommended)
6. Confirm and submit

## Troubleshooting

### Network Errors
- Ensure device has internet connectivity
- Check RustChain node status at https://rustchain.org

### Import Failures
- Verify private key format (64 hex chars or valid Base58)
- Ensure key hasn't been corrupted

### Build Issues
```bash
# Clear cache
npm start -- --clear

# Reinstall dependencies
rm -rf node_modules
npm install
```

## License

MIT

## Contributing

This is a reference implementation for RustChain Issue #22.
