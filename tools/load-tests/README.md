# RustChain Load Test Suite

Benchmarks for the five core RustChain API endpoints using **Locust**, **k6**, and **Artillery**. Each tool targets the same surface area so results are directly comparable.

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Node health / version |
| `/epoch` | GET | Current epoch, slot, height |
| `/headers/tip` | GET | Chain tip header |
| `/api/miners` | GET | Active miner list |
| `/wallet/balance?miner_id=<id>` | GET | Wallet balance lookup |

---

## 1. Locust (Python)

### Install

```bash
pip install locust
```

### Run (headless with CSV + JSON output)

```bash
cd tools/load-tests
locust -f locustfile.py \
  --host https://50.28.86.131 \
  --users 50 --spawn-rate 5 --run-time 2m \
  --headless --csv results/locust
```

CSV files (`locust_stats.csv`, `locust_stats_history.csv`, `locust_failures.csv`) and a `locust_summary.json` are written to `results/`.

### Run (web UI with graphs)

```bash
locust -f locustfile.py --host https://50.28.86.131
# Open http://localhost:8089
```

The Locust web UI renders live charts for RPS, response times, and failure rate.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `RUSTCHAIN_MINER_ID` | `Ivan-houzhiwen` | miner_id for `/wallet/balance` |

---

## 2. k6 (Go)

### Install

See https://grafana.com/docs/k6/latest/set-up/install-k6/

### Run

```bash
cd tools/load-tests
k6 run k6-test.js
```

Three scenarios execute in sequence:

| Scenario | VUs | Duration | Purpose |
|---|---|---|---|
| smoke | 5 | 30 s | Sanity check |
| load | 0 -> 25 -> 0 | ~1 m 45 s | Normal traffic |
| stress | 0 -> 50 -> 0 | ~1 m 45 s | Peak traffic |

### HTML report with graphs

```bash
k6 run k6-test.js
# -> results/k6_report.html  (response-time distribution, RPS, pass/fail)
# -> results/k6_summary.json
```

Or use the built-in web dashboard:

```bash
K6_WEB_DASHBOARD=true k6 run k6-test.js
```

### Thresholds

- **p95 response time < 3 000 ms**
- **Error rate < 5 %**

k6 exits with code 99 if any threshold is breached.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `RUSTCHAIN_HOST` | `https://50.28.86.131` | Base URL |
| `RUSTCHAIN_MINER_ID` | `Ivan-houzhiwen` | miner_id for balance query |

---

## 3. Artillery (Node.js)

### Install

```bash
npm install -g artillery
```

### Run

```bash
cd tools/load-tests
artillery run artillery-test.yml
```

### Generate HTML report

```bash
artillery run --output results/artillery_report.json artillery-test.yml
artillery report results/artillery_report.json \
  --output results/artillery_report.html
```

The HTML report includes latency distribution graphs and throughput charts.

### Phases

| Phase | Duration | Arrival rate | Purpose |
|---|---|---|---|
| Warm-up | 20 s | 2 req/s | Baseline |
| Ramp-up | 30 s | 2 -> 20 req/s | Gradual increase |
| Sustained | 60 s | 20 req/s | Steady-state |
| Cool-down | 15 s | 20 -> 1 req/s | Drain |

---

## Interpreting results

### Key metrics to watch

| Metric | Healthy | Warning |
|---|---|---|
| p95 latency | < 500 ms | > 1 000 ms |
| p99 latency | < 1 500 ms | > 3 000 ms |
| Error rate | < 1 % | > 5 % |
| RPS (50 VUs) | > 30 | < 15 |

### Example output

Sample summaries are in `results/example_locust_summary.json` and `results/example_k6_summary.json`.

### Common failure modes

- **Connection refused / timeout** — Node is down or rate-limiting. Check firewall and node logs.
- **HTTP 429** — The node is throttling requests. Reduce VU count or add wait time.
- **SSL errors** — All scripts disable TLS verification for the self-signed cert. If you still see errors, ensure the `insecureSkipTLSVerify` / `verify=False` flags are active.
- **High p99 with low p50** — A few slow outliers. Usually GC pauses or DB lock contention on the node side.

---

## Output files

After a test run the `results/` directory will contain:

```
results/
  locust_stats.csv            # per-endpoint stats
  locust_stats_history.csv    # time-series data (graphable)
  locust_failures.csv         # failure details
  locust_summary.json         # aggregate JSON
  k6_report.html              # visual HTML report with graphs
  k6_summary.json             # full metric dump
  artillery_report.json       # raw Artillery output
  artillery_report.html       # visual HTML report
```
