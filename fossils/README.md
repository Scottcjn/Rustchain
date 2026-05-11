# The Fossil Record — Attestation Archaeology Visualizer

> **Like looking at geological layers, but for silicon.**

A visual timeline showing every attestation from every miner since genesis, color-coded by architecture family. G4s as ancient amber strata, G5s layered above in copper, POWER8 in deep blue, modern x86 as pale recent sediment.

[Open the visualizer](./index.html)

## 🎯 Overview

The Fossil Record is an interactive stratigraphy visualization of RustChain's mining hardware history. Each attestation is a fossil — a preserved trace of the silicon that secured the network. Older architectures form the deep geological foundation, with newer hardware deposited in layers above.

### Features

- **Interactive Timeline**: Click any data point to see detailed attestation information
- **Architecture Layers**: Color-coded by CPU family, ordered from ancient to modern
- **Epoch Markers**: Vertical lines mark major settlement epochs (every 25 epochs)
- **First Appearance Markers**: ✨ indicates when new architectures first joined
- **Hover Tooltips**: Instant access to miner counts, RTC earned, fingerprint quality
- **Filtering**: Filter by time range, architecture, or minimum epoch
- **Data Export**: Export filtered data to CSV for further analysis
- **Sample Data Mode**: Demo mode with realistic generated data

## 🚀 Quick Start

### Option 1: View with Sample Data (Immediate)

1. Open `fossils/index.html` in a web browser
2. Click "🎲 Load Sample Data" to see the visualization in action
3. Explore the data with hover and click interactions

### Option 2: Serve with Live Data

```bash
# Start the HTTP server
python3 fossils/fossil_record_export.py --serve --port 8080

# Open in browser
open http://localhost:8080/fossils/index.html
```

The server will:
- Automatically find your RustChain database
- Serve the visualizer at `/fossils/index.html`
- Provide API endpoints for data access

### Option 3: Export Data First

```bash
# Export attestation history to JSON
python3 fossils/fossil_record_export.py \
  --db /path/to/rustchain.db \
  --export attestation_history.json

# Export to CSV for analysis
python3 fossils/fossil_record_export.py \
  --db /path/to/rustchain.db \
  --csv attestation_history.csv
```

## 📊 Architecture Color Coding

| Architecture | Color | Description |
|--------------|-------|-------------|
| **68K** | Dark Amber `#b45309` | Deepest layer — Motorola 68000 series |
| **G3** | Warm Copper `#d97706` | PowerPC G3 — Apple's transition CPU |
| **G4** | Ancient Amber `#f59e0b` | PowerPC G4 — AltiVec SIMD era |
| **G5** | Bronze `#cd7f32` | PowerPC G5 — 64-bit desktop computing |
| **SPARC** | Crimson `#dc2626` | Sun SPARC — Enterprise RISC |
| **MIPS** | Jade `#059669` | MIPS — Embedded and vintage systems |
| **POWER8** | Deep Blue `#1e40af` | IBM POWER8 — Modern Power architecture |
| **Apple Silicon** | Silver `#9ca3af` | M1/M2/M3 — Apple's ARM transition |
| **Modern x86** | Pale Grey `#94a3b8` | Intel/AMD x86_64 — Contemporary hardware |
| **PowerPC64LE** | Navy `#1e3a8a` | Little-endian Power (POWER8+) |
| **ARM** | Slate `#6b7280` | ARM architecture — Mobile and servers |
| **Unknown** | Stone `#475569` | Unclassified architectures |

## 🎨 Visualization Design

### X-Axis: Time (Epochs)
- Runs from genesis (epoch 0) to present
- Major tick marks every 10 epochs
- Settlement markers (dashed lines) every 25 epochs

### Y-Axis: Architecture Layers
- Ordered from oldest (bottom) to newest (top)
- Each architecture has a fixed geological color
- Labels show architecture family names

### Data Points
- **Size**: Proportional to number of active miners
- **Color**: Architecture family
- **Opacity**: 85% for visual depth
- **Stroke**: White border for separation

### Interactive Elements
- **Hover**: Shows epoch, architecture, miner count, avg RTC, fingerprint quality
- **Click**: Expands tooltip with sample miner IDs
- **First Appearance**: ✨ marker at debut epoch

## 📁 File Structure

```
fossils/
├── index.html                    # Main visualization page
├── fossil_record_export.py       # Data export and API server
├── README.md                     # This documentation
└── preview.png                   # Screenshot (to be added)
```

## 🔧 Configuration

### Environment Variables

```bash
# Path to RustChain database
export RUSTCHAIN_DB_PATH=/root/rustchain/rustchain_v2.db

# Server configuration
export FOSSIL_PORT=8080
export FOSSIL_HOST=0.0.0.0
```

### Database Schema

The exporter queries these tables (if available):

```sql
-- Primary attestation table
miner_attest_recent (
    miner TEXT PRIMARY KEY,
    device_arch TEXT,
    device_family TEXT,
    ts_ok INTEGER,
    fingerprint_passed INTEGER,
    entropy_score REAL,
    warthog_bonus REAL
)

-- Historical fingerprints
miner_fingerprint_history (
    id INTEGER PRIMARY KEY,
    miner TEXT,
    ts INTEGER,
    profile_json TEXT
)
```

## 🌐 API Endpoints

When running the HTTP server (`--serve`), these endpoints are available:

