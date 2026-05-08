#!/usr/bin/env python3
"""
RustChain Cross-Node Ledger Verification Tool
===============================================
Queries all RustChain nodes, compares state, alerts on mismatches.
Logs results to SQLite for historical tracking.

Usage:
    python3 ledger_verify.py              # One-shot verification
    python3 ledger_verify.py --ci         # Exit non-zero on mismatch (CI mode)
    python3 ledger_verify.py --webhook URL  # POST results to webhook on mismatch
    python3 ledger_verify.py --watch 300  # Run every 300 seconds continuously
    python3 ledger_verify.py --history    # Show recent check history

Bounty: https://github.com/Scottcjn/rustchain-bounties/issues/763
Author: NOX Ventures (noxxxxybot-sketch)
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Node configuration
# ---------------------------------------------------------------------------

NODES = [
    {"name": "Node 1 (Primary)", "url": "https://50.28.86.131", "id": "node1"},
    {"name": "Node 2",           "url": "https://50.28.86.153", "id": "node2"},
    # Node 3 is Tailscale-only; included for completeness but may be unreachable
    {"name": "Node 3 (Ryan)",    "url": "http://100.88.109.32:8099", "id": "node3"},
]

TIMEOUT_SECONDS = 10
DB_PATH = Path.home() / ".rustchain" / "ledger_verify.db"
SPOT_CHECK_WALLET = "founder_community"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sync_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checked_at TEXT NOT NULL,
            overall_ok INTEGER NOT NULL,
            epoch_match INTEGER NOT NULL,
            balance_match INTEGER NOT NULL,
            miner_count_match INTEGER NOT NULL,
            mismatch_details TEXT,
            merkle_roots TEXT,
            node_data TEXT
        );
        CREATE TABLE IF NOT EXISTS node_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            check_id INTEGER NOT NULL,
            node_id TEXT NOT NULL,
            node_name TEXT NOT NULL,
            reachable INTEGER NOT NULL,
            version TEXT,
            epoch INTEGER,
            slot INTEGER,
            enrolled_miners INTEGER,
            spot_balance REAL,
            active_miner_count INTEGER,
            merkle_root TEXT,
            raw_data TEXT,
            FOREIGN KEY (check_id) REFERENCES sync_checks(id)
        );
    """)
    conn.commit()
    return conn


def save_check_result(conn: sqlite3.Connection, result: dict):
    c = conn.execute(
        """INSERT INTO sync_checks
           (checked_at, overall_ok, epoch_match, balance_match, miner_count_match,
            mismatch_details, merkle_roots, node_data)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            result["timestamp"],
            1 if result["overall_ok"] else 0,
            1 if result["epoch_match"] else 0,
            1 if result["balance_match"] else 0,
            1 if result["miner_count_match"] else 0,
            json.dumps(result.get("mismatches", [])),
            json.dumps(result.get("merkle_roots", {})),
            json.dumps(result.get("node_data", {})),
        )
    )
    check_id = c.lastrowid
    for nd in result.get("node_snapshots", []):
        conn.execute(
            """INSERT INTO node_snapshots
               (check_id, node_id, node_name, reachable, version, epoch, slot,
                enrolled_miners, spot_balance, active_miner_count, merkle_root, raw_data)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                check_id,
                nd["node_id"], nd["node_name"],
                1 if nd.get("reachable") else 0,
                nd.get("version"), nd.get("epoch"), nd.get("slot"),
                nd.get("enrolled_miners"), nd.get("spot_balance"),
                nd.get("active_miner_count"), nd.get("merkle_root"),
                json.dumps(nd.get("raw_data", {})),
            )
        )
    conn.commit()
    return check_id


