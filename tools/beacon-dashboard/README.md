# Beacon Dashboard v1.1 — Live Transport Traffic Monitor

A polished terminal UI (TUI) for monitoring Beacon transport traffic in real-time.

## Features

- **Transport Health Panel** — Live status of all transports (Discord, Telegram, IRC, WebSocket) with uptime and latency
- **Per-Transport Counters** — Message counts, envelope kinds breakdown, throughput rates
- **Top Agent Stats** — Most active agents ranked by envelope volume
- **Filter/Search** — Real-time filtering by agent ID, envelope kind, or transport
- **CSV/JSON Export** — Snapshot current view to file
- **Sound Alerts** — Terminal bell on `mayday` envelopes and high-value tips (>50 RTC)
- **Auto-Refresh** — Configurable refresh interval (default 2s)

## Usage

```bash
# Launch dashboard (connects to local node DB)
python tools/beacon-dashboard/beacon_dashboard.py

# Or with beacon CLI alias
python tools/beacon-dashboard/beacon_dashboard.py dashboard

# Custom DB path
python tools/beacon-dashboard/beacon_dashboard.py --db /path/to/rustchain_v2.db

# Custom refresh interval (seconds)
python tools/beacon-dashboard/beacon_dashboard.py --refresh 5

# Disable sound alerts
python tools/beacon-dashboard/beacon_dashboard.py --no-sound
```

## Keyboard Controls

| Key | Action |
|-----|--------|
| `/` | Enter filter/search mode |
| `Esc` | Clear filter / exit search |
| `e` | Export current view (CSV) |
| `j` | Export current view (JSON) |
| `s` | Toggle sound alerts |
| `t` | Cycle through transport tabs |
| `r` | Force refresh |
| `q` | Quit |
| `↑/↓` | Scroll envelope list |

## Filter Syntax

- `kind:mayday` — Filter by envelope kind
- `agent:bcn_abc123` — Filter by agent ID
- `transport:discord` — Filter by transport
- Free text — Fuzzy match across all fields

## Export

Exports are written to the current directory:
- `beacon_snapshot_YYYYMMDD_HHMMSS.csv`
- `beacon_snapshot_YYYYMMDD_HHMMSS.json`

## Architecture

```
beacon_dashboard.py      — Main TUI (curses-based)
dashboard_helpers.py     — Data parsing, aggregation, export logic
test_dashboard.py        — Unit tests for helpers and parser
```

## Dependencies

- Python 3.8+ (stdlib only — `curses`, `sqlite3`, `csv`, `json`)
- No pip install required

## Bounty

Closes https://github.com/Scottcjn/rustchain-bounties/issues/321
