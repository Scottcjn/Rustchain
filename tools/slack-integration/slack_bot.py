#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
RustChain Slack Integration Bot

Slack slash commands and automated alerts for RustChain network monitoring.

Commands:
  /rtc-status  - Network status (block height, epoch, peers, TPS)
  /rtc-balance - Check wallet balance
  /rtc-miners  - Active miners and hashrate breakdown

Features:
  - Auto-alerts on missed blocks, peer drops, and fork detection
  - Daily summary posted at configurable time
  - Rate limiting per user/channel
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RUSTCHAIN_API = os.getenv("RUSTCHAIN_API_URL", "https://rustchain.org")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
ALERTS_CHANNEL = os.getenv("SLACK_ALERTS_CHANNEL", "#rustchain-alerts")
DAILY_SUMMARY_CHANNEL = os.getenv("SLACK_SUMMARY_CHANNEL", "#rustchain-daily")
DAILY_SUMMARY_HOUR = int(os.getenv("DAILY_SUMMARY_HOUR_UTC", "14"))
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_PER_MINUTE", "15"))

# Alert thresholds
MISSED_BLOCK_THRESHOLD = int(os.getenv("MISSED_BLOCK_THRESHOLD", "3"))
PEER_DROP_THRESHOLD = int(os.getenv("PEER_DROP_THRESHOLD", "5"))
MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL_SECONDS", "60"))

# DexScreener for wRTC price
WRTC_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
DEXSCREENER_API = f"https://api.dexscreener.com/latest/dex/tokens/{WRTC_MINT}"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("rustchain_slack")

# ---------------------------------------------------------------------------
# Slack app
# ---------------------------------------------------------------------------

app = AsyncApp(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGNING_SECRET,
)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

_user_hits: dict[str, list[float]] = {}


def _rate_ok(user_id: str) -> bool:
    now = time.time()
    hits = _user_hits.setdefault(user_id, [])
    hits[:] = [t for t in hits if t > now - 60]
    if len(hits) >= RATE_LIMIT_RPM:
        return False
    hits.append(now)
    return True


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

_http = httpx.AsyncClient(verify=False, timeout=15.0)


async def _api_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{RUSTCHAIN_API.rstrip('/')}{path}"
    try:
        r = await _http.get(url, params=params)
        r.raise_for_status()
        return r.json()
    except httpx.TimeoutException:
        return {"error": "Request timed out — node may be unreachable."}
    except httpx.HTTPStatusError as exc:
        return {"error": f"HTTP {exc.response.status_code}"}
    except Exception as exc:
        log.error("API error %s: %s", path, exc)
        return {"error": str(exc)}


async def _get_price_data() -> dict[str, Any] | None:
    """Fetch wRTC price from DexScreener."""
    try:
        r = await _http.get(DEXSCREENER_API, timeout=10.0)
        r.raise_for_status()
        data = r.json()
        pairs = data.get("pairs", [])
        if not pairs:
            return None
        pair = next((p for p in pairs if p.get("dexId") == "raydium"), pairs[0])
        return {
            "price_usd": float(pair.get("priceUsd", 0)),
            "h24_change": pair.get("priceChange", {}).get("h24", 0),
            "volume_h24": pair.get("volume", {}).get("h24", 0),
            "liquidity_usd": pair.get("liquidity", {}).get("usd", 0),
        }
    except Exception as exc:
        log.error("Price fetch error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Block formatting helpers
# ---------------------------------------------------------------------------

def _status_blocks(data: dict[str, Any]) -> list[dict]:
    """Build Slack Block Kit blocks for /rtc-status."""
    if "error" in data:
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": f":warning: *Error:* {data['error']}"}},
        ]

    height = data.get("block_height", "N/A")
    epoch = data.get("epoch", "N/A")
    peers = data.get("peers", "N/A")
    tps = data.get("tps", "N/A")
    uptime = data.get("uptime", "N/A")
    consensus = data.get("consensus", "Proof-of-Antiquity")

    return [
        {"type": "header", "text": {"type": "plain_text", "text": "RustChain Network Status"}},
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Block Height:*\n`{height}`"},
                {"type": "mrkdwn", "text": f"*Epoch:*\n`{epoch}`"},
                {"type": "mrkdwn", "text": f"*Connected Peers:*\n`{peers}`"},
                {"type": "mrkdwn", "text": f"*TPS:*\n`{tps}`"},
                {"type": "mrkdwn", "text": f"*Uptime:*\n`{uptime}`"},
                {"type": "mrkdwn", "text": f"*Consensus:*\n`{consensus}`"},
            ],
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Queried at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"},
            ],
        },
    ]