def show_history(db_path: Path = DB_PATH, limit: int = 20):
    if not db_path.exists():
        print("No history found. Run a check first.")
        return
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT checked_at, overall_ok, epoch_match, balance_match, mismatch_details "
        "FROM sync_checks ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    print(f"{'Timestamp':<30} {'Status':<10} {'Epoch':<8} {'Balance':<10} Mismatches")
    print("-" * 80)
    for r in rows:
        status = "✅ OK" if r[1] else "❌ FAIL"
        epoch = "✅" if r[2] else "❌"
        bal = "✅" if r[3] else "❌"
        mismatches = json.loads(r[4]) if r[4] else []
        mm_str = "; ".join(mismatches[:2]) if mismatches else "-"
        print(f"{r[0]:<30} {status:<10} {epoch:<8} {bal:<10} {mm_str}")
    conn.close()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch(url: str, timeout: int = TIMEOUT_SECONDS) -> Optional[dict]:
    """Fetch JSON from a URL. Returns None on failure."""
    ctx = __import__("ssl").create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rustchain-ledger-verify/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read())
    except Exception as e:
        return None


def post_webhook(url: str, payload: dict):
    """POST JSON payload to a webhook URL."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "User-Agent": "rustchain-ledger-verify/1.0"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except Exception as e:
        print(f"  ⚠️  Webhook delivery failed: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Merkle computation
# ---------------------------------------------------------------------------

def compute_merkle_root(miner_list: List[dict]) -> str:
    """
    Compute a Merkle root over sorted miner data for cross-node comparison.
    Miners are sorted by miner_id for determinism.
    """
    if not miner_list:
        return hashlib.sha256(b"empty").hexdigest()

    # Normalize each miner to a canonical string
    leaves = []
    for m in sorted(miner_list, key=lambda x: x.get("miner_id", x.get("wallet_name", ""))):
        canonical = json.dumps(
            {k: m.get(k) for k in sorted(m.keys())},
            sort_keys=True, separators=(",", ":")
        )
        leaves.append(hashlib.sha256(canonical.encode()).digest())

    # Build Merkle tree
    while len(leaves) > 1:
        if len(leaves) % 2 == 1:
            leaves.append(leaves[-1])  # duplicate last for odd count
        leaves = [
            hashlib.sha256(leaves[i] + leaves[i + 1]).digest()
            for i in range(0, len(leaves), 2)
        ]

    return leaves[0].hex()


# ---------------------------------------------------------------------------
# Node querying
# ---------------------------------------------------------------------------

def query_node(node: dict) -> dict:
    """Query all relevant endpoints for a single node."""
    base = node["url"]
    result = {
        "node_id": node["id"],
        "node_name": node["name"],
        "reachable": False,
        "raw_data": {},
    }

    # Health
    health = fetch(f"{base}/health")
    if not health:
        result["error"] = "Node unreachable"
        return result

    result["reachable"] = True
    result["version"] = health.get("version") or health.get("node_version")
    result["raw_data"]["health"] = health

    # Epoch
    epoch_data = fetch(f"{base}/epoch")
    if epoch_data:
        result["epoch"] = epoch_data.get("epoch")
        result["slot"] = epoch_data.get("slot")
        result["enrolled_miners"] = epoch_data.get("enrolled_miners") or epoch_data.get("total_miners")
        result["raw_data"]["epoch"] = epoch_data

    # Stats
    stats = fetch(f"{base}/api/stats")
    if stats:
        result["total_balance"] = stats.get("total_balance")
        result["miner_count"] = stats.get("miner_count") or stats.get("total_miners")
        result["raw_data"]["stats"] = stats

    # Spot check wallet balance
    balance_data = fetch(f"{base}/wallet/balance?miner_id={SPOT_CHECK_WALLET}")
    if balance_data:
        result["spot_balance"] = balance_data.get("balance") or balance_data.get("rtc_balance")
        result["raw_data"]["spot_balance"] = balance_data

    # Miners list (for Merkle)
    miners_data = fetch(f"{base}/api/miners")
    if miners_data:
        miners = miners_data if isinstance(miners_data, list) else miners_data.get("miners", [])
        result["active_miner_count"] = len(miners)
        result["merkle_root"] = compute_merkle_root(miners)
        result["raw_data"]["miners_sample"] = miners[:3]  # Save a sample, not all

    return result


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------

def compare_nodes(snapshots: List[dict]) -> dict:
    """Compare node snapshots and return a verification result."""
    reachable = [s for s in snapshots if s.get("reachable")]
    unreachable = [s for s in snapshots if not s.get("reachable")]

    mismatches = []
    epoch_match = True
    balance_match = True
    miner_count_match = True

    if len(reachable) < 2:
        return {
            "epoch_match": False,
            "balance_match": False,
            "miner_count_match": False,
            "mismatches": ["Insufficient reachable nodes for comparison"],
            "reachable_count": len(reachable),
        }

    # Epoch comparison
    epochs = [s.get("epoch") for s in reachable if s.get("epoch") is not None]
    if epochs and len(set(epochs)) > 1:
        epoch_match = False
        mismatches.append(f"EPOCH MISMATCH: {dict(zip([s['node_id'] for s in reachable], epochs))}")

    # Slot comparison (allow ±5 drift)
    slots = {s["node_id"]: s.get("slot") for s in reachable if s.get("slot") is not None}
    if len(slots) > 1:
        slot_values = [v for v in slots.values() if v is not None]
        if slot_values and (max(slot_values) - min(slot_values)) > 5:
            mismatches.append(f"SLOT DRIFT: {slots}")

    # Balance comparison
    balances = [s.get("spot_balance") for s in reachable if s.get("spot_balance") is not None]
    if balances and len(set(balances)) > 1:
        balance_match = False
        mismatches.append(f"BALANCE MISMATCH: {dict(zip([s['node_id'] for s in reachable], balances))}")

    # Miner count comparison
    miner_counts = [s.get("active_miner_count") for s in reachable if s.get("active_miner_count") is not None]
    if miner_counts and len(set(miner_counts)) > 1:
        miner_count_match = False
        mismatches.append(f"MINER COUNT MISMATCH: {dict(zip([s['node_id'] for s in reachable], miner_counts))}")

    # Merkle comparison
    merkle_roots = {s["node_id"]: s.get("merkle_root") for s in reachable if s.get("merkle_root")}
    roots = list(set(v for v in merkle_roots.values() if v))
    if len(roots) > 1:
        mismatches.append(f"MERKLE ROOT MISMATCH: {merkle_roots}")

    if unreachable:
        mismatches.append(f"UNREACHABLE: {[s['node_name'] for s in unreachable]}")

    return {
        "epoch_match": epoch_match,
        "balance_match": balance_match,
        "miner_count_match": miner_count_match,
        "mismatches": mismatches,
        "merkle_roots": merkle_roots,
        "reachable_count": len(reachable),
    }


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def print_report(result: dict):
    now = result["timestamp"]
    snapshots = result["node_snapshots"]
    comparison = result["comparison"]

    print()
    print("=" * 60)
    print("  RustChain Cross-Node Verification Report")
    print("=" * 60)
    print(f"  Timestamp: {now}")
    print()

    print("  Node Health:")
    for s in snapshots:
        status = "🟢" if s.get("reachable") else "🔴"
        version = s.get("version", "N/A")
        err = f" — {s.get('error', 'unreachable')}" if not s.get("reachable") else ""
        print(f"    {s['node_name']}: {status} v{version}{err}")

    print()
    print("  Epoch State:")
    for s in snapshots:
        if s.get("reachable"):
            ep = s.get("epoch", "?")
            slot = s.get("slot", "?")
            miners = s.get("enrolled_miners", s.get("active_miner_count", "?"))
            epoch_ok = "✅" if result["epoch_match"] else "❌"
            print(f"    {s['node_name']}: epoch={ep}, slot={slot}, miners={miners}  {epoch_ok}")
        else:
            print(f"    {s['node_name']}: ❌ unreachable")

    print()
    print(f"  Balance Spot-Check ({SPOT_CHECK_WALLET}):")
    for s in snapshots:
        if s.get("reachable") and s.get("spot_balance") is not None:
            bal = s.get("spot_balance", 0)
            bal_ok = "✅" if result["balance_match"] else "❌"
            print(f"    {s['node_name']}: {bal:,.2f} RTC  {bal_ok}")

    print()
    print("  Merkle Roots (Active Miners):")
    for node_id, root in result.get("merkle_roots", {}).items():
        node_name = next((s["node_name"] for s in snapshots if s["node_id"] == node_id), node_id)
        print(f"    {node_name}: {root[:16]}...")

    print()
    overall = "✅ ALL NODES IN SYNC" if result["overall_ok"] else "❌ SYNC MISMATCH DETECTED"
    print(f"  Result: {overall}")

    if result.get("mismatches"):
        print()
        print("  ⚠️  Mismatches:")
        for m in result["mismatches"]:
            print(f"    - {m}")

    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# Main verification run
# ---------------------------------------------------------------------------

def run_verification(
    webhook_url: Optional[str] = None,
    ci_mode: bool = False,
    db_path: Path = DB_PATH,
) -> Tuple[dict, bool]:
    """Run full verification. Returns (result, ok)."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"🔍 Querying {len(NODES)} nodes...")
    snapshots = []
    for node in NODES:
        print(f"   Querying {node['name']}...", end=" ", flush=True)
        snap = query_node(node)
        status = "✅" if snap.get("reachable") else "❌"
        print(status)
        snapshots.append(snap)

    comparison = compare_nodes(snapshots)

    result = {
        "timestamp": timestamp,
        "overall_ok": not comparison["mismatches"] or (
            comparison["reachable_count"] >= 2
            and comparison["epoch_match"]
            and comparison["balance_match"]
            and comparison["miner_count_match"]
        ),
        "epoch_match": comparison["epoch_match"],
        "balance_match": comparison["balance_match"],
        "miner_count_match": comparison["miner_count_match"],
        "mismatches": comparison.get("mismatches", []),
        "merkle_roots": comparison.get("merkle_roots", {}),
        "node_snapshots": snapshots,
        "node_data": {s["node_id"]: s.get("raw_data", {}) for s in snapshots},
        "comparison": comparison,
    }

    # Filter mismatches: unreachable-only doesn't fail overall if ≥2 reachable
    filtered_mismatches = [m for m in result["mismatches"] if "UNREACHABLE" not in m]
    result["overall_ok"] = len(filtered_mismatches) == 0

    # Save to DB
    conn = init_db(db_path)
    save_check_result(conn, result)
    conn.close()

    # Print report
    print_report(result)

    # Webhook on mismatch
    if webhook_url and not result["overall_ok"]:
        print(f"📤 Sending webhook to {webhook_url}...")
        post_webhook(webhook_url, {
            "event": "rustchain_sync_mismatch",
            "timestamp": timestamp,
            "mismatches": result["mismatches"],
            "merkle_roots": result["merkle_roots"],
        })

    return result, result["overall_ok"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="RustChain Cross-Node Ledger Verification Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 ledger_verify.py              # One-shot check
  python3 ledger_verify.py --ci         # Exit 1 if mismatch (CI mode)
  python3 ledger_verify.py --webhook https://hooks.slack.com/...
  python3 ledger_verify.py --watch 300  # Check every 5 minutes
  python3 ledger_verify.py --history    # Show recent check history
"""
    )
    parser.add_argument("--ci", action="store_true",
                        help="Exit non-zero on any mismatch (for GitHub Actions)")
    parser.add_argument("--webhook", metavar="URL",
                        help="POST mismatch alerts to this webhook URL")
    parser.add_argument("--watch", type=int, metavar="SECONDS",
                        help="Run continuously, checking every N seconds")
    parser.add_argument("--history", action="store_true",
                        help="Show recent verification history")
    parser.add_argument("--db", default=str(DB_PATH),
                        help=f"SQLite database path (default: {DB_PATH})")
    args = parser.parse_args()

    db_path = Path(args.db)

    if args.history:
        show_history(db_path)
        return

    if args.watch:
        print(f"🔁 Watch mode: checking every {args.watch}s (Ctrl+C to stop)")
        all_ok = True
        try:
            while True:
                _, ok = run_verification(
                    webhook_url=args.webhook,
                    ci_mode=args.ci,
                    db_path=db_path,
                )
                if not ok:
                    all_ok = False
                print(f"Next check in {args.watch}s...")
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nWatch mode stopped.")
        if args.ci and not all_ok:
            sys.exit(1)
        return

    _, ok = run_verification(
        webhook_url=args.webhook,
        ci_mode=args.ci,
        db_path=db_path,
    )

    if args.ci and not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
