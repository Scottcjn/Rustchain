# RTC Wallet Distribution Tracker

## Overview

A real-time web dashboard that tracks RTC token distribution across all wallets in the RustChain network.

**Reward:** 40 RTC bounty from [Task #159](https://github.com/Scottcjn/Rustchain/issues/159)

## Features

### ✅ Core Features (Delivered)

1. **Total wallets with non-zero balances** - Displays active wallet count
2. **Top holders table** - Ranked by balance, showing wallet ID, balance, and % of supply
3. **Distribution chart** - Pie chart showing token concentration
4. **Whale alerts** - Flags any wallet holding >1% of supply (83,000+ RTC)
5. **Gini coefficient** - Shows wealth inequality metric (0 = perfect equality, 1 = concentration)
6. **Auto-refresh** - Every 5 minutes

### 🎨 Additional Features

- **Founder wallet identification** - Labels known founder wallets:
  - `founder_community` - Community Fund
  - `founder_dev_fund` - Development Fund
  - `founder_team_bounty` - Team & Bounties
  - `founder_founders` - Founders Pool
- **Supply breakdown chart** - Shows founder vs community vs unminted tokens
- **Responsive design** - Mobile-friendly layout
- **Dark gradient theme** - Matches rustchain.org aesthetic
- **Real-time API integration** - Fetches live data from RustChain node

## Data Sources

The dashboard connects to the public RustChain APIs:

- **Miners API:** `GET https://rustchain.org/api/miners`
- **Balance API:** `GET https://rustchain.org/wallet/balance?miner_id=ID`

## Technical Details

### Implementation

- **Single HTML file** with embedded CSS and JavaScript
- **Chart.js** for interactive data visualization
- **Vanilla JavaScript** - No framework dependencies
- **REST API integration** - Fetches live data from RustChain node
- **Async/await** - Non-blocking data fetching
- **Promise.all** - Parallel API calls for better performance

### Key Metrics Displayed

| Metric | Description |
|--------|-------------|
| Total wallets | Number of wallets with non-zero balance |
| Total supply | 8,300,000 RTC (fixed) |
| In circulation | Sum of all wallet balances |
| % minted | Percentage of total supply in circulation |
| Gini coefficient | 0 = equality, 1 = extreme concentration |
| Whale threshold | 1% of supply (83,000+ RTC) |

### Color Coding

- **Founder wallets:** Yellow highlight (`#fff3cd`)
- **Whale wallets:** Red highlight (`#f8d7da`)
- **Community wallets:** Standard white background

## Installation & Usage

### Quick Start

1. Save `rtc-wallet-tracker.html` to your web server
2. Open in a browser
3. Dashboard will automatically load and refresh every 5 minutes

### Deployment Options

**Option A: GitHub Pages (Recommended)**
1. Upload to your GitHub repository
2. Enable GitHub Pages from repository settings
3. Access at `https://username.github.io/repo/rtc-wallet-tracker.html`

**Option B: Any Web Server**
- Apache, Nginx, or any static file hosting
- Just serve the HTML file

**Option C: Local Testing**
```bash
# Start a simple HTTP server
python3 -m http.server 8000
# Open http://localhost:8000/rtc-wallet-tracker.html
```

## API Endpoints Used

### 1. Get Miners List
```bash
curl https://rustchain.org/api/miners
```

Returns array of miners:
```json
[
  {
    "miner": "wallet_id_here",
    "device_arch": "M2",
    "hardware_type": "Apple Silicon (Modern)",
    ...
  }
]
```

### 2. Get Wallet Balance
```bash
curl "https://rustchain.org/wallet/balance?miner_id=wallet_id_here"
```

Returns:
```json
{
  "amount_i64": 159654480,
  "amount_rtc": 159.65448,
  "miner_id": "wallet_id_here"
}
```

## Bounty Requirements Met

✅ **Working tracker showing all wallets + balances + % of supply** (20 RTC)
- Fetches all miners from API
- Queries individual balances
- Displays top 50 holders
- Shows percentage of total supply

✅ **Distribution chart + whale alerts + Gini coefficient** (10 RTC)
- Interactive pie chart with Chart.js
- Whale detection and alerts (>1% supply)
- Gini coefficient calculation and display

✅ **Clean UI/output, labeled founder wallets, auto-refresh** (10 RTC)
- Modern gradient design
- Founder wallet identification and labeling
- 5-minute auto-refresh interval
- Responsive layout for mobile

## Screenshots

### Dashboard Overview
- Stats cards at the top
- Whale alerts (if any)
- Top 50 holders table
- Distribution analysis charts

### Key Visualizations
1. **Top Holders Pie Chart** - Shows distribution among top 20 wallets
2. **Supply Breakdown Doughnut** - Founder vs Community vs Unminted
3. **Gini Coefficient** - Wealth inequality metric

## Performance

- **Initial load:** ~2-5 seconds (depends on number of miners)
- **Auto-refresh:** Every 5 minutes
- **API calls:** Parallel batch fetching for faster results
- **Memory usage:** Minimal (client-side only)

## Browser Compatibility

- ✅ Chrome/Edge (latest)
- ✅ Firefox (latest)
- ✅ Safari (latest)
- ✅ Mobile browsers (iOS Safari, Chrome Mobile)

## Files

- `rtc-wallet-tracker.html` - Main dashboard (single file, self-contained)
- `test_rtc_tracker.py` - Python test script for validation
- `README.md` - This documentation

## Notes

- **Total supply:** Fixed at 8,300,000 RTC (no inflation)
- **Pre-mine:** 6% reserved for founder wallets
- **API rate limits:** None enforced at time of development
- **SSL:** Self-signed certificate (browsers may warn)

## Future Enhancements

Potential improvements for future versions:
- Historical tracking and charts
- Export to CSV/JSON
- WebSocket real-time updates
- Wallet search/filter
- Custom time range analysis
- Comparison with other networks

## Support

For issues or questions:
- GitHub Issue: https://github.com/Scottcjn/Rustchain/issues/159
- RustChain Docs: https://rustchain.org
- Block Explorer: https://rustchain.org/explorer

---

**Built with ❤️ by 绿龙一号 (Little Lobster) for the RustChain ecosystem**
