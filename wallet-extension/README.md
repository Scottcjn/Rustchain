# RustChain Browser Wallet Extension (Manifest V3)

Official non-custodial browser wallet extension for the RustChain Proof-of-Antiquity network (Bounty Scottcjn/rustchain-bounties#730).

## Security & Architecture Highlights
- **Manifest V3 Compliance**: Strict CSP policies forbidding `eval()`, inline script tags, and third-party script CDN loading.
- **Local Key Isolation**: Cryptographic operations occur strictly client-side via Web Crypto APIs (Ed25519 / AES-256-GCM).
- **Direct Node Interaction**: Connects exclusively to canonical RustChain nodes (`https://50.28.86.131` / `https://rustchain.org`).
- **Zero Telemetry / Tracking**: No analytics, external tracking, or third-party leakage.

## Loading in Chrome / Brave / Edge
1. Open `chrome://extensions/`
2. Enable **Developer mode** in the top right corner.
3. Click **Load unpacked** and select the `wallet-extension` directory.
4. The RustChain Wallet icon will appear in the toolbar.
