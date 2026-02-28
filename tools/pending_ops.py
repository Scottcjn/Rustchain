#!/usr/bin/env python3
"""
RustChain pending transfer operations.

This is an operator helper for:
- listing pending transfers
- confirming transfers that have passed confirms_at

It calls the node API endpoints:
- GET  /pending/list
- POST /pending/confirm
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request


def _req(method: str, url: str, admin_key: str, payload: dict | None = None, *, insecure: bool) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method.upper())
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Admin-Key", admin_key)
    ctx = ssl._create_unverified_context() if insecure else None
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def cmd_list(args: argparse.Namespace) -> int:
    url = f"{args.node.rstrip('/')}/pending/list?status={args.status}&limit={args.limit}"
    out = _req("GET", url, args.admin_key, insecure=args.insecure)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def cmd_confirm(args: argparse.Namespace) -> int:
    url = f"{args.node.rstrip('/')}/pending/confirm"
    out = _req("POST", url, args.admin_key, payload={}, insecure=args.insecure)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", default=os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org"))
    ap.add_argument("--admin-key", dest="admin_key", default=os.environ.get("RC_ADMIN_KEY", ""))
    ap.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS verification (node cert is often self-signed / hostname-mismatched).",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list", help="List pending transfers")
    sp.add_argument("--status", default="pending", choices=["pending", "confirmed", "voided", "all"])
    sp.add_argument("--limit", type=int, default=100)
    sp.set_defaults(fn=cmd_list)

    sp = sub.add_parser("confirm", help="Confirm ready pending transfers")
    sp.set_defaults(fn=cmd_confirm)

    args = ap.parse_args(argv)
    if not args.admin_key:
        print("error: missing --admin-key or RC_ADMIN_KEY", file=sys.stderr)
        return 2
    try:
        return args.fn(args)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {body}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
