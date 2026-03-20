// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

DB_PATH = 'rustchain.db'

def get_miner_hardware_profiles() -> List[Dict[str, Any]]:
    """Get all miner hardware profiles with attestation status"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT m.miner_id, m.hardware_fingerprint, m.hardware_type,
                   m.cpu_info, m.memory_info, m.attestation_status,
                   m.multiplier, m.last_seen, m.blocks_mined,
                   a.attestation_score, a.last_attestation_time,
                   a.verification_count
            FROM miners m
            LEFT JOIN attestations a ON m.miner_id = a.miner_id
            ORDER BY m.multiplier DESC, m.last_seen DESC
        """)

        profiles = []
        for row in cursor.fetchall():
            profile = dict(row)

            # Parse JSON fields if they exist
            if profile['hardware_fingerprint']:
                try:
                    profile['hardware_fingerprint'] = json.loads(profile['hardware_fingerprint'])
                except:
                    pass

            if profile['cpu_info']:
                try:
                    profile['cpu_info'] = json.loads(profile['cpu_info'])
                except:
                    pass

            if profile['memory_info']:
                try:
                    profile['memory_info'] = json.loads(profile['memory_info'])
                except:
                    pass

            profiles.append(profile)

        return profiles

def get_vintage_hardware_stats() -> Dict[str, Any]:
    """Get statistics about vintage hardware in the museum"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Hardware type distribution
        cursor.execute("""
            SELECT hardware_type, COUNT(*) as count, AVG(multiplier) as avg_multiplier
            FROM miners
            WHERE attestation_status = 'verified'
            GROUP BY hardware_type
            ORDER BY avg_multiplier DESC
        """)
        hardware_types = cursor.fetchall()

        # Age distribution (based on estimated hardware age)
        cursor.execute("""
            SELECT
                CASE
                    WHEN hardware_type LIKE '%68K%' OR hardware_type LIKE '%680%' THEN '1980s-1990s'
                    WHEN hardware_type LIKE '%PowerPC%' OR hardware_type LIKE '%G3%' OR hardware_type LIKE '%G4%' THEN '1990s-2000s'
                    WHEN hardware_type LIKE '%G5%' OR hardware_type LIKE '%SPARC%' THEN '2000s-2010s'
                    ELSE 'Modern'
                END as era,
                COUNT(*) as count,
                AVG(multiplier) as avg_multiplier
            FROM miners
            WHERE attestation_status = 'verified'
            GROUP BY era
            ORDER BY avg_multiplier DESC
        """)
        era_stats = cursor.fetchall()

        # Total stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_miners,
                COUNT(CASE WHEN attestation_status = 'verified' THEN 1 END) as verified_miners,
                AVG(multiplier) as avg_multiplier,
                MAX(multiplier) as max_multiplier,
                SUM(blocks_mined) as total_blocks
            FROM miners
        """)
        totals = cursor.fetchone()

        return {
            'hardware_types': [dict(zip(['type', 'count', 'avg_multiplier'], row)) for row in hardware_types],
            'era_distribution': [dict(zip(['era', 'count', 'avg_multiplier'], row)) for row in era_stats],
            'totals': dict(zip(['total_miners', 'verified_miners', 'avg_multiplier', 'max_multiplier', 'total_blocks'], totals))
        }

def get_miner_attestation_history(miner_id: str) -> List[Dict[str, Any]]:
    """Get attestation history for a specific miner"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT timestamp, attestation_type, result, score,
                   verification_data, attestor_node
            FROM attestation_history
            WHERE miner_id = ?
            ORDER BY timestamp DESC
            LIMIT 50
        """, (miner_id,))

        history = []
        for row in cursor.fetchall():
            entry = dict(row)
            if entry['verification_data']:
                try:
                    entry['verification_data'] = json.loads(entry['verification_data'])
                except:
                    pass
            history.append(entry)

        return history

def get_hardware_museum_timeline() -> List[Dict[str, Any]]:
    """Get chronological timeline of hardware joining the museum"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT m.miner_id, m.hardware_type, m.cpu_info, m.first_seen,
                   m.attestation_status, m.multiplier,
                   COUNT(b.hash) as blocks_contributed
            FROM miners m
            LEFT JOIN blocks b ON m.miner_id = b.miner
            WHERE m.attestation_status = 'verified'
            GROUP BY m.miner_id
            ORDER BY m.first_seen ASC
        """)

        timeline = []
        for row in cursor.fetchall():
            entry = dict(row)
            if entry['cpu_info']:
                try:
                    entry['cpu_info'] = json.loads(entry['cpu_info'])
                except:
                    pass
            timeline.append(entry)

        return timeline

