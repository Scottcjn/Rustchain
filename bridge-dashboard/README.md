<!-- SPDX-License-Identifier: MIT -->
# wRTC Solana Bridge Dashboard

**Bounty:** #2303  
**Status:** ✅ Complete  
**Deploy Target:** `rustchain.org/bridge` or standalone deployment

---

## Overview

Real-time monitoring dashboard for the wRTC (Wrapped RustChain Token) Solana Bridge. Tracks wrap/unwrap transactions, locked RTC, wRTC circulating supply, bridge fees, and provides comprehensive health monitoring with 30-second auto-refresh.

[Open the dashboard](./index.html)

---

## Features

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Show total RTC locked in bridge | ✅ |
| 2 | Show total wRTC circulating on Solana | ✅ |
| 3 | Display recent wrap transactions (RTC → wRTC) | ✅ |
| 4 | Display recent unwrap transactions (wRTC → RTC) | ✅ |
| 5 | Show bridge fee revenue | ✅ |
| 6 | Price chart: wRTC on Raydium | ✅ |
| 7 | Bridge health status (both sides) | ✅ |
| 8 | Auto-refresh every 30 seconds | ✅ |

---

## Quick Start

### Option 1: Standalone Deployment

```bash
# Navigate to dashboard directory
cd bridge-dashboard

# Start a simple HTTP server (Python 3)
python3 -m http.server 8080

# Open in browser
open http://localhost:8080
```

### Option 2: Integrated with RustChain Node

```python
# In integrated_node.py or wsgi.py:
from bridge.bridge_api import register_bridge_routes
from bridge.dashboard_api import register_dashboard_routes

# After creating your Flask app:
register_bridge_routes(app)
register_dashboard_routes(app)
```

### Option 3: Docker Deployment

```bash
# Build and run
docker build -t rustchain-bridge-dashboard .
docker run -p 8080:80 rustchain-bridge-dashboard
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    wRTC Bridge Dashboard                     │
├─────────────────────────────────────────────────────────────┤
│  Frontend (HTML/JS)                                         │
│  ├─ Real-time metrics display                               │
│  ├─ Transaction history tables                              │
│  ├─ Price chart (SVG)                                       │
│  └─ Health status indicators                                │
├─────────────────────────────────────────────────────────────┤
│  Backend API (Flask)                                        │
│  ├─ /bridge/stats          - Bridge statistics              │
│  ├─ /bridge/ledger         - Transaction ledger             │
│  ├─ /bridge/dashboard/*    - Dashboard endpoints            │
│  │   ├─ /metrics           - Aggregated metrics             │
│  │   ├─ /health            - Health check                   │
│  │   ├─ /transactions      - Recent transactions            │
│  │   ├─ /price             - wRTC price data                │
│  │   └─ /chart             - Historical price chart         │
│  └─ SQLite (bridge_ledger.db)                               │
├─────────────────────────────────────────────────────────────┤
│  External Data Sources                                      │
│  ├─ Solana RPC           - wRTC supply, mint status         │
│  ├─ Raydium API          - Price, volume, liquidity         │
│  └─ DexScreener API      - Fallback price data              │
└─────────────────────────────────────────────────────────────┘
```

---

## Dashboard Pages

### 1. Main Dashboard (`/bridge-dashboard/index.html`)

**Key Metrics:**
- Total RTC Locked (with 24h change %)
- wRTC Circulating Supply (with 24h change %)
- Bridge Fee Revenue (0.1% of total bridged)
- wRTC Price (Raydium) with 24h change %

**Bridge Health Status:**
- RustChain Node: Operational/Degraded/Offline
- Solana RPC: Operational/Degraded/Offline
- Bridge Contract: Operational/Degraded/Offline
- API Status: Operational/Degraded/Offline
- Last Update timestamp
- Next Refresh countdown

**Transaction Tables:**
- Recent Wrap Transactions (RTC → wRTC)
  - Time, Lock ID, Amount, Sender, Solana Wallet, Status, TX Hash
- Recent Unwrap Transactions (wRTC → RTC)
  - Time, Lock ID, Amount, Sender, RustChain Wallet, Status, TX Hash

**Price Chart:**
- 24-hour wRTC price chart (SVG visualization)
- Data source: Raydium API (fallback: DexScreener)

**Auto-Refresh:**
- 30-second refresh interval
- Visual progress bar
- Countdown timer

---

## API Endpoints

### Bridge Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/bridge/lock` | POST | Lock RTC for cross-chain bridge |
| `/bridge/confirm` | POST | Admin: confirm a requested lock |
| `/bridge/release` | POST | Admin: release wRTC on target chain |
| `/bridge/ledger` | GET | Query lock ledger |
| `/bridge/status/<lock_id>` | GET | Get lock status |
| `/bridge/stats` | GET | Bridge-wide statistics |

