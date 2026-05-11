# RustChain Miner Dashboard

A self-contained, mobile-responsive dashboard for RustChain miners to track their balance, rewards, and participation history.

## 🎯 Features

- **Balance Tracking**: Real-time RTC balance display
- **Miner Information**: Hardware details, antiquity multiplier, attestation history
- **Network Status**: Current epoch, slot, and network statistics
- **Reward History**: Transaction history with status tracking
- **Activity Monitoring**: Recent attestation activity across the network
- **Shareable URLs**: Pass miner ID via URL parameter (`?miner_id=your_wallet`)
- **Mobile Responsive**: Works on desktop and mobile devices

## 🚀 Usage

### Option 1: Open Locally

1. Download `index.html`
2. Open in any modern web browser
3. Enter your Miner ID and click "Load Dashboard"

### Option 2: Use Shareable URL

Add your miner ID as a URL parameter:
```
https://your-hosting.com/index.html?miner_id=scott
```

The dashboard will automatically load data for that miner.

### Option 3: Self-Host

Deploy to any static hosting service:
- GitHub Pages
- Netlify
- Vercel
- Your own web server

```bash
# Using Python's built-in HTTP server
cd miner-dashboard
python3 -m http.server 8080

# Or using Node.js http-server
npx http-server -p 8080
```

Then visit: `http://localhost:8080?miner_id=your_wallet`

## 📊 API Endpoints Used

This dashboard consumes the following RustChain public APIs:

| Endpoint | Purpose |
|----------|---------|
| `GET /wallet/balance?miner_id={id}` | Fetch miner's RTC balance |
| `GET /wallet/history?miner_id={id}&limit=20` | Fetch transaction history |
| `GET /api/miners` | List all active miners (for miner info) |
| `GET /epoch` | Current epoch and network stats |

All API calls are made directly from the browser (client-side only).

## 🎨 Design

- **Dark Theme**: Matches RustChain's visual style
- **Clean UI**: Minimal, focused on data clarity
- **Responsive**: Mobile-first design
- **No Dependencies**: Pure HTML/CSS/JS, no frameworks required

## 📱 Screenshots

Open the live dashboard preview in [index.html](./index.html).

## 🔧 Customization

### Colors

Edit CSS variables in the `<style>` section:

```css
:root {
    --bg-primary: #0d1117;      /* Main background */
    --bg-secondary: #161b22;    /* Header background */
    --bg-card: #21262d;         /* Card background */
    --text-primary: #f0f6fc;    /* Primary text */
    --text-secondary: #8b949e;  /* Secondary text */
    --accent: #58a6ff;          /* Accent color (blue) */
    --success: #3fb950;         /* Success color (green) */
    --warning: #d29922;         /* Warning color (yellow) */
}
```

### API Base URL

If running against a different RustChain node:

```javascript
const API_BASE = 'https://rustchain.org'; // Change to your node URL
```

## ✅ Acceptance Criteria Met

- [x] Miner ID can be entered or shared via URL parameter
- [x] Current balance is displayed
- [x] Recent reward/epoch history is displayed (transaction history)
- [x] Recent attestation/participation activity is displayed (miner list)
- [x] Page works against the live RustChain API
- [x] PR includes setup/usage notes (this README)
- [x] Mobile-responsive design implemented

## 🧪 Testing

Test with known miner IDs:

```bash
# Test with 'scott' wallet
curl -sk "https://rustchain.org/wallet/balance?miner_id=scott"

# Test epoch endpoint
curl -sk "https://rustchain.org/epoch"

# Test miners list
curl -sk "https://rustchain.org/api/miners"
```

## 📦 File Structure

```
miner-dashboard/
├── index.html          # Main dashboard (self-contained)
└── README.md           # This file
```

## 🎯 Bonus Features Implemented

- ✅ **Shareable URL**: Miner ID via URL parameter
- ✅ **Mobile Responsive**: Works on all screen sizes
- ✅ **Real-time Loading**: Parallel API calls for fast loading
- ✅ **Error Handling**: User-friendly error messages
- ✅ **Status Badges**: Visual indicators for transaction status
- ✅ **Auto-load**: Loads automatically from URL parameter

## 🚀 Future Enhancements (Optional)

- [ ] Chart.js integration for balance history visualization
- [ ] Auto-refresh every 30 seconds
- [ ] Export data as CSV/JSON
- [ ] Multi-miner comparison view
- [ ] Dark/light theme toggle

## 📝 License

MIT License - Feel free to use, modify, and distribute.

---

**Developer:** xiaoma  
**RTC Wallet:** `xiaoma-miner`  
**PR Submission:** [Link to PR]
