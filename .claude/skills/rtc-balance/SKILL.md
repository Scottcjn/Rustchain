---
name: rtc-balance
description: Check RustChain wallet balance, epoch info, and network status via the public RPC
author: Emanon4
tags: [rustchain, cryptocurrency, wallet, balance-checker]
---

# /rtc-balance — RustChain Wallet Balance Checker

## Installation

Copy this folder (`.claude/skills/rtc-balance/`) into your project's `.claude/skills/` directory. Claude Code automatically loads skills from that path.

```
mkdir -p .claude/skills
cp -r path/to/rtc-balance .claude/skills/rtc-balance
```

Requires `curl` (pre-installed on macOS and most Linux distributions). No additional dependencies.

## Usage

```
/rtc-balance <wallet_name>
```

`<wallet_name>` is your RustChain wallet address or miner ID.

## Procedure (executed on invocation)

When invoked with `<wallet_name>`, perform these steps in order:

### Step 1 — Fetch wallet balance

```
curl -sS --max-time 8 "https://rustchain.org/wallet/balance?miner_id=<wallet_name>"
```

Parse the JSON response:
- If the response contains `"amount_rtc"`: extract that float value as the balance
- If the response is empty or `curl` exits non-zero: the node is unreachable, skip to Step 3a

### Step 2 — Fetch network status

```
curl -sS --max-time 8 "https://rustchain.org/epoch"
```

Parse the JSON response for these fields:
- `epoch`: int — current epoch number
- `slot`: int — current slot within the epoch
- `enrolled_miners`: int — number of active miners

### Step 3a — Node offline path

If Step 1 or Step 2 failed (curl timeout or non-JSON response):

```
Error: Node unreachable
Check your network connection or try again later.
```

### Step 3b — Success path

Format and print the output:

```
Wallet: <wallet_name>
Balance: <amount_rtc> RTC ($<usd> USD)
Epoch: <epoch> | Slot: <slot> | Miners online: <count>
```

Where:
- `amount_rtc` = float from Step 1 (default `0.0` if wallet not found)
- `usd` = `amount_rtc * 0.10` (reference rate: 1 RTC = $0.10 USD)
- `epoch`, `slot`, `enrolled_miners` = integers from Step 2

### Error handling

| Scenario | Behavior |
|----------|----------|
| Wallet not found (API returns `{"amount_rtc": 0.0}`) | Show 0.00 RTC, continue |
| Node unreachable | Stop, print "Node unreachable" message |
| Empty wallet name | Print "Usage: /rtc-balance <wallet_name>" |

## Example

```
/rtc-balance Emanon4
```

Expected output:

```
Wallet: Emanon4
Balance: 0.00 RTC ($0.00 USD)
Epoch: 162 | Slot: 23411 | Miners online: 14
```
