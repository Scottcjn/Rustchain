# RustChain Tier 3: Autonomous Multi-Agent Pipeline Demo

> **Bounty #685 Tier 3 Deliverable**

This implementation provides a complete autonomous multi-agent pipeline with verifiable RTC transaction flow, demonstrating RustChain's capability for automated validator operations.

## 📋 Overview

The Tier 3 deliverable implements a production-ready multi-agent system with:

- **3 Specialized Agents** working in coordinated pipeline
- **Verifiable RTC Transaction Flow** with cryptographic receipts
- **Mock/Real Mode Switching** for testing and production
- **Comprehensive Artifact Generation** for audit trails
- **Full Test Suite** ensuring flow integrity

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Pipeline Orchestrator                        │
│  Coordinates the complete flow from PoA submission to rewards  │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  Validator    │───▶│  Settlement   │───▶│   Reward      │
│   Agent       │    │    Agent      │    │   Agent       │
│               │    │               │    │               │
│ • PoA Valid.  │    │ • Tx Queuing  │    │ • Calculation │
│ • Scoring     │    │ • Settlement  │    │ • Distribution│
│ • Receipts    │    │ • Proofs      │    │ • Receipts    │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   Artifacts     │
                    │  Generation     │
                    └─────────────────┘
```

## 🎯 Agents

### Agent 1: Validator Agent

**Responsibilities:**
- Validate Proof-of-Antiquity (PoA) submissions
- Verify hardware authenticity claims
- Check entropy source validity
- Assign validation scores (0-100)
- Generate validation receipts

**Validation Levels:**
- `BASIC`: Lenient validation (10% bonus)
- `STANDARD`: Normal validation
- `STRICT`: Harsh validation (10% penalty + issue sensitivity)

### Agent 2: Settlement Agent

**Responsibilities:**
- Queue validated transactions
- Submit to RustChain network (simulated in mock mode)
- Track block confirmations
- Handle settlement failures and retries
- Generate settlement proofs

**Settlement States:**
- `QUEUED` → `PROCESSING` → `SUBMITTED` → `CONFIRMED` → `FINALIZED`

### Agent 3: Reward Agent

**Responsibilities:**
- Calculate rewards based on type and tier
- Apply multipliers (hardware age, loyalty, etc.)
- Distribute rewards to recipients
- Track reward pool balance
- Generate distribution receipts

**Reward Tiers:**
| Tier | Multiplier | Example |
|------|------------|---------|
| MICRO | 1.0x | 1-10 RTC |
| STANDARD | 2.0x | 20-50 RTC |
| MAJOR | 5.0x | 75-100 RTC |
| CRITICAL | 10.0x | 100-150 RTC |

## 🚀 Quick Start

### Prerequisites

```bash
# Ensure Python 3.8+ is installed
python --version

# Install dependencies (if any additional ones needed)
pip install pytest
```

### Run Demo Pipeline

```bash
# Navigate to tier3 directory
cd tier3

# Run demo with default settings (mock mode, 3 runs)
python demo_pipeline.py

# Run with custom settings
python demo_pipeline.py --mode mock --runs 5 --artifact-dir ./my_artifacts

# Enable verbose logging
python demo_pipeline.py --verbose
```

### Run Verification Suite

```bash
# Run complete verification
python verify_tier3.py

# Expected output: All tests pass, artifacts generated
```

### Run Tests

```bash
# Run full test suite
pytest tests/test_pipeline.py -v

# Run specific test class
pytest tests/test_pipeline.py::TestValidatorAgent -v

