# Issue #2127 - Beacon Join Routing Deployment Notes

**Date**: 2026-03-16
**Status**: Implementation Complete
**Commit**: Local only (no push/PR/comment)

---

## Overview

This implementation adds beacon join routing functionality to the RustChain Beacon Atlas system. Agents can register themselves via POST `/beacon/join` and clients can discover registered agents via GET `/beacon/atlas`.

---

## Endpoints

### POST /beacon/join

Register or update a relay agent in the beacon atlas.

**Request Body** (JSON):
```json
{
  "agent_id": "bcn_my_agent",
  "pubkey_hex": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
  "name": "My Agent Name",
  "coinbase_address": "0x1234567890123456789012345678901234567890"
}
```

**Required Fields**:
- `agent_id`: Unique agent identifier
- `pubkey_hex`: Hex-encoded public key (with or without 0x prefix)

**Optional Fields**:
- `name`: Human-readable agent name
- `coinbase_address`: Base network address for payments (must be 0x-prefixed, 40 hex chars)

**Response** (200 OK):
```json
{
  "ok": true,
  "agent_id": "bcn_my_agent",
  "pubkey_hex": "0x1234567890abcdef...",
  "name": "My Agent Name",
  "status": "active",
  "timestamp": 1710604800
}
```

**Error Responses**:
- `400 Bad Request`: Invalid input (missing fields, invalid pubkey_hex format)

**Upsert Behavior**: Duplicate `agent_id` updates the existing record (no error).

---

### GET /beacon/atlas

Get list of all registered relay agents.

**Query Parameters**:
- `status` (optional): Filter by status (e.g., `?status=active`)

**Response** (200 OK):
```json
{
  "agents": [
    {
      "agent_id": "bcn_my_agent",
      "pubkey_hex": "0x1234567890abcdef...",
      "name": "My Agent Name",
      "status": "active",
      "coinbase_address": "0x1234567890123456789012345678901234567890",
      "created_at": 1710604800,
      "updated_at": 1710604900
    }
  ],
  "total": 1,
  "timestamp": 1710605000
}
```

---

## Database Schema

### relay_agents Table

```sql
CREATE TABLE relay_agents (
    agent_id TEXT PRIMARY KEY,
    pubkey_hex TEXT NOT NULL,
    name TEXT,
    status TEXT DEFAULT 'active',
    coinbase_address TEXT DEFAULT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER
);

CREATE INDEX idx_relay_agents_status ON relay_agents(status);
```

---

## Input Validation

### pubkey_hex Validation
- Must be valid hexadecimal string
- Optional `0x` or `0X` prefix (stripped before validation)
- Empty string after prefix removal returns 400

### coinbase_address Validation (if provided)
- Must start with `0x` or `0X`
- Must be exactly 40 hex characters after prefix (20 bytes)
- Must be valid hexadecimal

---

## Deployment Configuration

### Flask Application

The beacon endpoints are implemented in `node/beacon_api.py` as a Flask blueprint.

**To register the blueprint in your main app**:
```python
from beacon_api import beacon_api, init_beacon_tables

# Initialize database tables
init_beacon_tables('rustchain_v2.db')

# Register blueprint with /beacon prefix
app.register_blueprint(beacon_api, url_prefix='/beacon')
```

### Nginx Configuration

Add the following upstream and location blocks to your nginx config:

```nginx
# Beacon Atlas service upstream
upstream beacon_atlas_backend {
    server beacon-atlas:8100;
}

server {
    # ... existing config ...

    # Beacon Atlas endpoints
    location /beacon/join {
        proxy_pass http://beacon_atlas_backend/beacon/join;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Content-Type application/json;

        # CORS preflight handling
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' '*';
            add_header 'Access-Control-Allow-Methods' 'POST, OPTIONS';
            add_header 'Access-Control-Allow-Headers' 'Content-Type';
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain charset=UTF-8';
            add_header 'Content-Length' 0;
            return 204;
        }
    }

    location /beacon/atlas {
        proxy_pass http://beacon_atlas_backend/beacon/atlas;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # CORS preflight handling
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' '*';
            add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS';
            add_header 'Access-Control-Allow-Headers' 'Content-Type';
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain charset=UTF-8';
            add_header 'Content-Length' 0;
            return 204;
        }
    }
}
```

