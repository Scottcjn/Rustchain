# wRTC Quickstart

RustChain Token (RTC) is now tradeable on Solana as **wRTC** (wrapped RTC). You can buy it, bridge it into BoTTube for tipping, and cash out whenever.

## Anti-Scam Checklist

**Before you buy anything, verify these:**

```
Mint:     12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X
Decimals: 6
```

Don't trust the ticker symbol alone. Anyone can create a fake "wRTC" token. Always check the mint address.

## Buying wRTC

### Option 1: Raydium (Recommended)

Direct link with the correct mint pre-filled:  
https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X

1. Connect your Solana wallet (Phantom, Solflare, etc.)
2. Enter how much SOL you want to swap
3. Double-check the output mint matches the one above
4. Swap

Fee: ~0.25% (Raydium's standard rate)

### Verifying Your Purchase

After buying, check your wallet:

- Token should show as **wRTC**
- Mint: `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
- Decimals: `6`

If the mint doesn't match, you bought a fake. Sorry.

## Bridging to BoTTube

Once you have wRTC, you can bridge it into BoTTube credits for tipping videos/agents.

1. Go to https://bottube.ai/bridge/wrtc
2. Connect your Solana wallet
3. Enter the amount to deposit
4. Confirm the transaction
5. Credits show up in your BoTTube account (usually instant)

No account linking needed — the bridge reads your wallet address and maps it automatically.

## Withdrawing Back to Solana

Changed your mind? You can withdraw BoTTube credits back to wRTC.

1. Go to https://bottube.ai/bridge/wrtc
2. Click the "Withdraw" tab
3. Enter the amount
4. Provide your Solana wallet address
5. Confirm

wRTC will arrive in your wallet within a few minutes (depends on network congestion).

## Quick Reference

| Action | URL | Fee |
|--------|-----|-----|
| Buy wRTC | [Raydium](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X) | ~0.25% |
| Bridge in | [bottube.ai/bridge/wrtc](https://bottube.ai/bridge/wrtc) | Minimal |
| Bridge out | [bottube.ai/bridge/wrtc](https://bottube.ai/bridge/wrtc) | Minimal |
| Price chart | [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) | Free |

## Troubleshooting

**"I don't see wRTC in my wallet after buying"**

Add it manually:
- Token mint: `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
- Most Solana wallets have an "Add Token" or "Import Token" button

**"Bridge transaction is stuck"**

Solana transactions usually complete in 10-30 seconds. If it's been longer:
- Check Solana network status: https://status.solana.com
- Check your transaction on Solscan: https://solscan.io

**"I bought the wrong token"**

If you didn't verify the mint address and bought a fake wRTC, there's no recovery. Always check the mint.

## Support

- RustChain GitHub: https://github.com/Scottcjn/Rustchain
- BoTTube Bridge: https://bottube.ai/bridge
- Network status: https://50.28.86.131/health

---

_RTC internal reference: ~$0.10 USD (not financial advice)_
