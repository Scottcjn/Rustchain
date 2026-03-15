"""
RustChain Slack Bot — Real-time notifications and slash commands.

Provides:
  /rtc-status          — Current epoch, slot, and node health
  /rtc-balance <wallet> — Check RTC balance for a wallet
  New block notifications
  Epoch change alerts
  Miner join/leave notifications

Environment variables:
  SLACK_BOT_TOKEN       — Bot User OAuth Token (xoxb-...)
  SLACK_SIGNING_SECRET  — Request signing secret
  SLACK_CHANNEL         — Channel ID for notifications (e.g. C07XXXXXXXX)
  RUSTCHAIN_NODE_URL    — Node URL (default: https://50.28.86.131)
  POLL_INTERVAL         — Seconds between polls (default: 5)
"""

import os
import ssl
import json
import time
import logging
import threading
import urllib.request
from datetime import datetime, timezone

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ─── Configuration ──────────────────────────────────────────────────────────── #

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")  # for Socket Mode
NODE_URL = os.environ.get("RUSTCHAIN_NODE_URL", "https://50.28.86.131")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))

SSL_CTX = ssl._create_unverified_context()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("rustchain-slack")

app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)

# ─── Node API helpers ───────────────────────────────────────────────────────── #


def _fetch(path: str, params: dict | None = None) -> dict | list | None:
    """GET a JSON endpoint from the RustChain node."""
    url = f"{NODE_URL.rstrip('/')}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rustchain-slack-bot/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        log.warning("Node request failed: %s %s", path, exc)
        return None


def _ts_str(ts: float | int | None = None) -> str:
    """Format a timestamp for display."""
    dt = datetime.fromtimestamp(ts or time.time(), tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


# ─── Slash commands ─────────────────────────────────────────────────────────── #


@app.command("/rtc-status")
def handle_status(ack, respond):
    """Return current epoch, slot, height, and node health."""
    ack()

    health = _fetch("/health")
    epoch = _fetch("/epoch")

    if not health and not epoch:
        respond(text=":warning: RustChain node is unreachable.")
        return

    blocks = []

    if health:
        ok = health.get("ok", False)
        version = health.get("version", "unknown")
        uptime = health.get("uptime_s", 0)
        uptime_h = uptime / 3600
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Node Health*\n"
                        f"Status: {'Online' if ok else 'Degraded'}\n"
                        f"Version: `{version}`\n"
                        f"Uptime: {uptime_h:.1f} hours"
                    ),
                },
            }
        )

    if epoch:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Epoch Info*\n"
                        f"Epoch: `{epoch.get('epoch', '?')}`\n"
                        f"Slot: `{epoch.get('slot', '?')}`\n"
                        f"Height: `{epoch.get('height', '?')}`"
                    ),
                },
            }
        )

    respond(
        blocks=[
            {"type": "header", "text": {"type": "plain_text", "text": "RustChain Status"}},
            *blocks,
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"Node: `{NODE_URL}` | {_ts_str()}"}],
            },
        ],
        text="RustChain Status",
    )


@app.command("/rtc-balance")
def handle_balance(ack, respond, command):
    """Check the RTC balance for a given wallet."""
    ack()

    wallet = command.get("text", "").strip()
    if not wallet:
        respond(text="Usage: `/rtc-balance <wallet_name>`")
        return

    data = _fetch("/wallet/balance", params={"miner_id": wallet})

    if data is None:
        respond(text=f":warning: Could not fetch balance for `{wallet}`. Node may be unreachable.")
        return

    amount_rtc = data.get("amount_rtc", data.get("amount_i64", 0) / 1_000_000)
    miner_id = data.get("miner_id", wallet)

    respond(
        blocks=[
            {"type": "header", "text": {"type": "plain_text", "text": "RTC Balance"}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Wallet:* `{miner_id}`\n*Balance:* `{amount_rtc:,.6f} RTC`",
                },
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": _ts_str()}],
            },
        ],
        text=f"Balance for {miner_id}: {amount_rtc} RTC",
    )


# ─── Event monitor (polling) ────────────────────────────────────────────────── #


