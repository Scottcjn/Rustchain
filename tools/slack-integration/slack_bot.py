#!/usr/bin/env python3
"""
RustChain Slack Bot — Node Monitoring & Mining Alerts

Provides slash commands for real-time node health, wallet balances, and
miner status.  Runs a background scheduler that posts daily mining
summaries and proactive alerts when nodes go down or miner counts drop.

Requires:
    pip install slack-bolt requests apscheduler

Environment variables (see .env.example):
    SLACK_BOT_TOKEN        — Bot User OAuth Token  (xoxb-...)
    SLACK_SIGNING_SECRET   — Signing secret from Slack app settings
    SLACK_ALERT_CHANNEL    — Channel ID for automated alerts / summaries
    RUSTCHAIN_NODE_URLS    — Comma-separated node base URLs
                             (default: https://rustchain.org)
    MONITOR_INTERVAL_SEC   — Health-check polling interval (default: 300)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")  # for Socket Mode
SLACK_ALERT_CHANNEL = os.environ.get("SLACK_ALERT_CHANNEL", "")

NODE_URLS: List[str] = [
    u.strip()
    for u in os.environ.get(
        "RUSTCHAIN_NODE_URLS", "https://rustchain.org"
    ).split(",")
    if u.strip()
]

MONITOR_INTERVAL = int(os.environ.get("MONITOR_INTERVAL_SEC", "300"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT_SEC", "10"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("rustchain-slack")

# ---------------------------------------------------------------------------
# RustChain API helpers
# ---------------------------------------------------------------------------

_session = requests.Session()
_session.headers.update({"User-Agent": "rustchain-slack-bot/1.0"})


def _get_json(url: str) -> Tuple[bool, Any]:
    """GET a JSON endpoint; returns (ok, data_or_error_str)."""
    try:
        r = _session.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return True, r.json()
    except requests.RequestException as exc:
        return False, str(exc)


def fetch_node_health(base: str) -> Dict[str, Any]:
    """Poll /health on a single node."""
    ok, data = _get_json(f"{base.rstrip('/')}/health")
    return {"node": base, "ok": ok, "data": data}


def fetch_node_stats(base: str) -> Dict[str, Any]:
    """GET /api/stats for high-level numbers."""
    ok, data = _get_json(f"{base.rstrip('/')}/api/stats")
    return {"node": base, "ok": ok, "data": data}


def fetch_balance(base: str, miner_pk: str) -> Dict[str, Any]:
    """GET /balance/<miner_pk>."""
    ok, data = _get_json(f"{base.rstrip('/')}/balance/{miner_pk}")
    return {"node": base, "ok": ok, "data": data}


def fetch_miners(base: str) -> Dict[str, Any]:
    """GET /api/miners or fall back to /epoch for enrolled-miner list."""
    ok, data = _get_json(f"{base.rstrip('/')}/api/miners")
    if ok:
        return {"node": base, "ok": True, "data": data}
    # Fallback: /epoch contains enrolled_miners
    ok2, data2 = _get_json(f"{base.rstrip('/')}/epoch")
    return {"node": base, "ok": ok2, "data": data2}


def fetch_epoch(base: str) -> Dict[str, Any]:
    """GET /epoch for current epoch details."""
    ok, data = _get_json(f"{base.rstrip('/')}/epoch")
    return {"node": base, "ok": ok, "data": data}


def _parse_miners_list(payload: Any) -> List[Dict[str, Any]]:
    """Normalise various /api/miners response shapes into a flat list."""
    obj = payload
    if isinstance(payload, dict) and "miners" in payload:
        obj = payload["miners"]
    if isinstance(obj, list):
        return [m for m in obj if isinstance(m, dict)]
    if isinstance(obj, dict):
        return [v for v in obj.values() if isinstance(v, dict)]
    return []


# ---------------------------------------------------------------------------
# Slack App
# ---------------------------------------------------------------------------

app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ---- /rtc-status ----------------------------------------------------------

@app.command("/rtc-status")
def handle_status(ack, respond, command):
    """Report health of every configured node."""
    ack()
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "RustChain Node Status"},
        }
    ]

    for base in NODE_URLS:
        health = fetch_node_health(base)
        stats = fetch_node_stats(base)

        if health["ok"]:
            health_data = health["data"] if isinstance(health["data"], dict) else {}
            node_ok = health_data.get("ok", True)
            status_icon = ":large_green_circle:" if node_ok else ":red_circle:"
            status_text = "Healthy" if node_ok else "Degraded"
        else:
            status_icon = ":red_circle:"
            status_text = f"Unreachable — {health['data']}"

        fields = [
            f"*Node:* `{base}`",
            f"*Status:* {status_icon} {status_text}",
        ]

        if stats["ok"] and isinstance(stats["data"], dict):
            sd = stats["data"]
            if "version" in sd:
                fields.append(f"*Version:* {sd['version']}")
            if "epoch" in sd:
                fields.append(f"*Epoch:* {sd['epoch']}")
            if "miners" in sd:
                fields.append(f"*Miners:* {sd['miners']}")
            if "total_balance" in sd:
                fields.append(f"*Total RTC:* {sd['total_balance']}")

        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(fields)},
            }
        )
        blocks.append({"type": "divider"})

    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"Checked at {_utc_now()}"}],
        }
    )
    respond(blocks=blocks, response_type="in_channel")


# ---- /rtc-balance ----------------------------------------------------------

@app.command("/rtc-balance")
def handle_balance(ack, respond, command):
    """Check the RTC balance for a given miner public key.

    Usage:  /rtc-balance <miner_public_key>
    """
    ack()
    text = (command.get("text") or "").strip()
    if not text:
        respond(
            text=":warning: Please provide a miner public key.\n"
            "Usage: `/rtc-balance <miner_public_key>`",
        )
        return

    miner_pk = text.split()[0]
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"RTC Balance — {miner_pk[:16]}..."},
        }
    ]

    for base in NODE_URLS:
        result = fetch_balance(base, miner_pk)
        if result["ok"] and isinstance(result["data"], dict):
            bal = result["data"]
            balance_val = bal.get("balance", bal.get("rtc_balance", "N/A"))
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Node:* `{base}`\n"
                            f"*Wallet:* `{miner_pk}`\n"
                            f"*Balance:* `{balance_val} RTC`"
                        ),
                    },
                }
            )
            break  # one successful response is enough
        else:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Node:* `{base}` — :red_circle: Could not fetch balance",
                    },
                }
            )

    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"Queried at {_utc_now()}"}],
        }
    )
    respond(blocks=blocks, response_type="ephemeral")


# ---- /rtc-miners -----------------------------------------------------------

@app.command("/rtc-miners")
def handle_miners(ack, respond, command):
    """List active miners on the network."""
    ack()
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "RustChain Active Miners"},
        }
    ]

    for base in NODE_URLS:
        result = fetch_miners(base)
        if not result["ok"]:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Node:* `{base}` — :red_circle: Could not fetch miners",
                    },
                }
            )
            continue

        miners = _parse_miners_list(result["data"])
        miner_count = len(miners)

        # Also try /epoch for enrolled count
        epoch_res = fetch_epoch(base)
        epoch_info = ""
        if epoch_res["ok"] and isinstance(epoch_res["data"], dict):
            ep = epoch_res["data"]
            enrolled = ep.get("enrolled_miners", ep.get("miners", "?"))
            epoch_num = ep.get("epoch", ep.get("slot", "?"))
            pot = ep.get("pot", ep.get("reward_pot", "?"))
            epoch_info = f"\n*Epoch:* {epoch_num}  |  *Pot:* {pot} RTC  |  *Enrolled:* {enrolled}"

        fields = f"*Node:* `{base}`\n*Active miners:* {miner_count}{epoch_info}"

        # Show top miners (limit to 15 to avoid message overflow)
        if miners:
            lines = []
            for m in miners[:15]:
                mid = m.get("miner_id") or m.get("miner") or m.get("id") or "unknown"
                last_seen = m.get("last_seen") or m.get("last_attest_ts") or m.get("ts_ok")
                age_str = ""
                if last_seen:
                    try:
                        age_s = int(time.time() - float(last_seen))
                        if age_s < 60:
                            age_str = f" ({age_s}s ago)"
                        elif age_s < 3600:
                            age_str = f" ({age_s // 60}m ago)"
                        else:
                            age_str = f" ({age_s // 3600}h ago)"
                    except (ValueError, TypeError):
                        pass
                lines.append(f"  `{mid}`{age_str}")
            if len(miners) > 15:
                lines.append(f"  _...and {len(miners) - 15} more_")
            fields += "\n" + "\n".join(lines)

        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": fields},
            }
        )
        blocks.append({"type": "divider"})

    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"Queried at {_utc_now()}"}],
        }
    )
    respond(blocks=blocks, response_type="in_channel")


# ---------------------------------------------------------------------------
# Background monitor — proactive alerts & daily summary
# ---------------------------------------------------------------------------

class NodeMonitor:
    """Polls nodes on a fixed interval, fires Slack alerts on state changes."""

    def __init__(self, slack_app: App, channel: str, nodes: List[str]):
        self.slack = slack_app.client
        self.channel = channel
        self.nodes = nodes
        self._prev_states: Dict[str, bool] = {}
        self._prev_miner_counts: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._last_stats: Dict[str, Dict[str, Any]] = {}

    # -- health check -------------------------------------------------------

    def check_all(self) -> None:
        """Run one poll cycle across all nodes."""
        if not self.channel:
            return

        for base in self.nodes:
            health = fetch_node_health(base)
            is_ok = health["ok"] and (
                isinstance(health["data"], dict)
                and health["data"].get("ok", True)
            )

            with self._lock:
                prev = self._prev_states.get(base)
                self._prev_states[base] = is_ok

            # State transition alerts
            if prev is not None and prev != is_ok:
                if is_ok:
                    self._post_alert(
                        f":large_green_circle: *Node recovered:* `{base}` at {_utc_now()}"
                    )
                else:
                    reason = health["data"] if isinstance(health["data"], str) else "health check failed"
                    self._post_alert(
                        f":rotating_light: *Node DOWN:* `{base}` — {reason} at {_utc_now()}"
                    )
            elif prev is None and not is_ok:
                reason = health["data"] if isinstance(health["data"], str) else "unreachable"
                self._post_alert(
                    f":rotating_light: *Node DOWN on startup:* `{base}` — {reason} at {_utc_now()}"
                )

            # Miner-count drop detection
            miners_res = fetch_miners(base)
            if miners_res["ok"]:
                miners = _parse_miners_list(miners_res["data"])
                cur_count = len(miners)
                with self._lock:
                    prev_count = self._prev_miner_counts.get(base, cur_count)
                    self._prev_miner_counts[base] = cur_count

                drop = prev_count - cur_count
                if drop >= 2:
                    self._post_alert(
                        f":chart_with_downwards_trend: *Miner count drop* on `{base}`: "
                        f"{prev_count} -> {cur_count} (-{drop}) at {_utc_now()}"
                    )

            # Stash latest stats for daily summary
            stats = fetch_node_stats(base)
            if stats["ok"]:
                with self._lock:
                    self._last_stats[base] = stats["data"]

    # -- daily summary -------------------------------------------------------

    def daily_summary(self) -> None:
        """Post a daily mining summary to the alert channel."""
        if not self.channel:
            return

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Daily RustChain Mining Summary"},
            }
        ]

        with self._lock:
            states = dict(self._prev_states)
            miner_counts = dict(self._prev_miner_counts)
            stats_cache = dict(self._last_stats)

        for base in self.nodes:
            is_up = states.get(base, False)
            status = ":large_green_circle: Up" if is_up else ":red_circle: Down"
            mc = miner_counts.get(base, 0)

            text = f"*Node:* `{base}`\n*Status:* {status}\n*Active miners:* {mc}"

            sd = stats_cache.get(base)
            if isinstance(sd, dict):
                if "epoch" in sd:
                    text += f"\n*Current epoch:* {sd['epoch']}"
                if "total_balance" in sd:
                    text += f"\n*Total RTC distributed:* {sd['total_balance']}"
                if "version" in sd:
                    text += f"\n*Node version:* {sd['version']}"

            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": text},
                }
            )
            blocks.append({"type": "divider"})

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Summary generated at {_utc_now()}",
                    }
                ],
            }
        )

        try:
            self.slack.chat_postMessage(channel=self.channel, blocks=blocks)
        except Exception:
            log.exception("Failed to post daily summary")

    # -- helpers -------------------------------------------------------------

    def _post_alert(self, text: str) -> None:
        try:
            self.slack.chat_postMessage(channel=self.channel, text=text)
        except Exception:
            log.exception("Failed to post alert to %s", self.channel)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    if not SLACK_BOT_TOKEN:
        log.error("SLACK_BOT_TOKEN is not set")
        return 1
    if not SLACK_SIGNING_SECRET:
        log.error("SLACK_SIGNING_SECRET is not set")
        return 1

    monitor = NodeMonitor(app, SLACK_ALERT_CHANNEL, NODE_URLS)

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(monitor.check_all, "interval", seconds=MONITOR_INTERVAL)
    scheduler.add_job(monitor.daily_summary, "cron", hour=12, minute=0)  # noon UTC
    scheduler.start()
    log.info(
        "Background monitor started — polling every %ds, daily summary at 12:00 UTC",
        MONITOR_INTERVAL,
    )

    # Run an initial check immediately
    monitor.check_all()

    if SLACK_APP_TOKEN:
        # Socket Mode (no public URL needed)
        log.info("Starting in Socket Mode")
        handler = SocketModeHandler(app, SLACK_APP_TOKEN)
        handler.start()
    else:
        # HTTP mode — requires a public URL configured in Slack
        port = int(os.environ.get("PORT", "3000"))
        log.info("Starting HTTP server on port %d", port)
        app.start(port=port)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
