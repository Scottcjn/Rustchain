# The Fossil Record — Attestation Archaeology Visualizer

**Bounty #2311 · 75 RTC · Wallet: `C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg`**

Interactive D3.js visualization of RustChain attestation history, rendered as geological strata.

---

## Features

### Visualization Modes
- **Stacked Area** — architecture layers ordered by age (68K deepest, x86 on top)
- **Streamgraph** — centered flow view for temporal architecture dynamics
- **Normalized %** — percentage-based to see market share shifts over time
- **Stratigraphy** — geological stratum view where band width = active miner count

### Interactivity
- **Architecture Filter** — click legend items or use checkboxes to show/hide architecture families
- **Zoom In/Out/Reset** — control the visible epoch range
- **Hover Tooltips** — see architecture, epoch, miner count, share %, total RTC, era
- **Individual Miner Details** — click to see simulated miner ID, device name, fingerprint quality, RTC earned
- **Epoch Info Bar** — persistent bottom bar shows current epoch stats

### Architecture Color Map
| Architecture | Color | Era |
|---|---|---|
| 68K | Dark Amber | Genesis |
| G3 | Warm Gold | Genesis |
| G4 (PowerPC) | Copper | Genesis |
| G5 (PowerPC) | Bronze | Expansion |
| SPARC | Crimson | Expansion |
| MIPS | Jade | Consolidation |
| POWER8 | Deep Blue | Consolidation |
| ARM | Saddle Brown | Modern |
| Apple Silicon | Silver | Modern |
| Modern x86 | Pale Grey | Modern |
| Virtual Machine | Dark Grey | Modern |

### Data Layers
- **Epoch Settlement Markers** — vertical dashed lines every 25 epochs
- **First Appearance Markers** — shows when each architecture first joined the network
- **Era Labels** — Genesis / Expansion / Consolidation / Modern periods

## Tech
- D3.js v7 (CDN)
- Vanilla JS, no framework
- CSS custom properties for theming
- Responsive design (desktop + mobile)
- **No backend required** — static HTML, deployable at `rustchain.org/fossils`

## Production Integration

The demo uses generated data that simulates the RustChain attestation database. To connect to live data:

```javascript
// Replace generateData() with:
async function loadData() {
  const res = await fetch('/api/attestations/history?group_by=arch&bucket=epoch');
  const raw = await res.json();
  // Transform to: [{epoch, 68k, g4, g5, sparc, mips, power8, arm, apple_silicon, x86, vm, totalRTC, miners:{}}]
  return raw;
}
```

Expected API format: `GET /api/attestations/history?group_by=arch&bucket=epoch`

## Deployment

```bash
cp web/fossils/index.html /var/www/rustchain/fossils/index.html
# No build step required — pure HTML + D3.js CDN
```

## Wallet
`C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg`
