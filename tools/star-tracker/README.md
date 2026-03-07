# GitHub Star Growth Tracker

A dashboard that tracks Scottcjn repo stars over time.

## Features

- Store daily star snapshots in SQLite
- Render growth chart (HTML dashboard)
- Track all repositories
- Show total stars, daily delta, top growers

## Installation

```bash
pip install requests
```

## Usage

```bash
# Fetch latest star data
python main.py --fetch

# Generate HTML dashboard
python main.py --dashboard

# Both at once
python main.py --fetch --dashboard

# Watch mode (fetch and display every hour)
python main.py --fetch --watch
```

## Output

- SQLite database: `~/.github_star_tracker.db`
- HTML dashboard: `star_dashboard.html`

## Reward

10 RTC (upon completion of bounty #1110)

## Screenshot

![Dashboard](screenshot.png)
