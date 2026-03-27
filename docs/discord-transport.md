# Discord Transport — FlameNet Beacon

> **Bounty #320** — Hardened Discord transport with retry logic, listener mode, dry-run support, and full test coverage.

---

## Overview

`rustchain-poa/net/flame_beacon.py` is the Discord transport layer for the FlameNet Beacon system.
It watches a newline-delimited JSON event log (`poa_event_log.json`) for new beacon events and
broadcasts each one to a Discord channel via a webhook.

**New in Bounty #320:**

| Feature | Description |
|---|---|
| Retry + exponential back-off | Transient 5xx / network errors are retried automatically |
| 429 rate-limit handling | Respects `Retry-After` header (and JSON body) before retrying |
| Permanent 4xx short-circuit | 400/401/404 are logged and dropped — no wasted retries |
| Dry-run mode | Validates payload shape without sending a real HTTP request |
| Listener mode | Polls a Discord channel via Bot API for incoming beacon events |
| CLI sub-commands | `watch` (default sender) and `listen` (reader) |

---

## Quick Setup

### 1. Prerequisites

```bash
pip install requests
```

### 2. Create a Discord Webhook

1. Open your Discord server → channel settings → **Integrations → Webhooks**
2. Click **New Webhook**, name it `FlameNet Beacon`, copy the URL
3. Set the environment variable:

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/1234567890/abcdefg..."
```

### 3. Prepare your event log

Each line of `poa_event_log.json` must be a valid JSON object with at minimum:

```json
{"fingerprint": "deadbeef1234", "device": "Amiga 4000", "score": 9001, "rom": "Kickstart 3.1"}
```

A `timestamp` field is optional — the transport will inject the current UTC time if missing.

### 4. Run the watcher

```bash
# Basic watcher (sends each new event to Discord)
python3 rustchain-poa/net/flame_beacon.py watch

# With explicit options
python3 rustchain-poa/net/flame_beacon.py watch \
    --event-log /var/log/poa_event_log.json \
    --webhook-url "$DISCORD_WEBHOOK_URL" \
    --interval 10
```

**Expected output (normal operation):**

```
2026-01-01 00:00:00 [INFO] flame_beacon: [📡] FlameNet Beacon watcher active (dry_run=False) …
2026-01-01 00:00:06 [INFO] flame_beacon: [📡] Broadcasted: Amiga 4000 (score=9001)
```

**Expected output (rate limited → auto-retry):**

```
2026-01-01 00:00:12 [WARNING] flame_beacon: [⏳] Rate limited (429) — waiting 2.00s before retry 1/5
2026-01-01 00:00:14 [INFO] flame_beacon: [📡] Broadcasted: Amiga 4000 (score=9001)
```

---

## Dry-Run Mode

Use `--dry-run` to validate payloads locally without sending anything to Discord:

```bash
python3 rustchain-poa/net/flame_beacon.py watch --dry-run
```

**Expected output:**

```
2026-01-01 00:00:00 [INFO] flame_beacon: [DRY-RUN] Would send payload: {
  "content": "🔥 **FlameNet Beacon Broadcast** 🔥\n..."
}
```

This is useful for testing your event log format before going live.

---

## Listener Mode

Listener mode polls a Discord channel for **incoming** messages and processes them as beacon events.
This requires a Discord Bot token with the `Read Message History` permission.

### Setup

1. Create a Bot at <https://discord.com/developers/applications>
2. Add it to your server with `Read Messages` + `Read Message History`
3. Copy the channel snowflake ID (right-click channel → **Copy Channel ID** with Developer Mode on)

```bash
export DISCORD_BOT_TOKEN="Bot MTxxxxxxxxxxxxxxxxxxxxxxx.Gyyyyy.zzzzzzzz"
export DISCORD_CHANNEL_ID="1234567890123456789"

python3 rustchain-poa/net/flame_beacon.py listen \
    --channel-id "$DISCORD_CHANNEL_ID" \
    --bot-token  "$DISCORD_BOT_TOKEN" \
    --poll-interval 15
