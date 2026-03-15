# RustChain Webhook Notification System

Real-time webhook notifications for RustChain network events.

## Overview

The webhook system polls the RustChain node API, detects state changes, and dispatches HTTP POST notifications to registered subscriber URLs. Delivery failures are retried with exponential backoff.

## Supported Events

| Event | Trigger |
|---|---|
| `new_block` | Chain tip advances to a new slot |
| `new_epoch` | Epoch number increments |
| `miner_joined` | A new miner appears in the active attested set |
| `miner_left` | A previously-active miner drops out |
| `large_tx` | A wallet balance changes by more than the configured threshold |

## Quick Start

### 1. Start the dispatcher

```bash
python webhook_server.py --node http://localhost:5000 --port 9800
```

### 2. Start the example receiver

```bash
python webhook_client.py --port 9801
```

### 3. Register the receiver

```bash
curl -X POST http://localhost:9800/webhooks/subscribe \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://localhost:9801/hook",
    "events": ["new_block", "miner_joined", "miner_left"]
  }'
```

## Dispatcher API

### Subscribe

```
POST /webhooks/subscribe
```

```json
{
  "url": "https://example.com/my-webhook",
  "events": ["new_block", "new_epoch"],
  "secret": "optional-shared-secret",
  "id": "optional-custom-id"
}
```

- `url` (required) — Endpoint that will receive POST payloads
- `events` (optional) — Array of event types to subscribe to. Defaults to all events.
- `secret` (optional) — Shared secret for HMAC-SHA256 payload signing
- `id` (optional) — Custom subscriber ID. Auto-generated from URL hash if omitted.

### Unsubscribe

```
POST /webhooks/unsubscribe
```

```json
{
  "id": "subscriber-id"
}
```

### List Subscribers

```
GET /webhooks
```

## Webhook Payload Format

Every webhook POST contains:

```json
{
  "event": "new_block",
  "timestamp": 1710000000.123,
  "data": {
    "slot": 42,
    "previous_slot": 41,
    "miner": "abc123...",
    "tip_age": 5
  }
}
```

### Headers

| Header | Description |
|---|---|
| `Content-Type` | `application/json` |
| `X-RustChain-Event` | Event type name |
| `X-RustChain-Signature` | HMAC-SHA256 hex digest (only if secret is set) |

## Signature Verification

When a shared secret is configured, every payload is signed with HMAC-SHA256. To verify in your receiver:

```python
import hmac, hashlib

def verify(payload_bytes, header_sig, secret):
    expected = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_sig)
```

## Retry Policy

Failed deliveries are retried up to 5 times with exponential backoff:

| Attempt | Wait |
|---|---|
| 1 | Immediate |
| 2 | 1s |
| 3 | 2s |
| 4 | 4s |
| 5 | 8s |

Backoff is capped at 5 minutes for safety. All delivery attempts (successes and failures) are logged to a local SQLite database.

## Configuration

### CLI Arguments

| Flag | Default | Description |
|---|---|---|
| `--node` | `http://localhost:5000` | RustChain node URL |
| `--port` | `9800` | Admin API listen port |
| `--poll-interval` | `10` | Seconds between poll cycles |
| `--large-tx-threshold` | `100.0` | RTC amount that triggers `large_tx` |
| `--db` | `webhooks.db` | SQLite database path |

### Environment Variables

| Variable | Maps to |
|---|---|
| `RUSTCHAIN_NODE` | `--node` |
| `WEBHOOK_POLL_INTERVAL` | `--poll-interval` |
| `LARGE_TX_THRESHOLD` | `--large-tx-threshold` |
| `WEBHOOK_DB` | `--db` |

## Requirements

- Python 3.10+
- `requests` library (`pip install requests`)
