# SPDX-License-Identifier: MIT
# RustChain Machine Passport Ledger

Give every relic a biography. On-chain passport format for individual machines:
ROM hashes, repair history, capacitor swaps, benchmark signatures, and lineage notes.

## Quickstart

```bash
cd passport/
pip install -r requirements.txt
python passport_server.py
# Open http://localhost:8070
```

## Features

- **Machine Passport data structure** — machine_id, name, architecture, ROM hash,
  manufacture_year, photo_hash, provenance, repair_log, attestation_history,
  benchmark_signatures
- **Immutable passport hash** — SHA-256 for on-chain anchoring
- **Web viewer** — `rustchain.org/passport/<machine_id>`
- **CLI/API updates** — miners create and update passports via REST API
- **QR code** — links to on-chain passport (Bonus)
- **Search** — filter by architecture or name
- **Vintage aesthetic** — amber/copper dark-mode design matching RustChain brand

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/passports` | List all passports |
| GET | `/api/passport/<id>` | Get full passport |
| POST | `/api/passport` | Create or update passport |
| POST | `/api/passport/<id>/repair` | Add repair log entry |
| POST | `/api/passport/<id>/benchmark` | Add benchmark signature |
| GET | `/api/search?architecture=G4` | Search passports |

## Passport Data Structure

```json
{
  "machine_id": "a3f8c92e...",
  "name": "Old Faithful",
  "manufacture_year": 2004,
  "architecture": "G4",
  "cpu_model": "PowerPC G4 7447A",
  "rom_hash": "abc123...",
  "photo_hash": "ipfs://Qm...",
  "provenance": "eBay lot #4521",
  "repair_log": [
    {"date": "2024-03", "description": "Replaced PRAM battery", "parts": ["CR2032"]}
  ],
  "attestation_history": {
    "first_seen_epoch": 100,
    "total_epochs": 4200,
    "total_rtc_earned": 1050.5,
    "multiplier": 2.5
  },
  "benchmark_signatures": [...]
}
```

## Hardware Tiers

| Tier | Age | Multiplier |
|---|---|---|
| Ancient | 30+ years | 3.5x |
| Sacred | 25-29 years | 3.0x |
| Vintage | 20-24 years | 2.5x |
| Classic | 15-19 years | 2.0x |
| Retro | 10-14 years | 1.5x |
| Modern | 5-9 years | 1.0x |
| Recent | 0-4 years | 0.5x |
