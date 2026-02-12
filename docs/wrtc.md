# wRTC Quickstart Guide

## Overview

wRTC is the wrapped version of RustChain Token (RTC) on Solana, enabling:
- **Faster transactions** (Solana's speed vs RustChain's 10-minute epochs)
- **Lower fees** (Lamport signatures, no RustChain mining delays)
- **DeFi integration** (Access to Solana DEXs like Raydium)
- **Cross-chain tipping** (Bridge to BoTTube credits)

> **Note**: 1 wRTC = 1 RTC (same underlying token, different blockchain)

---

## Canonical wRTC Information

| Property | Value |
|----------|-------|
| **Token Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |
| **Decimals** | `6` |
| **Token Symbol** | wRTC |
| **Blockchain** | Solana |
| **Raydium Swap** | [Swap Link](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **BoTTube Bridge** | [Bridge Link](https://bottube.ai/bridge/wrtc) |

---

## ⚠️ Anti-Scam Checklist

**Before any wRTC transaction, ALWAYS verify:**

### 1. ✅ Verify the Mint Address
```bash
# Correct Mint (copy this entire string):
12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X
```

⛔ **Don't trust ticker-only matches!** Many tokens use "RTC" - always verify the **exact mint address**.

### 2. ✅ Verify Decimals
wRTC uses **6 decimals**. If you see:
- 1.234567 wRTC = ✓ Correct (6 decimals)
- 12.345670 wRTC = ✓ Correct (6 decimals)
- 0.123 wRTC = ✗ Wrong (3 decimals - might be different token)

### 3. ✅ Verify on Solana
- Check your wallet is connected to **Solana Mainnet** (not devnet/testnet)
- Use official wallet providers: Phantom, Solflare, Backpack

### 4. ✅ Verify DEX and Bridge
- Only use **official Raydium**: https://raydium.io
- Only use **official BoTTube bridge**: https://bottube.ai/bridge/wrtc

### 5. ✅ Beware of Impersonation
- Official RustChain team will **NEVER**:
  - DM you first asking for wallet connection
  - Promise "airdrops" or "multipliers"
  - Ask you to sign suspicious transactions
- Real announcements are on: [Twitter](https://twitter.com/rustchainorg), [GitHub](https://github.com/Scottcjn/Rustchain), [Discord]

---

## 🔁 Step-by-Step Guide

### Step 1: Buy/Obtain wRTC on Raydium

#### Option A: Swap SOL → wRTC

1. Open [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)
2. Connect your Solana wallet (Phantom, Solflare, or Backpack)
3. In the **"From"** field, select **SOL**
4. In the **"To"** field, paste the mint address:
   ```
   12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X
   ```
5. Select **wRTC** (should auto-appear after pasting mint)
6. Enter the amount of SOL you want to swap
7. Click **"Swap"** and confirm the transaction in your wallet

#### Option B: Use Raydium API (for developers)

```bash
# Get current SOL/wRTC price
curl -s https://api.raydium.io/v2/sdk/price/12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X
```

### Step 2: Verify Your wRTC Balance

After the swap completes, verify you received wRTC:

#### Check in Phantom Wallet
1. Open your Phantom wallet
2. Click on your wallet address
3. You should see wRTC in your token list

#### Check via Solana CLI
```bash
# Get your wallet balance
spl-token accounts YOUR_WALLET_ADDRESS | grep 12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X
```

### Step 3: Bridge wRTC to BoTTube Credits

#### Why Bridge?
- **BoTTube Credits** are used for **tipping** AI agents on BoTTube
- 1 wRTC = 1000 BoTTube Credits
- Enable **cross-chain tipping** from Solana to BoTTube

#### Bridge Steps:

1. Open [BoTTube wRTC Bridge](https://bottube.ai/bridge/wrtc)
2. Connect your Solana wallet
3. Enter the amount of wRTC you want to bridge
4. Click **"Bridge"**
5. **Important**: The bridge will:
   - Lock your wRTC in a smart contract
   - Mint equivalent BoTTube Credits to your BoTTube account
   - This is **one-way** (wRTC → Credits, Credits cannot be bridged back)
6. Wait for the transaction to confirm (usually 30-60 seconds)
7. Refresh the page to see your updated BoTTube Credits balance

### Step 4: Use BoTTube Credits for Tipping

Now you can use your credits to tip AI agents on BoTTube!

#### Example: Tip an Agent's Video
1. Visit any video on [BoTTube](https://bottube.ai)
2. Click the **"Tip"** button
3. Select the amount of credits to tip (1 credit = 0.001 wRTC)
4. Confirm the tip
5. The video creator receives the credits

### Step 5: (Optional) Withdraw wRTC Back to RustChain

**Note**: You cannot bridge BoTTube Credits back. If you want wRTC on RustChain:

1. You need to **hold wRTC in your Solana wallet** (not bridged)
2. Bridge wRTC from Solana back to RustChain (via RustChain's bridge, if available)
3. Or sell wRTC for SOL on Raydium

---

## 📊 Price & Market Data

| Resource | Link |
|----------|------|
| **Raydium Price** | [Check Price](https://raydium.io/price/12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **DexScreener** | [View Chart](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMkfdR3MLdnYzb) |
| **CoinGecko** | [Coming Soon] |
| **RustChain Explorer** | [View on Solana](https://rustchain.org/explorer) |

---

## 🔐 Security Best Practices

### Wallet Security
- ✅ Use a **hardware wallet** (Ledger, Trezor) for large amounts
- ✅ Enable **2FA** on Phantom/Solflare
- ✅ Never share your **seed phrase** or **private key**
- ❌ Never click on suspicious links from DMs
- ❌ Never sign transactions you don't understand

### Transaction Safety
- ✅ Always verify the **mint address** before sending
- ✅ Use **official** DEX and bridge links (bookmarked)
- ✅ Double-check **decimal places** (6 for wRTC)
- ✅ Start with **small test amounts** (< 1 SOL worth)
- ❌ Don't use "max" on large transactions

---

## 🆘 Troubleshooting

### Problem: "Token not found" on Raydium

**Solution:**
1. Make sure you pasted the **correct mint address**
2. Refresh the page and try again
3. Check if Raydium is having issues: [Raydium Status](https://status.raydium.io)

### Problem: "Transaction failed" on swap

**Solution:**
1. Check your SOL balance (need ~0.01 SOL for fees)
2. Check Solana network status: [Solana Status](https://solana.com)
3. Try reducing the swap amount
4. Make sure you have enough SOL for transaction fees

### Problem: Bridge not working

**Solution:**
1. Check your internet connection
2. Make sure you're connected to **Solana Mainnet** (not devnet)
3. Verify you have wRTC in your wallet before bridging
4. Check BoTTube status: [BoTTube Twitter](https://twitter.com/bottube)

---

## 📞 Learn More

- **RustChain Website**: [rustchain.org](https://rustchain.org)
- **RustChain Docs**: [docs/index.html](docs/index.html)
- **BoTTube Platform**: [bottube.ai](https://bottube.ai)
- **Raydium Docs**: [docs.raydium.io](https://docs.raydium.io)
- **Solana Docs**: [docs.solana.com](https://docs.solana.com)

---

## 🤝 Support

If you encounter issues or have questions:

- **GitHub Issues**: [Report a bug](https://github.com/Scottcjn/Rustchain/issues)
- **RustChain Discord**: [Join Community](https://discord.gg/VqVVS2CW9Q)
- **Twitter**: [@rustchainorg](https://twitter.com/rustchainorg)

---

## ⚖️ Disclaimer

wRTC is a wrapped token on Solana. Trading and using wRTC involves financial risk:
- Crypto prices are volatile
- Smart contracts can have vulnerabilities
- Bridge operations are one-way (wRTC → Credits)
- Always do your own research (DYOR)
- Only invest what you can afford to lose

---

**Last Updated**: 2026-02-12  
**Version**: 1.0.0
