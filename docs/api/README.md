# RustChain API Documentation

This directory contains the OpenAPI 3.0 specification and Swagger UI for the RustChain Proof-of-Antiquity blockchain API.

## Quick Start

### View Swagger UI

Open `swagger.html` in your browser:

```bash
# Serve locally with Python
python3 -m http.server 8000
# Then visit: http://localhost:8000/swagger.html
```

Or use the live production API at https://rustchain.org

### Download OpenAPI Spec

```bash
curl -O https://raw.githubusercontent.com/Scottcjn/Rustchain/main/docs/api/openapi.yaml
```

### Validate the Spec

```bash
# Install swagger-cli
npm install -g @apidevtools/swagger-cli

# Validate
swagger-cli validate openapi.yaml
```

### Test Endpoints

```bash
# Health check
curl https://rustchain.org/health

# Current epoch
curl https://rustchain.org/epoch

# List active miners
curl https://rustchain.org/api/miners

# Hall of Fame leaderboard
curl https://rustchain.org/api/hall_of_fame

# Check miner balance
curl "https://rustchain.org/balance?miner_id=YOUR_MINER_ID"

# Check mining eligibility
curl "https://rustchain.org/lottery/eligibility?miner_id=YOUR_MINER_ID"
```

## API Overview

### Public Endpoints (No Authentication)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Node health status |
| `/epoch` | GET | Current epoch and slot info |
| `/api/miners` | GET | List all active miners |
| `/api/hall_of_fame` | GET | Hall of Fame leaderboard |
| `/api/fee_pool` | GET | RIP-301 fee pool statistics |
| `/balance` | GET | Miner balance query |
| `/lottery/eligibility` | GET | Mining eligibility check |
| `/explorer` | GET | Block explorer page |

### Authenticated Endpoints (Require X-Admin-Key)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/attest/submit` | POST | Submit hardware attestation |
| `/wallet/transfer/signed` | POST | Submit signed transfer |
| `/wallet/transfer` | POST | Admin transfer |
| `/withdraw/request` | POST | Request withdrawal |

## Antiquity Multipliers

RustChain rewards older hardware with higher multipliers:

| Hardware | Age | Multiplier |
|----------|-----|------------|
| Modern x86_64 | < 10 years | 1.0x |
| Apple Silicon (M1/M2/M3) | < 5 years | 1.2x |
| PowerPC G5 | 18-21 years | 2.0x |
| PowerPC G4 | 20-25 years | 2.5x |

## Epoch Structure

- **Blocks per epoch:** 144
- **Block time:** ~10 minutes
- **Epoch duration:** ~24 hours
- **Total Supply:** 8,388,608 RTC
- **Block reward:** Variable (based on epoch pot)

## Hall of Fame Categories

The Hall of Fame recognizes top miners in 5 categories:

1. **Ancient Iron** - PowerPC G4/G5 systems (25+ years old)
2. **Rust Belt Veterans** - Core 2 Duo / early x86_64 (15-25 years)
3. **Silicon Survivors** - Modern systems with high uptime
4. **Thermal Warriors** - Systems surviving thermal events
5. **Capacitor Plague Resistance** - Systems resistant to capacitor plague

## Authentication

Protected endpoints require an `X-Admin-Key` header:

```bash
curl -X POST https://rustchain.org/attest/submit \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -d '{"wallet":"...","hardware_info":{...}}'
```

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request (invalid parameters) |
| 401 | Unauthorized (missing/invalid admin key) |
| 403 | Forbidden (insufficient privileges) |
| 404 | Not Found (endpoint or resource) |
| 500 | Internal Server Error |

## SDK & Libraries

- **Python:** See `/sdk/python/` for RustChain client
- **JavaScript:** Coming soon
- **Go:** Coming soon

## Support

- **GitHub Issues:** https://github.com/Scottcjn/Rustchain/issues
- **Discord:** [Join the RustChain Discord]
- **Documentation:** https://docs.rustchain.org

## License

MIT License - See LICENSE file for details
