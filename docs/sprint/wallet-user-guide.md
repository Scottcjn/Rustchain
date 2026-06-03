# RustChain Wallet User Guide

> Complete guide for managing your RTC wallet — creating, securing, sending, and receiving.

---

## Wallet Address Format

Every RustChain wallet address follows a fixed format:

```
RTC + 40 hexadecimal characters
```

**Example:**
```
RTCa3f82d9c1e4b07f5a2d6c8e9b0f1d3e2a4c5b7f8
```

- Always starts with the prefix `RTC`
- Followed by exactly 40 lowercase hex characters (`0-9`, `a-f`)
- Total length: 43 characters
- Never share your **private key** — only share your public wallet address

---

## Wallet Types

RustChain provides three wallet interfaces suited to different use cases:

### 1. CLI Wallet

The command-line wallet is the primary interface for miners and power users.

**Install:**
```bash
# Via the RustChain installer
curl -sSL https://rustchain.org/install.sh | bash

# Or clone and build from source
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/rustchain-wallet
cargo build --release
```

**Generate a new wallet:**
```bash
./rtc-wallet generate
# Output:
#   Public address : RTCa3f82d9c1e4b07f5a2d6c8e9b0f1d3e2a4c5b7f8
#   Private key    : [REDACTED — save this securely]
#   Seed phrase    : [12 words — write these down offline]
```

**Check balance:**
```bash
./rtc-wallet balance --address RTCa3f82d9c1e4b07f5a2d6c8e9b0f1d3e2a4c5b7f8
# Or via API:
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET" | jq .
```

### 2. Web Wallet

Access your wallet from any browser at **https://rustchain.org/wallet**

- No installation required
- Supports key import via seed phrase or private key
- View balance, transaction history, and epoch rewards
- Initiate transfers with a confirmation dialog

> ⚠️ Always verify you are on the official domain (`rustchain.org`) before entering keys.

### 3. Browser Extension

The RustChain browser extension integrates your wallet with dApps and the x402 payment layer.

**Install:**
- Chrome/Brave: Search "RustChain Wallet" in the Chrome Web Store
- Firefox: Available via the add-ons portal
- Source: `wallet-extension/` in this repo

**Features:**
- One-click payments via x402 protocol
- Auto-detect RustChain payment links on any page
- Hardware key signing support (Ledger, Trezor)
- Pop-up balance display without leaving the current tab

---

## Creating a Wallet

### Step-by-Step (CLI)

```bash
# 1. Generate keypair
./rtc-wallet generate --output ~/.rtc/wallet.json

# 2. Confirm your address
./rtc-wallet info --wallet ~/.rtc/wallet.json

# 3. Back up your seed phrase (see section below)
```

### Step-by-Step (Web)

1. Go to `https://rustchain.org/wallet`
2. Click **Create New Wallet**
3. Write down your 12-word seed phrase — **do not screenshot it**
4. Confirm two random words from the seed phrase
5. Your wallet address is now ready

---

## Backing Up Your Keys

Your wallet is only as safe as your backup. Two pieces of data matter:

| What | Description | How to store |
|------|-------------|--------------|
| **Seed phrase** | 12 words that can regenerate your private key | Paper, metal plate, offline password manager |
| **Private key** | Hex string — direct signing authority | Encrypted file, hardware wallet |

**Rules:**
- Write the seed phrase on paper and store it in a physically secure location
- Never type your seed phrase into any website you didn't navigate to yourself
- Never store seed phrases in cloud notes, screenshots, or email drafts
- Test restoring from backup before sending any funds to the wallet

**Restore from seed phrase (CLI):**
```bash
./rtc-wallet restore --seed "word1 word2 word3 ... word12"
```

---

## Sending RTC

### CLI Transfer

```bash
./rtc-wallet send \
  --from RTCa3f82d9c1e4b07f5a2d6c8e9b0f1d3e2a4c5b7f8 \
  --to   RTCb9e71c3d2f5a4e8b0c6d1f9a2e4b7c8d3f5a6e2 \
  --amount 10.5 \
  --wallet ~/.rtc/wallet.json
```

**Always do a small test transfer first** before sending large amounts.

### Signed Transfer API

For programmatic use:
```bash
curl -X POST https://rustchain.org/wallet/transfer/signed \
  -H "Content-Type: application/json" \
  -d '{
    "from_address": "RTCa3f82d9c1e4b07f5a2d6c8e9b0f1d3e2a4c5b7f8",
    "to_address": "RTCb9e71c3d2f5a4e8b0c6d1f9a2e4b7c8d3f5a6e2",
    "amount_rtc": 10.5,
    "nonce": 12345,
    "memo": "",
    "public_key": "<ed25519-public-key-hex>",
    "signature": "<ed25519-signature-hex>",
    "chain_id": "rustchain-mainnet-v2"
  }'
```

See `docs/API.md` for the full signing specification.

---

## Receiving RTC

Simply share your public wallet address. It is safe to share publicly.

- Epoch mining rewards are deposited automatically at settlement
- Peer transfers appear after block confirmation (~10 minutes)
- Check incoming transactions:

```bash
curl -sk "https://rustchain.org/wallet/history?address=RTCa3f82..." | jq .
```

---

## Security Best Practices

1. **Never share your private key or seed phrase** — not with support, not with the team
2. **Verify addresses before sending** — copy-paste, then double-check the first and last 6 chars
3. **Use hardware wallets** for large balances (Ledger/Trezor supported via browser extension)
4. **Enable 2FA** on any web wallet login if available
5. **Keep your wallet software updated** — security patches matter
6. **Be skeptical of DMs** — the RustChain team will never ask for your keys
7. **Air-gap key generation** for high-value wallets — generate offline, never touch the internet
8. **Monitor your balance** periodically for unexpected changes

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Balance shows 0 | Epoch not yet settled | Wait ~24h; check `/api/miners` |
| Wrong address shown | Querying wrong `miner_id` | Match exactly what the miner was started with |
| RTC vs wRTC confusion | Different tokens | RTC = native; wRTC = Solana bridge token |
| SSL warning on API | Self-signed TLS | Use `curl -sk` (expected in current release) |

---

*See also: `docs/API.md`, `docs/epoch-settlement.md`, `docs/MULTISIG_WALLET_GUIDE.md`*
