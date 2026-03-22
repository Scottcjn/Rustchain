# Implementation Notes - RustChain Web Explorer

## Overview

Pure client-side HTML/CSS/JavaScript implementation that works entirely in the browser with CORS-enabled nodes. No backend required.

## Architecture

```
┌─────────────────────────────────────────────┐
│                  Browser                      │
│  ┌─────────────────────────────────────────┐│
│  │  explorer.html - Main markup             ││
│  │  style.css      - Retro CRT/DOS styling  ││
│  │  explorer.js    - API and rendering      ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
         │ fetch (CORS)
         ▼
    ┌───────────┐
    │ RustChain │
    │   Node    │
    └───────────┘
```

**Key Design Decisions:**
- 100% client-side: Deploy to any static host (GitHub Pages, S3, nginx)
- No build step required: Plain HTML/CSS/JS works everywhere
- Responsive: Works on mobile and desktop
- Retro aesthetic: Authentic CRT scanlines, 80x25 inspiration, terminal colors

## Features Implemented

### ✓ Required Features

| Feature | Status | Notes |
|---------|--------|-------|
| Display blocks | ✅ | Latest 20 blocks with click-to-view detail |
| Validator info | ✅ | Keeper hardware, architecture, multipliers |
| NFT badge unlocks | ✅ | Grid display with legacy hardware badges |
| Faucet interface | ✅ | File upload + paste JSON, claim submission |
| Retro/fossil-punk theme | ✅ | Three themes: Amber/Green/DOS with scanlines |
| Mobile friendly | ✅ | Responsive grid, adaptive layout |

### ✓ Additional Features

- Auto-refresh every 30 seconds
- Theme switching with persistent localStorage
- Status bar showing connection state
- Error handling for offline/unreachable nodes
- Block transaction listing

## Endpoints Used

The explorer integrates with these standard RustChain endpoints:

| Endpoint | Method | Purpose | Required |
|----------|--------|---------|----------|
| `/health` | GET | Node health and version | Yes |
| `/epoch` | GET | Current epoch stats | Yes |
| `/api/miners` | GET | Active miners list | Yes |
| `/blocks` | GET | Latest blocks | Optional (graceful fallback) |
| `/faucet/claim` | POST | Submit claim | Yes (for faucet) |

## Theme System

Three built-in themes:

1. **Amber CRT** (default) - Warm amber on black, classic terminal
2. **Green CRT** - Traditional monochrome terminal green
3. **DOS Blue/White** - Original IBM PC DOS color scheme

CSS variables handle theming, easy to add new themes.

## CRT Effect

- Fixed scanline pattern at 4px spacing
- Animated slow vertical scroll for authentic flicker
- Subtle glow effect via container box-shadow
- Doesn't interfere with interaction (pointer-events: none)

## Responsive Design Breakpoints

- `> 600px`: Full desktop layout
- `< 600px`: Single column, stacked menu, smaller fonts

## Deployment Options

### 1. Static File Hosting

Just copy `src/*` to your web server directory. Works with:
- GitHub Pages
- Netlify
- S3 + CloudFront
- Any basic nginx/apache

### 2. Docker Compose

See `examples/docker-compose.yml` for a ready-to-go nginx container.

### 3. Local Testing

```bash
cd src
python3 -m http.server 8080
# Open http://localhost:8080/explorer.html
```

## Configuration

Edit the `CONFIG` object at the top of `explorer.js`:

```javascript
const CONFIG = {
  NODE_URL: 'https://rustchain.org',  // Your node URL
  SCRAPE_INTERVAL: 30000,             // Auto-refresh in ms
  DEFAULT_THEME: 'amber',             // Default theme
};
```

## Security Considerations

1. **CORS**: Node must allow CORS from the explorer origin
2. **No Storage**: No sensitive data stored locally
3. **Proof Validation**: Basic JSON validation client-side, node does full validation
4. **HTTPS**: Works with HTTPS nodes, mixed content blocked by browsers

## Performance

- Lightweight: Total filesize ~20KB (uncompressed)
- No frameworks: Plain JS for minimal overhead
- Caching: Browser caching of static assets
- Auto-refresh: Uses `setInterval` with reasonable 30s default

## Testing Notes

Tested with:
- Chrome/Firefox/Safari desktop
- Chrome Android
- Safari iOS
- Responsive down to 320px width

## Future Improvements

- Search by miner ID/wallet
- Pagination for older blocks
- Historical charts for statistics
- QR code display for wallet address
- Offline mode with cached data
