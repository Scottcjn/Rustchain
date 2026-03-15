# RustChain Log Analyzer

Command-line tool for parsing and analyzing RustChain node logs. Provides error frequency analysis, mining success/failure rates, attestation tracking, peer connection statistics, performance metrics over time, and automatic anomaly detection.

## Requirements

- Python 3.8+
- No external dependencies (stdlib only)

## Usage

### Analyze

Print a summary of log file contents:

```bash
python analyzer.py analyze /path/to/node.log
```

Output as JSON (suitable for piping into other tools):

```bash
python analyzer.py analyze /path/to/node.log --json
```

Analyze only the last N lines:

```bash
python analyzer.py analyze /path/to/node.log --tail 5000
```

Exit code `2` is returned when critical anomalies are detected, making it usable in CI/monitoring scripts.

### Report

Generate a self-contained HTML report:

```bash
python analyzer.py report /path/to/node.log -o report.html
```

The report includes:

- KPI cards (lines processed, blocks mined, errors, anomalies)
- Mining success/failure bar chart
- Attestation pass/fail rates
- Peer connection net change
- Payout/settlement status
- Log level distribution table
- Top errors by frequency
- Subsystem tag breakdown
- Anomaly alerts with severity

### Watch

Tail a live log file and print real-time anomaly alerts:

```bash
python analyzer.py watch /path/to/node.log --interval 2
```

Prints periodic summaries of new events and raises alerts when thresholds are breached. Press `Ctrl+C` to stop.

## What It Detects

| Category | Metrics |
|---|---|
| **Errors** | Frequency by message, severity distribution, error bursts per minute |
| **Mining** | Blocks mined vs failures, success rate, per-minute throughput |
| **Attestation** | Pass/fail counts, pass rate |
| **Peers** | Connects, disconnects, net peer change, churn ratio |
| **Consensus** | BFT event count (pre-prepare, prepare, commit, view-change) |
| **Payouts** | Successful vs failed withdrawals and settlements |

## Anomaly Thresholds

| Anomaly | Default Threshold |
|---|---|
| High error rate | > 5% of lines are ERROR/CRITICAL/FATAL |
| Mining failure rate | > 30% of mining attempts fail |
| Attestation failure rate | > 20% of attestations fail |
| Peer churn ratio | Disconnects exceed 3x connects |
| Error burst | > 10 errors in a single minute |
| Peer loss without new connections | Any disconnects with zero connects |

## Log Format Support

The analyzer recognizes these log formats used across RustChain node components:

- Python `logging` output: `2025-01-15 12:34:56,789 [BFT] message`
- Bracket-tagged prints: `[P2P] Added peer: http://...`
- Standard severity keywords: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

## Examples

```bash
# Quick health check
python analyzer.py analyze node.log --tail 1000

# Generate report for ops team
python analyzer.py report node.log -o /var/www/html/rustchain-health.html

# Monitor in production
python analyzer.py watch /var/log/rustchain/node.log --interval 5
```
