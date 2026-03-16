# Bounty Contribution

This addresses issue #1436: feat: embeddable price chart widget (bounty #26)

## Description
## Summary

Closes #26 — TradingView-style chart widget showing RustChain network stats in real time.

**What's in `dashboards/chart-widget/`:**

- `chart-widget.html` — fully self-contained, zero build step required
- `README.md` — embed instructions and API notes

**Charts:**
- Transfer volume per epoch (area, gold)
- Active miners trend (area, green)
- Epoch rewards history (area, blue)

**Features:**
- Fetches live data from `/epoch` + `/api/miners` every 2 minutes
- Time range selector: 24h

## Payment
0x4F666e7b4F63637223625FD4e9Ace6055fD6a847
