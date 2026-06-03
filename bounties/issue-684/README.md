<!-- SPDX-License-Identifier: MIT -->
# RIP-302 Agent-to-Agent Transaction Test Challenge

> **Bounty #684**: Reproducible Agent-to-Agent transaction test challenge artifacts for Beacon + Grazer + RIP-302

This directory contains the complete implementation of **RIP-302**: a reproducible test challenge framework for verifying Agent-to-Agent (A2A) transactions across the RustChain ecosystem.

## 📋 Overview

RIP-302 defines a standardized framework for testing and verifying:
- **Beacon Protocol** - Agent identity, heartbeat, and envelope signing
- **Grazer Skill Discovery** - Capability discovery between agents
- **x402 Payment Rails** - Agent-to-agent value transfer on Base
- **Contract Settlement** - Full lifecycle from listing to settlement

## 🎯 Challenge Scenarios

| Scenario | Description | Steps | Evidence |
|----------|-------------|-------|----------|
| `heartbeat` | Basic A2A heartbeat exchange | 3 | Envelopes, signatures |
| `contracts` | Contract negotiation & settlement | 6 | Contract states, escrow |
| `grazer` | Skill discovery via Grazer | 3 | Capabilities, hashes |
| `payment` | x402 payment flow | 3 | Payment intent, tx record |

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Optional: `beacon-skill` (for real envelope signing)
- Optional: `grazer-skill` (for real capability discovery)

### Installation

```bash
# Navigate to the challenge directory
cd bounties/issue-684

# Install optional dependencies (if available)
pip install beacon-skill grazer-skill
```

### Run All Scenarios

```bash
# Run the full challenge suite (uses mock mode if dependencies unavailable)
python scripts/run_challenge.py --all

# Output will be saved to: evidence/
```

### Run Specific Scenario

```bash
# Run only the heartbeat scenario
python scripts/run_challenge.py --scenario heartbeat

# Run only the contracts scenario
python scripts/run_challenge.py --scenario contracts
```

### Verify Evidence

```bash
# Verify all evidence in the evidence directory
python scripts/verify_evidence.py --evidence-dir evidence/

# Verify a specific result file
python scripts/verify_evidence.py --result-file evidence/result_heartbeat_xxx.json
```

### Collect Proof for Bounty Submission

```bash
# Collect all evidence into a proof bundle
python scripts/collect_proof.py --output proof.json --include-metadata
```

## 📁 Directory Structure

```
bounties/issue-684/
├── README.md                 # This file
├── scripts/
│   ├── run_challenge.py      # Main challenge runner
│   ├── verify_evidence.py    # Evidence verification
│   ├── collect_proof.py      # Proof collection
│   └── ci_validate.sh        # CI/CD validation script
├── fixtures/
│   ├── agent_alpha.json      # Test agent Alpha config
│   ├── agent_beta.json       # Test agent Beta config
│   └── expected_state.json   # Expected state schema
├── evidence/
│   └── ...                   # Generated evidence files
├── docs/
│   └── RIP-302.md            # Full specification
└── .state/                   # Temporary state (git-ignored)
```

## 🔍 Evidence Schema

Each challenge run produces evidence following this schema:

```json
{
  "challenge_id": "a2a_rip302_heartbeat",
  "run_id": "run_abc123",
  "scenario": "heartbeat",
  "timestamp": "2026-03-06T12:00:00Z",
  "agents": {
    "initiator": { "agent_id": "bcn_xxx", ... },
    "responder": { "agent_id": "bcn_yyy", ... }
  },
  "steps": [
    {
      "step": 1,
      "action": "heartbeat_sent",
      "evidence_hash": "blake2b(...)",
      "payload": {...},
      "verified": true,
      "timestamp": "..."
    }
  ],
  "final_state": {
    "status": "completed",
    "evidence_digest": "blake2b(...)",
    "proof_file": "evidence/proof.json"
  }
}
```

## ✅ Verification Checks

The verification script performs these checks:

