# RIP-0305 Bridge API Documentation

## Overview

The Bridge API provides REST endpoints for managing cross-chain transfers between RustChain and external chains (Solana, Ergo, Base). This implementation follows RIP-0305 Track C specifications.

## Base URL

```
Production: https://rustchain.org
Development: http://localhost:5000
```

## Authentication

### Admin Endpoints
Most bridge management endpoints require an admin key:
```
X-Admin-Key: <your-admin-key>
```

### API Callbacks
Bridge service callbacks use API key authentication:
```
X-API-Key: <bridge-api-key>
```

## Endpoints

### 1. Initiate Bridge Transfer

Create a new bridge transfer (deposit or withdraw).

**Endpoint:** `POST /api/bridge/initiate`

**Request:**
```json
{
    "direction": "deposit",
    "source_chain": "rustchain",
    "dest_chain": "solana",
    "source_address": "RTC_miner123",
    "dest_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
    "amount_rtc": 100.0,
    "memo": "Optional memo (max 256 chars)"
}
```

**Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| direction | string | Yes | `deposit` (RTC→external) or `withdraw` (external→RTC) |
| source_chain | string | Yes | Source chain: `rustchain`, `solana`, `ergo`, `base` |
| dest_chain | string | Yes | Destination chain (must differ from source) |
| source_address | string | Yes | Source wallet address |
| dest_address | string | Yes | Destination wallet address |
| amount_rtc | number | Yes | Amount in RTC (minimum: 1.0) |
| memo | string | No | Optional memo (max 256 characters) |

**Response (200 OK):**
```json
{
    "ok": true,
    "bridge_transfer_id": 12345,
    "tx_hash": "abc123def456...",
    "status": "pending",
    "lock_epoch": 85,
    "unlock_at": 1709942400,
    "estimated_completion": "2026-03-10T12:00:00Z",
    "direction": "deposit",
    "source_chain": "rustchain",
    "dest_chain": "solana",
    "amount_rtc": 100.0
}
```

**Error Responses:**
```json
// 400 Bad Request - Insufficient balance
{
    "error": "Insufficient available balance",
    "available_rtc": 50.0,
    "pending_debits_rtc": 20.0,
    "requested_rtc": 100.0
}

// 400 Bad Request - Invalid address
{
    "error": "Invalid solana address: length must be 32-44 characters"
}
```

---

### 2. Query Bridge Status

Get status of a specific bridge transfer.

**Endpoint:** `GET /api/bridge/status/<tx_hash>`

Or with query parameter:
```
GET /api/bridge/status?tx_hash=abc123...
GET /api/bridge/status?id=12345
```

**Response (200 OK):**
```json
{
    "ok": true,
    "transfer": {
        "id": 12345,
        "direction": "deposit",
        "source_chain": "rustchain",
        "dest_chain": "solana",
        "source_address": "RTC_miner123",
        "dest_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
        "amount_rtc": 100.0,
        "bridge_type": "bottube",
        "external_tx_hash": "5xKjPqR...",
        "external_confirmations": 8,
        "required_confirmations": 12,
        "status": "confirming",
        "lock_epoch": 85,
        "created_at": 1709856000,
        "updated_at": 1709859600,
        "expires_at": 1710460800,
        "tx_hash": "abc123def456...",
        "memo": null
    }
}
```

**Status Values:**
| Status | Description |
|--------|-------------|
| `pending` | Transfer initiated, awaiting lock |
| `locked` | Assets locked, awaiting external confirmation |
| `confirming` | External confirmations in progress |
| `completed` | Transfer completed successfully |
| `failed` | Transfer failed (see `failure_reason`) |
| `voided` | Transfer voided by admin/user |

**Error Responses:**
```json
// 404 Not Found
{
    "error": "Bridge transfer not found"
}
```

---

### 3. List Bridge Transfers

List bridge transfers with optional filters.

**Endpoint:** `GET /api/bridge/list`

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| status | string | - | Filter by status |
| source_address | string | - | Filter by source address |
| dest_address | string | - | Filter by destination address |
| direction | string | - | Filter by direction |
| limit | integer | 100 | Max results (max: 500) |

**Example:**
```
GET /api/bridge/list?status=pending&source_address=RTC_miner123&limit=50
```

