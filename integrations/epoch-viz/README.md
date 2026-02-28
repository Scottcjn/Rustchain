# RustChain Epoch Settlement Visualizer

An animated web visualization showing how RustChain epoch settlements work.

## Bounty

Built for [Bounty #43: Epoch Settlement Visualizer](https://github.com/Scottcjn/rustchain-bounties/issues/43) (50 RTC)

## Features

- ✅ Epoch countdown timer
- ✅ Weight distribution chart (Modern vs Vintage)
- ✅ Settlement animation (click to simulate)
- ✅ Active miners list with calculated rewards
- ✅ Real-time data from RustChain node API
- ✅ Responsive design
- ✅ Dark mode

## Quick Start

### Option 1: With Proxy Server (Recommended)

The proxy server handles CORS and SSL issues:

```bash
python3 server.py
```

Then open http://localhost:8888

### Option 2: Static File

Open `index.html` directly in a browser. Note: API calls may fail due to CORS. For production, serve via the proxy or host on a domain that allows CORS.

## Screenshots

The visualizer shows:
1. **Stats Grid** - Current epoch, pot size, miner count, countdown
2. **Weight Distribution** - Bar chart comparing Modern vs Vintage multipliers
3. **Settlement Animation** - Click to see reward particles distribute
4. **Active Miners List** - Each miner with architecture color and calculated reward

## Architecture Colors

| Color | Architecture | Multiplier |
|-------|-------------|------------|
| 🟠 Orange | PowerPC/G5 | 2.0x+ |
| 🟢 Green | Modern x86/ARM | 1.0x |
| 🔵 Blue | Apple Silicon | 1.0x |
| ⚫ Gray | Unknown | 1.0x |

## API Endpoints Used

- `GET /epoch` - Epoch info (number, pot, slot)
- `GET /api/miners` - List of enrolled miners with multipliers

## Files

- `index.html` - Single-page visualization (no build required)
- `server.py` - Proxy server for CORS/SSL handling

## Technical Details

- Pure HTML5/CSS3/JavaScript (no frameworks)
- Canvas-free design using CSS animations
- Responsive grid layout
- Auto-refresh every 30 seconds

## Customization

Edit the constants in `index.html`:

```javascript
const BLOCKS_PER_EPOCH = 144;
const BLOCK_TIME_SECONDS = 600;
```

## License

MIT License

## Credits

- Built for [RustChain](https://github.com/Scottcjn/Rustchain)
- Bounty: [Issue #43](https://github.com/Scottcjn/rustchain-bounties/issues/43)
