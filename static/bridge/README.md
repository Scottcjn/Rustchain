w RT Solana Bridge Dashboard

Real-time monitoring dashboard for the RustChain → Solana cross-chain bridge.

## Features

- **Total RTC Locked**: Shows the amount of RTC tokens locked in the bridge
- **wRTC Circulating**: Shows the total wRTC tokens on Solana
- **Wrap/Unwrap Volume**: Transaction volume for both directions
- **Price Chart**: Real-time wRTC price from Raydium/DexScreener
- **Bridge Health**: Status monitoring for all bridge components
- **Fee Revenue**: Bridge fee collection statistics
- **Transaction History**: Recent wrap/unwrap transactions
- **Auto-refresh**: Updates every 30 seconds

## Files

- `dashboard.html` - Main dashboard (new comprehensive version)
- `index.html` - Simple monitor (legacy)
- `update_stats.py` - Stats generation script

#+ API Integration

The dashboard integrates with:

1. **DexScreener API** - For wRTC price data
   - Endpoint: `https://api.dexscreener.com/latest/dex/tokens/{WRTC_MINT}`
   
2. **RustChain Bridge API** - For bridge statistics
   - `GET /bridge/stats` - Overall stats
   - `GET /bridge/ledger` - Transaction history
   
3. **Solana RPC** - For wRTC token supply (planned)

## Configuration

Key configuration in the JavaScript:

```javascript
const CONFIG = {
    WRTC_MINT: '12TAdKX`xGF6oCv4rqDz2NkgxjyHq6HQKoxKZYgf5i4X',
    RAYDIUM_POOL: '8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb',
    BRIDGE_API: 'https://rustchain.org/api/bridge',
    REFRESH_INTERVAL: 30000, // 30 seconds
    FEE_RATE: 0.001, // 0.1%
};
```

## Deployment

The dashboard can be deployed to:
- `rustchain.org/bridge/dashboard.html`
- Standalone static hosting

## Bounty

This dashboard was created for RustChain Bounty #2303.

**Wallet Address**: `9dRRMiHiJwjF3VW8pXtKDtpmmxAPFy3zWgV2JY5H6eeT`

## License

MIT License - Elyan Labs