# RustChain TUI Dashboard

> **Deprecated feature:** the price lookup in this tool queried third-party market-data services. It is deprecated: do not use, extend, or advertise it — RustChain official materials do not reference market prices. The code is left in place pending removal. The wRTC bridge is disabled; RTC is earned for contributions and spent on services in the ecosystem, with no off-ramp. See [Earn & Spend RTC](https://github.com/Scottcjn/rustchain-bounties/blob/main/docs/EARN_AND_SPEND.md).

Real-time terminal dashboard for monitoring the RustChain network.

![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)

## Features

- **Network Health** — colored status indicator, version, uptime, DB status, and API latency
- **Epoch / Slot** — current epoch number, slot counter with progress bar, epoch pot, enrolled miners, and total supply
- **Active Miners** — table showing miner IDs, hardware type, architecture, and antiquity multiplier
- **Recent Blocks** — live feed of new blocks as they appear on-chain
- **Auto-refresh** — configurable interval (default 5 seconds)

## Installation

```bash
cd tools/tui-dashboard
pip install -r requirements.txt
```

## Usage

```bash
# Connect to the default public node (https://rustchain.org)
python dashboard.py

# Connect to a local or custom node
python dashboard.py -u http://localhost:5000

# Change the refresh interval to 10 seconds
python dashboard.py --interval 10
```

Press **Ctrl+C** to exit.

## Layout

```
┌──────────────────────────────────────────────────────────────┐
│  RustChain Dashboard  |  Node: ...  |  Updated: ...         │
├──────────────────┬──────────────────┬────────────────────────┤
│  Network Health  │  Epoch / Slot    │  (price: deprecated)   │
│  ● HEALTHY       │  Epoch: 95       │                        │
│  Version: 2.2.1  │  Slot: 12345     │                        │
│  Uptime: 2d 5h   │  ████░░░░ 28.6%  │                        │
├──────────────────┴──────────────────┴────────────────────────┤
│  Active Miners (15 total)           │  Recent Blocks         │
│  ID         HW       Arch   Mult   │  Height  Hash    Seen  │
│  miner-01   x86_64   amd64  1.50x  │  67890   a1b2... 12:30 │
│  miner-02   arm64    rpi4   2.00x  │  67889   c3d4... 12:25 │
└─────────────────────────────────────┴────────────────────────┘
```

## API Endpoints Used

| Endpoint         | Data                              |
|------------------|-----------------------------------|
| `/health`        | Node health, version, uptime      |
| `/epoch`         | Epoch number, slot, pot, supply   |
| `/api/miners`    | Active miner list                 |
| `/headers/tip`   | Latest block height and hash      |

## Requirements

- Python 3.8+
- `rich` — terminal UI rendering
- `requests` — listed for compatibility; the dashboard uses `urllib` from stdlib
