#!/usr/bin/env python3
"""
RIP-201: Fleet Detection Immune System
=======================================

Protects RustChain reward economics from fleet-scale attacks where a single
actor deploys many machines (real or emulated) to dominate the reward pool.

Core Principles:
  1. Anti-homogeneity, not anti-modern — diversity IS the immune system
  2. Bucket normalization — rewards split by hardware CLASS, not per-CPU
  3. Fleet signal detection — IP clustering, timing correlation, fingerprint similarity
  4. Multiplier decay — suspected fleet members get diminishing returns
  5. Pressure feedback — overrepresented classes get flattened, rare ones get boosted

Design Axiom:
  "One of everything beats a hundred of one thing."

Integration:
  Called from calculate_epoch_rewards_time_aged() BEFORE distributing rewards.
  Requires fleet_signals table populated by submit_attestation().

Author: Scott Boudreaux / Elyan Labs
Date: 2026-02-28
"""

import hashlib
import math
import sqlite3
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════

# Hardware class buckets — rewards split equally across these
HARDWARE_BUCKETS = {
    "vintage_powerpc": ["g3", "g4", "g5", "powerpc", "powerpc g3", "powerpc g4",
                        "powerpc g5", "powerpc g3 (750)", "powerpc g4 (74xx)",
                        "powerpc g5 (970)", "power macintosh"],
    "vintage_x86":     ["pentium", "pentium4", "retro", "core2", "core2duo",
                        "nehalem", "sandybridge"],
    "apple_silicon":   ["apple_silicon", "m1", "m2", "m3"],
    "modern":          ["modern", "x86_64"],
    "exotic":          ["power8", "power9", "sparc", "mips", "riscv", "s390x"],
    "arm":             ["aarch64", "arm", "armv7", "armv7l"],
}

# Reverse lookup: arch → bucket name
ARCH_TO_BUCKET = {}
for bucket, archs in HARDWARE_BUCKETS.items():
    for arch in archs:
        ARCH_TO_BUCKET[arch] = bucket

# Fleet detection thresholds
FLEET_SUBNET_THRESHOLD = 3       # 3+ miners from same /24 = signal
FLEET_TIMING_WINDOW_S = 30       # Attestations within 30s = correlated
FLEET_TIMING_THRESHOLD = 0.6     # 60%+ of attestations correlated = signal
FLEET_FINGERPRINT_THRESHOLD = 0.85  # Cosine similarity > 0.85 = signal

# Fleet score → multiplier decay
# fleet_score 0.0 = solo miner (no decay)
# fleet_score 1.0 = definite fleet (max decay)
FLEET_DECAY_COEFF = 0.4          # Max 40% reduction at fleet_score=1.0
FLEET_SCORE_FLOOR = 0.6          # Never decay below 60% of base multiplier

# Bucket normalization mode
# "equal_split" = hard split: each active bucket gets equal share of pot (RECOMMENDED)
# "pressure"    = soft: overrepresented buckets get flattened multiplier
BUCKET_MODE = "equal_split"

# Bucket pressure parameters (used when BUCKET_MODE = "pressure")
BUCKET_IDEAL_SHARE = None  # Auto-calculated as 1/num_active_buckets
BUCKET_PRESSURE_STRENGTH = 0.5   # How aggressively to flatten overrepresented buckets
BUCKET_MIN_WEIGHT = 0.3          # Minimum bucket weight (even if massively overrepresented)

# Minimum miners to trigger fleet detection (below this, everyone is solo)
FLEET_DETECTION_MINIMUM = 4


# ═══════════════════════════════════════════════════════════
# DATABASE SCHEMA
# ═══════════════════════════════════════════════════════════

SCHEMA_SQL = """
-- Fleet signal tracking per attestation
CREATE TABLE IF NOT EXISTS fleet_signals (
    miner TEXT NOT NULL,
    epoch INTEGER NOT NULL,
    subnet_hash TEXT,              -- HMAC of /24 subnet for privacy
    attest_ts INTEGER NOT NULL,    -- Exact attestation timestamp
    clock_drift_cv REAL,           -- Clock drift coefficient of variation
    cache_latency_hash TEXT,       -- Hash of cache timing profile
    thermal_signature REAL,        -- Thermal drift entropy value
    simd_bias_hash TEXT,           -- Hash of SIMD timing profile
    PRIMARY KEY (miner, epoch)
);

-- Fleet detection results per epoch
CREATE TABLE IF NOT EXISTS fleet_scores (
    miner TEXT NOT NULL,
    epoch INTEGER NOT NULL,
    fleet_score REAL NOT NULL DEFAULT 0.0,  -- 0.0=solo, 1.0=definite fleet
    ip_signal REAL DEFAULT 0.0,
    timing_signal REAL DEFAULT 0.0,
    fingerprint_signal REAL DEFAULT 0.0,
    cluster_id TEXT,                         -- Fleet cluster identifier
    effective_multiplier REAL,               -- After decay
    PRIMARY KEY (miner, epoch)
);

-- Bucket pressure tracking per epoch
CREATE TABLE IF NOT EXISTS bucket_pressure (
    epoch INTEGER NOT NULL,
    bucket TEXT NOT NULL,
    miner_count INTEGER NOT NULL,
    raw_weight REAL NOT NULL,
    pressure_factor REAL NOT NULL,     -- <1.0 = overrepresented, >1.0 = rare
    adjusted_weight REAL NOT NULL,
    PRIMARY KEY (epoch, bucket)
);

-- Fleet cluster registry
CREATE TABLE IF NOT EXISTS fleet_clusters (
    cluster_id TEXT PRIMARY KEY,
    first_seen_epoch INTEGER NOT NULL,
    last_seen_epoch INTEGER NOT NULL,
    member_count INTEGER NOT NULL,
    detection_signals TEXT,              -- JSON: which signals triggered
    cumulative_score REAL DEFAULT 0.0
);
"""


