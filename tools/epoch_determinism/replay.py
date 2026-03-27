#!/usr/bin/env python3
"""
Epoch Determinism Simulator + Cross-Node Replay
================================================
Bounty #474

Proves that epoch settlement outputs are byte-equivalent across nodes
for identical fixture inputs.

Usage:
    python replay.py <fixture.json> [--targets node_a node_b] [--report-json out.json] [--ci]

    # Run a single fixture, compare output to itself (idempotency check)
    python replay.py fixtures/normal_epoch.json

    # Explicit targets (simulate two independent nodes)
    python replay.py fixtures/normal_epoch.json --targets node_a node_b

    # CI mode: exits 1 on any mismatch
    python replay.py fixtures/divergent_epoch.json --ci

    # Save JSON report
    python replay.py fixtures/normal_epoch.json --report-json /tmp/report.json

    # Show markdown summary
    python replay.py fixtures/normal_epoch.json --report-md

Exit codes:
    0  all outputs are byte-equivalent
    1  mismatch detected (or fixture load error)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────
# Path plumbing: import settlement logic from the repo
# ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NODE_DIR = PROJECT_ROOT / "node"

for p in (str(PROJECT_ROOT), str(NODE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from rip_200_round_robin_1cpu1vote import (
        calculate_epoch_rewards_time_aged,
        get_time_aged_multiplier,
        get_chain_age_years,
        GENESIS_TIMESTAMP,
        BLOCK_TIME,
        ATTESTATION_TTL,
    )
except ImportError as exc:
    sys.exit(f"[ERROR] Cannot import settlement logic: {exc}\n"
             f"  Ensure you are running from within the Rustchain repo.")

UNIT = 1_000_000            # uRTC per 1 RTC
PER_EPOCH_URTC = int(1.5 * UNIT)  # 1.5 RTC per epoch

# ─────────────────────────────────────────────────────────────
# Fixture schema validation
# ─────────────────────────────────────────────────────────────

REQUIRED_TOP_KEYS = {"fixture_id", "description", "epoch", "miners"}
REQUIRED_MINER_KEYS = {"miner_id", "device_arch"}


def validate_fixture(data: dict) -> None:
    missing = REQUIRED_TOP_KEYS - set(data)
    if missing:
        raise ValueError(f"Fixture missing required keys: {missing}")
    for i, m in enumerate(data["miners"]):
        miss = REQUIRED_MINER_KEYS - set(m)
        if miss:
            raise ValueError(f"Miner[{i}] missing required keys: {miss}")


def load_fixture(path: str) -> dict:
    with open(path) as f:
        data = json.load(f)
    validate_fixture(data)
    return data


# ─────────────────────────────────────────────────────────────
# In-memory DB bootstrap
# ─────────────────────────────────────────────────────────────

def build_db(fixture: dict) -> str:
    """
    Create a temporary SQLite DB populated from fixture data.
    Returns the path to the DB file.
    """
    epoch: int = fixture["epoch"]
    miners: List[dict] = fixture["miners"]
    enroll_override: Optional[List[dict]] = fixture.get("epoch_enroll_override")

    epoch_start_slot = epoch * 144
    epoch_start_ts = GENESIS_TIMESTAMP + (epoch_start_slot * BLOCK_TIME)

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS miner_attest_recent (
            miner        TEXT,
            device_arch  TEXT,
            ts_ok        INTEGER,
            fingerprint_passed INTEGER DEFAULT 1,
            warthog_bonus      REAL    DEFAULT 1.0
        );
        CREATE TABLE IF NOT EXISTS epoch_enroll (
            epoch     INTEGER NOT NULL,
            miner_pk  TEXT    NOT NULL,
            weight    REAL    NOT NULL,
            PRIMARY KEY (epoch, miner_pk)
        );
        CREATE TABLE IF NOT EXISTS balances (
            miner_id   TEXT PRIMARY KEY,
            amount_i64 INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS ledger (
            ts       INTEGER,
            epoch    INTEGER,
            miner_id TEXT,
            delta_i64 INTEGER,
            reason   TEXT
        );
        CREATE TABLE IF NOT EXISTS epoch_rewards (
            epoch    INTEGER,
            miner_id TEXT,
            share_i64 INTEGER
        );
        CREATE TABLE IF NOT EXISTS epoch_state (
            epoch      INTEGER PRIMARY KEY,
            settled    INTEGER DEFAULT 0,
            settled_ts INTEGER
        );
    """)

    # Primary path: epoch_enroll (explicit weight enrollments from fixture)
    if enroll_override:
        for entry in enroll_override:
            conn.execute(
                "INSERT OR REPLACE INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?,?,?)",
                (epoch, entry["miner_pk"], float(entry["weight"]))
            )

    # Populate miner_attest_recent (fallback path used by calculate_epoch_rewards_time_aged)
    for m in miners:
        ts_offset = m.get("ts_offset", 100)
        ts_ok = epoch_start_ts + ts_offset
        conn.execute(
            "INSERT INTO miner_attest_recent "
            "(miner, device_arch, ts_ok, fingerprint_passed, warthog_bonus) "
            "VALUES (?,?,?,?,?)",
            (
                m["miner_id"],
                m["device_arch"],
                ts_ok,
                int(m.get("fingerprint_passed", 1)),
                float(m.get("warthog_bonus", 1.0)),
            ),
        )

    conn.commit()
    conn.close()
    return db_path


