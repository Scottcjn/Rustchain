#!/usr/bin/env python3
"""
RustChain Network Monitor — CLI tool for checking node health, miners, and epoch.

Bounty: Standard (20-50 RTC) — creates a useful utility for the RustChain ecosystem.

Usage:
  rustchain-monitor              # Show full status
  rustchain-monitor --health    # Just health check
  rustchain-monitor --miners    # List active miners
  rustchain-monitor --epoch     # Show current epoch info
"""

import argparse
import requests
from datetime import datetime

NODE_URL = "https://rustchain.org"

def normalize_miners_payload(data):
    def valid_rows(rows):
        return [row for row in rows if isinstance(row, dict)]

    if isinstance(data, list):
        return valid_rows(data)
    if isinstance(data, dict):
        for key in ("miners", "data", "items"):
            miners = data.get(key)
            if isinstance(miners, list):
                return valid_rows(miners)
    return data

def require_object_payload(data, endpoint):
    if isinstance(data, dict):
        return data
    return {"error": f"unexpected {endpoint} response shape"}

def check_health():
    try:
        resp = requests.get(f"{NODE_URL}/health", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return require_object_payload(data, "health")
    except Exception as e:
        return {"error": str(e)}

def get_miners():
    try:
        resp = requests.get(f"{NODE_URL}/api/miners", timeout=10)
        resp.raise_for_status()
        return normalize_miners_payload(resp.json())
    except Exception as e:
        return {"error": str(e)}

def get_epoch():
    try:
        resp = requests.get(f"{NODE_URL}/epoch", timeout=10)
        resp.raise_for_status()
        return require_object_payload(resp.json(), "epoch")
    except Exception as e:
        return {"error": str(e)}

def print_health(data):
    if not isinstance(data, dict):
        print(f"❌ Health check failed: unexpected response: {data}")
        return
    if "error" in data:
        print(f"❌ Health check failed: {data['error']}")
        return
    print("✅ Node is healthy")
    print(f"   Version: {data.get('version')}")
    print(f"   Uptime: {data.get('uptime_s')}s ({data.get('uptime_s')/3600:.1f} hours)")
    print(f"   Backup age: {data.get('backup_age_hours'):.2f} hours")
    print(f"   DB RW: {data.get('db_rw')}")

def print_miners(data):
    if "error" in data:
        print(f"❌ Failed to fetch miners: {data['error']}")
        return
    if not isinstance(data, list):
        print(f"⚠ Unexpected response: {data}")
        return
    data = [entry for entry in data if isinstance(entry, dict)]
    print(f"📊 Active miners: {len(data)}")
    print("   Recent miners:")
    for entry in data[:10]:
        miner = entry.get('miner', 'unknown')
        hw = entry.get('hardware_type', 'unknown')
        mult = entry.get('antiquity_multiplier', 0)
        last = entry.get('last_attest', 0)
        if last:
            last_str = datetime.fromtimestamp(last).strftime('%H:%M')
        else:
            last_str = 'never'
        print(f"   - {miner:<40} HW: {hw:<25} Multiplier: {mult:<5} Last: {last_str}")
    if len(data) > 10:
        print(f"   ... and {len(data)-10} more")

def print_epoch(data):
    if not isinstance(data, dict):
        print(f"❌ Failed to fetch epoch: unexpected response: {data}")
        return
    if "error" in data:
        print(f"❌ Failed to fetch epoch: {data['error']}")
        return
    print(f"🕐 Epoch: {data.get('epoch')}")
    print(f"   Slot: {data.get('slot')}")
    print(f"   Height: {data.get('height')}")
    print(f"   Blocks per epoch: {data.get('blocks_per_epoch')}")
    print(f"   Epoch pot: {data.get('epoch_pot')} RTC")
    print(f"   Enrolled miners: {data.get('enrolled_miners')}")

def main():
    parser = argparse.ArgumentParser(description="RustChain Network Monitor")
    parser.add_argument('--health', action='store_true', help='Show node health')
    parser.add_argument('--miners', action='store_true', help='List active miners')
    parser.add_argument('--epoch', action='store_true', help='Show current epoch info')
    args = parser.parse_args()

    # Default: show all
    show_all = not (args.health or args.miners or args.epoch)

    if args.health or show_all:
        health = check_health()
        print_health(health)
        if show_all:
            print()

    if args.miners or show_all:
        miners = get_miners()
        print_miners(miners)
        if show_all:
            print()

    if args.epoch or show_all:
        epoch = get_epoch()
        print_epoch(epoch)

if __name__ == '__main__':
    main()
