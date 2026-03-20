# SPDX-License-Identifier: MIT

import sqlite3
import json
import hashlib
import time
from typing import Dict, List, Optional, Tuple, Any

DB_PATH = "rustchain.db"

KNOWN_ARCH_PROFILES = {
    'powerpc-g4': {
        'cpu_arch': 'powerpc',
        'endianness': 'big',
        'expected_flags': ['altivec', 'ppc750', 'g4'],
        'cache_sizes': {'l1_data': 32768, 'l1_inst': 32768, 'l2': 262144},
        'multiplier': 3.5,
        'min_consistency': 0.85
    },
    'powerpc-g5': {
        'cpu_arch': 'powerpc',
        'endianness': 'big',
        'expected_flags': ['altivec', 'ppc970', 'g5'],
        'cache_sizes': {'l1_data': 32768, 'l1_inst': 65536, 'l2': 524288},
        'multiplier': 4.2,
        'min_consistency': 0.87
    },
    'm68k-classic': {
        'cpu_arch': 'm68k',
        'endianness': 'big',
        'expected_flags': ['68040', 'fpu'],
        'cache_sizes': {'l1_data': 4096, 'l1_inst': 4096},
        'multiplier': 5.8,
        'min_consistency': 0.80
    },
    'sparc-ultra': {
        'cpu_arch': 'sparc',
        'endianness': 'big',
        'expected_flags': ['sparc64', 'vis'],
        'cache_sizes': {'l1_data': 16384, 'l1_inst': 16384, 'l2': 256000},
        'multiplier': 4.7,
        'min_consistency': 0.82
    },
    'x86-modern': {
        'cpu_arch': 'x86_64',
        'endianness': 'little',
        'expected_flags': ['sse2', 'avx'],
        'cache_sizes': {'l1_data': 32768, 'l1_inst': 32768, 'l2': 262144},
        'multiplier': 1.0,
        'min_consistency': 0.95
    }
}

def init_arch_validation_db():
    """Initialize architecture validation tables"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS arch_validation_scores (
                miner_id TEXT PRIMARY KEY,
                arch_profile TEXT,
                consistency_score REAL,
                fingerprint_hash TEXT,
                validation_data TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                validation_count INTEGER DEFAULT 1
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS arch_fingerprint_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT,
                fingerprint_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                consistency_delta REAL
            )
        """)
        conn.commit()

def calculate_fingerprint_hash(fingerprint_data: Dict) -> str:
    """Generate consistent hash from fingerprint data"""
    normalized = {
        'cpu_arch': fingerprint_data.get('cpu_arch', ''),
        'endianness': fingerprint_data.get('endianness', ''),
        'cache_l1d': fingerprint_data.get('cache_sizes', {}).get('l1_data', 0),
        'cache_l1i': fingerprint_data.get('cache_sizes', {}).get('l1_inst', 0),
        'flags': sorted(fingerprint_data.get('cpu_flags', []))
    }
    content = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()

def detect_arch_profile(fingerprint_data: Dict) -> Optional[str]:
    """Detect architecture profile from fingerprint data"""
    cpu_arch = fingerprint_data.get('cpu_arch', '').lower()
    cpu_flags = fingerprint_data.get('cpu_flags', [])
    cache_sizes = fingerprint_data.get('cache_sizes', {})

    # PowerPC detection
    if 'powerpc' in cpu_arch or 'ppc' in cpu_arch:
        if any('g5' in flag or 'ppc970' in flag for flag in cpu_flags):
            return 'powerpc-g5'
        elif any('g4' in flag or 'ppc750' in flag for flag in cpu_flags):
            return 'powerpc-g4'

    # M68K detection
    elif 'm68k' in cpu_arch or '68k' in cpu_arch:
        return 'm68k-classic'

    # SPARC detection
    elif 'sparc' in cpu_arch:
        return 'sparc-ultra'

    # Default to x86 modern
    elif 'x86' in cpu_arch or 'amd64' in cpu_arch:
        return 'x86-modern'

    return None

def score_arch_consistency(fingerprint_data: Dict, profile_name: str) -> float:
    """Score how well fingerprint matches expected architecture profile"""
    if profile_name not in KNOWN_ARCH_PROFILES:
        return 0.0

    profile = KNOWN_ARCH_PROFILES[profile_name]
    score = 0.0
    max_score = 0.0

    # CPU architecture match
    max_score += 30
    if fingerprint_data.get('cpu_arch', '').lower() == profile['cpu_arch']:
        score += 30
    elif profile['cpu_arch'] in fingerprint_data.get('cpu_arch', '').lower():
        score += 20

    # Endianness check
    max_score += 20
    if fingerprint_data.get('endianness') == profile['endianness']:
        score += 20

    # CPU flags validation
    max_score += 25
    cpu_flags = fingerprint_data.get('cpu_flags', [])
    expected_flags = profile['expected_flags']
    flag_matches = sum(1 for flag in expected_flags if any(flag in f for f in cpu_flags))
    score += (flag_matches / len(expected_flags)) * 25

    # Cache size verification
    max_score += 25
    cache_data = fingerprint_data.get('cache_sizes', {})
    expected_cache = profile['cache_sizes']
    cache_score = 0
    for cache_type, expected_size in expected_cache.items():
        actual_size = cache_data.get(cache_type, 0)
        if actual_size > 0:
            ratio = min(actual_size, expected_size) / max(actual_size, expected_size)
            cache_score += ratio
    if expected_cache:
        score += (cache_score / len(expected_cache)) * 25

    return min(score / max_score, 1.0) if max_score > 0 else 0.0

