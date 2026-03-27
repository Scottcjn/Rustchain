# flame_beacon.py
# FlameNet Beacon Discord Transport — hardened with retry/backoff, listener mode, dry-run
# Bounty #320: https://github.com/Scottcjn/rustchain-bounties/issues/320

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("flame_beacon")

# ---------------------------------------------------------------------------
# Configuration (override via environment variables)
# ---------------------------------------------------------------------------
EVENT_LOG_FILE: str = os.environ.get("FLAME_EVENT_LOG", "poa_event_log.json")
DISCORD_WEBHOOK_URL: str = os.environ.get(
    "DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/your_webhook_here"
)
DISCORD_BOT_TOKEN: str = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_ID: str = os.environ.get("DISCORD_CHANNEL_ID", "")
JSON_HISTORY_FILE: str = os.environ.get("FLAME_HISTORY_FILE", "flame_history.json")

# Retry / back-off knobs
MAX_RETRIES: int = int(os.environ.get("FLAME_MAX_RETRIES", "5"))
RETRY_BASE_DELAY: float = float(os.environ.get("FLAME_RETRY_BASE_DELAY", "1.0"))  # seconds
RETRY_MAX_DELAY: float = float(os.environ.get("FLAME_RETRY_MAX_DELAY", "60.0"))  # seconds

# Listener poll interval (seconds)
LISTENER_POLL_INTERVAL: float = float(os.environ.get("FLAME_LISTENER_POLL", "15.0"))

# Watcher sleep between file scans (seconds)
WATCHER_INTERVAL: float = float(os.environ.get("FLAME_WATCHER_INTERVAL", "6.0"))


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------

