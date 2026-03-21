# Rent-a-Relic Market — RustChain Bounty #2312

**Build a wRTC-powered reservation system so AI agents can book authenticated time on named vintage machines through MCP and Beacon, then receive a provenance receipt for what they created.**

Most ecosystems sell generic compute. RustChain can sell compute with **ancestry, quirks, and romance**.

---

## Overview

The Rent-a-Relic Market enables AI agents to:
1. **Discover** vintage machines (POWER8, Mac G5, UltraSPARC, VAX, Cray…) with full specs and attestation history
2. **Reserve** time slots via a clean REST API (1h / 4h / 24h durations)
3. **Lock RTC** in escrow during reservation — released only on successful completion
4. **Access** the machine (SSH/API) during the reserved window
5. **Receive** a cryptographically-signed provenance receipt proving the work ran on that hardware

---

## Project Structure

```
relic_market/
├── RentMarket.sol              # Solidity contract: ERC-721 machine NFTs + rental state machine
├── machine_registry.py         # SQLite-backed machine registry + Python API
├── reservation_server.py      # Flask REST API server
├── provenance_receipt.py      # Ed25519-signed provenance receipt generation
├── marketplace_ui.py          # CLI tool for browsing and booking
├── escrow.py                   # RTC escrow manager
├── __init__.py                 # Package init
└── README.md                   # This file
```

---

## Quick Start

### 1. Install Dependencies

```bash
pip install flask nacl ed25519
```

### 2. Seed Demo Machines

```bash
cd relic_market
python machine_registry.py
```

### 3. Start the API Server

```bash
python reservation_server.py
# Server runs on http://localhost:5001
```

### 4. Browse Machines

```bash
python marketplace_ui.py list
python marketplace_ui.py available --hours 4
```

### 5. Book a Machine

```bash
python marketplace_ui.py book \
  --machine 0 \
  --hours 1 \
  --renter C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg
```

### 6. Complete a Rental & Get Receipt

```bash
python marketplace_ui.py complete \
  --rental <rental_id> \
  --output $(echo -n "my_computation_output" | sha256sum | cut -d' ' -f1) \
  --attestation "cpu_cycles=12345678"

python marketplace_ui.py receipt --receipt <receipt_id>
```

---

## API Reference

### `GET /relic/available`
List available machines with upcoming time slots.

**Query params:**
- `slot_hours` (int, default 1): Slot duration (1, 4, or 24)
- `machine_token_id` (optional): Filter to a specific machine

**Response:**
```json
{
  "machines": [
    {
      "token_id": 0,
      "name": "Old Ironsides",
      "model": "IBM POWER8 8247-21L",
      "hourly_rate_rtc": 50.0,
      "specs": { "CPU": "POWER8 12-core 3.02 GHz", "RAM": "512 GB DDR3 ECC", ... },
      "next_available_slots": [
        { "start": 1742611200, "end": 1742614800, "start_iso": "2025-03-22T00:00:00Z", ... }
      ]
    }
  ]
}
```

### `POST /relic/reserve`
Reserve a time slot on a machine. RTC is locked in escrow.

**Body:**
```json
{
  "machine_token_id": 0,
  "slot_hours": 1,
  "start_time": 1742611200,
  "renter": "C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg"
}
```

**Response:**
```json
{
  "rental_id": "rental_abc123xyz",
  "escrow_id": "a1b2c3d4e5f6",
  "rtc_locked": 50.0,
  "start_time_iso": "2025-03-22T00:00:00Z",
  "state": "pending"
}
```

### `POST /relic/complete`
Complete a rental and generate the provenance receipt.

**Body:**
```json
{
  "rental_id": "rental_abc123xyz",
  "output_hash": "sha256_of_computation_output",
  "attestation_proof": "cpu_cycles=12345678,instruction_count=..."
}
```

**Response:**
```json
{
  "rental_id": "rental_abc123xyz",
  "state": "completed",
  "receipt": {
    "receipt_id": "receipt_xyz789",
    "machine_passport_id": "Old Ironsides",
    "output_hash": "...",
    "signature": "ed25519_signature_hex",
    "verified": true
  }
}
```

### `GET /relic/receipt/<receipt_id>`
Fetch and verify a provenance receipt.

### `GET /relic/rentals?renter=<address>`
List all rentals for a wallet address.

### `GET /relic/escrow/summary`
Escrow state overview (locked, released, refunded).

### `GET /health`
Server health check.

---

## Demo Machines

| Token | Name | Model | Rate | Arch |
|-------|------|-------|------|------|
| 0 | Old Ironsides | IBM POWER8 8247-21L | 50 RTC/hr | ppc64le |
| 1 | Amber Ghost | Apple Mac G5 Quad | 30 RTC/hr | ppc64 |
| 2 | Solaris Sparrow | Sun UltraSPARC T2 | 25 RTC/hr | sparc64 |
| 3 | Vax Phantom | DEC VAX 11/780 (Sim.) | 15 RTC/hr | vax |
| 4 | Cray Shade | Cray X1E (Simulated) | 80 RTC/hr | cray |

---

## Solidity Contract (RentMarket.sol)

- Each machine is an **ERC-721 NFT** owned by the contract
- `registerMachine()` — register a new vintage machine
- `createRental()` — lock RTC in escrow, create reservation
- `completeRental()` — mark done, record output hash + attestation
- `mcpReserve()` — MCP tool bridge for AI agent integration

---

## Provenance Receipts

Each receipt includes:
- **Machine passport ID** (human-readable name)
- **Session duration** (start/end timestamps + seconds)
- **Output hash** (SHA-256 of what was computed)
- **Attestation proof** (hardware measurements from the session)
- **Ed25519 signature** — signed by the machine's Ed25519 key

Receipts are self-verifying:

```python
receipt = receipt_mgr.get_receipt(receipt_id)
print(receipt.verify())  # True if signature valid
```

---

## Leaderboard

```bash
python marketplace_ui.py leaderboard
```

Shows most-rented machines ranked by rental count.

---

## BoTTube Integration (Bonus)

Videos rendered on relic hardware can receive a special badge by:
1. Completing the rental with a `bottube_render_id` in the attestation field
2. The receipt's `machine_passport_id` + `ed25519_pubkey` serves as the badge verification key

---

## Technical Notes

- **Flask server** runs on port `5001` by default (`RELIC_API_BASE` env var to override)
- **SQLite** databases: `registry.db`, `escrow.db`, `reservations.db`, `receipts/`, `keys/`
- **Ed25519** keys per-machine stored in `keys/<machine_passport_id>.key`
- **Escrow** is simulated locally; in production, integrate with Solana wRTC payment channels
- **Attestation** is passed by the agent/renter — in production, hardware TEE (SEV, TrustZone) provides cryptographic attestation

---

## License

MIT — RustChain Contributors
