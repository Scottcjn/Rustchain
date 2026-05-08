# Entropy Profile Temporal Validation

Implements temporal validation of entropy profiles for RustChain hardware fingerprinting.

## Features

- Stores last 10 fingerprint snapshots per miner
- `validate_temporal_consistency()` function for anomaly detection
- Detects "frozen" profiles (zero variance - emulator detection)
- Detects "noisy" profiles (random spoofing detection)
- Expected drift bands per check type
- Integration with reward calculation
- Unit tests with synthetic profiles

## Usage

```python
from entropy_profile_validation import (
    MinerFingerprintHistory,
    validate_temporal_consistency,
    extract_metrics_from_fingerprint
)

# Record fingerprints
history = MinerFingerprintHistory()
metrics = extract_metrics_from_fingerprint(fingerprint_result, miner_id)
history.add_fingerprint(metrics)

# Validate temporal consistency
is_valid, details = validate_temporal_consistency(metrics, history)

if not is_valid:
    # Flag miner for review
    print(f"Anomaly detected: {details['reason']}")
```

## Anomaly Detection

| Profile Type | Detection | Reason |
|-------------|-----------|--------|
| Frozen | Variance = 0 | Deterministic emulator |
| Noisy | Variance too high | Random spoofing |
| Anomalous | CV outside bands | Fake hardware |

## Wallet

`miner-20260508-rustchain`