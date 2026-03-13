# Issue #473: State Hash Validator

## Overview

**State Hash Validator** is a standalone verification tool for RustChain that validates the integrity and correctness of node state hashes. It ensures deterministic state transitions across the network by independently computing and verifying state hashes.

**Reward**: 113 RTC ($11.3)

## Features

- ✅ **Independent State Hash Computation** - Compute state hashes from raw node data
- ✅ **Cross-Node Verification** - Compare state hashes across multiple nodes
- ✅ **Historical Validation** - Verify past epoch state hashes
- ✅ **Divergence Detection** - Detect and report state divergence points
- ✅ **API Integration** - Query live RustChain nodes via REST API
- ✅ **Report Generation** - Generate detailed validation reports in JSON/Markdown

## Quick Start

### Basic Validation

```bash
# Validate current state hash from a node
python3 state_hash_validator.py --node https://rustchain.org --validate

# Validate with verbose output
python3 state_hash_validator.py --node https://rustchain.org --validate --verbose
```

### Cross-Node Comparison

```bash
# Compare state hashes across multiple nodes
python3 state_hash_validator.py --nodes https://rustchain.org https://node2.rustchain.org --compare

# Output comparison results to JSON
python3 state_hash_validator.py --nodes https://rustchain.org https://node2.rustchain.org --compare --output comparison.json
```

### Historical Validation

```bash
# Validate historical epoch state hashes
python3 state_hash_validator.py --node https://rustchain.org --epoch 100 --validate-epoch

# Validate multiple epochs
python3 state_hash_validator.py --node https://rustchain.org --epoch-range 95-100 --validate-epochs
```

### Generate Report

```bash
# Generate comprehensive validation report
python3 state_hash_validator.py --node https://rustchain.org --report --output validation_report.md
```

## Architecture

### State Hash Computation

The validator computes state hashes using the same deterministic algorithm as RustChain nodes:

```python
def compute_state_hash(node_state: NodeState) -> str:
    """Compute deterministic hash of node state."""
    state_data = {
        "current_slot": node_state.current_slot,
        "current_epoch": node_state.current_epoch,
        "chain_tip": node_state.chain_tip_hash,
        "miners": sorted(node_state.miner_ids),
        "epochs": sorted(node_state.epoch_numbers),
        "total_supply": node_state.total_supply,
    }
    data = json.dumps(state_data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(data.encode()).hexdigest()[:16]
```

### Validation Flow

```
1. Query Node API
   ├── GET /api/miners → Active miners list
   ├── GET /epoch → Current epoch info
   ├── GET /api/stats → Node statistics
   └── GET /health → Node health status

2. Compute Expected State Hash
   ├── Collect miner data
   ├── Compute epoch state
   ├── Calculate chain tip hash
   └── Generate state hash

3. Compare & Verify
   ├── Compare computed hash with node-reported hash
   ├── Detect divergence (if any)
   └── Generate validation result
```

## Data Structures

### NodeState

```python
@dataclass
class NodeState:
    """Snapshot of a node's state for validation."""
    node_id: str
    node_url: str
    current_slot: int
    current_epoch: int
    chain_tip_hash: str
    miner_ids: List[str]
    epoch_numbers: List[int]
    total_supply: int
    reported_state_hash: str  # Hash reported by node
    computed_state_hash: str  # Hash computed by validator
    is_valid: bool
    validation_timestamp: int
```

### ValidationResult

```python
@dataclass
class ValidationResult:
    """Result of a state hash validation."""
    node_url: str
    validation_time: str
    state_hash_match: bool
    reported_hash: str
    computed_hash: str
    epoch: int
    slot: int
    miner_count: int
    divergence_details: Optional[Dict]
    status: str  # "valid", "diverged", "error"
```

### ComparisonReport

```python
@dataclass
class ComparisonReport:
    """Report comparing multiple nodes."""
    timestamp: str
    nodes_compared: int
    all_converged: bool
    consensus_hash: Optional[str]
    node_results: Dict[str, ValidationResult]
    divergence_count: int
    recommendations: List[str]
```

## API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Node health check |
| `/epoch` | GET | Current epoch info |
| `/api/miners` | GET | Active miners list |
| `/api/stats` | GET | Node statistics |
| `/api/state` | GET | Full state snapshot (if available) |

## CLI Reference

```
state_hash_validator.py

--node URL          Single node URL to validate
--nodes URL [URL...]  Multiple nodes for comparison
--validate          Validate current state hash
--validate-epoch    Validate specific epoch
--epoch INT         Epoch number for validation
--epoch-range START-END  Epoch range for validation
--compare           Compare state hashes across nodes
--report            Generate validation report
--output PATH       Output file path
--format FORMAT     Output format: json, markdown, text (default: text)
--verbose           Enable verbose output
--timeout SECONDS   API request timeout (default: 30)
```

## Examples

### Example 1: Single Node Validation

```bash
$ python3 state_hash_validator.py --node https://rustchain.org --validate --verbose

Validating node: https://rustchain.org
├── Fetching node state...
├── Current epoch: 1523
├── Current slot: 219312
├── Active miners: 47
├── Computing state hash...
├── Reported hash:  a3f5c8d9e2b1f4a7
├── Computed hash:  a3f5c8d9e2b1f4a7
└── Status: ✅ VALID

Validation completed in 1.23s
```

### Example 2: Multi-Node Comparison

```bash
$ python3 state_hash_validator.py --nodes https://rustchain.org https://node2.rustchain.org --compare

Comparing state hashes across 2 nodes...

Node 1: https://rustchain.org
  State Hash: a3f5c8d9e2b1f4a7
  Epoch: 1523, Slot: 219312, Miners: 47

Node 2: https://node2.rustchain.org
  State Hash: a3f5c8d9e2b1f4a7
  Epoch: 1523, Slot: 219312, Miners: 47

Consensus: ✅ ALL NODES AGREED
Consensus Hash: a3f5c8d9e2b1f4a7
```

### Example 3: Generate Report

```bash
$ python3 state_hash_validator.py --node https://rustchain.org --report --output report.md --format markdown

Report generated: report.md
```

## Testing

### Run Unit Tests

```bash
cd bounties/issue-473
python3 -m pytest tests/ -v
```

### Run Integration Tests

```bash
# Test against live node
python3 -m pytest tests/test_integration.py -v --live-node

# Run all tests with coverage
python3 -m pytest tests/ -v --cov=src --cov-report=html
```

## Integration with RustChain

The validator integrates with RustChain's existing infrastructure:

- **Compatible with**: `rustchain_v2_integrated_v2.2.1_rip200.py` node implementation
- **State hash algorithm**: Matches `compute_state_hash()` in node code
- **API protocol**: Uses standard RustChain REST API endpoints
- **Test patterns**: Follows existing pytest conventions

## Evidence Collection

After implementation, collect evidence:

```bash
# Run validation against production node
python3 state_hash_validator.py --node https://rustchain.org --validate --output evidence/validation_result.json

# Generate comparison report
python3 state_hash_validator.py --nodes https://rustchain.org https://node2.rustchain.org --compare --output evidence/comparison.json

# Run test suite
python3 -m pytest tests/ -v --tb=short > evidence/test_results.txt 2>&1
```

## Security Considerations

- **SSL/TLS Verification**: Validates node certificates by default
- **Timeout Protection**: Prevents hanging on unresponsive nodes
- **Input Sanitization**: Validates all API responses before processing
- **No Write Operations**: Read-only tool, cannot modify node state

## License

Same license as RustChain main repository.

## Wallet for Bounty

**RTC Address**: `RTC4325af95d26d59c3ef025963656d22af638bb96b`
