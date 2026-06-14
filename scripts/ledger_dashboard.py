#!/usr/bin/env python3
"""
RustChain Ledger Dashboard
============================
Queries the RustChain VPS and displays a live dashboard of ledger health,
balances, recent transfers, and supply breakdown.

Usage:
    # Via SSH to VPS (default):
    python3 ledger_dashboard.py

    # With explicit credentials:
    python3 ledger_dashboard.py --ssh-host 50.28.86.131 --ssh-user root --ssh-pass PASS

    # With local DB copy:
    python3 ledger_dashboard.py --db-path /path/to/rustchain_v2.db

    # JSON output:
    python3 ledger_dashboard.py --json

Environment variables:
    RC_SSH_HOST     VPS hostname (default: 50.28.86.131)
    RC_SSH_USER     VPS SSH user (default: root)
    RC_SSH_PASS     VPS SSH password
    RC_DB_PATH      Local path to rustchain_v2.db
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MICRO_RTC = 1_000_000

FOUNDER_WALLETS = {
    "founder_community",
    "founder_dev_fund",
    "founder_founders",
    "founder_team_bounty",
}

SYSTEM_WALLETS = {
    "airdrop_pool",
    "bottube_platform",
    "team_bounty",
    "premine_completion",
}


# ---------------------------------------------------------------------------
# SSH query helper
# ---------------------------------------------------------------------------

def ssh_query(sql: str, ssh_host: str, ssh_user: str, ssh_pass: str,
              db_path: str = "/root/rustchain/rustchain_v2.db") -> str:
    """Run a SQLite query on the remote VPS via SSH and return raw output."""
    # Escape single quotes in SQL for the shell
    escaped_sql = sql.replace("'", "'\\''")
    cmd = [
        "sshpass", "-p", ssh_pass,
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        f"{ssh_user}@{ssh_host}",
        f"sqlite3 -separator '|' {db_path} '{escaped_sql}'",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"SSH query failed: {result.stderr[:200]}")
    return result.stdout.strip()


def local_query(conn: sqlite3.Connection, sql: str) -> list[tuple]:
    """Run a query against a local SQLite connection."""
    cur = conn.cursor()
    cur.execute(sql)
    return cur.fetchall()


class LedgerDashboard:
    """Queries the RustChain ledger and generates a dashboard."""

    def __init__(self, mode: str = "ssh", **kwargs):
        self.mode = mode
        self.ssh_host = kwargs.get("ssh_host", "50.28.86.131")
        self.ssh_user = kwargs.get("ssh_user", "root")
        self.ssh_pass = kwargs.get("ssh_pass", "")
        self.conn = kwargs.get("conn", None)
        self.data: dict[str, Any] = {}

    def query(self, sql: str) -> list[list[str]]:
        """Run a query and return rows as lists of strings."""
        if self.mode == "local" and self.conn:
            rows = local_query(self.conn, sql)
            return [list(map(str, r)) for r in rows]
        else:
            raw = ssh_query(sql, self.ssh_host, self.ssh_user, self.ssh_pass)
            if not raw:
                return []
            return [line.split("|") for line in raw.split("\n") if line]

    def collect_all(self) -> dict:
        """Collect all dashboard data."""
        self.data["generated_at"] = datetime.now(timezone.utc).isoformat()
        self.data["top_balances"] = self._top_balances()
        self.data["recent_transfers"] = self._recent_transfers()
        self.data["pending_transfers"] = self._pending_transfers()
        self.data["supply_breakdown"] = self._supply_breakdown()
        self.data["health"] = self._health_checks()
        self.data["mining_stats"] = self._mining_stats()
        self.data["ledger_stats"] = self._ledger_stats()
        return self.data

    def _top_balances(self) -> list[dict]:
        rows = self.query(
            "SELECT miner_id, amount_i64 FROM balances "
            "WHERE amount_i64 > 0 ORDER BY amount_i64 DESC LIMIT 30"
        )
        return [
            {"wallet": r[0], "balance_rtc": round(int(r[1]) / MICRO_RTC, 6)}
            for r in rows
        ]

    def _recent_transfers(self) -> list[dict]:
        cutoff = int(time.time()) - 86400  # last 24h
        rows = self.query(
            f"SELECT id, ts, miner_id, delta_i64, reason FROM ledger "
            f"WHERE ts > {cutoff} ORDER BY ts DESC LIMIT 50"
        )
        transfers = []
        for r in rows:
            try:
                transfers.append({
                    "id": int(r[0]),
                    "timestamp": datetime.fromtimestamp(int(r[1]), tz=timezone.utc).isoformat(),
                    "wallet": r[2],
                    "amount_rtc": round(int(r[3]) / MICRO_RTC, 6),
                    "reason": r[4] if len(r) > 4 else "",
                })
            except (ValueError, IndexError):
                continue
        return transfers

    def _pending_transfers(self) -> list[dict]:
        rows = self.query(
            "SELECT id, from_miner, to_miner, amount_i64, reason, status, "
            "datetime(created_at, 'unixepoch'), datetime(confirms_at, 'unixepoch') "
            "FROM pending_ledger WHERE status = 'pending' "
            "ORDER BY created_at DESC LIMIT 30"
        )
        return [
            {
                "id": int(r[0]),
                "from": r[1],
                "to": r[2],
                "amount_rtc": round(int(r[3]) / MICRO_RTC, 6),
                "reason": r[4] if len(r) > 4 else "",
                "status": r[5] if len(r) > 5 else "",
                "created_at": r[6] if len(r) > 6 else "",
                "confirms_at": r[7] if len(r) > 7 else "",
            }
            for r in rows
        ]

    def _supply_breakdown(self) -> dict:
        # Total supply from all balances
        rows = self.query("SELECT SUM(amount_i64) FROM balances")
        total_supply = int(rows[0][0]) / MICRO_RTC if rows and rows[0][0] else 0

        # Founder wallets
        founder_total = 0.0
        founder_detail = {}
        for fw in FOUNDER_WALLETS:
            rows = self.query(
                f"SELECT amount_i64 FROM balances WHERE miner_id = '{fw}'"
            )
            bal = int(rows[0][0]) / MICRO_RTC if rows and rows[0] and rows[0][0] else 0
            founder_detail[fw] = round(bal, 6)
            founder_total += bal

        # System wallets
        system_total = 0.0
        system_detail = {}
        for sw in SYSTEM_WALLETS:
            rows = self.query(
                f"SELECT amount_i64 FROM balances WHERE miner_id = '{sw}'"
            )
            bal = int(rows[0][0]) / MICRO_RTC if rows and rows[0] and rows[0][0] else 0
            system_detail[sw] = round(bal, 6)
            system_total += bal

        # Mining rewards (epoch_rewards total)
        rows = self.query("SELECT SUM(share_i64) FROM epoch_rewards")
        mining_total = int(rows[0][0]) / MICRO_RTC if rows and rows[0][0] else 0

        distributed = total_supply - founder_total - system_total

        return {
            "total_supply_rtc": round(total_supply, 2),
            "founder_wallets_rtc": round(founder_total, 2),
            "founder_detail": founder_detail,
            "system_wallets_rtc": round(system_total, 2),
            "system_detail": system_detail,
            "distributed_rtc": round(distributed, 2),
            "mining_rewards_cumulative_rtc": round(mining_total, 2),
        }

    def _health_checks(self) -> dict:
        """Verify ledger integrity: SUM(ledger.delta_i64) should equal SUM(balances.amount_i64)."""
        # Sum of all ledger deltas
        rows = self.query("SELECT SUM(delta_i64) FROM ledger")
        ledger_sum = int(rows[0][0]) if rows and rows[0][0] else 0

        # Sum of all balances
        rows = self.query("SELECT SUM(amount_i64) FROM balances")
        balance_sum = int(rows[0][0]) if rows and rows[0][0] else 0

        diff = ledger_sum - balance_sum
        ledger_ok = abs(diff) < MICRO_RTC  # within 1 RTC tolerance

        # Check for negative balances (should be impossible with CHECK constraint)
        rows = self.query(
            "SELECT COUNT(*) FROM balances WHERE amount_i64 < 0"
        )
        negative_count = int(rows[0][0]) if rows else 0

        # Ledger row count
        rows = self.query("SELECT COUNT(*) FROM ledger")
        ledger_rows = int(rows[0][0]) if rows else 0

        # Unique wallets
        rows = self.query("SELECT COUNT(DISTINCT miner_id) FROM balances WHERE amount_i64 > 0")
        active_wallets = int(rows[0][0]) if rows else 0

        # Pending count
        rows = self.query("SELECT COUNT(*) FROM pending_ledger WHERE status = 'pending'")
        pending_count = int(rows[0][0]) if rows else 0

        return {
            "ledger_sum_micro": ledger_sum,
            "balance_sum_micro": balance_sum,
            "difference_micro": diff,
            "difference_rtc": round(diff / MICRO_RTC, 6),
            "ledger_balance_match": ledger_ok,
            "negative_balances": negative_count,
            "ledger_rows": ledger_rows,
            "active_wallets": active_wallets,
            "pending_transfers": pending_count,
        }

    def _mining_stats(self) -> dict:
        # Active miners (attested in last 24h)
        cutoff = int(time.time()) - 86400
        rows = self.query(
            f"SELECT COUNT(*) FROM miner_attest_recent WHERE ts_ok > {cutoff}"
        )
        active_miners_24h = int(rows[0][0]) if rows else 0

        # Total unique miners ever
        rows = self.query("SELECT COUNT(*) FROM miner_attest_recent")
        total_miners = int(rows[0][0]) if rows else 0

        # Recent epoch rewards
        rows = self.query(
            "SELECT epoch, SUM(share_i64) FROM epoch_rewards "
            "GROUP BY epoch ORDER BY epoch DESC LIMIT 5"
        )
        recent_epochs = [
            {"epoch": int(r[0]), "total_rtc": round(int(r[1]) / MICRO_RTC, 6)}
            for r in rows
        ]

        return {
            "active_miners_24h": active_miners_24h,
            "total_miners_ever": total_miners,
            "recent_epochs": recent_epochs,
        }

    def _ledger_stats(self) -> dict:
        # Reason breakdown (top 10 by volume)
        rows = self.query(
            "SELECT "
            "  CASE "
            "    WHEN reason LIKE 'transfer_in:founder_community%' THEN 'community_payments' "
            "    WHEN reason LIKE 'transfer_in:founder_team_bounty%' THEN 'team_bounty_payments' "
            "    WHEN reason LIKE 'transfer_in:founder_dev_fund%' THEN 'dev_fund_payments' "
            "    WHEN reason LIKE 'transfer_out:%' THEN 'transfer_out' "
            "    WHEN reason LIKE 'premine_%' THEN 'premine' "
            "    WHEN reason LIKE 'epoch_reward%' THEN 'mining_rewards' "
            "    WHEN reason LIKE 'wallet_consolidation%' THEN 'consolidation' "
            "    WHEN reason LIKE 'ghost_wallet%' THEN 'ghost_recovery' "
            "    WHEN reason LIKE 'clawback%' THEN 'clawback' "
            "    ELSE 'other' "
            "  END AS category, "
            "  COUNT(*), "
            "  SUM(delta_i64) "
            "FROM ledger GROUP BY category ORDER BY ABS(SUM(delta_i64)) DESC"
        )
        return {
            "categories": [
                {
                    "category": r[0],
                    "count": int(r[1]),
                    "total_rtc": round(int(r[2]) / MICRO_RTC, 2),
                }
                for r in rows
            ]
        }


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_dashboard(data: dict) -> None:
    """Print a formatted dashboard to the terminal."""
    print("\n" + "=" * 72)
    print("  RUSTCHAIN LEDGER DASHBOARD")
    print(f"  Generated: {data['generated_at']}")
    print("=" * 72)

    # Health
    h = data["health"]
    status = "HEALTHY" if h["ledger_balance_match"] and h["negative_balances"] == 0 else "UNHEALTHY"
    status_icon = "[OK]" if status == "HEALTHY" else "[!!]"
    print(f"\n  {status_icon} Ledger Health: {status}")
    print(f"    Ledger SUM:    {h['ledger_sum_micro'] / MICRO_RTC:>14.2f} RTC")
    print(f"    Balance SUM:   {h['balance_sum_micro'] / MICRO_RTC:>14.2f} RTC")
    if h["difference_rtc"] != 0:
        print(f"    Difference:    {h['difference_rtc']:>14.6f} RTC")
    print(f"    Ledger rows:   {h['ledger_rows']:>14,}")
    print(f"    Active wallets:{h['active_wallets']:>14,}")
    print(f"    Pending TXs:   {h['pending_transfers']:>14,}")
    if h["negative_balances"] > 0:
        print(f"    [!!] NEGATIVE BALANCES: {h['negative_balances']}")

    # Supply
    s = data["supply_breakdown"]
    print(f"\n  Supply Breakdown:")
    print(f"    Total supply:           {s['total_supply_rtc']:>12.2f} RTC")
    print(f"    Founder wallets:        {s['founder_wallets_rtc']:>12.2f} RTC")
    for name, bal in sorted(s["founder_detail"].items(), key=lambda x: -x[1]):
        print(f"      {name:<28s} {bal:>12.2f} RTC")
    print(f"    System wallets:         {s['system_wallets_rtc']:>12.2f} RTC")
    for name, bal in sorted(s["system_detail"].items(), key=lambda x: -x[1]):
        print(f"      {name:<28s} {bal:>12.2f} RTC")
    print(f"    Distributed:            {s['distributed_rtc']:>12.2f} RTC")
    print(f"    Mining cumulative:      {s['mining_rewards_cumulative_rtc']:>12.2f} RTC")

    # Top Balances (non-founder)
    bals = data["top_balances"]
    non_founder = [b for b in bals
                   if b["wallet"] not in FOUNDER_WALLETS
                   and b["wallet"] not in SYSTEM_WALLETS]
    print(f"\n  Top Balances (non-founder):")
    print(f"    {'Wallet':<40s} {'Balance':>12s}")
    print(f"    {'-' * 40} {'-' * 12}")
    for b in non_founder[:15]:
        print(f"    {b['wallet']:<40s} {b['balance_rtc']:>12.2f} RTC")

    # Mining
    m = data["mining_stats"]
    print(f"\n  Mining:")
    print(f"    Active miners (24h):    {m['active_miners_24h']}")
    print(f"    Total miners ever:      {m['total_miners_ever']}")
    if m["recent_epochs"]:
        print(f"    Recent epoch rewards:")
        for ep in m["recent_epochs"]:
            print(f"      Epoch {ep['epoch']}: {ep['total_rtc']:.6f} RTC")

    # Recent Transfers
    transfers = data["recent_transfers"]
    if transfers:
        print(f"\n  Recent Transfers (last 24h): {len(transfers)}")
        print(f"    {'Time':<22s} {'Wallet':<30s} {'Amount':>12s}  Reason")
        print(f"    {'-' * 22} {'-' * 30} {'-' * 12}  {'-' * 30}")
        for t in transfers[:15]:
            ts = t["timestamp"][:19].replace("T", " ")
            reason_short = t["reason"][:40] if t["reason"] else ""
            print(f"    {ts:<22s} {t['wallet']:<30s} {t['amount_rtc']:>+12.2f}  {reason_short}")
    else:
        print(f"\n  No transfers in last 24h.")

    # Pending
    pending = data["pending_transfers"]
    if pending:
        print(f"\n  Pending Transfers: {len(pending)}")
        for p in pending[:10]:
            print(f"    {p['from']} -> {p['to']}: {p['amount_rtc']:.2f} RTC"
                  f"  ({p['reason'][:30]})")
    else:
        print(f"\n  No pending transfers.")

    # Ledger Categories
    cats = data["ledger_stats"]["categories"]
    if cats:
        print(f"\n  Ledger Categories:")
        print(f"    {'Category':<30s} {'Count':>8s} {'Total RTC':>14s}")
        print(f"    {'-' * 30} {'-' * 8} {'-' * 14}")
        for c in cats:
            print(f"    {c['category']:<30s} {c['count']:>8,} {c['total_rtc']:>14.2f}")

    print(f"\n{'=' * 72}")
    print("  END OF DASHBOARD")
    print(f"{'=' * 72}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="RustChain Ledger Dashboard")
    p.add_argument("--db-path", default=os.environ.get("RC_DB_PATH", ""),
                    help="Path to local rustchain_v2.db")
    p.add_argument("--ssh-host", default=os.environ.get("RC_SSH_HOST", "50.28.86.131"),
                    help="VPS SSH host")
    p.add_argument("--ssh-user", default=os.environ.get("RC_SSH_USER", "root"),
                    help="VPS SSH user")
    p.add_argument("--ssh-pass", default=os.environ.get("RC_SSH_PASS", ""),
                    help="VPS SSH password")
    p.add_argument("--json", action="store_true",
                    help="Output JSON to stdout")
    p.add_argument("--json-file", default="",
                    help="Write JSON to file")
    return p.parse_args()


def main():
    args = parse_args()

    if args.db_path and os.path.exists(args.db_path):
        conn = sqlite3.connect(args.db_path)
        dash = LedgerDashboard(mode="local", conn=conn)
    else:
        ssh_pass = args.ssh_pass
        if not ssh_pass:
            # Try reading from environment
            ssh_pass = os.environ.get("RC_SSH_PASS", "")
        if not ssh_pass:
            print("ERROR: No SSH password. Use --ssh-pass or set RC_SSH_PASS")
            sys.exit(1)

        dash = LedgerDashboard(
            mode="ssh",
            ssh_host=args.ssh_host,
            ssh_user=args.ssh_user,
            ssh_pass=ssh_pass,
        )

    print("Collecting data...")
    data = dash.collect_all()

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print_dashboard(data)

    if args.json_file:
        with open(args.json_file, "w") as f:
            json.dump(data, f, indent=2)
        print(f"JSON written to {args.json_file}")

    # Exit code based on health
    if not data["health"]["ledger_balance_match"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
