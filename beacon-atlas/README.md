# Beacon Atlas — Agent City Visualization

**Bounty #159: Beacon Atlas D3.js Visualization** — 50 RTC

Interactive D3.js force-directed graph of the RustChain agent network across 4 cities.

## Features

- **15 agents** across 4 cities (Alpha, Beta, Gamma, Delta)
- **15 properties** sized by valuation
- **35 connections**: heartbeat (blue), contract (green), mayday (red), ownership (orange)
- **Force-directed layout** with city hub pinning
- **Interactive**: zoom, pan, drag, search, filter by city
- **Click any node** for detailed sidebar (agents, properties, contracts, mayday signals)
- **Hover tooltips** with key metrics
- Pulsing rings on high-activity agents (>80%)

## Usage

Open `index.html` in a browser (no server required — all data is embedded).

## Data Source

Replace the hardcoded data in `app.js` with beacon-skill API calls:

```javascript
// Replace AGS, PROPS, CONNS arrays with:
fetch('http://50.28.86.131/api/agents')
  .then(r => r.json())
  .then(data => { /* use data */ });
```

## Files

- `index.html` — Main HTML (5KB)
- `app.js` — Application logic (20KB)
- `README.md` — This file

## Payout

- ETH/Base: `0x010A63e7Ee6E4925d2a71Bc93EA5374c9678869b`
- RTC: `RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff`
- GitHub: @kuanglaodi2-sudo