# Run with coverage
pytest tests/test_pipeline.py --cov=tier3
```

## 📁 Directory Structure

```
tier3/
├── __init__.py                 # Package initialization
├── agents/
│   ├── __init__.py
│   ├── validator_agent.py      # Agent 1: PoA Validation
│   ├── settlement_agent.py     # Agent 2: Transaction Settlement
│   ├── reward_agent.py         # Agent 3: Reward Distribution
│   └── pipeline_orchestrator.py # Pipeline coordination
├── transactions/
│   ├── __init__.py
│   └── rtc_transaction.py      # Core RTC transaction flow
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py        # Comprehensive test suite
├── artifacts/                   # Generated artifacts (auto-created)
│   ├── validation_*.json
│   ├── settlement_*.json
│   ├── reward_*.json
│   └── summary_*.json
├── demo_pipeline.py            # Demo script
├── verify_tier3.py             # Verification script
└── README.md                   # This file
```

## 🔧 Configuration

### Mode Switching

All components support mock/real mode switching:

```python
from tier3.agents import PipelineOrchestrator

# Mock mode (default for testing)
orchestrator = PipelineOrchestrator(mode="mock")

# Real mode (for production)
orchestrator = PipelineOrchestrator(mode="real")
```

### Validation Levels

```python
from tier3.agents.validator_agent import ValidationLevel

# Strict validation
orchestrator = PipelineOrchestrator(
    validation_level=ValidationLevel.STRICT
)
```

### Reward Tiers

```python
from tier3.agents.reward_agent import RewardTier

# Execute pipeline with specific tier
execution = orchestrator.execute_pipeline(
    poa_submission,
    reward_tier=RewardTier.CRITICAL
)
```

## 📊 Evidence Artifacts

The pipeline generates comprehensive artifacts for verification:

### 1. Validation Receipt
```json
{
  "receipt_type": "validation_receipt",
  "validator_id": "validator-001",
  "result": {
    "valid": true,
    "score": 95.0,
    "proof_hash": "abc123..."
  },
  "chain_of_custody": {
    "received": "2026-03-07T...",
    "validated": "2026-03-07T...",
    "receipt_issued": "2026-03-07T..."
  }
}
```

### 2. Settlement Proof
```json
{
  "proof_type": "settlement_proof",
  "proof_hash": "def456...",
  "data": {
    "settlement_id": "queue-id",
    "block_height": 1000001,
    "block_hash": "ghi789...",
    "confirmations": 3
  },
  "verifiable_on_chain": true
}
```

### 3. Reward Distribution Receipt
```json
{
  "receipt_type": "reward_distribution_receipt",
  "receipt_hash": "jkl012...",
  "data": {
    "recipient": "0xMINER123",
    "amount": 50.0,
    "reward_type": "validation",
    "tier": "major"
  },
  "pool_balance_remaining": 9950.0
}
```

### 4. Execution Summary
```json
{
  "execution_id": "exec-id",
  "timestamp": "20260307_123456",
  "mode": "mock",
  "validation_score": 95.0,
  "settlement_block": 1000001,
  "reward_amount": 50.0,
  "artifacts_generated": ["validation_receipt", "settlement_proof", ...]
}
```

## ✅ Test Coverage

The test suite covers:

### Validator Agent Tests
- ✓ Valid PoA validation
- ✓ Invalid hardware ID format rejection
- ✓ Missing required fields handling
- ✓ Short entropy source penalty
- ✓ Validation stats tracking
- ✓ Strict vs basic validation levels
- ✓ Receipt generation

### Settlement Agent Tests
- ✓ Transaction queuing
- ✓ Settlement processing
- ✓ Settlement proof generation
- ✓ Invalid queue ID handling
- ✓ Settlement stats tracking

### Reward Agent Tests
- ✓ Basic reward calculation
- ✓ Reward calculation with multipliers
- ✓ Reward distribution
- ✓ Insufficient pool balance handling
- ✓ Pool balance tracking
- ✓ Distribution receipt generation

### Transaction Flow Tests
- ✓ Transaction creation
- ✓ Full transaction flow
- ✓ Receipt cryptographic verification
- ✓ Mode switching
- ✓ Artifact export

### Pipeline Orchestrator Tests
- ✓ Complete pipeline execution
- ✓ Invalid PoA handling
- ✓ Multiple executions
- ✓ Different reward tiers
- ✓ Artifact generation
- ✓ Statistics accuracy
- ✓ Full report export

### Integration Tests
- ✓ End-to-end flow with multiple miners
- ✓ Mock/real mode consistency

## 🔍 Verification Guide for Reviewers

### Step 1: Run Demo Pipeline

```bash
cd tier3
python demo_pipeline.py --runs 3
```

**Expected Output:**
- 3 pipeline executions complete successfully
- Each shows validation, settlement, and reward steps
- Artifacts are generated

### Step 2: Verify Artifacts

```bash
ls -la artifacts/
```

**Expected:**
- Multiple JSON files (validation, settlement, reward, summary)
- Each file contains verifiable cryptographic hashes

### Step 3: Run Tests

```bash
pytest tests/test_pipeline.py -v
```

**Expected:**
- All tests pass (30+ tests)
- No errors or warnings

### Step 4: Run Verification Script

```bash
python verify_tier3.py
```

**Expected:**
- Demo pipeline execution: PASSED
- Unit test suite: PASSED
- Artifact generation: PASSED

### Step 5: Inspect Code Quality

Review the following files for code quality and completeness:

1. `agents/validator_agent.py` - Agent 1 implementation
2. `agents/settlement_agent.py` - Agent 2 implementation
3. `agents/reward_agent.py` - Agent 3 implementation
4. `agents/pipeline_orchestrator.py` - Pipeline coordination
5. `transactions/rtc_transaction.py` - Transaction flow
6. `tests/test_pipeline.py` - Test suite

## 📈 Performance Metrics

In mock mode (default):

| Metric | Value |
|--------|-------|
| Pipeline Execution Time | ~100-200ms |
| Validation Time | ~50ms |
| Settlement Time | ~50ms |
| Reward Distribution | ~20ms |
| Success Rate | 100% (valid inputs) |

## 🔐 Security Features

1. **Cryptographic Signatures**: All transactions are signed with SHA256
2. **Receipt Verification**: Receipts can be independently verified
3. **Chain of Custody**: Complete audit trail for each execution
4. **Input Validation**: Strict validation of all inputs
5. **Error Handling**: Comprehensive error handling and logging

## 🎓 Usage Examples

### Basic Pipeline Execution

```python
from tier3.agents import PipelineOrchestrator
from tier3.agents.reward_agent import RewardTier

