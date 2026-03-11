# RustChain Node Health Monitor CLI

A command-line tool to monitor RustChain node health with comprehensive checks for health status, epoch information, and peer/API reachability.

## Features

- **Health Checks**: Verify node health status, uptime, database status, and version
- **Epoch Information**: Display current epoch, slot, enrolled miners, and reward pot
- **API Reachability**: Test connectivity to multiple API endpoints with latency measurement
- **Multiple Output Formats**: Human-readable text or machine-parseable JSON
- **Proper Exit Codes**: Suitable for scripting and CI/CD integration
- **Configurable**: Custom node URLs, timeouts, and endpoints

## Installation

No installation required. The tool is a standalone Python script with no external dependencies (uses only Python standard library).

### Requirements

- Python 3.7+
- Network access to RustChain node

## Quick Start

```bash
# Check default node (rustchain.org)
python node_health.py

# Check local node
python node_health.py -n http://localhost:8099

# Output as JSON
python node_health.py --json

# Verbose output
python node_health.py -v

# Quiet mode (exit code only)
python node_health.py -q && echo "OK" || echo "FAILED"
```

## Usage

```
usage: node-health [-h] [-n NODE] [-t TIMEOUT] [-e ENDPOINTS [ENDPOINTS ...]]
                   [--json] [-v] [-q]

RustChain Node Health Monitor - Check node health, epoch info, and API reachability

options:
  -h, --help            show this help message and exit
  -n, --node NODE       Node URL to check (default: https://rustchain.org)
  -t, --timeout TIMEOUT
                        Request timeout in seconds (default: 10)
  -e, --endpoints ENDPOINTS [ENDPOINTS ...]
                        Custom endpoints to check reachability
  --json                Output in JSON format
  -v, --verbose         Verbose output with additional details
  -q, --quiet           Quiet mode - only output exit code
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All checks passed |
| 1 | Health check failed (node unhealthy or unreachable) |
| 2 | Epoch check failed (epoch data unavailable) |
| 3 | API reachability check failed |
| 4 | Multiple checks failed |

## Examples

### Basic Health Check

```bash
$ python node_health.py
============================================================
RustChain Node Health Check
============================================================
Node URL: https://rustchain.org
Timestamp: 2024-01-15T10:30:00Z

[✓] Health Status
    OK: True
    Version: 2.2.1
    Uptime: 1d 5h 30m
    DB Read/Write: OK

[✓] Epoch Information
    Epoch: 1234
    Slot: 567
    Epoch Pot: 1.5 RTC
    Enrolled Miners: 42
    Total Supply: 1000000 RTC

[✓] API Reachability
    ✓ /health: 45ms (HTTP 200)
    ✓ /epoch: 52ms (HTTP 200)
    ✓ /api/miners: 78ms (HTTP 200)
    ✓ /ready: 38ms (HTTP 200)

------------------------------------------------------------
STATUS: ALL CHECKS PASSED
EXIT CODE: 0
============================================================
```

### JSON Output for Automation

```bash
$ python node_health.py --json
{
  "node_url": "https://rustchain.org",
  "timestamp": "2024-01-15T10:30:00Z",
  "health": {
    "ok": true,
    "version": "2.2.1",
    "uptime_s": 106200,
    "db_rw": true,
    "backup_age_hours": 1.5,
    "tip_age_slots": 2,
    "error": null
  },
  "epoch": {
    "epoch": 1234,
    "slot": 567,
    "epoch_pot": 1.5,
    "enrolled_miners": 42,
    "blocks_per_epoch": 600,
    "total_supply_rtc": 1000000.0,
    "error": null
  },
  "reachability": [
    {
      "endpoint": "/health",
      "reachable": true,
      "latency_ms": 45.2,
      "status_code": 200,
      "error": null
    }
  ],
  "overall_ok": true,
  "exit_code": 0
}
```

### Check Specific Endpoints

```bash
# Check only health and epoch endpoints
python node_health.py -e /health /epoch

# Check custom API endpoints
python node_health.py -e /health /epoch /api/stats /ready
```

### Verbose Output

```bash
$ python node_health.py -v
============================================================
RustChain Node Health Check
============================================================
Node URL: https://rustchain.org
Timestamp: 2024-01-15T10:30:00Z