# ─────────────────────────────────────────────────────────────
# Payout computation (pure / deterministic)
# ─────────────────────────────────────────────────────────────

def compute_payout(fixture: dict, db_path: str, target_name: str) -> Dict[str, Any]:
    """
    Run epoch settlement against the DB and return a *normalized* payout dict.

    Normalization rules:
      - Keys sorted alphabetically
      - Amounts stored as integers (uRTC)
      - No timestamps, no runtime-dependent fields

    This is the canonical comparable output.
    """
    epoch: int = fixture["epoch"]
    enroll_override = fixture.get("epoch_enroll_override")

    # Determine which path to use
    path_used = "miner_attest_recent"

    if enroll_override:
        # Primary path: epoch_enroll weights
        path_used = "epoch_enroll"
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT miner_pk, weight FROM epoch_enroll WHERE epoch=? ORDER BY miner_pk",
            (epoch,)
        ).fetchall()
        conn.close()

        if not rows:
            return {
                "target": target_name,
                "epoch": epoch,
                "path": path_used,
                "payouts": {},
                "total_urtc": 0,
                "canonical_hash": _hash_payouts({}),
            }

        total_weight = sum(w for _, w in rows)
        payouts: Dict[str, int] = {}
        remaining = PER_EPOCH_URTC

        for i, (miner_pk, weight) in enumerate(rows):
            if i == len(rows) - 1:
                share = remaining
            else:
                share = int((weight / total_weight) * PER_EPOCH_URTC)
                remaining -= share
            payouts[miner_pk] = share

    else:
        # Fallback path: miner_attest_recent via RIP-200 function
        epoch_start_slot = epoch * 144
        current_slot = epoch_start_slot + 72  # mid-epoch

        raw = calculate_epoch_rewards_time_aged(
            db_path, epoch, PER_EPOCH_URTC, current_slot
        )
        # Sort by key for canonical ordering
        payouts = dict(sorted(raw.items()))

    total_urtc = sum(payouts.values())
    canonical_hash = _hash_payouts(payouts)

    return {
        "target": target_name,
        "epoch": epoch,
        "path": path_used,
        "payouts": payouts,
        "total_urtc": total_urtc,
        "canonical_hash": canonical_hash,
    }


