// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import hashlib
from datetime import datetime, timedelta
import json

DB_PATH = 'rustchain.db'

def get_machine_details(machine_id):
    """Get comprehensive machine details for profile page."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Get machine basic info
        cursor.execute("""
            SELECT fingerprint_hash, nickname, first_seen, last_seen,
                   total_attestations, rust_score, uptime_percentage
            FROM machines
            WHERE fingerprint_hash = ? OR id = ?
        """, (machine_id, machine_id))

        machine_data = cursor.fetchone()
        if not machine_data:
            return None

        fingerprint_hash, nickname, first_seen, last_seen, total_attestations, rust_score, uptime_pct = machine_data

        # Get recent attestation history
        cursor.execute("""
            SELECT epoch, timestamp, rust_score, block_height
            FROM attestations
            WHERE machine_id = (SELECT id FROM machines WHERE fingerprint_hash = ?)
            ORDER BY epoch DESC LIMIT 100
        """, (fingerprint_hash,))

        attestation_history = cursor.fetchall()

        # Get machine specs if available
        cursor.execute("""
            SELECT cpu_model, ram_gb, storage_gb, os_info
            FROM machine_specs
            WHERE machine_id = (SELECT id FROM machines WHERE fingerprint_hash = ?)
        """, (fingerprint_hash,))

        specs = cursor.fetchone()

        return {
            'fingerprint_hash': fingerprint_hash,
            'nickname': nickname or f"Machine-{fingerprint_hash[:8]}",
            'first_seen': first_seen,
            'last_seen': last_seen,
            'total_attestations': total_attestations,
            'rust_score': rust_score,
            'uptime_percentage': uptime_pct,
            'attestation_history': attestation_history,
            'specs': specs
        }

def format_attestation_timeline(attestation_history):
    """Format attestation history into timeline format."""
    if not attestation_history:
        return []

    timeline = []
    for epoch, timestamp, rust_score, block_height in attestation_history:
        dt = datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else datetime.fromtimestamp(timestamp)

        timeline.append({
            'epoch': epoch,
            'date': dt.strftime('%Y-%m-%d %H:%M UTC'),
            'rust_score': rust_score,
            'block_height': block_height,
            'days_ago': (datetime.utcnow() - dt).days
        })

    return timeline

def calculate_fleet_average():
    """Calculate current fleet averages for comparison."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT AVG(rust_score), AVG(uptime_percentage), AVG(total_attestations)
            FROM machines
            WHERE last_seen > datetime('now', '-7 days')
        """)

        result = cursor.fetchone()
        if result and result[0] is not None:
            return {
                'avg_rust_score': round(result[0], 2),
                'avg_uptime': round(result[1], 2),
                'avg_attestations': round(result[2], 1)
            }

        return {'avg_rust_score': 0, 'avg_uptime': 0, 'avg_attestations': 0}

def generate_rust_badge(rust_score):
    """Generate colored rust badge based on score."""
    if rust_score >= 95:
        color = "#28a745"
        label = "LEGENDARY"
    elif rust_score >= 85:
        color = "#17a2b8"
        label = "ELITE"
    elif rust_score >= 75:
        color = "#ffc107"
        label = "VETERAN"
    elif rust_score >= 60:
        color = "#fd7e14"
        label = "SOLID"
    else:
        color = "#dc3545"
        label = "ROOKIE"

    return f'<span style="background: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold;">{label}</span>'

def generate_machine_ascii_art(fingerprint_hash):
    """Generate simple ASCII art based on machine fingerprint."""
    hash_int = int(hashlib.md5(fingerprint_hash.encode()).hexdigest()[:8], 16)

    patterns = [
        """
    ┌─────────────┐
    │  ◉     ◉    │
    │      ∩      │
    │  ╰─────────╯ │
    └─────────────┘
        """,
        """
    ╭─────────────╮
    │  ●     ●    │
    │      ∩      │
    │  ∪─────────∪ │
    ╰─────────────╯
        """,
        """
    ╔═════════════╗
    ║  ◯     ◯    ║
    ║      ∩      ║
    ║  ╰═════════╯ ║
    ╚═════════════╝
        """,
    ]

    return patterns[hash_int % len(patterns)]

def get_machine_ranking(fingerprint_hash):
    """Get machine's current ranking in the leaderboard."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) + 1 as rank
            FROM machines m1
            WHERE rust_score > (
                SELECT rust_score FROM machines WHERE fingerprint_hash = ?
            )
        """, (fingerprint_hash,))

        result = cursor.fetchone()
        return result[0] if result else 999

def get_peer_machines(fingerprint_hash, limit=5):
    """Get similar machines for comparison."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Get current machine's rust score
        cursor.execute("SELECT rust_score FROM machines WHERE fingerprint_hash = ?", (fingerprint_hash,))
        current_score = cursor.fetchone()

        if not current_score:
            return []

        score = current_score[0]

        # Find machines with similar rust scores
        cursor.execute("""
            SELECT fingerprint_hash, nickname, rust_score, total_attestations
            FROM machines
            WHERE fingerprint_hash != ?
            AND rust_score BETWEEN ? AND ?
            AND last_seen > datetime('now', '-7 days')
            ORDER BY ABS(rust_score - ?) LIMIT ?
        """, (fingerprint_hash, score - 10, score + 10, score, limit))

        return cursor.fetchall()
