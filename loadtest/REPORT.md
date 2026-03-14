# RustChain API Load Test Report

**Issue:** [#1614 — Create Load Test Suite](https://github.com/Scottcjn/rustchain-bounties/issues/1614)
**API Base:** `https://50.28.86.131`
**Tool:** Locust 2.34.0
**Date:** 2026-03-14

---

## Test Configuration

| Parameter | Value |
|-----------|-------|
| Concurrent users | 5 |
| Spawn rate | 1 user/second |
| Duration | 30 seconds |
| User classes | `RustChainUser` + `RustChainReadHeavyUser` |
| TLS | Self-signed cert — `verify=False` |

---

## Results Summary

### Per-Endpoint Breakdown

| Endpoint | Requests | Failures | p50 (ms) | p95 (ms) | Avg (ms) | Min (ms) | Max (ms) | RPS |
|----------|----------|----------|----------|----------|----------|----------|----------|-----|
| GET /health | 14 | 0 | 5,800 | 7,200 | 5,718 | 2,986 | 7,248 | 0.48 |
| GET /epoch | 10 | 0 | 140 | 2,600 | 508 | 112 | 2,567 | 0.34 |
| GET /wallet/balance | 5 | 0 | 160 | 3,700 | 933 | 102 | 3,688 | 0.17 |
| **Aggregated** | **29** | **0** | **3,000** | **7,100** | **3,096** | **102** | **7,248** | **1.0** |

**Error rate: 0.00%**

---

## Analysis

### /health

The health endpoint showed unexpectedly high median latency (~5.8s). This is consistent
with the endpoint performing active checks (`db_rw`, `backup_age_hours`, `tip_age_slots`)
rather than a simple ping. Minimum response time of ~3s confirms this is server-side work,
not network latency.

- **Best-case latency:** ~3s (cold check + DB probe)
- **p95:** 7.2s — acceptable for a monitoring endpoint not in hot path
- **Recommendation:** Consider adding a lightweight `/ping` that returns immediately for
  high-frequency uptime monitors, while keeping `/health` for full diagnostics.

### /epoch

The epoch endpoint performed well, with a p50 of 140ms — indicating fast chain state reads
from an in-memory or cached structure. The wide p95 (2.6s) suggests occasional slow paths
(e.g., disk reads, lock contention during block production).

- **p50: 140ms** — fast under normal conditions
- **p95: 2.6s** — tail latency is elevated; investigate caching

### /wallet/balance

Balance lookups showed fast median response (160ms), consistent with indexed ledger reads.
The p95 spike to 3.7s on limited samples (5 requests) is likely noise from a single slow
query rather than a systemic issue.

- **p50: 160ms** — healthy
- **Recommendation:** Re-run with more sustained load (100+ requests) for stable percentiles

---

## Observations

1. **Zero failures** across all endpoints under 5 concurrent users — the API is stable.
2. `/health` has intentional latency from performing real DB and chain-state probes.
3. `/epoch` and `/wallet/balance` are fast in steady state; tail latency warrants caching review.
4. The API handles the tested concurrency level without errors or timeouts.

---

## Safety Notes

- `/wallet/transfer/signed` was **not tested** with live requests. It is provided as a
  commented mock in `locustfile.py` and `k6_script.js` for documentation purposes only.
- Load was kept gentle (5 users, 30s) to avoid disrupting the live network node.
- All requests used `verify=False` to handle the self-signed TLS certificate.

---

## Artifacts

| File | Description |
|------|-------------|
| `locustfile.py` | Locust test suite (two user classes) |
| `k6_script.js` | k6 alternative with staged load profile |
| `requirements.txt` | Python dependencies |
| `README.md` | Setup and usage guide |
| `results/report.html` | Full HTML report with graphs |
| `results/benchmark_stats.csv` | Per-endpoint statistics |
| `results/benchmark_stats_history.csv` | Time-series data |
| `results/benchmark_failures.csv` | Failure log (empty — 0 failures) |

---

## Reproducing

```bash
# Install dependencies
pip install -r loadtest/requirements.txt

# Run 30-second smoke test (5 users)
locust -f loadtest/locustfile.py \
  --headless -u 5 -r 1 -t 30s \
  --host https://50.28.86.131 \
  --csv loadtest/results/benchmark \
  --html loadtest/results/report.html

# Or with k6
k6 run --insecure-skip-tls-verify loadtest/k6_script.js
```
