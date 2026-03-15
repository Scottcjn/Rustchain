#!/usr/bin/env python3
"""
RustChain Uptime Monitor

Continuously monitors RustChain node health, tracks response times and uptime
percentages, stores historical data in SQLite, generates a public status page,
and sends alerts via email or webhook when downtime is detected.

Usage:
    python monitor.py                                  # defaults
    python monitor.py --nodes https://rustchain.org    # specific node(s)
    python monitor.py --interval 15                    # check every 15s
    python monitor.py --webhook https://hooks.slack.com/services/...
    python monitor.py --smtp-host smtp.gmail.com --alert-email ops@example.com
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import smtplib
import sqlite3
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.mime.text import MIMEText
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template
from threading import Event, Lock, Thread
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_NODES: List[str] = [
    "https://rustchain.org",
    "https://50.28.86.153",
    "http://76.8.228.245:8099",
]

HEALTH_ENDPOINT = "/health"
CHECK_INTERVAL = 30          # seconds
HTTP_TIMEOUT = 10            # seconds per probe
DB_FILE = "uptime.db"
STATUS_HTML_OUT = "status-page.html"
TEMPLATE_FILE = Path(__file__).with_name("status-page-template.html")

LOG = logging.getLogger("uptime-monitor")

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS checks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    node        TEXT    NOT NULL,
    ts          TEXT    NOT NULL,           -- ISO-8601 UTC
    ts_epoch    REAL    NOT NULL,
    healthy     INTEGER NOT NULL DEFAULT 0, -- 1 = up, 0 = down
    status_code INTEGER,
    response_ms REAL,
    error       TEXT
);

CREATE INDEX IF NOT EXISTS idx_checks_node_ts ON checks(node, ts_epoch);

CREATE TABLE IF NOT EXISTS incidents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    node        TEXT    NOT NULL,
    started     TEXT    NOT NULL,
    ended       TEXT,
    duration_s  REAL,
    resolved    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_incidents_node ON incidents(node, resolved);
"""


def _db_connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_CREATE_SQL)
    return conn


# ---------------------------------------------------------------------------
# HTTP probe
# ---------------------------------------------------------------------------

def _ssl_ctx(insecure: bool = True) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def probe_node(url: str, timeout: int = HTTP_TIMEOUT) -> Dict[str, Any]:
    """Probe a single node and return a result dict."""
    target = url.rstrip("/") + HEALTH_ENDPOINT
    result: Dict[str, Any] = {
        "node": url,
        "ts": _utc_iso(),
        "ts_epoch": time.time(),
        "healthy": False,
        "status_code": None,
        "response_ms": None,
        "error": None,
    }
    start = time.monotonic()
    try:
        req = urllib.request.Request(
            target, headers={"User-Agent": "rustchain-uptime-monitor/1.0"}
        )
        ctx = _ssl_ctx() if target.startswith("https") else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            _ = resp.read(64 * 1024)
            elapsed = (time.monotonic() - start) * 1000
            result["status_code"] = resp.status
            result["response_ms"] = round(elapsed, 2)
            result["healthy"] = 200 <= resp.status < 400
    except urllib.error.HTTPError as exc:
        elapsed = (time.monotonic() - start) * 1000
        result["status_code"] = exc.code
        result["response_ms"] = round(elapsed, 2)
        result["error"] = str(exc)
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        result["response_ms"] = round(elapsed, 2)
        result["error"] = str(exc)
    return result


# ---------------------------------------------------------------------------
# Uptime calculator
# ---------------------------------------------------------------------------

def calc_uptime(conn: sqlite3.Connection, node: str, window_s: float) -> float:
    """Return uptime percentage for *node* over the last *window_s* seconds."""
    cutoff = time.time() - window_s
    row = conn.execute(
        "SELECT COUNT(*) AS total, SUM(healthy) AS up "
        "FROM checks WHERE node = ? AND ts_epoch >= ?",
        (node, cutoff),
    ).fetchone()
    total, up = row
    if not total:
        return 100.0
    return round((up / total) * 100, 4)


def avg_response(conn: sqlite3.Connection, node: str, window_s: float) -> Optional[float]:
    cutoff = time.time() - window_s
    row = conn.execute(
        "SELECT AVG(response_ms) FROM checks WHERE node = ? AND ts_epoch >= ? AND healthy = 1",
        (node, cutoff),
    ).fetchone()
    return round(row[0], 2) if row and row[0] is not None else None


