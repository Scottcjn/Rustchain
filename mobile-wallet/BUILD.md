# Mobile Wallet Build Notes (iOS + Android)

## Prerequisites
- Node.js 20+
- npm 10+
- Xcode (for iOS)
- Android Studio + SDK (for Android)
- Expo CLI (`npx expo`)

## Install
```bash
cd mobile-wallet
npm install
```

## Start dev server
```bash
npm run start
```

## Android build/dev run
```bash
npm run android
```

## iOS build/dev run
```bash
npm run ios
```

## Production packaging (EAS recommended)
```bash
# install eas CLI once
npm i -g eas-cli

# configure project
cd mobile-wallet
eas build:configure

# android apk/aab
eas build -p android

# ios ipa
eas build -p ios
```

## Current implementation status
- Scaffolded flows: onboarding, session, receive, send, history, stats, biometric gate, QR scanner.
- Native integrations pending final wiring:
  - `expo-local-authentication`
  - `expo-camera` / barcode scanner
  - secure persistent storage for wallet secrets
