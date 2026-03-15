#!/usr/bin/env python3
"""
RustChain Alert Notifier

Lightweight alerting script that can:
  1. Receive Alertmanager webhook POSTs and forward them
  2. Run standalone as a poller against a RustChain node
  3. Send notifications via Email (SMTP), Slack, and generic webhooks

Usage:
  # Webhook receiver mode (listens for Alertmanager POSTs):
  python notify.py --mode webhook --port 9095

  # Poller mode (checks the node directly and fires alerts):
  python notify.py --mode poll --node https://rustchain.org --interval 60

Environment variables (all optional — override via flags or config file):
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_TO, SMTP_FROM
  SLACK_WEBHOOK_URL
  WEBHOOK_URL
  RUSTCHAIN_NODE
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import smtplib
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("rustchain-notify")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Config:
    """Centralised config populated from env vars and CLI flags."""

    def __init__(self, args: Optional[argparse.Namespace] = None):
        self.smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user: str = os.getenv("SMTP_USER", "")
        self.smtp_pass: str = os.getenv("SMTP_PASS", "")
        self.smtp_from: str = os.getenv("SMTP_FROM", self.smtp_user)
        self.smtp_to: str = os.getenv("SMTP_TO", "")

        self.slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
        self.webhook_url: str = os.getenv("WEBHOOK_URL", "")

        self.node: str = os.getenv("RUSTCHAIN_NODE", "https://rustchain.org")
        self.interval: int = 60
        self.port: int = 9095

        if args:
            self.node = args.node or self.node
            self.interval = args.interval
            self.port = args.port

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_user and self.smtp_to)

    @property
    def slack_enabled(self) -> bool:
        return bool(self.slack_webhook_url)

    @property
    def webhook_enabled(self) -> bool:
        return bool(self.webhook_url)


# ---------------------------------------------------------------------------
# Notification backends
# ---------------------------------------------------------------------------

def send_email(cfg: Config, subject: str, body: str) -> bool:
    """Send an alert email via SMTP/TLS."""
    if not cfg.email_enabled:
        log.debug("Email not configured — skipping")
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = cfg.smtp_from
        msg["To"] = cfg.smtp_to

        ctx = ssl.create_default_context()
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as srv:
            srv.ehlo()
            srv.starttls(context=ctx)
            srv.ehlo()
            srv.login(cfg.smtp_user, cfg.smtp_pass)
            srv.sendmail(cfg.smtp_from, cfg.smtp_to.split(","), msg.as_string())
        log.info("Email sent to %s", cfg.smtp_to)
        return True
    except Exception as exc:
        log.error("Email send failed: %s", exc)
        return False


def send_slack(cfg: Config, text: str) -> bool:
    """Post a message to Slack via incoming webhook."""
    if not cfg.slack_enabled:
        log.debug("Slack not configured — skipping")
        return False
    try:
        payload = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            cfg.slack_webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        log.info("Slack notification sent")
        return True
    except Exception as exc:
        log.error("Slack send failed: %s", exc)
        return False


def send_webhook(cfg: Config, payload: Dict[str, Any]) -> bool:
    """Forward the full alert payload to a generic webhook endpoint."""
    if not cfg.webhook_enabled:
        log.debug("Webhook not configured — skipping")
        return False
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            cfg.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        log.info("Webhook delivered to %s", cfg.webhook_url)
        return True
    except Exception as exc:
        log.error("Webhook send failed: %s", exc)
        return False


def dispatch(cfg: Config, subject: str, body: str, raw: Optional[Dict] = None):
    """Fan-out alert to every configured channel."""
    send_email(cfg, subject, body)
    send_slack(cfg, f"*{subject}*\n{body}")
    send_webhook(cfg, raw or {"subject": subject, "body": body})


# ---------------------------------------------------------------------------
# Alertmanager webhook receiver
# ---------------------------------------------------------------------------

class AlertHandler(BaseHTTPRequestHandler):
    """Receives POST /webhook from Prometheus Alertmanager."""

    cfg: Config  # set on the class before starting the server

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        alerts: List[Dict] = data.get("alerts", [])
        for alert in alerts:
            status = alert.get("status", "unknown")
            name = alert.get("labels", {}).get("alertname", "UnknownAlert")
            severity = alert.get("labels", {}).get("severity", "info")
            summary = alert.get("annotations", {}).get("summary", "")
            description = alert.get("annotations", {}).get("description", "")

            prefix = "RESOLVED" if status == "resolved" else status.upper()
            subject = f"[{prefix}] RustChain: {name} ({severity})"
            body = f"{summary}\n\n{description}"

            log.info("Alert received: %s — %s", subject, summary)
            dispatch(self.cfg, subject, body, raw=data)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, fmt, *args):
        log.debug(fmt, *args)


def run_webhook_server(cfg: Config):
    """Start the webhook receiver HTTP server."""
    AlertHandler.cfg = cfg
    server = HTTPServer(("0.0.0.0", cfg.port), AlertHandler)
    log.info("Webhook receiver listening on :%d", cfg.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down webhook server")
        server.server_close()


# ---------------------------------------------------------------------------
# Standalone poller mode
# ---------------------------------------------------------------------------

def fetch_json(url: str, timeout: int = 10) -> Optional[Dict]:
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "rustchain-notify/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        log.warning("Fetch %s failed: %s", url, exc)
        return None


def poll_loop(cfg: Config):
    """Continuously poll the RustChain node and fire alerts locally."""
    log.info("Polling %s every %ds", cfg.node, cfg.interval)

    last_slot: Optional[int] = None
    last_slot_change: float = time.time()
    node_was_down: bool = False

    while True:
        # --- Health check ---
        health = fetch_json(f"{cfg.node}/health")
        if health is None or not health.get("ok"):
            if not node_was_down:
                dispatch(cfg, "[CRITICAL] RustChain Node Down",
                         f"Health check failed for {cfg.node}")
                node_was_down = True
        else:
            if node_was_down:
                dispatch(cfg, "[RESOLVED] RustChain Node Recovered",
                         f"Health check passing again for {cfg.node}")
                node_was_down = False

        # --- Epoch stall check ---
        epoch = fetch_json(f"{cfg.node}/epoch")
        if epoch:
            slot = epoch.get("slot", 0)
            if last_slot is not None and slot != last_slot:
                last_slot_change = time.time()
            elif last_slot is not None and (time.time() - last_slot_change) > 600:
                dispatch(cfg, "[CRITICAL] Epoch Stalled",
                         f"No slot change in 10 min on {cfg.node}. "
                         f"Stuck at epoch {epoch.get('epoch')}, slot {slot}.")
                last_slot_change = time.time()  # debounce re-fire
            last_slot = slot

        # --- Miner count ---
        miners = fetch_json(f"{cfg.node}/api/miners")
        if miners is not None:
            count = len(miners)
            if count == 0:
                dispatch(cfg, "[CRITICAL] No Active Miners",
                         f"Zero miners reporting on {cfg.node}.")
            elif count < 3:
                dispatch(cfg, "[WARNING] Low Miner Count",
                         f"Only {count} active miners on {cfg.node}.")

        # --- API latency (measure health round-trip) ---
        t0 = time.time()
        fetch_json(f"{cfg.node}/health")
        latency = time.time() - t0
        if latency > 5.0:
            dispatch(cfg, "[WARNING] High API Latency",
                     f"Health endpoint took {latency:.1f}s on {cfg.node}.")

        time.sleep(cfg.interval)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="RustChain Alert Notifier")
    parser.add_argument("--mode", choices=["webhook", "poll"], default="poll",
                        help="Run as Alertmanager webhook receiver or standalone poller")
    parser.add_argument("--node", default=None,
                        help="RustChain node URL (default: $RUSTCHAIN_NODE or https://rustchain.org)")
    parser.add_argument("--interval", type=int, default=60,
                        help="Poll interval in seconds (poller mode only)")
    parser.add_argument("--port", type=int, default=9095,
                        help="HTTP port for webhook receiver mode")
    args = parser.parse_args()

    cfg = Config(args)

    if not (cfg.email_enabled or cfg.slack_enabled or cfg.webhook_enabled):
        log.warning(
            "No notification channels configured. Set SMTP_*, SLACK_WEBHOOK_URL, "
            "or WEBHOOK_URL environment variables."
        )

    if args.mode == "webhook":
        run_webhook_server(cfg)
    else:
        poll_loop(cfg)


if __name__ == "__main__":
    main()
