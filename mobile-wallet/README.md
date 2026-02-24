# RustChain Mobile Wallet (React Native/Expo)

Scaffold for bounty #22.

## Included
- BIP39 wallet create/import module
- Ed25519 signing helper
- Send/receive API client stubs
- Transaction history fetch flow
- QR + biometric integration hooks

## Run
```bash
cd mobile-wallet
npm install
npm run start
```


## Increment in this update
- Added transaction history screen scaffold wired to `wallet/history` API
- Added miner_id input + navigation hook from Home

- Added send screen scaffold wired to transfer API
- Added biometric confirmation hook note before transfer finalize
- Added security hooks screen for biometric lock + QR scanner integration placeholders
- Added receive screen scaffold with wallet display and QR-generation hook
- Added wallet session store scaffold (`src/store/session.ts`) with persistence hooks for AsyncStorage integration
- Added Price/Stats screen scaffold (`/epoch` + `/api/miners`) for `/price` parity on mobile
- Added onboarding checklist screen scaffold for first-run wallet UX and acceptance validation
- Added biometric gate screen scaffold (mock verify) for secure-action preflight UX
- Added QR scanner screen scaffold with camera/barcode integration notes
- Added transfer review screen scaffold for pre-submit confirmation flow


## Build instructions
See `BUILD.md` for iOS/Android local runs and EAS packaging flow.

## Demo / QA checklist
See `docs/DEMO_PLAN.md` for demo capture and acceptance validation steps.
