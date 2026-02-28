#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone

import requests


def get_json(session: requests.Session, url: str, timeout: float):
    resp = session.get(url, timeout=timeout, verify=False)
    resp.raise_for_status()
    return resp.json()


def post_discord(session: requests.Session, webhook_url: str, payload: dict, timeout: float):
    resp = session.post(webhook_url, json=payload, timeout=timeout)
    resp.raise_for_status()


def fmt_rtc(value: float) -> str:
    return f"{value:.6f}"


def short_id(s: str, keep: int = 14) -> str:
    if len(s) <= keep:
        return s
    return s[:keep] + "..."


def build_leaderboard_lines(rows, top_n: int):
    out = []
    out.append("Rank  Miner             Balance(RTC)  Arch")
    out.append("----  ----------------  ------------  ----")
    for i, row in enumerate(rows[:top_n], start=1):
        miner = short_id(row["miner"], 16).ljust(16)
        bal = fmt_rtc(row["balance_rtc"]).rjust(12)
        arch = row.get("arch", "unknown")
        out.append(f"{str(i).rjust(4)}  {miner}  {bal}  {arch}")
    return "\n".join(out)


def architecture_distribution(rows):
    c = Counter()
    total = 0
    for r in rows:
        arch = (r.get("arch") or "unknown").strip() or "unknown"
        c[arch] += 1
        total += 1
    dist = []
    for arch, n in c.most_common():
        pct = (n * 100.0 / total) if total else 0.0
        dist.append((arch, n, pct))
    return dist


def rewards_for_epoch(session: requests.Session, base: str, epoch: int, timeout: float):
    url = f"{base}/rewards/epoch/{epoch}"
    try:
        data = get_json(session, url, timeout)
    except Exception:
        return []
    rewards = data.get("rewards") or []
    out = []
    for item in rewards:
        miner = item.get("miner_id", "unknown")
        share = float(item.get("share_rtc", 0.0))
        out.append({"miner": miner, "share_rtc": share})
    out.sort(key=lambda x: x["share_rtc"], reverse=True)
    return out


def collect_data(session: requests.Session, base: str, timeout: float):
    miners = get_json(session, f"{base}/api/miners", timeout)
    epoch = get_json(session, f"{base}/epoch", timeout)
    health = get_json(session, f"{base}/health", timeout)

    rows = []
    for m in miners:
        miner_id = m.get("miner") or m.get("miner_id")
        if not miner_id:
            continue
        bal = 0.0
        try:
            b = get_json(session, f"{base}/wallet/balance?miner_id={miner_id}", timeout)
            bal = float(b.get("amount_rtc", 0.0))
        except Exception:
            pass

        arch = m.get("device_arch") or m.get("device_family") or "unknown"
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


def render_payload(session, base: str, timeout: float, rows, epoch, health, top_n: int, title_prefix: str):
    total_balance = sum(x["balance_rtc"] for x in rows)
    dist = architecture_distribution(rows)
    top_table = build_leaderboard_lines(rows, top_n)
    current_epoch = int(epoch.get("epoch", -1))

    rewards = []
    rewards_text = "No reward rows available for current epoch."
    if current_epoch >= 0:
        rewards = rewards_for_epoch(session, base, current_epoch, timeout)
    if rewards:
        lines = []
        for item in rewards[: min(5, len(rewards))]:
            lines.append(f"- {short_id(item['miner'], 18)}: {fmt_rtc(item['share_rtc'])} RTC")
        rewards_text = "\n".join(lines)

    arch_lines = []
    for arch, n, pct in dist[:8]:
        arch_lines.append(f"- {arch}: {n} ({pct:.1f}%)")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    uptime_s = int(health.get("uptime_s", 0))
    node_ok = bool(health.get("ok", False))

    content = (
        f"{title_prefix}\n"
        f"Epoch: {current_epoch}\n"
        f"Generated: {now}\n"
        f"Node OK: {node_ok}, Uptime: {uptime_s}s\n"
        f"Total miners: {len(rows)}\n"
        f"Total RTC across miners: {fmt_rtc(total_balance)}\n"
    )

    embed = {
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


def run_once(args):
    base = args.node.rstrip("/")
    session = requests.Session()
    session.headers.update({"User-Agent": "rustchain-leaderboard-bot/1.0"})
    requests.packages.urllib3.disable_warnings()  # self-signed cert on node

    rows, epoch, health = collect_data(session, base, args.timeout)
    payload = render_payload(session, base, args.timeout, rows, epoch, health, args.top_n, args.title_prefix)

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return

    webhook = args.webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        raise RuntimeError("Missing webhook URL. Use --webhook-url or DISCORD_WEBHOOK_URL.")
    post_discord(session, webhook, payload, args.timeout)


def main():
    p = argparse.ArgumentParser(description="Post RustChain leaderboard to Discord webhook.")
    p.add_argument("--node", default="https://rustchain.org", help="RustChain node base URL")
    p.add_argument("--webhook-url", default="", help="Discord webhook URL")
    p.add_argument("--top-n", type=int, default=10, help="Top N miners to include")
    p.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout seconds")
    p.add_argument("--schedule-seconds", type=int, default=0, help="If >0, run in a loop")
    p.add_argument("--title-prefix", default="RustChain daily leaderboard", help="Message prefix")
    p.add_argument("--dry-run", action="store_true", help="Print payload instead of posting")
    args = p.parse_args()

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
