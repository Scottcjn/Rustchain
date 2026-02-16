# RustChain Network Status Page

A simple GitHub Pages-friendly network health dashboard for issue #161.

## Path

- `web/status/index.html`

## Features

- Polls all 3 node health endpoints every 60 seconds
- Status indicators: green (healthy), yellow (>2s), red (down)
- Shows:
  - response time (ms)
  - current epoch
  - active miners count (`/api/miners`)
  - last block time (if available in health payload)
  - tip age slots
- Historical uptime windows (24h / 7d / 30d)
- Response-time mini chart per node
- 30-day local history retention via `localStorage`

## Run locally

```bash
cd web/status
python3 -m http.server 8080
# open http://localhost:8080
```

> Note: If node endpoints do not allow CORS from your browser origin, use a lightweight proxy or host from an allowed domain.
