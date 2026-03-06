# RIP-302 Evidence Schema Reference

This document defines the complete schema for RIP-302 challenge evidence.

## Result File Schema

### Root Object

```typescript
interface ChallengeResult {
  challenge_id: string;      // Unique identifier: "a2a_rip302_<scenario>"
  run_id: string;            // Unique run identifier: "run_<uuid>"
  scenario: string;          // Scenario name: "heartbeat" | "contracts" | "grazer" | "payment"
  timestamp: string;         // ISO 8601 timestamp
  agents: AgentsObject;      // Participating agents
  steps: EvidenceStep[];     // Ordered list of evidence steps
  final_state: FinalState;   // Final state summary
  duration_ms: number;       // Execution duration in milliseconds
  reproducible: boolean;     // Whether the run is reproducible
}
```

### Agents Object

```typescript
interface AgentsObject {
  initiator: AgentConfig;    // The agent that initiated the challenge
  responder: AgentConfig;    // The agent that responded
}

interface AgentConfig {
  agent_id: string;          // Beacon agent ID (format: "bcn_*")
  name: string;              // Human-readable name
  role: string;              // "initiator" | "responder"
  pubkey?: string;           // Public key for signature verification
  wallet?: string;           // Wallet address (for payment scenarios)
  capabilities?: string[];   // List of agent capabilities
}
```

### Evidence Step

```typescript
interface EvidenceStep {
  step: number;              // Step number (1-indexed)
  action: string;            // Action type (see Action Types below)
  evidence_hash: string;     // blake2b hash of payload (64 hex chars)
  payload: object;           // Action-specific payload
  verified: boolean;         // Whether the step was verified
  timestamp: string;         // ISO 8601 timestamp
}
```

### Final State

```typescript
interface FinalState {
  status: string;            // "completed" | "failed"
  evidence_digest: string;   // Aggregate blake2b hash of all step hashes
  proof_file: string;        // Path to proof bundle file
  steps_count: number;       // Total number of steps
}
```

## Action Types by Scenario

### Heartbeat Scenario

| Action | Payload Schema | Description |
|--------|---------------|-------------|
| `heartbeat_sent` | `{ from: string, envelope: string, direction: string }` | Agent sent heartbeat |
| `heartbeat_received` | `{ from: string, envelope: string, direction: string }` | Agent received heartbeat |
| `envelopes_verified` | `{ alpha_verified: boolean, beta_verified: boolean }` | Envelopes verified |

**Example Payload:**
```json
{
  "step": 1,
  "action": "heartbeat_sent",
  "evidence_hash": "abc123...",
  "payload": {
    "from": "bcn_alpha_rip302",
    "envelope": "{\"agent_id\":\"bcn_alpha_rip302\",\"kind\":\"heartbeat\"}...",
    "direction": "alpha->beta"
  },
  "verified": true,
  "timestamp": "2026-03-06T12:00:00.000000+00:00"
}
```

### Contracts Scenario

| Action | Payload Schema | Description |
|--------|---------------|-------------|
| `contract_listed` | `{ seller: string, contract_id: string, price_rtc: number, terms: object }` | Contract listed |
| `offer_made` | `{ buyer: string, contract_id: string, offered_price: number }` | Offer made |
| `offer_accepted` | `{ contract_id: string, accepted_by: string }` | Offer accepted |
| `escrow_funded` | `{ contract_id: string, tx_ref: string }` | Escrow funded |
| `contract_activated` | `{ contract_id: string, status: string }` | Contract activated |
| `contract_settled` | `{ contract_id: string, settled_at: string }` | Contract settled |

### Grazer Scenario

| Action | Payload Schema | Description |
|--------|---------------|-------------|
| `grazer_query` | `{ queried_agent: string, capabilities: object }` | Grazer query performed |
| `capabilities_verified` | `{ agent_id: string, capability_hash: string, skills_count: number }` | Capabilities verified |
| `service_requested` | `{ request: object, request_hash: string }` | Service requested |

### Payment Scenario

| Action | Payload Schema | Description |
|--------|---------------|-------------|
| `payment_intent_created` | `{ intent: object, intent_hash: string }` | Payment intent created |
| `payment_header_validated` | `{ header_present: boolean, header_hash: string }` | X-PAYMENT header validated |
| `payment_recorded` | `{ tx_record: object, verified: boolean }` | Payment recorded |

## Hash Computation

### Evidence Hash

