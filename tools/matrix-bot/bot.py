#!/usr/bin/env python3
"""RustChain Matrix Bot — monitors the RustChain network and responds to commands in Matrix rooms."""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

import requests
from nio import AsyncClient, MatrixRoom, RoomMessageText

# ---------------------------------------------------------------------------
# Configuration (environment variables)
# ---------------------------------------------------------------------------
MATRIX_HOMESERVER = os.getenv("MATRIX_HOMESERVER", "https://matrix.org")
MATRIX_USER = os.getenv("MATRIX_USER", "")
MATRIX_PASSWORD = os.getenv("MATRIX_PASSWORD", "")
MATRIX_ROOM_ID = os.getenv("MATRIX_ROOM_ID", "")

RUSTCHAIN_API = os.getenv("RUSTCHAIN_API", "https://rustchain.org")
DEXSCREENER_PAIR = os.getenv(
    "DEXSCREENER_PAIR",
    "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb",
)

EPOCH_POLL_INTERVAL = int(os.getenv("EPOCH_POLL_INTERVAL", "60"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("rustchain-matrix-bot")

# ---------------------------------------------------------------------------
# RustChain API helpers
# ---------------------------------------------------------------------------

def _get(path: str, params: dict | None = None, timeout: int = 10) -> dict | list | None:
    """GET request to the RustChain node. Returns parsed JSON or None on error."""
    url = f"{RUSTCHAIN_API}{path}"
    try:
        resp = requests.get(url, params=params, timeout=timeout, verify=False)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        log.warning("API request failed: %s — %s", url, exc)
        return None


def fetch_health() -> str:
    """Return a human-readable node health summary."""
    data = _get("/health")
    if data is None:
        return "Could not reach the RustChain node."
    status = data.get("status", "unknown")
    uptime = data.get("uptime", "n/a")
    version = data.get("version", "n/a")
    block_height = data.get("block_height", data.get("blockHeight", "n/a"))
    lines = [
        "RustChain Node Status",
        f"  Status      : {status}",
        f"  Block Height: {block_height}",
        f"  Uptime      : {uptime}",
        f"  Version     : {version}",
    ]
    return "\n".join(lines)


def fetch_balance(wallet: str) -> str:
    """Return the balance for a given wallet/miner_id."""
    data = _get("/wallet/balance", params={"miner_id": wallet})
    if data is None:
        return f"Could not fetch balance for '{wallet}'."
    balance = data.get("balance", data.get("rtc_balance", "n/a"))
    return f"Wallet: {wallet}\nBalance: {balance} RTC"


def fetch_miners() -> str:
    """Return a summary of active miners."""
    data = _get("/api/miners")
    if data is None:
        return "Could not fetch miner list."
    if isinstance(data, list):
        miners = data
    elif isinstance(data, dict):
        miners = data.get("miners", data.get("active_miners", []))
    else:
        return "Unexpected response from /api/miners."

    count = len(miners)
    header = f"Active Miners: {count}"
    if count == 0:
        return header

    lines = [header, ""]
    for m in miners[:15]:
        if isinstance(m, dict):
            name = m.get("miner_id", m.get("wallet", m.get("id", "unknown")))
            hw = m.get("hardware", m.get("hw_type", ""))
            mult = m.get("multiplier", "")
            detail = f"  {name}"
            if hw:
                detail += f" | {hw}"
            if mult:
                detail += f" | {mult}x"
            lines.append(detail)
        else:
            lines.append(f"  {m}")

    if count > 15:
        lines.append(f"  ... and {count - 15} more")
    return "\n".join(lines)


def fetch_epoch() -> str:
    """Return current epoch information."""
    data = _get("/epoch")
    if data is None:
        return "Could not fetch epoch data."
    epoch = data.get("epoch", data.get("current_epoch", "n/a"))
    remaining = data.get("remaining", data.get("time_remaining", "n/a"))
    reward_pool = data.get("reward_pool", data.get("base_reward", "n/a"))
    lines = [
        "Current Epoch Info",
        f"  Epoch       : {epoch}",
        f"  Time Left   : {remaining}s",
        f"  Reward Pool : {reward_pool} RTC",
    ]
    return "\n".join(lines)


def fetch_epoch_number() -> int | None:
    """Return just the epoch number, or None on failure."""
    data = _get("/epoch")
    if data is None:
        return None
    return data.get("epoch", data.get("current_epoch"))


def fetch_price() -> str:
    """Fetch wRTC price from DexScreener."""
    url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{DEXSCREENER_PAIR}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        pair = data.get("pair") or (data.get("pairs") or [None])[0]
        if pair is None:
            return "No pair data found on DexScreener."
        price_usd = pair.get("priceUsd", "n/a")
        price_native = pair.get("priceNative", "n/a")
        volume_24h = pair.get("volume", {}).get("h24", "n/a")
        price_change_24h = pair.get("priceChange", {}).get("h24", "n/a")
        liquidity = pair.get("liquidity", {}).get("usd", "n/a")
        lines = [
            "wRTC Price (DexScreener)",
            f"  USD         : ${price_usd}",
            f"  SOL         : {price_native}",
            f"  24h Volume  : ${volume_24h}",
            f"  24h Change  : {price_change_24h}%",
            f"  Liquidity   : ${liquidity}",
        ]
        return "\n".join(lines)
    except Exception as exc:
        log.warning("DexScreener request failed: %s", exc)
        return "Could not fetch wRTC price from DexScreener."


# ---------------------------------------------------------------------------
# Command dispatcher
# ---------------------------------------------------------------------------

HELP_TEXT = """RustChain Bot Commands:
  !status           — Node health
  !balance <wallet> — Check wallet balance
  !miners           — Active miners
  !epoch            — Current epoch info
  !price            — wRTC price (DexScreener)
  !help             — This message"""


def handle_command(body: str) -> str | None:
    """Parse a message body and return a response string, or None if not a command."""
    parts = body.strip().split()
    if not parts:
        return None

    cmd = parts[0].lower()

    if cmd == "!status":
        return fetch_health()
    elif cmd == "!balance":
        if len(parts) < 2:
            return "Usage: !balance <wallet>"
        return fetch_balance(parts[1])
    elif cmd == "!miners":
        return fetch_miners()
    elif cmd == "!epoch":
        return fetch_epoch()
    elif cmd == "!price":
        return fetch_price()
    elif cmd == "!help":
        return HELP_TEXT
    return None


# ---------------------------------------------------------------------------
# Matrix client
# ---------------------------------------------------------------------------

class RustChainMatrixBot:
    """Async Matrix bot that listens for commands and sends epoch notifications."""

    def __init__(self):
        self.client = AsyncClient(MATRIX_HOMESERVER, MATRIX_USER)
        self.last_epoch: int | None = None
        self._ready = False

    async def login(self):
        resp = await self.client.login(MATRIX_PASSWORD)
        if hasattr(resp, "access_token"):
            log.info("Logged in as %s", MATRIX_USER)
        else:
            log.error("Login failed: %s", resp)
            sys.exit(1)

    async def on_message(self, room: MatrixRoom, event: RoomMessageText):
        # Ignore messages from ourselves or before bot was ready
        if event.sender == self.client.user_id:
            return
        if not self._ready:
            return

        response = handle_command(event.body)
        if response:
            await self.client.room_send(
                room_id=room.room_id,
                message_type="m.room.message",
                content={"msgtype": "m.text", "body": response},
            )

    async def epoch_monitor(self):
        """Poll the epoch endpoint and notify the room when a new epoch starts."""
        while True:
            await asyncio.sleep(EPOCH_POLL_INTERVAL)
            current = fetch_epoch_number()
            if current is None:
                continue
            if self.last_epoch is not None and current != self.last_epoch:
                msg = f"New epoch started: {current} (previous: {self.last_epoch})"
                log.info(msg)
                if MATRIX_ROOM_ID:
                    try:
                        await self.client.room_send(
                            room_id=MATRIX_ROOM_ID,
                            message_type="m.room.message",
                            content={"msgtype": "m.notice", "body": msg},
                        )
                    except Exception as exc:
                        log.warning("Failed to send epoch notification: %s", exc)
            self.last_epoch = current

    async def run(self):
        await self.login()
        # Join the configured room if specified
        if MATRIX_ROOM_ID:
            await self.client.join(MATRIX_ROOM_ID)
            log.info("Joined room %s", MATRIX_ROOM_ID)

        # Do an initial sync so we don't replay old messages
        await self.client.sync(timeout=10000, full_state=True)
        self._ready = True

        # Register the message callback
        self.client.add_event_callback(self.on_message, RoomMessageText)

        # Seed the epoch tracker
        self.last_epoch = fetch_epoch_number()
        log.info("Initial epoch: %s", self.last_epoch)

        # Run the sync loop and epoch monitor concurrently
        log.info("Bot is running. Listening for commands...")
        await asyncio.gather(
            self.client.sync_forever(timeout=30000),
            self.epoch_monitor(),
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if not MATRIX_USER or not MATRIX_PASSWORD:
        print("Error: MATRIX_USER and MATRIX_PASSWORD environment variables are required.")
        print("See README.md for configuration details.")
        sys.exit(1)

    # Suppress urllib3 InsecureRequestWarning for self-signed certs on the node
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    bot = RustChainMatrixBot()
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
