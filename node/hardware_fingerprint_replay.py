#!/usr/bin/env python3
"""
Hardware Fingerprint Replay Attack Defense - Issue #2276
=========================================================
Detects and prevents replay attacks where attackers capture valid hardware
fingerprints and reuse them to impersonate legitimate miners.

Replay Attack Vectors Defended:
1. Fingerprint Replay: Capturing and resubmitting valid fingerprint data
2. Timing Replay: Reusing clock drift/cache timing measurements
3. Entropy Replay: Copying entropy profiles from legitimate miners
4. Cross-Miner Replay: Using one miner's fingerprint on another wallet

Defense Mechanisms:
- Nonce-based fingerprint binding (each fingerprint tied to attestation nonce)
- Temporal validation (fingerprints expire after short window)
- Entropy profile hashing with collision detection
- Rate limiting on fingerprint submissions per hardware ID
- Historical fingerprint tracking for anomaly detection
"""

import hashlib
import json
import os
import sqlite3
import time
from contextlib import closing
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict

# Configuration constants
REPLAY_WINDOW_SECONDS = 300  # 5 minutes - fingerprints expire after this
MAX_FINGERPRINT_SUBMISSIONS_PER_HOUR = 10  # Rate limit per hardware ID
ENTROPY_HASH_COLLISION_TOLERANCE = 0.95  # Similarity threshold for collision detection


def get_db_path() -> str:
    """Get database path from environment (evaluated at call time, not import time)."""
    return os.environ.get('RUSTCHAIN_DB_PATH') or os.environ.get('DB_PATH') or '/root/rustchain/rustchain_v2.db'

# Core entropy fields for fingerprint hashing
CORE_ENTROPY_FIELDS = [
    'clock_cv', 'clock_drift_hash', 
    'cache_hash', 'cache_l1', 'cache_l2', 
    'thermal_ratio', 'jitter_cv', 'jitter_map_hash',
    'simd_profile_hash'
]