```

**Expected output:**

```
2026-01-01 00:00:00 [INFO] flame_beacon: [👂] FlameNet listener active — polling channel 1234... every 15.0s …
2026-01-01 00:00:15 [INFO] flame_beacon: [📨] [2026-01-01T00:00:10] FlameBot: 🔥 FlameNet Beacon ...
```

---

## Environment Variables

All configuration can be set via environment variables:

| Variable | Default | Description |
|---|---|---|
| `DISCORD_WEBHOOK_URL` | `https://discord.com/api/webhooks/your_webhook_here` | Webhook URL for outbound sends |
| `DISCORD_BOT_TOKEN` | _(empty)_ | Bot token for listener mode |
| `DISCORD_CHANNEL_ID` | _(empty)_ | Channel snowflake ID for listener mode |
| `FLAME_EVENT_LOG` | `poa_event_log.json` | Path to event log file |
| `FLAME_HISTORY_FILE` | `flame_history.json` | Path to rolling send history |
| `FLAME_MAX_RETRIES` | `5` | Max send attempts before giving up |
| `FLAME_RETRY_BASE_DELAY` | `1.0` | Base back-off delay in seconds |
| `FLAME_RETRY_MAX_DELAY` | `60.0` | Maximum back-off cap in seconds |
| `FLAME_LISTENER_POLL` | `15.0` | Listener poll interval in seconds |
| `FLAME_WATCHER_INTERVAL` | `6.0` | Watcher file-scan interval in seconds |

---

## Retry / Back-off Behaviour

| HTTP Status | Behaviour |
|---|---|
| **204** | ✅ Success |
| **429** | Waits for `Retry-After` (header or JSON body), then retries |
| **400 / 401 / 403 / 404** | ❌ Permanent error — logged and dropped (no retry) |
| **5xx** | Exponential back-off retry up to `FLAME_MAX_RETRIES` |
| Network error | Exponential back-off retry up to `FLAME_MAX_RETRIES` |

Back-off formula: `min(base × 2^attempt, max_delay)` — defaults give delays of 1s, 2s, 4s, 8s, 16s.

---

## Running the Tests

```bash
python -m pytest tests/test_discord_transport.py -v
```

**Expected output:**

```
tests/test_discord_transport.py::TestBuildWebhookPayload::test_valid_entry_returns_content_key PASSED
tests/test_discord_transport.py::TestSendToDiscordSuccess::test_returns_true_on_204 PASSED
tests/test_discord_transport.py::TestSendToDiscordDryRun::test_dry_run_does_not_post PASSED
tests/test_discord_transport.py::TestSendToDiscord429::test_retries_after_429_with_retry_after_header PASSED
tests/test_discord_transport.py::TestSendToDiscord429::test_respects_retry_after_in_json_body PASSED
tests/test_discord_transport.py::TestSendToDiscord429::test_exhausts_retries_on_persistent_429 PASSED
tests/test_discord_transport.py::TestSendToDiscord4xx::test_400_does_not_retry PASSED
tests/test_discord_transport.py::TestSendToDiscord5xx::test_500_retries_and_succeeds PASSED
tests/test_discord_transport.py::TestListenerMode::test_fetch_returns_messages_reversed PASSED
... (30 tests total)
============================== 30 passed in 0.14s ==============================
```

---

## Troubleshooting

### `[❌] Discord rejected payload (401)` — Unauthorized
- Check your `DISCORD_WEBHOOK_URL` — it must be a valid, un-revoked webhook URL
- For listener mode, check `DISCORD_BOT_TOKEN` starts with `Bot ` (including the space)

### `[⚠️] Event log not found`
- Verify `FLAME_EVENT_LOG` points to the correct path
- Ensure the miner/PoA process is writing to that file

### `[❌] Discord rejected payload (400) — Cannot send empty message`
- Your event log entry is missing required fields: `device`, `score`, `rom`, `fingerprint`
- Run with `--dry-run` to inspect the payload before sending

### Rate limits keep recurring
- Reduce the watcher interval: `--interval 30` or `FLAME_WATCHER_INTERVAL=30`
- Discord webhooks allow ~30 requests/minute per webhook URL

### Listener mode: no messages appearing
- Ensure the bot has **Read Message History** permission on the target channel
- Verify `DISCORD_CHANNEL_ID` is the channel snowflake (not the guild/server ID)

---

## API Reference

```python
from rustchain_poa.net.flame_beacon import (
    build_webhook_payload,  # Build & validate payload dict from a beacon entry
    send_to_discord,        # Send with retries; returns bool
    watch_beacon,           # Main watcher loop (sender)
    listen_beacon,          # Main listener loop (reader)
    _fetch_channel_messages,# Low-level poll helper
)
```

### `send_to_discord(entry, webhook_url, dry_run, max_retries) → bool`

```python
ok = send_to_discord(
    entry={
        "fingerprint": "abc123",
        "device": "Amiga 4000",
        "score": 9001,
        "rom": "Kickstart 3.1",
    },
    webhook_url="https://discord.com/api/webhooks/...",
    dry_run=False,
    max_retries=5,
)
```

### `listen_beacon(channel_id, bot_token, poll_interval, event_callback)`

```python
def my_handler(msg):
    print(f"Received: {msg['content']}")

listen_beacon(
    channel_id="1234567890",
    bot_token="Bot MTxx...",
    poll_interval=15.0,
    event_callback=my_handler,
)
```
