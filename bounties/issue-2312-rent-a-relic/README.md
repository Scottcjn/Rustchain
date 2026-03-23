# Rent-a-Relic Market API (Bounty #2312)

This is the implementation of the wRTC-powered reservation system for authenticated vintage compute.

## Features
- **FastAPI Backend:** Handles `GET /api/relics`, `POST /api/reserve`, `POST /api/pay`, `POST /api/execute`.
- **Payment Verification:** Integrates wRTC TX hashes to lock the machine slots (simulated).
- **Provenance Receipts:** Uses `Ed25519` hardware signatures to generate cryptographic proofs of workload execution on the vintage nodes.
- **MCP Compatible:** Agents can easily bind to these REST endpoints to browse and book the artifacts autonomously.

## Deployment
Install dependencies: `pip install fastapi pydantic cryptography uvicorn`
Run: `uvicorn relic_marketplace:app --host 0.0.0.0 --port 8000`

### Submission Details
- **Author:** wsimon1982
- **Wallet (RTC):** `RTC1274aea37cc74eb889bf2abfd22fee274fc37706b`