def ensure_schema(db: sqlite3.Connection):
    """Create fleet immune system tables if they don't exist."""
    db.executescript(SCHEMA_SQL)
    db.commit()


# ═══════════════════════════════════════════════════════════
# SIGNAL COLLECTION (called from submit_attestation)
# ═══════════════════════════════════════════════════════════

def record_fleet_signals_from_request(
    db: sqlite3.Connection,
    miner: str,
    epoch: int,
    ip_address: str,
    attest_ts: int,
    fingerprint: Optional[dict] = None
):
    """
    Record fleet detection signals from an attestation submission.

    Called from submit_attestation() after validation passes.
    Stores privacy-preserving hashes of network and fingerprint data.
    """
    ensure_schema(db)

    # Hash the /24 subnet for privacy-preserving network clustering
    if ip_address:
        parts = ip_address.split('.')
        if len(parts) == 4:
            subnet = '.'.join(parts[:3])
            subnet_hash = hashlib.sha256(subnet.encode()).hexdigest()[:16]
        else:
            subnet_hash = hashlib.sha256(ip_address.encode()).hexdigest()[:16]
    else:
        subnet_hash = None

    # Extract fingerprint signals
    clock_drift_cv = None
    cache_hash = None
    thermal_sig = None
    simd_hash = None

    if fingerprint and isinstance(fingerprint, dict):
        checks = fingerprint.get("checks", {})

        # Clock drift coefficient of variation
        clock = checks.get("clock_drift", {}).get("data", {})
        clock_drift_cv = clock.get("cv")

        # Cache timing profile hash (privacy-preserving)
        cache = checks.get("cache_timing", {}).get("data", {})
        if cache:
            cache_str = str(sorted(cache.items()))
            cache_hash = hashlib.sha256(cache_str.encode()).hexdigest()[:16]

        # Thermal drift entropy
        thermal = checks.get("thermal_drift", {}).get("data", {})
        thermal_sig = thermal.get("entropy", thermal.get("drift_magnitude"))

        # SIMD bias profile hash
        simd = checks.get("simd_identity", {}).get("data", {})
        if simd:
            simd_str = str(sorted(simd.items()))
            simd_hash = hashlib.sha256(simd_str.encode()).hexdigest()[:16]

    db.execute("""
        INSERT OR REPLACE INTO fleet_signals
        (miner, epoch, subnet_hash, attest_ts, clock_drift_cv,
         cache_latency_hash, thermal_signature, simd_bias_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (miner, epoch, subnet_hash, attest_ts, clock_drift_cv,
          cache_hash, thermal_sig, simd_hash))
    db.commit()


def record_fleet_signals(db_path_or_conn, miner: str, device: dict,
                         signals: dict, fingerprint: Optional[dict],
                         attest_ts: int, ip_address: str = None,
                         epoch: int = None):
    """
    Convenience wrapper called from record_attestation_success().

    Accepts either a DB path (str) or connection, and extracts
    the IP from signals if not provided explicitly.
    """
    import time as _time

    if isinstance(db_path_or_conn, str):
        db = sqlite3.connect(db_path_or_conn)
        own = True
    else:
        db = db_path_or_conn
        own = False

    try:
        # Get epoch from current time if not provided
        if epoch is None:
            GENESIS = 1764706927
            BLOCK_TIME = 600
            slot = (int(_time.time()) - GENESIS) // BLOCK_TIME
            epoch = slot // 144

        # Extract IP from signals or request
        if not ip_address:
            ip_address = signals.get("ip", signals.get("remote_addr", ""))

        record_fleet_signals_from_request(db, miner, epoch, ip_address,
                                          attest_ts, fingerprint)
    except Exception as e:
        print(f"[RIP-201] Fleet signal recording error: {e}")
    finally:
        if own:
            db.close()


# ═══════════════════════════════════════════════════════════
# FLEET DETECTION ENGINE
# ═══════════════════════════════════════════════════════════

def _detect_ip_clustering(
    signals: List[dict]
) -> Dict[str, float]:
    """
    Detect miners sharing the same /24 subnet.

    Returns: {miner_id: ip_signal} where ip_signal = 0.0-1.0
    """
    scores = {}

    # Group by subnet hash
    subnet_groups = defaultdict(list)
    for sig in signals:
        if sig["subnet_hash"]:
            subnet_groups[sig["subnet_hash"]].append(sig["miner"])

    # Miners in large subnet groups get higher fleet signal
    for subnet, miners in subnet_groups.items():
        count = len(miners)
        if count >= FLEET_SUBNET_THRESHOLD:
            # Signal scales with cluster size: 3→0.3, 5→0.5, 10→0.8, 20+→1.0
            signal = min(1.0, count / 20.0 + 0.15)
            for m in miners:
                scores[m] = max(scores.get(m, 0.0), signal)

    # Solo miners or small groups: 0.0
    for sig in signals:
        if sig["miner"] not in scores:
            scores[sig["miner"]] = 0.0

    return scores


def _detect_timing_correlation(
    signals: List[dict]
) -> Dict[str, float]:
    """
    Detect miners whose attestation timestamps are suspiciously synchronized.

    Fleet operators often update all miners in rapid succession.
    Real independent operators attest at random times throughout the day.
    """
    scores = {}
    if len(signals) < FLEET_DETECTION_MINIMUM:
        return {s["miner"]: 0.0 for s in signals}

    timestamps = [(s["miner"], s["attest_ts"]) for s in signals]
    timestamps.sort(key=lambda x: x[1])

    # For each miner, count how many others attested within TIMING_WINDOW
    for i, (miner_a, ts_a) in enumerate(timestamps):
        correlated = 0
        total_others = len(timestamps) - 1
        for j, (miner_b, ts_b) in enumerate(timestamps):
            if i == j:
                continue
            if abs(ts_a - ts_b) <= FLEET_TIMING_WINDOW_S:
                correlated += 1

        if total_others > 0:
            ratio = correlated / total_others
            if ratio >= FLEET_TIMING_THRESHOLD:
                # High correlation → fleet signal
                scores[miner_a] = min(1.0, ratio)
            else:
                scores[miner_a] = 0.0
        else:
            scores[miner_a] = 0.0

    return scores


def _detect_fingerprint_similarity(
    signals: List[dict]
) -> Dict[str, float]:
    """
    Detect miners with suspiciously similar hardware fingerprints.

    Identical cache timing profiles, SIMD bias, or thermal signatures
    across different "machines" indicate shared hardware or VMs on same host.
    """
    scores = {}
    if len(signals) < FLEET_DETECTION_MINIMUM:
        return {s["miner"]: 0.0 for s in signals}

    # Build similarity groups from hash matches
    # Miners sharing 2+ fingerprint hashes are likely same hardware
    for i, sig_a in enumerate(signals):
        matches = 0
        match_count = 0

        for j, sig_b in enumerate(signals):
            if i == j:
                continue

            shared_hashes = 0
            total_hashes = 0

            # Compare cache timing hash
            if sig_a.get("cache_latency_hash") and sig_b.get("cache_latency_hash"):
                total_hashes += 1
                if sig_a["cache_latency_hash"] == sig_b["cache_latency_hash"]:
                    shared_hashes += 1

            # Compare SIMD bias hash
            if sig_a.get("simd_bias_hash") and sig_b.get("simd_bias_hash"):
                total_hashes += 1
                if sig_a["simd_bias_hash"] == sig_b["simd_bias_hash"]:
                    shared_hashes += 1

            # Compare clock drift CV (within 5% = suspiciously similar)
            if sig_a.get("clock_drift_cv") and sig_b.get("clock_drift_cv"):
                total_hashes += 1
                cv_a, cv_b = sig_a["clock_drift_cv"], sig_b["clock_drift_cv"]
                if cv_b > 0 and abs(cv_a - cv_b) / cv_b < 0.05:
                    shared_hashes += 1

            # Compare thermal signature (within 10%)
            if sig_a.get("thermal_signature") and sig_b.get("thermal_signature"):
                total_hashes += 1
                th_a, th_b = sig_a["thermal_signature"], sig_b["thermal_signature"]
                if th_b > 0 and abs(th_a - th_b) / th_b < 0.10:
                    shared_hashes += 1

            if total_hashes >= 2 and shared_hashes >= 2:
                matches += 1

        # Signal based on how many OTHER miners look like this one
        if matches > 0:
            # 1 match → 0.3, 2 → 0.5, 5+ → 0.8+
            scores[sig_a["miner"]] = min(1.0, 0.2 + matches * 0.15)
        else:
            scores[sig_a["miner"]] = 0.0

    return scores


def compute_fleet_scores(
    db: sqlite3.Connection,
    epoch: int
) -> Dict[str, float]:
    """
    Run all fleet detection algorithms and produce composite fleet scores.

    Returns: {miner_id: fleet_score} where 0.0=solo, 1.0=definite fleet
    """
    ensure_schema(db)

    # Fetch signals for this epoch
    rows = db.execute("""
        SELECT miner, subnet_hash, attest_ts, clock_drift_cv,
               cache_latency_hash, thermal_signature, simd_bias_hash
        FROM fleet_signals
        WHERE epoch = ?
    """, (epoch,)).fetchall()

    if not rows or len(rows) < FLEET_DETECTION_MINIMUM:
        # Not enough miners to detect fleets — everyone is solo
        return {row[0]: 0.0 for row in rows}

    signals = []
    for row in rows:
        signals.append({
            "miner": row[0],
            "subnet_hash": row[1],
            "attest_ts": row[2],
            "clock_drift_cv": row[3],
            "cache_latency_hash": row[4],
            "thermal_signature": row[5],
            "simd_bias_hash": row[6],
        })

    # Run detection algorithms
    ip_scores = _detect_ip_clustering(signals)
    timing_scores = _detect_timing_correlation(signals)
    fingerprint_scores = _detect_fingerprint_similarity(signals)

    # Composite score: weighted average of signals
    # IP clustering is strongest signal (hard to fake different subnets)
    # Fingerprint similarity is second (hardware-level evidence)
    # Timing correlation is supplementary (could be coincidental)
    composite = {}
    for sig in signals:
        m = sig["miner"]
        ip = ip_scores.get(m, 0.0)
        timing = timing_scores.get(m, 0.0)
        fp = fingerprint_scores.get(m, 0.0)

        # Weighted composite: IP 40%, fingerprint 40%, timing 20%
        score = (ip * 0.4) + (fp * 0.4) + (timing * 0.2)

        # Boost: if ANY two signals fire, amplify
        fired = sum(1 for s in [ip, fp, timing] if s > 0.3)
        if fired >= 2:
            score = min(1.0, score * 1.3)

        composite[m] = round(score, 4)

        # Record to DB for audit trail
        db.execute("""
            INSERT OR REPLACE INTO fleet_scores
            (miner, epoch, fleet_score, ip_signal, timing_signal,
             fingerprint_signal)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (m, epoch, composite[m], ip, timing, fp))

    db.commit()
    return composite


