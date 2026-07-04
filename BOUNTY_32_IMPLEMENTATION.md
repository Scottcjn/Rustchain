# Bounty #32: RTC/ERG Trading Pair on Spectrum DEX

## Overview

Implementation of RTC token on Ergo blockchain, cross-chain bridge, and Spectrum DEX liquidity pool.

**Bounty:** 150 RTC
**Status:** Implemented

## Components

### 1. Token Issuance (`ergo-anchor/rtc_token_issuance.py`)

Issues RustChain Token (RTC) as an Ergo native token following EIP-4 standard.

| Property | Value |
|----------|-------|
| Name | RustChain Token |
| Symbol | RTC |
| Decimals | 6 |
| Initial Supply | 100,000,000 |

**Usage:**
```bash
export ERGO_NODE="http://your-ergo-node:9053"
export ERGO_API_KEY="your-api-key"
export ERGO_WALLET_PASSWORD="your-password"

python ergo-anchor/rtc_token_issuance.py
```

### 2. Bridge Contract (`ergo-anchor/rtc_bridge.py`)

Lock RTC on RustChain, mint eRTC on Ergo. Burn eRTC, unlock RTC.

**Flow:**
```
RustChain                           Ergo
   |                                  |
   |-- Lock RTC (bridge_locks) ------>|
   |                                  |-- Mint eRTC (2-of-3 multisig)
   |                                  |
   |<-- Burn eRTC -------------------|
   |-- Unlock RTC ------------------>|
```

**Usage:**
```bash
# Lock RTC on RustChain
python ergo-anchor/rtc_bridge.py lock --amount 1000 --recipient 9h4...

# Mint eRTC on Ergo (after lock confirmed)
python ergo-anchor/rtc_bridge.py mint --tx_id <bridge_tx_id>

# Burn eRTC to unlock RTC
python ergo-anchor/rtc_bridge.py burn --tx_id <bridge_tx_id> --amount 500

# Check status
python ergo-anchor/rtc_bridge.py status --tx_id <bridge_tx_id>

# List pending bridges
python ergo-anchor/rtc_bridge.py pending
```

### 3. Spectrum DEX Pool (`ergo-anchor/spectrum_pool.py`)

Create and manage RTC/ERG liquidity pool on Spectrum DEX.

| Parameter | Value |
|-----------|-------|
| Initial RTC | 1,000 |
| Initial ERG | 67.0 |
| Price | 1 RTC = 0.067 ERG (~$0.10) |

**Usage:**
```bash
# Create pool
python ergo-anchor/spectrum_pool.py create

# Add liquidity
python ergo-anchor/spectrum_pool.py add --rtc 500 --erg 33.5

# Check status
python ergo-anchor/spectrum_pool.py status
```

## Environment Variables

```bash
ERGO_NODE=http://localhost:9053          # Ergo node URL
ERGO_API_KEY=                            # Ergo API key (optional)
ERGO_WALLET_PASSWORD=                    # Ergo wallet password
RTC_ERC_TOKEN_ID=                        # Token ID after issuance
SPECTRUM_API=https://api.spectrum.fi     # Spectrum API endpoint
SPECTRUM_UI=https://spectrum.fi          # Spectrum UI URL
BRIDGE_DB=/root/rustchain/bridge.db     # Bridge database path
```

## Architecture

```
ergo-anchor/
├── ergo_miner_anchor.py      # Miner anchor TX (existing)
├── rustchain_ergo_anchor.py  # State anchoring (existing)
├── rtc_token_issuance.py     # Token issuance (new)
├── rtc_bridge.py             # Bridge contract (new)
├── spectrum_pool.py          # DEX pool (new)
└── config/
    └── rustchain.conf
```

## Security

- Bridge uses 2-of-3 multisig for minting authorization
- 0.30% bridge fee on lock operations
- Min/Max lock amounts enforced (1 RTC - 10M RTC)
- All transactions signed via Ergo wallet

## Verification

1. **Token Issuance:** Check transaction on Ergo Explorer with returned token ID
2. **Bridge:** Monitor `bridge_locks` table for status transitions
3. **Pool:** View on Spectrum UI or query via API

## References

- [EIP-4: Ergo Token Standard](https://github.com/ergoplatform/EIPs/blob/master/EIP-0004/EIP-0004.md)
- [Spectrum DEX](https://spectrum.fi)
- [Ergo Node API](https://github.com/ergoplatform/sigma/blob/master/docs/api.md)
