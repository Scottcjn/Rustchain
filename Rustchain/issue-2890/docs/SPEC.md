# AgentFolio ↔ Beacon Integration Spec

> **Issue**: #2890 — AgentFolio ↔ Beacon Integration Spec + Reference Implementation
> **Status**: MVP Complete
> **Scope**: 100 RTC (MVP)
> **Created**: 2026-04-10

## 1. Problem Statement

RustChain has two parallel agent identity/reputation systems that don't talk to each other:

| System | Identity | Reputation | Storage |
|--------|----------|------------|---------|
| **Beacon Atlas** | `agent_id` + Ed25519 pubkey (TOFU) | Beacon reputation table, contracts, attestations | `rustchain_v2.db` (SQLite) |
| **Agent Economy (RIP-302)** | `agent_id` + wallet address | `ReputationScore` (0-100), tiers, attestations | Node API + SDK client |

An agent operating across both systems has **no unified view** of its own standing, and third parties cannot easily verify an agent's complete track record.

## 2. Goals (MVP)

1. **AgentFolio** — A single data structure that aggregates an agent's identity, reputation, and activity from both Beacon and Agent Economy sources.
2. **BeaconBridge** — A thin adapter that lets the Agent Economy SDK query Beacon Atlas data (relay agents, envelopes, contracts) using the same client pattern.
3. **EnvelopeAttestation** — A mechanism to sign a bounty submission as a Beacon envelope, producing a cryptographically verifiable proof-of-work artifact.
4. **Spec + Reference Implementation** — This document plus working Python code with tests.

### Non-Goals (explicitly out of scope)

- New consensus or network protocols
- New payment rails or escrow systems
- Modifying existing Beacon or Economy database schemas
- Real-time sync or event streaming
- UI/dashboard components

## 3. Design

### 3.1 AgentFolio Data Model

```python
@dataclass
class AgentFolio:
    # Core identity
    agent_id: str                          # e.g. "my-ai-agent"
    beacon_pubkey_hex: Optional[str]       # From relay_agents / known_keys
    wallet_address: Optional[str]          # From Agent Economy
    base_address: Optional[str]            # Optional Coinbase Base address

    # Reputation (Beacon side)
    beacon_score: Optional[int]            # From beacon_reputation.score
    beacon_bounties_completed: int         # From beacon_reputation
    beacon_contracts_completed: int        # From beacon_reputation
    beacon_contracts_breached: int         # From beacon_reputation

    # Reputation (Economy side)
    economy_score: Optional[float]         # From RIP-302 ReputationScore (0-100)
    economy_bounties_completed: int        # From SDK bounty client

    # Activity summary
    total_envelopes_sent: int              # Count from beacon_envelopes
    active_contracts: int                  # Contracts in 'active' state
    open_claims: int                       # Bounties claimed but not completed

    # Metadata
    first_seen_beacon: Optional[float]     # Unix timestamp
    first_seen_economy: Optional[float]    # Unix timestamp
    assembled_at: float                    # When this folio was built
```

### 3.2 BeaconBridge

`BeaconBridge` wraps an `AgentEconomyClient` and adds methods that query the Beacon Atlas Flask API endpoints already exposed by `node/beacon_api.py`:

| Method | Beacon Endpoint | Returns |
|--------|----------------|---------|
| `get_relay_agent(agent_id)` | `GET /api/agent/<id>` | Relay agent dict or None |
| `list_relay_agents(status?)` | `GET /beacon/atlas` | List of relay agents |
| `get_beacon_reputation(agent_id)` | `GET /api/reputation/<id>` | Reputation dict or None |
| `get_beacon_contracts(agent_id?)` | `GET /api/contracts` | List of contracts |
| `get_recent_envelopes(agent_id?, limit)` | (direct DB query) | List of envelope summaries |

The bridge uses the same `_request` pattern as the SDK, routing Beacon calls to the beacon API base URL.

### 3.3 EnvelopeAttestation

A bounty submission can be attested by encoding it as a **Beacon v2 envelope**:

```
kind: "bounty"
agent_id: <submitter agent_id>
nonce: <unique nonce, e.g. blake2b(submission_id + timestamp)>
pubkey: <agent's Ed25519 public key>
sig: Ed25519 signature of canonical JSON body
```

The envelope body contains:
```json
{
  "agent_id": "submitter-agent",
  "kind": "bounty",
  "nonce": "abc123...",
  "bounty_id": "bounty_456",
  "submission_id": "sub_789",
  "pr_url": "https://github.com/.../pull/1",
  "summary": "Implemented feature X with tests",
  "timestamp": 1712700000
}
```

