#!/usr/bin/env python3
"""
RustChain Agent Miner RPC Server
=================================

Headless JSON-RPC / REST API for autonomous AI agents to programmatically
control RustChain mining operations without human interaction.

Endpoints:
    POST /api/mining/start       - Start mining with specified wallet/threads
    POST /api/mining/stop        - Stop the active mining loop
    GET  /api/mining/status      - Machine-readable mining status (JSON)
    POST /api/mining/threads     - Adjust thread/intensity count
    GET  /health                 - Health check for orchestrators
    POST /api/webhooks/register  - Register webhook URL for event callbacks
    GET  /api/webhooks           - List registered webhooks
    DELETE /api/webhooks         - Remove a webhook

Usage:
    python3 agent_miner_rpc.py --port 8332
    python3 agent_miner_rpc.py --port 8332 --wallet <RTC_WALLET>

Agent Example:
    import requests
    r = requests.post("http://localhost:8332/api/mining/start",
                      json={"wallet": "YOUR_WALLET", "threads": 4})
    print(r.json())  # {"ok": true, "message": "Mining started"}

    s = requests.get("http://localhost:8332/api/mining/status")
    print(s.json())  # {"active": true, "cycle": 3, "uptime_s": 180, ...}

Author: RustChain Contributors
Ref: Issue #535 — Autonomous Agent Miner Node Support
"""

import argparse
import hashlib
import ipaddress
import json
import logging
import os
import platform
import re
import secrets
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Optional dependency: Flask (used by node/rustchain_dashboard.py already)
# ---------------------------------------------------------------------------
try:
    from flask import Flask, jsonify, request as flask_request
except ImportError:
    print("ERROR: Flask is required. Install: pip install flask")
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None  # Webhooks will be disabled

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("agent_miner_rpc")

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
# The API token is loaded from --auth-token CLI arg, or AGENT_MINER_AUTH_TOKEN
# environment variable.  When set, all mutating endpoints require:
#   Authorization: Bearer <token>
# Read-only endpoints (/health, GET /api/mining/status) are available without
# auth but return redacted data (wallet/balance fields omitted).
# ---------------------------------------------------------------------------

_auth_token = None  # Set at boot from CLI/env


def _is_authenticated():
    """Check if the current request has a valid bearer token."""
    if _auth_token is None:
        return True  # Auth not configured — all requests pass
    auth_header = flask_request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return secrets.compare_digest(auth_header[7:], _auth_token)
    return False


def require_auth(f):
    """Decorator: reject requests without a valid bearer token (401/403)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if _auth_token is None:
            return f(*args, **kwargs)
        if not _is_authenticated():
            return jsonify({
                "ok": False,
                "error": "Authentication required. Provide: Authorization: Bearer <token>",
            }), 401
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Webhook SSRF Protection
# ---------------------------------------------------------------------------

def _is_safe_webhook_url(url):
    """Reject webhook URLs that target internal/link-local/RFC1918 hosts.

    Returns (is_safe: bool, reason: str).
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL"

    # Only allow http and https schemes
    if parsed.scheme not in ("http", "https"):
        return False, "Only http:// and https:// webhook URLs are allowed"

    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname in webhook URL"

    # Block known dangerous hostnames
    blocked_hostnames = {
        "localhost", "metadata.google.internal",
        "metadata", "instance-data",
    }
    if hostname.lower() in blocked_hostnames:
        return False, "Blocked hostname: {}".format(hostname)

    # Block IP addresses in private/link-local/loopback ranges
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_loopback:
            return False, "Loopback addresses are blocked"
        if addr.is_private:
            return False, "RFC1918 private addresses are blocked"
        if addr.is_link_local:
            return False, "Link-local addresses (169.254.x.x) are blocked"
        if addr.is_reserved:
            return False, "Reserved addresses are blocked"
    except ValueError:
        pass  # hostname is a domain name, not an IP — that's fine

    return True, "OK"

# ---------------------------------------------------------------------------
# Mining Controller — wraps the miner lifecycle
# ---------------------------------------------------------------------------


