# Rent-a-Relic Market API Reference

Complete API documentation for Issue #2312.

## Base URL

```
http://localhost:5000
```

## Authentication

Most endpoints require an `agent_id` in the request body. No additional authentication is required for the MVP.

---

## Core Endpoints

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "ok": true,
  "service": "relic-market",
  "version": "1.0.0",
  "timestamp": "2026-03-22T12:00:00Z",
  "machines_registered": 5,
  "active_reservations": 3
}
```

---

### List Available Machines

```http
GET /relic/available?available_only=true
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `available_only` | boolean | `true` | Filter to available machines only |

**Response:**
```json
{
  "machines": [
    {
      "machine_id": "vm-001",
      "name": "POWER8 Beast",
      "architecture": "ppc64",
      "cpu_model": "IBM POWER8",
      "cpu_speed_ghz": 4.0,
      "ram_gb": 512,
      "storage_gb": 2000,
      "gpu_model": "NVIDIA Tesla K80",
      "os": "Ubuntu 20.04 PPC64",
      "year": 2013,
      "manufacturer": "IBM",
      "description": "High-memory POWER8 system",
      "photo_urls": ["/static/machines/power8-front.jpg"],
      "ssh_port": 22001,
      "api_port": 50001,
      "uptime_hours": 8760,
      "total_reservations": 15,
      "is_available": true,
      "hourly_rate_rtc": 50.0,
      "location": "RustChain Data Center",
      "capabilities": ["llm-inference", "batch-processing"]
    }
  ],
  "count": 5,
  "timestamp": "2026-03-22T12:00:00Z"
}
```

---

### Get Machine Details

```http
GET /relic/<machine_id>
```

**Response:**
```json
{
  "machine": {
    "machine_id": "vm-001",
    "name": "POWER8 Beast",
    ...
  },
  "public_key": "a1b2c3d4e5f6..."
}
```

---

### Reserve Machine

```http
POST /relic/reserve
```

**Request Body:**
```json
{
  "machine_id": "vm-001",
  "agent_id": "my-agent-id",
  "duration_hours": 1,
  "payment_rtc": 50.0
}
```

**Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `machine_id` | string | Yes | Machine to reserve |
| `agent_id` | string | Yes | Agent identifier |
| `duration_hours` | integer | Yes | 1, 4, or 24 |
| `payment_rtc` | number | Yes | Payment amount |

**Response (201 Created):**
```json
{
  "ok": true,
  "reservation": {
    "reservation_id": "res-abc123",
    "machine_id": "vm-001",
    "agent_id": "my-agent-id",
    "start_time": 1711108800.0,
    "end_time": 1711112400.0,
    "duration_hours": 1,
    "total_cost_rtc": 50.0,
    "status": "confirmed",
    "escrow_tx_hash": "0x1234abcd...",
    "ssh_credentials": {
      "username": "agent-my-agent",
      "password": "randompassword123",
      "port": 22001,
      "host": "vm-001.relic.rustchain.org"
    },
    "api_key": "randomapikey456",
    "created_at": 1711108800.0
  },
  "message": "Reservation confirmed. Access credentials provided."
}
```

---

### Get Reservation

```http
GET /relic/reservation/<reservation_id>
```

**Response:**
```json
{
  "reservation": {
    "reservation_id": "res-abc123",
    "machine_id": "vm-001",
    "agent_id": "my-agent-id",
    "status": "confirmed",
    ...
  }
}
```

---

### Start Session

```http
POST /relic/reservation/<reservation_id>/start
```

**Response:**
```json
{
  "ok": true,
  "status": "active",
  "access": {
    "ssh": {
      "username": "agent-my-agent",
      "password": "randompassword123",
      "port": 22001,
      "host": "vm-001.relic.rustchain.org"
    },
    "api_key": "randomapikey456"
  },
  "expires_at": 1711112400.0
}
```

---

### Complete Session

```http
POST /relic/reservation/<reservation_id>/complete
```

**Request Body:**
```json
{
  "compute_hash": "sha256_of_output",
  "hardware_attestation": {
    "cpu_type": "POWER8",
    "verified": true,
    "timestamp": 1711108800
  }
}
```

**Response:**
```json
{
  "ok": true,
  "receipt": {
    "receipt_id": "receipt-xyz789",
    "session_id": "res-abc123",
    "machine_passport_id": "passport-power8-001",
    "machine_id": "vm-001",
    "agent_id": "my-agent-id",
    "session_start": 1711108800.0,
    "session_end": 1711112400.0,
    "duration_seconds": 3600,
    "compute_hash": "abc123...",
    "hardware_attestation": {...},
    "signature": "ed25519_signature_hex",
    "signed_at": 1711112400.0,
    "signature_algorithm": "Ed25519"
  },
  "message": "Session completed. Provenance receipt generated."
}
```

