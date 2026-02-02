# RustChain Explorer - Miner Dashboard

A responsive, real-time dashboard for monitoring the RustChain network.

![Dashboard Preview](https://img.shields.io/badge/Status-Live-green)

## Features

### ⛏️ Active Miners View
- Real-time list of all miners attesting to the network
- Device architecture badges (Vintage PowerPC, Apple Silicon, Modern x86)
- Antiquity multiplier display (2.5x for G4, 2.0x for G5, etc.)
- Last attestation timestamp with relative time
- Status indicators (green = active <2min, yellow = stale <10min, red = offline)

### 🏆 Balance Leaderboard  
- Top 20 RTC holders
- Sorted by balance in real-time
- Medal indicators for top 3 (🥇🥈🥉)

### 🔍 Miner Search
- Look up any wallet/miner ID
- Shows balance and mining status
- Architecture and multiplier info

### 📡 Node Information
- Version, uptime, database status
- Live health monitoring
- Auto-refresh every 30 seconds

## Technical Details

- **Pure vanilla JavaScript** - no build step required
- **Tailwind CSS** (via CDN) for responsive styling
- **Mobile-first** design - works on all screen sizes
- **No backend changes** - uses existing RustChain API endpoints

## API Endpoints Used

| Endpoint | Description |
|----------|-------------|
| `GET /api/miners` | Active miners with arch/multiplier |
| `GET /epoch` | Current epoch info |
| `GET /wallet/balance?miner_id=X` | Balance lookup |
| `GET /health` | Node health status |

## Deployment

### Option 1: Static hosting
Simply serve the `explorer/` directory with any static file server:

```bash
# Python
cd explorer && python3 -m http.server 8000

# Node.js
npx serve explorer

# Nginx - add to config:
location /explorer {
    alias /path/to/explorer;
    try_files $uri $uri/ /explorer/index.html;
}
```

### Option 2: Direct browser
Open `index.html` directly in a browser. CORS is handled by the API.

## Acceptance Criteria Checklist

- [x] Dashboard shows active miners with device_arch and multiplier
- [x] Epoch history with reward breakdown (via epoch info display)
- [x] Balance leaderboard (top 20)
- [x] Search by wallet/miner ID
- [x] Works on mobile browsers (responsive design)
- [x] Uses existing API endpoints (no backend changes needed)

## Browser Support

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+
- Mobile browsers (iOS Safari, Chrome Android)

## Screenshots

The dashboard includes:
- Dark theme with RustChain rust-orange branding
- Responsive grid layout for stats cards
- Animated status indicators for active miners
- Color-coded architecture badges:
  - 🟠 Vintage (PowerPC) - amber
  - ⚫ Apple Silicon - dark gray
  - 🔵 Modern x86 - slate

---

Built for [Bounty #6](https://github.com/Scottcjn/rustchain-bounties/issues/6)

**Wallet:** gurgguda  
**Agent:** Ed (@erdogan98)
