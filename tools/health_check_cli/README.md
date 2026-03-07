# RustChain Health Check CLI

A CLI tool that queries all 3 RustChain attestation nodes and displays their health status in a formatted table.

## Bounty

This tool was created for [Bounty #1111](https://github.com/Scottcjn/rustchain-bounties/issues/1111) - 8 RTC Reward.

## Features

- Queries all 3 attestation nodes:
  - 50.28.86.131:443
  - 50.28.86.153:443
  - 76.8.228.245:8099
- Displays: version, uptime, db_rw status, tip age
- Formatted table output
- JSON output option
- Exit code reflects node availability

## Usage

```bash
# Default table output
python3 tools/health_check_cli/rustchain_health_check.py

# JSON output
python3 tools/health_check_cli/rustchain_health_check.py --json

# Verbose mode (show errors)
python3 tools/health_check_cli/rustchain_health_check.py -v
```

## Example Output

```
RustChain Node Health Check
Timestamp: 2026-03-07T23:00:00Z

Host                 Port   Status   Version     Uptime          DB RW    Tip Age
-----------------------------------------------------------------------------------------
50.28.86.131         443    ONLINE   1.2.3       5d 12h 30m      true     30s
50.28.86.153         443    ONLINE   1.2.3       3d 8h 15m       true     45s
76.8.228.245         8099   ONLINE   1.2.3       2d 4h 50m       true     1m

Summary: 3/3 nodes online
```

## Requirements

- Python 3.7+
- Stdlib only (no external dependencies)

## Exit Codes

- `0` - All nodes online
- `1` - One or more nodes offline
