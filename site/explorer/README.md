# RustChain Block Explorer — Real-Time WebSocket Feed

Live block explorer for the RustChain blockchain with real-time WebSocket updates.

**Bounty:** #2295 — RustChain Block Explorer: Real-Time WebSocket Feed (75 RTC)  
**Wallet:** `C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg`

## Features

- **Real-time block feed** — new blocks appear instantly as they are mined
- **Live attestation stream** — miner attestations stream in real-time
- **Epoch settlement notifications** — visual alert when epoch advances
- **Connection status indicator** — shows connected/reconnecting/offline state
- **Auto-reconnect** — exponential backoff reconnection on disconnect
- **Activity sparkline** — visualizes event rate over time
- **Raw event log** — full event stream for debugging

## Architecture

```
Browser (explorer.js)
    |
    | WebSocket / Socket.IO
    v
RustChain Node (wsgi.py)
    |
    +-- websocket_feed.py (Socket.IO /ws/feed)
    |       |
    |       +-- EventBus (thread-safe pub/sub)
    |               |
    |               +-- Poller thread (polls /epoch, /api/miners every 5s)
    |
    +-- explorer_routes.py (/explorer/*)
            |
            +-- site/explorer/ (static HTML/CSS/JS)
```

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /explorer` | Main explorer page |
| `GET /explorer/<file>` | Static assets (JS, CSS) |
| `WS /ws/feed` | Socket.IO WebSocket feed |
| `GET /ws/feed/status` | Feed connection status |
| `GET /api/explorer/status` | Explorer configuration info |

## WebSocket Events

| Event | Description | Payload |
|---|---|---|
| `new_block` | New slot/block detected | `{slot, epoch, timestamp}` |
| `attestation` | Miner attestation received | `{miner, arch, multiplier, timestamp}` |
| `epoch_settlement` | Epoch advanced | `{epoch, new_epoch, total_rtc, miners}` |

## Running

### As part of the node (integrated):

```bash
# The explorer is auto-registered when running wsgi.py
gunicorn -w 4 -b 0.0.0.0:8099 wsgi:app --timeout 120

# Open in browser:
# http://localhost:8099/explorer
```

### Standalone WebSocket feed:

```bash
# Run just the WebSocket feed server
cd Rustchain
python websocket_feed.py --port 5001 --node https://your-node-url

# Connect the explorer to a different WS endpoint:
# http://localhost:8099/explorer?ws=ws://localhost:5001
```

### Nginx Configuration

Add to your nginx server block:

```nginx
# Explorer UI
location /explorer/ {
    proxy_pass http://127.0.0.1:8099/explorer/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

# WebSocket feed
location /ws/feed {
    proxy_pass http://127.0.0.1:8099/ws/feed;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400s;
    proxy_send_timeout 86400s;
}
```

## Development

### File Structure

```
site/explorer/
    index.html   — Main explorer page
    explorer.js  — Vanilla JS WebSocket client
    styles.css   — Explorer styling

node/
    explorer_routes.py  — Flask blueprint serving /explorer
    wsgi.py            — Registers explorer + websocket_feed

websocket_feed.py  — Socket.IO real-time event feed (root of repo)
```

## Tech Stack

- **Frontend:** Vanilla JS, Socket.IO client, Canvas sparkline
- **Backend:** Python Flask + Flask-SocketIO + threading
- **WebSocket:** Socket.IO protocol over pure WebSocket
- **Styling:** Custom CSS (dark terminal theme)
