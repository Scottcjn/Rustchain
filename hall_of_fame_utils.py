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

def calculate_machine_rank(fingerprint_hash):
    """Calculate machine's rank in the fleet by rust score."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) + 1 as rank
            FROM machines m1
            WHERE m1.rust_score > (
                SELECT m2.rust_score FROM machines m2
                WHERE m2.fingerprint_hash = ?
            )
        """, (fingerprint_hash,))

        result = cursor.fetchone()
        return result[0] if result else None

def get_machine_performance_trend(fingerprint_hash, days=30):
    """Get machine performance trend over specified days."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DATE(timestamp) as date, AVG(rust_score) as avg_score
            FROM attestations
            WHERE fingerprint_hash = ?
            AND timestamp >= datetime('now', '-{} days')
            GROUP BY DATE(timestamp)
            ORDER BY date
        """.format(days), (fingerprint_hash,))

        return cursor.fetchall()
