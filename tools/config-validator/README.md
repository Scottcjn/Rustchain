# RustChain Configuration Validator

Pre-flight configuration checker for RustChain nodes. Catches misconfigurations before they cause runtime failures.

## What it checks

| Category | Details |
|---|---|
| **Environment variables** | Required (`RUSTCHAIN_HOME`, `RUSTCHAIN_DB`) and optional vars are present and well-formed |
| **Port ranges** | Configured ports are valid (1-65535), not privileged without root, and not already bound |
| **Database connectivity** | SQLite database exists, passes `PRAGMA integrity_check`, and contains expected tables |
| **Wallet files** | `WALLET_NAME` is configured, wallet JSON files exist in standard locations and parse correctly |
| **SSL certificates** | When `ENABLE_SSL=true`, cert and key files exist, load correctly, and are not expired |
| **Network connectivity** | TCP reachability to known RustChain endpoints and DNS resolution |
| **Directory permissions** | `RUSTCHAIN_HOME` and `DOWNLOAD_DIR` exist and are writable |
| **Hardware recommendations** | Suggests Docker resource limits based on detected CPU cores and RAM |

## Usage

```bash
# Basic validation (reads .env automatically)
python tools/config-validator/validate.py

# Point to a specific .env file
python tools/config-validator/validate.py --env-file /path/to/.env

# JSON output for CI pipelines
python tools/config-validator/validate.py --json

# Auto-create missing directories
python tools/config-validator/validate.py --fix
```

## Output

```
========================================================================
  RustChain Node Configuration Validator
========================================================================

  [PASS]  RUSTCHAIN_HOME is set
  [PASS]  RUSTCHAIN_DB is set
  [PASS]  RUSTCHAIN_DASHBOARD_PORT=8099 is valid
  [WARN]  WALLET_NAME is not configured or uses the placeholder value
  [SKIP]  SSL is disabled — skipping certificate checks
  [PASS]  Endpoint rustchain.org:443 is reachable

------------------------------------------------------------------------
  Result: WARN  |  Passed: 8  Warnings: 2  Failures: 0  Skipped: 3
------------------------------------------------------------------------

  Recommendations:
    - Detected 4 CPU core(s), 16.0 GB RAM
    - Recommended Docker limits: RUSTCHAIN_NODE_MEMORY=2g, RUSTCHAIN_NODE_CPUS=4
    - SSL is disabled. For production deployments, enable SSL.
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All checks passed (warnings are acceptable) |
| `1` | One or more checks failed |

## CI integration

Add to a GitHub Actions workflow:

```yaml
- name: Validate node config
  run: python tools/config-validator/validate.py --json
  env:
    RUSTCHAIN_HOME: /rustchain
    RUSTCHAIN_DB: /rustchain/data/rustchain_v2.db
```

## Requirements

Python 3.8+ (stdlib only, no third-party dependencies).
