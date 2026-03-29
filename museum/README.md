# Elyan Labs Vintage Hardware Museum 🖥️

A 3D WebGL interactive exhibit showcasing the real vintage hardware mining **RTC** on the RustChain network.

## Live Demo

Deploy anywhere as a static site. Open `index.html` in a browser, or run the included Python server:

```bash
python3 serve.py
# → http://localhost:8080
```

## Features

### 3D Environment (Three.js)
- Fully navigable 3D museum built with Three.js (CDN)
- Atmospheric fog, dynamic lighting, particle effects
- Minimap overlay showing player position and exhibit locations

### Navigation
| Action | Desktop | Mobile |
|--------|---------|--------|
| Move Forward | W / ↑ | Touch ▲ button |
| Move Back | S / ↓ | Touch ▼ button |
| Strafe Left | A / ← | Touch ◀ button |
| Strafe Right | D / → | Touch ▶ button |
| Look | Click canvas → mouse | Drag right half of screen |
| Up/Down | Q / E | — |
| Sprint | Shift | — |
| Inspect Exhibit | Click | Tap exhibit |

### Exhibits (Real Elyan Labs Hardware)
| Machine | Year | Multiplier | Notes |
|---------|------|-----------|-------|
| **IBM POWER8 S824** | 2014 | 1× | Centerpiece — 128 threads, 512 GB RAM |
| Dell C4130 GPU Cluster | 2016 | 1× | 4× Tesla P100 GPUs |
| Power Mac G4 MDD | 2003 | **2.5×** | Dual G4 CPUs |
| Power Mac G5 Dual | 2004 | **2.5×** | Liquid-cooled |
| PowerBook G4 Collection | 2002 | **2.5×** | Three models |
| SPARCstation Fleet | 1993 | **2.5×** | NetBSD/sparc |
| 486/386 Laptop Collection | 1994 | **2.5×** | DOS + custom miner |
| Elyan Labs Rack Array | 2010 | 1× | 8-node dual-Xeon cluster |

### Interactive Features
- **Click any exhibit** → detailed specs + live miner data
- **Green glow** = miner actively mining RTC
- **Live data** pulled from `https://50.28.86.131/api/miners` every 30s
- **Antiquity bonus** shown per-machine (vintage hardware earns 2.5×)

## Architecture (Modular Files)

```
museum/
├── index.html          # Entry point (~90 lines, well under 400-line limit)
├── serve.py            # Python static server for local dev
├── README.md
├── css/
│   └── style.css       # All styles
└── js/
    ├── exhibits.js     # Exhibit definitions (positions, specs, lore)
    ├── scene.js        # Three.js scene builder (floor, walls, meshes, lighting)
    ├── controls.js     # WASD + mouse look + mobile touch controls
    ├── miners-api.js   # Live data fetcher (50.28.86.131/api/miners)
    ├── panel.js        # Info panel UI (specs + miner stats)
    ├── minimap.js      # 2D minimap renderer
    └── app.js          # Main wiring / init / event handlers
```

## Deployment

**Static hosting (Netlify, Vercel, GitHub Pages, etc.):**
Just serve the `museum/` directory — all assets are CDN-loaded.

**Nginx:**
```nginx
server {
    listen 80;
    root /path/to/museum;
    index index.html;
    location / { try_files $uri $uri/ =404; }
}
```

**Python (local):**
```bash
cd museum && python3 serve.py
```

## Technology Stack
- **Three.js r134** via CDN (no build step required)
- Vanilla JS ES5/ES6 — no bundler, no npm
- Pure CSS — no framework
- Python 3 static server for local dev

---

*Built for RustChain Bounty #65 by LaphoqueRC*
*Wallet: RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff*
