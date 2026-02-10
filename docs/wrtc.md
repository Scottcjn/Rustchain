# wRTC Quickstart Guide

wRTC is the wrapped Solana SPL token version of RustChain's RTC. This guide covers how to buy, verify, and bridge wRTC safely.

---

## 📋 Quick Reference

| Property | Value |
|----------|-------|
| **Token Name** | Wrapped RustChain Token (wRTC) |
| **Mint Address** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |
| **Decimals** | 6 |
| **Network** | Solana |
| **Swap** | [Raydium](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| **Bridge** | [BoTTube Bridge](https://bottube.ai/bridge/wrtc) |
| **Price Chart** | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |

---

## 🛡️ Anti-Scam Checklist

Before buying or interacting with any wRTC token, **always verify**:

### ✅ Verify the Mint Address
The **only legitimate** wRTC mint address is:
```
12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X
```

**How to verify:**
1. On Raydium/Jupiter, click the token to expand details
2. Check that the mint address matches exactly
3. On Solscan: [View official token](https://solscan.io/token/12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)

### ✅ Verify Decimals = 6
The official wRTC has exactly **6 decimals**. Scam tokens often use different decimal places.

### ❌ Don't Trust Ticker Alone
Anyone can create a token called "wRTC" or "WRTC". The **ticker name means nothing** — only the mint address matters.

### ❌ Watch for Common Scams
- Fake airdrops asking for wallet access
- Tokens with similar names but different mints
- DMs offering "special" wRTC deals
- Websites that aren't `raydium.io` or `bottube.ai`

### ✅ Use Official Links Only
- **Raydium Swap**: https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X
- **BoTTube Bridge**: https://bottube.ai/bridge/wrtc
- **DexScreener**: https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb

---

## 💱 How to Buy wRTC on Raydium

### Prerequisites
- A Solana wallet (Phantom, Solflare, etc.)
- SOL for the swap (and a small amount for transaction fees)

### Steps

1. **Connect your wallet to Raydium**
   - Go to [Raydium Swap](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)
   - Click "Connect Wallet" and select your wallet

2. **Verify you're swapping for the correct token**
   - The output token should show wRTC with mint `12TAdKX...5i4X`
   - Click the token to confirm the full mint address

3. **Enter the amount of SOL to swap**
   - Enter how much SOL you want to exchange
   - The estimated wRTC output will be shown

4. **Review and confirm the swap**
   - Check the exchange rate and price impact
   - Click "Swap" and approve the transaction in your wallet

5. **Verify the tokens arrived**
   - Check your wallet for the wRTC balance
   - Confirm on Solscan that the mint matches

---

## 🌉 Bridging wRTC to BoTTube Credits

The BoTTube bridge allows you to convert wRTC into BoTTube credits, which can be used for RTC tipping within the BoTTube ecosystem.

### Steps to Bridge wRTC → BoTTube Credits

1. **Go to the BoTTube Bridge**
   - Navigate to [https://bottube.ai/bridge/wrtc](https://bottube.ai/bridge/wrtc)

2. **Connect your Solana wallet**
   - Click "Connect Wallet" and approve the connection

3. **Enter the amount to bridge**
   - Enter how much wRTC you want to convert to BoTTube credits
   - Review the conversion rate

4. **Confirm the bridge transaction**
   - Click "Bridge" and approve the transaction
   - Wait for confirmation (usually a few seconds)

5. **Check your BoTTube balance**
   - Your BoTTube credits should reflect the bridged amount
   - You can now use these for RTC tipping

---

## 🔄 Withdrawing BoTTube Credits to wRTC

To convert BoTTube credits back to wRTC:

1. **Go to the BoTTube Bridge**
   - Navigate to [https://bottube.ai/bridge/wrtc](https://bottube.ai/bridge/wrtc)

2. **Select "Withdraw" mode**
   - Toggle from deposit to withdraw

3. **Enter the amount to withdraw**
   - Enter how many credits to convert back to wRTC

4. **Enter your Solana wallet address**
   - Paste the address where you want to receive wRTC
   - Double-check it's correct!

5. **Confirm the withdrawal**
   - Review the details and confirm
   - wRTC will be sent to your wallet

---

## ❓ FAQ

### Where does wRTC come from?
wRTC is created by bridging native RTC (earned by mining on RustChain) to Solana via the official BoTTube Bridge. Each wRTC is backed 1:1 by RTC.

### What's the difference between RTC and wRTC?
- **RTC**: Native token on the RustChain blockchain, earned by mining with vintage hardware
- **wRTC**: Wrapped version on Solana, tradeable on DEXs and usable in DeFi

### Is wRTC inflationary?
wRTC supply matches the bridged RTC. Total RTC supply follows RustChain's emission schedule (see [tokenomics](tokenomics_v1.md)).

### Can I mine wRTC directly?
No. You mine RTC on the RustChain network using vintage hardware, then bridge to wRTC if you want to trade on Solana.

### My transaction failed, what do I do?
1. Check you have enough SOL for fees
2. Try increasing slippage tolerance (for swaps)
3. Ensure the amounts don't exceed pool liquidity

---

## 🔗 Official Resources

| Resource | Link |
|----------|------|
| RustChain Website | https://rustchain.org |
| Live Explorer | https://rustchain.org/explorer |
| GitHub | https://github.com/Scottcjn/Rustchain |
| Raydium Swap | [Swap wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| DexScreener | [Price Chart](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) |
| BoTTube Bridge | https://bottube.ai/bridge/wrtc |

---

*Protect yourself: When in doubt, verify the mint address!*
