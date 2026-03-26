# 🔴 Red Team Security Audit: Python SDK & Telegram Bot

**Bounty**: [#69](https://github.com/Scottcjn/rustchain-bounties/issues/69) — 75 RTC
**Auditor**: B1tor
**Date**: 2026-03-26
**Scope**: `sdk/python/rustchain_sdk/client.py` (306 lines), `tools/telegram-bot/rustchain_bot.py` (357 lines)

## Executive Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 2 |
| 🟠 High | 3 |
| 🟡 Medium | 4 |
| 🔵 Low | 3 |
| **Total** | **12** |

The Python SDK ships with **SSL verification disabled by default**, exposing all API traffic to MITM attacks. The Telegram bot has **no input sanitization** on the `/balance` command, allowing parameter injection.

## Findings

### 🔴 CRIT-01: SSL Verification Disabled by Default (SDK)
**File**: `sdk/python/rustchain_sdk/client.py:42`
`verify_ssl=False` by default → all traffic exposed to MITM.
**Fix**: Default `verify_ssl=True`, add `ca_bundle` param for self-signed certs.

### 🔴 CRIT-02: Private Key Transmitted in Plaintext (SDK)
**File**: `sdk/python/rustchain_sdk/client.py:198`
`transfer()` sends `private_key` in JSON payload over the wire.
Combined with CRIT-01, any MITM captures keys and drains wallets.
**Fix**: Client-side signing; never transmit private keys.

### 🟠 HIGH-01: No Input Validation on Balance Query (Bot)
**File**: `tools/telegram-bot/rustchain_bot.py:180`
`miner_id = ctx.args[0]` passed raw to API — path traversal / SSRF risk.
**Fix**: Regex validation `^[a-zA-Z0-9_\-]{1,64}$`

### 🟠 HIGH-02: Retry Amplification (SDK)
No upper bound on `retry_count` — can flood node API.
**Fix**: Cap at 5 retries, min 0.5s delay.

### 🟠 HIGH-03: Bot Token Exposure Risk (Bot)
No format validation or hardcode detection for bot token.
**Fix**: Validate format, warn on potential hardcoding.

### 🟡 MED-01: No Rate Limiting on SDK
Unlimited requests can overwhelm node API.
**Fix**: Built-in token bucket rate limiter.

### 🟡 MED-02: Negative Transfer Amount (SDK)
No validation — negative amounts pass through.
**Fix**: Validate `amount > 0` and cap at safety limit.

### 🟡 MED-03: Race Condition in Bot Rate Limiter
Non-atomic dict operations under asyncio allow bypass.
**Fix**: `asyncio.Lock` per user.

### 🟡 MED-04: Unbounded Memory in Rate Limiter
No eviction of stale user entries — memory grows forever.
**Fix**: Max users cap + periodic cleanup.

### 🔵 LOW-01: No Security Event Logging
### 🔵 LOW-02: Error Messages Leak Internal Details
### 🔵 LOW-03: No Price Validation on DexScreener Response

## Deliverables
- `README.md` — This report
- `patches/sdk_secure_defaults.py` — SDK patches
- `patches/bot_input_validation.py` — Bot patches
- `tests/test_security_patches.py` — 23 tests validating all fixes

## RTC Wallet
`RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`
