# RustChain Benchmarking Suite

Performance benchmarking tools for RustChain node infrastructure.

## What it measures

| Category | Metrics |
|---|---|
| **API Endpoint Latency** | p50, p95, p99 latency for all public endpoints (health, chain state, wallet, governance, beacon, attestation, P2P) |
| **Block Verification Throughput** | blake2b-256 block header hashing, prev-hash linkage verification (ops/sec) |
| **Attestation Processing** | HMAC signature verification, hardware hash validation, epoch eligibility checks (ops/sec) |
| **Database Query Performance** | Balance lookups, epoch attestation queries, miner listings, withdrawal history, block-by-height, recent transactions (queries/sec) |
| **Concurrent Connections** | RPS and latency under concurrent load at 1, 5, 10, 25, 50 connections |

## Requirements

```
pip install requests
```

No other dependencies required. The suite uses only stdlib + `requests`.

## Quick start

```bash
# Run against a local node
python benchmark.py --host http://localhost:5000

# Customize iterations and output directory
python benchmark.py --host http://localhost:5000 -n 200 -o results/

# Custom concurrency levels
python benchmark.py --host http://localhost:5000 --concurrency 1,10,50,100

# Point at an existing node database for realistic DB benchmarks
python benchmark.py --host http://localhost:5000 --db /path/to/rustchain_v2.db
```

## Comparison mode

Compare performance before and after a change:

```bash
# 1. Run baseline
python benchmark.py --host http://localhost:5000 -o results/
# -> results/bench_20250601_120000.json

# 2. Apply changes, restart node

# 3. Run again
python benchmark.py --host http://localhost:5000 -o results/
# -> results/bench_20250601_130000.json

# 4. Compare
python benchmark.py --compare results/bench_20250601_120000.json results/bench_20250601_130000.json -o results/
# -> results/comparison.json + results/comparison.html
```

The comparison report highlights regressions (>2% slower) and improvements (>2% faster) with color-coded badges.

## Output

Each run produces two files:

- **`bench_<timestamp>.json`** -- Machine-readable results with all raw metrics
- **`bench_<timestamp>.html`** -- Visual report with Chart.js charts covering latency distributions, throughput bars, concurrency curves, and database QPS

## CLI reference

```
usage: benchmark.py [-h] [--host HOST] [--iterations N] [--warmup WARMUP]
                    [--output DIR] [--db PATH] [--admin-key KEY]
                    [--concurrency LEVELS] [--compare BEFORE AFTER] [-v]

Options:
  --host            Node base URL (default: http://localhost:5000)
  -n, --iterations  Requests per endpoint (default: 100)
  --warmup          Warmup requests before measurement (default: 5)
  -o, --output      Output directory (default: current dir)
  --db              Path to node SQLite DB for realistic query benchmarks
  --admin-key       Admin API key (or set RC_ADMIN_KEY env var)
  --concurrency     Comma-separated concurrency levels (default: 1,5,10,25,50)
  --compare         Compare two JSON result files
  -v, --verbose     Verbose output
```

## Interpreting results

- **p50** -- Median latency. Most requests complete at or below this.
- **p95** -- 95th percentile. Only 5% of requests are slower.
- **p99** -- 99th percentile. Tail latency -- important for user-facing endpoints.
- **RPS** -- Requests per second under concurrent load.
- **QPS** -- Database queries per second (SQLite, single-connection).

A healthy RustChain node should show sub-50ms p95 on `/health` and `/epoch` endpoints with stable RPS scaling up to at least 25 concurrent connections.
