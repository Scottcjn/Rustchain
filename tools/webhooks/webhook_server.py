#!/usr/bin/env python3
"""
RustChain Webhook Dispatcher

Polls RustChain node API endpoints, detects state changes, and dispatches
webhook POST notifications to registered subscriber URLs.

Supported events:
  - new_block        Header tip advances to a new slot
  - new_epoch        Epoch number increments
  - miner_joined     A miner appears that was not in the previous poll
  - miner_left       A previously-seen miner disappears from the active set
  - large_tx         A wallet transfer exceeds the configurable threshold

Usage:
  python webhook_server.py                       # interactive / config file
  python webhook_server.py --node http://host:port --port 9800
"""

import argparse
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import socket
import sqlite3
import threading
import time
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("webhook-dispatcher")

# ---------------------------------------------------------------------------
# Constants & defaults
# ---------------------------------------------------------------------------
DEFAULT_NODE_URL = os.getenv("RUSTCHAIN_NODE", "http://localhost:5000")
DEFAULT_POLL_INTERVAL = int(os.getenv("WEBHOOK_POLL_INTERVAL", "10"))
DEFAULT_LARGE_TX_THRESHOLD = float(os.getenv("LARGE_TX_THRESHOLD", "100.0"))
DEFAULT_DB_PATH = os.getenv("WEBHOOK_DB", "webhooks.db")
MAX_ADMIN_BODY_BYTES = 1024 * 1024
MAX_RETRIES = 5
INITIAL_BACKOFF = 1.0  # seconds
BACKOFF_MULTIPLIER = 2.0
MAX_BACKOFF = 300.0  # 5 minutes cap

ALL_EVENT_TYPES = frozenset([
    "new_block",
    "new_epoch",
    "miner_joined",
    "miner_left",
    "large_tx",
])

# ---------------------------------------------------------------------------
# SSRF prevention — block internal / reserved address ranges
# ---------------------------------------------------------------------------
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # IPv4 loopback
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("10.0.0.0/8"),         # RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),      # RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),     # RFC 1918
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local / cloud metadata
    ipaddress.ip_network("224.0.0.0/4"),        # IPv4 multicast
    ipaddress.ip_network("240.0.0.0/4"),        # IPv4 reserved / future use
    ipaddress.ip_network("255.255.255.255/32"), # IPv4 limited broadcast
    ipaddress.ip_network("0.0.0.0/8"),          # "This" network
    ipaddress.ip_network("100.64.0.0/10"),      # CGNAT
    ipaddress.ip_network("192.0.0.0/24"),       # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1 (documentation)
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2 (documentation)
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3 (documentation)
    ipaddress.ip_network("fc00::/7"),           # IPv6 unique-local
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
    ipaddress.ip_network("ff00::/8"),           # IPv6 multicast
]


def _is_blocked_ip(ip_str: str) -> bool:
    """Return True if *ip_str* falls within a blocked (internal/reserved) range."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparseable → block
    return any(addr in net for net in _BLOCKED_NETWORKS)


def validate_webhook_url(url: str) -> Optional[str]:
    """Validate a subscriber URL.

    Returns ``None`` on success, or an error-message string on failure.

    Checks performed:
    1. Scheme must be ``http`` or ``https``.
    2. Hostname must resolve to a **public**, non-reserved IP address
       (prevents DNS-rebinding by resolving before storage).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "url must use http or https scheme"
    if not parsed.hostname:
        return "url must contain a hostname"

    # Resolve the hostname and check every returned IP
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return "url hostname could not be resolved"

    ips = {info[4][0] for info in infos}
    if not ips:
        return "url hostname could not be resolved"

    for ip in ips:
        if _is_blocked_ip(ip):
            return f"url resolves to a blocked address ({ip})"

    return None

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Subscriber:
    id: str
    url: str
    secret: Optional[str] = None
    events: Set[str] = field(default_factory=lambda: set(ALL_EVENT_TYPES))
    active: bool = True
    created_at: float = field(default_factory=time.time)


@dataclass
class WebhookEvent:
    event_type: str
    timestamp: float
    data: Dict[str, Any]


# ---------------------------------------------------------------------------
# Persistence (SQLite)
# ---------------------------------------------------------------------------

