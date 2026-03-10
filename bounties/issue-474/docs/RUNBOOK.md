# Runbook: Epoch Determinism Simulator Operations

## Quick Reference

| Task | Command |
|------|---------|
| Basic simulation | `python3 src/epoch_determinism_simulator.py --epochs 5 --verbose` |
| Multi-node check | `python3 src/epoch_determinism_simulator.py --epochs 3 --nodes 5` |
| Record replay log | `python3 src/cross_node_replay.py --record --epochs 3 --output log.json` |
| Verify determinism | `python3 src/cross_node_replay.py --verify log.json` |
| Run tests | `python3 -m pytest tests/ -v` |

## Common Scenarios

### Scenario 1: Verify Determinism After Code Changes

```bash
# Before making changes
python3 src/epoch_determinism_simulator.py --seed 42 --epochs 5 --output baseline.json

# Make code changes...

# After changes
python3 src/epoch_determinism_simulator.py --seed 42 --epochs 5 --output new.json

# Compare (should be identical if deterministic)
python3 -c "import json; a=json.load(open('baseline.json')); b=json.load(open('new.json')); print('MATCH' if a['final_state_hash']==b['final_state_hash'] else 'DIVERGED')"
```

### Scenario 2: Test New Miner Configuration

```bash
# Create custom scenario
cat > fixtures/scenario_custom.json << 'EOF'
{
  "name": "Custom Test",
  "seed": 42,
  "epochs": 3,
  "miners": [
    {"id": "m1", "public_key": "pk1", "stake": 1000, "cpu_model": "CPU1", "release_year": 1980, "uptime_days": 365},
    {"id": "m2", "public_key": "pk2", "stake": 2000, "cpu_model": "CPU2", "release_year": 1985, "uptime_days": 400}
  ]
}
EOF

# Run simulation
python3 src/epoch_determinism_simulator.py --scenario fixtures/scenario_custom.json --verbose
```

### Scenario 3: Stress Test

```bash
# High-load scenario
python3 src/epoch_determinism_simulator.py --seed 99999 --epochs 10 --miners 20 --nodes 5 --verbose

# Expected output:
# - Simulation completed in XXXms
# - Determinism check: PASS
```

### Scenario 4: CI Integration

```bash
#!/bin/bash
set -e

# Record baseline
python3 src/cross_node_replay.py --record --seed 42 --epochs 3 --output evidence/ci_log.json

# Verify determinism
python3 src/cross_node_replay.py --verify evidence/ci_log.json --ci

# Run tests
python3 -m pytest tests/ -v --tb=short

echo "All checks passed"
```

### Scenario 5: Debug Divergence

```bash
# Enable verbose output
python3 src/cross_node_replay.py --replay log.json --verbose

# Check individual node states
python3 -c "
import json
result = json.load(open('replay_result.json'))
for node_id, state in result['node_states'].items():
    print(f'{node_id}: {state[\"status\"]} - {state[\"state_hash\"]}')"
```

## Troubleshooting

### Issue: Tests Fail with "DIVERGED"

**Symptoms**:
```
Replay completed in 150.23ms
All nodes converged: False
Divergence details: {...}
```

**Causes**:
1. Non-deterministic operation in simulator
2. Different Python versions
3. Unsorted dictionary iteration

**Resolution**:
```bash
# Check Python version consistency
python3 --version

# Run with verbose to see divergence point
python3 src/cross_node_replay.py --verify log.json --verbose

# Check for non-deterministic patterns in code:
# - Use of random.random() instead of DeterministicRNG
# - Dict iteration without sorting
# - Time-dependent operations
```

### Issue: Slow Performance

**Symptoms**: Simulation takes >1s for small epoch counts

**Resolution**:
```bash
# Profile execution
python3 -m cProfile -s cumtime src/epoch_determinism_simulator.py --epochs 5

# Common bottlenecks:
# - Too many miners (reduce --miners)
# - Too many epochs (reduce --epochs)
# - Hash computation (expected overhead)
```