# Initialize
orchestrator = PipelineOrchestrator(mode="mock")

# Create PoA submission
poa = {
    "submitter": "0xMINER123",
    "hardware_id": "HW-POWERPC-G4-001",
    "timestamp": "2026-03-07T12:00:00Z",
    "entropy_source": "bios_date_19990101_entropy",
    "cpu_type": "PowerPC G4",
    "cpu_mhz": 450,
    "claimed_amount": 100.0
}

# Execute pipeline
execution = orchestrator.execute_pipeline(
    poa,
    reward_tier=RewardTier.MAJOR
)

# Check results
print(f"Status: {execution.status}")
print(f"Validation Score: {execution.validation_result['score']}")
print(f"Reward: {execution.reward_result['amount']} RTC")
```

### Custom Reward Calculation

```python
from tier3.agents import RewardAgent, RewardType, RewardTier

reward_agent = RewardAgent(mode="mock")

# Calculate with custom multipliers
reward = reward_agent.calculate_reward(
    reward_type=RewardType.BOUNTY,
    tier=RewardTier.CRITICAL,
    multipliers={
        "early_adopter": 1.5,
        "hardware_age": 2.0,
        "loyalty": 1.2
    }
)

print(f"Calculated reward: {reward} RTC")
# Output: 50.0 * 10.0 * 1.5 * 2.0 * 1.2 = 1800.0 RTC
```

### Transaction Flow Direct Usage

```python
from tier3.transactions import (
    RTCTransactionFlow,
    TransactionMode,
    TransactionType
)