1. **Evidence Integrity** - All hashes match payloads
2. **Completeness** - All required steps present
3. **Final State** - Digest and status consistent
4. **Agent Configuration** - Valid agent IDs and fields
5. **Timestamps** - Valid ISO 8601 format

## 🔄 Reproducibility

All challenges are designed to be reproducible:

- **Deterministic Seeds** - Test agents use fixed seeds
- **Mockable Dependencies** - Works without external services
- **Isolated State** - Each run uses fresh state
- **Environment Capture** - Metadata includes Python version, platform, etc.

To verify reproducibility:

```bash
# Run twice and compare digests
python scripts/run_challenge.py --scenario heartbeat --output run1/
python scripts/run_challenge.py --scenario heartbeat --output run2/

# Compare evidence digests (should match)
jq '.final_state.evidence_digest' run1/result_*.json
jq '.final_state.evidence_digest' run2/result_*.json
```

## 🧪 CI/CD Integration

Use the provided CI script for automated validation:

```bash
# Full validation
./scripts/ci_validate.sh

# Skip execution, only verify existing evidence
./scripts/ci_validate.sh --skip-run

# Run specific scenario
./scripts/ci_validate.sh --scenario contracts
```

The CI script:
1. Runs challenge scenarios
2. Verifies all evidence
3. Collects proof bundle
4. Generates summary report

## 📤 Bounty Submission

To submit for bounty #684:

1. **Run all scenarios**:
   ```bash
   python scripts/run_challenge.py --all
   ```

2. **Verify evidence**:
   ```bash
   python scripts/verify_evidence.py --evidence-dir evidence/
   ```

3. **Collect proof**:
   ```bash
   python scripts/collect_proof.py --output proof.json --include-metadata
   ```

4. **Submit** the following:
   - `proof.json` - Complete proof bundle
   - `evidence/` directory - All result files
   - Link to your PR/issue comment

## 📚 Documentation

- [RIP-302 Specification](../../rips/docs/RIP-302-agent-to-agent-test-challenge.md) - Full technical specification
- [Evidence Schema](#-evidence-schema) - Evidence format documentation
- [CI/CD Guide](#-ci-integration) - Automated validation guide

## 🛠️ Development

### Adding New Scenarios

1. Add scenario to `run_challenge.py`:
   ```python
   def run_scenario_mynewscenario(self) -> ChallengeResult:
       # Implementation
       pass
   ```

2. Add to scenario map:
   ```python
   scenario_map = {
       "mynewscenario": self.run_scenario_mynewscenario,
       ...
   }
   ```

3. Add required steps to `verify_evidence.py`:
   ```python
   required_steps = {
       "mynewscenario": ["step1", "step2", ...],
       ...
   }
   ```

### Testing

```bash
# Run with verbose output
python scripts/run_challenge.py --scenario heartbeat --verbose

# Run with mock mode (even if beacon-skill installed)
python scripts/run_challenge.py --all --mock
```

## 🔐 Security Considerations

- **Test Keys Only** - All keys are deterministic and for testing only
- **No Production Use** - Do not use test agents in production
- **State Isolation** - Test state is separate from production DB
- **Evidence Tampering** - Hashes detect any tampering

## 📊 Example Output

```
============================================================
CHALLENGE SUMMARY
============================================================
Scenario: heartbeat    | Status: completed | Steps: 3 | Duration: 45ms
Scenario: contracts    | Status: completed | Steps: 6 | Duration: 78ms
Scenario: grazer       | Status: completed | Steps: 3 | Duration: 52ms
Scenario: payment      | Status: completed | Steps: 3 | Duration: 41ms
============================================================
```

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new scenarios
4. Submit a PR referencing bounty #684

## 📄 License

Apache 2.0 - See [LICENSE](../../LICENSE) for details.

## 🙏 Acknowledgments

- Beacon Protocol v2
- Grazer skill discovery
- x402 payment protocol
- RustChain bounty program

---

**Bounty**: #684  
**Status**: Implemented  
**Reward**: TBD  
**Author**: RustChain Core Team  
**Created**: 2026-03-06
