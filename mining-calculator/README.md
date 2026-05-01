# RustChain Mining Calculator

A simple web-based calculator to estimate your RustChain (RTC) mining rewards based on hardware antiquity.

## Features

- 🎯 **Hardware Selection**: Choose from various hardware types with different antiquity multipliers
- 📊 **Live Network Data**: Auto-fetches current miner data from the RustChain network
- 💰 **Earnings Estimates**: Shows RTC and USD earnings for:
  - Per epoch (10 minutes)
  - Per hour
  - Per day
  - Per week
  - Per month
- 📈 **Sensitivity Table**: Shows how earnings change as network size grows
- 🎨 **Modern UI**: Clean, responsive design with dark theme

## How It Works

RustChain uses a Proof-of-Antiquity consensus mechanism that rewards older hardware with higher multipliers:

| Hardware | Multiplier | Examples |
|----------|------------|----------|
| PowerPC G4 | 2.5x | PowerBook G4, Power Mac G4 |
| PowerPC G5 | 2.0x | Power Mac G5, Xserve G5 |
| IBM POWER8 | 2.0x | IBM POWER8 S824 |
| PowerPC G3 | 1.8x | iBook G3, Power Mac G3 |
| Pentium 4 | 1.5x | Intel Pentium 4 systems |
| Core 2 Duo | 1.3x | Intel Core 2 Duo systems |
| Apple Silicon | 1.15x | Mac Mini M2, MacBook M1 |
| Modern x86 | 1.0x | Any modern PC/laptop |
| VM/Emulated | ~0x | Virtual machines (discouraged) |

### Reward Formula

```
your_share = (your_multiplier / sum_of_all_multipliers) × 1.5 RTC per epoch
```

Each 10-minute epoch distributes 1.5 RTC across all active miners, weighted by hardware antiquity.

## Usage

### Option 1: Open Locally

Simply open `index.html` in your web browser:

```bash
# On macOS
open index.html

# On Windows
start index.html

# On Linux
xdg-open index.html
```

### Option 2: Host Locally

```bash
# Using Python 3
python3 -m http.server 8000

# Then visit http://localhost:8000
```

### Option 3: Deploy

Deploy to any static hosting service:
- GitHub Pages
- Netlify
- Vercel
- Cloudflare Pages

## API Integration

The calculator attempts to fetch live network data from:
- `https://rustchain.org/api/miners` - Active miners list

If the API is unavailable, it falls back to default network composition.

## Customization

You can modify the following constants in the JavaScript section:

```javascript
const RTC_PER_EPOCH = 1.5;        // RTC distributed per epoch
const EPOCHS_PER_HOUR = 6;        // 6 epochs per hour (10 min each)
const EPOCHS_PER_DAY = 144;       // 144 epochs per day
const EPOCHS_PER_WEEK = 1008;     // 1008 epochs per week
const EPOCHS_PER_MONTH = 4320;    // 4320 epochs per month
const USD_RATE = 0.10;            // $0.10 per RTC reference rate
```

## Files

- `index.html` - Single-file calculator (HTML + CSS + JavaScript)
- `README.md` - This file

## License

MIT License - Feel free to use, modify, and distribute.

## Contributing

Issues and PRs welcome! This calculator helps new miners understand potential rewards and drives adoption of the RustChain network.

## Support

For questions about RustChain mining:
- GitHub: https://github.com/Scottcjn/Rustchain
- Explorer: https://rustchain.org/explorer/
- API Docs: https://rustchain.org/epoch

---

**Built for the RustChain community** ⛏️
