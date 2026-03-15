#!/usr/bin/env python3
"""
RustChain IRC Bot

Lightweight IRC bot for RustChain network monitoring.
Uses only Python standard library — zero external dependencies.

Commands:
    !status             Node health overview
    !balance <wallet>   Check wallet balance
    !miners             Active miner count and details
    !epoch              Current epoch information
    !price              wRTC / RTC price from DexScreener

Configuration via environment variables:
    IRC_SERVER          IRC server hostname  (default: irc.libera.chat)
    IRC_PORT            IRC server port      (default: 6697)
    IRC_USE_SSL         Enable TLS           (default: true)
    IRC_NICK            Bot nickname         (default: RustChainBot)
    IRC_CHANNEL         Channel to join      (default: #rustchain)
    RUSTCHAIN_NODE_URL  Node API base URL    (default: https://rustchain.org)
"""

from __future__ import annotations

import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

IRC_SERVER = os.environ.get("IRC_SERVER", "irc.libera.chat")
IRC_PORT = int(os.environ.get("IRC_PORT", "6697"))
IRC_USE_SSL = os.environ.get("IRC_USE_SSL", "true").lower() in ("true", "1", "yes")
IRC_NICK = os.environ.get("IRC_NICK", "RustChainBot")
IRC_CHANNEL = os.environ.get("IRC_CHANNEL", "#rustchain")
NODE_URL = os.environ.get("RUSTCHAIN_NODE_URL", "https://rustchain.org").rstrip("/")

DEXSCREENER_WRTC = (
    "https://api.dexscreener.com/latest/dex/tokens/"
    "B1Nqo1RH6gBSk4DNcomYrGDAMBh9GHxQALaz1P1Cpump"
)

RECONNECT_DELAY = 30
HTTP_TIMEOUT = 10
CMD_COOLDOWN = 3          # seconds between identical commands

# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------

_ssl_ctx: Optional[ssl.SSLContext] = None


def _get_ssl_ctx() -> ssl.SSLContext:
    global _ssl_ctx
    if _ssl_ctx is None:
        _ssl_ctx = ssl.create_default_context()
        _ssl_ctx.check_hostname = False
        _ssl_ctx.verify_mode = ssl.CERT_NONE
    return _ssl_ctx


