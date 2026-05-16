# RustChain API Documentation

Complete OpenAPI 3.0 specification and Swagger UI for the RustChain REST API.

## Quick Start

### View Documentation

1. **Open Swagger UI**: Open `swagger.html` in a web browser
2. **Read OpenAPI Spec**: View `openapi.yaml` directly
3. **Test Endpoints**: Use "Try it out" in Swagger UI to test against live node

### Serve Locally

```bash
# Python 3 HTTP server
cd docs/api
python3 -m http.server 8080

# Then open in browser
open http://localhost:8080/swagger.html
```

## Files

| File | Description |
|------|-------------|
| `openapi.yaml` | OpenAPI 3.0.3 specification |
| `swagger.html` | Self-contained Swagger UI |
| `validate_openapi.py` | Schema validation script |
| `README.md` | This documentation |
| `REFERENCE.md` | Quick API reference |

## Endpoints Overview

### Public Endpoints (No Authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Node health check |
| GET | `/ready` | Readiness probe |
| GET | `/epoch` | Current epoch information |
| GET | `/api/miners` | List active miners |
| GET | `/api/nodes` | List connected nodes |
| GET | `/api/stats` | Network statistics |
| GET | `/api/hall_of_fame` | Hall of Fame leaderboard |
| GET | `/api/fee_pool` | RIP-301 fee pool stats |
| GET | `/api/settlement/{epoch}` | Historical settlement data |
| GET | `/wallet/balance?miner_id=X` | Wallet balance |
| GET | `/wallet/history?miner_id=X` | Transaction history |
| GET | `/wallet/swap-info` | Swap/bridge information |
| GET | `/lottery/eligibility?miner_id=X` | Epoch eligibility |
| GET | `/explorer` | Block explorer UI (HTML) |
| GET | `/governance/proposals` | List proposals |
| GET | `/governance/proposal/{id}` | Proposal details |
| GET | `/governance/ui` | Governance UI (HTML) |
| GET | `/api/premium/videos` | Premium video export |
| GET | `/api/premium/analytics/{agent}` | Agent analytics |
| GET | `/api/premium/reputation` | Reputation data |

### Signed Write Endpoints (Ed25519 Signature)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/wallet/transfer/signed` | Submit signed transfer |
| POST | `/attest/submit` | Submit hardware attestation |
| POST | `/governance/propose` | Create proposal |
| POST | `/governance/vote` | Submit vote |

### Admin Endpoints (X-Admin-Key Required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/wallet/transfer` | Admin transfer |
| POST | `/rewards/settle` | Trigger epoch settlement |
| POST | `/api/bridge/initiate` | Initiate bridge transfer |
| POST | `/api/bridge/void` | Void bridge transfer |
| POST | `/api/lock/release` | Release lock |
| POST | `/api/lock/forfeit` | Forfeit lock |

### Worker Endpoints (X-Worker-Key Required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/lock/auto-release` | Auto-release expired locks |

## Authentication

### Public Endpoints
No authentication required. Rate limits apply.

### Admin Authentication
Include the `X-Admin-Key` header:
```bash
curl -sk https://rustchain.org/wallet/transfer \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"from_miner": "treasury", "to_miner": "scott", "amount_rtc": 10.0}'
```

### Signed Transfers
Ed25519 signature in request body (no admin key needed):
```json
{
  "from_address": "senderRTC",
  "to_address": "recipientRTC",
  "amount_rtc": 10.0,
  "nonce": 1771187406,
  "signature": "base64_encoded_signature",
  "public_key": "hex_encoded_public_key"
}
```

## Rate Limits

| Endpoint Category | Limit |
|------------------|-------|
| Health/Ready | 60/min |
| Epoch/Miners/Stats | 30/min |
| Wallet Balance | 30/min |
| Attestation | 1/min per miner |
| Admin endpoints | 10/min |

## HTTPS Certificate

The node uses a self-signed certificate. Options:

```bash
# Option 1: Skip verification (development)
curl -sk https://rustchain.org/health

# Option 2: Trust the certificate
openssl s_client -connect rustchain.org:443 -showcerts < /dev/null 2>/dev/null | \
  openssl x509 -outform PEM > rustchain.pem
curl --cacert rustchain.pem https://rustchain.org/health
```

## Validation

### Validate OpenAPI Spec

