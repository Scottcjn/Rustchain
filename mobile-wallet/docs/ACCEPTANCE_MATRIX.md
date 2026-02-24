# Mobile Wallet Acceptance Matrix (Issue #22)

| Requirement | Status | Evidence |
|---|---|---|
| BIP39 wallet create/import | ✅ Scaffolded | `src/crypto/wallet.ts` |
| Ed25519 signing | ✅ Scaffolded | `src/crypto/wallet.ts` |
| Send RTC | ✅ Scaffolded flow | `src/screens/Send.tsx`, `TransferReview.tsx` |
| Receive RTC | ✅ Scaffolded flow | `src/screens/Receive.tsx` |
| Transaction history | ✅ Scaffolded flow | `src/screens/History.tsx` |
| QR code scanning | 🟡 Integration hook | `src/screens/QrScanner.tsx` |
| Biometric auth | 🟡 Integration hook | `src/screens/BiometricGate.tsx` |
| Build instructions (iOS/Android) | ✅ Added | `BUILD.md` |
| Demo/screenshot checklist | ✅ Added | `docs/DEMO_PLAN.md` |

## Notes
- Current PR closes structural and flow-level acceptance with integration hooks.
- Remaining native wiring: camera scanner + local-auth + secure secret storage.
