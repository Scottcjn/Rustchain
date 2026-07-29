# AgentFolio ↔ Beacon Integration

> **Issue**: #2890 — AgentFolio ↔ Beacon Integration Spec + Reference Implementation
> **Scope**: 100 RTC (MVP)
> **Status**: MVP Complete — reference implementation with tests and demo

## One-Liner

Unified agent profiles (`AgentFolio`) that aggregate identity and reputation from both **Beacon Atlas** and **Agent Economy (RIP-302)**, plus cryptographically verifiable **bounty submission attestations** as Beacon v2 envelopes.

## Quick Start

```bash
cd bounties/issue-2890

# Run the demo
python examples/demo_folio.py

# Run tests
pytest tests/ -v
```

## What's Included

| Module | Purpose | Lines |
|--------|---------|-------|
| `src/agentfolio_beacon/folio.py` | `AgentFolio` dataclass + `assemble_folio()` | ~200 |
| `src/agentfolio_beacon/bridge.py` | `BeaconBridge` adapter for Beacon Atlas APIs | ~200 |
| `src/agentfolio_beacon/attestation.py` | `EnvelopeAttestation` — sign/verify bounty submissions | ~250 |
| `tests/test_folio.py` | Folio assembly, diff, table conversion | ~300 |
| `tests/test_bridge.py` | Bridge routing, error handling, mock integration | ~250 |
| `tests/test_attestation.py` | Attestation creation, verification, tamper detection | ~250 |
| `docs/SPEC.md` | Full specification | — |
| `examples/demo_folio.py` | End-to-end demo with mocked data | ~150 |

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  AgentFolio Assembly                  │
│                                                       │
│  AgentEconomyClient ──┐                               │
│                        ├──► BeaconBridge ──► Folio    │
│  Beacon Atlas API   ──┘                               │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│              Bounty Submission Attestation             │
│                                                       │
│  Submission ──► EnvelopeAttestation ──► Beacon v2     │
│                   (Ed25519 signed)                     │
│                                                       │
│  Anyone with pubkey ──► verify_attestation() ──► ✅   │
└──────────────────────────────────────────────────────┘
```

## Usage

### 1. Assemble an AgentFolio

```python
from rustchain.agent_economy import AgentEconomyClient
from agentfolio_beacon import BeaconBridge, assemble_folio

# Connect to your node
client = AgentEconomyClient(base_url="http://localhost:5000")
bridge = BeaconBridge(client)

# Assemble unified profile
folio = assemble_folio("my-agent", client, bridge)

print(f"Beacon pubkey: {folio.beacon_pubkey_hex}")
print(f"Economy score: {folio.economy_score}")
print(f"Beacon score:  {folio.beacon_score}")
print(f"Envelopes:     {folio.total_envelopes_sent}")
print(f"Active contracts: {folio.active_contracts}")
```

### 2. Create a Bounty Submission Attestation

```python
from nacl.signing import SigningKey
from agentfolio_beacon import attest_bounty_submission, verify_attestation

# Load your signing key (from secure storage, never hardcode)
signing_key = SigningKey(bytes.fromhex("your_private_key_hex"))

# Attest your submission
attestation = attest_bounty_submission(
    bounty_id="bounty_123",
    submission_id="sub_456",
    submitter_agent_id="my-agent",
    pr_url="https://github.com/Scottcjn/Rustchain/pull/123",
    summary="Implemented feature X with tests",
    signing_key_hex=signing_key.encode().hex(),
)

# The attestation is a self-contained, verifiable Beacon envelope
envelope_json = attestation.to_json()

# Anyone can verify it:
valid, reason = verify_attestation(attestation)
if valid:
    print("✅ Attestation is valid")
else:
    print(f"❌ Invalid: {reason}")
```

### 3. Verify an Attestation from JSON

```python
from agentfolio_beacon import verify_attestation_from_json

# Received from a submitter
received_json = '{"agent_id":"my-agent","kind":"bounty",...}'

valid, reason = verify_attestation_from_json(received_json)
```

### 4. Query Beacon Data Directly

```python
from agentfolio_beacon import BeaconBridge

bridge = BeaconBridge(economy_client)

# Relay agents
agents = bridge.list_relay_agents(status="active")

# Beacon reputation
rep = bridge.get_beacon_reputation("some-agent")

# Contracts
contracts = bridge.get_contracts(agent_id="my-agent", state="active")

# Open bounties
bounties = bridge.get_open_bounties()
```

## Dependencies

**Runtime**: Python 3.9+, stdlib only.

**Optional** (for attestation creation):
```bash
pip install pynacl
```

**Optional** (for attestation verification, alternative to pynacl):
```bash
pip install cryptography
```

The `BeaconBridge` and `AgentFolio` modules work without any crypto libraries — they only read data.

## Testing

```bash
cd bounties/issue-2890

# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=agentfolio_beacon --cov-report=term-missing

