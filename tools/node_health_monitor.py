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
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Shared body-validating node probe (issue #17180): liveness is never decided
# from the HTTP status code alone — a 200 answered by an HTML page is an
# "impostor", surfaced via NodeStatus.probe_state.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from monitoring.node_probe import (  # noqa: E402
    probe_health, UP, DOWN, IMPOSTOR, DEGRADED, UNREACHABLE,
)

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

# The node exposes /health and /epoch. It has never exposed /status, which is
# what this monitor asked for, so every probe of a real node returned 404 and
# was filed as "slow" with no epoch: the monitor had never once read state from
# node 1 or node 2. Combined with a dead node reporting online, the result was
# exactly inverted. /epoch is tried first because it carries both the epoch and
# the enrolled miner count; /status is kept for any deployment that has it.
STATUS_ENDPOINTS = ("/epoch", "/status", "/health")
REQUEST_TIMEOUT   = 5      # seconds per HTTP request

# Steady state is a lag of 1: the current epoch is in progress and the previous
# one is settled. 3 tolerates one late settlement plus clock skew without
# crying wolf, while still catching a real stall on its second day rather than
# its eighty-fourth.
SETTLEMENT_LAG_THRESHOLD = 3

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
    # Epochs since this node last settled one. The epoch number advances off
    # wall-clock whether or not anybody is being paid, so `epoch` alone stayed
    # perfectly healthy through the 84-epoch settlement outage of 2026-03-03 to
    # 2026-05-27. None means the node does not report it (older build).
    settlement_lag_epochs: Optional[int] = None
    # State from the shared /health probe (monitoring/node_probe.py):
    # "up" | "down" | "impostor" | "degraded" | "unreachable". "impostor" means
    # the host answered HTTP 200 but is not a RustChain node.
    probe_state: Optional[str] = None

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
    # True when any online node has not settled an epoch in a while. Kept
    # separate from consensus_ok/split_brain because nodes can agree perfectly
    # on the epoch number and still be paying nobody — which is exactly what
    # happened for 84 consecutive epochs in 2026.
    settlement_stalled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NodeHealthMonitor:
    """Monitors RustChain attestation nodes for health, consensus, and split-brain."""

    def __init__(self, nodes: Optional[List[str]] = None, timeout: int = REQUEST_TIMEOUT):
        self.nodes = nodes or DEFAULT_NODES
        self.timeout = timeout

    # ── Per-node check ────────────────────────────────────────────────────────

    def _fetch_status_json(self, url: str) -> Tuple[Optional[dict], str, Optional[str]]:
        """Fetch the first status endpoint that answers with a JSON object.

        Returns (data, path, error). data is None when no endpoint produced a
        JSON object; error explains why. A 404 means this deployment does not
        expose the path we asked for, so the next known endpoint is tried.
        """
        problems = []
        for path in STATUS_ENDPOINTS:
            req = urllib.request.Request(
                f"{url}{path}",
                headers={"Accept": "application/json", "User-Agent": "RustChain-HealthMonitor/1.0"},
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    problems.append(f"{path}: 404")
                    continue
                return None, path, f"HTTP {exc.code}: {exc.reason}"
            except Exception as exc:  # noqa: BLE001
                return None, path, str(exc)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict):
                return data, path, None
            problems.append(f"{path}: non-JSON body ({len(raw)} bytes)")
        return None, STATUS_ENDPOINTS[0], "; ".join(problems) or "no endpoint answered"

    def check_node(self, url: str) -> NodeStatus:
        """
        Probe a single node. Returns a NodeStatus with:
          status            "online" | "slow" | "offline"
          response_time_ms  round-trip in milliseconds (None if unreachable)
          epoch             current epoch number from node (None if unavailable)
          miners            active miner count (None if unavailable)
          error             error message string (None if OK)
          probe_state       shared-probe state of /health: "up" | "down" |
                            "impostor" | "degraded" | "unreachable"

        Liveness and identity come from the shared probe of /health
        (monitoring/node_probe.py), never from the HTTP status code alone.

        A 200 is not evidence of a node. RustChain node 4 stopped being a node
        and the host was reused for a single-page app, which answers 200 on
        EVERY path. The old code quietly replaced the unparseable body with {}
        and reported the node "online" for months. Now anything that is not a
        genuine RustChain /health body is surfaced as probe_state="impostor".
        """
        health_url = f"{url.rstrip('/')}/health"
        probe = probe_health(health_url, timeout=self.timeout)
        rt = probe.response_ms

        if probe.state == UNREACHABLE:
            return NodeStatus(
                url=url, status="offline", response_time_ms=None,
                epoch=None, miners=None,
                error=f"/health unreachable: {probe.detail}", probe_state=UNREACHABLE,
            )
        if probe.state == IMPOSTOR:
            return NodeStatus(
                url=url, status="offline", response_time_ms=rt,
                epoch=None, miners=None,
                error=f"IMPOSTOR — {probe.detail}", probe_state=IMPOSTOR,
            )
        if probe.state == DOWN:
            # The host answered /health with an error code — reachable but unwell.
            return NodeStatus(
                url=url, status="slow", response_time_ms=rt,
                epoch=None, miners=None,
                error=f"/health HTTP {probe.status_code}: {probe.detail}", probe_state=DOWN,
            )

        # probe.state is "up" or "degraded": a genuine node answered /health.
        # Pull epoch/miners from the status endpoints for consensus tracking.
        data, path, fetch_err = self._fetch_status_json(url)
        if data is None:
            return NodeStatus(
                url=url, status="offline", response_time_ms=rt,
                epoch=None, miners=None,
                error=f"{fetch_err} (but /health probe says {probe.state})",
                probe_state=probe.state,
            )

        epoch  = data.get("epoch") or data.get("current_epoch")
        miners = (data.get("miners") or data.get("active_miners")
                  or data.get("miner_count") or data.get("enrolled_miners"))

        # Coerce to int if present, tolerating a malformed value rather
        # than raising inside the probe.
        try:
            epoch = int(epoch) if epoch is not None else None
        except (TypeError, ValueError):
            epoch = None
        try:
            miners = int(miners) if miners is not None else None
        except (TypeError, ValueError):
            miners = None

        # JSON with no epoch is not node state either — it is some
        # other service that happens to speak JSON on this address.
        if epoch is None:
            return NodeStatus(
                url=url, status="offline", response_time_ms=rt,
                epoch=None, miners=miners,
                error=f"{path} carried no epoch (not a RustChain node?)",
                probe_state=probe.state,
            )

        lag = data.get("settlement_lag_epochs")
        try:
            lag = int(lag) if lag is not None else None
        except (TypeError, ValueError):
            lag = None

        status = "slow" if (rt or 0) > SLOW_THRESHOLD_MS else "online"
        # A settlement stall does not make the node offline — it is
        # answering, and miners must keep enrolling so the stalled
        # epochs stay reconstructible. Report it, do not hide it in
        # the status word.
        err = None
        if probe.state == DEGRADED:
            err = f"degraded: {probe.detail}"
        if lag is not None and lag >= SETTLEMENT_LAG_THRESHOLD:
            stall = (f"settlement stalled: {lag} epochs since last settled "
                     f"(miners are enrolling and being paid nothing)")
            err = f"{err}; {stall}" if err else stall
        return NodeStatus(
            url=url,
            status=status,
            response_time_ms=rt,
            epoch=epoch,
            miners=miners,
            error=err,
            settlement_lag_epochs=lag,
            probe_state=probe.state,
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
        # The attestation nodes are replicas of one shared ledger, so each online
        # node reports the SAME network-wide miner count (the sibling tools
        # ledger_verify / node_sync_validator flag any divergence as a mismatch).
        # Summing per-node counts would multiply the true figure by the number of
        # online nodes, so take the agreed value (max is robust to a node that is
        # mid-sync and momentarily reporting fewer miners).
        miner_counts = [s.miners for s in online if s.miners is not None]
        total_miners = max(miner_counts) if miner_counts else 0

        epochs = {s.epoch for s in online if s.epoch is not None}
        consensus_ok = len(epochs) <= 1  # 0 or 1 distinct epoch → consensus holds
        split_brain  = self.detect_split_brain(statuses)

        alerts: List[str] = []
        offline_nodes = [s for s in statuses if s.status == "offline"]
        slow_nodes    = [s for s in statuses if s.status == "slow"]

        if offline_nodes:
            urls = ", ".join(s.url for s in offline_nodes)
            alerts.append(f"Node(s) offline: {urls}")
        for s in statuses:
            if getattr(s, "probe_state", None) == "impostor":
                alerts.append(
                    f"IMPOSTOR at {s.url}: HTTP 200 but not a RustChain node ({s.error})"
                )
            elif getattr(s, "probe_state", None) == "degraded":
                alerts.append(f"Node degraded: {s.url} ({s.error})")
        if slow_nodes:
            urls = ", ".join(f"{s.url} ({s.response_time_ms:.0f}ms)" for s in slow_nodes)
            alerts.append(f"Slow response from: {urls}")
        if split_brain:
            alerts.append(f"SPLIT BRAIN detected — divergent epochs: {sorted(epochs)}")
        if nodes_online == 0:
            alerts.append("ALL NODES OFFLINE — network unreachable")

        stalled = [s for s in online
                   if s.settlement_lag_epochs is not None
                   and s.settlement_lag_epochs >= SETTLEMENT_LAG_THRESHOLD]
        if stalled:
            detail = ", ".join(f"{s.url} ({s.settlement_lag_epochs} epochs)"
                               for s in stalled)
            alerts.append(
                f"SETTLEMENT STALLED — no epoch settled recently: {detail}. "
                f"Miners are still enrolling and earning nothing."
            )

        return NetworkHealth(
            nodes_online=nodes_online,
            total_nodes=len(statuses),
            total_miners=total_miners,
            consensus_ok=consensus_ok,
            split_brain=split_brain,
            alerts=alerts,
            settlement_stalled=bool(stalled),
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
