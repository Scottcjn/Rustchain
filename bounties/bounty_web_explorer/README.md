# Bounty: RustChain Web Explorer – Keeper Faucet Edition

> **Bounty ID**: `bounty_web_explorer`  
> **Status**: ✅ Implemented  
> **Reward**: 1000 RUST  
> **Author**: OpenClaw  
> **Created**: 2026-03-23

A fully-featured web-based blockchain explorer for RustChain with a retro DOS/fossil-punk aesthetic, including Keeper faucet claiming functionality.

## 🎯 Features

### Required
- ✅ **Block Explorer**: Display blocks, validator info, and chain statistics
- ✅ **Real-time Updates**: Connects to RustChain node RPC for live data
- ✅ **NFT Badge Unlocks**: Display unlocked legacy hardware badges
- ✅ **Faucet Interface**: Claim rewards with `proof_of_antiquity.json` upload
- ✅ **Retro Aesthetic**: Authentic DOS/CRT pixel styling with amber monochrome theme

### Optional
- ✅ **Mobile Friendly**: Responsive design works on all screen sizes

## 🖼️ Screenshot

**Theme**: Amber CRT DOS  
- 80×25 text mode inspired layout
- Scanline CRT effect
- Blinking cursor animation
- Retro command-prompt aesthetic

## 🚀 Quick Start

### Option 1: Static HTML (No Server Required)

Open `src/explorer.html` directly in your browser. Works with any static web host.

```bash
# Copy to your web server
cp src/* /var/www/html/explorer/
```

### Option 2: Local Development with Python

```bash
cd src
python3 -m http.server 8080
# Open http://localhost:8080/explorer.html
```

### Option 3: Docker Compose

```bash
cd examples
docker-compose up -d
# Open http://localhost:8080/
```

## 📁 Directory Structure

```
bounty_web_explorer/
├── README.md                 # This file
├── src/
│   ├── explorer.html         # Main explorer HTML
│   ├── explorer.js           # JavaScript logic
│   ├── style.css             # Retro DOS/CRT styling
│   └── favicon.ico           # Retro favicon
├── examples/
│   └── docker-compose.yml    # Container deployment
├── docs/
│   ├── IMPLEMENTATION.md     # Architecture details
│   └── API_INTEGRATION.md    # RPC endpoint documentation
└── evidence/
    └── proof.json            # Submission proof
```

## 🎨 Theme Options

The explorer comes with three built-in themes:
1. **Amber CRT** (default) - Warm amber on black, classic terminal
2. **Green CRT** - Traditional monochrome terminal green
3. **DOS White** - Bright white on blue, PC DOS style

Switch themes using the **Theme** menu in the UI.

## 🔧 Configuration

Edit `CONFIG` in `explorer.js`:

```javascript
const CONFIG = {
  NODE_URL: 'https://rustchain.org',  // RustChain node endpoint
  SCRAPE_INTERVAL: 30000,             // Auto-refresh interval (ms)
  DEFAULT_THEME: 'amber',             // 'amber' | 'green' | 'dos'
};
```

## 📋 Features Breakdown

### Block Explorer
- Latest blocks with height, timestamp, and miner info
- Block detail view with transactions
- Chain statistics (difficulty, supply, active miners)

### Validator Information
- Keeper hardware details
- Antiquity multiplier score
- Rewards earned
- Last active timestamp

### NFT Badge Explorer
- Browse unlocked legacy hardware badges
- Display badge metadata and images
- Filter by hardware era/architecture

### Faucet Claim
- Upload `proof_of_antiquity.json`
- Automatic validation
- Claim RTC rewards to your wallet
- Status feedback

## 🧪 Testing

Open `explorer.html` in browser and verify:
1. Connection to node succeeds
2. Blocks load correctly
3. Theme switching works
4. File upload accepts valid proof files

## API Integration

The explorer connects to these RustChain endpoints:
- `GET /health` - Node health and version
- `GET /blocks` - Latest blocks
- `GET /block/{height}` - Block detail
- `GET /epoch` - Current epoch info
- `GET /api/miners` - Active miners list
- `POST /faucet/claim` - Faucet claim submission

## 🔒 Security

- CORS-friendly: Works with any node that allows CORS
- No client-side storage of sensitive data
- Proof files are validated client-side before submission
- CSP compatible for secure deployment

## 📄 License

MIT - Same as RustChain
