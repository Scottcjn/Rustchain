# Ghost Miner PoC (Issue #491)

This PoC demonstrates bypass strategies for the RIP-201 Fleet Detection Immune System.

## Bypassed Mechanisms:
1. **IP Clustering**: Implements IP diversity strategy across distinct /24 subnets.
2. **Timing Correlation**: Utilizes non-linear randomized jitter for attestation timestamps.
3. **Fingerprint Similarity**: Injects compute noise (cache pressure and SIMD load) to perturb hardware hashes.

## Usage:
```bash
python3 ghost_miner.py --count 5
```

## Significance:
Demonstrates the need for more advanced attestation challenges (e.g., memory-hard or interactive) to detect sophisticated "Ghost" fleets that decouple behavioral signals.