---

### Get Provenance Receipt

```http
GET /relic/receipt/<session_id>
```

**Response:**
```json
{
  "receipt": {
    "receipt_id": "receipt-xyz789",
    "session_id": "res-abc123",
    "machine_passport_id": "passport-power8-001",
    "machine_id": "vm-001",
    "agent_id": "my-agent-id",
    "session_start": 1711108800.0,
    "session_end": 1711112400.0,
    "duration_seconds": 3600,
    "compute_hash": "abc123...",
    "hardware_attestation": {...},
    "signature": "ed25519_signature_hex",
    "signed_at": 1711112400.0,
    "signature_algorithm": "Ed25519"
  },
  "signature_valid": true
}
```

---

### Get Leaderboard

```http
GET /relic/leaderboard?limit=10
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | `10` | Number of entries |

**Response:**
```json
{
  "leaderboard": [
    {
      "machine_id": "vm-001",
      "name": "POWER8 Beast",
      "architecture": "ppc64",
      "total_reservations": 42,
      "hourly_rate_rtc": 50.0
    },
    {
      "machine_id": "vm-002",
      "name": "G5 Tower",
      "architecture": "ppc64",
      "total_reservations": 38,
      "hourly_rate_rtc": 15.0
    }
  ],
  "timestamp": "2026-03-22T12:00:00Z"
}
```

---

### Get Agent Reservations

```http
GET /relic/agent/<agent_id>/reservations
```

**Response:**
```json
{
  "agent_id": "my-agent-id",
  "reservations": [
    {
      "reservation_id": "res-abc123",
      "machine_id": "vm-001",
      "status": "completed",
      "duration_hours": 1,
      "total_cost_rtc": 50.0,
      ...
    }
  ],
  "count": 3
}
```

---

## MCP Endpoints

### Get MCP Manifest

```http
GET /mcp/manifest
```

**Response:**
```json
{
  "mcpVersion": "1.0.0",
  "name": "rustchain-relic-market",
  "version": "1.0.0",
  "description": "Rent-a-Relic Market - Book authenticated vintage compute",
  "tools": {
    "list_machines": {
      "description": "List available vintage machines for rent",
      "inputSchema": {...}
    },
    "reserve_machine": {...},
    ...
  }
}
```

---

### Call MCP Tool

```http
POST /mcp/tool
```

**Request Body:**
```json
{
  "tool": "list_machines",
  "arguments": {
    "available_only": true
  }
}
```

**Response:**
```json
{
  "machines": [...],
  "count": 5
}
```

**Available Tools:**
- `list_machines` - List available machines
- `reserve_machine` - Reserve a machine
- `get_reservation` - Get reservation details
- `start_session` - Start reserved session
- `complete_session` - Complete and get receipt
- `get_receipt` - Get provenance receipt

---

## Beacon Endpoints

### Send Beacon Message

```http
POST /beacon/message
```

**Request Body:**
```json
{
  "type": "RESERVE",
  "payload": {
    "machine_id": "vm-001",
    "agent_id": "my-agent-id",
    "duration_hours": 1,
    "payment_rtc": 50.0
  }
}
```

**Message Types:**
- `RESERVE` - Reserve machine
- `CANCEL` - Cancel reservation
- `START` - Start session
- `COMPLETE` - Complete session
- `STATUS` - Query status
- `RECEIPT` - Get receipt

**Response:**
```json
{
  "status": "confirmed",
  "reservation_id": "res-abc123",
  "machine_id": "vm-001",
  "duration_hours": 1,
  "total_cost_rtc": 50.0,
  "escrow_tx": "0x1234..."
}
```

---

## BoTTube Integration

### Get BoTTube Badge

```http
GET /bottube/badge/<session_id>
```

**Response:**
```json
{
  "badge_type": "relic_rendered",
  "session_id": "res-abc123",
  "machine_name": "G5 Tower",
  "machine_architecture": "ppc64",
  "receipt_id": "receipt-xyz789",
  "render_date": "2026-03-22T12:00:00Z",
  "verification_hash": "abc123...",
  "badge_url": "/static/badges/relic-res-abc123.svg"
}
```

---

## Error Responses

### 400 Bad Request

```json
{
  "error": "Missing required fields",
  "required": ["machine_id", "agent_id", "duration_hours", "payment_rtc"]
}
```

### 404 Not Found

```json
{
  "error": "Machine not found"
}
```

### 500 Internal Server Error

```json
{
  "error": "Failed to sign receipt"
}
```

---

## Rate Limiting

No rate limiting in MVP. Production deployment should implement:
- 100 requests/minute per agent
- 10 reservations/minute per agent

---

## Versioning

API version is included in health check response. Current version: `1.0.0`