**Response (200 OK):**
```json
{
    "ok": true,
    "count": 3,
    "transfers": [
        {
            "id": 12345,
            "direction": "deposit",
            "source_chain": "rustchain",
            "dest_chain": "solana",
            "source_address": "RTC_miner123",
            "dest_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
            "amount_rtc": 100.0,
            "bridge_type": "bottube",
            "external_tx_hash": "5xKjPqR...",
            "external_confirmations": 8,
            "required_confirmations": 12,
            "status": "confirming",
            "lock_epoch": 85,
            "created_at": 1709856000,
            "tx_hash": "abc123def456..."
        }
    ]
}
```

---

### 4. Void Bridge Transfer (Admin)

Void a pending bridge transfer and release associated locks.

**Endpoint:** `POST /api/bridge/void`

**Headers:**
```
X-Admin-Key: <admin-key>
```

**Request:**
```json
{
    "tx_hash": "abc123def456...",
    "reason": "user_request",
    "voided_by": "admin_john"
}
```

**Reason Values:**
| Value | Description |
|-------|-------------|
| `user_request` | User requested cancellation |
| `security_hold` | Security team flagged transfer |
| `failed_external` | External chain transfer failed |
| `admin_void` | General admin void |

**Response (200 OK):**
```json
{
    "ok": true,
    "voided_id": 12345,
    "tx_hash": "abc123def456...",
    "source_address": "RTC_miner123",
    "dest_address": "4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
    "amount_rtc": 100.0,
    "voided_by": "admin_john",
    "reason": "user_request",
    "lock_released": true
}
```

---

### 5. Update External Confirmation (Bridge Service)

Update external transaction confirmation data (called by bridge service).

**Endpoint:** `POST /api/bridge/update-external`

**Headers:**
```
X-API-Key: <bridge-api-key>
```

**Request:**
```json
{
    "tx_hash": "abc123def456...",
    "external_tx_hash": "5xKjPqR...",
    "confirmations": 8,
    "required_confirmations": 12
}
```

**Response (200 OK):**
```json
{
    "ok": true,
    "tx_hash": "abc123def456...",
    "status": "confirming",
    "external_confirmations": 8,
    "required_confirmations": 12
}
```

---

### 6. Get Miner Locks

Get lock ledger entries for a specific miner.

**Endpoint:** `GET /api/lock/miner/<miner_id>`

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| status | string | - | Filter: `locked`, `released`, `forfeited`, or `summary` |
| limit | integer | 100 | Max results |

**Example:**
```
GET /api/lock/miner/RTC_miner123?status=locked
GET /api/lock/miner/RTC_miner123?status=summary
```

**Response (200 OK) - List:**
```json
{
    "ok": true,
    "miner_id": "RTC_miner123",
    "count": 2,
    "locks": [
        {
            "id": 789,
            "amount_rtc": 50.0,
            "lock_type": "bridge_deposit",
            "status": "locked",
            "locked_at": 1709856000,
            "unlock_at": 1709942400,
            "time_until_unlock": 86400
        }
    ]
}
```

**Response (200 OK) - Summary:**
```json
{
    "miner_id": "RTC_miner123",
    "total_locked_rtc": 150.0,
    "total_locked_count": 3,
    "breakdown": {
        "bridge_deposit": {"amount_rtc": 100.0, "count": 2},
        "bridge_withdraw": {"amount_rtc": 50.0, "count": 1}
    },
    "next_unlock": {
        "unlock_at": 1709942400,
        "amount_rtc": 50.0,
        "seconds_until": 86400
    }
}
```

---

### 7. Get Pending Unlocks

Get locks ready to be released.

**Endpoint:** `GET /api/lock/pending-unlock`

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| before | integer | - | Unix timestamp filter |
| limit | integer | 100 | Max results |

**Response (200 OK):**
```json
{
    "ok": true,
    "count": 5,
    "locks": [
        {
            "id": 789,
            "miner_id": "RTC_miner123",
            "amount_rtc": 50.0,
            "lock_type": "bridge_deposit",
            "unlock_at": 1709856000,
            "expired_seconds": 3600
        }
    ]
}
```

---

### 8. Release Lock (Admin)

Manually release a lock.

**Endpoint:** `POST /api/lock/release`

**Headers:**
```
X-Admin-Key: <admin-key>
```

**Request:**
```json
{
    "lock_id": 789,
    "release_tx_hash": "optional_tx_hash"
}
```