class SubscriberStore:
    """Thread-safe subscriber storage backed by SQLite."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        with self._lock, self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    id          TEXT PRIMARY KEY,
                    url         TEXT NOT NULL,
                    secret      TEXT,
                    events      TEXT NOT NULL,
                    active      INTEGER NOT NULL DEFAULT 1,
                    created_at  REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS delivery_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    subscriber_id TEXT NOT NULL,
                    event_type  TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    status_code INTEGER,
                    attempt     INTEGER NOT NULL DEFAULT 1,
                    delivered_at REAL,
                    error       TEXT,
                    FOREIGN KEY (subscriber_id) REFERENCES subscribers(id)
                )
            """)
            conn.commit()

    # -- CRUD ---------------------------------------------------------------

    def add(self, sub: Subscriber) -> Subscriber:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO subscribers (id, url, secret, events, active, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (sub.id, sub.url, sub.secret, json.dumps(sorted(sub.events)),
                 int(sub.active), sub.created_at),
            )
            conn.commit()
        return sub

    def remove(self, sub_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM subscribers WHERE id = ?", (sub_id,))
            conn.commit()
            return cur.rowcount > 0

    def get(self, sub_id: str) -> Optional[Subscriber]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM subscribers WHERE id = ?", (sub_id,)).fetchone()
        if not row:
            return None
        return self._row_to_sub(row)

    def list_all(self) -> List[Subscriber]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM subscribers ORDER BY created_at").fetchall()
        return [self._row_to_sub(r) for r in rows]

    def list_for_event(self, event_type: str) -> List[Subscriber]:
        subs = self.list_all()
        return [s for s in subs if s.active and event_type in s.events]

    def log_delivery(self, sub_id: str, event_type: str, payload: str,
                     status_code: Optional[int], attempt: int, error: Optional[str] = None):
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO delivery_log (subscriber_id, event_type, payload, status_code, attempt, delivered_at, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sub_id, event_type, payload, status_code, attempt, time.time(), error),
            )
            conn.commit()

    @staticmethod
    def _row_to_sub(row) -> Subscriber:
        return Subscriber(
            id=row["id"],
            url=row["url"],
            secret=row["secret"],
            events=set(json.loads(row["events"])),
            active=bool(row["active"]),
            created_at=row["created_at"],
        )


# ---------------------------------------------------------------------------
# Webhook delivery with exponential backoff
# ---------------------------------------------------------------------------

def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """HMAC-SHA256 signature for webhook verification."""
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


def deliver_webhook(sub: Subscriber, event: WebhookEvent, store: SubscriberStore):
    """POST the event payload to the subscriber URL with retry + backoff."""
    validation_error = validate_webhook_url(sub.url)
    if validation_error:
        log.warning("Skipping webhook delivery to %s: %s", sub.url, validation_error)
        store.log_delivery(sub.id, event.event_type, "", None, 0, validation_error)
        return

    payload = json.dumps({
        "event": event.event_type,
        "timestamp": event.timestamp,
        "data": event.data,
    }, default=str)
    payload_bytes = payload.encode()

    headers = {
        "Content-Type": "application/json",
        "X-RustChain-Event": event.event_type,
    }
    if sub.secret:
        headers["X-RustChain-Signature"] = _sign_payload(payload_bytes, sub.secret)

    backoff = INITIAL_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                sub.url, data=payload_bytes, headers=headers, timeout=10, allow_redirects=False,
            )
            store.log_delivery(sub.id, event.event_type, payload, resp.status_code, attempt)
            if 200 <= resp.status_code < 300:
                log.info("Delivered %s to %s (attempt %d, status %d)",
                         event.event_type, sub.url, attempt, resp.status_code)
                return
            log.warning("Non-2xx from %s: %d (attempt %d/%d)",
                        sub.url, resp.status_code, attempt, MAX_RETRIES)
        except requests.RequestException as exc:
            log.warning("Delivery failed to %s: %s (attempt %d/%d)",
                        sub.url, exc, attempt, MAX_RETRIES)
            store.log_delivery(sub.id, event.event_type, payload, None, attempt, str(exc))

        if attempt < MAX_RETRIES:
            sleep_time = min(backoff, MAX_BACKOFF)
            log.info("Retrying in %.1fs ...", sleep_time)
            time.sleep(sleep_time)
            backoff *= BACKOFF_MULTIPLIER

    log.error("Exhausted retries for %s -> %s", event.event_type, sub.url)


def dispatch_event(event: WebhookEvent, store: SubscriberStore):
    """Fan-out an event to all matching subscribers (each in its own thread)."""
    subscribers = store.list_for_event(event.event_type)
    if not subscribers:
        return
    log.info("Dispatching %s to %d subscriber(s)", event.event_type, len(subscribers))
    for sub in subscribers:
        t = threading.Thread(target=deliver_webhook, args=(sub, event, store), daemon=True)
        t.start()


# ---------------------------------------------------------------------------
# RustChain state poller
# ---------------------------------------------------------------------------

