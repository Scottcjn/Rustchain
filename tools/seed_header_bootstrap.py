#!/usr/bin/env python3
"""Seed the RustChain header-key bootstrap allowlist (miner_header_bootstrap).

The allowlist is admin-managed only — init_db does NOT auto-grandfather existing
keys (the miner_header_keys table is polluted with hundreds of thousands of
alias-strings). Operators seed the REAL block producers DELIBERATELY with this
helper before enabling RC_HEADER_KEY_STRICT_BOOTSTRAP.

Usage:
  # Seed from a curated file (one "miner_id pubkey_hex" per line; '#' comments ok)
  python3 tools/seed_header_bootstrap.py --db /root/rustchain/rustchain_v2.db --file producers.txt

  # Seed specific identities by copying THEIR current key from miner_header_keys
  python3 tools/seed_header_bootstrap.py --db ... --from-keys power8-s824-sophia g5-...

  # Inspect what would be seeded without writing
  python3 tools/seed_header_bootstrap.py --db ... --file producers.txt --dry-run

Deliberately does NOT support "seed everything" — curate the producer list.
Stdlib only.
"""
import argparse
import os
import sqlite3
import sys


def _pairs_from_file(path):
    pairs = []
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.split("#", 1)[0].strip()
            if not ln:
                continue
            parts = ln.split()
            if len(parts) != 2:
                raise SystemExit(f"bad line (need 'miner_id pubkey_hex'): {ln!r}")
            pairs.append((parts[0], parts[1].lower()))
    return pairs


def _pairs_from_keys(conn, miner_ids):
    pairs = []
    for mid in miner_ids:
        rows = conn.execute(
            "SELECT pubkey_hex FROM miner_header_keys WHERE miner_id=?", (mid,)
        ).fetchall()
        if not rows:
            print(f"  WARN: no header key found for {mid!r}", file=sys.stderr)
        for (pk,) in rows:
            pairs.append((mid, pk))
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("RUSTCHAIN_DB_PATH") or os.environ.get("DB_PATH"))
    ap.add_argument("--file", help="curated 'miner_id pubkey_hex' file")
    ap.add_argument("--from-keys", nargs="+", metavar="MINER_ID",
                    help="seed these identities from their current miner_header_keys rows")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.db:
        raise SystemExit("--db (or RUSTCHAIN_DB_PATH) required")
    if not args.file and not args.from_keys:
        raise SystemExit("provide --file or --from-keys (refusing to seed everything)")

    conn = sqlite3.connect(args.db)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS miner_header_bootstrap "
        "(miner_id TEXT NOT NULL, pubkey_hex TEXT NOT NULL, PRIMARY KEY (miner_id, pubkey_hex))"
    )
    pairs = []
    if args.file:
        pairs += _pairs_from_file(args.file)
    if args.from_keys:
        pairs += _pairs_from_keys(conn, args.from_keys)

    seen = set()
    pairs = [(m, p) for (m, p) in pairs if (m, p) not in seen and not seen.add((m, p))]
    print(f"{'(dry-run) would seed' if args.dry_run else 'seeding'} {len(pairs)} (miner_id, pubkey) pair(s):")
    for m, p in pairs:
        print(f"  {m}  {p[:16]}...")
    if args.dry_run:
        return
    conn.executemany(
        "INSERT OR IGNORE INTO miner_header_bootstrap (miner_id, pubkey_hex) VALUES (?, ?)", pairs
    )
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM miner_header_bootstrap").fetchone()[0]
    print(f"done. allowlist now holds {total} entr{'y' if total == 1 else 'ies'}.")


if __name__ == "__main__":
    main()