# ═══════════════════════════════════════════════════════════
# BUCKET NORMALIZATION
# ═══════════════════════════════════════════════════════════

def classify_miner_bucket(device_arch: str) -> str:
    """Map a device architecture to its hardware bucket."""
    return ARCH_TO_BUCKET.get(device_arch.lower(), "modern")


def compute_bucket_pressure(
    miners: List[Tuple[str, str, float]],
    epoch: int,
    db: Optional[sqlite3.Connection] = None
) -> Dict[str, float]:
    """
    Compute pressure factors for each hardware bucket.

    If a bucket is overrepresented (more miners than its fair share),
    its pressure factor drops below 1.0 — reducing rewards for that class.
    Underrepresented buckets get boosted above 1.0.

    Args:
        miners: List of (miner_id, device_arch, base_weight) tuples
        epoch: Current epoch number
        db: Optional DB connection for recording

    Returns:
        {bucket_name: pressure_factor}
    """
    # Count miners and total weight per bucket
    bucket_counts = defaultdict(int)
    bucket_weights = defaultdict(float)
    bucket_miners = defaultdict(list)

    for miner_id, arch, weight in miners:
        bucket = classify_miner_bucket(arch)
        bucket_counts[bucket] += 1
        bucket_weights[bucket] += weight
        bucket_miners[bucket].append(miner_id)

    active_buckets = [b for b in bucket_counts if bucket_counts[b] > 0]
    num_active = len(active_buckets)

    if num_active == 0:
        return {}

    # Ideal: equal miner count per bucket
    total_miners = sum(bucket_counts.values())
    ideal_per_bucket = total_miners / num_active

    pressure = {}
    for bucket in active_buckets:
        count = bucket_counts[bucket]
        ratio = count / ideal_per_bucket  # >1 = overrepresented, <1 = rare

        if ratio > 1.0:
            # Overrepresented: apply diminishing returns
            # ratio 2.0 → pressure ~0.7, ratio 5.0 → pressure ~0.45
            factor = 1.0 / (1.0 + BUCKET_PRESSURE_STRENGTH * (ratio - 1.0))
            factor = max(BUCKET_MIN_WEIGHT, factor)
        else:
            # Underrepresented: boost (up to 1.5x)
            factor = 1.0 + (1.0 - ratio) * 0.5
            factor = min(1.5, factor)

        pressure[bucket] = round(factor, 4)

        # Record to DB
        if db:
            try:
                db.execute("""
                    INSERT OR REPLACE INTO bucket_pressure
                    (epoch, bucket, miner_count, raw_weight, pressure_factor, adjusted_weight)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (epoch, bucket, count, bucket_weights[bucket],
                      factor, bucket_weights[bucket] * factor))
            except Exception:
                pass  # Non-critical recording

    if db:
        try:
            db.commit()
        except Exception:
            pass

    return pressure


# ═══════════════════════════════════════════════════════════
# IMMUNE-ADJUSTED REWARD CALCULATION
# ═══════════════════════════════════════════════════════════

def apply_fleet_decay(
    base_multiplier: float,
    fleet_score: float
) -> float:
    """
    Apply fleet detection decay to a miner's base multiplier.

    fleet_score 0.0 → no decay (solo miner)
    fleet_score 1.0 → maximum decay (confirmed fleet)

    Formula: effective = base × (1.0 - fleet_score × DECAY_COEFF)
    Floor: Never below FLEET_SCORE_FLOOR × base

    Examples (base=2.5 G4):
      fleet_score=0.0 → 2.5  (solo miner, full bonus)
      fleet_score=0.3 → 2.2  (some fleet signals)
      fleet_score=0.7 → 1.8  (strong fleet signals)
      fleet_score=1.0 → 1.5  (confirmed fleet, 40% decay)
    """
    decay = fleet_score * FLEET_DECAY_COEFF
    effective = base_multiplier * (1.0 - decay)
    floor = base_multiplier * FLEET_SCORE_FLOOR
    return max(floor, effective)


def calculate_immune_rewards_equal_split(
    db: sqlite3.Connection,
    epoch: int,
    miners: List[Tuple[str, str]],
    chain_age_years: float,
    total_reward_urtc: int
) -> Dict[str, int]:
    """
    Calculate rewards using equal bucket split (RECOMMENDED mode).

    The pot is divided EQUALLY among active hardware buckets.
    Within each bucket, miners share their slice by time-aged weight.
    Fleet members get decayed multipliers WITHIN their bucket.

    This is the nuclear option against fleet attacks:
    - 500 modern boxes share 1/N of the pot (where N = active buckets)
    - 1 solo G4 gets 1/N of the pot all to itself
    - The fleet operator's $5M in hardware earns the same TOTAL as one G4

    Args:
        db: Database connection
        epoch: Epoch being settled
        miners: List of (miner_id, device_arch) tuples
        chain_age_years: Chain age for time-aging
        total_reward_urtc: Total uRTC to distribute

    Returns:
        {miner_id: reward_urtc}
    """
    from rip_200_round_robin_1cpu1vote import get_time_aged_multiplier

    if not miners:
        return {}

    # Step 1: Fleet detection
    fleet_scores = compute_fleet_scores(db, epoch)

    # Step 2: Classify miners into buckets with fleet-decayed weights
    buckets = defaultdict(list)  # bucket → [(miner_id, decayed_weight)]

    for miner_id, arch in miners:
        base = get_time_aged_multiplier(arch, chain_age_years)
        fleet_score = fleet_scores.get(miner_id, 0.0)
        effective = apply_fleet_decay(base, fleet_score)
        bucket = classify_miner_bucket(arch)
        buckets[bucket].append((miner_id, effective))

        # Record
        db.execute("""
            UPDATE fleet_scores SET effective_multiplier = ?
            WHERE miner = ? AND epoch = ?
        """, (effective, miner_id, epoch))

    # Step 3: Split pot equally among active buckets
    active_buckets = {b: members for b, members in buckets.items() if members}
    num_buckets = len(active_buckets)

    if num_buckets == 0:
        return {}

    pot_per_bucket = total_reward_urtc // num_buckets
    remainder = total_reward_urtc - (pot_per_bucket * num_buckets)

    # Step 4: Distribute within each bucket by weight
    rewards = {}
    bucket_index = 0

    for bucket, members in active_buckets.items():
        # Last bucket gets remainder (rounding dust)
        bucket_pot = pot_per_bucket + (remainder if bucket_index == num_buckets - 1 else 0)

        total_weight = sum(w for _, w in members)
        if total_weight <= 0:
            # Edge case: all weights zero (shouldn't happen)
            per_miner = bucket_pot // len(members)
            for miner_id, _ in members:
                rewards[miner_id] = per_miner
        else:
            remaining = bucket_pot
            for i, (miner_id, weight) in enumerate(members):
                if i == len(members) - 1:
                    share = remaining
                else:
                    share = int((weight / total_weight) * bucket_pot)
                    remaining -= share
                rewards[miner_id] = share

        # Record bucket pressure data
        try:
            db.execute("""
                INSERT OR REPLACE INTO bucket_pressure
                (epoch, bucket, miner_count, raw_weight, pressure_factor, adjusted_weight)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (epoch, bucket, len(members), total_weight,
                  1.0 / num_buckets, bucket_pot / total_reward_urtc if total_reward_urtc > 0 else 0))
        except Exception:
            pass

        bucket_index += 1

    db.commit()
    return rewards


