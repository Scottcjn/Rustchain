#!/usr/bin/env python3
"""
RustChain TUI Dashboard — real-time terminal dashboard for RustChain network.

Displays network health, epoch/slot progress, active miners, recent blocks,
and wRTC price data in a rich terminal interface with auto-refresh.

Usage:
    python dashboard.py                             # default node
    python dashboard.py -u http://localhost:5000    # custom node
    python dashboard.py --interval 10               # refresh every 10s
"""

from __future__ import annotations

import argparse
import signal
import ssl
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json

from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_NODE = "https://rustchain.org"
WRTC_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
SLOTS_PER_EPOCH = 43200  # default assumption; overridden if API provides it

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def fetch_json(url: str, timeout: int = 8) -> Optional[Any]:
    """GET a URL and return parsed JSON, or None on failure."""
    try:
        req = Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "rustchain-tui-dashboard/1.0",
        })
        with urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            body = resp.read(2 * 1024 * 1024).decode("utf-8", errors="replace")
            return json.loads(body)
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Data collectors
# ---------------------------------------------------------------------------

class RustChainData:
    """Aggregates data from various RustChain API endpoints."""

    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.health: Dict[str, Any] = {}
        self.epoch: Dict[str, Any] = {}
        self.miners: List[Dict[str, Any]] = []
        self.tip: Dict[str, Any] = {}
        self.price: Dict[str, Any] = {}
        self.last_refresh: Optional[datetime] = None
        self.latency_ms: float = 0.0
        self.block_history: List[Dict[str, Any]] = []

    def refresh(self) -> None:
        t0 = time.time()

        self.health = fetch_json(f"{self.base}/health") or {}
        self.epoch = fetch_json(f"{self.base}/epoch") or {}

        miners_raw = fetch_json(f"{self.base}/api/miners")
        if isinstance(miners_raw, list):
            self.miners = miners_raw
        elif isinstance(miners_raw, dict):
            self.miners = miners_raw.get("miners", miners_raw.get("data", []))
        else:
            self.miners = []

        tip = fetch_json(f"{self.base}/headers/tip") or {}
        if tip and tip != self.tip:
            self.block_history.insert(0, {
                "height": tip.get("height", tip.get("block_height", "?")),
                "hash": tip.get("hash", tip.get("block_hash", "?")),
                "timestamp": tip.get("timestamp"),
                "time_seen": datetime.now(timezone.utc),
            })
            self.block_history = self.block_history[:20]
        self.tip = tip

        self.price = self._fetch_price()
        self.latency_ms = (time.time() - t0) * 1000
        self.last_refresh = datetime.now(timezone.utc)

    def _fetch_price(self) -> Dict[str, Any]:
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{WRTC_MINT}"
            data = fetch_json(url)
            if data and "pairs" in data and len(data["pairs"]) > 0:
                pair = data["pairs"][0]
                return {
                    "price_usd": float(pair.get("priceUsd", 0)),
                    "change_24h": float(pair.get("priceChange", {}).get("h24", 0)),
                    "volume_24h": float(pair.get("volume", {}).get("h24", 0)),
                    "liquidity": float(pair.get("liquidity", {}).get("usd", 0)),
                }
        except Exception:
            pass
        return {}

# ---------------------------------------------------------------------------
# Panel builders
# ---------------------------------------------------------------------------

def build_health_panel(data: RustChainData) -> Panel:
    """Network health panel with colored status indicators."""
    h = data.health
    is_healthy = h.get("ok", False)

    lines = Text()

    # Status
    status_str = "HEALTHY" if is_healthy else "DEGRADED"
    status_style = "bold green" if is_healthy else "bold red"
    lines.append("Status:  ", style="dim")
    lines.append(f"● {status_str}\n", style=status_style)

    # Version
    version = h.get("version", "unknown")
    lines.append("Version: ", style="dim")
    lines.append(f"{version}\n", style="cyan")

    # Uptime
    uptime_s = h.get("uptime_s")
    if uptime_s is not None:
        days, rem = divmod(int(uptime_s), 86400)
        hours, rem = divmod(rem, 3600)
        mins, _ = divmod(rem, 60)
        uptime_str = f"{days}d {hours}h {mins}m"
    else:
        uptime_str = "n/a"
    lines.append("Uptime:  ", style="dim")
    lines.append(f"{uptime_str}\n", style="white")

    # DB status
    db_ok = h.get("db_rw")
    if db_ok is not None:
        db_style = "green" if db_ok else "red"
        db_str = "OK" if db_ok else "ERROR"
    else:
        db_style = "yellow"
        db_str = "n/a"
    lines.append("DB R/W:  ", style="dim")
    lines.append(f"{db_str}\n", style=db_style)

    # Latency
    lines.append("Latency: ", style="dim")
    lat = data.latency_ms
    lat_style = "green" if lat < 1000 else ("yellow" if lat < 3000 else "red")
    lines.append(f"{lat:.0f} ms", style=lat_style)

    return Panel(lines, title="[bold]Network Health[/bold]", border_style="green" if is_healthy else "red")


