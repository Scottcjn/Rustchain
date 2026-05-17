# wRTC Onboarding Tutorial (Bridge + Aerodrome + Safety)

This guide explains what RTC vs wRTC means and how to bridge/swap safely using
the current Base/Aerodrome model returned by `/wallet/swap-info`.

## 1) RTC vs wRTC

- `RTC` is the native RustChain token used on the RustChain network.
- `wRTC` is a wrapped representation of RTC on Base.
- Use `wRTC` for Base-native liquidity and payments, including Aerodrome swaps
  and x402 payment flows.

Official Base contracts:

- wRTC: `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`
- USDC: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
- Aerodrome pool: `0x4C2A0b915279f0C22EA766D58F9B815Ded2d2A3F`

## 2) Official links

- Bridge UI: <https://bottube.ai/bridge/wrtc>
- Direct bridge page (wRTC): <https://bottube.ai/bridge/wrtc>
- Aerodrome swap (USDC -> wRTC):
  <https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6>
- Live RustChain swap info:
  <https://rustchain.org/wallet/swap-info>
- BaseScan wRTC contract:
  <https://basescan.org/address/0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6>

## 3) Bridge walkthrough (RTC <-> wRTC)

1. Open <https://bottube.ai/bridge/wrtc>.
2. Select the direction you need:
   - RTC -> wRTC, to receive wRTC on Base.
   - wRTC -> RTC, to return to the RustChain side.
3. Connect the correct wallet for each side as requested by the UI.
4. For Base-side transfers, verify the wallet address is an `0x` Base address.
5. Enter amount and review the summary.
6. Confirm the transaction and wait for final confirmation.
7. Verify receipt in the wallet and in the bridge history/tx details.

## 4) Find the correct Aerodrome pool and swap

1. Open the official Aerodrome swap link above.
2. Confirm the source token is Base USDC:
   `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`.
3. Confirm the output token is wRTC:
   `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`.
4. Confirm the connected wallet is on Base.
5. Set amount and slippage, then execute the swap.

## 5) Common failure modes and safety notes

- Wrong wallet format/network:
  - Bridge transactions can fail if you provide an incompatible address or wrong
    chain wallet.
  - Double-check Base `0x` addresses and RustChain wallet/miner ids before
    confirming.
- Fake contract / scam token:
  - Always verify the wRTC contract equals
    `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`.
  - Do not trust copied symbols/names alone.
- Slippage too tight:
  - Volatile pools can fail with low slippage settings.
  - Increase slippage carefully in small steps.
- Wrong direction in bridge:
  - Confirm whether you are wrapping (RTC -> wRTC) or unwrapping (wRTC -> RTC).
- Partial balance or fee shortage:
  - Keep enough ETH on Base for gas and enough RTC/wRTC for bridge amount plus
    fees.
- Phishing links:
  - Bookmark official URLs and avoid bridge/swap links from unknown DMs.

## 6) Quick checklist before every transaction

- Official bridge URL is correct.
- wRTC contract is exactly `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`.
- USDC contract is exactly `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`.
- Wallet network and destination address are correct.
- Slippage and amount are reviewed.
- You understand bridge direction (RTC -> wRTC or wRTC -> RTC).

## 7) Support and verification

If something looks wrong:

- Stop before signing.
- Re-open this tutorial and re-check contract addresses and URLs.
- Query <https://rustchain.org/wallet/swap-info> and compare the live response.
- Ask in official RustChain channels with tx hash; never share seed phrase or
  private key.
