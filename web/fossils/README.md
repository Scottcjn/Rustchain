# The Fossil Record — Attestation Archaeology Visualizer

**Bounty #2311 · 75 RTC**

Interactive D3.js visualization of RustChain attestation history, rendered as geological strata.

## Features

- **Stacked Area Chart** — architecture layers ordered by age (68K deepest, x86 on top)
- **Streamgraph Mode** — centered flow view for temporal dynamics
- **Normalized Mode** — percentage-based to see market share shifts
- **Interactive Tooltips** — hover any layer for miner count, epoch, RTC earned, share %
- **Architecture Color Coding** — 11 families from amber (68K) to pale grey (x86)
- **Epoch Settlement Markers** — vertical dashed lines every 25 epochs
- **First Appearance Markers** — shows when each architecture joined the network
- **Responsive** — works on desktop and mobile
- **No Backend Required** — static HTML + D3.js, deployable at `rustchain.org/fossils`

## Architecture Color Map

| Architecture | Color | Depth |
|---|---|---|
| 68K | Dark Amber | Deepest |
| G3 | Warm Gold | |
| G4 (PowerPC) | Copper | |
| G5 (PowerPC) | Bronze | |
| SPARC | Crimson | |
| MIPS | Jade | |
| POWER8 | Deep Blue | |
| ARM | Saddle Brown | |
| Apple Silicon | Silver | |
| Modern x86 | Pale Grey | |
| Virtual Machine | Dark Grey | Surface |

## Deployment

Copy `index.html` to `rustchain.org/fossils/`:

```bash
cp web/fossils/index.html /var/www/rustchain/fossils/index.html
```

No build step, no dependencies beyond D3.js (loaded from CDN).

## Production Integration

The demo uses generated data. To connect to live RustChain data:

1. Replace `generateData()` with a fetch to the attestation API
2. API endpoint: `GET /api/attestations/history?group_by=arch&bucket=epoch`
3. Expected format: `[{epoch, 68k, g4, g5, sparc, mips, power8, arm, apple_silicon, x86, vm, totalRTC}]`

## Tech Stack

- D3.js v7 (CDN)
- Vanilla JS, no framework
- CSS custom properties for theming
- Vintage terminal aesthetic matching rustchain.org