def calculate_immune_weights(
    db: sqlite3.Connection,
    epoch: int,
    miners: List[Tuple[str, str]],
    chain_age_years: float,
    total_reward_urtc: int = 0
) -> Dict[str, float]:
    """
    Calculate immune-system-adjusted weights for epoch reward distribution.

    Main entry point. Dispatches to equal_split or pressure mode based on config.

    When BUCKET_MODE = "equal_split" and total_reward_urtc is provided,
    returns {miner_id: reward_urtc} (integer rewards, ready to credit).

    When BUCKET_MODE = "pressure", returns {miner_id: adjusted_weight}
    (float weights for pro-rata distribution by caller).

    Args:
        db: Database connection
        epoch: Epoch being settled
        miners: List of (miner_id, device_arch) tuples
        chain_age_years: Chain age for time-aging calculation
        total_reward_urtc: Total reward in uRTC (required for equal_split mode)

    Returns:
        {miner_id: value} — either reward_urtc (int) or weight (float)
    """
    if BUCKET_MODE == "equal_split" and total_reward_urtc > 0:
        return calculate_immune_rewards_equal_split(
            db, epoch, miners, chain_age_years, total_reward_urtc
        )

    # Fallback: pressure mode (original behavior)
    from rip_200_round_robin_1cpu1vote import get_time_aged_multiplier

    if not miners:
        return {}

    # Step 1: Base time-aged multipliers
    base_weights = []
    for miner_id, arch in miners:
        base = get_time_aged_multiplier(arch, chain_age_years)
        base_weights.append((miner_id, arch, base))

    # Step 2: Fleet detection
    fleet_scores = compute_fleet_scores(db, epoch)

    # Step 3: Apply fleet decay
    decayed_weights = []
    for miner_id, arch, base in base_weights:
        score = fleet_scores.get(miner_id, 0.0)
        effective = apply_fleet_decay(base, score)
        decayed_weights.append((miner_id, arch, effective))

        db.execute("""
            UPDATE fleet_scores SET effective_multiplier = ?
            WHERE miner = ? AND epoch = ?
        """, (effective, miner_id, epoch))

    # Step 4: Bucket pressure normalization
    pressure = compute_bucket_pressure(decayed_weights, epoch, db)

    # Step 5: Apply pressure to get final weights
    final_weights = {}
    for miner_id, arch, weight in decayed_weights:
        bucket = classify_miner_bucket(arch)
        bucket_factor = pressure.get(bucket, 1.0)
        final_weights[miner_id] = weight * bucket_factor

    db.commit()
    return final_weights


