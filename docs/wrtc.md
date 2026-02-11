# wRTC Quickstart Guide

## What is wRTC?

**wRTC** (Wrapped RustChain Token) is the Solana-based SPL token representation of RTC, enabling fast trading on Solana DEXs like Raydium and seamless bridging to BoTTube for tipping and rewards.

---

## ⚠️ Anti-Scam Checklist

Before buying or bridging wRTC, **verify you have the correct token:**

### ✅ Official wRTC Details
- **Mint Address:** `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
- **Decimals:** `6`
- **Symbol:** `wRTC`
- **Network:** Solana mainnet

### 🚨 How to Verify

1. **Check the mint address** - Must match exactly (case-sensitive)
2. **Verify decimals** - Must be `6` (not 8, not 9)
3. **Don't trust ticker alone** - Anyone can create a token with "wRTC" symbol
4. **Check liquidity** - Real wRTC has liquidity on Raydium
5. **Verify bridge** - Only bridge at `https://bottube.ai/bridge/wrtc`

### 🛡️ Red Flags

❌ Token with different mint address  
❌ Token with wrong decimal places  
❌ Unknown/sketchy DEX  
❌ Telegram/Discord DMs offering "special deals"  
❌ Bridge sites other than bottube.ai  

---

## 1️⃣ How to Buy wRTC

### Option A: Raydium Swap (Recommended)

1. **Get a Solana wallet:**
   - [Phantom](https://phantom.app/) (browser extension)
   - [Solflare](https://solflare.com/) (mobile/web)

2. **Fund your wallet with SOL:**
   - Buy on Coinbase, Binance, or other exchanges
   - Transfer to your Solana wallet address

3. **Swap SOL → wRTC on Raydium:**
   - Go to: [Raydium Swap](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)
   - Connect your wallet
   - Select SOL as input, wRTC as output
   - **Verify the mint:** `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
   - Enter amount and confirm swap

4. **Verify in your wallet:**
   ```
   Token: wRTC
   Mint: 12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X
   Decimals: 6
   ```

---

## 2️⃣ Bridge wRTC to BoTTube Credits

### What is BoTTube?

BoTTube is a decentralized video platform where you can tip creators with RTC. Bridging wRTC converts your Solana tokens into BoTTube credits (1:1 ratio).

### Bridging Steps

1. **Go to the official bridge:**
   - URL: [https://bottube.ai/bridge/wrtc](https://bottube.ai/bridge/wrtc)
   - **Verify the URL** - Don't use links from DMs or unknown sources

2. **Connect your Solana wallet:**
   - Click "Connect Wallet"
   - Select Phantom, Solflare, or your wallet
   - Approve the connection

3. **Enter bridge amount:**
   - Specify how much wRTC to bridge
   - Keep ~0.01 SOL for transaction fees
   - Review conversion: 1 wRTC = 1 BoTTube credit

4. **Confirm transaction:**
   - Approve in your wallet
   - Wait for Solana confirmation (~2-5 seconds)
   - Credits appear in your BoTTube account

5. **Start tipping:**
   - Browse videos on [BoTTube](https://bottube.ai)
   - Tip creators with your credits
   - Earn rewards for engagement

---

## 3️⃣ Withdraw BoTTube Credits Back to wRTC

### When to Withdraw

- You want to sell wRTC on Raydium
- You prefer holding tokens in your wallet
- You need SOL liquidity

### Withdrawal Steps

1. **Go to BoTTube bridge:**
   - [https://bottube.ai/bridge/wrtc](https://bottube.ai/bridge/wrtc)
   - Connect your wallet

2. **Select "Withdraw" tab:**
   - Enter withdrawal amount
   - Specify destination wallet (your Solana address)

3. **Confirm withdrawal:**
   - Approve transaction
   - Wait for processing (~10-30 seconds)
   - wRTC appears in your Solana wallet

4. **Verify receipt:**
   ```
   Token: wRTC
   Mint: 12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X
   Amount: [your withdrawal amount]
   ```

---

## 💰 Trading wRTC

### Sell wRTC on Raydium

1. Go to [Raydium Swap](https://raydium.io/swap/)
2. Connect wallet
3. Select wRTC as input, SOL (or USDC) as output
4. Verify mint: `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
5. Enter amount and swap

### Check Price

- [Raydium Pool](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)
- [Solscan Token](https://solscan.io/token/12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)
- [DexScreener](https://dexscreener.com/solana/12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)

---

## 🔄 Quick Reference

| Action | Platform | Link |
|--------|----------|------|
| Buy wRTC | Raydium | [Swap SOL→wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |
| Bridge to BoTTube | BoTTube | [bridge/wrtc](https://bottube.ai/bridge/wrtc) |
| Withdraw to wallet | BoTTube | [bridge/wrtc](https://bottube.ai/bridge/wrtc) |
| Check balance | Solscan | [Token page](https://solscan.io/token/12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |

---

## ❓ FAQ

### What's the difference between RTC and wRTC?

- **RTC** = Native RustChain token (mined on vintage hardware)
- **wRTC** = Wrapped version on Solana (for DEX trading)
- Conversion rate: 1 RTC = 1 wRTC

### How long does bridging take?

- **To BoTTube:** ~2-5 seconds (Solana confirmation time)
- **From BoTTube:** ~10-30 seconds (withdrawal processing)

### Are there bridge fees?

- Check [bottube.ai/bridge/wrtc](https://bottube.ai/bridge/wrtc) for current fee structure
- Solana network fees: ~0.00001 SOL per transaction

### Is bridging safe?

Yes, when using the official bridge at `bottube.ai/bridge/wrtc`. Always verify:
- ✅ Correct URL (bottube.ai)
- ✅ Correct mint address
- ✅ SSL certificate (padlock icon)

### Can I bridge back anytime?

Yes! Withdrawals are always available (subject to BoTTube balance).

### What if I sent to wrong address?

**Blockchain transactions are irreversible.** Always:
- Double-check recipient addresses
- Test with small amounts first
- Verify mint addresses before swapping

---

## 🆘 Need Help?

- **Discord:** [RustChain Community](https://discord.gg/VqVVS2CW9Q)
- **GitHub Issues:** [Report problems](https://github.com/Scottcjn/Rustchain/issues)
- **BoTTube Support:** Contact via [bottube.ai](https://bottube.ai)

---

## 📚 Related Docs

- [RustChain Whitepaper](../README.md)
- [Mining Guide](./mining.md)
- [Vintage Hardware List](../README_VINTAGE_CPUS.md)
- [FAQ](./FAQ.md)

---

**Last Updated:** February 2026  
**Maintainer:** RustChain Core Team  
**Bounty:** Issue #58 (40 RTC)