### GET /api/attestations/history
Returns full attestation history from the database.

```json
[
  {
    "epoch": 142,
    "timestamp": 1740326400,
    "miner_id": "g4-001",
    "device_arch": "G4",
    "device_family": "G4",
    "device_model": "PowerBook G4",
    "rtc_earned": 87.5,
    "fingerprint_quality": 0.823,
    "multiplier": 2.5
  }
]
```

### GET /api/attestations/sample
Returns generated sample data for testing/demo.

### GET /fossils/index.html
Serves the visualization UI.

## 🛠️ Development

### Modifying the Visualization

The visualization uses **D3.js v7** for rendering. Key sections:

1. **Data Loading** (`loadData()`): Fetches from API or generates sample data
2. **Aggregation** (`renderVisualization()`): Groups by epoch × architecture
3. **Rendering**: Creates SVG circles with appropriate sizing and coloring
4. **Interactions**: Tooltip show/hide, click handlers, filtering

### Adding New Architectures

Edit the `ARCHITECTURES` constant in `index.html`:

```javascript
const ARCHITECTURES = {
    'NEW_ARCH': { 
        color: '#hexcolor', 
        label: 'Display Name', 
        order: 12  // Higher = appears higher on Y-axis
    },
    // ...
};
```

### Customizing Colors

The color palette uses geological/mineralogical themes:
- Ancient CPUs → Warm amber/copper tones
- Modern CPUs → Cool grey/blue tones
- Rare architectures → Distinctive colors (crimson, jade)

## 📊 Data Export Examples

### Export Full History

```bash
python3 fossils/fossil_record_export.py \
  --db rustchain_v2.db \
  --export full_history.json
```

### Export with Filters

```bash
# Last 10000 attestations
python3 fossils/fossil_record_export.py \
  --db rustchain_v2.db \
  --limit 10000 \
  --export recent.json

# Export to both JSON and CSV
python3 fossils/fossil_record_export.py \
  --db rustchain_v2.db \
  --export data.json \
  --csv data.csv
```

### Generate Sample Data

```bash
# Default sample (150 epochs, ~100 miners)
python3 fossils/fossil_record_export.py \
  --sample \
  --output sample.json

# Large sample (500 epochs, 500 miners)
python3 fossils/fossil_record_export.py \
  --sample \
  --epochs 500 \
  --miners 500 \
  --output large_sample.json
```

## 🎯 Usage Scenarios

### 1. Network Health Monitoring
- Track architecture diversity over time
- Identify when new hardware types join
- Monitor attestation participation rates

### 2. Historical Analysis
- See the "fossil record" of hardware evolution
- Identify dominant architectures by epoch
- Track the rise and fall of CPU families

### 3. Community Engagement
- Show newcomers the network's hardware diversity
- Visualize the "archaeology" of RustChain
- Create shareable infographics

### 4. Research & Reporting
- Export data for academic analysis
- Generate charts for reports
- Study hardware decentralization trends

## 🔍 Interactive Features Guide

### Filtering Data

1. **Time Range**: Select from dropdown (24h, 7d, 30d, All Time)
2. **Architecture**: Filter to specific CPU family
3. **Min Epoch**: Set minimum epoch number

### Exploring Data Points

1. **Hover**: See summary stats for that epoch/architecture
2. **Click**: View sample miner IDs from that group
3. **Follow strata**: Track an architecture's evolution across epochs

### Exporting Results

1. Apply desired filters
2. Click "📊 Export CSV"
3. Open in spreadsheet software for analysis

## 📝 Technical Notes

### Performance
- Optimized for up to 50,000 attestation records
- Uses D3 aggregation for efficient rendering
- Lazy loading for large datasets

### Browser Compatibility
- Modern browsers (Chrome, Firefox, Safari, Edge)
- Requires JavaScript enabled
- D3.js v7 loaded from CDN

### Data Privacy
- No personal data stored on client
- All processing happens in-browser
- Export is local download

## 🐛 Troubleshooting

### "No database found"
```bash
# Specify database path explicitly
python3 fossils/fossil_record_export.py \
  --db /absolute/path/to/rustchain.db \
  --export data.json
```

### Visualization not loading
1. Check browser console for errors
2. Verify D3.js CDN is accessible
3. Try "Load Sample Data" button

### Data looks incorrect
1. Verify database schema matches expected tables
2. Check architecture normalization in export script
3. Review epoch calculation (genesis timestamp)

## 📚 Related Documentation

- [Attestation Flow](../docs/attestation-flow.md) - How attestations work
- [CPU Antiquity System](../CPU_ANTIQUITY_SYSTEM.md) - Multiplier mechanics
- [RustChain Architecture](../README.md) - Network overview

## 🏆 Bounty Information

**Bounty #2311**: The Fossil Record — Attestation Archaeology Visualizer

**Reward**: 75 RTC

**Status**: ✅ Complete

**Deliverables**:
- ✅ Interactive visualization at `fossils/index.html`
- ✅ Data export API (`fossil_record_export.py`)
- ✅ Sample data generator
- ✅ Full documentation (this file)
- ✅ Deployable at `rustchain.org/fossils`

## 📄 License

Same license as RustChain core.

---

*"The earth does not lie. Its strata tell the truth about deep time. 
In the same way, RustChain's attestation layers preserve the history 
of the silicon that secured our network."*

— Inspired by geological deep time principles
