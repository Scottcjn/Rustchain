# RustChain Stats Dashboard

A live web dashboard displaying core RustChain network statistics with auto-refresh.

[Open the dashboard](./index.html)

## Features

- **Live Epoch Tracking** - Current epoch number and slot
- **Miner Count** - Active enrolled miners on the network
- **Circulating Supply** - Real-time RTC token supply metrics
- **Transaction Stats** - Total network transactions
- **Auto-Refresh** - Updates every 30 seconds automatically
- **Mobile Responsive** - Optimized for all screen sizes (+3 RTC bonus)
- **Dark Theme** - Easy on the eyes for 24/7 monitoring

## Quick Start

### Option 1: Open Directly (Simplest)

Just open `index.html` in your browser:

```bash
# macOS
open index.html

# Linux
xdg-open index.html

# Windows
start index.html
```

### Option 2: Local Web Server

For best experience, serve with a local web server:

```bash
# Using Python 3
python3 -m http.server 8080

# Then open: http://localhost:8080
```

### Option 3: VS Code Live Server

1. Install "Live Server" extension in VS Code
2. Right-click `index.html`
3. Select "Open with Live Server"

## Dashboard Metrics

| Metric | Description | API Endpoint |
|--------|-------------|--------------|
| **Current Epoch** | Current epoch number | `/epoch` |
| **Active Miners** | Number of enrolled miners | `/epoch.enrolled_miners` |
| **Circulating Supply** | Total RTC in circulation | Calculated |
| **Total Transactions** | Network transaction count | `/epoch.height` |
| **Current Slot** | Slot within current epoch | `/epoch.slot` |
| **Epoch POT** | Proof-of-transactions for epoch | `/epoch.epoch_pot` |
| **Block Height** | Current blockchain height | `/epoch.height` |
| **Node Version** | RustChain node version | `/health.version` |
| **Node Uptime** | How long node has been running | `/health.uptime_s` |

## Configuration

Edit the constants at the top of the `<script>` section:

```javascript
const API_BASE = 'https://rustchain.org';  // Change to your node URL
const REFRESH_INTERVAL = 30000;            // Refresh every 30 seconds
const MAX_SUPPLY = 8388608;                // Maximum RTC supply
```

## API Endpoints Used

This dashboard consumes the following public RustChain APIs:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/epoch` | GET | Current epoch, slot, height, miners, POT |
| `/health` | GET | Node version, uptime, status |
| `/api/miners` | GET | List of all enrolled miners |

## File Structure

```
rustchain-stats/
├── index.html          # Main dashboard (self-contained)
└── README.md           # This file
```

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Mobile)

## Troubleshooting

### Dashboard shows "Connection Error"

1. Check your internet connection
2. Verify the RustChain node is accessible
3. Check browser console for detailed errors (F12)

### Stats not updating

1. Click the "Refresh Now" button
2. Check if auto-refresh is enabled (30s interval)
3. Verify API endpoints are responding

### CORS errors in console

Run with a local web server (Option 2 above) instead of opening file directly.

## Customization

### Change Refresh Interval

```javascript
const REFRESH_INTERVAL = 60000;  // 60 seconds
```

### Change Color Theme

Edit CSS variables in the `<style>` section:

```css
:root {
    --accent: #58a6ff;      /* Primary accent color */
    --success: #3fb950;     /* Success/positive changes */
    --warning: #d29922;     /* Warning/error states */
}
```

### Add More Metrics

Add new stat cards in the HTML:

```html
<div class="stat-card">
    <div class="stat-icon">🎯</div>
    <div class="stat-label">Your Metric</div>
    <div class="stat-value" id="myValue">--</div>
</div>
```

Then update in JavaScript:

```javascript
document.getElementById('myValue').textContent = data.myMetric;
```

## Development

### Testing Locally

1. Make changes to `index.html`
2. Refresh browser (Ctrl/Cmd + R)
3. Check browser console for errors

### Production Deployment

Deploy to any static hosting:

- GitHub Pages
- Netlify
- Vercel
- Your own web server

```bash
# Deploy to GitHub Pages
git add dashboards/rustchain-stats/
git commit -m "feat: Add RustChain stats dashboard (#1600)"
git push
```

## Bounty Requirements

This dashboard fulfills [Issue #1600](https://github.com/Scottcjn/rustchain-bounties/issues/1600):

| Requirement | Status |
|-------------|--------|
| Web page with live epoch | ✅ |
| Miner count display | ✅ |
| Supply display | ✅ |
| Transactions display | ✅ |
| Auto-refresh | ✅ (30s) |
| Mobile responsive | ✅ (+3 RTC bonus) |
| Any framework | ✅ (Vanilla JS) |

## License

MIT - Same as main RustChain repository

## Support

For issues or questions:
- Open an issue on [rustchain-bounties](https://github.com/Scottcjn/rustchain-bounties)
- Check browser console for errors
- Verify API endpoints are accessible

---

**Built for RustChain** | [View on GitHub](https://github.com/Scottcjn/Rustchain)