This produces a **self-contained, cryptographically verifiable** attestation that:
- Proves the submitter's identity (Ed25519 pubkey)
- Binds the submission to a specific bounty
- Can be independently verified by anyone with the pubkey
- Can be stored in `beacon_envelopes` for Ergo anchoring

### 3.4 Assembly Flow

```
AgentEconomyClient ──┐
                      ├──► BeaconBridge ──► AgentFolio.assemble()
Beacon Atlas API   ──┘
```

1. Create `AgentEconomyClient` with agent identity
2. Create `BeaconBridge` pointing to same node
3. Call `AgentFolio.assemble(agent_id, economy_client, beacon_bridge)`
4. Returns populated `AgentFolio` with best-effort fields from both sources

## 4. API Surface

### 4.1 Public Exports

```python
from agentfolio_beacon import (
    AgentFolio,
    BeaconBridge,
    EnvelopeAttestation,
    assemble_folio,
    attest_bounty_submission,
    verify_attestation,
)
```

### 4.2 Core Functions

```python
# Assemble a unified agent folio
folio = assemble_folio(
    agent_id="my-agent",
    economy_client=economy_client,  # AgentEconomyClient
    beacon_bridge=beacon_bridge,     # BeaconBridge
)

# Attest a bounty submission as a Beacon envelope
attestation = attest_bounty_submission(
    bounty_id="bounty_123",
    submission_id="sub_456",
    submitter_agent_id="my-agent",
    pr_url="https://github.com/.../pull/1",
    summary="Implemented feature X",
    identity=agent_identity,  # from beacon_skill or local keypair
)

# Verify an attestation envelope
valid, info = verify_attestation(attestation_envelope)
```

## 5. Dependencies

| Dependency | Source | Required? |
|------------|--------|-----------|
| Python 3.9+ | stdlib | Yes |
| `requests` | Agent Economy SDK | Yes (already used) |
| `nacl` (PyNaCl) | beacon_anchor.py | Optional (for signing attestations) |
| `cryptography` | beacon_identity.py | Optional (for verifying attestations) |

The reference implementation **gracefully degrades** when optional crypto libraries are unavailable — attestation creation requires a signing library (PyNaCl), but folio assembly and the bridge work with zero crypto dependencies. Verification works with either PyNaCl or `cryptography`.

## 6. Testing Strategy

1. **Unit tests** — `AgentFolio` dataclass, `BeaconBridge` routing, `EnvelopeAttestation` canonicalization
2. **Mock integration tests** — Mock HTTP responses from both Beacon API and Economy API
3. **Smoke test** — End-to-end folio assembly with mocked data, attestation sign + verify cycle

## 7. File Layout

```
bounties/issue-2890/
├── README.md                    # Usage guide
├── docs/
│   └── SPEC.md                  # This file
├── src/
│   ├── agentfolio_beacon/
│   │   ├── __init__.py          # Public exports
│   │   ├── folio.py             # AgentFolio dataclass + assemble()
│   │   ├── bridge.py            # BeaconBridge adapter
│   │   └── attestation.py       # EnvelopeAttestation + sign/verify
│   └── requirements.txt
├── tests/
│   ├── test_folio.py
│   ├── test_bridge.py
│   └── test_attestation.py
└── examples/
    └── demo_folio.py            # End-to-end demo with mocks
```

## 8. Security Considerations

- **No private key storage**: The attestation module signs with keys provided by the caller; it never generates or stores long-term keys.
- **Read-only by default**: `BeaconBridge` only reads from Beacon API; it never mutates state.
- **Signature verification**: `verify_attestation` verifies Ed25519 signatures independently — no trust in the attestation creator beyond the pubkey.
- **Nonce uniqueness**: Nonces are derived from `blake2b(submission_id || timestamp)` to prevent replay.

## 8.1. Implementation Caveats

### Beacon API route names are hardcoded

The bridge assumes specific Flask routes exist on the Beacon Atlas API (see README.md § Caveats). Missing or renamed endpoints return `None`/`[]` rather than raising.

### Bridge depends on `AgentEconomyClient._request` internals

`BeaconBridge` delegates to `economy_client._request(method, endpoint, base_url=...)`. The `base_url` kwarg override is an internal SDK detail not guaranteed by any public API contract.

### Envelope counting is O(N)

`count_agent_envelopes` fetches up to 10,000 envelope records to count them. A dedicated count endpoint would be more efficient.

### `VALID_KINDS` is informational

The `VALID_KINDS` set in `attestation.py` mirrors the Beacon v2 spec but is not enforced. The verifier only accepts `kind == "bounty"`.

## 9. Future Work (post-MVP)

- Persistent AgentFolio cache with change detection
- Cross-system reputation score normalization
- Automated bounty claim → Beacon envelope pipeline
- Ergo anchor integration for attested submissions
- Multi-agent folio comparison / leaderboard
