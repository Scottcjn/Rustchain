# Wallet Network Error Handling Guide

## Overview

The RustChain wallet tools (`clawrtc wallet coinbase show`, GUI wallets) now include robust network error handling with:

- **Error Classification**: Distinguishes between network unreachable, timeouts, and API errors
- **Retry Strategy**: Exponential backoff for transient failures (3 retries, 1s→2s→4s delays)
- **User Diagnostics**: Clear troubleshooting hints for each error type

## Current Wallet Host

Use `https://rustchain.org` for public wallet and health queries.

If you see `Balance: (could not reach network)` from an older `clawrtc` helper build, verify the live node directly:

```bash
curl -sk https://rustchain.org/health | jq .
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME" | jq .
```

Older helper packages may still reference the retired `bulbous-bouffant.metalseed.net` host. Also note that current `clawrtc` releases do not expose a generic `clawrtc wallet show` command; the supported helper is `clawrtc wallet coinbase show`.

## Error Types

### 1. Network Unreachable

**Symptoms:**
- "Network unreachable: DNS resolution failed"
- "Network unreachable: Cannot connect to host:port"

**Causes:**
- No internet connection
- DNS server issues
- Firewall blocking the connection
- Node is offline

**Troubleshooting:**
```bash
# 1. Check internet connection
ping 8.8.8.8

# 2. Test DNS resolution
nslookup rustchain.org

# 3. Test connectivity to node
curl -skI https://rustchain.org/health

# 4. Check firewall settings
# Ensure outbound HTTPS (port 443) is allowed
```

### 2. Request Timeout

**Symptoms:**
- "Request timeout after 15s (tried 3x)"

**Causes:**
- Node is under heavy load
- Slow network connection
- Node is syncing

**Troubleshooting:**
```bash
# 1. Check node status
curl -sk https://rustchain.org/health | jq

# 2. Wait and retry (node may be busy)

# 3. Check your network speed
speedtest-cli  # or use your preferred speed test tool
```

### 3. API Error

**Symptoms:**
- "API error: HTTP 404" (wallet not found)
- "API error: HTTP 500" (server error)

**Causes:**
- Wallet doesn't exist on chain yet
- Node API bug
- Invalid request format

**Troubleshooting:**
```bash
# 1. Verify wallet address format
# Should be 0x + 40 hex characters for Base addresses

# 2. Check if wallet exists
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_ADDRESS"

# 3. Check node API status
curl -sk https://rustchain.org/api/stats | jq
```

## Retry Strategy

The wallet tools implement exponential backoff:

| Attempt | Delay Before Retry | Total Elapsed |
|---------|-------------------|---------------|
| 1       | -                 | 0s            |
| 2       | 1s                | ~1s           |
| 3       | 2s                | ~3s           |
| 4       | 4s                | ~7s           |

**Configuration:**
- `MAX_RETRIES = 3` (4 total attempts)
- `INITIAL_RETRY_DELAY = 1.0` seconds
- `MAX_RETRY_DELAY = 10.0` seconds (capped)
- `NETWORK_TIMEOUT = 15` seconds per request

## CLI Examples

### Show Wallet with Network Diagnostics

```bash
# Show Coinbase wallet (with balance check)
clawrtc wallet coinbase show

# Example output with network error:
#   Coinbase Base Wallet
#   Address:    0x1234567890abcdef...
#   Network:    Base (eip155:8453)
#   Balance:    Unable to fetch
#              Error: Network unreachable: DNS resolution failed
#
#   ⚠ Network Issue Detected:
#      DNS resolution failed for rustchain.org
#   Troubleshooting:
#      1. Check your internet connection
#      2. Verify DNS is working (try: ping ...)
#      3. Check firewall/proxy settings
#      4. Node may be temporarily offline
```

### GUI Wallet Error Dialog

When using the GUI wallet (`rustchain_wallet_gui.py` or `rustchain_wallet_secure.py`):

- Network errors trigger a popup dialog with troubleshooting hints
- Status bar shows abbreviated error message
- Balance display shows "0.00000000 RTC" when fetch fails

## Programmatic Usage

### Using the Retry Functions

```python
from coinbase_wallet import _fetch_with_retry, _check_network_connectivity

# Check connectivity first
is_reachable, error = _check_network_connectivity()
if not is_reachable:
    print(f"Network issue: {error}")
    # Show troubleshooting hints

# Fetch with retry logic
data, error = _fetch_with_retry(
    url="https://rustchain.org/wallet/balance?miner_id=0x...",
    max_retries=3,
    timeout=15
)

if error:
    if "Network unreachable" in error:
        # Handle network issues
    elif "timeout" in error:
        # Handle timeout
    elif "API error" in error:
        # Handle API error
else:
    balance = data.get("balance", 0)
    print(f"Balance: {balance}")
```

## Architecture

### Error Classification Flow

```
┌─────────────────────────────────────────────────────────┐
│                  Network Request Fails                   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Exception Type?       │
              └───────────────────────┘
                    │         │         │
          ┌─────────┘         │         └─────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │ Connection  │    │   Timeout   │    │    HTTP     │
   │    Error    │    │             │    │    Error    │
   └─────────────┘    └─────────────┘    └─────────────┘
          │                   │                   │
          ▼                   │                   │
   ┌─────────────┐            │                   │
   │  Check Net  │            │                   │
   │ Connectivity│            │                   │
   └─────────────┘            │                   │
          │                   │                   │
    ┌─────┴─────┐             │                   │
    │           │             │                   │
    ▼           ▼             │                   │
Reachable  Unreachable        │                   │
    │           │             │                   │
    │           ▼             │                   │
    │    ┌─────────────┐      │                   │
    │    │ Return Net  │      │                   │
    │    │ Unreachable │      │                   │
    │    └─────────────┘      │                   │
    │                         │                   │
    ▼           ▼             ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│              Retry with Exponential Backoff              │
│         (up to MAX_RETRIES attempts)                     │
└─────────────────────────────────────────────────────────┘
                          │
                    ┌─────┴─────┐
                    │           │
                    ▼           ▼
              Success       All Failed
                    │           │
                    │           ▼
                    │    ┌─────────────┐
                    │    │  Return     │
                    │    │  Error +    │
                    │    │  Hints      │
                    │    └─────────────┘
                    │
                    ▼
              ┌─────────────┐
              │  Return     │
              │  Data       │
              └─────────────┘
```

## Testing

Run the test suite:

```bash
cd /path/to/Rustchain/wallet
pytest tests/test_wallet_network_errors.py -v
```

Tests cover:
- Network connectivity checks (success, DNS failure, connection refused)
- Retry logic with exponential backoff
- Error classification (network, timeout, API)
- Balance extraction from various response formats
- User-facing error messages

## Related Files

- `wallet/coinbase_wallet.py` - Coinbase wallet with network error handling
- `wallet/rustchain_wallet_gui.py` - GUI wallet with retry logic
- `wallet/rustchain_wallet_secure.py` - Secure wallet with error diagnostics
- `wallet/tests/test_wallet_network_errors.py` - Test suite

## See Also

- [SDK Error Handling](../sdk/rustchain/exceptions.py)
- [API Reference](../docs/api-reference.md)
- [Troubleshooting Guide](../docs/FAQ_TROUBLESHOOTING.md)