def _balance_blocks(address: str, data: dict[str, Any]) -> list[dict]:
    """Build blocks for /rtc-balance."""
    if "error" in data:
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": f":warning: *Error:* {data['error']}"}},
        ]

    balance = data.get("balance", "0")
    pending = data.get("pending", "0")
    staked = data.get("staked", "0")
    tx_count = data.get("tx_count", 0)

    return [
        {"type": "header", "text": {"type": "plain_text", "text": "RTC Wallet Balance"}},
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Wallet:* `{address}`"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Available:*\n`{balance} RTC`"},
                {"type": "mrkdwn", "text": f"*Pending:*\n`{pending} RTC`"},
                {"type": "mrkdwn", "text": f"*Staked:*\n`{staked} RTC`"},
                {"type": "mrkdwn", "text": f"*Transactions:*\n`{tx_count}`"},
            ],
        },
    ]


def _miners_blocks(data: dict[str, Any]) -> list[dict]:
    """Build blocks for /rtc-miners."""
    if "error" in data:
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": f":warning: *Error:* {data['error']}"}},
        ]

    active = data.get("active_miners", "N/A")
    hashrate = data.get("total_hashrate", "N/A")
    difficulty = data.get("difficulty", "N/A")
    last_block_miner = data.get("last_block_miner", "N/A")

    # Architecture breakdown if available
    arch_breakdown = data.get("architecture_breakdown", {})
    arch_lines = []
    for arch, count in arch_breakdown.items():
        arch_lines.append(f"  • {arch}: {count}")
    arch_text = "\n".join(arch_lines) if arch_lines else "  _No breakdown available_"

    return [
        {"type": "header", "text": {"type": "plain_text", "text": "RustChain Miners"}},
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Active Miners:*\n`{active}`"},
                {"type": "mrkdwn", "text": f"*Total Hashrate:*\n`{hashrate}`"},
                {"type": "mrkdwn", "text": f"*Difficulty:*\n`{difficulty}`"},
                {"type": "mrkdwn", "text": f"*Last Block By:*\n`{last_block_miner}`"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Architecture Breakdown:*\n{arch_text}"},
        },
    ]


# ---------------------------------------------------------------------------
# Slash commands
# ---------------------------------------------------------------------------

@app.command("/rtc-status")
async def handle_status(ack, command):
    """Network status: block height, epoch, peers, TPS."""
    await ack()
    user_id = command["user_id"]
    if not _rate_ok(user_id):
        await app.client.chat_postEphemeral(
            channel=command["channel_id"],
            user=user_id,
            text="Rate limit reached — try again in a minute.",
        )
        return

    data = await _api_get("/api/v1/status")
    blocks = _status_blocks(data)
    await app.client.chat_postMessage(
        channel=command["channel_id"],
        blocks=blocks,
        text="RustChain Network Status",
    )


@app.command("/rtc-balance")
async def handle_balance(ack, command):
    """Check wallet balance. Usage: /rtc-balance <wallet_address>"""
    await ack()
    user_id = command["user_id"]
    if not _rate_ok(user_id):
        await app.client.chat_postEphemeral(
            channel=command["channel_id"],
            user=user_id,
            text="Rate limit reached — try again in a minute.",
        )
        return

    address = command.get("text", "").strip()
    if not address:
        await app.client.chat_postEphemeral(
            channel=command["channel_id"],
            user=user_id,
            text="Usage: `/rtc-balance <wallet_address>`",
        )
        return

    data = await _api_get(f"/api/v1/balance/{address}")
    blocks = _balance_blocks(address, data)
    await app.client.chat_postMessage(
        channel=command["channel_id"],
        blocks=blocks,
        text=f"Balance for {address}",
    )


@app.command("/rtc-miners")
async def handle_miners(ack, command):
    """Active miners and hashrate breakdown."""
    await ack()
    user_id = command["user_id"]
    if not _rate_ok(user_id):
        await app.client.chat_postEphemeral(
            channel=command["channel_id"],
            user=user_id,
            text="Rate limit reached — try again in a minute.",
        )
        return

    data = await _api_get("/api/v1/miners")
    blocks = _miners_blocks(data)
    await app.client.chat_postMessage(
        channel=command["channel_id"],
        blocks=blocks,
        text="RustChain Miners",
    )


# ---------------------------------------------------------------------------
# Auto-alerts (background monitor)
# ---------------------------------------------------------------------------

_prev_height: int | None = None
_prev_peers: int | None = None


