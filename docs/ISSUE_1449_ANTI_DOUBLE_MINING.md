# Issue #1449: Anti-Double-Mining Implementation

## Overview

This implementation enforces the rule that **one physical machine earns at most one reward per epoch**, regardless of how many miner IDs are run on that machine. This prevents reward manipulation through multiple miner instances on the same hardware.

## Problem Statement

Without anti-double-mining enforcement:
- A single machine could run multiple miner instances with different `miner_id` values
- Each miner ID would receive separate rewards for the same epoch
- This violates the "one CPU = one vote" principle of RIP-200
- Legitimate miners with multiple machines are unaffected

## Solution

### Machine Identity Keying

Machines are identified by a **hardware fingerprint hash** combining:
- `device_arch`: CPU architecture family (e.g., "g4", "g5", "modern")
- `fingerprint_profile`: Hardware characteristics from attestation:
  - CPU serial (when available)
  - Clock drift characteristics
  - Thermal variance
  - Cache timing ratios

This ensures:
- Same physical machine = same identity (even with different miner_ids)
- Different physical machines = different identities
- No false positives for legitimate distinct machines

### Ledger-Side Guardrails

At epoch settlement time (`settle_epoch_rip200`):

1. **Group miners by machine identity** - Query `miner_attest_recent` and `miner_fingerprint_history` to group all miners by their hardware fingerprint hash

2. **Select representative miner** - For machines with multiple miner IDs, select one representative using:
   - Highest entropy score (most authentic attestation)
   - Most recent attestation timestamp (tie-breaker)
   - Alphabetical order (deterministic final tie-breaker)

3. **Distribute one reward per machine** - Calculate time-aged multipliers per machine, not per miner_id

4. **Record telemetry** - Log all duplicate detections for monitoring

### Telemetry & Alerts

The system logs:
- **WARNING**: When duplicate machine identities are detected
- **INFO**: Which miner was selected as representative
- **INFO**: Which miners were skipped (with their representative)
- **METRIC**: `duplicate_machines_count=N epoch=X` for monitoring systems

Example log output:
```
[ANTI-DOUBLE-MINING] WARNING: Epoch 0: Detected 2 machines with multiple miner IDs
[ANTI-DOUBLE-MINING] WARNING:   Machine fac4d140... (g4): 3 miner IDs detected
[ANTI-DOUBLE-MINING] WARNING:     [1] miner-a3
[ANTI-DOUBLE-MINING] WARNING:     [2] miner-a2
[ANTI-DOUBLE-MINING] WARNING:     [3] miner-a1
[ANTI-DOUBLE-MINING] INFO: METRIC: duplicate_machines_count=2 epoch=0
[ANTI-DOUBLE-MINING] INFO: Epoch 0: Machine fac4d140... has 3 miners, selected miner-a3 as representative
```

## Files Modified/Created

### New Files

1. **`node/anti_double_mining.py`** - Core anti-double-mining logic
   - `compute_machine_identity_hash()` - Generate unique machine identity
   - `normalize_fingerprint()` - Extract stable hardware characteristics
   - `detect_duplicate_identities()` - Find machines with multiple miner IDs
   - `select_representative_miner()` - Choose which miner gets rewarded
   - `calculate_anti_double_mining_rewards()` - Full reward calculation with enforcement
   - `settle_epoch_with_anti_double_mining()` - Drop-in settlement function

2. **`node/tests/test_anti_double_mining.py`** - Comprehensive test suite
   - 19 tests covering all scenarios
   - Tests for identity computation, duplicate detection, representative selection
   - Tests for reward calculation, idempotency, and edge cases

### Modified Files

1. **`node/rewards_implementation_rip200.py`**
   - Added import for `anti_double_mining` module
   - Updated `settle_epoch_rip200()` with `enable_anti_double_mining` parameter (default: `True`)
   - Falls back to standard rewards if anti-double-mining fails

## Test Coverage

### Test Categories

1. **Machine Identity Tests** (6 tests)
   - Same fingerprint produces same identity hash
   - Different fingerprints produce different hashes
   - Different architectures produce different hashes
   - Empty fingerprint handling
   - Fingerprint normalization (CPU serial, clock characteristics)

2. **Duplicate Detection Tests** (2 tests)
   - Detects same machine with multiple miner IDs
   - No false positives for distinct machines

