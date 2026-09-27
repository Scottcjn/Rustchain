#!/usr/bin/env python3
import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


def load_records(args):
    if args.file:
        return json.loads(Path(args.file).read_text(encoding="utf-8"))
    query = urlencode({"miner_id": args.miner_id, "limit": args.limit})
    with urlopen(f"https://rustchain.org/wallet/history?{query}", timeout=15) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description="Summarize RustChain wallet history")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", help="Read wallet-history JSON from a local file")
    source.add_argument("--miner-id", help="Fetch public wallet history for this miner_id")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    rows = load_records(args)
    if not isinstance(rows, list):
        raise SystemExit("Expected a JSON array from /wallet/history")

    status = Counter()
    direction = Counter()
    sent = 0.0
    received = 0.0

    for tx in rows:
        status[str(tx.get("status", "unknown"))] += 1
        tx_direction = str(tx.get("direction", "unknown"))
        direction[tx_direction] += 1
        amount = float(tx.get("amount_rtc", tx.get("amount", 0)) or 0)
        if tx_direction == "sent":
            sent += amount
        elif tx_direction == "received":
            received += amount

    print(f"transactions: {len(rows)}")
    print("status:", ", ".join(f"{key}={status[key]}" for key in sorted(status)) or "none")
    print("direction:", ", ".join(f"{key}={direction[key]}" for key in sorted(direction)) or "none")
    print(f"received_rtc: {received:.6f}")
    print(f"sent_rtc: {sent:.6f}")
    print(f"net_flow_rtc: {received - sent:.6f}")


if __name__ == "__main__":
    main()
