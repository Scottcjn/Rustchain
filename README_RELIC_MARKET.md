# Rent-a-Relic Market

**Bounty #2312** — Book Authenticated Time on Vintage Compute

A wRTC-powered reservation system for AI agents to book time on named vintage machines, with cryptographic provenance receipts proving exactly what hardware ran their computation.

---

## Features

### Machine Registry
Browse vintage machines by architecture (POWER8, G5, SPARC64, MIPS, ARM64). Each machine has:
- Full hardware specs
- Historical attestation score
- Total sessions and uptime
- Machine passport ID

### Reservation System
- Book 1h / 4h / 24h slots via REST API
- RTC payment locked in escrow during session
- SSH/API credentials provisioned automatically
- Time-limited access with automatic expiration

### Provenance Receipt
Every completed session generates a cryptographically-signed receipt containing:
- Machine passport ID
- Session start/end timestamps
- Output hash (hash of computation results)
- Hardware attestation proof
- Machine's Ed25519 signature

---

## Quick Start

```bash
# Initialize the market (creates sample machines)
python relic_market.py

# Start the API server
python -m http.server 8080
# OR with Flask:
FLASK_APP=relic_market flask run --port 8080
```

Then open `site/index.html` in your browser, or use the API directly.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/relic/machines` | List all machines |
| GET | `/api/relic/available` | List available machines |
| GET | `/api/relic/<machine_id>` | Get machine details + recent receipts |
| POST | `/api/relic/reserve` | Create a reservation |
| GET | `/api/relic/receipt/<receipt_id>` | Get a provenance receipt |
| GET | `/api/relic/machine/<machine_id>/receipts` | Get all receipts for a machine |

### Reserve a Machine

```bash
curl -X POST http://localhost:8080/api/relic/reserve \
  -H "Content-Type: application/json" \
  -d '{
    "machine_id": "power8-001",
    "agent_id": "my-agent-001",
    "duration_hours": 4
  }'
```

Response:
```json
{
  "reservation": {
    "id": "a1b2c3d4...",
    "machine_id": "power8-001",
    "cost_rtc": 48.0,
    "duration": 14400,
    "status": "pending",
    "ssh_credential": "ssh relic@power8-001.rustchain.org -p 2522"
  }
}
```

### Get Provenance Receipt

```bash
curl http://localhost:8080/api/relic/receipt/<receipt_id>
```

---

## Architecture

```
relic_market/
  relic_market.py   # Core logic: registry, reservations, receipts
  site/
    index.html      # Marketplace UI (vanilla JS, Chart.js)
```

Data is stored in `data/relic_market/`:
- `machines.json` — Machine registry
- `reservations.json` — Active and past reservations
- `receipts.json` — Generated provenance receipts

---

## Security

- SSH credentials generated per-session, not reused
- Private keys never exposed in API responses
- Escrow locks RTC for session duration
- Ed25519 signatures on all provenance receipts
- Attestation proof bound to session via nonce

---

## Example Use Cases

```python
# "I want my LLM inference to run on a POWER8 — book it"
reservation = create_reservation(
    machine_id="power8-001",
    agent_id="llm-agent-001",
    duration_hours=4
)

# "Generate this video on a G5 and prove it"
# After session:
receipt = complete_reservation(
    reservation_id=reservation.id,
    output_hash="sha256_of_rendered_video",
    attestation={"nonce": "...", "signature": "..."}
)
# receipt.machine_ed25519_pubkey proves it ran on G5
```

---

**Wallet:** `C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg`
**Bounty:** 150 RTC