def validate_arch_consistency(miner_id: str, fingerprint_data: Dict) -> Tuple[float, str]:
    """Main validation function - returns (consistency_score, arch_profile)"""
    init_arch_validation_db()

    # Detect architecture profile
    detected_profile = detect_arch_profile(fingerprint_data)
    if not detected_profile:
        return 0.0, 'unknown'

    # Calculate consistency score
    consistency_score = score_arch_consistency(fingerprint_data, detected_profile)
    fingerprint_hash = calculate_fingerprint_hash(fingerprint_data)

    # Store validation results
    with sqlite3.connect(DB_PATH) as conn:
        # Check for existing record
        existing = conn.execute(
            "SELECT consistency_score, validation_count FROM arch_validation_scores WHERE miner_id = ?",
            (miner_id,)
        ).fetchone()

        validation_data = json.dumps({
            'fingerprint': fingerprint_data,
            'detected_profile': detected_profile,
            'timestamp': time.time()
        })

        if existing:
            # Update existing record with running average
            old_score, count = existing
            new_count = count + 1
            avg_score = ((old_score * count) + consistency_score) / new_count

            conn.execute("""
                UPDATE arch_validation_scores
                SET arch_profile = ?, consistency_score = ?, fingerprint_hash = ?,
                    validation_data = ?, last_updated = CURRENT_TIMESTAMP,
                    validation_count = ?
                WHERE miner_id = ?
            """, (detected_profile, avg_score, fingerprint_hash, validation_data, new_count, miner_id))

            consistency_score = avg_score
        else:
            # Insert new record
            conn.execute("""
                INSERT INTO arch_validation_scores
                (miner_id, arch_profile, consistency_score, fingerprint_hash, validation_data)
                VALUES (?, ?, ?, ?, ?)
            """, (miner_id, detected_profile, consistency_score, fingerprint_hash, validation_data))

        # Log fingerprint history
        conn.execute("""
            INSERT INTO arch_fingerprint_history (miner_id, fingerprint_data, consistency_delta)
            VALUES (?, ?, ?)
        """, (miner_id, json.dumps(fingerprint_data), consistency_score))

        conn.commit()

    return consistency_score, detected_profile

def get_miner_validation_status(miner_id: str) -> Dict[str, Any]:
    """Get current validation status for a miner"""
    with sqlite3.connect(DB_PATH) as conn:
        result = conn.execute("""
            SELECT arch_profile, consistency_score, fingerprint_hash,
                   validation_data, last_updated, validation_count
            FROM arch_validation_scores
            WHERE miner_id = ?
        """, (miner_id,)).fetchone()

        if not result:
            return {'status': 'not_validated', 'miner_id': miner_id}

        arch_profile, score, fp_hash, validation_data, last_updated, count = result

        # Check if meets minimum consistency threshold
        min_threshold = KNOWN_ARCH_PROFILES.get(arch_profile, {}).get('min_consistency', 0.8)
        is_valid = score >= min_threshold

        return {
            'miner_id': miner_id,
            'arch_profile': arch_profile,
            'consistency_score': score,
            'is_valid': is_valid,
            'fingerprint_hash': fp_hash,
            'last_updated': last_updated,
            'validation_count': count,
            'multiplier': KNOWN_ARCH_PROFILES.get(arch_profile, {}).get('multiplier', 1.0),
            'status': 'valid' if is_valid else 'inconsistent'
        }

def get_all_validation_scores() -> List[Dict[str, Any]]:
    """Get validation scores for all miners"""
    with sqlite3.connect(DB_PATH) as conn:
        results = conn.execute("""
            SELECT miner_id, arch_profile, consistency_score, last_updated, validation_count
            FROM arch_validation_scores
            ORDER BY consistency_score DESC
        """).fetchall()

        validations = []
        for row in results:
            miner_id, arch_profile, score, last_updated, count = row
            profile_data = KNOWN_ARCH_PROFILES.get(arch_profile, {})
            is_valid = score >= profile_data.get('min_consistency', 0.8)

            validations.append({
                'miner_id': miner_id,
                'arch_profile': arch_profile,
                'consistency_score': score,
                'is_valid': is_valid,
                'multiplier': profile_data.get('multiplier', 1.0),
                'last_updated': last_updated,
                'validation_count': count
            })

        return validations