### Docker Compose (Optional)

For containerized deployment, add the beacon service:

```yaml
services:
  beacon-atlas:
    build:
      context: .
      dockerfile: Dockerfile
    command: python node/beacon_api.py
    ports:
      - "8100:8100"
    volumes:
      - beacon_data:/data
    environment:
      - DB_PATH=/data/beacon_atlas.db
    restart: unless-stopped

volumes:
  beacon_data:
```

---

## Running Locally

### Development Mode

```bash
# 1. Install dependencies
pip install flask

# 2. Initialize and run the beacon API
cd node/
python3 -c "from beacon_api import init_beacon_tables; init_beacon_tables()"
python3 beacon_api.py
```

The server will start on `http://localhost:8100` (or configured port).

### Test the Endpoints

```bash
# Register an agent
curl -X POST http://localhost:8100/beacon/join \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "bcn_test",
    "pubkey_hex": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
    "name": "Test Agent"
  }'

# Get all agents
curl http://localhost:8100/beacon/atlas

# Test upsert (same agent_id, different data)
curl -X POST http://localhost:8100/beacon/join \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "bcn_test",
    "pubkey_hex": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    "name": "Updated Test Agent"
  }'

# Test invalid pubkey (should return 400)
curl -X POST http://localhost:8100/beacon/join \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "bcn_invalid",
    "pubkey_hex": "not-valid-hex"
  }'
```

---

## Running Tests

```bash
cd tests/
python3 test_beacon_join_routing.py -v
```

**Expected Output**:
```
test_atlas_agent_fields ... ok
test_atlas_empty_list ... ok
test_atlas_options_returns_cors_headers ... ok
test_atlas_returns_registered_agents ... ok
test_atlas_status_filter ... ok
test_full_join_then_atlas_workflow ... ok
test_join_invalid_coinbase_address_returns_400 ... ok
test_join_invalid_json_returns_400 ... ok
test_join_invalid_pubkey_hex_returns_400 ... ok
test_join_missing_agent_id_returns_400 ... ok
test_join_missing_pubkey_hex_returns_400 ... ok
test_join_options_returns_cors_headers ... ok
test_join_pubkey_without_0x_prefix ... ok
test_join_register_new_agent ... ok
test_join_upsert_duplicate_agent ... ok
test_join_with_coinbase_address ... ok
test_pubkey_hex_format_validation ... ok

Ran 17 tests in ~0.05s
OK
```

---

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| POST /beacon/join registers agent | ✅ Implemented |
| POST /beacon/join upserts on duplicate agent_id | ✅ Implemented |
| POST /beacon/join returns 400 for invalid pubkey_hex | ✅ Implemented |
| GET /beacon/atlas returns list of agents | ✅ Implemented |
| SQLite upsert on relay_agents table | ✅ Implemented |
| Input validation for all fields | ✅ Implemented |
| CORS headers for cross-origin requests | ✅ Implemented |
| Tests for join/atlas behavior | ✅ 17 tests passing |
| Nginx route config snippet | ✅ Added to nginx.conf |
| Deployment notes | ✅ This document |

---

## Files Modified/Created

### Modified
- `node/beacon_api.py` - Added relay_agents table, /beacon/join, /beacon/atlas endpoints
- `nginx.conf` - Added beacon proxy routes

### Created
- `tests/test_beacon_join_routing.py` - Test suite (17 tests)
- `docs/ISSUE_2127_DEPLOYMENT.md` - This deployment guide

---

## Security Considerations

1. **Input Validation**: All inputs are validated before database insertion
2. **SQL Injection**: Parameterized queries used throughout
3. **CORS**: Configured for cross-origin access (adjust for production)
4. **Rate Limiting**: Consider adding rate limiting in production
5. **Authentication**: Currently open; add auth for production if needed

---

## Future Enhancements

- Add authentication/authorization for join endpoint
- Implement rate limiting
- Add agent heartbeat/health check mechanism
- Add agent removal endpoint (POST /beacon/leave)
- Add pagination for /beacon/atlas with many agents
- Add agent search/filter capabilities
