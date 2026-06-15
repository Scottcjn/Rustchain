#!/usr/bin/env python3
"""
RustChain Network Snapshot Tool
================================
A lightweight daily snapshot utility for the RustChain network.

Captures network state (miners, epochs, health) to JSON/CSV
for trend analysis and historical comparison.

Usage:
    python rustchain_snapshot.py              # take a single snapshot
    python rustchain_snapshot.py --daily      # append to daily log
    python rustchain_snapshot.py --csv out/  # export CSV to directory
    python rustchain_snapshot.py --watch 60   # snapshot every 60 sec

Author: alex (OpenClaw Agent)
License: MIT
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_NODE = "https://50.28.86.131"
ENDPOINTS = {
    "health": "/health",
    "miners": "/api/miners",
    "epoch": "/epoch",
}


def fetch_json(url: str, timeout: float = 15.0) -> dict[str, Any]:
    """Fetch JSON from a RustChain API endpoint."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}", "_url": url}
    except Exception as e:
        return {"_error": str(e), "_url": url}


def take_snapshot(node: str) -> dict[str, Any]:
    """Collect a full network snapshot."""
    ts = datetime.now(timezone.utc).isoformat()
    snapshot = {
        "timestamp": ts,
        "node": node,
        "health": fetch_json(f"{node}/health"),
        "miners": fetch_json(f"{node}/api/miners"),
        "epoch": fetch_json(f"{node}/epoch"),
    }
    return snapshot


def snapshot_to_csv_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten snapshot into CSV-ready rows (one per miner)."""
    rows: list[dict[str, Any]] = []
    ts = snapshot.get("timestamp", "")
    miners_data = snapshot.get("miners", {})
    miner_list = miners_data.get("miners", []) if isinstance(miners_data, dict) else []
    epoch_data = snapshot.get("epoch", {})
    epoch_num = epoch_data.get("epoch", "") if isinstance(epoch_data, dict) else ""
    for m in miner_list:
        rows.append({
            "timestamp": ts,
            "epoch": epoch_num,
            "miner_id": m.get("miner", ""),
            "device_arch": m.get("device_arch", ""),
            "device_family": m.get("device_family", ""),
            "hardware_type": m.get("hardware_type", ""),
            "antiquity_multiplier": m.get("antiquity_multiplier", 0),
            "last_attest": m.get("last_attest", 0),
        })
    return rows


def save_json(snapshot: dict[str, Any], out_dir: Path) -> Path:
    """Save snapshot as a timestamped JSON file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"snapshot_{ts}.json"
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def append_csv(rows: list[dict[str, Any]], out_dir: Path) -> Path:
    """Append rows to a daily CSV file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = out_dir / f"miners_{date}.csv"
    fieldnames = [
        "timestamp", "epoch", "miner_id", "device_arch",
        "device_family", "hardware_type", "antiquity_multiplier", "last_attest",
    ]
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)
    return path


def print_summary(snapshot: dict[str, Any]) -> None:
    """Pretty-print a snapshot summary."""
    ts = snapshot.get("timestamp", "?")
    miners_data = snapshot.get("miners", {})
    miner_list = miners_data.get("miners", []) if isinstance(miners_data, dict) else []
    epoch_data = snapshot.get("epoch", {})
    health_data = snapshot.get("health", {})

    print(f"RustChain Snapshot @ {ts}")
    print("-" * 50)
    print(f"Node health : {'OK' if health_data.get('ok') else 'DEGRADED'}")
    print(f"Active miners : {len(miner_list)}")
    print(f"Current epoch : {epoch_data.get('epoch', '?') if isinstance(epoch_data, dict) else '?'}")
    print(f"Epoch pot : {epoch_data.get('pot_rtc', '?') if isinstance(epoch_data, dict) else '?'} RTC")
    if miner_list:
        arch_counts: dict[str, int] = {}
        for m in miner_list:
            arch_counts[m.get("hardware_type", "Unknown")] = arch_counts.get(m.get("hardware_type", "Unknown"), 0) + 1
        print("Hardware distribution:")
        for arch, cnt in sorted(arch_counts.items(), key=lambda x: -x[1]):
            print(f"  - {arch}: {cnt}")
    print("-" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(description="RustChain Network Snapshot Tool")
    parser.add_argument("--node", default=DEFAULT_NODE, help="RustChain node URL")
    parser.add_argument("--json-out", type=Path, default=Path("snapshots"), help="JSON output directory")
    parser.add_argument("--csv-out", type=Path, default=Path("snapshots"), help="CSV output directory")
    parser.add_argument("--daily", action="store_true", help="Append to daily CSV log")
    parser.add_argument("--watch", type=int, metavar="SEC", help="Repeat every N seconds")
    parser.add_argument("--quiet", action="store_true", help="Suppress summary output")
    args = parser.parse_args()

    while True:
        snapshot = take_snapshot(args.node)

        if not args.quiet:
            print_summary(snapshot)

        json_path = save_json(snapshot, args.json_out)
        if not args.quiet:
            print(f"JSON saved: {json_path}")

        if args.daily or args.csv_out:
            rows = snapshot_to_csv_rows(snapshot)
            if rows:
                csv_path = append_csv(rows, args.csv_out)
                if not args.quiet:
                    print(f"CSV appended: {csv_path}")

        if not args.watch:
            break
        time.sleep(args.watch)


if __name__ == "__main__":
    main()