async def _check_alerts():
    """Poll the node and fire alerts when thresholds are breached."""
    global _prev_height, _prev_peers

    data = await _api_get("/api/v1/status")
    if "error" in data:
        log.warning("Alert check failed: %s", data["error"])
        return

    height = data.get("block_height")
    peers = data.get("peers")

    # Missed-block alert
    if _prev_height is not None and height is not None:
        if height == _prev_height:
            log.warning("No new block since last check (height %s)", height)
        missed = height - _prev_height
        if missed < 0:
            await _post_alert(
                ":rotating_light: *Fork detected* — block height went from "
                f"`{_prev_height}` to `{height}`. Possible chain reorganization."
            )

    # Peer-drop alert
    if _prev_peers is not None and peers is not None:
        drop = _prev_peers - peers
        if drop >= PEER_DROP_THRESHOLD:
            await _post_alert(
                f":warning: *Peer count dropped* from `{_prev_peers}` to `{peers}` "
                f"(-{drop} in {MONITOR_INTERVAL}s)."
            )

    _prev_height = height
    _prev_peers = peers


async def _post_alert(text: str):
    """Send an alert message to the alerts channel."""
    try:
        await app.client.chat_postMessage(
            channel=ALERTS_CHANNEL,
            text=text,
            mrkdwn=True,
        )
        log.info("Alert posted: %s", text[:80])
    except Exception as exc:
        log.error("Failed to post alert: %s", exc)


# ---------------------------------------------------------------------------
# Daily summary
# ---------------------------------------------------------------------------

async def _post_daily_summary():
    """Compile and post the daily network summary."""
    status = await _api_get("/api/v1/status")
    miners = await _api_get("/api/v1/miners")
    price = await _get_price_data()

    lines = [
        ":newspaper: *RustChain Daily Summary*",
        f"_{datetime.now(timezone.utc).strftime('%A, %B %d %Y — %H:%M UTC')}_",
        "",
    ]

    # Network
    if "error" not in status:
        lines += [
            "*Network*",
            f"  Block height: `{status.get('block_height', 'N/A')}`",
            f"  Epoch: `{status.get('epoch', 'N/A')}`",
            f"  Peers: `{status.get('peers', 'N/A')}`",
            f"  TPS: `{status.get('tps', 'N/A')}`",
            "",
        ]
    else:
        lines += ["*Network:* _unavailable_", ""]

    # Miners
    if "error" not in miners:
        lines += [
            "*Mining*",
            f"  Active miners: `{miners.get('active_miners', 'N/A')}`",
            f"  Hashrate: `{miners.get('total_hashrate', 'N/A')}`",
            f"  Difficulty: `{miners.get('difficulty', 'N/A')}`",
            "",
        ]
    else:
        lines += ["*Mining:* _unavailable_", ""]

    # Price
    if price:
        change = price.get("h24_change", 0)
        arrow = ":chart_with_upwards_trend:" if change >= 0 else ":chart_with_downwards_trend:"
        lines += [
            "*wRTC Price*",
            f"  Price: `${price['price_usd']:.4f}`",
            f"  24h change: `{change}%` {arrow}",
            f"  24h volume: `${price.get('volume_h24', 0):,.0f}`",
            "",
        ]

    try:
        await app.client.chat_postMessage(
            channel=DAILY_SUMMARY_CHANNEL,
            text="\n".join(lines),
            mrkdwn=True,
        )
        log.info("Daily summary posted.")
    except Exception as exc:
        log.error("Failed to post daily summary: %s", exc)


# ---------------------------------------------------------------------------
# Background loops
# ---------------------------------------------------------------------------

async def _monitor_loop():
    """Run alert checks on an interval."""
    while True:
        try:
            await _check_alerts()
        except Exception as exc:
            log.error("Monitor loop error: %s", exc)
        await asyncio.sleep(MONITOR_INTERVAL)


async def _daily_summary_loop():
    """Post daily summary at the configured hour (UTC)."""
    while True:
        now = datetime.now(timezone.utc)
        # Seconds until the next target hour
        target = now.replace(hour=DAILY_SUMMARY_HOUR, minute=0, second=0, microsecond=0)
        if now >= target:
            target = target.replace(day=target.day + 1)
        wait = (target - now).total_seconds()
        log.info("Next daily summary in %.0f seconds", wait)
        await asyncio.sleep(wait)
        await _post_daily_summary()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def main():
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        log.error(
            "SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set. "
            "See README.md for setup instructions."
        )
        sys.exit(1)

    handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)

    # Start background tasks
    asyncio.create_task(_monitor_loop())
    asyncio.create_task(_daily_summary_loop())

    log.info("RustChain Slack bot starting (Socket Mode)...")
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
