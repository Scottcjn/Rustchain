# Rent-a-Relic

> Vintage compute reservation marketplace for RustChain agents.

Rent-a-Relic lets agents reserve rare, vintage hardware for time-boxed compute sessions.
RTC is locked in escrow on reservation and released on completion or timeout.
Every session produces a signed Ed25519 provenance receipt.

## Quick Start

```bash
pip install flask cryptography
cd rustchain-fork
python -m tools.rent_a_relic.server
# Server on http://0.0.0.0:5050
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET  | /relic/available             | Available machines with specs & time slots |
| POST | /relic/reserve               | Reserve machine, lock RTC escrow |
| GET  | /relic/receipt/<session_id>  | Signed Ed25519 provenance receipt |
| GET  | /relic/machines              | Full registry with attestation history |
| GET  | /relic/leaderboard           | Most-rented machines |
| GET  | /relic/reservation/<id>      | Reservation status |
| POST | /relic/complete/<session_id> | Complete session, release escrow |

## Machine Registry

8 vintage machines: G3, G4, G5, POWER8, SPARC Ultra, AlphaServer, Amiga 3000T, HiFive Unmatched.

Architectures: ppc32, ppc64, ppc64le, sparc64, alpha, m68k, riscv64.

## Time Slots

Only 1h, 4h, or 24h slots are supported.

## RTC Escrow

- Locked: on `POST /relic/reserve`
- Released (completed): on `POST /relic/complete/<session_id>`
- Released (timeout): auto-swept on next request when `expires_at` has passed

## Provenance Receipts

Each session generates an Ed25519-signed receipt containing:
- `machine_passport_id` — anchored to on-chain registry
- `session_id`, `agent_id`, `duration_hours`
- `output_hash` — SHA-256 of session output
- `attestation_proof` — deterministic SHA-256 digest
- `ed25519_signature` — signed by machine's private key
- `public_key_hex` — for independent verification

```python
from tools.rent_a_relic.provenance import verify_receipt
valid = verify_receipt(receipt)  # True / False
```

## MCP Integration

```python
from tools.rent_a_relic.mcp_integration import MCP_TOOLS, RelicMCPClient

client = RelicMCPClient()
machines = client.list_relics(arch_filter="ppc64")
result   = client.reserve_relic("my_agent", "g5-dual", 4, 32.0)
receipt  = client.get_receipt(result["session_id"])
```

## Tests

```bash
pytest tests/test_rent_a_relic.py -v
# 31 tests, all passing
```

## License

Apache 2.0