def init_replay_defense_schema():
    """Initialize database tables for replay attack defense."""
    with closing(sqlite3.connect(get_db_path())) as conn:
        # Table 1: Track submitted fingerprint hashes with timestamps
        conn.execute('''
            CREATE TABLE IF NOT EXISTS fingerprint_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint_hash TEXT NOT NULL,
                miner_id TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                hardware_id TEXT,
                nonce TEXT NOT NULL,
                submitted_at INTEGER NOT NULL,
                entropy_profile_hash TEXT,
                checks_hash TEXT,
                attestation_valid INTEGER DEFAULT 0,
                UNIQUE(fingerprint_hash, nonce)
            )
        ''')
        
        # Table 2: Track entropy profile collisions
        conn.execute('''
            CREATE TABLE IF NOT EXISTS entropy_collisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entropy_profile_hash TEXT NOT NULL,
                wallet_a TEXT NOT NULL,
                wallet_b TEXT NOT NULL,
                detected_at INTEGER NOT NULL,
                collision_type TEXT,
                resolved INTEGER DEFAULT 0
            )
        ''')
        
        # Table 3: Rate limiting for fingerprint submissions
        conn.execute('''
            CREATE TABLE IF NOT EXISTS fingerprint_rate_limits (
                hardware_id TEXT PRIMARY KEY,
                submission_count INTEGER DEFAULT 0,
                window_start INTEGER NOT NULL,
                last_submission INTEGER
            )
        ''')
        
        # Table 4: Historical fingerprint sequences for temporal analysis
        conn.execute('''
            CREATE TABLE IF NOT EXISTS fingerprint_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                fingerprint_hash TEXT NOT NULL,
                sequence_num INTEGER DEFAULT 0,
                recorded_at INTEGER NOT NULL
            )
        ''')
        
        # Table 5: Snapshot history per miner for temporal consistency analysis (Issue #19)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS miner_fingerprint_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                clock_cv REAL,
                cache_l2_l1 REAL,
                thermal_ratio REAL,
                jitter_fp_int REAL,
                recorded_at INTEGER NOT NULL
            )
        ''')
        
        # Create indexes for performance
        conn.execute('CREATE INDEX IF NOT EXISTS idx_fp_submissions_hash ON fingerprint_submissions(fingerprint_hash)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_fp_submissions_nonce ON fingerprint_submissions(nonce)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_fp_submissions_miner ON fingerprint_submissions(miner_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_fp_submissions_wallet ON fingerprint_submissions(wallet_address)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_entropy_collisions_hash ON entropy_collisions(entropy_profile_hash)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_fp_history_miner ON fingerprint_history(miner_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_mfp_history_miner ON miner_fingerprint_history(miner_id)')
        
        conn.commit()
    
    print("[REPLAY_DEFENSE] Initialized replay attack defense schema")


def compute_fingerprint_hash(fingerprint: Dict) -> str:
    """
    Compute a cryptographic hash of the fingerprint data.
    This creates a unique identifier for the fingerprint payload.

    Args:
        fingerprint: The fingerprint dictionary containing checks and data

    Returns:
        SHA-256 hash (hex) of the normalized fingerprint
    """
    if fingerprint is None:
        return ""
    
    if not isinstance(fingerprint, dict):
        return ""

    # Normalize the fingerprint for consistent hashing
    checks = fingerprint.get('checks', {})
    normalized = {
        'checks': {},
        'timestamp': fingerprint.get('timestamp', 0),
        'bridge_type': fingerprint.get('bridge_type', '')
    }
    
    # Extract and normalize each check
    for check_name, check_data in checks.items():
        if isinstance(check_data, dict):
            normalized['checks'][check_name] = {
                'passed': check_data.get('passed', False),
                'data': _normalize_check_data(check_data.get('data', {}))
            }
        elif isinstance(check_data, bool):
            normalized['checks'][check_name] = {'passed': check_data}
    
    # Serialize and hash
    serialized = json.dumps(normalized, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(serialized.encode()).hexdigest()


def _normalize_check_data(data: Dict) -> Dict:
    """Normalize check data for consistent hashing, removing volatile fields."""
    if not isinstance(data, dict):
        return {}
    
    normalized = {}
    for key, value in data.items():
        # Skip highly volatile fields that change between submissions
        if key in ('samples', 'timestamp', 'elapsed_ns', 'mean_ns'):
            continue
        # Include stable entropy fields
        if isinstance(value, (int, float, str, bool)):
            normalized[key] = value
        elif isinstance(value, list) and len(value) < 100:
            normalized[key] = value
    
    return normalized


def compute_entropy_profile_hash(fingerprint: Dict) -> str:
    """
    Compute hash of the entropy profile extracted from fingerprint.
    This is used for collision detection across different wallets.
    
    Args:
        fingerprint: The fingerprint dictionary
        
    Returns:
        SHA-256 hash (hex) of the entropy profile
    """
    checks = fingerprint.get('checks', {}) if isinstance(fingerprint, dict) else {}
    
    entropy_values = {}

    # The producer (node/fingerprint_checks.py) emits load-normalized *ratios*
    # and coefficients of variation as the stable per-machine characteristics;
    # the raw *_ns latencies vary run-to-run and are intentionally excluded so
    # the same box yields a stable profile across attestations.

    # Extract clock drift entropy
    clock_data = checks.get('clock_drift', {}).get('data', {})
    if isinstance(clock_data, dict):
        entropy_values['clock_cv'] = clock_data.get('cv', 0)

    # Extract cache timing entropy (hierarchy ratios are the stable signal)
    cache_data = checks.get('cache_timing', {}).get('data', {})
    if isinstance(cache_data, dict):
        entropy_values['cache_l2_l1_ratio'] = cache_data.get('l2_l1_ratio', 0)
        entropy_values['cache_l3_l2_ratio'] = cache_data.get('l3_l2_ratio', 0)

    # Extract thermal drift entropy
    thermal_data = checks.get('thermal_drift', {}).get('data', {})
    if isinstance(thermal_data, dict):
        entropy_values['thermal_ratio'] = thermal_data.get('drift_ratio', 0)

    # Extract jitter entropy as load-robust relative timings (fp/int, branch/int);
    # the producer emits only per-op *_avg_ns, so derive dimensionless ratios.
    jitter_data = checks.get('instruction_jitter', {}).get('data', {})
    if isinstance(jitter_data, dict):
        int_avg = jitter_data.get('int_avg_ns', 0) or 0
        if int_avg:
            entropy_values['jitter_fp_int_ratio'] = round(
                jitter_data.get('fp_avg_ns', 0) / int_avg, 3
            )
            entropy_values['jitter_branch_int_ratio'] = round(
                jitter_data.get('branch_avg_ns', 0) / int_avg, 3
            )
    
    # Extract SIMD profile entropy
    simd_data = checks.get('simd_identity', {}).get('data', {})
    if isinstance(simd_data, dict):
        entropy_values['simd_profile_hash'] = hashlib.sha256(
            json.dumps(simd_data, sort_keys=True).encode()
        ).hexdigest()[:16]
    
    # Hash the entropy profile
    serialized = json.dumps(entropy_values, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(serialized.encode()).hexdigest()


def check_fingerprint_replay(
    fingerprint_hash: str,
    nonce: str,
    wallet_address: str,
    miner_id: str
) -> Tuple[bool, str, Optional[Dict]]:
    """
    Check if a fingerprint submission is a replay attack.
    
    Args:
        fingerprint_hash: Hash of the fingerprint data
        nonce: Attestation nonce (should be unique per submission)
        wallet_address: The wallet submitting the attestation
        miner_id: The miner identifier
        
    Returns:
        Tuple of (is_replay: bool, reason: str, details: dict or None)
    """
    now = int(time.time())
    window_start = now - REPLAY_WINDOW_SECONDS

    with sqlite3.connect(get_db_path()) as conn:
        c = conn.cursor()
        
        # Check 1: Exact fingerprint hash replay (same fingerprint, different nonce)
        c.execute('''
            SELECT wallet_address, miner_id, submitted_at, nonce
            FROM fingerprint_submissions
            WHERE fingerprint_hash = ? AND submitted_at > ?
            ORDER BY submitted_at DESC
            LIMIT 10
        ''', (fingerprint_hash, window_start))
        
        recent_submissions = c.fetchall()
        
        if recent_submissions:
            for prev_wallet, prev_miner, prev_time, prev_nonce in recent_submissions:
                # Same fingerprint, different nonce = replay attack
                if prev_nonce != nonce:
                    return True, "fingerprint_replay_detected", {
                        'attack_type': 'exact_fingerprint_replay',
                        'previous_wallet': prev_wallet[:20] + '...' if len(prev_wallet) > 20 else prev_wallet,
                        'previous_miner': prev_miner[:20] + '...' if len(prev_miner) > 20 else prev_miner,
                        'previous_nonce': prev_nonce[:16] + '...' if len(prev_nonce) > 16 else prev_nonce,
                        'time_delta_seconds': now - prev_time,
                        'severity': 'high'
                    }
                
                # Same fingerprint, same nonce, different wallet = wallet hijacking
                if prev_nonce == nonce and prev_wallet != wallet_address:
                    return True, "nonce_collision_attack", {
                        'attack_type': 'nonce_collision',
                        'conflicting_wallet': prev_wallet[:20] + '...',
                        'severity': 'critical'
                    }
        
        # Check 2: Same nonce used twice (direct replay)
        c.execute('''
            SELECT wallet_address, miner_id, submitted_at
            FROM fingerprint_submissions
            WHERE nonce = ? AND submitted_at > ?
        ''', (nonce, window_start))
        
        nonce_usage = c.fetchone()
        if nonce_usage:
            prev_wallet, prev_miner, prev_time = nonce_usage
            if prev_wallet != wallet_address or prev_miner != miner_id:
                return True, "nonce_reuse_detected", {
                    'attack_type': 'nonce_reuse',
                    'original_wallet': prev_wallet[:20] + '...',
                    'original_miner': prev_miner[:20] + '...',
                    'time_delta_seconds': now - prev_time,
                    'severity': 'critical'
                }
        
        # Check 3: Rate limiting per hardware (if hardware_id provided)
        # This is checked separately in check_fingerprint_rate_limit
        
    return False, "no_replay_detected", None


def check_entropy_collision(
    entropy_profile_hash: str,
    wallet_address: str,
    miner_id: str
) -> Tuple[bool, str, Optional[Dict]]:
    """
    Check if the entropy profile matches another wallet's profile.
    This detects hardware sharing or entropy profile theft.
    
    Args:
        entropy_profile_hash: Hash of the entropy profile
        wallet_address: The wallet submitting
        miner_id: The miner identifier
        
    Returns:
        Tuple of (is_collision: bool, reason: str, details: dict or None)
    """
    now = int(time.time())
    window_start = now - (REPLAY_WINDOW_SECONDS * 12)  # 1 hour window

    with sqlite3.connect(get_db_path()) as conn:
        c = conn.cursor()
        
        # Find recent submissions with similar entropy profile
        c.execute('''
            SELECT DISTINCT wallet_address, miner_id, submitted_at
            FROM fingerprint_submissions
            WHERE entropy_profile_hash = ? 
            AND submitted_at > ?
            AND wallet_address != ?
            LIMIT 5
        ''', (entropy_profile_hash, window_start, wallet_address))
        
        collisions = c.fetchall()
        
        if collisions:
            collision_wallets = [
                {
                    'wallet': w[:20] + '...' if len(w) > 20 else w,
                    'miner': m[:20] + '...' if len(m) > 20 else m,
                    'time_ago': now - t
                }
                for w, m, t in collisions
            ]
            
            # Record the collision
            for coll_wallet, coll_miner, _ in collisions:
                c.execute('''
                    INSERT OR IGNORE INTO entropy_collisions
                    (entropy_profile_hash, wallet_a, wallet_b, detected_at, collision_type)
                    VALUES (?, ?, ?, ?, ?)
                ''', (entropy_profile_hash, wallet_address, coll_wallet, now, 'entropy_profile_match'))
            
            conn.commit()
            
            return True, "entropy_profile_collision", {
                'attack_type': 'entropy_sharing',
                'collision_count': len(collisions),
                'collision_wallets': collision_wallets,
                'severity': 'medium'
            }
    
    return False, "no_collision_detected", None


def check_fingerprint_rate_limit(
    hardware_id: str,
    wallet_address: str
) -> Tuple[bool, str, Optional[Dict]]:
    """
    Check if a hardware ID is submitting fingerprints too frequently.
    
    Args:
        hardware_id: Unique hardware identifier
        wallet_address: The wallet submitting
        
    Returns:
        Tuple of (is_allowed: bool, reason: str, details: dict or None)
    """
    if not hardware_id:
        return True, "no_hardware_id", None  # Can't rate limit without hardware ID

    now = int(time.time())
    window_start = now - 3600  # 1 hour window

    with sqlite3.connect(get_db_path()) as conn:
        c = conn.cursor()
        
        # Get or create rate limit record
        c.execute('''
            SELECT submission_count, window_start, last_submission
            FROM fingerprint_rate_limits
            WHERE hardware_id = ?
        ''', (hardware_id,))
        
        row = c.fetchone()
        
        if row is None:
            # First submission from this hardware
            c.execute('''
                INSERT INTO fingerprint_rate_limits
                (hardware_id, submission_count, window_start, last_submission)
                VALUES (?, 1, ?, ?)
            ''', (hardware_id, now, now))
            conn.commit()
            return True, "first_submission", None
        
        count, prev_window_start, last_submission = row
        
        # Reset counter if window expired
        if now - prev_window_start > 3600:
            c.execute('''
                UPDATE fingerprint_rate_limits
                SET submission_count = 1, window_start = ?, last_submission = ?
                WHERE hardware_id = ?
            ''', (now, now, hardware_id))
            conn.commit()
            return True, "window_reset", None
        
        # Check if limit exceeded
        if count >= MAX_FINGERPRINT_SUBMISSIONS_PER_HOUR:
            return False, "rate_limit_exceeded", {
                'limit': MAX_FINGERPRINT_SUBMISSIONS_PER_HOUR,
                'current_count': count,
                'window_start': prev_window_start,
                'retry_after_seconds': 3600 - (now - prev_window_start),
                'severity': 'low'
            }
        
        # Update counter
        c.execute('''
            UPDATE fingerprint_rate_limits
            SET submission_count = submission_count + 1, last_submission = ?
            WHERE hardware_id = ?
        ''', (now, hardware_id))
        conn.commit()
        
        return True, "within_limit", {
            'remaining': MAX_FINGERPRINT_SUBMISSIONS_PER_HOUR - count - 1,
            'window_reset_in_seconds': 3600 - (now - prev_window_start)
        }


def record_fingerprint_submission(
    fingerprint: Dict,
    nonce: str,
    wallet_address: str,
    miner_id: str,
    hardware_id: Optional[str] = None,
    attestation_valid: bool = True
) -> Dict:
    """
    Record a fingerprint submission for future replay detection.
    
    Args:
        fingerprint: The fingerprint dictionary
        nonce: Attestation nonce
        wallet_address: Wallet that submitted
        miner_id: Miner identifier
        hardware_id: Optional hardware binding ID
        attestation_valid: Whether the attestation passed validation
        
    Returns:
        Dict with submission details
    """
    now = int(time.time())
    fingerprint_hash = compute_fingerprint_hash(fingerprint)
    entropy_profile_hash = compute_entropy_profile_hash(fingerprint)
    checks_hash = hashlib.sha256(
        json.dumps(fingerprint.get('checks', {}), sort_keys=True).encode()
    ).hexdigest()

    with sqlite3.connect(get_db_path()) as conn:
        c = conn.cursor()
        
        # Insert submission record
        c.execute('''
            INSERT OR IGNORE INTO fingerprint_submissions
            (fingerprint_hash, miner_id, wallet_address, hardware_id, 
             nonce, submitted_at, entropy_profile_hash, checks_hash, attestation_valid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (fingerprint_hash, miner_id, wallet_address, hardware_id,
              nonce, now, entropy_profile_hash, checks_hash, 1 if attestation_valid else 0))
        
        # Update fingerprint history sequence
        c.execute('''
            SELECT COALESCE(MAX(sequence_num), -1) + 1
            FROM fingerprint_history
            WHERE miner_id = ? AND wallet_address = ?
        ''', (miner_id, wallet_address))
        
        next_seq = c.fetchone()[0]
        
        c.execute('''
            INSERT INTO fingerprint_history
            (miner_id, wallet_address, fingerprint_hash, sequence_num, recorded_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (miner_id, wallet_address, fingerprint_hash, next_seq, now))
        
        conn.commit()
    
    return {
        'fingerprint_hash': fingerprint_hash[:16] + '...',
        'entropy_profile_hash': entropy_profile_hash[:16] + '...',
        'sequence_number': next_seq,
        'recorded_at': now
    }


def detect_fingerprint_anomalies(
    miner_id: str,
    wallet_address: str,
    fingerprint_hash: str
) -> Tuple[bool, List[Dict]]:
    """
    Detect anomalous fingerprint patterns for a miner.
    
    Args:
        miner_id: The miner identifier
        wallet_address: The wallet address
        fingerprint_hash: Current fingerprint hash
        
    Returns:
        Tuple of (has_anomalies: bool, anomalies: list)
    """
    anomalies = []
    now = int(time.time())

    with sqlite3.connect(get_db_path()) as conn:
        c = conn.cursor()
        
        # Get recent fingerprint history for this miner
        c.execute('''
            SELECT fingerprint_hash, sequence_num, recorded_at, wallet_address
            FROM fingerprint_history
            WHERE miner_id = ?
            ORDER BY recorded_at DESC
            LIMIT 20
        ''', (miner_id,))
        
        history = c.fetchall()
        
        if len(history) < 2:
            return False, []  # Not enough history
        
        # Check 1: Fingerprint volatility (too many different fingerprints)
        unique_hashes = set(h[0] for h in history[:10])
        if len(unique_hashes) > 8:  # More than 8 different fingerprints in 10 submissions
            anomalies.append({
                'type': 'excessive_fingerprint_volatility',
                'unique_fingerprints': len(unique_hashes),
                'submissions_analyzed': 10,
                'severity': 'medium',
                'description': 'Miner submitting many different fingerprints rapidly'
            })
        
        # Check 2: Wallet hopping (same miner, different wallets)
        unique_wallets = set(h[3] for h in history[:10])
        if len(unique_wallets) > 3:  # More than 3 wallets in 10 submissions
            anomalies.append({
                'type': 'wallet_hopping',
                'unique_wallets': len(unique_wallets),
                'submissions_analyzed': 10,
                'severity': 'high',
                'description': 'Miner associated with many different wallets'
            })
        
        # Check 3: Fingerprint reuse after long gap (possible replay)
        for prev_hash, prev_seq, prev_time, prev_wallet in history[1:]:
            if prev_hash == fingerprint_hash and prev_wallet != wallet_address:
                time_gap = now - prev_time
                if time_gap > 86400:  # More than 24 hours
                    anomalies.append({
                        'type': 'delayed_fingerprint_replay',
                        'time_gap_hours': time_gap // 3600,
                        'previous_wallet': prev_wallet[:20] + '...',
                        'severity': 'high',
                        'description': 'Fingerprint reused after long gap by different wallet'
                    })
    
    return len(anomalies) > 0, anomalies


def get_replay_defense_report(
    wallet_address: Optional[str] = None,
    miner_id: Optional[str] = None,
    hours: int = 24
) -> Dict:
    """
    Generate a replay defense report for monitoring.
    
    Args:
        wallet_address: Optional wallet to filter by
        miner_id: Optional miner to filter by
        hours: Time window in hours
        
    Returns:
        Dict with replay defense statistics
    """
    now = int(time.time())
    window_start = now - (hours * 3600)

    with sqlite3.connect(get_db_path()) as conn:
        c = conn.cursor()
        
        # Base query
        base_query = "SELECT COUNT(*) FROM fingerprint_submissions WHERE submitted_at > ?"
        params = [window_start]
        
        if wallet_address:
            base_query += " AND wallet_address = ?"
            params.append(wallet_address)
        
        if miner_id:
            base_query += " AND miner_id = ?"
            params.append(miner_id)
        
        # Total submissions
        c.execute(base_query, params)
        total_submissions = c.fetchone()[0]
        
        # Unique fingerprints
        unique_query = base_query.replace("COUNT(*)", "COUNT(DISTINCT fingerprint_hash)")
        c.execute(unique_query, params)
        unique_fingerprints = c.fetchone()[0]
        
        # Detected replays (approximate - would need additional logging)
        c.execute('''
            SELECT COUNT(*) FROM entropy_collisions
            WHERE detected_at > ?
        ''', (window_start,))
        collision_count = c.fetchone()[0]
        
        # Rate limited submissions
        c.execute('''
            SELECT COUNT(*) FROM fingerprint_rate_limits
            WHERE submission_count >= ?
        ''', (MAX_FINGERPRINT_SUBMISSIONS_PER_HOUR,))
        rate_limited_hardware = c.fetchone()[0]
        
        return {
            'time_window_hours': hours,
            'total_submissions': total_submissions,
            'unique_fingerprints': unique_fingerprints,
            'entropy_collisions_detected': collision_count,
            'rate_limited_hardware_ids': rate_limited_hardware,
            'replay_window_seconds': REPLAY_WINDOW_SECONDS,
            'max_submissions_per_hour': MAX_FINGERPRINT_SUBMISSIONS_PER_HOUR
        }


# =====================================================================
# Temporal Validation & Entropy Drift Detection (Issue #19 / Bounty 40 RTC)
# =====================================================================

MAX_TEMPORAL_HISTORY = 10

# Expected variance / drift bands for real physical silicon
# If variance == 0 across >= 5 snapshots -> FROZEN (deterministic VM/emulator)
# If coefficient of variation of ratios exceeds NOISE_CV_THRESHOLD -> NOISY (randomized spoofing)
FROZEN_VARIANCE_TOLERANCE = 1e-9
NOISE_CV_THRESHOLD = 0.65


def extract_snapshot_metrics(fingerprint: Dict) -> Dict[str, float]:
    """Extract dimensionless, load-normalized metrics for temporal tracking."""
    metrics = {
        'clock_cv': 0.0,
        'cache_l2_l1': 0.0,
        'thermal_ratio': 0.0,
        'jitter_fp_int': 0.0,
    }
    if not isinstance(fingerprint, dict):
        return metrics

    checks = fingerprint.get('checks', {})
    if not isinstance(checks, dict):
        return metrics

    # Clock drift CV
    clock_data = checks.get('clock_drift', {}).get('data', {})
    if isinstance(clock_data, dict):
        metrics['clock_cv'] = float(clock_data.get('cv', 0.0) or 0.0)

    # Cache ratio
    cache_data = checks.get('cache_timing', {}).get('data', {})
    if isinstance(cache_data, dict):
        metrics['cache_l2_l1'] = float(cache_data.get('l2_l1_ratio', 0.0) or 0.0)

    # Thermal ratio
    thermal_data = checks.get('thermal_drift', {}).get('data', {})
    if isinstance(thermal_data, dict):
        metrics['thermal_ratio'] = float(thermal_data.get('drift_ratio', 0.0) or 0.0)

    # Jitter ratio
    jitter_data = checks.get('instruction_jitter', {}).get('data', {})
    if isinstance(jitter_data, dict):
        int_avg = jitter_data.get('int_avg_ns', 0) or 0
        if int_avg:
            metrics['jitter_fp_int'] = float(round(jitter_data.get('fp_avg_ns', 0) / int_avg, 4))

    return metrics


def store_fingerprint_snapshot(
    miner_id: str,
    wallet_address: str,
    fingerprint: Dict,
    recorded_at: Optional[int] = None
) -> Dict[str, Any]:
    """
    Store a fingerprint snapshot in miner_fingerprint_history, pruning to last 10 records.
    """
    now = recorded_at if recorded_at is not None else int(time.time())
    metrics = extract_snapshot_metrics(fingerprint)
    snapshot_json = json.dumps(metrics, sort_keys=True)

    with sqlite3.connect(get_db_path()) as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO miner_fingerprint_history
            (miner_id, wallet_address, snapshot_json, clock_cv, cache_l2_l1, thermal_ratio, jitter_fp_int, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            miner_id,
            wallet_address,
            snapshot_json,
            metrics['clock_cv'],
            metrics['cache_l2_l1'],
            metrics['thermal_ratio'],
            metrics['jitter_fp_int'],
            now
        ))

        # Prune to keep only the last MAX_TEMPORAL_HISTORY snapshots per miner
        c.execute('''
            DELETE FROM miner_fingerprint_history
            WHERE miner_id = ? AND id NOT IN (
                SELECT id FROM miner_fingerprint_history
                WHERE miner_id = ?
                ORDER BY recorded_at DESC, id DESC
                LIMIT ?
            )
        ''', (miner_id, miner_id, MAX_TEMPORAL_HISTORY))
        conn.commit()

    return {
        'miner_id': miner_id,
        'metrics': metrics,
        'recorded_at': now
    }


def _calc_stats(values: List[float]) -> Tuple[float, float, float]:
    """Returns (mean, variance, cv) for a float series."""
    n = len(values)
    if n == 0:
        return 0.0, 0.0, 0.0
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0, 0.0
    var = sum((x - mean) ** 2 for x in values) / (n - 1)
    std = var ** 0.5
    cv = (std / mean) if mean > 1e-12 else 0.0
    return mean, var, cv


def validate_temporal_consistency(
    miner_id: str,
    min_snapshots: int = 5
) -> Dict[str, Any]:
    """
    Evaluate the temporal consistency of a miner's entropy history.
    
    Returns:
        Dict with:
          - 'status': 'PASS' | 'FROZEN' | 'NOISY' | 'INSUFFICIENT_HISTORY'
          - 'anomaly_detected': bool
          - 'flagged_for_review': bool
          - 'score': float (0.0 to 1.0, where 1.0 is healthy natural physical drift)
          - 'details': detailed variance/CV stats per tracked metric
    """
    with sqlite3.connect(get_db_path()) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT clock_cv, cache_l2_l1, thermal_ratio, jitter_fp_int, recorded_at
            FROM miner_fingerprint_history
            WHERE miner_id = ?
            ORDER BY recorded_at ASC, id ASC
            LIMIT ?
        ''', (miner_id, MAX_TEMPORAL_HISTORY))
        rows = c.fetchall()

    if len(rows) < min_snapshots:
        return {
            'status': 'INSUFFICIENT_HISTORY',
            'snapshots_count': len(rows),
            'min_required': min_snapshots,
            'anomaly_detected': False,
            'flagged_for_review': False,
            'score': 1.0,
            'details': {}
        }

    clocks = [r[0] for r in rows if r[0] is not None]
    caches = [r[1] for r in rows if r[1] is not None]
    thermals = [r[2] for r in rows if r[2] is not None]
    jitters = [r[3] for r in rows if r[3] is not None]

    clock_mean, clock_var, clock_cv = _calc_stats(clocks)
    cache_mean, cache_var, cache_cv = _calc_stats(caches)
    thermal_mean, thermal_var, thermal_cv = _calc_stats(thermals)
    jitter_mean, jitter_var, jitter_cv = _calc_stats(jitters)

    details = {
        'snapshots': len(rows),
        'clock_cv_stats': {'mean': round(clock_mean, 6), 'variance': round(clock_var, 8), 'cv': round(clock_cv, 4)},
        'cache_l2_l1_stats': {'mean': round(cache_mean, 4), 'variance': round(cache_var, 8), 'cv': round(cache_cv, 4)},
        'thermal_ratio_stats': {'mean': round(thermal_mean, 4), 'variance': round(thermal_var, 8), 'cv': round(thermal_cv, 4)},
        'jitter_ratio_stats': {'mean': round(jitter_mean, 4), 'variance': round(jitter_var, 8), 'cv': round(jitter_cv, 4)},
    }

    # 1. Detection of "frozen" profiles (zero variance across all entropy channels)
    if (clock_var < FROZEN_VARIANCE_TOLERANCE and
        cache_var < FROZEN_VARIANCE_TOLERANCE and
        thermal_var < FROZEN_VARIANCE_TOLERANCE and
        jitter_var < FROZEN_VARIANCE_TOLERANCE):
        return {
            'status': 'FROZEN',
            'snapshots_count': len(rows),
            'anomaly_detected': True,
            'flagged_for_review': True,
            'score': 0.0,
            'reason': 'zero_variance_deterministic_emulation',
            'details': details
        }

    # 2. Detection of "noisy" profiles (excessive variation / randomizer spoofing)
    high_noise_metrics = []
    if clock_cv > NOISE_CV_THRESHOLD:
        high_noise_metrics.append('clock_cv')
    if cache_cv > NOISE_CV_THRESHOLD:
        high_noise_metrics.append('cache_l2_l1')
    if thermal_cv > NOISE_CV_THRESHOLD:
        high_noise_metrics.append('thermal_ratio')
    if jitter_cv > NOISE_CV_THRESHOLD:
        high_noise_metrics.append('jitter_fp_int')

    if len(high_noise_metrics) >= 2:
        return {
            'status': 'NOISY',
            'snapshots_count': len(rows),
            'anomaly_detected': True,
            'flagged_for_review': True,
            'score': 0.2,
            'reason': f'excessive_entropy_variance_spoofing: {high_noise_metrics}',
            'details': details
        }

    # Healthy real physical silicon: expected gentle drift
    drift_score = round(max(0.8, 1.0 - (clock_cv + cache_cv + thermal_cv) * 0.1), 3)
    return {
        'status': 'PASS',
        'snapshots_count': len(rows),
        'anomaly_detected': False,
        'flagged_for_review': False,
        'score': drift_score,
        'reason': 'natural_physical_silicon_drift',
        'details': details
    }


# Initialize on import
try:
    init_replay_defense_schema()
except Exception as e:
    print(f"[REPLAY_DEFENSE] Init warning: {e}")


if __name__ == "__main__":
    print("Hardware Fingerprint Replay Defense Module")
    print("=" * 50)
    print(f"Replay Window: {REPLAY_WINDOW_SECONDS}s")
    print(f"Rate Limit: {MAX_FINGERPRINT_SUBMISSIONS_PER_HOUR}/hour")
    print(f"Collision Tolerance: {ENTROPY_HASH_COLLISION_TOLERANCE:.0%}")
    print("\nModule ready for integration.")