class RustChainPoller:
    """Polls RustChain API endpoints and emits webhook events on state changes."""

    def __init__(self, node_url: str, store: SubscriberStore,
                 poll_interval: int = DEFAULT_POLL_INTERVAL,
                 large_tx_threshold: float = DEFAULT_LARGE_TX_THRESHOLD):
        self.node_url = node_url.rstrip("/")
        self.store = store
        self.poll_interval = poll_interval
        self.large_tx_threshold = large_tx_threshold

        # Previous-state snapshots
        self._prev_tip_slot: Optional[int] = None
        self._prev_epoch: Optional[int] = None
        self._prev_miners: Set[str] = set()
        self._prev_balances: Dict[str, float] = {}
        self._running = False

    def _get(self, path: str) -> Optional[dict]:
        try:
            resp = requests.get(f"{self.node_url}{path}", timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            log.debug("Failed to fetch %s: %s", path, exc)
            return None

    def _check_block(self):
        tip = self._get("/headers/tip")
        if not tip or tip.get("slot") is None:
            return
        slot = int(tip["slot"])
        if self._prev_tip_slot is not None and slot > self._prev_tip_slot:
            dispatch_event(WebhookEvent(
                event_type="new_block",
                timestamp=time.time(),
                data={
                    "slot": slot,
                    "previous_slot": self._prev_tip_slot,
                    "miner": tip.get("miner"),
                    "tip_age": tip.get("tip_age"),
                },
            ), self.store)
        self._prev_tip_slot = slot

    def _check_epoch(self):
        stats = self._get("/api/stats")
        if not stats:
            return
        epoch = stats.get("epoch")
        if epoch is None:
            return
        if self._prev_epoch is not None and epoch != self._prev_epoch:
            dispatch_event(WebhookEvent(
                event_type="new_epoch",
                timestamp=time.time(),
                data={
                    "epoch": epoch,
                    "previous_epoch": self._prev_epoch,
                    "total_miners": stats.get("total_miners"),
                    "total_balance": stats.get("total_balance"),
                },
            ), self.store)
        self._prev_epoch = epoch

    def _check_miners(self):
        miners_data = self._get("/api/miners")
        if miners_data is None or not isinstance(miners_data, list):
            return
        current_miners = {m["miner"] for m in miners_data if "miner" in m}

        if self._prev_miners:
            joined = current_miners - self._prev_miners
            left = self._prev_miners - current_miners

            for miner_id in joined:
                miner_info = next((m for m in miners_data if m.get("miner") == miner_id), {})
                dispatch_event(WebhookEvent(
                    event_type="miner_joined",
                    timestamp=time.time(),
                    data={
                        "miner": miner_id,
                        "hardware_type": miner_info.get("hardware_type"),
                        "device_family": miner_info.get("device_family"),
                        "device_arch": miner_info.get("device_arch"),
                    },
                ), self.store)

            for miner_id in left:
                dispatch_event(WebhookEvent(
                    event_type="miner_left",
                    timestamp=time.time(),
                    data={"miner": miner_id},
                ), self.store)

        self._prev_miners = current_miners

    def _check_large_tx(self):
        balances_data = self._get("/api/balances")
        if balances_data is None or not isinstance(balances_data, list):
            return

        current_balances: Dict[str, float] = {}
        for entry in balances_data:
            miner_id = entry.get("miner_id") or entry.get("miner")
            balance = entry.get("balance") or entry.get("amount", 0)
            if miner_id is not None:
                try:
                    current_balances[miner_id] = float(balance)
                except (ValueError, TypeError):
                    continue

        if self._prev_balances:
            for miner_id, new_bal in current_balances.items():
                old_bal = self._prev_balances.get(miner_id, 0.0)
                delta = new_bal - old_bal
                if abs(delta) >= self.large_tx_threshold:
                    dispatch_event(WebhookEvent(
                        event_type="large_tx",
                        timestamp=time.time(),
                        data={
                            "miner": miner_id,
                            "previous_balance": old_bal,
                            "new_balance": new_bal,
                            "delta": round(delta, 6),
                            "direction": "credit" if delta > 0 else "debit",
                        },
                    ), self.store)

        self._prev_balances = current_balances

    def poll_once(self):
        """Run a single polling cycle across all event detectors."""
        self._check_block()
        self._check_epoch()
        self._check_miners()
        self._check_large_tx()

    def run(self):
        """Blocking poll loop."""
        self._running = True
        log.info("Poller started (node=%s, interval=%ds, large_tx_threshold=%.2f RTC)",
                 self.node_url, self.poll_interval, self.large_tx_threshold)
        while self._running:
            try:
                self.poll_once()
            except Exception:
                log.exception("Unhandled error in poll cycle")
            time.sleep(self.poll_interval)

    def stop(self):
        self._running = False


# ---------------------------------------------------------------------------
# Management HTTP API
# ---------------------------------------------------------------------------

class WebhookAdminHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for managing webhook subscriptions."""

    store: SubscriberStore  # injected via class attribute
    # FIX(#2867 M3): API key for admin endpoints, read from env var
    ADMIN_API_KEY: str = os.environ.get("WEBHOOK_ADMIN_API_KEY", "")

    def log_message(self, fmt, *args):
        log.debug(fmt, *args)

    def _send_json(self, status: int, body: Any):
        payload = json.dumps(body, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length > MAX_ADMIN_BODY_BYTES:
            raise ValueError("request body too large")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    # FIX(#2867 M3): Authenticate admin API requests
    def _check_api_key(self) -> bool:
        if not self.ADMIN_API_KEY:
            return True  # No key configured — allow (development mode)
        provided = self.headers.get("X-Admin-API-Key", "")
        if not hmac.compare_digest(provided, self.ADMIN_API_KEY):
            self._send_json(401, {"error": "invalid or missing API key"})
            return False
        return True

    def do_GET(self):
        if not self._check_api_key():
            return
        if self.path == "/webhooks":
            subs = self.store.list_all()
            self._send_json(200, {
                "subscribers": [
                    {
                        "id": s.id, "url": s.url,
                        "events": sorted(s.events),
                        "active": s.active,
                    }
                    for s in subs
                ],
            })
        elif self.path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if not self._check_api_key():
            return
        if self.path == "/webhooks/subscribe":
            self._handle_subscribe()
        elif self.path == "/webhooks/unsubscribe":
            self._handle_unsubscribe()
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_subscribe(self):
        try:
            body = self._read_body()
        except ValueError as exc:
            status = 413 if "too large" in str(exc) else 400
            self._send_json(status, {"error": str(exc)})
            return
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
            return

        url = body.get("url")
        if not url:
            self._send_json(400, {"error": "url is required"})
            return

        error = validate_webhook_url(url)
        if error:
            self._send_json(400, {"error": error})
            return

        events_raw = body.get("events")
        if events_raw:
            events = set(events_raw) & ALL_EVENT_TYPES
            if not events:
                self._send_json(400, {
                    "error": "no valid events specified",
                    "valid_events": sorted(ALL_EVENT_TYPES),
                })
                return
        else:
            events = set(ALL_EVENT_TYPES)

        sub_id = body.get("id") or hashlib.sha256(url.encode()).hexdigest()[:12]
        secret = body.get("secret")

        sub = Subscriber(id=sub_id, url=url, secret=secret, events=events)
        self.store.add(sub)
        log.info("Subscriber registered: %s -> %s (events: %s)", sub_id, url, sorted(events))
        self._send_json(201, {
            "id": sub_id,
            "url": url,
            "events": sorted(events),
            "message": "subscribed",
        })

    def _handle_unsubscribe(self):
        try:
            body = self._read_body()
        except ValueError as exc:
            status = 413 if "too large" in str(exc) else 400
            self._send_json(status, {"error": str(exc)})
            return
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
            return

        sub_id = body.get("id")
        if not sub_id:
            self._send_json(400, {"error": "id is required"})
            return

        if self.store.remove(sub_id):
            log.info("Subscriber removed: %s", sub_id)
            self._send_json(200, {"id": sub_id, "message": "unsubscribed"})
        else:
            self._send_json(404, {"error": "subscriber not found"})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="RustChain Webhook Dispatcher")
    parser.add_argument("--node", default=DEFAULT_NODE_URL,
                        help="RustChain node base URL (default: %(default)s)")
    parser.add_argument("--port", type=int, default=9800,
                        help="Admin API listen port (default: %(default)s)")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL,
                        help="Seconds between poll cycles (default: %(default)s)")
    parser.add_argument("--large-tx-threshold", type=float, default=DEFAULT_LARGE_TX_THRESHOLD,
                        help="RTC threshold for large_tx events (default: %(default)s)")
    parser.add_argument("--db", default=DEFAULT_DB_PATH,
                        help="SQLite database path (default: %(default)s)")
    args = parser.parse_args()

    store = SubscriberStore(db_path=args.db)

    # Start the poller in a background thread
    poller = RustChainPoller(
        node_url=args.node,
        store=store,
        poll_interval=args.poll_interval,
        large_tx_threshold=args.large_tx_threshold,
    )
    poller_thread = threading.Thread(target=poller.run, daemon=True)
    poller_thread.start()

    # Start the admin HTTP server
    WebhookAdminHandler.store = store
    server = HTTPServer(("0.0.0.0", args.port), WebhookAdminHandler)
    log.info("Admin API listening on http://0.0.0.0:%d", args.port)
    log.info("  POST /webhooks/subscribe   - Register a webhook")
    log.info("  POST /webhooks/unsubscribe - Remove a webhook")
    log.info("  GET  /webhooks             - List subscriptions")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down ...")
        poller.stop()
        server.shutdown()


if __name__ == "__main__":
    main()