### Issue: Memory Usage High

**Symptoms**: OOM errors with large epoch counts

**Resolution**:
```bash
# Reduce event logging
# Modify simulator to skip event recording for large runs

# Or reduce scope
python3 src/epoch_determinism_simulator.py --epochs 2 --miners 5
```

## Evidence Collection

For bounty submission or CI:

```bash
# Create evidence directory
mkdir -p evidence

# Generate replay log
python3 src/cross_node_replay.py --record --seed 42 --epochs 5 --nodes 3 --output evidence/replay_log.json

# Verify determinism
python3 src/cross_node_replay.py --verify evidence/replay_log.json --output evidence/verification.json --verbose

# Run test suite
python3 -m pytest tests/ -v --tb=short > evidence/test_results.txt 2>&1

# Generate summary
cat > evidence/summary.json << 'EOF'
{
  "timestamp": "$(date -Iseconds)",
  "seed": 42,
  "epochs": 5,
  "nodes": 3,
  "tests_passed": true,
  "determinism_verified": true
}
EOF

# List evidence
ls -la evidence/
```

## Performance Benchmarks

Expected performance on modern hardware:

| Configuration | Expected Time |
|--------------|---------------|
| 1 epoch, 3 miners | ~10ms |
| 3 epochs, 5 miners | ~50ms |
| 5 epochs, 10 miners | ~150ms |
| 10 epochs, 10 miners | ~300ms |
| 10 epochs, 10 miners, 5 nodes | ~1.5s |

## Integration Points

### With Existing RustChain Tests

```bash
# Add to existing test suite
cd tests/
python3 -m pytest test_epoch_simulator.py test_cross_node_replay.py -v
```

### With Consensus Probe

```bash
# Compare simulator output with consensus_probe.py
python3 node/consensus_probe.py --nodes node1,node2,node3
python3 src/epoch_determinism_simulator.py --nodes 3 --epochs 1
```

### With Attestation Fuzz Harness

```bash
# Use simulator to generate test cases
python3 src/epoch_determinism_simulator.py --scenario fixtures/scenario_basic.json --output test_input.json

# Feed to fuzz harness
python3 testing/attest_fuzz.py --input test_input.json
```

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUSTCHAIN_SEED` | 42 | Default simulation seed |
| `RUSTCHAIN_EPOCHS` | 5 | Default epoch count |
| `RUSTCHAIN_NODES` | 1 | Default node count |

### Scenario File Schema

```json
{
  "name": "string",
  "description": "string",
  "seed": "integer",
  "epochs": "integer",
  "miners": [
    {
      "id": "string",
      "public_key": "string",
      "stake": "integer",
      "cpu_model": "string",
      "release_year": "integer",
      "uptime_days": "integer"
    }
  ]
}
```

## Security Considerations

1. **Seed Handling**: Seeds are not secret but should be recorded for reproducibility
2. **No External I/O**: Simulator doesn't access network or filesystem during simulation
3. **Deterministic Only**: No cryptographic operations, only simulation

## Maintenance

### Updating Epoch Constants

If RustChain epoch parameters change:

```python
# Update in epoch_determinism_simulator.py
EPOCH_SLOTS = <new_value>  # Was 144
BLOCK_TIME = <new_value>   # Was 600
```

### Adding New Event Types

```python
# In _record_event method
self._record_event(slot, epoch, "new_event_type", actor, {
    "field1": value1,
    "field2": value2
})
```

### Extending Miner Attributes

```python
@dataclass
class MinerState:
    # Add new fields with defaults
    new_attribute: str = "default_value"
```

## Support

For issues or questions:
1. Check this runbook
2. Review IMPLEMENTATION.md for design details
3. Run tests with `-v` for detailed output
4. Check existing issues in bounties/issue-474