def build_epoch_panel(data: RustChainData) -> Panel:
    """Epoch and slot info with progress bar."""
    e = data.epoch
    epoch_num = e.get("epoch", "?")
    slot = e.get("slot", 0)
    blocks_per_epoch = e.get("blocks_per_epoch", SLOTS_PER_EPOCH)
    epoch_pot = e.get("epoch_pot", "?")
    enrolled = e.get("enrolled_miners", "?")
    supply = e.get("total_supply_rtc", "?")

    progress = min(slot / max(blocks_per_epoch, 1), 1.0) if isinstance(slot, (int, float)) else 0

    lines = Text()
    lines.append("Epoch:    ", style="dim")
    lines.append(f"{epoch_num}\n", style="bold cyan")
    lines.append("Slot:     ", style="dim")
    lines.append(f"{slot}", style="white")
    if isinstance(blocks_per_epoch, (int, float)):
        lines.append(f" / {blocks_per_epoch}", style="dim")
    lines.append("\n")

    # Progress bar
    bar_width = 30
    filled = int(progress * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)
    pct = progress * 100
    color = "green" if pct < 75 else ("yellow" if pct < 90 else "red")
    lines.append("Progress: ", style="dim")
    lines.append(f"{bar} ", style=color)
    lines.append(f"{pct:.1f}%\n", style=color)

    lines.append("\n")
    lines.append("Epoch Pot:       ", style="dim")
    lines.append(f"{epoch_pot} RTC\n", style="yellow")
    lines.append("Enrolled Miners: ", style="dim")
    lines.append(f"{enrolled}\n", style="white")
    lines.append("Total Supply:    ", style="dim")
    if isinstance(supply, (int, float)):
        lines.append(f"{supply:,.2f} RTC", style="white")
    else:
        lines.append(f"{supply} RTC", style="white")

    return Panel(lines, title="[bold]Epoch / Slot[/bold]", border_style="cyan")


def build_miners_panel(data: RustChainData) -> Panel:
    """Active miners table."""
    table = Table(expand=True, show_lines=False, pad_edge=False)
    table.add_column("Miner ID", style="cyan", no_wrap=True, max_width=24)
    table.add_column("Hardware", style="white", max_width=16)
    table.add_column("Arch", style="dim", max_width=12)
    table.add_column("Multiplier", justify="right", style="yellow")

    miners = data.miners[:15]
    if not miners:
        table.add_row("No miners available", "", "", "")
    else:
        for m in miners:
            miner_id = str(m.get("miner_id", m.get("id", "?")))
            if len(miner_id) > 24:
                miner_id = miner_id[:21] + "..."
            hw = str(m.get("hardware_type", m.get("hardware", "?")))
            arch = str(m.get("device_arch", m.get("arch", "?")))
            mult = m.get("antiquity_multiplier", m.get("multiplier", "?"))
            if isinstance(mult, float):
                mult_str = f"{mult:.2f}x"
            else:
                mult_str = str(mult)
            table.add_row(miner_id, hw, arch, mult_str)

    count = len(data.miners)
    title = f"[bold]Active Miners[/bold] [dim]({count} total)[/dim]"
    return Panel(table, title=title, border_style="magenta")


def build_blocks_panel(data: RustChainData) -> Panel:
    """Recent blocks feed."""
    table = Table(expand=True, show_lines=False, pad_edge=False)
    table.add_column("Height", style="bold white", justify="right", max_width=10)
    table.add_column("Hash", style="dim", max_width=20)
    table.add_column("Seen", style="cyan", max_width=12)

    blocks = data.block_history[:10]
    if not blocks:
        # Show current tip at least
        if data.tip:
            height = data.tip.get("height", data.tip.get("block_height", "?"))
            bhash = str(data.tip.get("hash", data.tip.get("block_hash", "?")))
            if len(bhash) > 18:
                bhash = bhash[:8] + "..." + bhash[-7:]
            table.add_row(str(height), bhash, "now")
        else:
            table.add_row("—", "waiting for blocks...", "")
    else:
        for b in blocks:
            height = str(b["height"])
            bhash = str(b["hash"])
            if len(bhash) > 18:
                bhash = bhash[:8] + "..." + bhash[-7:]
            seen = b["time_seen"].strftime("%H:%M:%S")
            table.add_row(height, bhash, seen)

    return Panel(table, title="[bold]Recent Blocks[/bold]", border_style="blue")


