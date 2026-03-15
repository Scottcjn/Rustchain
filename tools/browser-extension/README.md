# RustChain RTC Balance — Browser Extension

Chrome/Firefox extension that displays your RTC wallet balance, network health, and latest block info directly from the toolbar.

## Features

- **RTC Balance** — Enter your Miner ID to see your current RTC balance.
- **Network Status** — Live health check showing online/offline, node version, and uptime.
- **Block Info** — Current epoch, slot, and chain height.
- **Persistent storage** — Your Miner ID is saved between sessions.
- **Fallback** — Tries `rustchain.org` first, falls back to the node IP if unreachable.

## Install (Chrome / Chromium)

1. Open `chrome://extensions/`
2. Enable **Developer mode** (top-right toggle).
3. Click **Load unpacked** and select this `browser-extension/` folder.
4. The **R** icon appears in your toolbar — click it, enter your Miner ID, and hit refresh.

## Install (Firefox)

1. Open `about:debugging#/runtime/this-firefox`
2. Click **Load Temporary Add-on** and select `manifest.json` from this folder.

## API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Node status, version, uptime |
| `GET /epoch` | Current epoch, slot, block height |
| `GET /wallet/balance?miner_id=<ID>` | RTC balance for a miner |

All requests go to `https://rustchain.org` with automatic fallback to `https://50.28.86.131`.

## File Structure

```
browser-extension/
  manifest.json   — Manifest V3 config
  popup.html      — Extension popup UI
  popup.js        — API calls and DOM logic
  popup.css       — Dark theme styles
  icons/          — SVG icons (16, 48, 128px)
  README.md       — This file
```

## License

Same as the RustChain project — see repository root.
