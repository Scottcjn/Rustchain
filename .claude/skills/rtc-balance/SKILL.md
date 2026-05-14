---
name: rtc-balance
description: Check RustChain wallet balance, epoch info, and network status
author: Emanon4
tags: [rustchain, cryptocurrency, wallet, balance-checker]
---

# /rtc-balance — RustChain Wallet Balance Checker

## Usage

```
/rtc-balance <wallet_name>
```

## Description

Queries the RustChain node API to check a wallet's RTC balance and current network status.

## Output Format

```
Wallet: <wallet_name>
Balance: <amount> RTC ($<usd> USD)
Epoch: <epoch> | Slot: <slot> | Miners online: <count>
```

## API Calls

1. **Wallet Balance**: GET https://50.28.86.131/wallet/balance?miner_id={wallet_name}
   - Returns: {"amount_rtc": float, "miner_id": string}

2. **Network Status**: GET https://50.28.86.131/epoch
   - Returns: {"epoch": int, "slot": int, "enrolled_miners": int}

## Error Handling

- Wallet not found: Shows "0.00 RTC"
- Node offline: Shows "Node unreachable"
- Empty name: Shows usage hint

## Conversion

1 RTC = $0.10 USD (reference rate)

## Example

```
/rtc-balance Emanon4
```

Output:
```
Wallet: Emanon4
Balance: 0.00 RTC ($0.00 USD)
Epoch: 162 | Slot: 23411 | Miners online: 14
```
