# Issue #474: Epoch Determinism Simulator + Cross-Node Replay Harness

## Overview

This bounty implements a **deterministic epoch simulation tool** and **cross-node replay harness** for RustChain. The simulator provides reproducible state transitions across multiple nodes using seeded PRNG, enabling verification of consensus determinism and detection of state divergence.

## Components

### 1. Epoch Determinism Simulator (`src/epoch_determinism_simulator.py`)

A deterministic simulator for RustChain epoch transitions that:
- Uses seeded PRNG for full reproducibility
- Simulates block production with RIP-200 round-robin weighted by antiquity
- Tracks miner rewards, attestations, and epoch finalization
- Produces identical state hashes given the same seed and initial state

### 2. Cross-Node Replay Harness (`src/cross_node_replay.py`)

A replay system that:
- Records simulation events to portable JSON logs
- Replays events across multiple simulated nodes
- Verifies state convergence across nodes
- Detects and reports divergence points

## Quick Start

### Basic Simulation

```bash
# Run a 5-epoch simulation with default settings
python3 src/epoch_determinism_simulator.py --seed 42 --epochs 5 --verbose

# Run with custom miner count
python3 src/epoch_determinism_simulator.py --seed 123 --epochs 3 --miners 10 --verbose

# Output results to JSON
python3 src/epoch_determinism_simulator.py --seed 42 --epochs 5 --output results.json
```

### Multi-Node Determinism Check

```bash
# Verify determinism across 5 parallel node simulations
python3 src/epoch_determinism_simulator.py --seed 42 --epochs 3 --nodes 5 --verbose
```

### Using Scenario Files

```bash
# Run with predefined scenario
python3 src/epoch_determinism_simulator.py --scenario fixtures/scenario_basic.json --verbose
```

### Cross-Node Replay

```bash
# Record a simulation for replay
python3 src/cross_node_replay.py --record --seed 42 --epochs 3 --nodes 3 --output replay_log.json

# Replay the recorded simulation
python3 src/cross_node_replay.py --replay replay_log.json --verbose

# Verify determinism of a replay log
python3 src/cross_node_replay.py --verify replay_log.json --verbose
```

## Architecture

### Deterministic RNG

```
DeterministicRNG
├── seed: int           # Initial seed value
├── state: int          # Current PRNG state
├── next_int()          # Generate deterministic integer
├── next_float()        # Generate deterministic float
├── choice()            # Deterministic list selection
└── shuffle()           # Deterministic list shuffle
```

### Simulation Flow

```
initialize_chain(miners)
    ↓
for each slot in epochs:
    ├── _get_epoch(slot)
    ├── _select_block_producer(slot)  # Weighted by antiquity
    ├── _produce_block(slot)
    ├── _distribute_block_reward()
    ├── _process_attestation()
    └── _record_event()
    ↓
_finalize_epoch()
    ↓
return SimulationResult
```

### Replay Flow

```
record_simulation() → ReplayLog
    ↓
replay_all(ReplayLog)
    ├── Initialize N nodes with same seed/miners
    ├── For each node:
    │   └── Replay all events in order
    ├── Compare final state hashes
    └── Return ReplayResult
```

## Data Structures

### MinerState

```python
@dataclass
class MinerState:
    miner_id: str
    public_key: str
    stake: int
    cpu_model: str
    release_year: int      # For antiquity calculation
    uptime_days: int
    blocks_produced: int = 0
    attestations_submitted: int = 0
    rewards_earned: int = 0
```

### SimulationResult

```python
@dataclass
class SimulationResult:
    seed: int
    node_id: str
    final_state_hash: str   # Key determinism indicator
    total_slots: int
    total_epochs: int
    total_blocks: int
    events: List[SimulationEvent]
    epoch_states: Dict[int, EpochState]
    miner_rewards: Dict[str, int]
    execution_time_ms: float
    deterministic: bool
```

### ReplayLog

```python
@dataclass
class ReplayLog:
    version: str
    seed: int
    total_epochs: int
    total_slots: int
    total_events: int
    initial_miners: List[Dict]
    events: List[Dict]
    expected_final_hash: str
    node_count: int
    recorded_at: int
```

## Antiquity Score Calculation

Block producer selection uses weighted antiquity scores:

```python
def compute_antiquity_score(self) -> float:
    current_year = 2025
    age_factor = float(current_year - self.release_year)
    uptime_factor = (float(self.uptime_days) + 1.0) ** 0.5
    stake_factor = (float(self.stake) / 1000.0) ** 0.3
    return age_factor * uptime_factor * stake_factor
```

Vintage CPUs with high uptime receive higher block production priority.

## Testing

### Run All Tests

```bash
cd bounties/issue-474
python3 -m pytest tests/ -v
```

### Run Specific Test Files

```bash
# Unit tests
python3 -m pytest tests/test_epoch_simulator.py -v

# Integration tests
python3 -m pytest tests/test_cross_node_replay.py -v
```

### CI Mode

```bash
# Exit with error on any failure
python3 -m pytest tests/ -v --tb=short
python3 src/cross_node_replay.py --verify replay_log.json --ci
```

## Scenario Files

Predefined scenarios in `fixtures/`:

| File | Description |
|------|-------------|
| `scenario_basic.json` | 5 miners with varying antiquity |
| `scenario_single_miner.json` | Single miner edge case |
| `scenario_stress.json` | 10 miners, 10 epochs load test |
| `scenario_seed_test.json` | Seed sensitivity verification |

## Evidence Collection

After running tests, collect evidence:

```bash
# Generate replay log
python3 src/cross_node_replay.py --record --seed 42 --epochs 5 --output evidence/replay_log.json

# Verify determinism
python3 src/cross_node_replay.py --verify evidence/replay_log.json --output evidence/verification.json --verbose

# Run full test suite
python3 -m pytest tests/ -v --tb=short > evidence/test_results.txt 2>&1
```

## Integration with RustChain

The simulator aligns with existing RustChain patterns:

- **Epoch constants**: `EPOCH_SLOTS = 144` (matches production)
- **Antiquity scoring**: Compatible with `proof_of_antiquity.rs`
- **Block production**: RIP-200 round-robin selection
- **Test patterns**: Follows existing pytest conventions

## CLI Reference

### epoch_determinism_simulator.py

```
--seed INT        Random seed (default: 42)
--epochs INT      Number of epochs (default: 5)
--nodes INT       Parallel node simulations (default: 1)
--miners INT      Genesis miner count (default: 5)
--scenario PATH   Scenario JSON file
--output PATH     Output results JSON
--verbose         Enable verbose output
```

### cross_node_replay.py

```
--record          Record new simulation
--replay PATH     Replay from log file
--verify PATH     Verify determinism
--seed INT        Random seed (default: 42)
--epochs INT      Epochs to simulate (default: 3)
--nodes INT       Node count (default: 3)
--output PATH     Output path
--verbose         Verbose output
--ci              Exit error on divergence
```

## License

Same license as RustChain main repository.