3. **Representative Selection Tests** (3 tests)
   - Selects highest entropy score
   - Uses most recent attestation on ties
   - Deterministic alphabetic tie-breaker

4. **Reward Calculation Tests** (3 tests)
   - Only one reward per machine
   - Different identities unaffected
   - Telemetry reports duplicates correctly

5. **Idempotency Tests** (2 tests)
   - Same rewards on repeated calculations
   - Same representative selection on re-runs

6. **Edge Case Tests** (3 tests)
   - Fingerprint failure = zero weight (no reward)
   - Missing fingerprint profile handled gracefully
   - Empty epoch returns empty rewards

### Running Tests

```bash
# Run all tests
cd node
python3 -m pytest tests/test_anti_double_mining.py -v

# Run standalone test
python3 anti_double_mining.py
```

All 19 tests pass ✓

## Behavior Examples

### Example 1: Same Machine, Multiple Miners

**Setup:**
- Machine A (serial: SERIAL-A-12345) runs 3 miners: `miner-a1`, `miner-a2`, `miner-a3`
- All have same fingerprint profile

**Result:**
- Only `miner-a3` receives reward (highest entropy score)
- `miner-a1` and `miner-a2` are skipped
- Telemetry logs the duplicate detection

### Example 2: Distinct Machines

**Setup:**
- Machine B (serial: SERIAL-B-67890) runs `miner-b1`
- Machine C (serial: SERIAL-C-11111) runs `miner-c1`

**Result:**
- Both miners receive rewards independently
- No duplicate detection logged

### Example 3: Idempotent Re-runs

**Setup:**
- Run reward calculation 5 times for same epoch

**Result:**
- All 5 runs produce identical rewards
- Same representative selected each time
- No double-spending possible

## Configuration

### Enable/Disable Anti-Double-Mining

```python
# In rewards_implementation_rip200.py
settle_epoch_rip200(db_path, epoch, enable_anti_double_mining=True)  # Default: enabled
```

### Monitoring Integration

The system emits structured logs suitable for monitoring:

```python
# Metric format
METRIC: duplicate_machines_count=N epoch=X

# Warning format
[ANTI-DOUBLE-MINING] WARNING: Machine <hash>... (<arch>): N miner IDs detected
```

Integrate with your monitoring stack (Prometheus, Grafana, etc.) to alert on high duplicate counts.

## Security Considerations

### False Positive Prevention

The implementation avoids false positives through:

1. **Stable hardware characteristics** - Uses CPU serial, clock drift, thermal variance
2. **Graceful degradation** - Missing fingerprint data doesn't block rewards
3. **Architecture separation** - Different CPU arch = different identity

### Attack Vectors Mitigated

1. **Multiple miner IDs on same machine** - Only one reward per machine
2. **Fingerprint spoofing** - Hardware characteristics are difficult to spoof
3. **Entropy manipulation** - Selection uses multiple criteria (entropy, timestamp, alphabetic)

### Remaining Considerations

1. **Hardware changes** - If a machine's hardware changes significantly, it may be treated as a new machine
2. **VM environments** - VMs with identical configurations may share identity (intended behavior)
3. **Privacy** - Machine identity hashes are not reversible, but operators should be aware of fingerprinting

## Backward Compatibility

- **Existing deployments**: Anti-double-mining is enabled by default but falls back gracefully if module is unavailable
- **Database schema**: No schema changes required; uses existing `miner_attest_recent` and `miner_fingerprint_history` tables
- **API compatibility**: `settle_epoch_rip200()` signature unchanged (new parameter has default value)

## Performance Impact

- **Minimal overhead**: Identity computation is O(n) where n = number of miners
- **Cached results**: Representative selection is deterministic, no re-computation needed
- **Database queries**: Uses indexed queries on `ts_ok` and `miner` columns

## Future Enhancements

Potential improvements for future iterations:

1. **Real-time detection** - Warn at attestation time if duplicate detected
2. **Historical tracking** - Store duplicate detection history for analytics
3. **Configurable thresholds** - Allow operators to tune fingerprint matching sensitivity
4. **Cross-epoch tracking** - Detect machines that rotate miner IDs across epochs

## References

- Issue #1449: Anti-Double-Mining Rule Enforcement
- RIP-200: Round-Robin + Time-Aged Consensus
- RIP-PoA: Proof of Antiquity Hardware Fingerprinting
