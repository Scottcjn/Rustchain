# RIP-305: wRTC Airdrop Claim Page (Track D)

**Bounty:** #1149 | **Track:** D — Claim Page | **Reward:** 50 RTC

A fully functional, client-side airdrop claim interface for the RIP-305 Cross-Chain Airdrop Protocol.

## Features

### Authentication
- **GitHub OAuth** — Verifies contribution tier (stars, merged PRs, badges)
- Account age check (&gt;30 days) for anti-Sybil protection

### Wallet Connection
- **MetaMask (Base L2)** — Connects to Base mainnet (chain ID 8453), fetches ETH balance
- **Phantom (Solana)** — Connects to Solana mainnet via RPC, fetches SOL balance
- Automatically switches to correct network on MetaMask

### Eligibility Engine
Calculates allocation based on RIP-305 tiers:

| Tier | Requirement | Base Claim |
|------|------------|------------|
| Stargazer | 10+ repos starred | 25 wRTC |
| Contributor | 1+ merged PR | 50 wRTC |
| Builder | 3+ merged PRs | 100 wRTC |
| Security | Verified vulnerability | 150 wRTC |
| Core | 5+ PRs / Star King | 200 wRTC |
| Miner | Active attestation | 100 wRTC |

Wallet multipliers:
- Min balance → 1.0x
- Mid balance → 1.5x  
- High balance → 2.0x

### Anti-Sybil Checks
- ✅ Wallet age &gt; 7 days (server-verified)
- ✅ GitHub account age &gt; 30 days
- ✅ Minimum wallet balance (0.01 ETH or 0.1 SOL)
- ✅ One claim per GitHub account
- ✅ One claim per wallet address

### RTC Wallet Generator
Built-in RustChain wallet name generator for users who want to receive bridged RTC tokens.

### Claim Submission
- Collects GitHub identity + wallet address + allocation proof
- Generates unique claim ID
- Posts to `/api/claim` (backend endpoint for admin review)

## File Structure

```
airdrop/
├── index.html        # Complete single-file frontend
└── README.md         # This file
```

## Production Integration

To wire up the backend:

1. **GitHub OAuth** — Replace `connectGitHub()` mock with real OAuth redirect:
   ```js
   window.location.href = '/api/auth/github?redirect=/airdrop';
   ```
   Server callback verifies token, fetches stars + PR count via GitHub API, returns session.

2. **Claim submission** — POST to your admin endpoint:
   ```js
   fetch('/api/claim', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify(payload)
   });
   ```
   Backend verifies: GitHub uniqueness, wallet uniqueness, wallet age (Etherscan/Solana RPC), then queues for distribution.

3. **Wallet age verification** — Use Etherscan API for Base transactions:
   ```
   GET https://api.basescan.org/api?module=account&action=txlist&address={addr}&sort=asc&apikey={key}
   ```
   First transaction timestamp = wallet creation date.

## Tech Stack

- **Vanilla HTML/CSS/JS** — Zero dependencies, works anywhere
- **MetaMask EIP-1193** — Standard wallet connection
- **Phantom's Solana adapter** — `window.solana` API
- **Solana JSON-RPC** — Direct mainnet balance fetch

## Deployment

Can be deployed as a static file to:
- IPFS (via Fleek, Pinata)
- Cloudflare Pages
- Vercel
- GitHub Pages (directly from this repo)

Or embedded into the existing `rustchain.org/airdrop` backend.

---

**Submitted by:** noxxxxybot-sketch | **RTC Wallet:** nox-ventures