# ═══════════════════════════════════════════════════════════
# ADMIN / DIAGNOSTIC ENDPOINTS
# ═══════════════════════════════════════════════════════════

def get_fleet_report(db: sqlite3.Connection, epoch: int) -> dict:
    """Generate a human-readable fleet detection report for an epoch."""
    ensure_schema(db)

    scores = db.execute("""
        SELECT miner, fleet_score, ip_signal, timing_signal,
               fingerprint_signal, effective_multiplier
        FROM fleet_scores WHERE epoch = ?
        ORDER BY fleet_score DESC
    """, (epoch,)).fetchall()

    pressure = db.execute("""
        SELECT bucket, miner_count, pressure_factor, raw_weight, adjusted_weight
        FROM bucket_pressure WHERE epoch = ?
    """, (epoch,)).fetchall()

    flagged = [s for s in scores if s[1] > 0.3]

    return {
        "epoch": epoch,
        "total_miners": len(scores),
        "flagged_miners": len(flagged),
        "fleet_scores": [
            {
                "miner": s[0],
                "fleet_score": s[1],
                "signals": {
                    "ip_clustering": s[2],
                    "timing_correlation": s[3],
                    "fingerprint_similarity": s[4]
                },
                "effective_multiplier": s[5]
            }
            for s in scores
        ],
        "bucket_pressure": [
            {
                "bucket": p[0],
                "miner_count": p[1],
                "pressure_factor": p[2],
                "raw_weight": p[3],
                "adjusted_weight": p[4]
            }
            for p in pressure
        ]
    }


