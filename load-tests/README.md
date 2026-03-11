# RustChain API Load Test Suite

> **Issue #1614**: Add load test suite for RustChain API with configurable targets/rates

This directory contains comprehensive load testing tools for the RustChain API, supporting both **k6** (JavaScript) and **Locust** (Python) frameworks.

## Quick Start

### Using k6 (Recommended)

```bash
# Install k6
brew install k6  # macOS
sudo apt-get install k6  # Linux

# Run a quick smoke test
./run-load-test.sh k6 smoke

# Run standard load test
./run-load-test.sh k6 load

# Run stress test
./run-load-test.sh k6 stress
```

### Using Locust

```bash
# Install dependencies
pip install -r locust-requirements.txt

# Run with web UI (open http://localhost:8089)
./run-load-test.sh locust web

# Run headless
./run-load-test.sh locust headless
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `TARGET_URL` | `https://rustchain.org` | API base URL |
| `MINER_ID` | `scott` | Miner wallet ID for testing |
| `DURATION` | `5m` | Test duration (e.g., `30s`, `5m`, `1h`) |
| `USERS` | `10` | Concurrent users (Locust) |
| `SPAWN_RATE` | `2` | User spawn rate per second (Locust) |
| `OUTPUT_DIR` | `./results` | Results output directory |

### k6 Configuration

k6 tests can be configured via:

1. **Environment variables** (runtime):
   ```bash
   k6 run -e TARGET_URL=http://localhost:8099 -e MINER_ID=test k6-load-test.js
   ```

2. **Config file** (`k6-config.json`):
   ```bash
   k6 run --config k6-config.json k6-load-test.js
   ```

3. **Scenario presets** (`k6-scenarios.json`):
   ```bash
   k6 run --config k6-scenarios.json --scenario api-baseline k6-load-test.js
   ```

## Test Scenarios

### k6 Scenarios

| Scenario | Description | Duration | VUs | Use Case |
|----------|-------------|----------|-----|----------|
| `smoke` | Basic health check | 30s | 1 | Quick validation |
| `load` | Standard load test | 5m | 0→10→0 | Regular testing |
| `stress` | Peak load test | 6m | 0→100→0 | Capacity planning |
| `quick-smoke` | CI/CD smoke test | 30s | 2 | Pipeline integration |
| `api-baseline` | Performance baseline | 5m | 10 | Benchmarking |
| `soak-test` | Endurance test | 30m | 25 | Memory leak detection |
| `spike-test` | Sudden load spike | 5m | 5→75→5 | Resilience testing |

### Locust User Classes

| User Class | Description | Wait Time | Use Case |
|------------|-------------|-----------|----------|
| `RustChainAPIUser` | Standard API user | 1-3s | Normal load testing |
| `HeavyLoadUser` | Aggressive user | 0.1-0.5s | Stress testing |
| `WriteLoadUser` | Write operations | 2-5s | Mutation testing |

## Endpoints Tested

| Endpoint | Method | Description | Weight |
|----------|--------|-------------|--------|
| `/health` | GET | Node health status | High |
| `/ready` | GET | Kubernetes readiness probe | Medium |
| `/epoch` | GET | Current epoch/slot info | High |
| `/api/miners` | GET | List active miners | High |
| `/api/nodes` | GET | List connected nodes | Medium |
| `/wallet/balance` | GET | Wallet balance lookup | Medium |
| `/governance/proposals` | GET | Governance proposals | Low |
| `/lottery/eligibility` | GET | Miner eligibility check | Low |

## Output & Reporting

### k6 Output

k6 generates:
- **Console output**: Real-time metrics during test
- **JSON results**: `load-test-results.json` with summary metrics
- **Detailed logs**: When using `--out json=<file>`

Example metrics:
```json
{
  "test_info": {
    "target_url": "https://rustchain.org",
    "timestamp": "2026-03-11T12:00:00Z"
  },
  "metrics": {
    "total_requests": 1500,
    "request_rate": 5.0,
    "error_rate": 0.02,
    "avg_latency_ms": 245.5,
    "p95_latency_ms": 890.2,
    "p99_latency_ms": 1250.8
  },
  "checks": {
    "health_pass_rate": 0.99,
    "epoch_pass_rate": 0.98,
    "miners_pass_rate": 0.97,
    "balance_pass_rate": 0.95
  }
}
```

### Locust Output

Locust generates:
- **HTML report**: Interactive report with charts
- **JSON results**: Raw data for further analysis
- **Web UI**: Real-time monitoring (when running with `--web`)

## Performance Thresholds

