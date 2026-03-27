#!/usr/bin/env python3
"""
beacon keys — CLI sub-commands for TOFU key management.

Usage
-----
    python -m node.beacon_keys_cli list [--all] [--json]
    python -m node.beacon_keys_cli revoke <agent_id> [--reason TEXT]
    python -m node.beacon_keys_cli rotate --agent-id <id> --new-pubkey <hex> --sig <hex>
    python -m node.beacon_keys_cli show <agent_id>
    python -m node.beacon_keys_cli expire [--dry-run] [--ttl SECONDS]

Or imported and called from beacon_api.py:
    from node.beacon_keys_cli import build_parser, dispatch

Closes: Scottcjn/rustchain-bounties#392
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

from .beacon_identity import (
    DEFAULT_KEY_TTL,
    DB_PATH,
    expire_old_keys,
    get_key_info,
    list_keys,
    revoke_key,
    rotate_key,
)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_keys_list(args: argparse.Namespace) -> int:
    """beacon keys list — print known keys in a table or JSON."""
    keys = list_keys(
        include_revoked=args.all,
        include_expired=args.all,
        ttl=args.ttl,
        db_path=args.db,
    )
    if args.json:
        print(json.dumps(keys, indent=2, default=str))
        return 0

    if not keys:
        print("No known keys.")
        return 0

    header = f"{'Agent ID':<20}  {'Revoked':<8}  {'Expired':<8}  {'Rotations':<10}  {'Age(d)':<7}  {'Last Seen'}"
    print(header)
    print("-" * len(header))
    for k in keys:
        revoked = "YES" if k["is_revoked"] else "no"
        expired = "YES" if k["is_expired"] else "no"
        print(
            f"{k['agent_id']:<20}  {revoked:<8}  {expired:<8}  "
            f"{k['rotation_count']:<10}  {k['age_days']:<7}  {k['last_seen']}"
        )
    print(f"\nTotal: {len(keys)} keys")
    return 0


def cmd_keys_show(args: argparse.Namespace) -> int:
    """beacon keys show <agent_id> — detailed key info."""
    info = get_key_info(args.agent_id, db_path=args.db)
    if info is None:
        print(f"Key not found: {args.agent_id}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(info, indent=2, default=str))
        return 0

    print(f"Agent ID      : {info['agent_id']}")
    print(f"Public Key    : {info['pubkey_hex']}")
    print(f"First Seen    : {info['first_seen']}")
    print(f"Last Seen     : {info['last_seen']}")
    print(f"Rotation Count: {info['rotation_count']}")
    print(f"Previous Key  : {info.get('previous_key') or 'none'}")
    print(f"Revoked       : {'YES' if info['is_revoked'] else 'no'}")
    if info.get("revoked_at"):
        print(f"Revoked At    : {info['revoked_at']}")
        print(f"Revoked Reason: {info.get('revoked_reason')}")
    print(f"Expired (TTL) : {'YES' if info['is_expired'] else 'no'}")
    print(f"Age (days)    : {info['age_days']}")
    return 0


def cmd_keys_revoke(args: argparse.Namespace) -> int:
    """beacon keys revoke <agent_id> — revoke a key."""
    success, message = revoke_key(args.agent_id, reason=args.reason, db_path=args.db)
    if success:
        print(f"✓ {message}")
        return 0
    print(f"✗ {message}", file=sys.stderr)
    return 1


def cmd_keys_rotate(args: argparse.Namespace) -> int:
    """beacon keys rotate — rotate key with old-key signature.

    The signature must be Ed25519 of the payload:
        b"rotate:<agent_id>:<new_pubkey_hex>"
    signed with the OLD private key.
    """
    success, message = rotate_key(
        agent_id=args.agent_id,
        new_pubkey_hex=args.new_pubkey,
        signature_hex=args.sig,
        db_path=args.db,
    )
    if success:
        print(f"✓ {message}")
        return 0
    print(f"✗ {message}", file=sys.stderr)
    return 1


def cmd_keys_expire(args: argparse.Namespace) -> int:
    """beacon keys expire — list or delete TTL-expired keys."""
    expired = expire_old_keys(ttl=args.ttl, dry_run=args.dry_run, db_path=args.db)
    if not expired:
        print("No expired keys found.")
        return 0

    verb = "Would remove" if args.dry_run else "Removed"
    print(f"{verb} {len(expired)} expired key(s):")
    for agent_id in expired:
        print(f"  - {agent_id}")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser(prog: str = "beacon keys") -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=prog, description="Beacon agent key management (TOFU)")
    p.add_argument("--db", default=DB_PATH, metavar="PATH", help="SQLite DB path")
    p.add_argument("--ttl", type=int, default=DEFAULT_KEY_TTL, metavar="SECONDS",
                   help=f"Key TTL in seconds (default: {DEFAULT_KEY_TTL})")

    sub = p.add_subparsers(dest="sub", required=True)

    # list
    sp = sub.add_parser("list", help="List all known agent keys")
    sp.add_argument("--all", action="store_true", help="Include revoked and expired keys")
    sp.add_argument("--json", action="store_true", help="Output as JSON")
    sp.set_defaults(func=cmd_keys_list)

    # show
    sp = sub.add_parser("show", help="Show details for a specific key")
    sp.add_argument("agent_id", help="Agent ID (e.g. bcn_abc123def456)")
    sp.add_argument("--json", action="store_true", help="Output as JSON")
    sp.set_defaults(func=cmd_keys_show)

    # revoke
    sp = sub.add_parser("revoke", help="Revoke a known key")
    sp.add_argument("agent_id", help="Agent ID to revoke")
    sp.add_argument("--reason", default=None, help="Optional reason for revocation")
    sp.set_defaults(func=cmd_keys_revoke)

    # rotate
    sp = sub.add_parser("rotate", help="Rotate key (requires old-key signature)")
    sp.add_argument("--agent-id", required=True, dest="agent_id", help="Agent ID")
    sp.add_argument("--new-pubkey", required=True, metavar="HEX", help="New public key (hex)")
    sp.add_argument("--sig", required=True, metavar="HEX",
                    help="Ed25519 signature of 'rotate:<agent_id>:<new_pubkey_hex>' by old key")
    sp.set_defaults(func=cmd_keys_rotate)

    # expire
    sp = sub.add_parser("expire", help="Remove TTL-expired keys")
    sp.add_argument("--dry-run", action="store_true", help="Preview only, don't delete")
    sp.set_defaults(func=cmd_keys_expire)

    return p


def dispatch(args: Optional[list] = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(args)
    return ns.func(ns)


if __name__ == "__main__":
    sys.exit(dispatch())
