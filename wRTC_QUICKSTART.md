# wRTC Quickstart Guide

This guide covers everything you need to know about **wRTC (wrapped RustChain Token)** on Solana - how to buy, verify, and bridge between RTC and wRTC.

## 📋 Table of Contents
- [What is wRTC?](#what-is-wrtc)
- [How to Buy wRTC](#how-to-buy-wrtc)
- [How to Verify wRTC](#how-to-verify-wrtc)
- [How to Bridge RTC ↔ wRTC](#how-to-bridge-rtc--wrtc)
- [Token Information](#token-information)
- [Security Notes](#security-notes)

## What is wRTC?

**wRTC (wrapped RustChain Token)** is the Solana-compatible version of RustChain's native RTC token. It allows you to:
- Trade RTC on Solana DEXes like Raydium
- Use RTC in Solana DeFi protocols
- Bridge between RustChain mainnet and Solana

The wRTC token maintains a 1:1 peg with native RTC through the BoTTube Bridge.

## How to Buy wRTC

### Option 1: Swap on Raydium DEX
1. Go to [Raydium DEX](https://raydium.io/swap/)
2. Connect your Solana wallet (Phantom, Backpack, etc.)
3. Select **SOL** as input token
4. Paste the wRTC contract address as output token:  
   `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
5. Enter the amount you want to swap
6. Click **Swap** and confirm the transaction

### Option 2: Direct Link
Use this pre-configured Raydium link to swap SOL for wRTC directly:  
[Raydium wRTC Swap](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)

## How to Verify wRTC

### On Solana Explorer
1. Visit [Solana Explorer](https://explorer.solana.com/)
2. Search for the wRTC token address:  
   `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
3. Verify the token details:
   - **Name**: wRTC (wrapped RustChain Token)
   - **Symbol**: wRTC
   - **Decimals**: 9
   - **Total Supply**: Check against official RustChain supply

### On DexScreener
Monitor wRTC price and liquidity on [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb)

### Wallet Verification
When you receive wRTC in your wallet:
- Ensure the token address matches: `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
- Check that your wallet shows it as "wRTC" or "wrapped RustChain Token"
- Verify the balance matches your expected amount

## How to Bridge RTC ↔ wRTC

### Bridge from RustChain to Solana (RTC → wRTC)
1. Go to the [BoTTube Bridge](https://bottube.ai/bridge)
2. Connect your **RustChain wallet** (contains native RTC)
3. Connect your **Solana wallet** (will receive wRTC)
4. Enter the amount of RTC to bridge
5. Review the bridge fee and confirmation details
6. Confirm the transaction on both chains
7. Wait for the bridge to complete (typically 5-15 minutes)

### Bridge from Solana to RustChain (wRTC → RTC)
1. Go to the [BoTTube Bridge](https://bottube.ai/bridge)
2. Connect your **Solana wallet** (contains wRTC)
3. Connect your **RustChain wallet** (will receive native RTC)
4. Enter the amount of wRTC to bridge
5. Review the bridge fee and confirmation details
6. Confirm the transaction on both chains
7. Wait for the bridge to complete (typically 5-15 minutes)

### Bridge Requirements
- **Minimum amounts**: Check current minimums on the bridge interface
- **Gas fees**: You'll need SOL for Solana transactions and RTC for RustChain transactions
- **Wallet compatibility**: Ensure both wallets support the respective chains

## Token Information

| Property | Value |
|----------|-------|
| **Token Name** | wrapped RustChain Token |
| **Symbol** | wRTC |
| **Chain** | Solana |
| **Contract Address** | `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X` |
| **Decimals** | 9 |
| **Bridge** | [BoTTube Bridge](https://bottube.ai/bridge) |
| **DEX** | [Raydium](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) |

## Security Notes

### 🔒 Always Verify
- **Double-check contract addresses** before any transaction
- **Bookmark official links** to avoid phishing sites
- **Verify token details** in your wallet before approving transactions

### ⚠️ Bridge Safety
- Start with **small test amounts** when using the bridge for the first time
- Ensure you have **sufficient gas fees** on both chains
- **Never share your private keys** with bridge interfaces

### 🛡️ Official Resources
- **Website**: [rustchain.org](https://rustchain.org)
- **Explorer**: [rustchain.org/explorer](https://rustchain.org/explorer)
- **Whitepaper**: [RustChain Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf)
- **GitHub**: [github.com/Scottcjn/Rustchain](https://github.com/Scottcjn/Rustchain)

---

> **Note**: wRTC enables RustChain's Proof-of-Antiquity ecosystem to integrate with Solana's DeFi landscape while maintaining the core principle that **authentic vintage hardware deserves recognition and value**.

*If you use RustChain, you're not just mining tokens – you're preserving computing history.*