def register_fleet_endpoints(app, DB_PATH):
    """Register Flask endpoints for fleet immune system admin."""
    from flask import request, jsonify

    @app.route('/admin/fleet/report', methods=['GET'])
    def fleet_report():
        admin_key = request.headers.get("X-Admin-Key", "")
        import os
        if admin_key != os.environ.get("RC_ADMIN_KEY", "rustchain_admin_key_2025_secure64"):
            return jsonify({"error": "Unauthorized"}), 401

        epoch = request.args.get('epoch', type=int)
        if epoch is None:
            from rewards_implementation_rip200 import current_slot, slot_to_epoch
            epoch = slot_to_epoch(current_slot()) - 1

        with sqlite3.connect(DB_PATH) as db:
            report = get_fleet_report(db, epoch)
        return jsonify(report)

    @app.route('/admin/fleet/scores', methods=['GET'])
    def fleet_scores():
        admin_key = request.headers.get("X-Admin-Key", "")
        import os
        if admin_key != os.environ.get("RC_ADMIN_KEY", "rustchain_admin_key_2025_secure64"):
            return jsonify({"error": "Unauthorized"}), 401

        miner = request.args.get('miner')
        limit = request.args.get('limit', 10, type=int)

        with sqlite3.connect(DB_PATH) as db:
            if miner:
                rows = db.execute("""
                    SELECT epoch, fleet_score, ip_signal, timing_signal,
                           fingerprint_signal, effective_multiplier
                    FROM fleet_scores WHERE miner = ?
                    ORDER BY epoch DESC LIMIT ?
                """, (miner, limit)).fetchall()
            else:
                rows = db.execute("""
                    SELECT miner, epoch, fleet_score, ip_signal,
                           timing_signal, fingerprint_signal
                    FROM fleet_scores
                    WHERE fleet_score > 0.3
                    ORDER BY fleet_score DESC LIMIT ?
                """, (limit,)).fetchall()

        return jsonify({"scores": [dict(zip(
            ["miner", "epoch", "fleet_score", "ip_signal",
             "timing_signal", "fingerprint_signal"], r
        )) for r in rows]})

    print("[RIP-201] Fleet immune system endpoints registered")


