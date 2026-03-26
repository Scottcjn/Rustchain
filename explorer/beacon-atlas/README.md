# ⚡ Beacon Atlas — Interactive Agent Trust Network Visualization

A real-time, interactive force-directed graph showing every miner, beacon agent, and trust connection in the RustChain network.

## Features

- **Force-directed graph** — D3.js physics simulation with drag, zoom, pan
- **Architecture coloring** — G4 (amber), G5 (blue), POWER8 (purple), x86 (green), ARM (red)
- **Beacon agents** — Hexagonal nodes, distinct from miner circles
- **Node size** — Scaled by trust score / antiquity multiplier
- **Edge types** — Trust connections (cyan) vs attestation links (amber), thickness = strength
- **Live API data** — Fetches from `/api/miners`, `/beacon/atlas`, `/epoch`
- **Filter by architecture** — Click filter buttons to isolate node types
- **Search** — Real-time search by miner ID or agent name
- **Click for details** — Info panel shows wallet, architecture, attestation, balance, connections
- **Auto-refresh** — Pulls fresh data every 30 seconds
- **Responsive** — Works on mobile, adapts to window resize
- **Zero dependencies** — D3.js loaded from CDN, no build step
- **GitHub Pages ready** — Pure static site, deploy anywhere

## Usage

```bash
# Open locally
open explorer/beacon-atlas/index.html

# Or serve
cd explorer/beacon-atlas && python -m http.server 8080
# Then open http://localhost:8080
```

## Demo Mode

If the RustChain API is unreachable, the atlas shows demo nodes with sample architecture distribution and trust links.

## Files

| File | Purpose |
|------|---------|
| `index.html` | UI layout, CSS, structure |
| `beacon_atlas.js` | D3.js visualization engine |
| `README.md` | This documentation |

## Keyboard / Mouse

| Action | Effect |
|--------|--------|
| Scroll | Zoom in/out |
| Drag background | Pan |
| Drag node | Move node (physics re-settle) |
| Click node | Show details panel |
| Type in search | Filter nodes by name/ID |
| Click filter button | Show only that architecture |

## Screenshots

The visualization renders as a dark-themed force-directed graph with glowing colored nodes representing different hardware architectures, connected by semi-transparent trust links.

## Bounty

Closes https://github.com/Scottcjn/Rustchain/issues/1856
