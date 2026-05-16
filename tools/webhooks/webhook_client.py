#!/usr/bin/env python3
"""
RustChain Webhook Client — Example Receiver

Starts a local HTTP server that listens for webhook events from the
RustChain webhook dispatcher and prints them to the console.  Optionally
verifies HMAC-SHA256 signatures when a shared secret is provided.

Usage:
  # 1. Start this receiver
  python webhook_client.py --port 9801

  # 2. Register it with the dispatcher
  export WEBHOOK_ADMIN_API_KEY="local-dev-admin-key"
  curl -X POST http://localhost:9800/webhooks/subscribe \
       -H "Content-Type: application/json" \
       -H "X-Admin-API-Key: $WEBHOOK_ADMIN_API_KEY" \
       -d '{"url": "http://localhost:9801/hook", "events": ["new_block", "miner_joined"]}'

  # 3. Watch events stream in
"""

import argparse
import hashlib
import hmac
import json
import logging
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("webhook-client")

# Will be set from CLI args
SHARED_SECRET: str | None = None


def verify_signature(payload: bytes, received_sig: str | None, secret: str) -> bool:
    """Verify HMAC-SHA256 signature from X-RustChain-Signature header."""
    if not received_sig:
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_sig)


def format_event(event_type: str, data: dict, ts: float) -> str:
    """Pretty-print a webhook event for the console."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [f"\n{'=' * 60}"]
    lines.append(f"  Event:     {event_type}")
    lines.append(f"  Received:  {dt}")

    if event_type == "new_block":
        lines.append(f"  Slot:      {data.get('slot')} (prev: {data.get('previous_slot')})")
        lines.append(f"  Miner:     {data.get('miner', 'N/A')}")
        lines.append(f"  Tip age:   {data.get('tip_age', '?')}s")

    elif event_type == "new_epoch":
        lines.append(f"  Epoch:     {data.get('epoch')} (prev: {data.get('previous_epoch')})")
        lines.append(f"  Miners:    {data.get('total_miners', '?')}")
        lines.append(f"  Balance:   {data.get('total_balance', '?')} RTC")

    elif event_type == "miner_joined":
        lines.append(f"  Miner:     {data.get('miner', '?')}")
        lines.append(f"  Hardware:  {data.get('hardware_type', 'unknown')}")
        lines.append(f"  Family:    {data.get('device_family', '?')} / {data.get('device_arch', '?')}")

    elif event_type == "miner_left":
        lines.append(f"  Miner:     {data.get('miner', '?')}")

    elif event_type == "large_tx":
        lines.append(f"  Miner:     {data.get('miner', '?')}")
        lines.append(f"  Delta:     {data.get('delta', 0):+.6f} RTC ({data.get('direction', '?')})")
        lines.append(f"  Balance:   {data.get('previous_balance', '?')} -> {data.get('new_balance', '?')} RTC")

    else:
        lines.append(f"  Data:      {json.dumps(data, indent=2)}")

    lines.append(f"{'=' * 60}")
    return "\n".join(lines)


class WebhookReceiver(BaseHTTPRequestHandler):
    """HTTP handler that receives webhook POST payloads."""

    def log_message(self, fmt, *args):
        pass  # suppress default logging

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self.send_response(400)
            self.end_headers()
            return

        payload = self.rfile.read(content_length)

        # Signature verification
        if SHARED_SECRET:
            sig = self.headers.get("X-RustChain-Signature")
            if not verify_signature(payload, sig, SHARED_SECRET):
                log.warning("Signature verification FAILED — rejecting payload")
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b'{"error": "invalid signature"}')
                return

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        event_type = data.get("event", "unknown")
        timestamp = data.get("timestamp", 0)
        event_data = data.get("data", {})

        print(format_event(event_type, event_data, timestamp))

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "received"}).encode())

    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "listening"}).encode())


def main():
    parser = argparse.ArgumentParser(description="RustChain Webhook Receiver (Example Client)")
    parser.add_argument("--port", type=int, default=9801,
                        help="Port to listen on (default: %(default)s)")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Bind address (default: %(default)s)")
    parser.add_argument("--secret", default=None,
                        help="Shared secret for HMAC signature verification")
    args = parser.parse_args()

    global SHARED_SECRET
    SHARED_SECRET = args.secret

    server = HTTPServer((args.host, args.port), WebhookReceiver)
    log.info("Webhook receiver listening on http://%s:%d", args.host, args.port)
    if SHARED_SECRET:
        log.info("Signature verification enabled")
    else:
        log.info("Signature verification disabled (no --secret provided)")

    log.info("Register this receiver with the dispatcher:")
    log.info('  export WEBHOOK_ADMIN_API_KEY="local-dev-admin-key"')
    log.info('  curl -X POST http://localhost:9800/webhooks/subscribe \\')
    log.info('    -H "Content-Type: application/json" \\')
    log.info('    -H "X-Admin-API-Key: $WEBHOOK_ADMIN_API_KEY" \\')
    log.info('    -d \'{"url": "http://localhost:%d/hook"}\'', args.port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down receiver ...")
        server.shutdown()


if __name__ == "__main__":
    main()
