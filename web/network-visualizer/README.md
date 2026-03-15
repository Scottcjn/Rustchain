# RustChain Network Topology Visualizer

Interactive real-time visualization of the RustChain peer-to-peer network.

## Features

- **Live Network Graph** — D3.js force-directed layout showing all connected nodes and their peer relationships
- **Hardware-Colored Nodes** — Each node is color-coded by CPU architecture (x86-64, ARM64, PowerPC, RISC-V, MIPS, SPARC, etc.)
- **Node Size by Activity** — Node radius scales with blocks mined
- **Hover Details** — Hover any node to see hardware type, uptime, blocks mined, antiquity multiplier, and peer count
- **Click to Inspect** — Sidebar panel shows full node details and connected peers with clickable navigation
- **Hardware Filtering** — Toggle hardware types on/off in the legend to isolate specific architectures
- **Search** — Filter nodes by name, ID, hardware type, or region
- **Real-Time API Polling** — Connects to the RustChain node API (`/health`, `/epoch`, `/api/peers`, `/api/nodes`) with 15-second refresh
- **Demo Mode** — Falls back to a realistic simulated topology when the API is unreachable
- **Zoom & Pan** — Scroll to zoom, drag to pan, with fit-to-view and pause controls

## Usage

Open `index.html` in any modern browser. No build step or dependencies to install — D3.js v7 is loaded from CDN.

```
# Local
open web/network-visualizer/index.html

# Or serve it
python -m http.server 8080 --directory web/network-visualizer
```

## API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Node health and version |
| `GET /epoch` | Current epoch and block height |
| `GET /api/peers` | Connected peer list with metadata |
| `GET /api/nodes` | Registered node list (fallback) |

## Configuration

Edit the constants at the top of the script in `index.html`:

```javascript
const API_BASE = "https://50.28.86.131";  // RustChain node URL
const POLL_INTERVAL = 15000;               // Refresh interval (ms)
```

## RustChain Hardware Types

| Type | Color | Antiquity Multiplier |
|------|-------|---------------------|
| x86-64 (Modern) | Blue | 1.0x |
| ARM64 | Green | 1.0x |
| x86 (32-bit) | Purple | 1.5x |
| PPC64LE | Orange | 1.8x |
| PowerPC 64 | Dark Orange | 2.0x |
| PowerPC | Gold | 2.5x |
| RISC-V | Pink | 1.0x |
| MIPS | Red | 1.0x |
| SPARC | Light Blue | 1.0x |
