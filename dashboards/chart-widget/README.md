# RustChain Price Chart Widget

An embeddable, standalone chart widget showing RustChain network stats in real time.

## What it shows

- **Transfer Volume** — RTC transferred per epoch, derived from live network data
- **Active Miners** — enrolled miners trend across epochs
- **Epoch Rewards** — RTC distributed per epoch over time

All panels support interactive zoom, pan, and crosshair inspection.

## Usage

### Option 1: iframe embed

```html
<iframe
  src="https://your-host/dashboards/chart-widget.html"
  width="100%"
  height="780"
  frameborder="0"
  style="border-radius:8px;"
></iframe>
```

### Option 2: Open directly in browser

Just open `chart-widget.html` in any modern browser. No build step, no dependencies to install.

## API

The widget connects to `https://rustchain.org` (self-signed cert). It fetches:

- `GET /epoch` — current epoch, enrolled miners, epoch pot
- `GET /api/miners` — live miner attestations

Data refreshes automatically every 2 minutes. If the API is unreachable, the widget falls back to simulated data seeded from known network state.

**Note on self-signed certs:** The browser will block the API fetch unless you've accepted the certificate exception for `https://rustchain.org`. Visit that URL directly and accept the cert, then the widget will load live data.

## Time ranges

The range selector supports: 24h · 7d · 30d · All

## Files

```
chart-widget.html   — self-contained widget (HTML + CSS + JS, no build step)
README.md           — this file
```

## Dependencies (CDN)

- [lightweight-charts v4.1.3](https://github.com/tradingview/lightweight-charts) — TradingView charting library