Each step's evidence hash is computed as:

```
evidence_hash = blake2b(json_serialize(payload), digest_size=32).hexdigest()
```

Where `json_serialize` uses:
- `sort_keys=True`
- `separators=(',', ':')`

### Evidence Digest

The final evidence digest combines all step hashes:

```
evidence_digest = blake2b(step1_hash + "|" + step2_hash + "|" + ... + stepN_hash)
```

## Complete Example

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
      "pubkey": "0x_alpha_pubkey_deterministic_seed_rip302_test",
      "capabilities": ["heartbeat", "contracts"]
    },
    "responder": {
      "agent_id": "bcn_beta_rip302",
      "name": "Agent Beta",
      "role": "responder",
      "pubkey": "0x_beta_pubkey_deterministic_seed_rip302_test",
      "capabilities": ["heartbeat", "contracts"]
    }
  },
  "steps": [
    {
      "step": 1,
      "action": "heartbeat_sent",
      "evidence_hash": "a1b2c3d4e5f6...",
      "payload": {
        "from": "bcn_alpha_rip302",
        "envelope": "{\"agent_id\":\"bcn_alpha_rip302\",\"kind\":\"heartbeat\"}...",
        "direction": "alpha->beta"
      },
      "verified": true,
      "timestamp": "2026-03-06T12:00:00.001000+00:00"
    },
    {
      "step": 2,
      "action": "heartbeat_received",
      "evidence_hash": "f6e5d4c3b2a1...",
      "payload": {
        "from": "bcn_beta_rip302",
        "envelope": "{\"agent_id\":\"bcn_beta_rip302\",\"kind\":\"heartbeat\"}...",
        "direction": "beta->alpha"
      },
      "verified": true,
      "timestamp": "2026-03-06T12:00:00.002000+00:00"
    },
    {
      "step": 3,
      "action": "envelopes_verified",
      "evidence_hash": "1a2b3c4d5e6f...",
      "payload": {
        "alpha_verified": true,
        "beta_verified": true
      },
      "verified": true,
      "timestamp": "2026-03-06T12:00:00.003000+00:00"
    }
  ],
  "final_state": {
    "status": "completed",
    "evidence_digest": "abc123def456...",
    "proof_file": "evidence/proof_run_abc123.json",
    "steps_count": 3
  },
  "duration_ms": 45,
  "reproducible": true
}
```

## Proof Bundle Schema

The proof bundle collects multiple results:

```typescript
interface ProofBundle {
  rip: string;                    // "RIP-302"
  challenge_type: string;         // "Agent-to-Agent Transaction Test"
  proof_digest: string;           // Aggregate digest of all results
  results: ChallengeResult[];     // All challenge results
  metadata?: MetadataObject;      // Optional metadata
  summary: SummaryObject;         // Summary statistics
}

interface MetadataObject {
  collected_at: string;           // ISO 8601 timestamp
  evidence_dir: string;           // Path to evidence directory
  results_count: number;          // Number of results
  environment: EnvironmentInfo;   // Python version, platform, etc.
  dependencies: DependencyInfo;   // Package versions
  git?: GitInfo;                  // Git commit and branch
}

interface SummaryObject {
  total_scenarios: number;        // Total number of scenarios
  scenarios: string[];            // List of scenario names
  total_steps: number;            // Total steps across all scenarios
  all_completed: boolean;         // Whether all scenarios completed
  proof_digest: string;           // Same as root proof_digest
}
```

## Verification Report Schema

```typescript
interface VerificationReport {
  verification_timestamp: string;  // ISO 8601 timestamp
  files_verified: number;          // Number of files verified
  all_passed: boolean;             // Overall pass/fail
  results: VerificationResult[];   // Per-file results
}

interface VerificationResult {
  file: string;                    // File path
  scenario: string;                // Scenario name
  run_id: string;                  // Run ID
  passed: boolean;                 // Pass/fail
  summary: VerificationSummary;    // Detailed results
}

interface VerificationSummary {
  all_passed: boolean;             // All checks passed
  checks: Record<string, boolean>; // Individual check results
  issues_count: number;            // Number of issues
  warnings_count: number;          // Number of warnings
  issues: Issue[];                 // List of issues
  warnings: Warning[];             // List of warnings
}
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-06 | Initial schema definition |

---

**Schema Version**: 1.0  
**Last Updated**: 2026-03-06  
**Maintained By**: RustChain Core Team
