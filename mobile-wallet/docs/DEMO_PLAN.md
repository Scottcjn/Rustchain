# Mobile Wallet Demo / QA Plan

Use this checklist when recording demo video or validating release candidate.

## Core flows
- [ ] Create mnemonic wallet (BIP39)
- [ ] Import existing mnemonic
- [ ] Verify Ed25519 public key generation
- [ ] Save/load session continuity
- [ ] Open Receive screen and verify wallet id display
- [ ] Open Send -> Review -> Submit flow
- [ ] Open History screen and verify API rendering
- [ ] Open Price/Stats and verify epoch + miner fetch
- [ ] Open Biometric Gate mock flow
- [ ] Open QR Scanner scaffold flow

## Security / UX checks
- [ ] No private key persisted in plain text
- [ ] Secure-action preflight shown before transfer submit
- [ ] Error handling visible for failed API responses
- [ ] Build docs verified on Android/iOS dev setup

## Artifacts to collect
- [ ] Screenshots for each screen
- [ ] 1-2 minute demo capture
- [ ] Device + OS version used