def build_webhook_payload(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the Discord webhook JSON payload from a beacon entry.

    Returns a dict ready to be sent as ``json=payload`` to the webhook URL.
    Raises ``ValueError`` if required fields are missing.
    """
    required = {"device", "score", "rom", "fingerprint"}
    missing = required - entry.keys()
    if missing:
        raise ValueError(f"Beacon entry missing required fields: {missing}")

    fingerprint_short = str(entry["fingerprint"])[:12]
    timestamp = entry.get("timestamp", datetime.now(timezone.utc).isoformat())

    content = (
        f"🔥 **FlameNet Beacon Broadcast** 🔥\n"
        f"[🕰️] `{timestamp}`\n"
        f"[💾] **Device**: {entry['device']}\n"
        f"[⚙️] **Score**: {entry['score']}\n"
        f"[📼] **ROM**: {entry['rom']}\n"
        f"[🔑] **ID**: `{fingerprint_short}...`"
    )

    return {"content": content}


# ---------------------------------------------------------------------------
# Retry / back-off send
# ---------------------------------------------------------------------------

def _backoff_delay(attempt: int) -> float:
    """Exponential backoff capped at RETRY_MAX_DELAY."""
    delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
    return delay


def send_to_discord(
    entry: Dict[str, Any],
    webhook_url: str = DISCORD_WEBHOOK_URL,
    dry_run: bool = False,
    max_retries: int = MAX_RETRIES,
) -> bool:
    """
    Send a beacon entry to a Discord webhook with exponential back-off retry.

    Handles:
    - 204 No Content  → success
    - 429 Too Many Requests → honour ``Retry-After`` header, then retry
    - 4xx (not 429)   → log error, do NOT retry (permanent client error)
    - 5xx             → exponential back-off retry
    - Network errors  → exponential back-off retry

    Parameters
    ----------
    entry : dict
        Beacon event entry to broadcast.
    webhook_url : str
        Discord webhook URL.
    dry_run : bool
        When True, build and validate the payload but do not send it.
    max_retries : int
        Maximum number of send attempts.

    Returns
    -------
    bool
        True if the message was delivered (or dry-run succeeded), False otherwise.
    """
    try:
        payload = build_webhook_payload(entry)
    except ValueError as exc:
        logger.error("Invalid beacon entry — skipping send: %s", exc)
        return False

    if dry_run:
        logger.info("[DRY-RUN] Would send payload: %s", json.dumps(payload, indent=2))
        return True

    for attempt in range(max_retries):
        try:
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )
        except requests.exceptions.RequestException as exc:
            delay = _backoff_delay(attempt)
            logger.warning(
                "Network error on attempt %d/%d: %s — retrying in %.1fs",
                attempt + 1, max_retries, exc, delay,
            )
            time.sleep(delay)
            continue

        status = response.status_code

        # Success
        if status == 204:
            logger.info(
                "[📡] Broadcasted: %s (score=%s)", entry.get("device"), entry.get("score")
            )
            return True

        # Rate limited
        if status == 429:
            retry_after = float(response.headers.get("Retry-After", _backoff_delay(attempt)))
            try:
                body = response.json()
                retry_after = float(body.get("retry_after", retry_after))
            except Exception:
                pass
            logger.warning(
                "[⏳] Rate limited (429) — waiting %.2fs before retry %d/%d",
                retry_after, attempt + 1, max_retries,
            )
            time.sleep(retry_after)
            continue

        # Permanent client errors (4xx != 429)
        if 400 <= status < 500:
            try:
                err_body = response.json()
            except Exception:
                err_body = response.text
            logger.error(
                "[❌] Discord rejected payload (%d) — not retrying. Body: %s",
                status, err_body,
            )
            return False

        # Server errors (5xx)
        if status >= 500:
            delay = _backoff_delay(attempt)
            logger.warning(
                "[⚠️] Discord server error (%d) on attempt %d/%d — retrying in %.1fs",
                status, attempt + 1, max_retries, delay,
            )
            time.sleep(delay)
            continue

        # Unexpected status
        logger.error("[❌] Unexpected Discord response (%d): %s", status, response.text)
        return False

    logger.error("[❌] All %d send attempts exhausted for entry: %s", max_retries, entry.get("fingerprint"))
    return False


# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------

def update_history(entry: Dict[str, Any], history_file: str = JSON_HISTORY_FILE) -> None:
    """Append an entry to the rolling JSON history file (max 500 entries)."""
    try:
        history: List[Dict[str, Any]] = []
        path = Path(history_file)
        if path.exists():
            with open(path, "r") as fh:
                history = json.load(fh)
        history.append(entry)
        with open(path, "w") as fh:
            json.dump(history[-500:], fh, indent=2)
    except Exception as exc:
        logger.warning("[⚠️] Failed to update history: %s", exc)


# ---------------------------------------------------------------------------
# Event log reader
# ---------------------------------------------------------------------------

def load_events(path: str = EVENT_LOG_FILE) -> List[Dict[str, Any]]:
    """Load newline-delimited JSON events from *path*."""
    try:
        with open(path, "r") as fh:
            return [json.loads(line.strip()) for line in fh if line.strip()]
    except FileNotFoundError:
        logger.warning("[⚠️] Event log not found: %s", path)
        return []
    except Exception as exc:
        logger.error("[❌] Error loading events: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Watcher (sender) mode
# ---------------------------------------------------------------------------

def watch_beacon(
    event_log: str = EVENT_LOG_FILE,
    webhook_url: str = DISCORD_WEBHOOK_URL,
    dry_run: bool = False,
    interval: float = WATCHER_INTERVAL,
) -> None:
    """
    Watch *event_log* for new beacon events and broadcast each to Discord.

    Runs until interrupted (KeyboardInterrupt / SIGTERM).
    """
    logger.info("[📡] FlameNet Beacon watcher active (dry_run=%s) …", dry_run)
    seen: set = set()

    while True:
        entries = load_events(event_log)
        for entry in entries:
            entry_id = entry.get("fingerprint")
            if not entry_id or entry_id in seen:
                continue
            seen.add(entry_id)
            if "timestamp" not in entry:
                entry["timestamp"] = datetime.now(timezone.utc).isoformat()
            ok = send_to_discord(entry, webhook_url=webhook_url, dry_run=dry_run)
            if ok and not dry_run:
                update_history(entry)
        time.sleep(interval)


# ---------------------------------------------------------------------------
# Listener (reader / poll) mode
# ---------------------------------------------------------------------------

def _fetch_channel_messages(
    channel_id: str,
    bot_token: str,
    limit: int = 50,
    after: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Poll a Discord channel for recent messages via the Bot API.

    Parameters
    ----------
    channel_id : str
        Discord channel snowflake ID.
    bot_token : str
        Discord bot token (``Bot <token>``).
    limit : int
        Number of messages to retrieve (1–100).
    after : str, optional
        Snowflake ID — only retrieve messages after this ID.

    Returns
    -------
    list[dict]
        Parsed message objects, oldest-first.
    """
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {bot_token}"}
    params: Dict[str, Any] = {"limit": min(max(1, limit), 100)}
    if after:
        params["after"] = after

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
    except requests.exceptions.RequestException as exc:
        logger.warning("[⚠️] Listener fetch error: %s", exc)
        return []

    if resp.status_code == 200:
        messages = resp.json()
        # API returns newest-first; reverse to chronological order
        return list(reversed(messages))

    if resp.status_code == 429:
        retry_after = float(resp.headers.get("Retry-After", 1.0))
        logger.warning("[⏳] Listener rate-limited — sleeping %.2fs", retry_after)
        time.sleep(retry_after)
        return []

    logger.error("[❌] Listener fetch failed (%d): %s", resp.status_code, resp.text)
    return []


def listen_beacon(
    channel_id: str = DISCORD_CHANNEL_ID,
    bot_token: str = DISCORD_BOT_TOKEN,
    poll_interval: float = LISTENER_POLL_INTERVAL,
    event_callback=None,
) -> None:
    """
    Lightweight listener (poll/read) mode for the Discord transport.

    Polls *channel_id* for new messages and emits each as a beacon event via
    *event_callback(message_dict)*.  If no callback is provided, messages are
    logged to stdout.

    Parameters
    ----------
    channel_id : str
        Discord channel to monitor.
    bot_token : str
        Discord bot token.
    poll_interval : float
        Seconds between poll cycles.
    event_callback : callable, optional
        Called with each new Discord message dict.
    """
    if not channel_id or not bot_token:
        logger.error(
            "[❌] Listener mode requires DISCORD_CHANNEL_ID and DISCORD_BOT_TOKEN env vars."
        )
        return

    logger.info(
        "[👂] FlameNet listener active — polling channel %s every %.1fs …",
        channel_id, poll_interval,
    )

    last_id: Optional[str] = None

    while True:
        messages = _fetch_channel_messages(channel_id, bot_token, after=last_id)
        for msg in messages:
            last_id = msg.get("id", last_id)
            if event_callback:
                try:
                    event_callback(msg)
                except Exception as exc:
                    logger.warning("[⚠️] Event callback raised: %s", exc)
            else:
                logger.info(
                    "[📨] [%s] %s: %s",
                    msg.get("timestamp", ""),
                    msg.get("author", {}).get("username", "?"),
                    msg.get("content", "")[:120],
                )
        time.sleep(poll_interval)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(
        description="FlameNet Beacon Discord Transport",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    # watcher sub-command
    watch_p = sub.add_parser("watch", help="Watch event log and send to Discord (default)")
    watch_p.add_argument("--event-log", default=EVENT_LOG_FILE, help="Path to event log file")
    watch_p.add_argument("--webhook-url", default=DISCORD_WEBHOOK_URL, help="Discord webhook URL")
    watch_p.add_argument("--dry-run", action="store_true", help="Validate payloads without sending")
    watch_p.add_argument("--interval", type=float, default=WATCHER_INTERVAL, help="Scan interval (s)")

    # listener sub-command
    listen_p = sub.add_parser("listen", help="Poll Discord channel for incoming beacon events")
    listen_p.add_argument("--channel-id", default=DISCORD_CHANNEL_ID, help="Discord channel ID")
    listen_p.add_argument("--bot-token", default=DISCORD_BOT_TOKEN, help="Discord bot token")
    listen_p.add_argument("--poll-interval", type=float, default=LISTENER_POLL_INTERVAL, help="Poll interval (s)")

    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.mode == "watch":
        watch_beacon(
            event_log=args.event_log,
            webhook_url=args.webhook_url,
            dry_run=args.dry_run,
            interval=args.interval,
        )
    elif args.mode == "listen":
        listen_beacon(
            channel_id=args.channel_id,
            bot_token=args.bot_token,
            poll_interval=args.poll_interval,
        )