# Specific module
pytest tests/test_attestation.py -v
```

### Test Coverage

| Module | Tests | What's Covered |
|--------|-------|----------------|
| `attestation.py` | 15+ | Nonce generation, canonical fields, serialization, sign/verify, tamper detection, wrong key detection |
| `bridge.py` | 15+ | Relay agent lookup, reputation, contracts, bounties, envelopes, health, error handling |
| `folio.py` | 12+ | Dataclass serialization, assembly from both sources, failure isolation, diff detection |

## File Layout

```
bounties/issue-2890/
├── README.md                    # This file
├── docs/
│   └── SPEC.md                  # Full specification
├── src/
│   ├── agentfolio_beacon/
│   │   ├── __init__.py          # Public exports
│   │   ├── folio.py             # AgentFolio + assemble_folio()
│   │   ├── bridge.py            # BeaconBridge adapter
│   │   └── attestation.py       # EnvelopeAttestation + sign/verify
│   └── requirements.txt
├── tests/
│   ├── test_folio.py
│   ├── test_bridge.py
│   └── test_attestation.py
└── examples/
    └── demo_folio.py            # End-to-end demo
```

## Design Decisions

### Why a separate package (not in sdk/)?

This is a **cross-cutting integration** between two existing systems (Beacon Atlas + Agent Economy). It doesn't belong in either — it's a thin adapter layer with its own data model (`AgentFolio`) and attestation mechanism.

### Why graceful degradation?

Not all nodes have PyNaCl or cryptography installed. The folio assembly and bridge modules work with **zero crypto dependencies**. Attestation creation requires PyNaCl, but verification works with either PyNaCl or cryptography.

### Why Beacon v2 envelope format for attestations?

Reusing the existing Beacon envelope format means:
- Attestations can be stored in `beacon_envelopes` table
- They participate in the Ergo anchoring digest
- Verification uses the same canonical JSON rules already implemented
- No new schema or protocol needed

### Why read-only bridge?

The MVP scope is **aggregation and verification**, not mutation. The bridge reads from Beacon Atlas APIs to build folios. State changes (creating contracts, claiming bounties) are handled by the existing Agent Economy SDK.

## Security Notes

- **No private key storage**: The attestation module signs with caller-provided keys; it never generates or stores long-term keys.
- **Tamper-evident**: Any modification to an attestation's fields after signing invalidates the Ed25519 signature.
- **Replay-resistant**: Nonces are derived from `blake2b(submission_id || timestamp)`.
- **Read-only by default**: `BeaconBridge` never mutates state.

## Caveats and Assumptions

### Beacon API route names are hardcoded

`BeaconBridge` assumes the following routes exist on the Beacon Atlas Flask API
(`node/beacon_api.py`):

| Route | Purpose |
|-------|---------|
| `GET /api/agent/<id>` | Single relay agent lookup |
| `GET /beacon/atlas` | List all relay agents |
| `GET /api/reputation/<id>` | Agent reputation |
| `GET /api/reputation` | List all reputations |
| `GET /api/contracts` | All contracts |
| `GET /api/bounties` | Open bounties |
| `GET /api/beacon/envelopes` | Envelope summaries (may not exist on all nodes) |
| `GET /api/health` | Health check |

If a node renames or removes these endpoints, the corresponding bridge method
will return `None` or `[]` rather than raising — this is intentional graceful
degradation, but callers should be aware that an empty result may mean "endpoint
unavailable" rather than "no data."

### Bridge depends on `AgentEconomyClient._request` internals

`BeaconBridge._request` delegates to `economy_client._request(method, endpoint, ...)`
and optionally passes `base_url` as a kwarg. This assumes the SDK's `_request`
method accepts a `base_url` override. If the SDK changes this internal API, the
bridge will need updating. The bridge is tested against the current SDK behavior
via mocks; integration tests against a live node would catch drift.

### `count_agent_envelopes` fetches up to 10,000 envelopes

`count_agent_envelopes` calls `get_recent_envelopes(limit=10000)` and counts the
results. This is a stopgap because there is no `COUNT` endpoint. For agents with
more than 10,000 envelopes, the count will be capped. A proper solution would add
a `GET /api/beacon/envelopes/count/<agent_id>` endpoint to the Beacon API.

### `VALID_KINDS` constant is informational

`attestation.py` defines `VALID_KINDS = {"hello", "heartbeat", "want", "bounty", ...}`
matching the Beacon v2 spec, but the verifier only accepts `kind == "bounty"`.
The constant is present as a reference for future work that may support other
envelope kinds.

### Attestation signing requires PyNaCl; verification works with PyNaCl _or_ `cryptography`

- **Creating** attestations requires `pynacl` (Ed25519 signing).
- **Verifying** attestations works with either `pynacl` or `cryptography`.
- If neither is installed, `verify_attestation` returns `(False, "signature_verification_unavailable")`.
- The folio assembly and bridge modules have **zero** crypto dependencies.

### No private key management

This module signs with caller-provided keys and never generates, stores, or
rotates keys. Key management is the caller's responsibility.

## See Also

- [RIP-302 Agent Economy Spec](../../rips/docs/RIP-302-agent-economy.md)
- [Beacon Atlas API](../../node/beacon_api.py)
- [Beacon Anchor (Ergo)](../../node/beacon_anchor.py)
- [Beacon Identity (TOFU)](../../node/beacon_identity.py)
- [Agent Economy SDK](../../sdk/docs/AGENT_ECONOMY_SDK.md)
