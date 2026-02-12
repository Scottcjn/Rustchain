#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    from payout_preflight import validate_wallet_transfer_admin, validate_wallet_transfer_signed
except ImportError:
    from node.payout_preflight import validate_wallet_transfer_admin, validate_wallet_transfer_signed


def read_payload(path: str) -> Any:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = open(path, "r", encoding="utf-8").read()
    return json.loads(raw)


def main() -> int:
    p = argparse.ArgumentParser(description="RustChain payout preflight checker (dry-run validation)")
    p.add_argument("--mode", choices=["admin", "signed"], required=True)
    p.add_argument("--input", required=True, help="path to JSON file, or '-' for stdin")
    args = p.parse_args()

    try:
        payload = read_payload(args.input)
    except Exception as e:
        print(json.dumps({"ok": False, "error": "invalid_json", "details": str(e)}))
        return 2

    res = validate_wallet_transfer_admin(payload) if args.mode == "admin" else validate_wallet_transfer_signed(payload)
    print(json.dumps({"ok": res.ok, "error": res.error, "details": res.details}, indent=2))
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