[✓] Health Status
    OK: True
    Version: 2.2.1
    Uptime: 1d 5h 30m
    DB Read/Write: OK
    Backup Age: 1.5 hours
    Tip Age: 2 slots

[✓] Epoch Information
    Epoch: 1234
    Slot: 567
    Epoch Pot: 1.5 RTC
    Enrolled Miners: 42
    Total Supply: 1000000 RTC

[✓] API Reachability
    ✓ /health: 45ms (HTTP 200)
    ✓ /epoch: 52ms (HTTP 200)
    ✓ /api/miners: 78ms (HTTP 200)
    ✓ /ready: 38ms (HTTP 200)

------------------------------------------------------------
STATUS: ALL CHECKS PASSED
EXIT CODE: 0
============================================================
```

### Scripting Integration

```bash
#!/bin/bash
# Monitor script with alerting

NODE_URL="https://rustchain.org"

python node_health.py -n "$NODE_URL" -q
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "Node health check failed with exit code $EXIT_CODE"
    # Send alert (email, Slack, PagerDuty, etc.)
    # send_alert "RustChain node $NODE_URL health check failed"
    exit 1
fi

echo "Node health check passed"
exit 0
```

### Cron Job Monitoring

```bash
# Add to crontab for hourly checks
0 * * * * /usr/bin/python3 /path/to/node_health.py -n https://rustchain.org -q || /path/to/alert_script.sh
```

### Docker Health Check

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python /app/node_health.py -n http://localhost:8099 -q || exit 1
```

## Output Fields

### Health Status

| Field | Description |
|-------|-------------|
| `ok` | Overall health status (true/false) |
| `version` | Node software version |
| `uptime_s` | Node uptime in seconds |
| `db_rw` | Database read/write status |
| `backup_age_hours` | Age of last backup in hours |
| `tip_age_slots` | Age of chain tip in slots |

### Epoch Information

| Field | Description |
|-------|-------------|
| `epoch` | Current epoch number |
| `slot` | Current slot within epoch |
| `epoch_pot` | Reward pot size for current epoch (RTC) |
| `enrolled_miners` | Number of enrolled miners |
| `blocks_per_epoch` | Total blocks per epoch |
| `total_supply_rtc` | Total RTC supply |

### Reachability Status

| Field | Description |
|-------|-------------|
| `endpoint` | API endpoint path |
| `reachable` | Whether endpoint is reachable |
| `latency_ms` | Response latency in milliseconds |
| `status_code` | HTTP status code |
| `error` | Error message if unreachable |

## Troubleshooting

### Connection Timeout

```
Error: Connection timeout
```

**Solution**: Increase timeout with `-t` flag or check network connectivity.

```bash
python node_health.py -t 30  # 30 second timeout
```

### Node Unreachable

```
Error: Connection refused
```

**Solution**: Verify node is running and URL is correct.

```bash
# Test with curl first
curl -s https://rustchain.org/health

# Then check with node_health
python node_health.py -n https://rustchain.org
```

### JSON Parse Error

```
Error: JSON parse error: ...
```

**Solution**: Node may be returning HTML error page. Check if node is properly configured.

## API Endpoints

The tool checks these endpoints by default:

| Endpoint | Description |
|----------|-------------|
| `/health` | Node health status |
| `/epoch` | Current epoch information |
| `/api/miners` | List of enrolled miners |

Custom endpoints can be specified with `-e` flag.

## Related Tools

- **monitoring/rustchain-exporter.py**: Prometheus exporter for continuous monitoring
- **node/consensus_probe.py**: Cross-node consistency checker
- **sdk/python/rustchain_sdk.py**: Python SDK for RustChain API

## License

MIT - Same as RustChain

## Contributing

See main [CONTRIBUTING.md](../../CONTRIBUTING.md) for contribution guidelines.

## Testing

Run the test suite:

```bash
cd tools/node-health-cli
python -m pytest tests/test_node_health.py -v

# Or with unittest
python -m unittest tests/test_node_health.py -v
```
