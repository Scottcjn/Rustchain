#!/usr/bin/env python3
"""
rustchain-health.py — CLI tool to monitor RustChain node health.

Features:
  - Color-coded terminal output (green = healthy, red = issues, yellow = warning)
  - Checks /health, /epoch, /api/miners, /headers/tip endpoints
  - Shows miner status, peer/miner count, chain tip, epoch info
  - Watch mode: auto-refresh every N seconds (--watch N)
  - Single file, no dependencies beyond requests (stdlib fallback included)

Bounty #1606 — Scottcjn/rustchain-bounties

Usage:
    python rustchain-health.py                          # default: https://rustchain.org
    python rustchain-health.py -u http://localhost:5000  # custom node
    python rustchain-health.py --watch 10                # refresh every 10s
    python rustchain-health.py --json                    # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import ssl
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ── colour helpers ──────────────────────────────────────────────────────────

_NO_COLOR = os.environ.get("NO_COLOR") is not None

def _supports_color() -> bool:
    if _NO_COLOR:
        return False
    if sys.platform == "win32":
        # Windows 10+ supports ANSI via VT mode
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return os.environ.get("TERM") is not None
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_COLOR = _supports_color()

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text

def green(t: str) -> str:   return _c("32", t)
def red(t: str) -> str:     return _c("31", t)
def yellow(t: str) -> str:  return _c("33", t)
def cyan(t: str) -> str:    return _c("36", t)
def bold(t: str) -> str:    return _c("1", t)
def dim(t: str) -> str:     return _c("2", t)

def status_dot(ok: bool) -> str:
    return green("●") if ok else red("●")

# ── HTTP helpers ────────────────────────────────────────────────────────────

def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx

def fetch(url: str, timeout: int = 8) -> Tuple[bool, Any, float]:
    """GET *url*, return (ok, parsed_json_or_None, latency_ms)."""
    t0 = time.time()
    try:
        req = Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "rustchain-health-cli/1.0",
        })
        with urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            body = resp.read(2 * 1024 * 1024).decode("utf-8", errors="replace")
            latency = (time.time() - t0) * 1000
            try:
                return True, json.loads(body), latency
            except json.JSONDecodeError:
                return True, body.strip(), latency
    except (HTTPError, URLError, OSError) as exc:
        latency = (time.time() - t0) * 1000
        return False, str(exc), latency

# ── individual checks ──────────────────────────────────────────────────────

def check_health(base: str, timeout: int) -> Dict[str, Any]:
    ok, data, ms = fetch(f"{base}/health", timeout)
    result: Dict[str, Any] = {"reachable": ok, "latency_ms": round(ms, 1)}
    if ok and isinstance(data, dict):
        result["ok"] = data.get("ok", False)
        result["version"] = data.get("version")
        result["uptime_s"] = data.get("uptime_s")
        result["db_rw"] = data.get("db_rw")
        result["tip_age_slots"] = data.get("tip_age_slots")
    elif ok:
        result["ok"] = True
        result["raw"] = str(data)[:200]
    else:
        result["ok"] = False
        result["error"] = str(data)
    return result

def check_epoch(base: str, timeout: int) -> Dict[str, Any]:
    ok, data, ms = fetch(f"{base}/epoch", timeout)
    result: Dict[str, Any] = {"reachable": ok, "latency_ms": round(ms, 1)}
    if ok and isinstance(data, dict):
        result["epoch"] = data.get("epoch")
        result["slot"] = data.get("slot")
        result["epoch_pot"] = data.get("epoch_pot")
        result["enrolled_miners"] = data.get("enrolled_miners")
        result["blocks_per_epoch"] = data.get("blocks_per_epoch")
        result["total_supply_rtc"] = data.get("total_supply_rtc")
    elif ok:
        result["raw"] = str(data)[:200]
    else:
        result["error"] = str(data)
    return result

def check_miners(base: str, timeout: int) -> Dict[str, Any]:
    ok, data, ms = fetch(f"{base}/api/miners", timeout)
    result: Dict[str, Any] = {"reachable": ok, "latency_ms": round(ms, 1)}
    if ok and isinstance(data, list):
        result["miner_count"] = len(data)
        result["miners"] = data[:10]  # first 10 for display
    elif ok and isinstance(data, dict):
        miners = data.get("miners", data.get("data", []))
        result["miner_count"] = len(miners) if isinstance(miners, list) else data.get("count", "?")
        if isinstance(miners, list):
            result["miners"] = miners[:10]
    else:
        result["miner_count"] = 0
        result["error"] = str(data) if not ok else None
    return result

def check_tip(base: str, timeout: int) -> Dict[str, Any]:
    ok, data, ms = fetch(f"{base}/headers/tip", timeout)
    result: Dict[str, Any] = {"reachable": ok, "latency_ms": round(ms, 1)}
    if ok and isinstance(data, dict):
        result["height"] = data.get("height", data.get("block_height"))
        result["hash"] = data.get("hash", data.get("block_hash"))
        result["timestamp"] = data.get("timestamp")
    elif ok:
        result["raw"] = str(data)[:200]
    else:
        result["error"] = str(data)
    return result

# ── aggregator ──────────────────────────────────────────────────────────────

def collect(base_url: str, timeout: int = 8) -> Dict[str, Any]:
    base = base_url.rstrip("/")
    return {
        "node": base,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "health": check_health(base, timeout),
        "epoch": check_epoch(base, timeout),
        "miners": check_miners(base, timeout),
        "tip": check_tip(base, timeout),
    }

# ── pretty printer ──────────────────────────────────────────────────────────

def _fmt_uptime(secs: Optional[int]) -> str:
    if secs is None:
        return "n/a"
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)

def _trunc_hash(h: Optional[str], n: int = 16) -> str:
    if not h:
        return "n/a"
    return h[:n] + "..." if len(h) > n else h

def render(snapshot: Dict[str, Any]) -> str:
    lines: List[str] = []
    w = 58

    lines.append("")
    lines.append(bold(cyan("  RustChain Node Health Monitor")))
    lines.append(dim("  " + "─" * w))
    lines.append(f"  Node      : {snapshot['node']}")
    lines.append(f"  Checked   : {snapshot['checked_at']}")
    lines.append("")

    # ── Health ───
    h = snapshot["health"]
    h_ok = h.get("ok", False) and h["reachable"]
    lines.append(f"  {status_dot(h_ok)}  {bold('Health')}          "
                 f"{green('healthy') if h_ok else red('UNHEALTHY')}  "
                 f"{dim(str(round(h['latency_ms'])) + ' ms')}")
    if h.get("version"):
        lines.append(f"     Version        : {h['version']}")
    if h.get("uptime_s") is not None:
        lines.append(f"     Uptime         : {_fmt_uptime(h['uptime_s'])}")
    if h.get("db_rw") is not None:
        db_ok = h["db_rw"]
        lines.append(f"     DB Read/Write  : {green('OK') if db_ok else red('FAIL')}")
    if h.get("error"):
        lines.append(f"     {red('Error')}: {h['error'][:80]}")
    lines.append("")

    # ── Epoch ───
    e = snapshot["epoch"]
    e_ok = e["reachable"] and e.get("epoch") is not None
    lines.append(f"  {status_dot(e_ok)}  {bold('Epoch')}           "
                 f"{green(str(e.get('epoch', '?'))) if e_ok else red('unavailable')}  "
                 f"{dim(str(round(e['latency_ms'])) + ' ms')}")
    if e_ok:
        if e.get("slot") is not None:
            lines.append(f"     Slot           : {e['slot']}")
        if e.get("epoch_pot") is not None:
            lines.append(f"     Epoch Pot      : {e['epoch_pot']} RTC")
        if e.get("enrolled_miners") is not None:
            lines.append(f"     Enrolled Miners: {e['enrolled_miners']}")
        if e.get("total_supply_rtc") is not None:
            lines.append(f"     Total Supply   : {e['total_supply_rtc']} RTC")
    if e.get("error"):
        lines.append(f"     {red('Error')}: {e['error'][:80]}")
    lines.append("")

    # ── Chain Tip ───
    t = snapshot["tip"]
    t_ok = t["reachable"] and t.get("height") is not None
    lines.append(f"  {status_dot(t_ok)}  {bold('Chain Tip')}       "
                 f"{'#' + str(t.get('height', '?')) if t_ok else yellow('unknown')}  "
                 f"{dim(str(round(t['latency_ms'])) + ' ms')}")
    if t_ok:
        lines.append(f"     Hash           : {_trunc_hash(t.get('hash'))}")
        if t.get("timestamp"):
            lines.append(f"     Timestamp      : {t['timestamp']}")
    if t.get("error"):
        lines.append(f"     {red('Error')}: {t['error'][:80]}")
    lines.append("")

    # ── Miners ───
    m = snapshot["miners"]
    m_ok = m["reachable"]
    count = m.get("miner_count", 0)
    count_str = str(count) if isinstance(count, int) else str(count)
    color_count = green(count_str) if (isinstance(count, int) and count > 0) else yellow(count_str)
    lines.append(f"  {status_dot(m_ok)}  {bold('Active Miners')}   "
                 f"{color_count}  "
                 f"{dim(str(round(m['latency_ms'])) + ' ms')}")
    miners_list = m.get("miners", [])
    if miners_list and isinstance(miners_list, list):
        for miner in miners_list[:5]:
            if isinstance(miner, dict):
                mid = miner.get("miner_id", miner.get("id", "?"))
                lines.append(f"     - {mid}")
            else:
                lines.append(f"     - {miner}")
        if isinstance(count, int) and count > 5:
            lines.append(f"     {dim(f'... and {count - 5} more')}")
    if m.get("error"):
        lines.append(f"     {red('Error')}: {m['error'][:80]}")
    lines.append("")

    # ── Overall ───
    all_ok = (h.get("ok", False) and h["reachable"]
              and e["reachable"]
              and m["reachable"])
    lines.append(dim("  " + "─" * w))
    if all_ok:
        lines.append(f"  {green(bold('STATUS: ALL SYSTEMS OPERATIONAL'))}")
    else:
        lines.append(f"  {red(bold('STATUS: ISSUES DETECTED'))}")
    lines.append("")

    return "\n".join(lines)

# ── CLI ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rustchain-health",
        description="CLI monitor for RustChain node health, epoch, chain tip, and miners.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s                                  check default node
  %(prog)s -u http://localhost:5000         check local dev node
  %(prog)s --watch 15                       auto-refresh every 15 s
  %(prog)s --json                           JSON output (for scripts)
  %(prog)s --json --watch 30 > log.jsonl    streaming JSON log
""",
    )
    p.add_argument(
        "-u", "--url",
        default="https://rustchain.org",
        help="Node base URL (default: https://rustchain.org)",
    )
    p.add_argument(
        "-t", "--timeout",
        type=int,
        default=10,
        help="HTTP request timeout in seconds (default: 10)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    p.add_argument(
        "--watch", "-w",
        type=int,
        default=0,
        metavar="SECS",
        help="Watch mode: re-check every SECS seconds",
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    return p


def clear_screen() -> None:
    if sys.platform == "win32":
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def main() -> int:
    global _COLOR
    args = build_parser().parse_args()

    if args.no_color:
        _COLOR = False

    def run_once() -> int:
        snapshot = collect(args.url, timeout=args.timeout)
        if args.json_output:
            print(json.dumps(snapshot, indent=2))
        else:
            print(render(snapshot))
        # exit 0 if healthy, 1 otherwise
        all_ok = (snapshot["health"].get("ok", False)
                  and snapshot["health"]["reachable"]
                  and snapshot["epoch"]["reachable"]
                  and snapshot["miners"]["reachable"])
        return 0 if all_ok else 1

    if args.watch > 0:
        try:
            while True:
                if not args.json_output:
                    clear_screen()
                run_once()
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print(dim("\n  Stopped."))
            return 0
    else:
        return run_once()


if __name__ == "__main__":
    sys.exit(main())