Default thresholds (configurable in `k6-config.json`):

| Metric | Threshold | Description |
|--------|-----------|-------------|
| `p50 latency` | < 500ms | 50th percentile response time |
| `p95 latency` | < 2000ms | 95th percentile response time |
| `p99 latency` | < 5000ms | 99th percentile response time |
| `error rate` | < 5% | HTTP error rate |
| `health check` | > 95% | Health endpoint pass rate |
| `balance check` | > 90% | Balance endpoint pass rate |

## CI/CD Integration

### GitHub Actions Example

```yaml
name: API Load Test

on: [push, pull_request]

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install k6
        run: |
          curl https://github.com/grafana/k6/releases/download/v0.47.0/k6-v0.47.0-linux-amd64.tar.gz | tar xz
          sudo cp k6-v0.47.0-linux-amd64/k6 /usr/local/bin/
      
      - name: Run smoke test
        run: |
          cd load-tests
          k6 run --config k6-scenarios.json --scenario quick-smoke k6-load-test.js
        env:
          TARGET_URL: ${{ secrets.RUSTCHAIN_TEST_URL }}
```

### GitLab CI Example

```yaml
load_test:
  stage: test
  image: grafana/k6:latest
  script:
    - cd load-tests
    - k6 run --config k6-scenarios.json --scenario quick-smoke k6-load-test.js
  variables:
    TARGET_URL: https://rustchain.org
  artifacts:
    reports:
      load_test: load-tests/load-test-results.json
```

## Advanced Usage

### Custom k6 Scenarios

Create custom scenarios in a new config file:

```json
{
  "scenarios": {
    "custom-test": {
      "executor": "ramping-vus",
      "startVUs": 5,
      "stages": [
        { "duration": "2m", "target": 30 },
        { "duration": "5m", "target": 30 },
        { "duration": "1m", "target": 0 }
      ]
    }
  }
}
```

Run with:
```bash
k6 run --config custom-config.json --scenario custom-test k6-load-test.js
```

### Distributed Load Testing (Locust)

For high-load tests, run Locust in distributed mode:

```bash
# Master node
locust -f locust-load-test.py --master --expect-workers 4

# Worker nodes (on separate machines)
locust -f locust-load-test.py --worker --master-host=<master-ip>
```

### Custom Metrics

Add custom metrics in k6:

```javascript
import { Trend } from 'k6/metrics';

const customMetric = new Trend('custom_metric');

export default function() {
  const response = http.get('https://rustchain.org/health');
  customMetric.add(response.timings.duration);
}
```

## Troubleshooting

### k6 Issues

**Problem**: `k6: command not found`
```bash
# Install k6
brew install k6  # macOS
sudo apt-get install k6  # Debian/Ubuntu
winget install k6  # Windows
```

**Problem**: TLS certificate errors
```bash
# k6 handles self-signed certs with insecureSkipTLSVerify in config
# Or use environment variable:
export K6_INSECURE_SKIP_TLS_VERIFY=true
```

### Locust Issues

**Problem**: `ModuleNotFoundError: No module named 'locust'`
```bash
pip install -r locust-requirements.txt
```

**Problem**: Connection refused
```bash
# Verify TARGET_URL is accessible
curl -sk https://rustchain.org/health

# Check firewall/proxy settings
```

## Best Practices

1. **Start small**: Begin with smoke tests before running load/stress tests
2. **Monitor resources**: Watch server CPU, memory, and network during tests
3. **Use realistic data**: Configure `MINER_ID` with actual wallet addresses
4. **Run regularly**: Schedule load tests in CI/CD pipelines
5. **Compare baselines**: Track performance metrics over time
6. **Test in staging**: Never run stress tests directly on production

## File Structure

```
load-tests/
├── README.md                    # This file
├── .env.example                 # Environment configuration template
├── k6-load-test.js              # Main k6 test script
├── k6-config.json               # Default k6 configuration
├── k6-scenarios.json            # Pre-configured k6 scenarios
├── locust-load-test.py          # Locust test script
├── locust-requirements.txt      # Python dependencies
├── run-load-test.sh             # Unified test runner
└── results/                     # Test output directory (gitignored)
    ├── k6-*.json
    ├── locust-*.html
    └── locust-*.json
```

## References

- [k6 Documentation](https://k6.io/docs/)
- [Locust Documentation](https://docs.locust.io/)
- [RustChain API Reference](../docs/api-reference.md)
- [RustChain Postman Collection](../docs/postman/RustChain.postman_collection.json)

## License

Same as RustChain project license.