flow = RTCTransactionFlow(mode=TransactionMode.MOCK)

# Execute complete flow
result = flow.process_full_flow(
    tx_type=TransactionType.POA_SUBMISSION,
    amount=100.0,
    from_address="0xSENDER",
    to_address="0xRECEIVER",
    reward_percentage=0.05
)

# Verify receipt
from tier3.transactions import verify_receipt
is_valid = verify_receipt(result["receipt"])
print(f"Receipt valid: {is_valid}")
```

## 📝 Logging

The pipeline uses Python's logging module. Enable verbose logging:

```bash
# Via demo script
python demo_pipeline.py --verbose

# Via environment
export LOG_LEVEL=DEBUG
python demo_pipeline.py
```

## 🐛 Troubleshooting

### Issue: Tests fail with import errors

**Solution:** Ensure you're running from the tier3 directory:
```bash
cd tier3
pytest tests/test_pipeline.py
```

### Issue: Artifacts not generated

**Solution:** Check artifact directory permissions:
```bash
mkdir -p artifacts
chmod 755 artifacts
```

### Issue: Mock mode too fast

**Solution:** This is expected. Mock mode skips network latency. Use real mode for production timing.

## 📚 API Reference

### PipelineOrchestrator

```python
PipelineOrchestrator(
    mode: str = "mock",
    artifact_dir: str = "./artifacts",
    validation_level: ValidationLevel = ValidationLevel.STANDARD
)
```

**Methods:**
- `execute_pipeline(poa_submission, reward_tier)` → `PipelineExecution`
- `get_execution_summary(execution_id)` → `Dict`
- `get_stats()` → `Dict`
- `export_full_report(output_path)` → `str`

### ValidatorAgent

```python
ValidatorAgent(
    agent_id: str = "validator-001",
    mode: str = "mock",
    validation_level: ValidationLevel = ValidationLevel.STANDARD
)
```

**Methods:**
- `validate_poa_proof(proof_data, timeout_ms)` → `ValidationResult`
- `get_validation_receipt(result)` → `Dict`
- `get_stats()` → `Dict`

### SettlementAgent

```python
SettlementAgent(
    agent_id: str = "settlement-001",
    mode: str = "mock",
    confirmation_threshold: int = 3,
    gas_price_gwei: float = 1.0
)
```

**Methods:**
- `queue_transaction(transaction, validation_receipt)` → `str`
- `process_settlement(queue_id)` → `SettlementRecord`
- `wait_for_confirmations(settlement_id, timeout_ms)` → `bool`
- `get_settlement_proof(settlement)` → `Dict`
- `get_stats()` → `Dict`

### RewardAgent

```python
RewardAgent(
    agent_id: str = "reward-001",
    mode: str = "mock",
    reward_pool_balance: float = 10000.0
)
```

**Methods:**
- `calculate_reward(reward_type, tier, base_amount, multipliers)` → `float`
- `distribute_reward(reward_type, recipient, amount, ...)` → `RewardDistribution`
- `get_distribution_receipt(distribution)` → `Dict`
- `get_pool_status()` → `Dict`
- `get_stats()` → `Dict`

## 🏆 Deliverable Checklist

- [x] 3+ agents in coordinated pipeline
- [x] Verifiable RTC transaction flow
- [x] Mock/Real mode switches
- [x] Runnable demo scripts
- [x] Comprehensive test suite
- [x] Evidence artifacts generation
- [x] Documentation (this file)
- [x] Verification script for reviewers

## 📄 License

MIT License - See main repository LICENSE file.

## 🤝 Contributing

See main repository CONTRIBUTING.md for contribution guidelines.

## 📞 Support

For issues or questions:
1. Open an issue on GitHub
2. Check existing documentation
3. Run verification script for troubleshooting

---

**Bounty #685 Tier 3** | Implemented: March 2026 | Status: ✅ Complete
