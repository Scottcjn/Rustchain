# RustChain Wallet - React Native

A practical mobile wallet application for RustChain (RTC) built with React Native and Expo.

## Features

- ✅ **Create New Wallet** - Generate Ed25519 key pairs with secure password encryption
- ✅ **Import Wallet** - Import existing wallets using hex or Base58-encoded private keys
- ✅ **View Balance** - Real-time balance queries from RustChain mainnet
- ✅ **Send Transactions** - Transfer RTC with dry-run validation
- ✅ **Transaction History** - View sent and received transactions
- ✅ **Secure Storage** - AES-256-GCM encrypted local key storage using Expo SecureStore
- ✅ **QR Code Scanning** - Scan recipient addresses using device camera (expo-camera)
- ✅ **QR Code Display** - Display receive address as QR code for easy sharing
- ✅ **Biometric Authentication** - Face ID/Touch ID/Fingerprint authentication for sensitive actions
- ✅ **Graceful Fallback** - Password authentication when biometric unavailable

## Prerequisites

- Node.js 18+ and npm/yarn
- Expo CLI (`npm install -g expo-cli`)
- iOS Simulator (macOS) or Android Emulator, or physical device with Expo Go
- Camera permission (for QR scanning)
- Biometric hardware enrolled (Face ID, Touch ID, or Fingerprint) for biometric auth

## Installation

```bash
cd react-native-wallet

# Install dependencies
npm install

# Start Expo development server
npm start
```

## Platform Setup

### iOS Setup

1. **Camera Permission**: Add to `ios/Info.plist` (handled in app.json):
```xml
<key>NSCameraUsageDescription</key>
<string>This app needs camera access to scan QR codes for wallet addresses</string>
```

2. **Face ID Permission**: Add to `ios/Info.plist` (handled in app.json):
```xml
<key>NSFaceIDUsageDescription</key>
<string>This app uses Face ID to authenticate sensitive transactions</string>
```

### Android Setup

1. **Camera Permission**: Add to `AndroidManifest.xml` (handled in app.json):
```xml
<uses-permission android:name="android.permission.CAMERA" />
```

2. **Biometric Permission**: Add to `AndroidManifest.xml` (handled in app.json):
```xml
<uses-permission android:name="android.permission.USE_BIOMETRIC" />
<uses-permission android:name="android.permission.USE_FINGERPRINT" />
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
│   ├── send.tsx             # Send transaction screen (QR + Biometric)
│   ├── history.tsx          # Transaction history
│   └── wallet/
│       ├── create.tsx       # Create new wallet
│       ├── import.tsx       # Import existing wallet
│       └── [name].tsx       # Wallet details screen (QR display)
├── src/
│   ├── api/
│   │   └── rustchain.ts     # RustChain API client
│   ├── utils/
│   │   ├── crypto.ts        # Ed25519 crypto utilities
│   │   └── biometric.ts     # Biometric authentication utilities
│   ├── components/
│   │   └── QRScanner.tsx    # QR code scanner component
│   └── storage/
│       └── secure.ts        # Encrypted wallet storage
├── package.json
├── app.json                 # Expo configuration (includes permissions)
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

### Biometric Authentication Gate
- **Face ID / Touch ID / Fingerprint** required before sending transactions
- Graceful fallback to password when biometric unavailable
- Supports iOS Face ID, iOS Touch ID, Android Fingerprint, Android Face Recognition
- Biometric status indicator shows authentication state
- Session-based verification (verify once per session)

### QR Code Security
- **Address validation** before accepting scanned QR codes
- Warns if scanned content doesn't match expected address format
- Flash/torch control for low-light scanning
- Permission-based camera access with clear user prompts

### Replay Protection
- Nonce tracking prevents transaction replay
- Nonces persisted in secure storage

## New Features (Issue #22)

### QR Code Scanning for Addresses

**Send Screen:**
- Tap the camera button (📷) next to the recipient address field
- Position QR code within the frame
- Automatically validates scanned address format
- Supports standard wallet address QR codes

**Receive (Wallet Details):**
- Tap the QR button (📷) next to your wallet address
- View your receive address in a shareable format
- Copy address to clipboard with one tap
- Warning about sending only RTC to this address

### Biometric Authentication

**How it works:**
1. Unlock wallet with password (existing flow)
2. When attempting to send, biometric prompt appears
3. Authenticate with Face ID/Touch ID/Fingerprint
4. Upon success, biometric badge shows "Verified"
5. Proceed with transaction confirmation

**When biometric is unavailable:**
- App detects lack of biometric hardware or enrollment
- Falls back to password-only authentication
- Clear indicator shows biometric status

**Supported biometric types:**
- iOS: Face ID, Touch ID
- Android: Fingerprint, Face Recognition, Iris
- Graceful degradation when unavailable

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
