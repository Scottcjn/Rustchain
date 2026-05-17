# wRTC Quickstart Guide

> Get started with wRTC (Wrapped RustChain Token) on Base using the live
> RustChain swap-info contract model.

This guide covers buying wRTC with USDC on Aerodrome, bridging between RTC and
wRTC, and verifying every address before signing.

---

## Table of Contents

- [Anti-Scam Checklist](#anti-scam-checklist)
- [What is wRTC?](#what-is-wrtc)
- [Buying wRTC on Aerodrome](#buying-wrtc-on-aerodrome)
- [Bridging RTC to wRTC](#bridging-rtc-to-wrtc)
- [Withdrawing wRTC to RTC](#withdrawing-wrtc-to-rtc)
- [Quick Reference](#quick-reference)
- [Troubleshooting](#troubleshooting)

---

## Anti-Scam Checklist

Before every transaction, verify all canonical values:

| Check | Canonical Value | Verification |
|-------|-----------------|--------------|
| wRTC contract | `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6` | Base address, 0x + 40 hex characters |
| USDC contract | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` | Native USDC on Base |
| Aerodrome pool | `0x4C2A0b915279f0C22EA766D58F9B815Ded2d2A3F` | wRTC liquidity pool |
| Decimals | `6` | wRTC uses 6 decimal places |
| Official bridge | `https://bottube.ai/bridge/wrtc` | Bookmark this URL |
| Official swap | `https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6` | Verify from/to contracts |
| Live swap info | `https://rustchain.org/wallet/swap-info` | Should return Base/Aerodrome fields |

### Red Flags - Stop if you see these

- The wRTC contract does not match `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`.
- A page asks you to use an unrelated legacy route for the current live
  `/wallet/swap-info` flow.
- The bridge URL is not exactly `https://bottube.ai/bridge/wrtc`.
- A swap link points to unknown contracts or a chain other than Base.
- Someone sends a "better" bridge or swap link in a direct message.

---

## What is wRTC?

`wRTC` is the wrapped representation of RustChain Token (RTC) used by the
current Base/Aerodrome onramp.

| Feature | RTC (Native) | wRTC (Base) |
|---------|--------------|-------------|
| Network | RustChain | Base (`eip155:8453`) |
| Primary use | Mining rewards, RustChain services | Trading, liquidity, x402 payments |
| Wallet | RustChain wallet/miner id | Coinbase/Base-compatible 0x wallet |
| Swap venue | Bridge only | Aerodrome |
| Contract | Native ledger balance | `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6` |

### Why use wRTC?

1. Trade on Base DEX liquidity through Aerodrome.
2. Use USDC as the Base-side quote asset.
3. Keep bridge and swap instructions aligned with `/wallet/swap-info`.
4. Use Base-compatible wallets and tooling for x402 and agent payments.

---

## Buying wRTC on Aerodrome

### Prerequisites

- A Base-compatible wallet such as Coinbase Wallet, MetaMask, or another 0x
  wallet that supports Base.
- USDC on Base for the swap.
- ETH on Base for transaction fees.

### Step-by-Step Guide

#### Step 1: Open the official swap

Use the swap URL from the live API:

```text
https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6
```

You can also verify it directly:

```bash
curl -sk https://rustchain.org/wallet/swap-info
```

The response should include:

```json
{
  "network": "Base (eip155:8453)",
  "usdc_contract": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
  "wrtc_contract": "0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6",
  "aerodrome_pool": "0x4C2A0b915279f0C22EA766D58F9B815Ded2d2A3F",
  "reference_price_usd": 0.1
}
```

#### Step 2: Verify the contracts

1. Confirm the source asset is Base USDC:
   `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`.
2. Confirm the output asset is wRTC:
   `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`.
3. Confirm the wallet is connected to Base, not Ethereum mainnet or another
   chain.

#### Step 3: Connect wallet

1. Click **Connect Wallet** in Aerodrome.
2. Select your Base-compatible wallet.
3. Verify the connected account is the 0x address you intend to use.

#### Step 4: Enter swap amount

1. Input: USDC on Base.
2. Output: wRTC on Base.
3. Enter the amount of USDC you want to swap.
4. Review the estimated wRTC, route, price impact, and fees.

#### Step 5: Execute swap

1. Approve USDC if Aerodrome requires an allowance transaction.
2. Click **Swap**.
3. Review the transaction in your wallet.
4. Sign only if the wallet shows the expected Base network and contracts.

#### Step 6: Verify receipt

Check your wallet, the Aerodrome transaction, or BaseScan for the wRTC contract:

```text
0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6
```

---

## Bridging RTC to wRTC

Bridge native RTC earned on RustChain into wRTC on Base.

### Prerequisites

- RustChain wallet or miner id with RTC balance.
- Base-compatible destination wallet address (`0x...`).
- Access to the official BoTTube bridge.

### Step-by-Step Guide

#### Step 1: Open the official bridge

```text
https://bottube.ai/bridge/wrtc
```

#### Step 2: Select direction

Choose **RTC -> wRTC**.

#### Step 3: Enter destination

Use a Base address:

```text
0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6
```

The value above is the token contract, not your receiving wallet. Your receiving
wallet should also be an `0x` Base address.

#### Step 4: Review and confirm

1. Check the RTC amount.
2. Check the destination Base wallet.
3. Check bridge fees.
4. Confirm only after every field matches the intended transfer.

#### Step 5: Verify wRTC receipt

After completion, verify wRTC on Base with the canonical contract:

```text
0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6
```

---

## Withdrawing wRTC to RTC

Bridge wRTC on Base back to native RTC on RustChain.

### Prerequisites

- Base wallet with wRTC balance.
- ETH on Base for gas.
- RustChain wallet or miner id as the destination.

### Step-by-Step Guide

#### Step 1: Open bridge

```text
https://bottube.ai/bridge/wrtc
```

#### Step 2: Select direction

Choose **wRTC -> RTC**.

#### Step 3: Connect Base wallet

1. Connect the wallet holding wRTC.
2. Confirm the wallet network is Base.
3. Confirm the wRTC contract is
   `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`.

#### Step 4: Enter RustChain destination

Enter your RustChain wallet or miner id. Double-check it before signing.

#### Step 5: Confirm and monitor

1. Approve or sign the Base transaction.
2. Monitor the bridge UI until the transfer completes.
3. Verify the native RTC balance:

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=my-miner-id"
```

---

## Quick Reference

### Token Details

| Property | Value |
|----------|-------|
| Token name | Wrapped RustChain Token |
| Symbol | wRTC |
| Contract | `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6` |
| Decimals | 6 |
| Network | Base (`eip155:8453`) |
| Standard | ERC-20 compatible |

### Official Links

| Resource | URL |
|----------|-----|
| Aerodrome swap | <https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6> |
| BoTTube bridge | <https://bottube.ai/bridge/wrtc> |
| Live swap info | <https://rustchain.org/wallet/swap-info> |
| BaseScan wRTC | <https://basescan.org/address/0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6> |
| BaseScan USDC | <https://basescan.org/address/0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913> |
| DexScreener | <https://dexscreener.com/search?q=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6> |
| RustChain Explorer | <https://rustchain.org/explorer> |

### Bridge Fees

| Direction | Typical Fee | Time |
|-----------|-------------|------|
| RTC -> wRTC | Check bridge quote | Check bridge UI |
| wRTC -> RTC | Check bridge quote | Check bridge UI |

### Transaction Costs

| Operation | Network Fee |
|-----------|-------------|
| Aerodrome swap | Base gas |
| Bridge wRTC -> RTC | Base gas + bridge fee |
| Transfer wRTC | Base gas |

---

## Troubleshooting

### Common Issues

#### Issue: "Wrong network"

Solution:

1. Switch the wallet to Base.
2. Reopen the Aerodrome or bridge page.
3. Confirm the wallet account is still the intended one.

#### Issue: "Token not found"

Solution:

1. Add wRTC manually with contract
   `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`.
2. Verify decimals are `6`.
3. Verify the network is Base.

#### Issue: "Insufficient gas"

Solution:

1. Keep ETH on Base for gas.
2. Do not use Ethereum mainnet ETH for Base transactions.
3. Retry with a smaller amount if the wallet needs a gas buffer.

#### Issue: "Bridge transaction pending"

Solution:

1. Wait for the bridge UI to update.
2. Check the Base transaction status on BaseScan.
3. Check the RustChain explorer for the corresponding native-side balance.
4. Contact official support with transaction hash if it remains pending.

#### Issue: "Slippage tolerance exceeded"

Solution:

1. Check the Aerodrome quote and pool liquidity.
2. Try a smaller swap.
3. Adjust slippage carefully.
4. Verify the contracts again before signing.

#### Issue: "Invalid destination address"

Solution:

- Base wallet addresses use `0x` plus 40 hexadecimal characters.
- RustChain wallet/miner ids are native RustChain identifiers.
- Do not paste a Base address where the UI requests a RustChain destination,
  or a RustChain id where the UI requests a Base wallet.

### Safety Reminders

1. Never share seed phrases or private keys.
2. Never approve transactions you do not understand.
3. Always verify contract addresses character by character.
4. Bookmark official URLs.
5. Start with small amounts when testing a new path.
6. Use the live `/wallet/swap-info` endpoint as the source of truth.

---

## Additional Resources

- [RustChain Whitepaper](WHITEPAPER.md)
- [Protocol Specification](./PROTOCOL.md)
- [API Reference](./API.md)
- [Wallet User Guide](./WALLET_USER_GUIDE.md)
- [Onboarding Tutorial](./WRTC_ONBOARDING_TUTORIAL.md)

---

Questions? Open an issue on [GitHub](https://github.com/Scottcjn/Rustchain).
