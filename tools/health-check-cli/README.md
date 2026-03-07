# RustChain Health Check CLI

A CLI tool that queries all 3 RustChain attestation nodes and displays health status.

## Features

- Query multiple attestation nodes
- Display version, uptime, DB read/write status, and tip age
- Formatted table output
- JSON output option
- Continuous watch mode

## Installation

```bash
pip install requests
```

## Usage

```bash
# Basic health check
python main.py

# JSON output
python main.py --json

# Watch mode (continuous monitoring)
python main.py --watch

# Watch with custom interval
python main.py --watch --interval 5
```

## Nodes

- Node 1: 50.28.86.131:8099
- Node 2: 50.28.86.153:8099
- Node 3: 76.8.228.245:8099

## Reward

8 RTC (upon completion of bounty #1111)