class MiningController:
    """Thread-safe mining controller for programmatic start/stop."""

    def __init__(self):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._mine_thread = None
        self._miner = None

        # State
        self.active = False
        self.wallet = None
        self.threads = 1
        self.cycle = 0
        self.started_at = None
        self.last_error = None
        self.last_balance = 0
        self.last_enrollment_ok = False

        # Webhook registry: list of {"url": ..., "events": [...]}
        self.webhooks = []
        self._webhook_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Mining lifecycle
    # ------------------------------------------------------------------

    def start(self, wallet, threads=1, wart_address=None,
              wart_pool=None, bzminer_path=None, manage_bzminer=False):
        """Start mining in a background thread."""
        with self._lock:
            if self.active:
                return False, "Mining is already active"

            self.wallet = wallet
            self.threads = max(1, threads)
            self._stop_event.clear()
            self.cycle = 0
            self.last_error = None
            self.started_at = time.time()

            self._mine_thread = threading.Thread(
                target=self._mine_loop,
                kwargs={
                    "wallet": wallet,
                    "wart_address": wart_address,
                    "wart_pool": wart_pool,
                    "bzminer_path": bzminer_path,
                    "manage_bzminer": manage_bzminer,
                },
                daemon=True,
                name="agent-miner",
            )
            self.active = True
            self._mine_thread.start()
            logger.info("Mining started — wallet=%s threads=%d", wallet, self.threads)
            self._fire_webhook("mining_started", {
                "wallet": wallet, "threads": self.threads
            })
            return True, "Mining started"

    def stop(self):
        """Stop the mining loop gracefully."""
        with self._lock:
            if not self.active:
                return False, "Mining is not active"
            self._stop_event.set()

        # Wait for thread to finish (up to 10s)
        if self._mine_thread and self._mine_thread.is_alive():
            self._mine_thread.join(timeout=10)

        with self._lock:
            self.active = False
            logger.info("Mining stopped after %d cycles", self.cycle)
            self._fire_webhook("mining_stopped", {
                "cycles": self.cycle,
                "uptime_s": round(time.time() - self.started_at, 1) if self.started_at else 0,
            })
            return True, "Mining stopped"

    def set_threads(self, count):
        """Adjust thread/intensity count (hot-reload)."""
        count = max(1, min(count, 64))
        old = self.threads
        self.threads = count
        logger.info("Threads adjusted: %d -> %d", old, count)
        return True, "Threads set to {}".format(count)

    def status(self):
        """Return machine-readable status dict."""
        uptime = round(time.time() - self.started_at, 1) if self.started_at else 0
        return {
            "active": self.active,
            "wallet": self.wallet,
            "threads": self.threads,
            "cycle": self.cycle,
            "uptime_s": uptime,
            "last_balance_rtc": self.last_balance,
            "last_enrollment_ok": self.last_enrollment_ok,
            "last_error": self.last_error,
            "started_at": (
                datetime.fromtimestamp(self.started_at, tz=timezone.utc).isoformat()
                if self.started_at else None
            ),
        }

    # ------------------------------------------------------------------
    # Internal mining loop
    # ------------------------------------------------------------------

    def _mine_loop(self, wallet, wart_address=None, wart_pool=None,
                   bzminer_path=None, manage_bzminer=False):
        """Background mining loop — mirrors LocalMiner.mine() but stoppable."""
        # Lazy import to avoid loading miner at module level
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "linux"))
            from rustchain_linux_miner import LocalMiner
        except ImportError as exc:
            self.last_error = "Failed to import LocalMiner: {}".format(exc)
            logger.error(self.last_error)
            self._fire_webhook("node_error", {"error": self.last_error})
            with self._lock:
                self.active = False
            return

        try:
            miner = LocalMiner(
                wallet=wallet,
                wart_address=wart_address,
                wart_pool=wart_pool,
                bzminer_path=bzminer_path,
                manage_bzminer=manage_bzminer,
            )
            self._miner = miner
        except Exception as exc:
            self.last_error = "Miner initialization failed: {}".format(exc)
            logger.error(self.last_error)
            self._fire_webhook("node_error", {"error": self.last_error})
            with self._lock:
                self.active = False
            return

        block_time = 600  # 10 minutes

        while not self._stop_event.is_set():
            self.cycle += 1
            logger.info("Cycle #%d starting", self.cycle)

            try:
                enrolled = miner.enroll()
                self.last_enrollment_ok = enrolled

                if enrolled:
                    self._fire_webhook("epoch_enrolled", {
                        "cycle": self.cycle,
                        "wallet": wallet,
                    })

                    # Wait for block time, checking stop event every 10s
                    waited = 0
                    while waited < block_time and not self._stop_event.is_set():
                        time.sleep(min(10, block_time - waited))
                        waited += 10

                    # Check balance after epoch
                    try:
                        balance = miner.check_balance()
                        if balance and balance != self.last_balance:
                            old_balance = self.last_balance
                            self.last_balance = balance
                            if balance > old_balance:
                                self._fire_webhook("payout_received", {
                                    "old_balance": old_balance,
                                    "new_balance": balance,
                                    "delta": balance - old_balance,
                                })
                    except Exception:
                        pass

                else:
                    self.last_error = "Enrollment failed at cycle {}".format(self.cycle)
                    logger.warning(self.last_error)
                    self._fire_webhook("node_error", {
                        "error": self.last_error, "cycle": self.cycle,
                    })
                    # Back off before retry
                    for _ in range(6):  # 60s in 10s chunks
                        if self._stop_event.is_set():
                            break
                        time.sleep(10)

            except Exception as exc:
                self.last_error = "Mining loop error: {}".format(exc)
                logger.error(self.last_error)
                self._fire_webhook("node_error", {"error": self.last_error})
                for _ in range(3):
                    if self._stop_event.is_set():
                        break
                    time.sleep(10)

        with self._lock:
            self.active = False
        logger.info("Mine loop exited cleanly")

    # ------------------------------------------------------------------
    # Webhook system
    # ------------------------------------------------------------------

    def register_webhook(self, url, events=None):
        """Register a webhook URL for event callbacks."""
        if not url:
            return False, "webhook_url is required"

        # SSRF protection: reject internal/loopback/RFC1918 targets
        safe, reason = _is_safe_webhook_url(url)
        if not safe:
            return False, "Webhook URL rejected: {}".format(reason)

        valid_events = [
            "mining_started", "mining_stopped", "epoch_enrolled",
            "payout_received", "node_error", "block_found",
        ]
        events = events or valid_events
        # Validate event names
        for ev in events:
            if ev not in valid_events:
                return False, "Unknown event: '{}'. Valid: {}".format(ev, valid_events)

        with self._webhook_lock:
            # Deduplicate by URL
            self.webhooks = [w for w in self.webhooks if w["url"] != url]
            self.webhooks.append({"url": url, "events": events})

        logger.info("Webhook registered: %s (events: %s)", url, events)
        return True, "Webhook registered"

    def remove_webhook(self, url):
        """Remove a registered webhook by URL."""
        with self._webhook_lock:
            before = len(self.webhooks)
            self.webhooks = [w for w in self.webhooks if w["url"] != url]
            removed = before - len(self.webhooks)
        return removed > 0, "Removed {} webhook(s)".format(removed)

    def list_webhooks(self):
        """Return list of registered webhooks."""
        with self._webhook_lock:
            return list(self.webhooks)

    def _fire_webhook(self, event, data):
        """Fire webhook callbacks for an event (non-blocking)."""
        if not requests:
            return
        with self._webhook_lock:
            targets = [
                w["url"] for w in self.webhooks if event in w.get("events", [])
            ]
        if not targets:
            return

        payload = {
            "event": event,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "data": data,
        }

        def _send(url, body):
            try:
                requests.post(url, json=body, timeout=5)
            except Exception as exc:
                logger.warning("Webhook delivery failed to %s: %s", url, exc)

        for url in targets:
            threading.Thread(
                target=_send, args=(url, payload), daemon=True
            ).start()


# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------

controller = MiningController()
app = Flask(__name__)

# Suppress Flask request logs in production
log = logging.getLogger("werkzeug")
log.setLevel(logging.WARNING)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for orchestrators / load balancers."""
    return jsonify({
        "status": "healthy",
        "uptime_s": round(time.time() - _boot_time, 1),
        "mining_active": controller.active,
        "version": "agent-miner-rpc/1.0.0",
        "platform": platform.system(),
        "arch": platform.machine(),
    })


@app.route("/api/mining/start", methods=["POST"])
@require_auth
def api_mining_start():
    """Start mining with the given wallet and thread count."""
    body = flask_request.get_json(silent=True) or {}
    wallet = body.get("wallet")
    if not wallet:
        return jsonify({"ok": False, "error": "wallet is required"}), 400

    threads = body.get("threads", 1)
    if not isinstance(threads, int) or threads < 1:
        return jsonify({"ok": False, "error": "threads must be a positive integer"}), 400

    ok, msg = controller.start(
        wallet=wallet,
        threads=threads,
        wart_address=body.get("wart_address"),
        wart_pool=body.get("wart_pool"),
        bzminer_path=body.get("bzminer_path"),
        manage_bzminer=body.get("manage_bzminer", False),
    )
    status_code = 200 if ok else 409
    return jsonify({"ok": ok, "message": msg}), status_code


@app.route("/api/mining/stop", methods=["POST"])
@require_auth
def api_mining_stop():
    """Stop the active mining loop."""
    ok, msg = controller.stop()
    status_code = 200 if ok else 409
    return jsonify({"ok": ok, "message": msg}), status_code


@app.route("/api/mining/status", methods=["GET"])
def api_mining_status():
    """Return machine-readable mining status.

    When auth is configured but the caller is unauthenticated, sensitive
    fields (wallet, balance) are redacted.
    """
    status = controller.status()
    if _auth_token is not None and not _is_authenticated():
        # Redact sensitive fields for unauthenticated callers
        status.pop("wallet", None)
        status.pop("last_balance_rtc", None)
    return jsonify(status)


@app.route("/api/mining/threads", methods=["POST"])
@require_auth
def api_mining_threads():
    """Adjust thread/intensity count on the fly."""
    body = flask_request.get_json(silent=True) or {}
    threads = body.get("threads")
    if threads is None or not isinstance(threads, int):
        return jsonify({"ok": False, "error": "threads (int) is required"}), 400

    ok, msg = controller.set_threads(threads)
    return jsonify({"ok": ok, "message": msg, "threads": controller.threads})


@app.route("/api/webhooks/register", methods=["POST"])
@require_auth
def api_webhooks_register():
    """Register a webhook URL for event callbacks."""
    body = flask_request.get_json(silent=True) or {}
    url = body.get("webhook_url")
    events = body.get("events")

    ok, msg = controller.register_webhook(url, events)
    status_code = 200 if ok else 400
    return jsonify({"ok": ok, "message": msg}), status_code


@app.route("/api/webhooks", methods=["GET"])
@require_auth
def api_webhooks_list():
    """List all registered webhooks."""
    return jsonify({"webhooks": controller.list_webhooks()})


@app.route("/api/webhooks", methods=["DELETE"])
@require_auth
def api_webhooks_delete():
    """Remove a webhook by URL."""
    body = flask_request.get_json(silent=True) or {}
    url = body.get("webhook_url")
    if not url:
        return jsonify({"ok": False, "error": "webhook_url is required"}), 400

    ok, msg = controller.remove_webhook(url)
    status_code = 200 if ok else 404
    return jsonify({"ok": ok, "message": msg}), status_code


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_boot_time = time.time()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RustChain Agent Miner RPC Server — headless mining for autonomous AI agents"
    )
    parser.add_argument(
        "--port", type=int, default=8332,
        help="Port to listen on (default: 8332)",
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="Bind address (default: 127.0.0.1; use 0.0.0.0 for remote access)",
    )
    parser.add_argument(
        "--wallet", type=str, default=None,
        help="Auto-start mining with this wallet on boot",
    )
    parser.add_argument(
        "--threads", type=int, default=1,
        help="Initial thread count when auto-starting (default: 1)",
    )
    parser.add_argument(
        "--auth-token", type=str, default=None,
        help="Bearer token for API authentication (or set AGENT_MINER_AUTH_TOKEN env)",
    )
    args = parser.parse_args()

    # Resolve auth token: CLI flag takes precedence over env var
    _auth_token = args.auth_token or os.environ.get("AGENT_MINER_AUTH_TOKEN")

    # Fail-closed: refuse to bind to non-loopback without auth
    is_loopback = args.host in ("127.0.0.1", "::1", "localhost")
    if not is_loopback and _auth_token is None:
        logger.error(
            "SECURITY: Refusing to bind to %s without --auth-token. "
            "A headless mining RPC exposed on the network without authentication "
            "is a remote-control surface. Set --auth-token or bind to 127.0.0.1.",
            args.host,
        )
        sys.exit(1)

    if _auth_token:
        logger.info("Authentication enabled (bearer token configured)")
    else:
        logger.info("Authentication disabled (loopback-only)")

    logger.info("Agent Miner RPC starting on %s:%d", args.host, args.port)

    if args.wallet:
        logger.info("Auto-starting mining with wallet %s", args.wallet)
        controller.start(wallet=args.wallet, threads=args.threads)

    app.run(host=args.host, port=args.port, debug=False)