def recent_checks(conn: sqlite3.Connection, node: str, limit: int = 60) -> List[Dict]:
    rows = conn.execute(
        "SELECT ts, healthy, status_code, response_ms, error "
        "FROM checks WHERE node = ? ORDER BY ts_epoch DESC LIMIT ?",
        (node, limit),
    ).fetchall()
    return [
        {"ts": r[0], "healthy": bool(r[1]), "status_code": r[2],
         "response_ms": r[3], "error": r[4]}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Incident tracking
# ---------------------------------------------------------------------------

def _open_incident(conn: sqlite3.Connection, node: str, ts: str) -> None:
    existing = conn.execute(
        "SELECT id FROM incidents WHERE node = ? AND resolved = 0", (node,)
    ).fetchone()
    if existing:
        return
    conn.execute(
        "INSERT INTO incidents (node, started, resolved) VALUES (?, ?, 0)",
        (node, ts),
    )
    conn.commit()


def _close_incident(conn: sqlite3.Connection, node: str, ts: str) -> Optional[float]:
    row = conn.execute(
        "SELECT id, started FROM incidents WHERE node = ? AND resolved = 0", (node,)
    ).fetchone()
    if not row:
        return None
    inc_id, started = row
    try:
        start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        duration = (end_dt - start_dt).total_seconds()
    except Exception:
        duration = 0
    conn.execute(
        "UPDATE incidents SET ended = ?, duration_s = ?, resolved = 1 WHERE id = ?",
        (ts, duration, inc_id),
    )
    conn.commit()
    return duration


# ---------------------------------------------------------------------------
# Alerting — email
# ---------------------------------------------------------------------------

def send_email_alert(
    subject: str,
    body: str,
    to_addr: str,
    from_addr: str,
    smtp_host: str,
    smtp_port: int = 587,
    smtp_user: Optional[str] = None,
    smtp_pass: Optional[str] = None,
) -> None:
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as srv:
            srv.ehlo()
            if smtp_port != 25:
                srv.starttls()
                srv.ehlo()
            if smtp_user:
                srv.login(smtp_user, smtp_pass or "")
            srv.sendmail(from_addr, [to_addr], msg.as_string())
        LOG.info("Email alert sent to %s", to_addr)
    except Exception as exc:
        LOG.error("Failed to send email alert: %s", exc)


# ---------------------------------------------------------------------------
# Alerting — webhook (Slack / Discord / generic)
# ---------------------------------------------------------------------------

def send_webhook_alert(url: str, payload: Dict[str, Any]) -> None:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json",
                 "User-Agent": "rustchain-uptime-monitor/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            LOG.info("Webhook alert sent (%s)", resp.status)
    except Exception as exc:
        LOG.error("Webhook alert failed: %s", exc)


# ---------------------------------------------------------------------------
# Status page generation
# ---------------------------------------------------------------------------

def _utc_iso(ts: Optional[float] = None) -> str:
    ts = time.time() if ts is None else ts
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _status_class(pct: float) -> str:
    if pct >= 99.9:
        return "operational"
    if pct >= 95.0:
        return "degraded"
    return "down"


def _status_label(pct: float) -> str:
    if pct >= 99.9:
        return "Operational"
    if pct >= 95.0:
        return "Degraded"
    return "Major Outage"


def generate_status_page(
    conn: sqlite3.Connection,
    nodes: List[str],
    out_path: str = STATUS_HTML_OUT,
) -> None:
    """Render the status page HTML to disk."""
    now = _utc_iso()
    rows_html: List[str] = []
    overall_up = True

    for node in nodes:
        up_24h = calc_uptime(conn, node, 86400)
        up_7d = calc_uptime(conn, node, 604800)
        up_30d = calc_uptime(conn, node, 2592000)
        avg_ms = avg_response(conn, node, 3600)
        css = _status_class(up_24h)
        label = _status_label(up_24h)
        if up_24h < 99.9:
            overall_up = False

        # Build 90-bar sparkline (last 90 checks)
        checks = recent_checks(conn, node, 90)
        bars = []
        for c in reversed(checks):
            bar_cls = "bar-up" if c["healthy"] else "bar-down"
            title = f"{c['ts']} — {'UP' if c['healthy'] else 'DOWN'}"
            if c["response_ms"] is not None:
                title += f" ({c['response_ms']}ms)"
            bars.append(f'<div class="bar {bar_cls}" title="{title}"></div>')
        sparkline = "".join(bars)

        rows_html.append(
            f"""
        <div class="node-card">
            <div class="node-header">
                <span class="node-name">{node}</span>
                <span class="status-badge {css}">{label}</span>
            </div>
            <div class="sparkline">{sparkline}</div>
            <div class="node-stats">
                <span>Response: <b>{avg_ms if avg_ms else '—'}ms</b></span>
                <span>24h: <b>{up_24h}%</b></span>
                <span>7d: <b>{up_7d}%</b></span>
                <span>30d: <b>{up_30d}%</b></span>
            </div>
        </div>"""
        )

    overall_css = "operational" if overall_up else "degraded"
    overall_label = "All Systems Operational" if overall_up else "Some Systems Degraded"

    # Load template
    if TEMPLATE_FILE.exists():
        tpl = TEMPLATE_FILE.read_text(encoding="utf-8")
    else:
        tpl = _FALLBACK_TEMPLATE

    html = (
        tpl.replace("{{GENERATED}}", now)
        .replace("{{OVERALL_STATUS}}", overall_label)
        .replace("{{OVERALL_CLASS}}", overall_css)
        .replace("{{NODE_ROWS}}", "\n".join(rows_html))
    )

    Path(out_path).write_text(html, encoding="utf-8")
    LOG.info("Status page written to %s", out_path)


_FALLBACK_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>RustChain Status</title>
<style>body{font-family:sans-serif;max-width:800px;margin:2rem auto;padding:0 1rem}
.operational{color:#22c55e}.degraded{color:#eab308}.down{color:#ef4444}
.node-card{border:1px solid #e5e7eb;border-radius:.5rem;padding:1rem;margin:1rem 0}
.sparkline{display:flex;gap:1px;height:28px;margin:.5rem 0}
.bar{flex:1;border-radius:2px}.bar-up{background:#22c55e}.bar-down{background:#ef4444}
.node-header{display:flex;justify-content:space-between;align-items:center}
.node-stats{display:flex;gap:1.5rem;font-size:.85rem;color:#6b7280}
.status-badge{font-weight:600;font-size:.85rem}
</style></head><body>
<h1>RustChain Network Status</h1>
<p class="{{OVERALL_CLASS}}" style="font-size:1.2rem;font-weight:600">{{OVERALL_STATUS}}</p>
{{NODE_ROWS}}
<footer style="margin-top:2rem;font-size:.75rem;color:#9ca3af">Last updated: {{GENERATED}}</footer>
</body></html>"""


# ---------------------------------------------------------------------------
# Monitor loop
# ---------------------------------------------------------------------------

class UptimeMonitor:
    def __init__(
        self,
        nodes: List[str],
        interval: int = CHECK_INTERVAL,
        db_path: str = DB_FILE,
        status_out: str = STATUS_HTML_OUT,
        webhook_url: Optional[str] = None,
        alert_email: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_pass: Optional[str] = None,
        smtp_from: Optional[str] = None,
        serve_port: Optional[int] = None,
    ):
        self.nodes = nodes
        self.interval = interval
        self.db_path = db_path
        self.status_out = status_out
        self.webhook_url = webhook_url
        self.alert_email = alert_email
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.smtp_from = smtp_from or "uptime@rustchain.org"
        self.serve_port = serve_port

        self.conn = _db_connect(db_path)
        self._lock = Lock()
        self._stop = Event()
        self._prev_state: Dict[str, bool] = {}  # debounce alerts

    # ── single check round ────────────────────────────────────────────
    def _check_round(self) -> None:
        for node in self.nodes:
            result = probe_node(node)
            with self._lock:
                self.conn.execute(
                    "INSERT INTO checks (node, ts, ts_epoch, healthy, status_code, response_ms, error) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (result["node"], result["ts"], result["ts_epoch"],
                     int(result["healthy"]), result["status_code"],
                     result["response_ms"], result["error"]),
                )
                self.conn.commit()

            was_up = self._prev_state.get(node, True)
            is_up = result["healthy"]

            # State transition: UP -> DOWN
            if was_up and not is_up:
                LOG.warning("Node DOWN: %s — %s", node, result.get("error", ""))
                _open_incident(self.conn, node, result["ts"])
                self._send_alert(node, result, down=True)

            # State transition: DOWN -> UP
            if not was_up and is_up:
                LOG.info("Node RECOVERED: %s", node)
                duration = _close_incident(self.conn, node, result["ts"])
                self._send_alert(node, result, down=False, duration=duration)

            self._prev_state[node] = is_up

            status = "UP" if is_up else "DOWN"
            LOG.info(
                "[%s] %s — %sms (HTTP %s)",
                status, node, result["response_ms"], result["status_code"],
            )

        # Regenerate status page after every round
        try:
            with self._lock:
                generate_status_page(self.conn, self.nodes, self.status_out)
        except Exception as exc:
            LOG.error("Status page generation failed: %s", exc)

    # ── alert dispatch ────────────────────────────────────────────────
    def _send_alert(
        self, node: str, result: Dict, *, down: bool, duration: Optional[float] = None
    ) -> None:
        if down:
            subject = f"[RustChain] Node DOWN: {node}"
            body = (
                f"Node {node} is unreachable.\n"
                f"Time: {result['ts']}\n"
                f"Error: {result.get('error', 'N/A')}\n"
                f"Status code: {result.get('status_code', 'N/A')}\n"
            )
            webhook_payload = {
                "text": subject,
                "content": subject,
                "node": node,
                "event": "down",
                "details": body,
            }
        else:
            dur_str = f"{duration:.0f}s" if duration else "unknown"
            subject = f"[RustChain] Node RECOVERED: {node}"
            body = (
                f"Node {node} is back online.\n"
                f"Time: {result['ts']}\n"
                f"Downtime duration: {dur_str}\n"
            )
            webhook_payload = {
                "text": subject,
                "content": subject,
                "node": node,
                "event": "recovery",
                "details": body,
            }

        if self.webhook_url:
            send_webhook_alert(self.webhook_url, webhook_payload)

        if self.alert_email and self.smtp_host:
            send_email_alert(
                subject, body, self.alert_email,
                self.smtp_from, self.smtp_host, self.smtp_port,
                self.smtp_user, self.smtp_pass,
            )

    # ── HTTP server for live status page ──────────────────────────────
    def _serve_status(self) -> None:
        out = self.status_out

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                p = Path(out)
                if not p.exists():
                    self.send_error(503, "Status page not generated yet")
                    return
                html = p.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)

            def log_message(self, fmt, *args):
                LOG.debug("HTTP %s", fmt % args)

        server = ThreadingHTTPServer(("0.0.0.0", self.serve_port), Handler)
        LOG.info("Status page HTTP server on :%d", self.serve_port)
        server.serve_forever()

    # ── main loop ─────────────────────────────────────────────────────
    def run(self) -> None:
        LOG.info(
            "Starting uptime monitor — %d node(s), interval %ds",
            len(self.nodes), self.interval,
        )

        if self.serve_port:
            Thread(target=self._serve_status, daemon=True).start()

        while not self._stop.is_set():
            try:
                self._check_round()
            except Exception:
                LOG.exception("Unexpected error in check round")
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="RustChain node uptime monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--nodes", nargs="+", default=DEFAULT_NODES,
        help="Node base URLs to monitor (default: built-in list)",
    )
    p.add_argument("--interval", type=int, default=CHECK_INTERVAL,
                    help="Seconds between check rounds (default: 30)")
    p.add_argument("--db", default=DB_FILE, help="SQLite database path")
    p.add_argument("--status-out", default=STATUS_HTML_OUT,
                    help="Path for generated status page HTML")
    p.add_argument("--serve", type=int, default=None, metavar="PORT",
                    help="Serve the status page over HTTP on this port")

    g = p.add_argument_group("Webhook alerts")
    g.add_argument("--webhook", default=None,
                    help="Webhook URL for down/recovery alerts (Slack, Discord, etc.)")

    g = p.add_argument_group("Email alerts")
    g.add_argument("--alert-email", default=None, help="Recipient email for alerts")
    g.add_argument("--smtp-host", default=None)
    g.add_argument("--smtp-port", type=int, default=587)
    g.add_argument("--smtp-user", default=None)
    g.add_argument("--smtp-pass", default=None)
    g.add_argument("--smtp-from", default=None)

    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main() -> None:
    args = build_parser().parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    monitor = UptimeMonitor(
        nodes=args.nodes,
        interval=args.interval,
        db_path=args.db,
        status_out=args.status_out,
        webhook_url=args.webhook,
        alert_email=args.alert_email,
        smtp_host=args.smtp_host,
        smtp_port=args.smtp_port,
        smtp_user=args.smtp_user,
        smtp_pass=args.smtp_pass,
        smtp_from=args.smtp_from,
        serve_port=args.serve,
    )

    try:
        monitor.run()
    except KeyboardInterrupt:
        LOG.info("Shutting down.")
        monitor.stop()


if __name__ == "__main__":
    main()