**Response (200 OK):**
```json
{
    "ok": true,
    "lock_id": 789,
    "miner_id": "RTC_miner123",
    "amount_rtc": 50.0,
    "released_by": "admin",
    "release_tx_hash": "optional_tx_hash",
    "released_at": 1709859600
}
```

---

### 9. Forfeit Lock (Admin)

Forfeit a lock (penalty/slashing).

**Endpoint:** `POST /api/lock/forfeit`

**Headers:**
```
X-Admin-Key: <admin-key>
```

**Request:**
```json
{
    "lock_id": 789,
    "reason": "penalty"
}
```

**Response (200 OK):**
```json
{
    "ok": true,
    "lock_id": 789,
    "miner_id": "RTC_miner123",
    "amount_rtc": 50.0,
    "reason": "penalty",
    "forfeited_by": "admin",
    "forfeited_at": 1709859600,
    "note": "Forfeited assets are retained by protocol"
}
```

---

### 10. Auto-Release Expired Locks (Worker)

Automatically release locks that have passed their unlock time.

**Endpoint:** `POST /api/lock/auto-release`

**Headers:**
```
X-Worker-Key: <worker-key>
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| batch_size | integer | 100 | Max locks to release per call |

**Response (200 OK):**
```json
{
    "released_count": 10,
    "total_amount_rtc": 500.0,
    "errors": [],
    "processed_at": 1709859600
}
```

---

## Error Codes

| HTTP Code | Description |
|-----------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid payload or validation error |
| 401 | Unauthorized - Missing or invalid auth key |
| 404 | Not Found - Resource doesn't exist |
| 500 | Internal Server Error |

---

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `RC_BRIDGE_DEFAULT_CONFIRMATIONS` | 12 | Default external confirmations required |
| `RC_BRIDGE_LOCK_EXPIRY_SECONDS` | 604800 | Max lock duration (7 days) |
| `RC_BRIDGE_MIN_AMOUNT_RTC` | 1.0 | Minimum bridge amount |
| `RC_BRIDGE_API_KEY` | - | API key for bridge callbacks |

---

## Integration Example

### Python Example: Initiate Bridge Transfer

```python
import requests

BASE_URL = "https://rustchain.org"

def initiate_bridge_deposit(miner_id, dest_address, amount_rtc):
    """Initiate a bridge deposit from RustChain to Solana."""
    response = requests.post(
        f"{BASE_URL}/api/bridge/initiate",
        json={
            "direction": "deposit",
            "source_chain": "rustchain",
            "dest_chain": "solana",
            "source_address": miner_id,
            "dest_address": dest_address,
            "amount_rtc": amount_rtc
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Bridge initiated: {result['tx_hash']}")
        print(f"Status: {result['status']}")
        print(f"Estimated completion: {result['estimated_completion']}")
        return result
    else:
        print(f"Error: {response.json()}")
        return None

# Usage
result = initiate_bridge_deposit(
    miner_id="RTC_miner123",
    dest_address="4TRwNqXqXqXqXqXqXqXqXqXqXqXqXqXqXqXq",
    amount_rtc=100.0
)
```

### Python Example: Check Bridge Status

```python
def check_bridge_status(tx_hash):
    """Check status of a bridge transfer."""
    response = requests.get(f"{BASE_URL}/api/bridge/status/{tx_hash}")
    
    if response.status_code == 200:
        transfer = response.json()["transfer"]
        print(f"Status: {transfer['status']}")
        print(f"Confirmations: {transfer['external_confirmations']}/{transfer['required_confirmations']}")
        return transfer
    else:
        print(f"Error: {response.json()}")
        return None

# Usage
status = check_bridge_status("abc123def456...")
```

---

## Security Considerations

1. **Admin Key Protection**: Store admin keys securely, never expose in client code
2. **Address Validation**: Always validate destination addresses before initiating
3. **Confirmation Monitoring**: Monitor external confirmations for completion
4. **Lock Expiry**: Transfers auto-expire after 7 days if not completed
5. **Rate Limiting**: Implement rate limiting on production endpoints

---

## Related Documentation

- [RIP-0305 Specification](../rips/docs/RIP-0305-bridge-lock-ledger.md)
- [Bridge Integration Guide](../bridge/README.md)
- [Lock Ledger Architecture](../rips/docs/RIP-0305-bridge-lock-ledger.md#12-lock-ledger-table)