```bash
# Using Python validator
python3 docs/api/validate_openapi.py docs/api/openapi.yaml

# Using swagger-cli (Node.js)
npm install -g swagger-cli
swagger-cli validate docs/api/openapi.yaml

# Using spectral (API linter)
npm install -g @stoplight/spectral-cli
spectral lint docs/api/openapi.yaml
```

### Expected Output
```
Validating: docs/api/openapi.yaml
------------------------------------------------------------
Loading specification...
✓ Specification loaded successfully
Validating Root structure...
✓ Root structure passed
Validating Paths and operations...
✓ Paths and operations passed
Validating Components...
✓ Components passed
Validating References...
✓ References passed
Validating Security...
✓ Security passed

============================================================
VALIDATION RESULTS
============================================================

✅ No errors or warnings found!
============================================================
```

## Usage Examples

### cURL Examples

#### Health Check
```bash
curl -sk https://rustchain.org/health | jq
```

#### Get Epoch Info
```bash
curl -sk https://rustchain.org/epoch | jq
```

#### List Miners
```bash
curl -sk https://rustchain.org/api/miners | jq
```

#### Check Balance
```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=scott" | jq
```

#### Get Transaction History
```bash
curl -sk "https://rustchain.org/wallet/history?miner_id=scott&limit=10" | jq
```

#### Check Eligibility
```bash
curl -sk "https://rustchain.org/lottery/eligibility?miner_id=scott" | jq
```

### Python Examples

```python
import requests

BASE_URL = "https://rustchain.org"

def get_health():
    """Check node health."""
    resp = requests.get(f"{BASE_URL}/health", verify=False)
    return resp.json()

def get_epoch():
    """Get current epoch info."""
    resp = requests.get(f"{BASE_URL}/epoch", verify=False)
    return resp.json()

def get_miners():
    """List active miners."""
    resp = requests.get(f"{BASE_URL}/api/miners", verify=False)
    return resp.json()

def get_balance(miner_id):
    """Get wallet balance."""
    resp = requests.get(
        f"{BASE_URL}/wallet/balance",
        params={"miner_id": miner_id},
        verify=False
    )
    return resp.json()

def get_history(miner_id, limit=10):
    """Get transaction history."""
    resp = requests.get(
        f"{BASE_URL}/wallet/history",
        params={"miner_id": miner_id, "limit": limit},
        verify=False
    )
    return resp.json()

def check_eligibility(miner_id):
    """Check epoch eligibility."""
    resp = requests.get(
        f"{BASE_URL}/lottery/eligibility",
        params={"miner_id": miner_id},
        verify=False
    )
    return resp.json()

# Usage
if __name__ == "__main__":
    print("Health:", get_health())
    print("Epoch:", get_epoch())
    print("Balance:", get_balance("scott"))
```

### JavaScript Examples

```javascript
const BASE_URL = "https://rustchain.org";

async function getHealth() {
  const resp = await fetch(`${BASE_URL}/health`);
  return resp.json();
}

async function getEpoch() {
  const resp = await fetch(`${BASE_URL}/epoch`);
  return resp.json();
}

async function getBalance(minerId) {
  const resp = await fetch(
    `${BASE_URL}/wallet/balance?miner_id=${minerId}`
  );
  return resp.json();
}

async function getHistory(minerId, limit = 10) {
  const resp = await fetch(
    `${BASE_URL}/wallet/history?miner_id=${minerId}&limit=${limit}`
  );
  return resp.json();
}

// Usage
getHealth().then(console.log);
getEpoch().then(console.log);
getBalance("scott").then(console.log);
```

### Bash Script Example

```bash
#!/bin/bash
# RustChain API helper script

BASE_URL="https://rustchain.org"
CURL="curl -sk"

get_health() {
  $CURL "$BASE_URL/health" | jq
}

get_epoch() {
  $CURL "$BASE_URL/epoch" | jq
}

get_balance() {
  local miner_id="$1"
  $CURL "$BASE_URL/wallet/balance?miner_id=$miner_id" | jq
}

get_history() {
  local miner_id="$1"
  local limit="${2:-10}"
  $CURL "$BASE_URL/wallet/history?miner_id=$miner_id&limit=$limit" | jq
}

check_eligibility() {
  local miner_id="$1"
  $CURL "$BASE_URL/lottery/eligibility?miner_id=$miner_id" | jq
}

# CLI interface
case "$1" in
  health) get_health ;;
  epoch) get_epoch ;;
  balance) get_balance "$2" ;;
  history) get_history "$2" "$3" ;;
  eligibility) check_eligibility "$2" ;;
  *) echo "Usage: $0 {health|epoch|balance|history|eligibility}" ;;
esac
```