def get_hardware_fingerprint_analysis() -> Dict[str, Any]:
    """Analyze hardware fingerprints for museum classification"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT hardware_fingerprint, hardware_type, multiplier
            FROM miners
            WHERE attestation_status = 'verified'
            AND hardware_fingerprint IS NOT NULL
        """)

        fingerprints = []
        architecture_counts = {}

        for row in cursor.fetchall():
            fp_data = row['hardware_fingerprint']
            if fp_data:
                try:
                    fp_json = json.loads(fp_data) if isinstance(fp_data, str) else fp_data

                    # Extract architecture info
                    arch = 'Unknown'
                    if 'cpu_arch' in fp_json:
                        arch = fp_json['cpu_arch']
                    elif 'processor' in fp_json:
                        proc = fp_json['processor'].lower()
                        if 'powerpc' in proc or 'ppc' in proc:
                            arch = 'PowerPC'
                        elif '68k' in proc or 'm680' in proc:
                            arch = '68K'
                        elif 'sparc' in proc:
                            arch = 'SPARC'
                        elif 'x86' in proc:
                            arch = 'x86'

                    architecture_counts[arch] = architecture_counts.get(arch, 0) + 1

                    fingerprints.append({
                        'fingerprint': fp_json,
                        'hardware_type': row['hardware_type'],
                        'multiplier': row['multiplier'],
                        'architecture': arch
                    })
                except:
                    continue

        return {
            'fingerprints': fingerprints,
            'architecture_distribution': architecture_counts
        }

def get_recent_museum_activity(hours: int = 24) -> Dict[str, Any]:
    """Get recent activity in the hardware museum"""
    cutoff_time = datetime.now() - timedelta(hours=hours)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Recent blocks by vintage hardware
        cursor.execute("""
            SELECT b.hash, b.timestamp, b.miner, m.hardware_type, m.multiplier
            FROM blocks b
            JOIN miners m ON b.miner = m.miner_id
            WHERE b.timestamp > ? AND m.attestation_status = 'verified'
            ORDER BY b.timestamp DESC
            LIMIT 20
        """, (cutoff_time.isoformat(),))
        recent_blocks = [dict(row) for row in cursor.fetchall()]

        # Recent attestations
        cursor.execute("""
            SELECT ah.miner_id, ah.timestamp, ah.attestation_type, ah.result,
                   ah.score, m.hardware_type
            FROM attestation_history ah
            JOIN miners m ON ah.miner_id = m.miner_id
            WHERE ah.timestamp > ?
            ORDER BY ah.timestamp DESC
            LIMIT 15
        """, (cutoff_time.isoformat(),))
        recent_attestations = [dict(row) for row in cursor.fetchall()]

        # New miners joined
        cursor.execute("""
            SELECT miner_id, hardware_type, first_seen, multiplier
            FROM miners
            WHERE first_seen > ?
            ORDER BY first_seen DESC
        """, (cutoff_time.isoformat(),))
        new_miners = [dict(row) for row in cursor.fetchall()]

        return {
            'recent_blocks': recent_blocks,
            'recent_attestations': recent_attestations,
            'new_miners': new_miners
        }

def get_hardware_rarity_scores() -> List[Dict[str, Any]]:
    """Calculate rarity scores for different hardware types"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT hardware_type, COUNT(*) as count, AVG(multiplier) as avg_multiplier,
                   MAX(multiplier) as max_multiplier, MIN(first_seen) as oldest_seen
            FROM miners
            WHERE attestation_status = 'verified'
            GROUP BY hardware_type
            ORDER BY count ASC, avg_multiplier DESC
        """)

        hardware_stats = []
        total_miners = 0

        # First pass to get total count
        for row in cursor.fetchall():
            total_miners += row['count']

        # Reset cursor
        cursor.execute("""
            SELECT hardware_type, COUNT(*) as count, AVG(multiplier) as avg_multiplier,
                   MAX(multiplier) as max_multiplier, MIN(first_seen) as oldest_seen
            FROM miners
            WHERE attestation_status = 'verified'
            GROUP BY hardware_type
            ORDER BY count ASC, avg_multiplier DESC
        """)

        for row in cursor.fetchall():
            stats = dict(row)

            # Calculate rarity score (lower count = higher rarity)
            rarity_score = (total_miners - stats['count']) / total_miners * 100
            stats['rarity_score'] = round(rarity_score, 2)
            stats['rarity_tier'] = (
                'Legendary' if rarity_score > 80 else
                'Rare' if rarity_score > 60 else
                'Uncommon' if rarity_score > 40 else
                'Common'
            )

            hardware_stats.append(stats)

        return hardware_stats