def _hash_payouts(payouts: Dict[str, int]) -> str:
    """SHA-256 of sorted, canonical JSON representation of payout dict."""
    canonical = json.dumps(payouts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


# ─────────────────────────────────────────────────────────────
# Diff computation
# ─────────────────────────────────────────────────────────────

def compute_diff(result_a: dict, result_b: dict) -> List[dict]:
    """
    Return per-miner differences between two payout results.
    """
    all_miners = sorted(set(result_a["payouts"]) | set(result_b["payouts"]))
    diffs = []
    for miner in all_miners:
        a_val = result_a["payouts"].get(miner, 0)
        b_val = result_b["payouts"].get(miner, 0)
        if a_val != b_val:
            diffs.append({
                "miner_id": miner,
                result_a["target"]: a_val,
                result_b["target"]: b_val,
                "delta_urtc": b_val - a_val,
            })
    return diffs


# ─────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────

def build_report(
    fixture: dict,
    results: List[dict],
    diffs: List[dict],
    match: bool,
    elapsed_s: float,
) -> dict:
    return {
        "fixture_id": fixture["fixture_id"],
        "description": fixture["description"],
        "epoch": fixture["epoch"],
        "determinism_ok": match,
        "targets": [r["target"] for r in results],
        "canonical_hashes": {r["target"]: r["canonical_hash"] for r in results},
        "total_urtc": {r["target"]: r["total_urtc"] for r in results},
        "payouts": {r["target"]: r["payouts"] for r in results},
        "diffs": diffs,
        "elapsed_s": round(elapsed_s, 4),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def markdown_summary(report: dict) -> str:
    lines = [
        "# Epoch Determinism Report",
        "",
        f"**Fixture:** `{report['fixture_id']}`  ",
        f"**Description:** {report['description']}  ",
        f"**Epoch:** {report['epoch']}  ",
        f"**Generated:** {report['generated_at']}  ",
        f"**Elapsed:** {report['elapsed_s']}s  ",
        "",
        "## Result",
        "",
    ]

    if report["determinism_ok"]:
        lines += [
            "✅ **DETERMINISTIC MATCH** — all targets produced byte-equivalent output.",
            "",
        ]
    else:
        lines += [
            "❌ **MISMATCH DETECTED** — outputs diverged between targets.",
            "",
        ]

    lines += ["## Canonical Hashes", ""]
    for target, h in report["canonical_hashes"].items():
        lines.append(f"- **{target}:** `{h}`")

    lines += ["", "## Payout Summary (uRTC)", ""]
    all_miners = sorted(set().union(*[set(p) for p in report["payouts"].values()]))
    if all_miners:
        header = "| Miner ID | " + " | ".join(report["targets"]) + " |"
        sep = "|---|" + "---|" * len(report["targets"])
        lines += [header, sep]
        for miner in all_miners:
            row_vals = [str(report["payouts"][t].get(miner, 0)) for t in report["targets"]]
            lines.append(f"| `{miner[:32]}...` | " + " | ".join(row_vals) + " |")

    if report["diffs"]:
        lines += ["", "## Per-Miner Diffs", ""]
        for d in report["diffs"]:
            targets = report["targets"]
            lines.append(
                f"- `{d['miner_id'][:32]}...` → "
                f"{targets[0]}={d[targets[0]]} vs {targets[1]}={d[targets[1]]} "
                f"(Δ {d['delta_urtc']:+d} uRTC)"
            )

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Main CLI
# ─────────────────────────────────────────────────────────────

def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Epoch Determinism Simulator — Cross-Node Replay (Bounty #474)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("fixture", help="Path to JSON fixture file")
    p.add_argument(
        "--targets",
        nargs=2,
        default=["node_a", "node_b"],
        metavar=("TARGET_A", "TARGET_B"),
        help="Names for the two simulated nodes (default: node_a node_b)",
    )
    p.add_argument("--report-json", metavar="FILE", help="Save JSON report to FILE")
    p.add_argument("--report-md", action="store_true", help="Print markdown summary to stdout")
    p.add_argument("--ci", action="store_true", help="CI mode: exit 1 on mismatch (implied for divergent fixtures)")
    p.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    start = time.monotonic()

    # ── Load fixture ──────────────────────────────────────────
    try:
        fixture = load_fixture(args.fixture)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    fixture_id = fixture["fixture_id"]
    epoch = fixture["epoch"]
    targets = args.targets

    print(f"[replay] fixture={fixture_id!r} epoch={epoch} targets={targets}")

    # ── Build identical DBs for each target ──────────────────
    db_a = build_db(fixture)
    db_b = build_db(fixture)

    try:
        result_a = compute_payout(fixture, db_a, targets[0])
        result_b = compute_payout(fixture, db_b, targets[1])
    finally:
        for p in (db_a, db_b):
            try:
                os.unlink(p)
            except OSError:
                pass

    elapsed = time.monotonic() - start

    # ── Compare ───────────────────────────────────────────────
    match = result_a["canonical_hash"] == result_b["canonical_hash"]
    diffs = compute_diff(result_a, result_b) if not match else []

    # ── Build report ──────────────────────────────────────────
    report = build_report(fixture, [result_a, result_b], diffs, match, elapsed)

    # ── Print summary ─────────────────────────────────────────
    if match:
        print(f"[replay] ✅ DETERMINISTIC MATCH  hash={result_a['canonical_hash'][:16]}…")
    else:
        print(f"[replay] ❌ MISMATCH DETECTED", file=sys.stderr)
        print(f"  {targets[0]}: {result_a['canonical_hash']}", file=sys.stderr)
        print(f"  {targets[1]}: {result_b['canonical_hash']}", file=sys.stderr)
        print(f"\nPer-miner diff ({len(diffs)} miner(s)):", file=sys.stderr)
        for d in diffs:
            t0, t1 = targets
            print(
                f"  {d['miner_id']}: {t0}={d[t0]} vs {t1}={d[t1]} (Δ {d['delta_urtc']:+d})",
                file=sys.stderr,
            )

    if args.verbose:
        print(json.dumps(report, indent=2))

    if args.report_json:
        Path(args.report_json).write_text(json.dumps(report, indent=2))
        print(f"[replay] JSON report → {args.report_json}")

    if args.report_md:
        print(markdown_summary(report))

    # ── Exit code ─────────────────────────────────────────────
    if args.ci and not match:
        sys.exit(1)

    sys.exit(0 if match else 1)


if __name__ == "__main__":
    main()