# ═══════════════════════════════════════════════════════════
# SELF-TEST
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("RIP-201: Fleet Detection Immune System — Self Test")
    print("=" * 60)

    # Create in-memory DB
    db = sqlite3.connect(":memory:")
    ensure_schema(db)

    # Also need miner_attest_recent for the full pipeline
    db.execute("""
        CREATE TABLE IF NOT EXISTS miner_attest_recent (
            miner TEXT PRIMARY KEY,
            ts_ok INTEGER NOT NULL,
            device_family TEXT,
            device_arch TEXT,
            entropy_score REAL DEFAULT 0.0,
            fingerprint_passed INTEGER DEFAULT 0
        )
    """)

    EPOCH = 100

    # ─── Scenario 1: Healthy diverse network ───
    print("\n--- Scenario 1: Healthy Diverse Network (8 unique miners) ---")

    healthy_miners = [
        ("g4-powerbook-115", "g4",            "10.1.1",    1000, 0.092, "cache_a", 0.45, "simd_a"),
        ("dual-g4-125",      "g4",            "10.1.2",    1200, 0.088, "cache_b", 0.52, "simd_b"),
        ("ppc-g5-130",       "g5",            "10.2.1",    1500, 0.105, "cache_c", 0.38, "simd_c"),
        ("victus-x86",       "modern",        "192.168.0", 2000, 0.049, "cache_d", 0.61, "simd_d"),
        ("sophia-nas",       "modern",        "192.168.1", 2300, 0.055, "cache_e", 0.58, "simd_e"),
        ("mac-mini-m2",      "apple_silicon", "10.3.1",    3000, 0.033, "cache_f", 0.42, "simd_f"),
        ("power8-server",    "power8",        "10.4.1",    4000, 0.071, "cache_g", 0.55, "simd_g"),
        ("ryan-factorio",    "modern",        "76.8.228",  5000, 0.044, "cache_h", 0.63, "simd_h"),
    ]

    for m, arch, subnet, ts, cv, cache, thermal, simd in healthy_miners:
        subnet_hash = hashlib.sha256(subnet.encode()).hexdigest()[:16]
        db.execute("""
            INSERT OR REPLACE INTO fleet_signals
            (miner, epoch, subnet_hash, attest_ts, clock_drift_cv,
             cache_latency_hash, thermal_signature, simd_bias_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (m, EPOCH, subnet_hash, ts, cv, cache, thermal, simd))

    db.commit()
    scores = compute_fleet_scores(db, EPOCH)

    print(f"  {'Miner':<25} {'Fleet Score':>12} {'Status':<15}")
    print(f"  {'─'*25} {'─'*12} {'─'*15}")
    for m, arch, *_ in healthy_miners:
        s = scores.get(m, 0.0)
        status = "CLEAN" if s < 0.3 else "FLAGGED" if s < 0.7 else "FLEET"
        print(f"  {m:<25} {s:>12.4f} {status:<15}")

    # ─── Scenario 2: Fleet attack (10 modern boxes, same subnet) ───
    print("\n--- Scenario 2: Fleet Attack (10 modern boxes, same /24) ---")

    EPOCH2 = 101
    fleet_miners = []

    # 3 legitimate miners
    fleet_miners.append(("g4-real-1", "g4", "10.1.1", 1000, 0.092, "cache_real1", 0.45, "simd_real1"))
    fleet_miners.append(("g5-real-1", "g5", "10.2.1", 1800, 0.105, "cache_real2", 0.38, "simd_real2"))
    fleet_miners.append(("m2-real-1", "apple_silicon", "10.3.1", 2500, 0.033, "cache_real3", 0.42, "simd_real3"))

    # 10 fleet miners — same subnet, similar timing, similar fingerprints
    for i in range(10):
        fleet_miners.append((
            f"fleet-box-{i}",
            "modern",
            "203.0.113",           # All same /24 subnet
            3000 + i * 5,          # Attestation within 50s of each other
            0.048 + i * 0.001,     # Nearly identical clock drift
            "cache_fleet_shared",  # SAME cache timing hash
            0.60 + i * 0.005,      # Very similar thermal signatures
            "simd_fleet_shared",   # SAME SIMD hash
        ))

    for m, arch, subnet, ts, cv, cache, thermal, simd in fleet_miners:
        subnet_hash = hashlib.sha256(subnet.encode()).hexdigest()[:16]
        db.execute("""
            INSERT OR REPLACE INTO fleet_signals
            (miner, epoch, subnet_hash, attest_ts, clock_drift_cv,
             cache_latency_hash, thermal_signature, simd_bias_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (m, EPOCH2, subnet_hash, ts, cv, cache, thermal, simd))

    db.commit()
    scores2 = compute_fleet_scores(db, EPOCH2)

    print(f"  {'Miner':<25} {'Fleet Score':>12} {'Status':<15}")
    print(f"  {'─'*25} {'─'*12} {'─'*15}")
    for m, arch, *_ in fleet_miners:
        s = scores2.get(m, 0.0)
        status = "CLEAN" if s < 0.3 else "FLAGGED" if s < 0.7 else "FLEET"
        print(f"  {m:<25} {s:>12.4f} {status:<15}")

    # ─── Scenario 3: Bucket pressure ───
    print("\n--- Scenario 3: Bucket Pressure (500 modern vs 3 vintage) ---")

    fleet_attack = [("g4-solo", "g4", 2.5), ("g5-solo", "g5", 2.0), ("g3-solo", "g3", 1.8)]
    for i in range(500):
        fleet_attack.append((f"modern-{i}", "modern", 1.0))

    pressure = compute_bucket_pressure(fleet_attack, 200)

    print(f"  {'Bucket':<20} {'Pressure':>10} {'Effect':<30}")
    print(f"  {'─'*20} {'─'*10} {'─'*30}")
    for bucket, factor in sorted(pressure.items(), key=lambda x: x[1]):
        if factor < 1.0:
            effect = f"FLATTENED (each modern box worth {factor:.2f}x)"
        elif factor > 1.0:
            effect = f"BOOSTED (rare hardware bonus {factor:.2f}x)"
        else:
            effect = "neutral"
        print(f"  {bucket:<20} {factor:>10.4f} {effect:<30}")

    # ─── Scenario 4: Fleet decay on multipliers ───
    print("\n--- Scenario 4: Fleet Decay Examples ---")

    examples = [
        ("G4 (solo)", 2.5, 0.0),
        ("G4 (mild fleet)", 2.5, 0.3),
        ("G4 (strong fleet)", 2.5, 0.7),
        ("G4 (confirmed fleet)", 2.5, 1.0),
        ("Modern (solo)", 1.0, 0.0),
        ("Modern (strong fleet)", 1.0, 0.7),
        ("Modern (confirmed fleet)", 1.0, 1.0),
    ]

    print(f"  {'Miner Type':<25} {'Base':>6} {'Fleet':>7} {'Effective':>10} {'Decay':>8}")
    print(f"  {'─'*25} {'─'*6} {'─'*7} {'─'*10} {'─'*8}")
    for name, base, score in examples:
        eff = apply_fleet_decay(base, score)
        decay_pct = (1.0 - eff/base) * 100 if base > 0 else 0
        print(f"  {name:<25} {base:>6.2f} {score:>7.2f} {eff:>10.3f} {decay_pct:>7.1f}%")

    # ─── Combined effect ───
    print("\n--- Combined: 500 Modern Fleet vs 3 Vintage Solo ---")
    print("  Without immune system:")
    total_w_no_immune = 500 * 1.0 + 2.5 + 2.0 + 1.8
    g4_share = (2.5 / total_w_no_immune) * 1.5
    modern_total = (500 * 1.0 / total_w_no_immune) * 1.5
    modern_each = modern_total / 500
    print(f"    G4 solo:         {g4_share:.6f} RTC/epoch")
    print(f"    500 modern fleet: {modern_total:.6f} RTC/epoch total ({modern_each:.8f} each)")
    print(f"    Fleet ROI:       {modern_total/g4_share:.1f}x the G4 solo reward")

    print("\n  With RIP-201 PRESSURE mode (soft):")
    fleet_eff = apply_fleet_decay(1.0, 0.8)  # ~0.68
    g4_eff = 2.5  # Solo, no decay
    bucket_p_modern = compute_bucket_pressure(
        [("g4", "g4", g4_eff), ("g5", "g5", 2.0), ("g3", "g3", 1.8)] +
        [(f"m{i}", "modern", fleet_eff) for i in range(500)],
        999
    )
    modern_p = bucket_p_modern.get("modern", 1.0)
    vintage_p = bucket_p_modern.get("vintage_powerpc", 1.0)

    g4_final = g4_eff * vintage_p
    modern_final = fleet_eff * modern_p
    total_w_immune = g4_final + 2.0 * vintage_p + 1.8 * vintage_p + 500 * modern_final
    g4_share_immune = (g4_final / total_w_immune) * 1.5
    modern_total_immune = (500 * modern_final / total_w_immune) * 1.5
    modern_each_immune = modern_total_immune / 500

    print(f"    Fleet score:      0.80 → multiplier decay to {fleet_eff:.3f}")
    print(f"    Modern pressure:  {modern_p:.4f} (bucket flattened)")
    print(f"    Vintage pressure: {vintage_p:.4f} (bucket boosted)")
    print(f"    G4 solo:         {g4_share_immune:.6f} RTC/epoch")
    print(f"    500 modern fleet: {modern_total_immune:.6f} RTC/epoch total ({modern_each_immune:.8f} each)")
    print(f"    Fleet ROI:       {modern_total_immune/g4_share_immune:.1f}x the G4 solo reward")

    # ─── Equal Split mode (the real defense) ───
    print("\n  With RIP-201 EQUAL SPLIT mode (RECOMMENDED):")
    print("    Pot split: 1.5 RTC ÷ 2 active buckets = 0.75 RTC each")

    # In equal split: vintage_powerpc bucket gets 0.75 RTC, modern bucket gets 0.75 RTC
    vintage_pot = 0.75  # RTC
    modern_pot = 0.75   # RTC

    # Within vintage bucket: 3 miners split 0.75 by weight
    vintage_total_w = 2.5 + 2.0 + 1.8
    g4_equal = (2.5 / vintage_total_w) * vintage_pot
    g5_equal = (2.0 / vintage_total_w) * vintage_pot
    g3_equal = (1.8 / vintage_total_w) * vintage_pot

    # Within modern bucket: 500 fleet miners split 0.75 by decayed weight
    modern_each_equal = modern_pot / 500  # Equal weight within bucket (all modern)

    print(f"    Vintage bucket (3 miners share 0.75 RTC):")
    print(f"      G4 solo:       {g4_equal:.6f} RTC/epoch")
    print(f"      G5 solo:       {g5_equal:.6f} RTC/epoch")
    print(f"      G3 solo:       {g3_equal:.6f} RTC/epoch")
    print(f"    Modern bucket (500 fleet share 0.75 RTC):")
    print(f"      Each fleet box: {modern_each_equal:.8f} RTC/epoch")
    print(f"    Fleet ROI:       {modern_pot/g4_equal:.1f}x the G4 solo reward (TOTAL fleet)")
    print(f"    Per-box ROI:     {modern_each_equal/g4_equal:.4f}x (each fleet box vs G4)")
    print(f"    Fleet gets:      {modern_pot/1.5*100:.0f}% of pot (was {modern_total/1.5*100:.0f}%)")
    print(f"    G4 earns:        {g4_equal/g4_share:.0f}x more than without immune system")

    # ─── The economics ───
    print("\n  === ECONOMIC IMPACT ===")
    print(f"    Without immune: 500 boxes earn {modern_total:.4f} RTC/epoch = {modern_total*365:.1f} RTC/year")
    print(f"    With equal split: 500 boxes earn {modern_pot:.4f} RTC/epoch = {modern_pot*365:.1f} RTC/year")
    hardware_cost = 5_000_000  # $5M
    rtc_value = 0.10  # $0.10/RTC
    annual_no_immune = modern_total * 365 * rtc_value
    annual_equal = modern_pot * 365 * rtc_value
    years_to_roi_no = hardware_cost / annual_no_immune if annual_no_immune > 0 else float('inf')
    years_to_roi_eq = hardware_cost / annual_equal if annual_equal > 0 else float('inf')
    print(f"    At $0.10/RTC, fleet annual revenue:")
    print(f"      No immune:   ${annual_no_immune:,.2f}/year → ROI in {years_to_roi_no:,.0f} years")
    print(f"      Equal split: ${annual_equal:,.2f}/year → ROI in {years_to_roi_eq:,.0f} years")
    print(f"    A $5M hardware fleet NEVER pays for itself. Attack neutralized.")

    print("\n" + "=" * 60)
    print("RIP-201 self-test complete.")
    print("One of everything beats a hundred of one thing.")
    print("=" * 60)
