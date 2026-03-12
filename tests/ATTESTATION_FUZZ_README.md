# Attestation Fuzz Harness + Crash Regression Corpus

**Issue:** [#475](https://github.com/Scottcjn/rustchain-bounties/issues/475)  
**Bounty:** Attestation fuzz harness + crash regression corpus  
**Status:** ✅ Implemented

## Overview

This implementation provides a comprehensive fuzz testing framework for the RustChain attestation endpoint (`POST /attest/submit`). It includes:

1. **Fuzz Runner** - Practical fuzz testing harness with multiple mutation strategies
2. **Corpus Management** - Save, load, replay, deduplicate, and minimize test corpora
3. **Regression Tests** - Pytest-based regression verification tied to real endpoints/validators
4. **CI Integration** - Exit codes and reporting for CI/CD pipelines

## Quick Start

### Run Fuzz Testing

```bash
# Basic fuzz run (1000 iterations)
python3 tests/fuzz_attestation_runner.py

# Run with more iterations
python3 tests/fuzz_attestation_runner.py --count 5000

# Target a specific URL
python3 tests/fuzz_attestation_runner.py --url http://localhost:5000

# Save interesting cases to corpus
python3 tests/fuzz_attestation_runner.py --save-corpus --verbose

# CI mode (exit 1 if any crash found)
python3 tests/fuzz_attestation_runner.py --ci
```

### Run Regression Tests

```bash
# Run all regression tests
pytest tests/test_attestation_regression.py -v

# Run specific test class
pytest tests/test_attestation_regression.py::TestValidateFingerprintData -v

# Run corpus replay tests only
pytest tests/test_attestation_regression.py::test_corpus_no_unhandled_exceptions -v

# Run crash regression tests (verifies fixes)
pytest tests/test_attestation_regression.py::test_crash_corpus_regression_fixed -v
```

### Corpus Management

```bash
# Replay saved corpus
python3 tests/fuzz_attestation_runner.py --replay

# Minimize corpus (remove redundant entries)
python3 tests/fuzz_attestation_runner.py --minimize --verbose

# View crash report
python3 tests/fuzz_attestation_runner.py --report

# View fuzz statistics
python3 tests/fuzz_attestation_runner.py --stats
```

## Components

### 1. Fuzz Runner (`tests/fuzz_attestation_runner.py`)

The main fuzz testing harness with the following features:

#### Mutation Strategies

| Strategy | Description |
|----------|-------------|
| `missing_field` | Removes required fields |
| `wrong_type` | Replaces values with wrong types |
| `unknown_field` | Injects unexpected fields |
| `nested_bomb` | Creates deeply nested structures (JSON bomb) |
| `array_overflow` | Makes arrays extremely large |
| `float_edge` | Uses edge-case float values (inf, nan, etc.) |
| `unicode_inject` | Injects unicode edge cases |
| `size_extremes` | Tests empty/huge strings |
| `sql_injection` | SQL injection attempts |
| `xss_attempt` | XSS injection attempts |

#### CLI Options

```
--count N          Number of fuzz iterations (default: 1000)
--ci               Exit non-zero if any crash found
--save-corpus      Save interesting payloads to corpus
--verbose          Print every result
--report           Show saved crash report
--stats            Show fuzz statistics
--replay           Replay saved corpus
--minimize         Minimize corpus size
--seed N           Random seed for reproducibility
--url URL          Override target URL
```

#### Output

```
🔥 RustChain Attestation Fuzz Runner
   Target: http://localhost:5000/attest/submit
   Iterations: 1000
   Save corpus: True
   Seed: 42

  ✓  [  100] missing_field        → HTTP 400 (12ms)
  ✨ [  234] wrong_type           → HTTP 400 (new coverage)
  💥 [  567] nested_bomb          → CRASH: HTTP 500 server error (105ms)

============================================================
  Fuzz Summary
============================================================
  Total iterations: 1000
  Crashes found: 3
  Interesting cases: 47
  Unique coverage: 52
  Duration: 45.2s
  Rate: 22.1 iter/s
```

### 2. Corpus Structure

```
tests/
├── attestation_corpus/          # Interesting test cases
│   ├── valid_baseline.json      # Valid baseline payload
│   ├── malformed_*.json         # Malformed payloads
│   ├── attack_*.json            # Attack vectors
│   └── edge_*.json              # Edge cases
├── attestation_crash_corpus/    # Crash-inducing payloads
│   └── *.json                   # Saved crash cases
├── fuzz_crashes.json            # Crash report
└── fuzz_stats.json              # Fuzz statistics
```

#### Corpus Entry Format

```json
{
  "iteration": 234,
  "mutator": "wrong_type",
  "payload": {...},
  "status_code": 400,
  "response_preview": "...",
  "elapsed_ms": 12.5,
  "is_crash": false,
  "crash_detail": "",
  "coverage_hash": "abc123...",
  "timestamp": "20260310_143022"
}
```

### 3. Regression Tests (`tests/test_attestation_regression.py`)

Pytest-based regression tests that verify:

1. **Corpus Replay** - All saved corpus entries don't cause crashes
2. **Crash Regression** - Previously fixed crashes stay fixed
3. **Validator Tests** - `validate_fingerprint_data` handles malformed inputs
4. **Mutation Tests** - Various mutation strategies don't cause 500 errors
5. **Security Tests** - SQL injection, XSS, path traversal handled
6. **Edge Cases** - Large payloads, nested structures, float edges
7. **Property-Based** - Random mutations don't cause crashes

#### Test Classes

- `TestValidateFingerprintData` - Validator unit tests
- `TestValidateAttestationPayloadShape` - Payload shape validation
- `TestMutationStrategies` - Mutation strategy tests
- `TestSecurityVectors` - Security-focused tests
- `TestEdgeCases` - Edge case tests
- `TestPropertyBased` - Property-based tests

## Integration

### CI/CD Pipeline

Add to your CI workflow:

```yaml
# .github/workflows/fuzz.yml
name: Fuzz Testing

on: [push, pull_request]

jobs:
  fuzz:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install flask pytest
      
      - name: Run fuzz tests (CI mode)
        run: python3 tests/fuzz_attestation_runner.py --ci --count 1000
      
      - name: Run regression tests
        run: pytest tests/test_attestation_regression.py -v
      
      - name: Upload crash report
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: fuzz-crash-report
          path: tests/fuzz_crashes.json
```

### Local Development

```bash
# Pre-commit hook: run quick fuzz test
#!/bin/bash
python3 tests/fuzz_attestation_runner.py --count 100 --ci || exit 1
pytest tests/test_attestation_regression.py -q
```

## Crash Analysis

When a crash is found:

1. **Immediate Output** - Crash details printed to console
2. **Crash Report** - Saved to `tests/fuzz_crashes.json`
3. **Crash Corpus** - Payload saved to `tests/attestation_crash_corpus/`
4. **Statistics** - Updated in `tests/fuzz_stats.json`

### Analyzing Crashes

```bash
# View crash report
python3 tests/fuzz_attestation_runner.py --report

# Replay specific crash
python3 tests/replay_attestation_corpus.py tests/attestation_crash_corpus/20260310_143022_nested_bomb_000567.json

# Run regression tests to verify fix
pytest tests/test_attestation_regression.py::test_crash_corpus_regression_fixed -v
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUSTCHAIN_URL` | `http://localhost:5000` | Target server URL |
| `ATTEST_FUZZ_CASES` | `250` | Default test cases for pytest |
| `ATTEST_FUZZ_SEED` | `None` | Random seed for reproducibility |

### Tuning

```bash
# Adjust timeout (in fuzz_attestation_runner.py)
TIMEOUT = 10  # seconds

# Adjust iteration count
python3 tests/fuzz_attestation_runner.py --count 10000

# Adjust delay between requests
time.sleep(0.01)  # 10ms delay
```

## Performance

Typical performance metrics:

- **Rate:** 20-50 iterations/second (local)
- **Rate:** 5-15 iterations/second (remote)
- **Coverage:** ~50-100 unique responses per 1000 iterations
- **Crash Detection:** < 1 second from occurrence

## Troubleshooting

### Connection Refused

```
Error: Connection refused
```

Ensure the target server is running:
```bash
python3 node/rustchain_v2_integrated_v2.2.1_rip200.py
```

### Test Failures

```
AssertionError: Got 500 error with payload
```

This indicates a regression - a previously fixed crash is back. Check:
1. The payload in the error message
2. Recent changes to `/attest/submit` handler
3. Error logs for stack trace

### Slow Performance

```
Rate: 2 iter/s
```

Possible causes:
- Network latency (use local server)
- Server overload (reduce concurrent load)
- Timeout issues (adjust TIMEOUT constant)

## Security Notes

⚠️ **Warning:** This fuzz harness generates adversarial payloads including:
- SQL injection attempts
- XSS injection attempts
- Path traversal attempts
- Unicode edge cases
- Extremely large payloads

**Only run against test/development servers. Never run against production.**

## Related Files

- `tests/fuzz_attestation_runner.py` - Main fuzz runner
- `tests/test_attestation_regression.py` - Regression tests
- `tests/replay_attestation_corpus.py` - Corpus replay utility
- `tests/attestation_corpus/` - Test corpus directory
- `testing/attest_fuzz.py` - Legacy fuzz harness (deprecated)

## License

Same as RustChain project license.

## Contributing

To add new mutation strategies:

1. Add mutation function to `MUTATORS` list in `fuzz_attestation_runner.py`
2. Add corresponding test to `test_attestation_regression.py`
3. Add corpus entry if it produces interesting coverage
4. Update this documentation

## Version History

- **v1.0** (2026-03-10) - Initial implementation for issue #475
  - Fuzz runner with 15 mutation strategies
  - Corpus management (save/load/replay/minimize)
  - Regression test suite with 50+ tests
  - CI/CD integration
