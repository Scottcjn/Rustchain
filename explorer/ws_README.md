# RustChain Block Explorer — Real-Time WebSocket Feed

## Bounty #2295 — 75 RTC

Live WebSocket updates to `rustchain.org/explorer`. No more page refreshes.

## What Was Added

### Real-Time Features
- **WebSocket connection** via Socket.IO to the RustChain event feed
- **Live block notifications** — new slots appear instantly without refresh
- **Live attestation feed** — miner attestations stream in real-time
- **Epoch settlement alerts** — toast notification when epoch advances
- **Auto-reconnect** with exponential backoff (3s → 30s max)
- **Connection status indicator** — live dot in header (green=connected, amber=connecting, red=offline)
- **Sound notifications** — press `S` to toggle epoch settlement chimes

### Bonus Features
- **Toast notifications** for all live events (up to 3 at once)
- **Miner count sparkline** — attestation rate chart in real-time
- **Live table updates** — new attestations highlighted in the Recent Miners table

## Architecture

```
explorer/enhanced-explorer.html   ← Updated with WebSocket client
websocket_feed.py                  ← Existing (bounty #748, reuses)
```

### WebSocket Events Consumed
| Event | Action |
|-------|--------|
| `new_block` | Updates slot/epoch display, shows toast |
| `attestation` | Highlights miner row, updates sparkline |
| `epoch_settlement` | Shows settlement toast, plays sound, refreshes stats |

### nginx Configuration
```nginx
location /ws/feed {
    proxy_pass http://127.0.0.1:5001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400;
}
```

## Running

The explorer at `rustchain.org/explorer` already connects to the WebSocket endpoint at `/ws/feed`. Ensure `websocket_feed.py` is running on port 5001 (or behind nginx).

```bash
# Start WebSocket feed (already implemented by bounty #748)
python3 websocket_feed.py --port 5001 --node https://50.28.86.131
```

## Bonus Checklist
- [x] Sound/visual notification on new epoch settlement (press S to toggle)
- [x] Miner count sparkline chart

**Wallet:** `C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg`