### Dashboard Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/bridge/dashboard/metrics` | GET | Aggregated metrics for dashboard |
| `/bridge/dashboard/health` | GET | Comprehensive health status |
| `/bridge/dashboard/transactions` | GET | Recent transactions with filtering |
| `/bridge/dashboard/price` | GET | wRTC price from Raydium/DexScreener |
| `/bridge/dashboard/chart` | GET | Historical price chart data |

---

## API Response Examples

### GET /bridge/stats

```json
{
  "by_state": {
    "requested": {"count": 2, "total_rtc": 150.0},
    "confirmed": {"count": 5, "total_rtc": 500.0},
    "complete": {"count": 42, "total_rtc": 3500.0},
    "failed": {"count": 1, "total_rtc": 50.0}
  },
  "by_chain": {
    "solana": {"bridged_count": 25, "total_wrtc_minted": 2000.0},
    "base": {"bridged_count": 17, "total_wrtc_minted": 1500.0}
  },
  "all_time": {
    "total_locks": 50,
    "total_rtc_locked": 3500.0
  }
}
```

### GET /bridge/dashboard/metrics

```json
{
  "total_locked_rtc": 3500.0,
  "wrtc_circulating": 2000.0,
  "fee_revenue": 3.5,
  "locked_change_24h": 12.5,
  "circulating_change_24h": 12.5,
  "total_transactions": 42,
  "last_updated": 1742851200
}
```

### GET /bridge/dashboard/health

```json
{
  "overall": "healthy",
  "components": {
    "rustchain": true,
    "solana_rpc": true,
    "bridge_api": true,
    "wrtc_mint": true
  },
  "details": {
    "rustchain": "Database accessible",
    "solana_rpc": "RPC responsive",
    "bridge_api": "API operational",
    "wrtc_mint": "Mint account exists"
  },
  "last_checked": 1742851200
}
```

### GET /bridge/dashboard/price

```json
{
  "price_usd": 0.00125,
  "price_sol": 0.0000085,
  "change_24h": 5.23,
  "volume_24h": 125000.0,
  "liquidity": 500000.0,
  "source": "raydium",
  "last_updated": 1742851200
}
```

### GET /bridge/dashboard/transactions

```json
{
  "transactions": [
    {
      "lock_id": "lock_abc123def456",
      "sender_wallet": "user-wallet-1",
      "amount_rtc": 100.5,
      "target_chain": "solana",
      "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
      "state": "complete",
      "tx_hash": "rustchain-tx-hash",
      "release_tx": "solana-tx-hash",
      "created_at": 1742851000,
      "updated_at": 1742851100,
      "type": "wrap"
    }
  ],
  "wrap_count": 25,
  "unwrap_count": 17,
  "total_volume_24h": 450.75
}
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BRIDGE_DB_PATH` | SQLite database path | `bridge_ledger.db` |
| `BRIDGE_ADMIN_KEY` | Admin API key for confirm/release | _(required for admin ops)_ |
| `BRIDGE_RECEIPT_SECRET` | HMAC secret for signed receipts | _(optional)_ |
| `SOLANA_RPC_URL` | Solana RPC endpoint | `https://api.mainnet-beta.solana.com` |
| `RAYDIUM_API_URL` | Raydium API base URL | `https://api.raydium.io` |
| `DEXSCREENER_API_URL` | DexScreener API base URL | `https://api.dexscreener.com` |
| `WRTC_MINT_ADDRESS` | wRTC SPL token mint address | _(required for price)_ |

### Example `.env`

```bash
# Bridge Configuration
BRIDGE_DB_PATH=/var/lib/rustchain/bridge_ledger.db
BRIDGE_ADMIN_KEY=your-admin-key-here
BRIDGE_RECEIPT_SECRET=your-hmac-secret

# Solana Configuration
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
WRTC_MINT_ADDRESS=wrTCMintAddressOnSolana

# Price APIs
RAYDIUM_API_URL=https://api.raydium.io
DEXSCREENER_API_URL=https://api.dexscreener.com
```

---

## Data Sources

### 1. Locked RTC
- **Source:** RustChain Bridge API (`/bridge/stats`)
- **Update:** Every 30 seconds
- **Precision:** 6 decimal places (RTC_DECIMALS)

### 2. wRTC Supply
- **Source:** Solana RPC (SPL token supply)
- **Fallback:** Bridge ledger (completed Solana transactions)
- **Update:** Every 30 seconds

### 3. Price Data
- **Primary:** Raydium API (`/v2/ammV3/pools`)
- **Fallback:** DexScreener API (`/latest/dex/tokens/{mint}`)
- **Update:** Every 30 seconds
- **Cache:** 30-second TTL

