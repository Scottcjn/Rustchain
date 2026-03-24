# RustChain API Load Test Suite

Benchmarks for the [RustChain](https://github.com/Scottcjn/Rustchain) API.
Covers `/health`, `/epoch`, and `/wallet/balance` — read-only endpoints only.

> **Safety note:** `/wallet/transfer/signed` is intentionally excluded from active tests
> to prevent accidental on-chain transactions. It is included as a commented mock for
> reference only.

---

## Endpoints Under Test

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/epoch` | Current epoch / slot / height |
| GET | `/wallet/balance?miner_id=X` | Balance lookup |
| POST | `/wallet/transfer/signed` | **MOCK ONLY — not executed** |

**Base URL:** `https://50.28.86.131`
**TLS:** Self-signed cert — use `--insecure` / `verify=False`

---

## Option A: Locust (Python)

### Prerequisites

```bash
pip install -r requirements.txt
```

### Run headless (recommended for CI / servers)

```bash
locust -f locustfile.py \
  --headless \
  -u 5 \          # 5 concurrent users
  -r 1 \          # spawn 1 user/second
  -t 30s \        # run for 30 seconds
  --host https://50.28.86.131 \
  --csv results/benchmark \
  --html results/report.html
```

### Run with web UI (local dev)

```bash
locust -f locustfile.py --host https://50.28.86.131
# Open http://localhost:8089 in your browser
```

### CSV output files

| File | Contents |
|------|----------|
| `results/benchmark_stats.csv` | Per-endpoint request counts, latencies, failure rates |
| `results/benchmark_failures.csv` | Any failed requests with details |
| `results/benchmark_stats_history.csv` | Time-series latency data |
| `results/report.html` | Full HTML report with graphs |

### User classes

- **`RustChainUser`** — Balanced read scenario (health 3x, epoch 2x, balance 1x)
- **`RustChainReadHeavyUser`** — Explorer / dashboard pattern (health 5x, epoch 3x, balance 2x)

To run only one class:

```bash
locust -f locustfile.py --class-picker --host https://50.28.86.131
```

---

## Option B: k6 (JavaScript)

### Prerequisites

```bash
# macOS
brew install k6

# Linux
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6
```

### Run

```bash
k6 run --insecure-skip-tls-verify k6_script.js
```

### Output with JSON results

```bash
k6 run --insecure-skip-tls-verify --out json=results/k6_results.json k6_script.js
```

### Load profile

| Stage | Duration | Users |
|-------|----------|-------|
| Ramp up | 10s | 0 → 3 |
| Steady | 20s | 5 |
| Ramp down | 10s | 5 → 0 |

---

## Interpreting Results

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| p50 latency | < 200ms | 200–500ms | > 500ms |
| p95 latency | < 1000ms | 1–2s | > 2s |
| Error rate | < 1% | 1–5% | > 5% |
| RPS (5 users) | > 10 | 5–10 | < 5 |

**Common issues:**

- `ConnectionError` / `SSLError` — Use `--insecure` flag or `verify=False`
- High p95 on `/wallet/balance` — Balance lookups hit the ledger, expect higher latency
- 404 on balance — Miner ID may not exist; this is treated as success in the suite

---

## Recommended Test Levels

| Scenario | Users | Duration | Purpose |
|----------|-------|----------|---------|
| Smoke | 1 | 10s | Sanity check |
| Light | 5 | 30s | Normal benchmarking |
| Moderate | 10 | 60s | Stress testing |

> **Do not exceed 10 concurrent users.** This is a live network node.