class ChainMonitor:
    """Polls the RustChain node and posts Slack notifications on state changes."""

    def __init__(self, client, channel: str):
        self.client = client
        self.channel = channel
        self._last_epoch: int | None = None
        self._last_slot: int | None = None
        self._known_miners: set[str] = set()
        self._initialized = False

    # ── Notifications ────────────────────────────────────────────────────── #

    def _post(self, text: str, blocks: list | None = None):
        if not self.channel:
            log.warning("SLACK_CHANNEL not set — skipping notification")
            return
        try:
            self.client.chat_postMessage(channel=self.channel, text=text, blocks=blocks)
        except Exception as exc:
            log.error("Slack post failed: %s", exc)

    def _notify_new_block(self, slot: int, epoch: int | None, height: int | None):
        parts = [f"Slot `{slot}`"]
        if epoch is not None:
            parts.append(f"Epoch `{epoch}`")
        if height is not None:
            parts.append(f"Height `{height}`")
        self._post(
            text=f"New block: slot {slot}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":cube: *New Block*  |  {' | '.join(parts)}",
                    },
                }
            ],
        )

    def _notify_epoch_change(self, old_epoch: int, new_epoch: int, extra: dict):
        reward = extra.get("pot_rtc", extra.get("reward_pot", "?"))
        miners = extra.get("enrolled_miners", extra.get("miners_enrolled", "?"))
        self._post(
            text=f"Epoch changed: {old_epoch} -> {new_epoch}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f":rotating_light: *Epoch Settlement*\n"
                            f"Epoch `{old_epoch}` -> `{new_epoch}`\n"
                            f"Reward pot: `{reward} RTC` | Enrolled miners: `{miners}`"
                        ),
                    },
                }
            ],
        )

    def _notify_miner_join(self, wallet: str, arch: str, multiplier: float):
        self._post(
            text=f"Miner joined: {wallet}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f":pick: *Miner Joined*\n"
                            f"Wallet: `{wallet}` | Arch: `{arch}` | Multiplier: `{multiplier}x`"
                        ),
                    },
                }
            ],
        )

    def _notify_miner_leave(self, wallet: str):
        self._post(
            text=f"Miner left: {wallet}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":wave: *Miner Left*\nWallet: `{wallet}`",
                    },
                }
            ],
        )

    # ── Poll cycle ───────────────────────────────────────────────────────── #

    def poll(self):
        """Run one poll cycle — call from the background thread."""
        # Epoch / block data
        epoch_data = _fetch("/epoch")
        if epoch_data:
            epoch = epoch_data.get("epoch")
            slot = epoch_data.get("slot", epoch_data.get("epoch_slot"))
            height = epoch_data.get("height")

            if slot is not None and slot != self._last_slot:
                if self._initialized:
                    self._notify_new_block(slot, epoch, height)
                self._last_slot = slot

            if epoch is not None and epoch != self._last_epoch:
                if self._initialized and self._last_epoch is not None:
                    self._notify_epoch_change(self._last_epoch, epoch, epoch_data)
                self._last_epoch = epoch

        # Miner roster
        miners_raw = _fetch("/api/miners")
        if miners_raw:
            miners_list = miners_raw if isinstance(miners_raw, list) else miners_raw.get("miners", [])
            current_wallets: dict[str, dict] = {}
            for m in miners_list:
                w = m.get("wallet_name", m.get("wallet", ""))
                if w:
                    current_wallets[w] = m

            current_set = set(current_wallets.keys())

            if self._initialized:
                joined = current_set - self._known_miners
                left = self._known_miners - current_set

                for w in joined:
                    info = current_wallets[w]
                    arch = info.get("hardware_type", info.get("arch", "unknown"))
                    mult = info.get("multiplier", info.get("rtc_multiplier", 1.0))
                    self._notify_miner_join(w, arch, mult)

                for w in left:
                    self._notify_miner_leave(w)

            self._known_miners = current_set

        self._initialized = True


def _monitor_loop(monitor: ChainMonitor):
    """Background polling loop."""
    log.info("Chain monitor started (interval=%ds, channel=%s)", POLL_INTERVAL, monitor.channel)
    while True:
        try:
            monitor.poll()
        except Exception as exc:
            log.error("Monitor poll error: %s", exc)
        time.sleep(POLL_INTERVAL)


# ─── Entrypoint ─────────────────────────────────────────────────────────────── #


def main():
    log.info("Starting RustChain Slack bot")
    log.info("Node: %s | Channel: %s | Poll interval: %ds", NODE_URL, SLACK_CHANNEL, POLL_INTERVAL)

    # Start the chain monitor in a background thread
    if SLACK_CHANNEL:
        monitor = ChainMonitor(client=app.client, channel=SLACK_CHANNEL)
        t = threading.Thread(target=_monitor_loop, args=(monitor,), daemon=True)
        t.start()
    else:
        log.warning("SLACK_CHANNEL not set — notifications disabled (slash commands still work)")

    # Start the Slack bot
    if SLACK_APP_TOKEN:
        handler = SocketModeHandler(app, SLACK_APP_TOKEN)
        handler.start()
    else:
        log.info("No SLACK_APP_TOKEN — starting in HTTP mode on port 3000")
        app.start(port=int(os.environ.get("PORT", "3000")))


if __name__ == "__main__":
    main()
