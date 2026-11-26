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
from pathlib import Path

# One shared /health body validator. In a checkout this imports the
# canonical implementation from monitoring/node_probe.py; when this file is
# copied out on its own (it is a standalone, stdlib-only script) the
# vendored copy below is used instead. The parity test in
# monitoring/test_impostor_across_monitors.py asserts both agree.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
try:
    from monitoring.node_probe import (
        STATE_DEGRADED,
        STATE_IMPOSTOR,
        ProbeResult,
        classify_health,
    )
    _PROBE_SHARED = True
except ImportError:  # standalone copy: use the vendored classifier below
    _PROBE_SHARED = False
    # Everything between these markers is copied verbatim into
    # health-dashboard/server.py and into the fallback path of
    # tools/node_health_monitor.py and tools/node-health-cli/node_health.py.
    # It must stay self-contained: only json / dataclasses / typing names.
    # The parity test in monitoring/test_impostor_across_monitors.py asserts
    # every copy returns the canonical verdict on all fixtures.
    STATE_UP = "up"
    STATE_DOWN = "down"
    STATE_IMPOSTOR = "impostor"
    STATE_DEGRADED = "degraded"
    STATE_UNREACHABLE = "unreachable"

    STATES = (STATE_UP, STATE_DOWN, STATE_IMPOSTOR, STATE_DEGRADED, STATE_UNREACHABLE)

    # A /health body without any of these is not a node body.
    REQUIRED_KEYS = ("ok", "version", "uptime_s")

    # Slots behind the tip before a live node counts as degraded.
    DEFAULT_TIP_AGE_SLOTS_THRESHOLD = 600


    @dataclass
    class ProbeResult:
        """The verdict of one /health probe."""

        state: str
        status_code: Optional[int] = None
        ok: Optional[bool] = None
        version: Optional[str] = None
        uptime_s: Optional[int] = None
        db_rw: Optional[bool] = None
        tip_age_slots: Optional[int] = None
        detail: str = ""
        response_ms: Optional[float] = None
        content_type: Optional[str] = None
        # Parsed JSON object when the body was one, else None. Monitors read
        # extra fields (active_miners, epoch, ...) from here without re-parsing.
        body: Optional[Dict] = None


    def _coerce_content_type(content_type) -> str:
        if isinstance(content_type, str):
            return content_type
        return ""


    def _coerce_body(body) -> bytes:
        if isinstance(body, (bytes, bytearray)):
            return bytes(body)
        if isinstance(body, str):
            return body.encode("utf-8")
        return b""


    def _is_number(value) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)


    def classify_health(status_code, content_type, body, *,
                        tip_age_slots_threshold: int = DEFAULT_TIP_AGE_SLOTS_THRESHOLD
                        ) -> ProbeResult:
        """Classify one /health answer. Pure function — no I/O.

        ``status_code`` is the HTTP status (None when there was no response),
        ``content_type`` the response Content-Type header, ``body`` the raw
        response bytes (a str is accepted for convenience).
        """
        content_type = _coerce_content_type(content_type)
        raw = _coerce_body(body)
        media = content_type.split(";")[0].strip().lower()

        if status_code is None:
            return ProbeResult(state=STATE_UNREACHABLE, detail="no HTTP response")

        head = raw.lstrip()[:200].decode("utf-8", errors="replace").lower()
        is_html = (
            media == "text/html"
            or head.startswith("<!doctype html")
            or head.startswith("<html")
        )
        if is_html:
            if status_code == 200:
                return ProbeResult(
                    state=STATE_IMPOSTOR,
                    status_code=status_code,
                    content_type=content_type,
                    detail=("HTTP 200 with text/html body — an unrelated site "
                            "(e.g. a single-page app) is answering on this address, "
                            "not a RustChain node"),
                )
            # An HTML error page from a proxy is the node being down, not an impostor.
            return ProbeResult(
                state=STATE_DOWN,
                status_code=status_code,
                content_type=content_type,
                detail="HTTP %s" % status_code,
            )

        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else None
        except (ValueError, UnicodeDecodeError):
            parsed = None
        data = parsed if isinstance(parsed, dict) else None
        if data is None:
            if status_code == 200:
                return ProbeResult(
                    state=STATE_IMPOSTOR,
                    status_code=status_code,
                    content_type=content_type,
                    detail="HTTP 200 but /health body is not a JSON object",
                )
            return ProbeResult(
                state=STATE_DOWN,
                status_code=status_code,
                content_type=content_type,
                detail="HTTP %s" % status_code,
            )

        missing = [key for key in REQUIRED_KEYS if key not in data]
        if "ok" in data and not isinstance(data["ok"], bool):
            missing.append("ok (not a boolean)")
        if "version" in data and not (isinstance(data["version"], str)
                                      and data["version"]):
            missing.append("version (not a non-empty string)")
        if "uptime_s" in data and (not _is_number(data["uptime_s"])
                                   or data["uptime_s"] < 0):
            missing.append("uptime_s (not a number >= 0)")
        if missing:
            if status_code == 200:
                return ProbeResult(
                    state=STATE_IMPOSTOR,
                    status_code=status_code,
                    content_type=content_type,
                    body=data,
                    detail=("HTTP 200 but /health JSON is missing required field(s): "
                            + ", ".join(missing)),
                )
            return ProbeResult(
                state=STATE_DOWN,
                status_code=status_code,
                content_type=content_type,
                body=data,
                detail="HTTP %s" % status_code,
            )

        ok = data["ok"]
        db_rw = data.get("db_rw")
        tip_age = data.get("tip_age_slots")
        tip_age = tip_age if _is_number(tip_age) else None

        result = ProbeResult(
            state=STATE_UP,
            status_code=status_code,
            ok=ok,
            version=data["version"],
            uptime_s=data["uptime_s"],
            db_rw=db_rw if isinstance(db_rw, bool) else None,
            tip_age_slots=tip_age,
            content_type=content_type,
            body=data,
        )
        if ok is False:
            result.state = STATE_DEGRADED
            result.detail = "node reports ok:false"
            return result
        if db_rw is False:
            result.state = STATE_DEGRADED
            result.detail = "node reports db_rw:false"
            return result
        if tip_age is not None and tip_age > tip_age_slots_threshold:
            result.state = STATE_DEGRADED
            result.detail = ("tip_age_slots %s is above threshold %s"
                             % (tip_age, tip_age_slots_threshold))
            return result
        if status_code != 200:
            # A valid healthy body behind an HTTP error status: the transport
            # says something is wrong, so do not call it up.
            result.state = STATE_DOWN
            result.detail = "HTTP %s" % status_code
            return result
        return result

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
    # Verdict of the shared /health body probe for this node ("up" |
    # "degraded" | "impostor" | "down" | "unreachable"; None when the probe
    # did not run). Kept separate from `status`: the status vocabulary
    # ("online" | "slow" | "offline") is pinned by
    # tests/test_node_liveness_requires_node_state.py, where an impostor
    # reads as "offline" — this field says why.
    health_state: Optional[str] = None
    health_detail: Optional[str] = None

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

    def _check_node_epoch(self, url: str) -> NodeStatus:
        """
        Probe a single node via /epoch (or /status). Returns a NodeStatus with:
          status            "online" | "slow" | "offline"
          response_time_ms  round-trip in milliseconds (None if unreachable)
          epoch             current epoch number from node (None if unavailable)
          miners            active miner count (None if unavailable)
          error             error message string (None if OK)
        """
        start = time.monotonic()
        try:
            path = getattr(self, "_status_path", None) or STATUS_ENDPOINTS[0]
            req = urllib.request.Request(
                f"{url}{path}",
                headers={"Accept": "application/json", "User-Agent": "RustChain-HealthMonitor/1.0"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                elapsed_ms = (time.monotonic() - start) * 1000
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = None
                if not isinstance(data, dict):
                    data = None

                # A 200 is not evidence of a node.
                #
                # RustChain node 4 stopped being a node and the host was reused
                # for a single-page app. An SPA answers 200 on EVERY unknown
                # path, so /status returned 200 with HTML, json.loads failed,
                # the body was quietly replaced with {}, and the node was
                # reported "online" indefinitely because status was decided
                # purely on response time. The loss went unnoticed for months.
                #
                # A node is online only if it answered with JSON that actually
                # carries node state. Anything else is impersonating one.
                if data is None:
                    return NodeStatus(
                        url=url,
                        status="offline",
                        response_time_ms=round(elapsed_ms, 1),
                        epoch=None,
                        miners=None,
                        error=(f"/status returned {len(raw)} bytes of non-JSON "
                               f"(is this still a node?): {raw[:60]!r}"),
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
                        url=url,
                        status="offline",
                        response_time_ms=round(elapsed_ms, 1),
                        epoch=None,
                        miners=miners,
                        error="/status carried no epoch (not a RustChain node?)",
                    )

                lag = data.get("settlement_lag_epochs")
                try:
                    lag = int(lag) if lag is not None else None
                except (TypeError, ValueError):
                    lag = None

                status = "slow" if elapsed_ms > SLOW_THRESHOLD_MS else "online"
                # A settlement stall does not make the node offline — it is
                # answering, and miners must keep enrolling so the stalled
                # epochs stay reconstructible. Report it, do not hide it in
                # the status word.
                err = None
                if lag is not None and lag >= SETTLEMENT_LAG_THRESHOLD:
                    err = (f"settlement stalled: {lag} epochs since last settled "
                           f"(miners are enrolling and being paid nothing)")
                return NodeStatus(
                    url=url,
                    status=status,
                    response_time_ms=round(elapsed_ms, 1),
                    epoch=epoch,
                    miners=miners,
                    error=err,
                    settlement_lag_epochs=lag,
                )

        except urllib.error.HTTPError as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            # A 404 means this deployment does not expose the path we asked
            # for, not that the node is unwell. Try the next known endpoint
            # before concluding anything: asking /status of a node that only
            # serves /epoch is how every real node came back "slow" forever.
            if exc.code == 404:
                tried = getattr(self, "_status_path", None) or STATUS_ENDPOINTS[0]
                remaining = [p for p in STATUS_ENDPOINTS if p != tried]
                for nxt in remaining:
                    self._status_path = nxt
                    try:
                        result = self._check_node_epoch(url)
                    finally:
                        self._status_path = None
                    if result.status != "offline" or "404" not in (result.error or ""):
                        return result
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

    def check_node(self, url: str) -> NodeStatus:
        """
        Probe a single node: the epoch probe first (it carries the epoch and
        miner count), then the shared /health body probe, whose verdict is
        attached as ``health_state`` / ``health_detail``.

        ``status`` keeps its existing vocabulary ("online" | "slow" |
        "offline") — the epoch probe decides it, exactly as before. The
        /health verdict is surfaced separately so an impostor is named as
        one (table, JSON, alerts) instead of silently counting as online.
        """
        result = self._check_node_epoch(url)
        probe = self._probe_health(url)
        result.health_state = probe.state
        result.health_detail = probe.detail or None
        return result

    def _probe_health(self, url: str) -> ProbeResult:
        """Classify ``<url>/health`` with the shared probe. Never raises."""
        target = "%s/health" % url.rstrip("/")
        try:
            req = urllib.request.Request(
                target,
                headers={"Accept": "application/json",
                         "User-Agent": "RustChain-HealthMonitor/1.0"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = getattr(resp, "status", 200)
                if not isinstance(status, int) or isinstance(status, bool):
                    # urlopen only returns a response object for 2xx.
                    status = 200
                headers = getattr(resp, "headers", None)
                content_type = ""
                if headers is not None:
                    get_type = getattr(headers, "get_content_type", None)
                    if callable(get_type):
                        try:
                            content_type = get_type() or ""
                        except Exception:
                            content_type = ""
                    else:
                        try:
                            content_type = headers.get("Content-Type", "") or ""
                        except Exception:
                            content_type = ""
                    if not isinstance(content_type, str):
                        content_type = ""
                return classify_health(status, content_type, resp.read())
        except urllib.error.HTTPError as exc:
            try:
                raw = exc.read() or b""
            except Exception:
                raw = b""
            return classify_health(exc.code, "", raw)
        except Exception as exc:  # timeout, refused, DNS, ...
            return ProbeResult(state="unreachable",
                               detail="unreachable: %s" % exc)

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
        if slow_nodes:
            urls = ", ".join(f"{s.url} ({s.response_time_ms:.0f}ms)" for s in slow_nodes)
            alerts.append(f"Slow response from: {urls}")
        impostors = [s for s in statuses if s.health_state == STATE_IMPOSTOR]
        degraded_nodes = [s for s in statuses
                          if s.health_state == STATE_DEGRADED]
        if impostors:
            urls = ", ".join(s.url for s in impostors)
            alerts.append(f"IMPOSTOR: {urls} — /health answers 200 but is "
                          f"not a node (see health_state)")
        if degraded_nodes:
            detail = ", ".join(f"{s.url} ({s.health_detail})"
                               for s in degraded_nodes)
            alerts.append(f"DEGRADED: {detail}")
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

def _color_status(status: str, health_state: Optional[str] = None) -> str:
    # The /health verdict names the failure: an impostor is not merely
    # offline, and a degraded node is still answering.
    if health_state == STATE_IMPOSTOR:
        return f"{RED}{BOLD}◆ impostor{RESET}"
    if health_state == STATE_DEGRADED:
        return f"{YELLOW}{BOLD}◐ degraded{RESET}"
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
        status_str = _color_status(s.status, s.health_state)
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
