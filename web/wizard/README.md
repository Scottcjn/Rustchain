# RustChain Miner Setup Wizard

A browser-based, single-file wizard that guides users through setting up the RustChain miner — no command-line knowledge required.

## Live Version

Open `setup-wizard.html` directly in your browser, or visit the hosted version.

## Features

- **7-step guided wizard**: Platform Detection → Python Check → Wallet Setup → Download → Configure → Test Connection → First Attestation
- **Pure frontend**: Single HTML file, no build step, no server required
- **Platform auto-detection**: Detects Linux, macOS, Raspberry Pi automatically
- **Ed25519 wallet generation**: Uses Web Crypto API to generate a keypair directly in the browser
- **Copy-paste commands**: Every step includes a ready-to-run command with a copy button
- **Network test**: Verifies connectivity to the RustChain node and attestation system
- **Mobile friendly**: Responsive layout, works on phones and tablets
- **Dark theme**: GitHub-inspired dark UI

## Usage

1. Open `setup-wizard.html` in any modern browser (Chrome, Firefox, Safari, Edge)
2. Follow each step in order
3. Copy and run commands in your terminal
4. Complete the first attestation to start earning RTC

## Bounty

This wizard was built as part of the [RustChain Bounty #47](https://github.com/Scottcjn/rustchain-bounties/issues/47) — 50 RTC payout.

**Wallet for bounty payment**: `eB51DWp1uECrLZRLsE2cnyZUzfRWvzUzaJzkatTpQV9`

## Technical Details

- **No external dependencies** — all CSS and JS are inline
- **Wallet generation** — uses Web Crypto API (Ed25519) with a BIP39 wordlist fallback for seed phrase display
- **Network requests** — uses XMLHttpRequest for node health and attestation checks (CORS must be allowed by the node)
- **Platform detection** — User-Agent based with architecture reporting

## File Structure

```
web/wizard/
├── setup-wizard.html   # The wizard (open directly in browser)
└── README.md           # This file
```

## Browser Compatibility

- Chrome 60+
- Firefox 55+
- Safari 11+
- Edge 79+

Requires Web Crypto API support.
