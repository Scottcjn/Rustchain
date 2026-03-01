# RustChain Node API Documentation

OpenAPI 3.0 specification and Swagger UI for the RustChain node API.

## Files

- `openapi.yaml` - OpenAPI 3.0 specification
- `swagger.html` - Self-contained Swagger UI page

## Endpoints Documented

### Public Endpoints (No Authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Node health check |
| GET | `/ready` | Readiness probe |
| GET | `/epoch` | Current epoch, slot, enrolled miners |
| GET | `/api/miners` | Active miners with attestation data |
| GET | `/api/stats` | Network statistics |
| GET | `/api/hall_of_fame` | Hall of Fame leaderboard (5 categories) |
| GET | `/api/fee_pool` | RIP-301 fee pool statistics |
| GET | `/balance?miner_id=X` | Miner balance lookup |
| GET | `/lottery/eligibility?miner_id=X` | Epoch eligibility check |
| GET | `/explorer` | Block explorer page |

### Authenticated Endpoints (X-Admin-Key Header)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/attest/submit` | Submit hardware attestation |
| POST | `/wallet/transfer/signed` | Ed25519 signed transfer |
| POST | `/wallet/transfer` | Admin transfer (requires admin key) |
| POST | `/withdraw/request` | Withdrawal request |

## Usage

### View Documentation Locally

1. Open `swagger.html` in a web browser
2. The page will load the OpenAPI spec from `openapi.yaml`
3. Use "Try it out" to test endpoints against the live node

### Host with Python

```bash
# Serve files locally
python3 -m http.server 8080

# Open in browser
open http://localhost:8080/swagger.html
```

### Validate Spec

```bash
# Install swagger-cli
npm install -g swagger-cli

# Validate
swagger-cli validate openapi.yaml
```

### Test Against Live Node

Test endpoints against the production node:

```bash
# Health check
curl -sk https://rustchain.org/health | jq

# Epoch info
curl -sk https://rustchain.org/epoch | jq

# Active miners
curl -sk https://rustchain.org/api/miners | jq

# Hall of Fame
curl -sk https://rustchain.org/api/hall_of_fame | jq
```

## Integration

### Import into Postman

1. Open Postman
2. File → Import
3. Select `openapi.yaml`
4. Collection created with all endpoints

### Generate Client SDKs

```bash
# Python client
openapi-generator generate -i openapi.yaml -g python -o ./client-python

# JavaScript client
openapi-generator generate -i openapi.yaml -g javascript -o ./client-js

# Go client
openapi-generator generate -i openapi.yaml -g go -o ./client-go
```

### Embed in Documentation

The `swagger.html` file is self-contained and can be:
- Hosted on any static web server
- Embedded in existing documentation sites
- Served directly from the RustChain node

## API Response Examples

### Health Check
```json
{
  "status": "ok",
  "version": "2.2.1-rip200",
  "uptime_seconds": 12345,
  "timestamp": 1740783600
}
```

### Epoch Info
```json
{
  "epoch": 88,
  "slot": 12700,
  "slot_progress": 0.45,
  "seconds_remaining": 300,
  "enrolled_miners": [
    {
      "miner_id": "dual-g4-125",
      "architecture": "G4",
      "rust_score": 450.5
    }
  ]
}
```

### Miner List
```json
{
  "miners": [
    {
      "miner_id": "dual-g4-125",
      "architecture": "G4",
      "rust_score": 450.5,
      "last_attestation_timestamp": 1740783600,
      "attestations_count": 150,
      "status": "active"
    }
  ]
}
```

## Version History

- **2.2.1-rip200** - Current version with RIP-200 and RIP-301 support
- Added fee pool endpoints
- Added Hall of Fame categories
- Enhanced attestation response format