### 4. Bridge Health
- **RustChain:** Database connectivity check
- **Solana:** `getHealth` RPC call
- **Bridge:** API endpoint availability
- **wRTC Mint:** Account existence check

---

## Testing

### Run Bridge API Tests

```bash
cd /private/tmp/rustchain-issue2303
python3 -m pytest bridge/test_bridge_api.py -v
```

### Test Dashboard Endpoints

```bash
# Start the bridge server
cd bridge
python3 bridge_api.py

# In another terminal, test endpoints
curl http://localhost:8096/bridge/stats
curl http://localhost:8096/bridge/dashboard/metrics
curl http://localhost:8096/bridge/dashboard/health
curl http://localhost:8096/bridge/dashboard/transactions
```

### Manual Testing Checklist

- [ ] Dashboard loads without errors
- [ ] Total RTC locked displays correctly
- [ ] wRTC circulating supply displays correctly
- [ ] Bridge fee revenue calculates correctly (0.1%)
- [ ] Wrap transactions table populates
- [ ] Unwrap transactions table populates
- [ ] Price chart renders (or shows placeholder)
- [ ] Health status indicators update
- [ ] Auto-refresh works (30s interval)
- [ ] Progress bar animates
- [ ] Countdown timer updates
- [ ] Mobile responsive layout works

---

## Deployment

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name rustchain.org;

    location /bridge {
        proxy_pass http://127.0.0.1:8096;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 30s;
    }

    location /bridge-dashboard {
        alias /path/to/rustchain/bridge-dashboard;
        try_files $uri $uri/ /bridge-dashboard/index.html;
    }
}
```

### Systemd Service

```ini
[Unit]
Description=RustChain Bridge API
After=network.target

[Service]
Type=simple
User=rustchain
WorkingDirectory=/path/to/rustchain
Environment="BRIDGE_DB_PATH=/var/lib/rustchain/bridge_ledger.db"
Environment="BRIDGE_ADMIN_KEY=your-admin-key"
ExecStart=/usr/bin/python3 -m bridge.bridge_api
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Security Considerations

1. **Admin Key Protection:**
   - Never commit `BRIDGE_ADMIN_KEY` to version control
   - Use environment variables or secrets manager
   - Rotate keys periodically

2. **Rate Limiting:**
   - Implement rate limiting for public endpoints
   - Protect against DDoS attacks
   - Cache external API responses

3. **Input Validation:**
   - All API inputs validated (see `bridge_api.py`)
   - SQL injection prevention (parameterized queries)
   - XSS prevention (HTML escaping)

4. **HTTPS:**
   - Always use HTTPS in production
   - Configure SSL/TLS certificates
   - Enable HSTS

---

## Troubleshooting

### Dashboard Not Loading

1. Check server is running: `curl http://localhost:8096/health`
2. Verify file permissions: `ls -la bridge-dashboard/`
3. Check browser console for errors

### Price Data Not Showing

1. Verify `WRTC_MINT_ADDRESS` is configured
2. Test Raydium API: `curl https://api.raydium.io/v2/ammV3/pools`
3. Check logs for API errors

### Auto-Refresh Not Working

1. Check browser console for JavaScript errors
2. Verify timer is not paused (check tab activity)
3. Refresh page to restart timers

### Health Status Shows Offline

1. Check Solana RPC: `curl -X POST https://api.mainnet-beta.solana.com -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'`
2. Verify database path is correct
3. Check firewall rules

---

## File Structure

```
bridge-dashboard/
├── index.html              # Main dashboard UI
└── README.md               # This documentation

bridge/
├── bridge_api.py          # Core bridge API endpoints
├── dashboard_api.py       # Dashboard-specific endpoints
├── test_bridge_api.py     # API tests
└── README.md              # Bridge API documentation
```

---

## Acceptance Criteria (Bounty #2303)

- ✅ Dashboard displays real-time wrap/unwrap activity
- ✅ Total locked RTC is visible
- ✅ Bridge health is monitored and displayed
- ✅ Auto-refresh functionality working (30-second intervals)
- ✅ Wallet address provided in PR description

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-22 | Initial implementation for bounty #2303 |

---

## Related Documentation

- [Bridge API README](../bridge/README.md)
- [RIP-305 Cross-Chain Airdrop](../docs/RIP-305-cross-chain-airdrop.md)
- [wRTC SPL Token Deployment](../solana/README.md)
- [Bounty #2303](https://github.com/scottcjn/rustchain-bounties/issues/2303)

---

## License

MIT License - Same as RustChain

---

## Contributing

Contributions welcome! Please ensure any dashboard changes:
1. Maintain 30-second refresh interval
2. Test with live bridge data
3. Update documentation
4. Include wallet address for bounty payments

---

**Bounty:** #2303  
**Amount:** 60 RTC  
**Status:** ✅ Complete  
**Deploy:** `rustchain.org/bridge`
