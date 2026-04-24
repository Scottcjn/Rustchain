# ⛓ RustChain Fork Choice Graph Visualizer

**Bounty #2389** — A real-time fork choice analysis dashboard for RustChain.

## ✨ Features

| Feature | Description |
|---------|-------------|
| **🌲 Fork Tree** | Visual graph of fork choice decisions with canonical chain highlighting |
| **📊 Real-Time Metrics** | Live epoch, slot, height, fork count, validator activity |
| **📈 Historical Tracking** | Time-series chart of fork activity over time |
| **🔍 Fork Details Table** | Complete fork metadata: slot, weight, validators, status |
| **🔄 Auto-Refresh** | Data updates every 30 seconds |
| **📡 API Backend** | Python Flask API serving fork choice data |

## 🚀 Quick Start

### Option 1: Static HTML (No server needed)

Open `visualizations/fork_choice_graph.html` directly in a browser.
It connects to the RustChain node API and displays live data.
If the node is unreachable, demo data is shown automatically.

### Option 2: Full Stack (Python API + HTML)

```bash
# Install dependencies
pip install flask flask-cors requests

# Start the visualizer server
cd visualizations
python3 fork_choice_graph.py
```

Then open `http://localhost:8765` in your browser.

### CLI Options

```bash
# Export data as JSON
python3 fork_choice_graph.py --export

# Generate simulated fork data
python3 fork_choice_graph.py --simulate

# Use simulated mode (when node is offline)
SIMULATE=1 python3 fork_choice_graph.py
```

## 📡 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Node health status |
| `GET /api/epoch` | Current epoch/slot/height |
| `GET /api/forks` | Active fork list |
| `GET /api/history` | Historical fork data |
| `GET /api/dashboard` | All metrics aggregated |
| `GET /api/refresh` | Trigger data refresh |

## 🏗 Architecture

```
visualizations/
├── fork_choice_graph.html    # Frontend dashboard (self-contained)
├── fork_choice_graph.py      # Python API backend
├── fork_choice_history.json  # Persisted historical data
└── README.md                  # This file
```

## 🔗 Integration

The visualizer connects to the RustChain node at `https://50.28.86.131`.
It uses the standard API endpoints (`/health`, `/epoch`) to gather data
for fork choice analysis.

**Wallet for bounty:** `kuanglaodi2-sudo`

---

*Built for [Bounty #2389](https://github.com/Scottcjn/Rustchain/issues/2389)*
