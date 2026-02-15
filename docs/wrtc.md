# wRTC Quickstart Guide

> **Get started with wRTC (Wrapped RustChain Token) on Solana in minutes.**
> 
> This guide covers everything from buying wRTC on Raydium to bridging between RTC and wRTC safely.

---

## 📋 Table of Contents

- [Anti-Scam Checklist](#-anti-scam-checklist)
- [What is wRTC?](#-what-is-wrtc)
- [Buying wRTC on Raydium](#-buying-wrtc-on-raydium)
- [Bridging RTC to wRTC](#-bridging-rtc-to-wrtc)
- [Withdrawing wRTC to RTC](#-withdrawing-wrtc-to-rtc)
- [Quick Reference](#-quick-reference)
- [Troubleshooting](#-troubleshooting)

---

## 🛡️ Anti-Scam Checklist

**Before every transaction, verify ALL of the following:**

| Check | Canonical Value | Verification |
|-------|-----------------|--------------|
| **Token Mint** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` | Must match exactly - 44 characters, base58 |
| **Decimals** | `6` | wRTC uses 6 decimal places |
| **Official Bridge** | `https://bottube.ai/bridge/wrtc` | Bookmark this URL |
| **Official Swap** | `https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` | Verify mint in URL |
| **DexScreener** | `https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb` | Verify liquidity pool |

### ⚠️ Red Flags - STOP if you see these:

- [ ] Token mint address doesn't match exactly
- [ ] Website URL is slightly different (typosquatting)
- [ ] Someone DM'd you a "better" bridge link
- [ ] Token shows different decimal places (e.g., 9 or 18)
- [ ] Price seems too good to be true (likely honeypot)

---

## 🪙 What is wRTC?

**wRTC** is the Solana-native representation of RustChain Token (RTC). 

| Feature | RTC (Native) | wRTC (Solana) |
|---------|--------------|---------------|
| **Network** | RustChain | Solana |
| **Use Case** | Mining rewards | Trading, DeFi |
| **Wallet** | RustChain wallet | Phantom, Solflare, etc. |
| **Exchange** | Bridge only | Raydium, Jupiter |
| **Speed** | ~10 min epochs | ~400ms finality |

### Why Use wRTC?

1. **Trade on DEXs** - Swap wRTC for SOL or other tokens on Raydium
2. **Liquidity** - Provide liquidity to earn fees
3. **Speed** - Near-instant transfers on Solana
4. **Ecosystem** - Use with any Solana DeFi protocol

---

## 💱 Buying wRTC on Raydium

### Prerequisites

- [ ] Solana wallet (Phantom, Solflare, or Backpack recommended)
- [ ] SOL for transaction fees (~0.001 SOL per swap)
- [ ] SOL or USDC to swap for wRTC

### Step-by-Step Guide

#### Step 1: Open Raydium

Navigate to the official Raydium swap URL:

```
https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X
```

#### Step 2: Verify the Token

**CRITICAL: Check ALL of these before proceeding:**

1. Look at the URL - confirm outputMint is `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
2. In the Raydium UI, click the output token dropdown
3. Verify the mint address displayed matches exactly

```
✅ Correct: 12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X
❌ Wrong:   12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4Y (different last char)
❌ Wrong:   Any other address
```

#### Step 3: Connect Wallet

1. Click **"Connect Wallet"** in the top right
2. Select your wallet (Phantom, Solflare, etc.)
3. Approve the connection in your wallet popup

#### Step 4: Enter Swap Amount

1. **Input**: Select SOL (or USDC)
2. **Output**: wRTC (should auto-populate)
3. Enter the amount of SOL you want to swap
4. Review the estimated wRTC you'll receive

#### Step 5: Adjust Slippage (Optional)

- Default: 0.5% (recommended for stable pairs)
- Volatile markets: 1-2%
- **Never exceed 5%** - high slippage increases MEV risk

To adjust: Click the gear icon → Set slippage tolerance

#### Step 6: Execute Swap

1. Click **"Swap"**
2. Review the transaction details in the confirmation modal
3. Click **"Confirm Swap"**
4. Approve the transaction in your wallet
5. Wait for confirmation (~2-5 seconds)

#### Step 7: Verify Receipt

1. Check your wallet balance for wRTC
2. View transaction on [Solscan](https://solscan.io) or [SolanaFM](https://solana.fm)
3. The token should appear automatically in most wallets

**If wRTC doesn't appear:**
- Phantom: Click "Manage token list" → Search wRTC → Enable
- Solflare: Click "+" → Paste mint address → Add

---

## 🌉 Bridging RTC to wRTC

Bridge your native RTC (earned from mining) to wRTC on Solana.

### Prerequisites

- [ ] RustChain wallet with RTC balance
- [ ] Solana wallet address (destination)
- [ ] Both wallets ready and accessible

### Step-by-Step Guide

#### Step 1: Navigate to BoTTube Bridge

Open the official bridge URL:

```
https://bottube.ai/bridge/wrtc
```

**Always verify the URL:**
- ✅ `https://bottube.ai/bridge/wrtc`
- ❌ Any variation (bottube.com, bottube-bridge.xyz, etc.)

#### Step 2: Select Bridge Direction

Choose **"RTC → wRTC"** (RustChain to Solana)

#### Step 3: Connect RustChain Wallet

1. Click **"Connect RustChain Wallet"**
2. Enter your wallet address or connect via available method
3. Verify your RTC balance displays correctly

#### Step 4: Enter wRTC Destination

1. Enter your Solana wallet address (where wRTC will be sent)
2. **Double-check this address** - transactions are irreversible
3. Verify the address starts with a letter/number (base58 format)

```
✅ Valid:   7nx8QmzxD1wKX7QJ1FVqT5hX9YvJxKqZb8yPoR3dL8mN
❌ Invalid: 0x... (Ethereum format)
❌ Invalid: Any non-base58 characters
```

#### Step 5: Enter Amount

1. Enter the amount of RTC to bridge
2. Review the bridge fee (usually 0.1-0.5%)
3. Ensure you have enough RTC after fees

#### Step 6: Review and Confirm

**Final Checklist:**
- [ ] Source RTC wallet has sufficient balance
- [ ] Destination Solana address is correct
- [ ] Amount + fees are acceptable
- [ ] You understand this may take 5-30 minutes

Click **"Bridge"** or **"Confirm"**

#### Step 7: Wait for Confirmation

Bridging involves two transactions:
1. **Lock on RustChain** (~1-5 minutes)
2. **Mint on Solana** (~1-5 minutes)

Monitor the bridge UI for status updates. You'll see:
- "Pending" → "Confirming" → "Completed"

#### Step 8: Verify wRTC Receipt

1. Check your Solana wallet for wRTC balance
2. View transaction on [Solscan](https://solscan.io)
3. The wRTC should appear automatically

---

## 🔄 Withdrawing wRTC to RTC

Bridge your wRTC back to native RTC on RustChain.

### Prerequisites

- [ ] Solana wallet with wRTC balance
- [ ] RustChain wallet address (destination)
- [ ] SOL for Solana transaction fees (~0.0001 SOL)

### Step-by-Step Guide

#### Step 1: Navigate to BoTTube Bridge

Open: `https://bottube.ai/bridge/wrtc`

#### Step 2: Select Bridge Direction

Choose **"wRTC → RTC"** (Solana to RustChain)

#### Step 3: Connect Solana Wallet

1. Click **"Connect Solana Wallet"**
2. Select your wallet provider (Phantom, Solflare, etc.)
3. Approve the connection
4. Verify your wRTC balance displays

#### Step 4: Enter RTC Destination

1. Enter your RustChain wallet address
2. **Double-check this address**
3. Ensure it's a valid RustChain address format

#### Step 5: Enter Amount

1. Enter the amount of wRTC to bridge
2. Review the bridge fee
3. Click **"Max"** to bridge entire balance (minus fees)

#### Step 6: Review and Confirm

**Final Checklist:**
- [ ] Source wRTC balance is sufficient
- [ ] Destination RustChain address is correct
- [ ] Amount + fees are acceptable
- [ ] You have SOL for transaction fees

Click **"Bridge"**

#### Step 7: Approve Solana Transaction

1. Your wallet will prompt for transaction approval
2. Review the transaction details
3. Click **"Approve"** or **"Sign"**

#### Step 8: Wait for Confirmation

Bridging process:
1. **Burn on Solana** (~5-15 seconds)
2. **Release on RustChain** (~5-30 minutes)

Monitor the bridge UI for updates.

#### Step 9: Verify RTC Receipt

1. Check your RustChain wallet balance
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET"
```
2. Verify on [RustChain Explorer](https://rustchain.org/explorer)

---

## 📊 Quick Reference

### Token Details

| Property | Value |
|----------|-------|
| **Token Name** | Wrapped RustChain Token |
| **Symbol** | wRTC |
| **Mint Address** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |
| **Decimals** | 6 |
| **Network** | Solana |
| **Standard** | SPL Token |

### Official Links

| Resource | URL |
|----------|-----|
| **Raydium Swap (SOL→wRTC)** | <https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X> |
| **BoTTube Bridge** | <https://bottube.ai/bridge/wrtc> |
| **DexScreener** | <https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb> |
| **RustChain Explorer** | <https://rustchain.org/explorer> |

### Bridge Fees

| Direction | Typical Fee | Time |
|-----------|-------------|------|
| RTC → wRTC | 0.1-0.5% | 5-30 min |
| wRTC → RTC | 0.1-0.5% | 5-30 min |

### Transaction Costs

| Operation | Network Fee |
|-----------|-------------|
| Raydium Swap | ~0.001 SOL |
| Bridge (wRTC→RTC) | ~0.0001 SOL |
| Transfer wRTC | ~0.000005 SOL |

---

## 🔧 Troubleshooting

### Common Issues

#### Issue: "Insufficient SOL for transaction fees"

**Solution:**
- Ensure your Solana wallet has at least 0.001 SOL
- Buy SOL on any exchange and transfer to your wallet
- Even small amounts (0.01 SOL) are sufficient for many transactions

#### Issue: "Token mint not found" or wrong token showing

**Solution:**
1. Verify you're using the correct mint: `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
2. Clear your wallet's token cache (settings → clear cache)
3. Manually add the token using the mint address

#### Issue: Bridge transaction stuck on "Pending"

**Solution:**
1. Wait up to 1 hour (network congestion)
2. Check [Solscan](https://solscan.io) for your Solana transaction status
3. Check RustChain explorer for the corresponding transaction
4. Contact support with transaction hash if >1 hour

#### Issue: "Slippage tolerance exceeded" on Raydium

**Solution:**
1. Increase slippage tolerance (gear icon) to 1-2%
2. Try swapping a smaller amount
3. Wait a few minutes and retry (price may be volatile)
4. Check DexScreener for current pool liquidity

#### Issue: Bridge shows "Failed" or "Rejected"

**Solution:**
1. Verify you have enough balance for the amount + fees
2. Check that both wallet addresses are correct
3. Ensure you're on the correct network (Mainnet Beta for Solana)
4. Clear browser cache and try again
5. Try a smaller amount first

#### Issue: wRTC not appearing in wallet after purchase

**Solution:**
- **Phantom**: Settings → Preferences → Manage token list → Search "wRTC"
- **Solflare**: Portfolio → Click "+" → Paste mint address → Add
- **Backpack**: Tokens → Search or paste mint

#### Issue: "Invalid address format" when bridging

**Solution:**
- RustChain addresses: Alphanumeric, case-sensitive
- Solana addresses: 32-44 characters, base58 encoded
- Never use Ethereum (0x...) addresses for Solana transactions

### Emergency Contacts

| Issue | Contact |
|-------|---------|
| Bridge problems | BoTTube support on [bottube.ai](https://bottube.ai) |
| RustChain issues | GitHub Issues: [Scottcjn/Rustchain](https://github.com/Scottcjn/Rustchain) |
| Scam reports | Report to official RustChain Discord/Telegram mods |

### Safety Reminders

1. **Never share your seed phrase or private keys**
2. **Never approve transactions you don't understand**
3. **Always verify mint addresses character-by-character**
4. **Bookmark official URLs** - never click links from DMs
5. **Start with small amounts** when testing new processes
6. **Keep software updated** - wallet apps, browsers

---

## 📚 Additional Resources

- [RustChain Whitepaper](RustChain_Whitepaper_Flameholder_v0.97-1.pdf)
- [Protocol Specification](./PROTOCOL.md)
- [API Reference](./API.md)
- [Wallet User Guide](./WALLET_USER_GUIDE.md)
- [Original Onboarding Tutorial](./WRTC_ONBOARDING_TUTORIAL.md)

---

<div align="center">

**Questions?** Open an issue on [GitHub](https://github.com/Scottcjn/Rustchain) or reach out in official community channels.

*Always verify, never rush. Your security is worth the extra 30 seconds.*

</div>