def build_price_panel(data: RustChainData) -> Panel:
    """wRTC price ticker panel."""
    p = data.price
    lines = Text()

    if not p:
        lines.append("Price data unavailable", style="dim")
        return Panel(lines, title="[bold]wRTC Price[/bold]", border_style="yellow")

    price_usd = p.get("price_usd", 0)
    change = p.get("change_24h", 0)
    volume = p.get("volume_24h", 0)
    liquidity = p.get("liquidity", 0)

    lines.append("Price:     ", style="dim")
    lines.append(f"${price_usd:.6f}\n", style="bold white")

    lines.append("24h:       ", style="dim")
    ch_style = "green" if change >= 0 else "red"
    arrow = "▲" if change >= 0 else "▼"
    lines.append(f"{arrow} {change:+.2f}%\n", style=ch_style)

    lines.append("Volume:    ", style="dim")
    if volume >= 1_000_000:
        vol_str = f"${volume / 1_000_000:.2f}M"
    elif volume >= 1_000:
        vol_str = f"${volume / 1_000:.1f}K"
    else:
        vol_str = f"${volume:.2f}"
    lines.append(f"{vol_str}\n", style="white")

    lines.append("Liquidity: ", style="dim")
    if liquidity >= 1_000_000:
        liq_str = f"${liquidity / 1_000_000:.2f}M"
    elif liquidity >= 1_000:
        liq_str = f"${liquidity / 1_000:.1f}K"
    else:
        liq_str = f"${liquidity:.2f}"
    lines.append(liq_str, style="white")

    return Panel(lines, title="[bold]wRTC Price[/bold]", border_style="yellow")


def build_header(data: RustChainData, interval: int) -> Panel:
    """Top header bar."""
    t = Text()
    t.append("  RustChain Dashboard", style="bold white")
    t.append("  |  ", style="dim")
    t.append(f"Node: {data.base}", style="cyan")
    t.append("  |  ", style="dim")
    if data.last_refresh:
        t.append(f"Updated: {data.last_refresh.strftime('%H:%M:%S UTC')}", style="dim")
    t.append("  |  ", style="dim")
    t.append(f"Refresh: {interval}s", style="dim")
    t.append("  |  ", style="dim")
    t.append("Ctrl+C to exit", style="dim red")
    return Panel(t, style="bold blue")


def build_layout(data: RustChainData, interval: int) -> Layout:
    """Assemble the full dashboard layout."""
    layout = Layout()

    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="top", size=14),
        Layout(name="bottom"),
    )

    layout["top"].split_row(
        Layout(name="health", ratio=1),
        Layout(name="epoch", ratio=1),
        Layout(name="price", ratio=1),
    )

    layout["bottom"].split_row(
        Layout(name="miners", ratio=3),
        Layout(name="blocks", ratio=2),
    )

    layout["header"].update(build_header(data, interval))
    layout["health"].update(build_health_panel(data))
    layout["epoch"].update(build_epoch_panel(data))
    layout["price"].update(build_price_panel(data))
    layout["miners"].update(build_miners_panel(data))
    layout["blocks"].update(build_blocks_panel(data))

    return layout

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="RustChain TUI Dashboard")
    parser.add_argument("-u", "--url", default=DEFAULT_NODE,
                        help="RustChain node URL (default: %(default)s)")
    parser.add_argument("--interval", type=int, default=5,
                        help="Refresh interval in seconds (default: 5)")
    args = parser.parse_args()

    console = Console()
    data = RustChainData(args.url)

    # Graceful shutdown
    def handle_signal(sig, frame):
        console.print("\n[dim]Dashboard stopped.[/dim]")
        sys.exit(0)
    signal.signal(signal.SIGINT, handle_signal)

    console.print(f"[bold cyan]Starting RustChain Dashboard...[/bold cyan]")
    console.print(f"[dim]Connecting to {args.url}[/dim]\n")

    # Initial data fetch
    data.refresh()

    with Live(build_layout(data, args.interval), console=console,
              refresh_per_second=1, screen=True) as live:
        while True:
            try:
                data.refresh()
                live.update(build_layout(data, args.interval))
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break
            except Exception as e:
                # Keep running even if a single refresh fails
                time.sleep(args.interval)

    console.print("[dim]Dashboard stopped.[/dim]")


if __name__ == "__main__":
    main()