## Integration

### Import into Postman

1. Open Postman
2. File → Import
3. Select `openapi.yaml`
4. Collection created with all endpoints

### Generate Client SDKs

```bash
# Install openapi-generator
# npm install -g @openapitools/openapi-generator-cli

# Python client
openapi-generator generate -i openapi.yaml -g python -o ./client-python

# JavaScript/TypeScript client
openapi-generator generate -i openapi.yaml -g typescript-axios -o ./client-ts

# Go client
openapi-generator generate -i openapi.yaml -g go -o ./client-go

# Rust client
openapi-generator generate -i openapi.yaml -g rust -o ./client-rust
```

### Embed in Documentation

The `swagger.html` file is self-contained and can be:
- Hosted on any static web server
- Embedded in existing documentation sites
- Served directly from the RustChain node

## Common Mistakes

### Wrong Endpoints

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| `/balance/{address}` | `/wallet/balance?miner_id=NAME` |
| `/miners?limit=N` | `/api/miners` (no pagination) |
| `/block/{height}` | `/explorer` (web UI) |
| `/api/balance` | `/wallet/balance?miner_id=...` |

### Wrong Field Names

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| `epoch_number` | `epoch` |
| `current_slot` | `slot` |
| `miner_id` (in response) | `miner` |
| `multiplier` | `antiquity_multiplier` |
| `last_attestation` | `last_attest` |

### Certificate Errors

```bash
# ❌ Wrong - will fail with certificate error
curl https://rustchain.org/health

# ✅ Correct - skip verification
curl -sk https://rustchain.org/health
```

## Response Examples

### Health Response
```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 43200,
  "db_rw": true,
  "backup_age_hours": 12.5,
  "tip_age_slots": 0
}
```

### Epoch Response
```json
{
  "epoch": 75,
  "slot": 10800,
  "blocks_per_epoch": 144,
  "epoch_pot": 1.5,
  "enrolled_miners": 10
}
```

### Miner Info Response
```json
{
  "miner": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC",
  "device_arch": "G4",
  "device_family": "PowerPC",
  "hardware_type": "PowerPC G4 (Vintage)",
  "antiquity_multiplier": 2.5,
  "entropy_score": 0.0,
  "last_attest": 1771187406,
  "first_attest": 1770000000
}
```

### Balance Response
```json
{
  "ok": true,
  "miner_id": "scott",
  "amount_rtc": 42.5,
  "amount_i64": 42500000
}
```

## Error Codes

| HTTP Code | Error | Description |
|-----------|-------|-------------|
| 200 | - | Success |
| 400 | `BAD_REQUEST` | Invalid JSON or parameters |
| 400 | `VM_DETECTED` | Hardware fingerprint failed |
| 400 | `INVALID_SIGNATURE` | Ed25519 signature invalid |
| 401 | `UNAUTHORIZED` | Missing or invalid X-Admin-Key |
| 404 | `NOT_FOUND` | Endpoint or resource not found |
| 404 | `WALLET_NOT_FOUND` | Wallet not found |
| 402 | `INSUFFICIENT_BALANCE` | Not enough RTC |
| 409 | `HARDWARE_ALREADY_BOUND` | Hardware enrolled to another wallet |
| 429 | `RATE_LIMITED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error |

## Related Documentation

- [API Reference](./REFERENCE.md) - Quick API reference
- [Bridge API](../bridge-api.md) - Cross-chain bridge documentation
- [API Walkthrough](../API_WALKTHROUGH.md) - Step-by-step guide

## Version History

| Version | Changes |
|---------|---------|
| 2.2.1-rip200 | Current version with RIP-200 and RIP-301 support |
| 2.2.0 | Added bridge endpoints (RIP-0305) |
| 2.1.0 | Added governance endpoints |
| 2.0.0 | Initial OpenAPI specification |

## Support

- GitHub: https://github.com/Scottcjn/rustchain-bounties
- Documentation: https://github.com/Scottcjn/Rustchain/tree/main/docs