def http_get_json(url: str, timeout: int = HTTP_TIMEOUT) -> Tuple[bool, Any]:
    """GET *url* and return (ok, parsed_json)."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "rustchain-irc-bot/1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout, context=_get_ssl_ctx()) as r:
            body = r.read(1024 * 1024).decode("utf-8", errors="replace")
            return True, json.loads(body)
    except Exception:
        return False, None

# ---------------------------------------------------------------------------
# RustChain API wrappers
# ---------------------------------------------------------------------------


def fetch_status() -> str:
    """!status — node health summary."""
    ok_health, health = http_get_json(f"{NODE_URL}/health")
    ok_tip, tip = http_get_json(f"{NODE_URL}/headers/tip")

    parts: List[str] = []

    if ok_health and isinstance(health, dict):
        status = health.get("status", "unknown")
        version = health.get("version", "?")
        uptime = health.get("uptime", "?")
        parts.append(f"Status: {status} | Version: {version} | Uptime: {uptime}")
    else:
        parts.append("Node /health endpoint unreachable")

    if ok_tip and isinstance(tip, dict):
        height = tip.get("height", "?")
        ts = tip.get("timestamp", "?")
        parts.append(f"Chain tip: block {height} ({ts})")

    return " | ".join(parts) if parts else "Unable to reach RustChain node"


def fetch_balance(wallet: str) -> str:
    """!balance <wallet> — check wallet balance."""
    if not wallet or len(wallet) < 10:
        return "Usage: !balance <wallet_address>"

    ok, data = http_get_json(f"{NODE_URL}/api/balance/{wallet}")
    if not ok or data is None:
        return f"Could not retrieve balance for {wallet[:12]}..."

    if isinstance(data, dict):
        balance = data.get("balance", data.get("amount", "?"))
        pending = data.get("pending", None)
        msg = f"Balance for {wallet[:12]}...: {balance} RTC"
        if pending is not None:
            msg += f" (pending: {pending} RTC)"
        return msg

    return f"Balance for {wallet[:12]}...: {data}"


def fetch_miners() -> str:
    """!miners — active miner count."""
    ok, data = http_get_json(f"{NODE_URL}/api/miners")
    if not ok or data is None:
        return "Could not retrieve miner information"

    if isinstance(data, dict):
        count = data.get("count", data.get("total", data.get("active", "?")))
        attestation = data.get("last_attestation", None)
        msg = f"Active miners: {count}"
        if attestation:
            msg += f" | Last attestation: {attestation}"
        return msg

    if isinstance(data, list):
        return f"Active miners: {len(data)}"

    return f"Miners: {data}"


def fetch_epoch() -> str:
    """!epoch — current epoch info."""
    ok, data = http_get_json(f"{NODE_URL}/epoch")
    if not ok or data is None:
        return "Could not retrieve epoch information"

    if isinstance(data, dict):
        epoch = data.get("epoch", data.get("current_epoch", "?"))
        start = data.get("start_block", data.get("start", "?"))
        end = data.get("end_block", data.get("end", "?"))
        reward = data.get("reward", data.get("block_reward", None))
        msg = f"Epoch {epoch} | Blocks {start}-{end}"
        if reward is not None:
            msg += f" | Reward: {reward} RTC"
        return msg

    return f"Epoch: {data}"


def fetch_price() -> str:
    """!price — wRTC price from DexScreener."""
    ok, data = http_get_json(DEXSCREENER_WRTC)
    if not ok or data is None:
        return "Could not fetch wRTC price data"

    try:
        pairs = data.get("pairs", [])
        if not pairs:
            return "No trading pairs found for wRTC"

        pair = pairs[0]
        price_usd = pair.get("priceUsd", "?")
        price_native = pair.get("priceNative", "?")
        change_24h = pair.get("priceChange", {}).get("h24", "?")
        volume_24h = pair.get("volume", {}).get("h24", "?")
        liquidity = pair.get("liquidity", {}).get("usd", "?")
        dex = pair.get("dexId", "?")

        parts = [f"wRTC ${price_usd} USD"]
        if price_native != "?":
            parts.append(f"{price_native} SOL")
        if change_24h != "?":
            parts.append(f"24h: {change_24h}%")
        if volume_24h != "?":
            parts.append(f"Vol: ${volume_24h}")
        if liquidity != "?":
            parts.append(f"Liq: ${liquidity}")
        if dex != "?":
            parts.append(f"DEX: {dex}")

        return " | ".join(parts)
    except Exception:
        return "Error parsing wRTC price data"

# ---------------------------------------------------------------------------
# Command dispatcher
# ---------------------------------------------------------------------------

COMMANDS = {
    "!status":  (lambda _args: fetch_status(),          "Node health overview"),
    "!balance": (lambda args: fetch_balance(args),      "Check wallet balance"),
    "!miners":  (lambda _args: fetch_miners(),          "Active miner count"),
    "!epoch":   (lambda _args: fetch_epoch(),           "Current epoch info"),
    "!price":   (lambda _args: fetch_price(),           "wRTC / RTC price"),
}

_last_cmd: Dict[str, float] = {}


def handle_command(text: str) -> Optional[str]:
    """Parse a message and return a response, or None if not a command."""
    text = text.strip()
    if not text.startswith("!"):
        return None

    parts = text.split(None, 1)
    cmd = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "!help":
        lines = ["RustChain IRC Bot commands:"]
        for name, (_, desc) in sorted(COMMANDS.items()):
            lines.append(f"  {name:12s} {desc}")
        return " | ".join(lines)

    handler = COMMANDS.get(cmd)
    if handler is None:
        return None

    # Rate-limit identical commands
    now = time.time()
    if cmd in _last_cmd and (now - _last_cmd[cmd]) < CMD_COOLDOWN:
        return None
    _last_cmd[cmd] = now

    fn, _ = handler
    try:
        return fn(args)
    except Exception as exc:
        return f"Error processing {cmd}: {exc}"

# ---------------------------------------------------------------------------
# IRC protocol layer
# ---------------------------------------------------------------------------

_PRIVMSG_RE = re.compile(
    r"^:(\S+)!\S+\s+PRIVMSG\s+(\S+)\s+:(.*)"
)


class IRCBot:
    """Minimal IRC client with TLS support."""

    def __init__(
        self,
        server: str = IRC_SERVER,
        port: int = IRC_PORT,
        use_ssl: bool = IRC_USE_SSL,
        nick: str = IRC_NICK,
        channel: str = IRC_CHANNEL,
    ):
        self.server = server
        self.port = port
        self.use_ssl = use_ssl
        self.nick = nick
        self.channel = channel
        self._sock: Optional[socket.socket] = None
        self._file = None

    # -- low-level I/O -------------------------------------------------------

    def _connect(self) -> None:
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw.settimeout(300)

        if self.use_ssl:
            ctx = ssl.create_default_context()
            self._sock = ctx.wrap_socket(raw, server_hostname=self.server)
        else:
            self._sock = raw

        self._sock.connect((self.server, self.port))
        self._file = self._sock.makefile("r", encoding="utf-8", errors="replace")
        self._log(f"Connected to {self.server}:{self.port}")

    def _send(self, data: str) -> None:
        if self._sock is None:
            return
        line = data if data.endswith("\r\n") else data + "\r\n"
        self._sock.sendall(line.encode("utf-8"))

    def _recv_line(self) -> Optional[str]:
        if self._file is None:
            return None
        line = self._file.readline()
        return line.rstrip("\r\n") if line else None

    @staticmethod
    def _log(msg: str) -> None:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        print(f"[{ts}] {msg}", flush=True)

    # -- IRC commands ---------------------------------------------------------

    def _register(self) -> None:
        self._send(f"NICK {self.nick}")
        self._send(f"USER {self.nick} 0 * :RustChain IRC Bot")

    def _join(self) -> None:
        self._send(f"JOIN {self.channel}")
        self._log(f"Joined {self.channel}")

    def _privmsg(self, target: str, text: str) -> None:
        # IRC line limit ~510 bytes; split long messages
        max_len = 400
        for i in range(0, len(text), max_len):
            self._send(f"PRIVMSG {target} :{text[i:i+max_len]}")

    def _pong(self, payload: str) -> None:
        self._send(f"PONG :{payload}")

    # -- main loop ------------------------------------------------------------

    def _handle_line(self, line: str) -> None:
        if line.startswith("PING"):
            payload = line.split(":", 1)[1] if ":" in line else line.split(None, 1)[-1]
            self._pong(payload)
            return

        # Numeric 376 (end of MOTD) or 422 (no MOTD) → join channel
        parts = line.split()
        if len(parts) >= 2 and parts[1] in ("376", "422"):
            self._join()
            return

        # PRIVMSG handling
        m = _PRIVMSG_RE.match(line)
        if m:
            sender, target, message = m.group(1), m.group(2), m.group(3)
            reply_to = target if target.startswith("#") else sender

            response = handle_command(message)
            if response:
                self._privmsg(reply_to, response)

    def run(self) -> None:
        """Connect and loop forever, reconnecting on errors."""
        while True:
            try:
                self._connect()
                self._register()

                while True:
                    line = self._recv_line()
                    if line is None:
                        self._log("Connection lost (EOF)")
                        break
                    self._handle_line(line)

            except KeyboardInterrupt:
                self._log("Shutting down")
                if self._sock:
                    self._send("QUIT :Bye")
                    self._sock.close()
                sys.exit(0)

            except Exception as exc:
                self._log(f"Error: {exc}")

            finally:
                if self._sock:
                    try:
                        self._sock.close()
                    except Exception:
                        pass
                    self._sock = None
                    self._file = None

            self._log(f"Reconnecting in {RECONNECT_DELAY}s...")
            time.sleep(RECONNECT_DELAY)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("RustChain IRC Bot", flush=True)
    print(f"  Server:  {IRC_SERVER}:{IRC_PORT} (SSL={IRC_USE_SSL})", flush=True)
    print(f"  Nick:    {IRC_NICK}", flush=True)
    print(f"  Channel: {IRC_CHANNEL}", flush=True)
    print(f"  Node:    {NODE_URL}", flush=True)
    print(flush=True)
    bot = IRCBot()
    bot.run()


if __name__ == "__main__":
    main()
