# Bounty Contribution

This addresses issue #5: feat: RustChain Health Check CLI Tool (Bounty #1111)

## Description
## Summary

Implements RustChain Health Check CLI Tool for Bounty #1111 (8 RTC reward).

## Features

- Queries all 3 attestation nodes: 50.28.86.131, 50.28.86.153, 76.8.228.245:8099
- Displays: version, uptime, db_rw status, tip age
- Formatted table output
- Watch mode support for continuous monitoring (-w flag)
- JSON output option (-j flag)

## Usage

```bash
python tools/health-check-cli/main.py
python tools/health-check-cli/main.py --json
python tools/health-check-cli/main.py --watch --int

## Payment
0x4F666e7b4F63637223625FD4e9Ace6055fD6a847
