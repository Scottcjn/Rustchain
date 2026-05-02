<!-- SPDX-License-Identifier: MIT -->
# RIP-302 Challenge Guide

> Detailed instructions for executing and verifying RIP-302 Agent-to-Agent transaction test challenges.

## Table of Contents

1. [Introduction](#introduction)
2. [Architecture Overview](#architecture-overview)
3. [Setup Guide](#setup-guide)
4. [Running Challenges](#running-challenges)
5. [Understanding Evidence](#understanding-evidence)
6. [Verification Process](#verification-process)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)

## Introduction

### What is RIP-302?

RIP-302 (RustChain Improvement Proposal 302) defines a **reproducible test challenge framework** for verifying Agent-to-Agent transactions. It provides:

- **Standardized testing** of A2A communication patterns
- **Cryptographic evidence** of transaction completion
- **Automated verification** of challenge results
- **Bounty submission** artifacts

### Why RIP-302 Matters

As RustChain's agent ecosystem grows, ensuring reliable A2A communication becomes critical. RIP-302 enables:

- **Developers** to test agent integrations
- **Auditors** to verify transaction integrity
- **Bounty hunters** to demonstrate working implementations
- **Users** to trust agent interactions

### Key Concepts

| Term | Definition |
|------|------------|
| **Agent** | Autonomous entity with identity (Beacon ID) and capabilities |
| **Envelope** | Signed message containing agent communication |
| **Heartbeat** | Periodic agent status broadcast |
| **Grazer** | Skill/capability discovery protocol |
| **x402** | Payment protocol for machine-to-machine transactions |
| **Evidence** | Cryptographic proof of challenge completion |
| **Proof Bundle** | Packaged evidence for bounty submission |

## Architecture Overview

### Component Flow

```
┌─────────────────┐
│  Challenge      │
│  Runner         │
│  (run_challenge.py) │
└────────┬────────┘
         │
         ├──────────────────┐
         │                  │
         ▼                  ▼
┌─────────────────┐  ┌─────────────────┐
│  Beacon         │  │  Grazer         │
│  Protocol       │  │  Discovery      │
│  - Identity     │  │  - Capabilities │
│  - Heartbeat    │  │  - Reputation   │
│  - Envelopes    │  │                 │
└────────┬────────┘  └────────┬────────┘
         │                    │
         └──────────┬─────────┘
                    │
                    ▼
         ┌──────────────────┐
         │  Evidence        │
         │  Collection      │
         │  - Hashes        │
         │  - Signatures    │
         │  - Timestamps    │
         └──────────────────┘
```

### Evidence Chain

Each challenge produces an evidence chain:

1. **Step 1**: Action performed (e.g., heartbeat sent)
2. **Step 2**: Payload hashed with blake2b
3. **Step 3**: Hash stored with timestamp
4. **Step 4**: All hashes combined into digest
5. **Step 5**: Digest signed and timestamped

## Setup Guide

### System Requirements

- **Python**: 3.10 or higher
- **Disk Space**: 100MB minimum
- **Memory**: 256MB minimum

### Installation Steps

#### Step 1: Clone Repository

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/bounties/issue-684
```

#### Step 2: Create Virtual Environment (Recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scriptsctivate
```

#### Step 3: Install Dependencies

```bash
# Core dependencies (always required)
pip install pytest

# Optional: Real Beacon integration
pip install beacon-skill

# Optional: Real Grazer integration
pip install grazer-skill
```

#### Step 4: Verify Installation

```bash
# Check Python version
python --version  # Should be 3.10+

# Test challenge runner
python scripts/run_challenge.py --list
```

Expected output:
```
Available RIP-302 Challenge Scenarios:
==================================================
  heartbeat    - Basic A2A Heartbeat Exchange
  contracts    - Contract Negotiation & Settlement
  grazer       - Skill Discovery via Grazer
  payment      - x402 Payment Flow
==================================================
```

### Configuration

No configuration required for basic usage. Advanced options:

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `RIP302_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARN, ERROR) |
| `RIP302_STATE_DIR` | `.state` | Directory for temporary state |
| `RIP302_EVIDENCE_DIR` | `evidence/` | Directory for evidence output |

## Running Challenges

### Basic Usage

#### Run All Scenarios

```bash
python scripts/run_challenge.py --all
```

This executes all four scenarios and saves results to `evidence/`.

#### Run Specific Scenario

```bash
# Heartbeat exchange
python scripts/run_challenge.py --scenario heartbeat

# Contract negotiation
python scripts/run_challenge.py --scenario contracts

# Grazer discovery
python scripts/run_challenge.py --scenario grazer

# Payment flow
python scripts/run_challenge.py --scenario payment
```

### Advanced Options

#### Verbose Output

```bash
python scripts/run_challenge.py --scenario heartbeat --verbose
```

#### Custom Output Directory

```bash
python scripts/run_challenge.py --all --output /path/to/output/
```

#### Force Mock Mode

Even if beacon-skill is installed, use mock implementations:

```bash
python scripts/run_challenge.py --all --mock
```

### Expected Output

```
2026-03-06 12:00:00,000 [INFO] Running Scenario 1: Heartbeat Exchange
2026-03-06 12:00:00,001 [INFO] Step 1: heartbeat_sent (hash: abc123...)
2026-03-06 12:00:00,002 [INFO] Step 2: heartbeat_received (hash: def456...)
2026-03-06 12:00:00,003 [INFO] Step 3: envelopes_verified (hash: ghi789...)
2026-03-06 12:00:00,045 [INFO] Saved result to evidence/result_heartbeat_run_abc123.json

============================================================
CHALLENGE SUMMARY
============================================================
Scenario: heartbeat    | Status: completed | Steps: 3 | Duration: 45ms
============================================================
```

## Understanding Evidence

### Result File Structure

Each challenge produces a JSON result file:

```json
{
  "challenge_id": "a2a_rip302_heartbeat",
  "run_id": "run_abc123def456",
  "scenario": "heartbeat",
  "timestamp": "2026-03-06T12:00:00.000000+00:00",
  "agents": {
    "initiator": {
      "agent_id": "bcn_alpha_rip302",
      "name": "Agent Alpha",
      "role": "initiator",
      "pubkey": "0x...",
      "capabilities": ["heartbeat", "contracts"]
    },
    "responder": {
      "agent_id": "bcn_beta_rip302",
      "name": "Agent Beta",
      "role": "responder",
      "pubkey": "0x...",
      "capabilities": ["heartbeat", "contracts"]
    }
  },
  "steps": [
    {
      "step": 1,
      "action": "heartbeat_sent",
      "evidence_hash": "blake2b_hash_of_payload",
      "payload": {
        "from": "bcn_alpha_rip302",
        "envelope": "...",
        "direction": "alpha->beta"
      },
      "verified": true,
      "timestamp": "2026-03-06T12:00:00.001000+00:00"
    }
  ],
  "final_state": {
    "status": "completed",
    "evidence_digest": "aggregate_hash_of_all_steps",
    "proof_file": "evidence/proof_run_abc123.json",
    "steps_count": 3
  },
  "duration_ms": 45,
  "reproducible": true
}
```

### Key Fields Explained

| Field | Description |
|-------|-------------|
| `challenge_id` | Unique identifier for the challenge type |
| `run_id` | Unique ID for this specific run |
| `scenario` | Which scenario was executed |
| `agents` | Participating agents with IDs and pubkeys |
| `steps` | Ordered list of actions performed |
| `evidence_hash` | blake2b hash of step payload |
| `evidence_digest` | Aggregate hash of all step hashes |
| `verified` | Whether the step was successfully verified |

### Evidence Hash Computation

Each step's evidence hash is computed as:

```python
import hashlib
import json

def blake2b_hash(data):
    if isinstance(data, (dict, list)):
        serialized = json.dumps(data, sort_keys=True, separators=(',', ':'))
    else:
        serialized = str(data)
    return hashlib.blake2b(serialized.encode(), digest_size=32).hexdigest()
```

The final evidence digest combines all step hashes:

```python
def compute_digest(steps):
    combined = "|".join(s["evidence_hash"] for s in steps)
    return blake2b_hash(combined)
```

## Verification Process

### Manual Verification

#### Step 1: Verify Evidence Integrity

```bash
python scripts/verify_evidence.py --evidence-dir evidence/
```

This checks:
- All evidence hashes match payloads
- No tampering detected
- All required steps present

#### Step 2: Check Completeness

The verifier ensures all required steps are present:

| Scenario | Required Steps |
|----------|---------------|
| heartbeat | `heartbeat_sent`, `heartbeat_received`, `envelopes_verified` |
| contracts | `contract_listed`, `offer_made`, `offer_accepted`, `escrow_funded`, `contract_activated`, `contract_settled` |
| grazer | `grazer_query`, `capabilities_verified`, `service_requested` |
| payment | `payment_intent_created`, `payment_header_validated`, `payment_recorded` |

#### Step 3: Verify Final State

```bash
python scripts/verify_evidence.py \
  --result-file evidence/result_heartbeat_xxx.json \
  --verbose
```

Checks:
- Evidence digest matches computed digest
- Status is "completed"
- Steps count matches actual steps

### Automated Verification (CI/CD)

```bash
./scripts/ci_validate.sh
```

This runs:
1. Challenge execution
2. Evidence verification
3. Proof collection
4. Summary report generation

### Verification Report

The verification script produces a JSON report:

```json
{
  "verification_timestamp": "2026-03-06T12:00:00Z",
  "files_verified": 4,
  "all_passed": true,
  "results": [
    {
      "file": "evidence/result_heartbeat_xxx.json",
      "scenario": "heartbeat",
      "passed": true,
      "summary": {
        "checks": {
          "integrity": true,
          "completeness": true,
          "final_state": true,
          "agents": true,
          "timestamps": true
        },
        "issues_count": 0,
        "warnings_count": 0
      }
    }
  ]
}
```

## Troubleshooting

### Common Issues

#### Issue: "beacon-skill not installed"

**Symptom**: Warning message about beacon-skill not being available.

**Solution**: This is normal. The challenge runs in mock mode without beacon-skill. To use real Beacon:

```bash
pip install beacon-skill
```

#### Issue: "No result files found"

**Symptom**: Verification script reports no files to verify.

**Solution**: Run the challenge first:

```bash
python scripts/run_challenge.py --all
```

#### Issue: "Hash mismatch"

**Symptom**: Verification fails with hash mismatch error.

**Possible Causes**:
1. Evidence file was modified after creation
2. File corruption
3. Different Python version (affects JSON serialization)

**Solution**: Re-run the challenge and verify immediately.

#### Issue: "Missing steps"

**Symptom**: Verification reports missing required steps.

**Solution**: Ensure the challenge completed successfully. Check logs for errors.

### Debug Mode

Enable debug logging for detailed output:

```bash
python scripts/run_challenge.py --scenario heartbeat --verbose
```

Or set environment variable:

```bash
export RIP302_LOG_LEVEL=DEBUG
python scripts/run_challenge.py --all
```

### Getting Help

1. Check the [main README](../README.md)
2. Review the [RIP-302 specification](../docs/RIP-302-agent-to-agent-test-challenge.md)
3. Open an issue on GitHub
4. Ask in RustChain Discord

## Best Practices

### For Developers

1. **Run challenges early**: Test your agent integration before deployment
2. **Save evidence**: Keep all result files for audit trails
3. **Verify locally**: Run verification before pushing code
4. **Use mock mode**: Faster iteration during development

### For Bounty Hunters

1. **Run all scenarios**: Complete the full challenge suite
2. **Include metadata**: Use `--include-metadata` when collecting proof
3. **Verify twice**: Run verification before and after proof collection
4. **Document anomalies**: Note any warnings in your bounty submission

### For Auditors

1. **Check reproducibility**: Run challenges multiple times
2. **Verify hashes**: Manually verify a sample of hashes
3. **Review timestamps**: Ensure chronological order
4. **Inspect agent IDs**: Verify proper format (bcn_*)

### For CI/CD Integration

1. **Use the CI script**: `ci_validate.sh` handles all steps
2. **Cache evidence**: Store evidence as build artifacts
3. **Fail on warnings**: Treat warnings as errors in production
4. **Generate reports**: Save verification reports for compliance

## Appendix A: Command Reference

### Challenge Runner

```bash
python scripts/run_challenge.py --all                    # Run all scenarios
python scripts/run_challenge.py --scenario heartbeat     # Run specific scenario
python scripts/run_challenge.py --list                   # List scenarios
python scripts/run_challenge.py --output custom/         # Custom output dir
python scripts/run_challenge.py --mock                   # Force mock mode
python scripts/run_challenge.py --verbose                # Verbose output
```

### Evidence Verifier

```bash
python scripts/verify_evidence.py --evidence-dir evidence/     # Verify all
python scripts/verify_evidence.py --result-file result.json    # Verify one
python scripts/verify_evidence.py --check-reproducibility      # Check reproducibility
python scripts/verify_evidence.py --output report.json         # Save report
python scripts/verify_evidence.py --verbose                    # Verbose output
```

### Proof Collector

```bash
python scripts/collect_proof.py --output proof.json            # Collect proof
python scripts/collect_proof.py --include-metadata             # Include metadata
python scripts/collect_proof.py --result-files a.json b.json   # Specific files
```

### CI Validator

```bash
./scripts/ci_validate.sh                    # Full validation
./scripts/ci_validate.sh --skip-run         # Skip execution
./scripts/ci_validate.sh --scenario heartbeat  # Specific scenario
./scripts/ci_validate.sh --help             # Show help
```

## Appendix B: Evidence Schema Reference

See [expected_state.json](../fixtures/expected_state.json) for the complete schema definition.

---

**Document Version**: 1.0  
**Last Updated**: 2026-03-06  
**Maintained By**: RustChain Core Team
