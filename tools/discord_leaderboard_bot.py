#!/usr/bin/env python3
"""RustChain Discord Leaderboard Bot - Posts miner leaderboard to Discord webhook."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests


def get_json(session: requests.Session, url: str, timeout: float) -> Any:
    """Fetch JSON from URL using provided session.
    
    Args:
        session: requests.Session with configured headers
        url: URL to fetch
        timeout: Request timeout in seconds
        
    Returns:
        Parsed JSON response
        
    Raises:
        requests.HTTPError: If response status is not 2xx
    """
    resp: requests.Response = session.get(url, timeout=timeout, verify=False)
    resp.raise_for_status()
    return resp.json()


def post_discord(session: requests.Session, webhook_url: str, payload: dict[str, Any], timeout: float) -> None:
    """Post payload to Discord webhook.
    
    Args:
        session: requests.Session with configured headers
        webhook_url: Discord webhook URL
        payload: JSON payload to post
        timeout: Request timeout in seconds
        
    Raises:
        requests.HTTPError: If response status is not 2xx
    """
    resp: requests.Response = session.post(webhook_url, json=payload, timeout=timeout)
    resp.raise_for_status()


def fmt_rtc(value: float) -> str:
    """Format RTC value with 6 decimal places.
    
    Args:
        value: RTC amount to format
        
    Returns:
        Formatted string with 6 decimal places
    """
    return f"{value:.6f}"


def short_id(s: str, keep: int = 14) -> str:
    """Truncate long IDs with ellipsis.
    
    Args:
        s: String to truncate
        keep: Number of characters to keep before truncation
        
    Returns:
        Truncated string with ellipsis if longer than keep
    """
    if len(s) <= keep:
        return s
    return s[:keep] + "..."


def build_leaderboard_lines(rows: List[Dict[str, Any]], top_n: int) -> str:
    """Build formatted leaderboard text table.
    
    Args:
        rows: List of miner data dictionaries
        top_n: Number of top miners to include
        
    Returns:
        Formatted text table as string
    """
    out: List[str] = []
    out.append("Rank  Miner             Balance(RTC)  Arch")
    out.append("----  ----------------  ------------  ----")
    for i, row in enumerate(rows[:top_n], start=1):
        miner: str = short_id(row["miner"], 16).ljust(16)
        bal: str = fmt_rtc(row["balance_rtc"]).rjust(12)
        arch: str = row.get("arch", "unknown")
        out.append(f"{str(i).rjust(4)}  {miner}  {bal}  {arch}")
    return "\n".join(out)


def architecture_distribution(rows: List[Dict[str, Any]]) -> List[Tuple[str, int, float]]:
    """Calculate architecture distribution from miner rows.
    
    Args:
        rows: List of miner data dictionaries
        
    Returns:
        List of (architecture, count, percentage) tuples
    """
    c: Counter = Counter()
    total: int = 0
    for r in rows:
        arch: str = (r.get("arch") or "unknown").strip() or "unknown"
        c[arch] += 1
        total += 1
    dist: List[Tuple[str, int, float]] = []
    for arch, n in c.most_common():
        pct: float = (n * 100.0 / total) if total else 0.0
        dist.append((arch, n, pct))
    return dist


def rewards_for_epoch(session: requests.Session, base: str, epoch: int, timeout: float) -> List[Dict[str, Any]]:
    """Fetch reward data for a specific epoch.
    
    Args:
        session: requests.Session with configured headers
        base: Node base URL
        epoch: Epoch number to fetch
        timeout: Request timeout in seconds
        
    Returns:
        List of {miner, share_rtc} dictionaries sorted by share descending
    """
    url: str = f"{base}/rewards/epoch/{epoch}"
    try:
        data: Any = get_json(session, url, timeout)
    except Exception:
        return []
    rewards: List[Dict[str, Any]] = data.get("rewards") or []
    out: List[Dict[str, Any]] = []
    for item in rewards:
        miner: str = item.get("miner_id", "unknown")
        share: float = float(item.get("share_rtc", 0.0))
        out.append({"miner": miner, "share_rtc": share})
    out.sort(key=lambda x: x["share_rtc"], reverse=True)
    return out


def collect_data(session: requests.Session, base: str, timeout: float) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """Collect all data needed for leaderboard from node.
    
    Args:
        session: requests.Session with configured headers
        base: Node base URL
        timeout: Request timeout in seconds
        
    Returns:
        Tuple of (miner_rows, epoch_data, health_data)
    """
    miners: List[Dict[str, Any]] = get_json(session, f"{base}/api/miners", timeout)
    epoch: Dict[str, Any] = get_json(session, f"{base}/epoch", timeout)
    health: Dict[str, Any] = get_json(session, f"{base}/health", timeout)

    rows: List[Dict[str, Any]] = []
    for m in miners:
        miner_id: Optional[str] = m.get("miner") or m.get("miner_id")
        if not miner_id:
            continue
        bal: float = 0.0
        try:
            b: Dict[str, Any] = get_json(session, f"{base}/wallet/balance?miner_id={miner_id}", timeout)
            bal = float(b.get("amount_rtc", 0.0))
        except Exception:
            pass

        arch: str = m.get("device_arch") or m.get("device_family") or "unknown"
        rows.append(
            {
                "miner": miner_id,
                "balance_rtc": bal,
                "arch": arch,
                "multiplier": float(m.get("antiquity_multiplier", 0.0)),
            }
        )

    rows.sort(key=lambda x: x["balance_rtc"], reverse=True)
    return rows, epoch, health


def render_payload(
    session: requests.Session,
    base: str,
    timeout: float,
    rows: List[Dict[str, Any]],
    epoch: Dict[str, Any],
    health: Dict[str, Any],
    top_n: int,
    title_prefix: str,
) -> Dict[str, Any]:
    """Render Discord webhook payload from collected data.
    
    Args:
        session: requests.Session with configured headers
        base: Node base URL
        timeout: Request timeout in seconds
        rows: List of miner data dictionaries
        epoch: Epoch data dictionary
        health: Health data dictionary
        top_n: Number of top miners to include
        title_prefix: Prefix for message content
        
    Returns:
        Discord webhook payload dictionary
    """
    total_balance: float = sum(x["balance_rtc"] for x in rows)
    dist: List[Tuple[str, int, float]] = architecture_distribution(rows)
    top_table: str = build_leaderboard_lines(rows, top_n)
    current_epoch: int = int(epoch.get("epoch", -1))

    rewards: List[Dict[str, Any]] = []
    rewards_text: str = "No reward rows available for current epoch."
    if current_epoch >= 0:
        rewards = rewards_for_epoch(session, base, current_epoch, timeout)
    if rewards:
        lines: List[str] = []
        for item in rewards[: min(5, len(rewards))]:
            lines.append(f"- {short_id(item['miner'], 18)}: {fmt_rtc(item['share_rtc'])} RTC")
        rewards_text = "\n".join(lines)

    arch_lines: List[str] = []
    for arch, n, pct in dist[:8]:
        arch_lines.append(f"- {arch}: {n} ({pct:.1f}%)")

    now: str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    uptime_s: int = int(health.get("uptime_s", 0))
    node_ok: bool = bool(health.get("ok", False))

    content: str = (
        f"{title_prefix}\n"
        f"Epoch: {current_epoch}\n"
        f"Generated: {now}\n"
        f"Node OK: {node_ok}, Uptime: {uptime_s}s\n"
        f"Total miners: {len(rows)}\n"
        f"Total RTC across miners: {fmt_rtc(total_balance)}\n"
    )

    embed: Dict[str, Any] = {
        "title": "RustChain Leaderboard",
        "description": "Top miners by current RTC balance",
        "color": 3066993,
        "fields": [
            {"name": "Top Miners", "value": f"```text\n{top_table}\n```", "inline": False},
            {"name": "Top Earners (current epoch)", "value": rewards_text, "inline": False},
            {
                "name": "Architecture Distribution",
                "value": "\n".join(arch_lines) if arch_lines else "No data",
                "inline": False,
            },
        ],
    }
    return {"content": content, "embeds": [embed]}


def run_once(args: argparse.Namespace) -> None:
    """Run a single leaderboard post iteration.
    
    Args:
        args: Parsed command-line arguments
    """
    base: str = args.node.rstrip("/")
    session: requests.Session = requests.Session()
    session.headers.update({"User-Agent": "rustchain-leaderboard-bot/1.0"})
    requests.packages.urllib3.disable_warnings()  # self-signed cert on node

    rows, epoch, health = collect_data(session, base, args.timeout)
    payload: Dict[str, Any] = render_payload(session, base, args.timeout, rows, epoch, health, args.top_n, args.title_prefix)

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return

    webhook: Optional[str] = args.webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        raise RuntimeError("Missing webhook URL. Use --webhook-url or DISCORD_WEBHOOK_URL.")
    post_discord(session, webhook, payload, args.timeout)


def main() -> None:
    """Main entry point for Discord leaderboard bot."""
    p: argparse.ArgumentParser = argparse.ArgumentParser(description="Post RustChain leaderboard to Discord webhook.")
    p.add_argument("--node", default="https://rustchain.org", help="RustChain node base URL")
    p.add_argument("--webhook-url", default="", help="Discord webhook URL")
    p.add_argument("--top-n", type=int, default=10, help="Top N miners to include")
    p.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout seconds")
    p.add_argument("--schedule-seconds", type=int, default=0, help="If >0, run in a loop")
    p.add_argument("--title-prefix", default="RustChain daily leaderboard", help="Message prefix")
    p.add_argument("--dry-run", action="store_true", help="Print payload instead of posting")
    args: argparse.Namespace = p.parse_args()

    if args.top_n <= 0:
        print("--top-n must be > 0", file=sys.stderr)
        sys.exit(2)

    if args.schedule_seconds <= 0:
        run_once(args)
        return

    while True:
        try:
            run_once(args)
            print(f"[ok] posted at {datetime.now(timezone.utc).isoformat()}")
        except Exception as e:
            print(f"[error] {e}", file=sys.stderr)
        time.sleep(args.schedule_seconds)


if __name__ == "__main__":
    main()
