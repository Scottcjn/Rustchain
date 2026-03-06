# wRTC Onboarding Tutorial (Bridge + Raydium + Safety)

This guide explains what RTC vs wRTC means and how to bridge/swap safely.

## 1) RTC vs wRTC

- `RTC` is the native RustChain token used on the RustChain network.
- `wRTC` is a wrapped representation of RTC on Solana.
- Use `wRTC` for Solana-native trading/liquidity tools (for example Raydium).

Official Solana mint for wRTC:

`12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`

## 2) Official links

- Bridge UI: <https://bottube.ai/bridge>
- Direct bridge page (wRTC): <https://bottube.ai/bridge/wrtc>
- Raydium swap (SOL -> wRTC):
  <https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X>
- DexScreener pool view:
  <https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb>

## 3) Bridge walkthrough (RTC <-> wRTC)

1. Open <https://bottube.ai/bridge>.
2. Select the direction you need:
   - RTC -> wRTC (to use on Solana), or
   - wRTC -> RTC (to return to RustChain side).
3. Connect the correct wallet for each side as requested by the UI.
4. Enter amount and review summary.
5. Confirm the transaction and wait for final confirmation.
6. Verify receipt in wallet and in the bridge history/tx details.

## 4) Find the correct Raydium pool and swap

1. Open the official Raydium swap link above.
2. Confirm output token mint is exactly:
   `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
3. If selecting token manually, only use official links from RustChain docs/channels.
4. Set amount and slippage, then execute the swap.

## 5) Common failure modes and safety notes

- Wrong wallet format/network:
  - Bridge transactions can fail if you provide an incompatible address or wrong chain wallet.
  - Double-check chain and address format before confirming.
- Fake mint / scam token:
  - Always verify mint equals
    `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`.
  - Do not trust copied symbols/names alone.
- Slippage too tight:
  - Volatile pools can fail with low slippage settings.
  - Increase slippage carefully in small steps.
- Wrong direction in bridge:
  - Confirm whether you are wrapping (RTC -> wRTC) or unwrapping (wRTC -> RTC).
- Partial balance or fee shortage:
  - Keep enough native gas token for fees on both chains.
- Phishing links:
  - Bookmark official URLs and avoid bridge/swap links from unknown DMs.

## 6) Quick checklist before every transaction

- Official bridge URL is correct.
- Mint is exactly `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`.
- Wallet network and destination address are correct.
- Slippage and amount are reviewed.
- You understand bridge direction (RTC -> wRTC or wRTC -> RTC).

## 7) Support and verification

If something looks wrong:

- Stop before signing.
- Re-open this tutorial and re-check mint + URL.
- Ask in official RustChain channels with tx hash (never share seed phrase/private key).
