#!/usr/bin/env python3
"""
RustChain Attestation Node Health Monitor
Monitors all 3 attestation nodes and reports network health.

Usage:
    python node_health_monitor.py              # pretty-printed status table
    python node_health_monitor.py --json       # machine-readable JSON
    python node_health_monitor.py --watch 10   # refresh every 10 seconds
    python node_health_monitor.py --alert      # only print if something is wrong (cron-safe)
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

# ── ANSI color codes ─────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
CYAN   = "\033[96m"
DIM    = "\033[2m"

# ── Thresholds ────────────────────────────────────────────────────────────────
SLOW_THRESHOLD_MS = 1000   # response times above this are "yellow"
REQUEST_TIMEOUT   = 5      # seconds per HTTP request

# ── Known attestation nodes ───────────────────────────────────────────────────
DEFAULT_NODES = [
    "http://50.28.86.131:8088",
    "http://50.28.86.153:8088",
    "http://76.8.228.245:8099",
]


@dataclass
class NodeStatus:
    url: str
    status: str           # "online" | "slow" | "offline"
    response_time_ms: Optional[float]
    epoch: Optional[int]
    miners: Optional[int]
    error: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NetworkHealth:
    nodes_online: int
    total_nodes: int
    total_miners: int
    consensus_ok: bool
    split_brain: bool
    alerts: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NodeHealthMonitor:
    """Monitors RustChain attestation nodes for health, consensus, and split-brain."""

    def __init__(self, nodes: Optional[List[str]] = None, timeout: int = REQUEST_TIMEOUT):
        self.nodes = nodes or DEFAULT_NODES
        self.timeout = timeout

    # ── Per-node check ────────────────────────────────────────────────────────

    def check_node(self, url: str) -> NodeStatus:
        """
        Probe a single node. Returns a NodeStatus with:
          status            "online" | "slow" | "offline"
          response_time_ms  round-trip in milliseconds (None if unreachable)
          epoch             current epoch number from node (None if unavailable)
          miners            active miner count (None if unavailable)
          error             error message string (None if OK)
        """
        start = time.monotonic()
        try:
            req = urllib.request.Request(
                f"{url}/status",
                headers={"Accept": "application/json", "User-Agent": "RustChain-HealthMonitor/1.0"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                elapsed_ms = (time.monotonic() - start) * 1000
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {}

                epoch  = data.get("epoch") or data.get("current_epoch")
                miners = data.get("miners") or data.get("active_miners") or data.get("miner_count")

                # Coerce to int if present
                if epoch  is not None: epoch  = int(epoch)
                if miners is not None: miners = int(miners)

                status = "slow" if elapsed_ms > SLOW_THRESHOLD_MS else "online"
                return NodeStatus(
                    url=url,
                    status=status,
                    response_time_ms=round(elapsed_ms, 1),
                    epoch=epoch,
                    miners=miners,
                    error=None,
                )

        except urllib.error.HTTPError as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            # Node replied but with an error code — treat as degraded
            return NodeStatus(
                url=url,
                status="slow",
                response_time_ms=round(elapsed_ms, 1),
                epoch=None,
                miners=None,
                error=f"HTTP {exc.code}: {exc.reason}",
            )
        except Exception as exc:  # noqa: BLE001  (timeout, connection refused, etc.)
            return NodeStatus(
                url=url,
                status="offline",
                response_time_ms=None,
                epoch=None,
                miners=None,
                error=str(exc),
            )

    # ── Multi-node checks ─────────────────────────────────────────────────────

    def check_all(self) -> List[NodeStatus]:
        """Check every known node and return a list of NodeStatus objects."""
        return [self.check_node(url) for url in self.nodes]

    # ── Network-level health ──────────────────────────────────────────────────

    def get_network_health(self, statuses: Optional[List[NodeStatus]] = None) -> NetworkHealth:
        """
        Aggregate per-node statuses into a NetworkHealth summary.
        consensus_ok is True when ALL online nodes report the same epoch.
        """
        if statuses is None:
            statuses = self.check_all()

        online = [s for s in statuses if s.status != "offline"]
        nodes_online = len(online)
        total_miners = sum(s.miners or 0 for s in online)

        epochs = {s.epoch for s in online if s.epoch is not None}
        consensus_ok = len(epochs) <= 1  # 0 or 1 distinct epoch → consensus holds
        split_brain  = self.detect_split_brain(statuses)

        alerts: List[str] = []
        offline_nodes = [s for s in statuses if s.status == "offline"]
        slow_nodes    = [s for s in statuses if s.status == "slow"]

        if offline_nodes:
            urls = ", ".join(s.url for s in offline_nodes)
            alerts.append(f"Node(s) offline: {urls}")
        if slow_nodes:
            urls = ", ".join(f"{s.url} ({s.response_time_ms:.0f}ms)" for s in slow_nodes)
            alerts.append(f"Slow response from: {urls}")
        if split_brain:
            alerts.append(f"SPLIT BRAIN detected — divergent epochs: {sorted(epochs)}")
        if nodes_online == 0:
            alerts.append("ALL NODES OFFLINE — network unreachable")

        return NetworkHealth(
            nodes_online=nodes_online,
            total_nodes=len(statuses),
            total_miners=total_miners,
            consensus_ok=consensus_ok,
            split_brain=split_brain,
            alerts=alerts,
        )

    def detect_split_brain(self, statuses: Optional[List[NodeStatus]] = None) -> bool:
        """
        Return True if two or more online nodes report different epoch numbers.
        A single online node (or none) cannot produce a split brain.
        """
        if statuses is None:
            statuses = self.check_all()
        epochs = {s.epoch for s in statuses if s.status != "offline" and s.epoch is not None}
        return len(epochs) > 1


# ── Rendering helpers ─────────────────────────────────────────────────────────

def _color_status(status: str) -> str:
    if status == "online":
        return f"{GREEN}{BOLD}●  online{RESET}"
    if status == "slow":
        return f"{YELLOW}{BOLD}◐   slow{RESET}"
    return f"{RED}{BOLD}○ offline{RESET}"


def _color_ms(ms: Optional[float]) -> str:
    if ms is None:
        return f"{DIM}     —{RESET}"
    if ms > SLOW_THRESHOLD_MS:
        return f"{YELLOW}{ms:>7.1f}ms{RESET}"
    return f"{GREEN}{ms:>7.1f}ms{RESET}"


def _color_val(val: Optional[int]) -> str:
    if val is None:
        return f"{DIM}   —{RESET}"
    return str(val)


def print_table(statuses: List[NodeStatus], health: NetworkHealth) -> None:
    """Print a human-readable colored status table."""
    width = 72
    now   = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    print(f"\n{BOLD}{CYAN}{'━' * width}{RESET}")
    print(f"{BOLD}{CYAN}  RustChain Attestation Node Health Monitor  —  {now}{RESET}")
    print(f"{BOLD}{CYAN}{'━' * width}{RESET}")

    # Header
    print(f"\n  {'NODE':<30} {'STATUS':<18} {'RT':>10} {'EPOCH':>8} {'MINERS':>7}")
    print(f"  {'─' * 28}  {'─' * 15}  {'─' * 10}  {'─' * 6}  {'─' * 6}")

    for s in statuses:
        node_label = s.url.replace("http://", "")
        status_str = _color_status(s.status)
        rt_str     = _color_ms(s.response_time_ms)
        epoch_str  = _color_val(s.epoch)
        miners_str = _color_val(s.miners)
        print(f"  {node_label:<30}  {status_str}  {rt_str}  {epoch_str:>8}  {miners_str:>7}")

    # Summary bar
    print(f"\n  {BOLD}Network Summary{RESET}")
    print(f"  {'─' * 40}")

    online_color = GREEN if health.nodes_online == health.total_nodes else (YELLOW if health.nodes_online > 0 else RED)
    consensus_color = GREEN if health.consensus_ok else RED
    split_color     = RED   if health.split_brain  else GREEN

    print(f"  Nodes online   : {online_color}{health.nodes_online}/{health.total_nodes}{RESET}")
    print(f"  Total miners   : {health.total_miners}")
    print(f"  Consensus      : {consensus_color}{'✔ OK' if health.consensus_ok else '✘ DIVERGED'}{RESET}")
    print(f"  Split brain    : {split_color}{'⚠ YES' if health.split_brain else '✔ no'}{RESET}")

    if health.alerts:
        print(f"\n  {BOLD}{RED}⚠  Alerts{RESET}")
        for alert in health.alerts:
            print(f"  {RED}  • {alert}{RESET}")
    else:
        print(f"\n  {GREEN}✔  All systems nominal{RESET}")

    print(f"\n{BOLD}{CYAN}{'━' * width}{RESET}\n")


# ── CLI entry point ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="RustChain multi-node health monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--json",  action="store_true", help="Output machine-readable JSON")
    p.add_argument("--watch", metavar="N", type=int, help="Refresh every N seconds")
    p.add_argument("--alert", action="store_true", help="Only print output if something is wrong (cron-safe)")
    p.add_argument("--nodes", nargs="+", metavar="URL", help="Override node URLs (default: 3 known nodes)")
    p.add_argument("--timeout", type=int, default=REQUEST_TIMEOUT, help=f"Request timeout in seconds (default: {REQUEST_TIMEOUT})")
    return p


def run_once(monitor: NodeHealthMonitor, args: argparse.Namespace) -> bool:
    """Run a single health-check cycle. Returns True if alerts were found."""
    statuses = monitor.check_all()
    health   = monitor.get_network_health(statuses)
    has_alert = bool(health.alerts)

    if args.alert and not has_alert:
        return False  # stay silent

    if args.json:
        output = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "nodes": [s.to_dict() for s in statuses],
            "network": health.to_dict(),
        }
        print(json.dumps(output, indent=2))
    else:
        print_table(statuses, health)

    return has_alert


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    monitor = NodeHealthMonitor(
        nodes=args.nodes,
        timeout=args.timeout,
    )

    if args.watch:
        try:
            while True:
                # Clear screen for watch mode (skip in JSON mode)
                if not args.json:
                    print("\033[2J\033[H", end="")
                run_once(monitor, args)
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            sys.exit(0)
    else:
        has_alert = run_once(monitor, args)
        sys.exit(1 if has_alert else 0)


if __name__ == "__main__":
    main()
