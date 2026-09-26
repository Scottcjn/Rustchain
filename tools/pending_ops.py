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


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("limit must be a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("limit must be a positive integer")
    return parsed


def _req(method: str, url: str, admin_key: str, payload: dict | None = None, *, insecure: bool) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method.upper())
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Admin-Key", admin_key)
    ctx = ssl._create_unverified_context() if insecure else None
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("node response must be a JSON object")
        return body


def cmd_list(args: argparse.Namespace) -> int:
    url = f"{args.node.rstrip('/')}/pending/list?status={args.status}&limit={args.limit}"
    out = _req("GET", url, args.admin_key, insecure=args.insecure)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def confirm_failure_reason(out: dict) -> str | None:
    """Return why a /pending/confirm response is NOT a success, or None.

    The exit code is the only signal a cron/CI caller gets. This used to return
    0 for any JSON object, so a pass in which every transfer raised (left
    pending, nothing delivered) exited green. Fail closed:
      * ``ok`` must be exactly True (a missing ``ok`` is an unexpected shape);
      * ``overdue_stats_measured: false`` means the node could not measure the
        queue, and "could not measure" is not "nothing to do".
    """
    if out.get("ok") is not True:
        failed = out.get("failed_ids")
        return f"node reported ok={out.get('ok')!r} (failed_ids={failed!r})"
    if out.get("overdue_stats_measured") is False:
        return f"pending queue could not be measured: {out.get('overdue_stats_error')!r}"
    return None


def cmd_confirm(args: argparse.Namespace) -> int:
    url = f"{args.node.rstrip('/')}/pending/confirm"
    out = _req("POST", url, args.admin_key, payload={}, insecure=args.insecure)
    print(json.dumps(out, indent=2, sort_keys=True))
    reason = confirm_failure_reason(out)
    if reason:
        print(f"error: confirm pass not healthy: {reason}", file=sys.stderr)
        return 1
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
    sp.add_argument("--limit", type=positive_int, default=100)
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
