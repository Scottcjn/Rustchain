# wRTC Quickstart: Buy, Verify, Bridge

This guide shows the safest path to:
1. get real `wRTC` on Solana,
2. verify token authenticity,
3. bridge `wRTC` into BoTTube credits for RTC tipping,
4. withdraw back to `wRTC`.

## Canonical Token Info (Use This Only)

- Mint: `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
- Decimals: `6`
- Raydium swap URL:
  `https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
- BoTTube bridge URL:
  `https://bottube.ai/bridge/wrtc`

## Anti-Scam Checklist (Do Not Skip)

- Always verify the full mint address, not token name/ticker only.
- Confirm token decimals are exactly `6`.
- Use the official Raydium swap link from this guide.
- Do not trust random DMs, fake support, or shortened links.
- Bookmark official pages and access via bookmarks.
- Start with a small test amount before moving larger balances.

## Prerequisites

- Solana wallet with SOL for network fees.
- Access to Raydium and BoTTube Bridge from a secure browser session.

## Step 1: Swap SOL to wRTC on Raydium

Open:
`https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`

Then:
1. Connect your wallet.
2. Confirm the output token mint is:
   `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`.
3. Enter amount, review price impact, and execute swap.
4. Keep transaction signature for audit/reference.

## Step 2: Verify You Received Real wRTC

Inside wallet token details, verify:
- Mint is `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
- Decimals is `6`

If either does not match, do not continue bridging.

## Step 3: Bridge wRTC to BoTTube Credits

Open:
`https://bottube.ai/bridge/wrtc`

Then:
1. Connect same wallet holding wRTC.
2. Select deposit/bridge to BoTTube credits.
3. Enter amount and confirm wallet transaction.
4. Wait for confirmation and verify credits appear in your BoTTube account.

## Step 4: Withdraw Back to wRTC

From BoTTube Bridge:
1. Choose withdraw back to wRTC.
2. Enter destination Solana wallet address.
3. Confirm amount and submit withdrawal.
4. Verify received token mint/decimals again after arrival.

## Troubleshooting

- Bridge pending: wait for network confirmations and refresh session.
- Token not visible: add custom token in wallet using canonical mint.
- Wrong token risk: compare mint and decimals before every transfer.

## Safety Notes

- No one from the project will ask for your seed phrase.
- Use hardware wallets for larger balances.
- Consider keeping separate wallets for operations vs storage.
