# RustChain API Documentation

Complete OpenAPI 3.0 specification for the RustChain Node API.

## 📚 Documentation

- **Swagger UI**: Open `swagger.html` in your browser for interactive API documentation
- **OpenAPI Spec**: `openapi.yaml` - Machine-readable API specification

## 🚀 Quick Start

### View Documentation Locally

```bash
# Option 1: Open HTML file directly
open swagger.html

# Option 2: Serve with Python
python3 -m http.server 8000
# Then visit: http://localhost:8000/swagger.html

# Option 3: Serve with Node.js
npx http-server -p 8000
# Then visit: http://localhost:8000/swagger.html
```

### Validate Specification

```bash
npm install -g @apidevtools/swagger-cli
swagger-cli validate openapi.yaml
```

## 📖 API Overview

### Public Endpoints (No Authentication)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Node health check |
| `/ready` | GET | Readiness probe |
| `/epoch` | GET | Current epoch information |
| `/api/miners` | GET | List active miners |
| `/api/hall_of_fame` | GET | Hall of Fame leaderboard |
| `/api/fee_pool` | GET | Fee pool statistics (RIP-301) |
| `/balance` | GET | Get miner balance |
| `/lottery/eligibility` | GET | Check epoch eligibility |
| `/explorer` | GET | Block explorer page |

### Authenticated Endpoints (Require `X-Admin-Key`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/attest/submit` | POST | Submit hardware attestation |
| `/wallet/transfer/signed` | POST | Submit signed transfer |
| `/wallet/transfer` | POST | Admin transfer |
| `/withdraw/request` | POST | Request withdrawal |

## 🔧 Usage Examples

### Get Node Health

```bash
curl -s https://rustchain.org/health | jq
```

**Response:**
```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 12188,
  "db_rw": true,
  "tip_age_slots": 0,
  "backup_age_hours": 4.27
}
```

### Get Current Epoch

```bash
curl -s https://rustchain.org/epoch | jq
```

**Response:**
```json
{
  "epoch": 88,
  "slot": 12739,
  "blocks_per_epoch": 144,
  "enrolled_miners": 24,
  "epoch_pot": 1.5,
  "total_supply_rtc": 8388608
}
```

### List Active Miners

```bash
curl -s https://rustchain.org/api/miners | jq '.[0]'
```

**Response:**
```json
{
  "miner": "macmini-m2-134",
  "device_arch": "M2",
  "device_family": "Apple Silicon",
  "hardware_type": "Apple Silicon (Modern)",
  "last_attest": 1772350545,
  "antiquity_multiplier": 1.2,
  "entropy_score": 0,
  "first_attest": null
}
```

### Get Hall of Fame

```bash
curl -s https://rustchain.org/api/hall_of_fame | jq '.stats'
```

**Response:**
```json
{
  "total_machines": 73,
  "total_attestations": 426415,
  "oldest_year": 2001,
  "highest_rust_score": 310.4,
  "active_miners_now": 16,
  "average_rust_score": 61.9
}
```

## 🛠️ Development

### Generate Client SDKs

Use the OpenAPI spec to generate client libraries:

```bash
# JavaScript/TypeScript
npx @openapitools/openapi-generator-cli generate \
  -i openapi.yaml \
  -g typescript-axios \
  -o ./client-ts

# Python
openapi-generator-cli generate \
  -i openapi.yaml \
  -g python \
  -o ./client-python

# Go
openapi-generator-cli generate \
  -i openapi.yaml \
  -g go \
  -o ./client-go
```

### Import into Postman

1. Open Postman
2. Click "Import"
3. Select `openapi.yaml`
4. All endpoints will be imported with examples

### Use with Insomnia

1. Open Insomnia
2. Click "Create" → "Import From" → "File"
3. Select `openapi.yaml`

## 📝 Specification Details

- **OpenAPI Version**: 3.0.3
- **API Version**: 2.2.1-rip200
- **Base URL**: https://rustchain.org
- **Authentication**: API Key (X-Admin-Key header)
- **Response Format**: JSON

## 🔗 Links

- **Live API**: https://rustchain.org
- **GitHub**: https://github.com/Scottcjn/Rustchain
- **Bounties**: https://github.com/Scottcjn/rustchain-bounties

## 📄 License

MIT License - See [LICENSE](https://github.com/Scottcjn/Rustchain/blob/main/LICENSE)

## 🤝 Contributing

Found an issue or want to add more endpoints? Please open a PR or issue on GitHub!

---

**Generated for**: RustChain Bounty #502 (30 RTC)  
**Author**: ansomeck  
**Date**: 2026-03-01
