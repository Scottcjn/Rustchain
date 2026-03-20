// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
from typing import List, Dict, Optional, Tuple
import hashlib
import os

DB_PATH = 'node/fingerprint_history.db'

class FingerprintHistory:
    def __init__(self, max_history_per_miner: int = 50):
        self.max_history = max_history_per_miner
        self._init_database()

    def _init_database(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS fingerprint_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    miner_address TEXT NOT NULL,
                    fingerprint_hash TEXT NOT NULL,
                    fingerprint_data TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    block_height INTEGER,
                    attestation_count INTEGER DEFAULT 1,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_miner_timestamp
                ON fingerprint_history(miner_address, timestamp DESC)
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_fingerprint_hash
                ON fingerprint_history(fingerprint_hash)
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_block_height
                ON fingerprint_history(block_height DESC)
            ''')

    def store_fingerprint(self, miner_address: str, fingerprint_data: Dict,
                         block_height: Optional[int] = None) -> bool:
        fingerprint_json = json.dumps(fingerprint_data, sort_keys=True)
        fingerprint_hash = hashlib.sha256(fingerprint_json.encode()).hexdigest()
        current_time = int(time.time())

        with sqlite3.connect(DB_PATH) as conn:
            # Check if identical fingerprint exists recently (within 1 hour)
            recent_check = conn.execute('''
                SELECT id, attestation_count FROM fingerprint_history
                WHERE miner_address = ? AND fingerprint_hash = ?
                AND timestamp > ?
                ORDER BY timestamp DESC LIMIT 1
            ''', (miner_address, fingerprint_hash, current_time - 3600)).fetchone()

            if recent_check:
                # Update attestation count for recent identical fingerprint
                conn.execute('''
                    UPDATE fingerprint_history
                    SET attestation_count = attestation_count + 1,
                        timestamp = ?
                    WHERE id = ?
                ''', (current_time, recent_check[0]))
                return True

            # Insert new fingerprint entry
            conn.execute('''
                INSERT INTO fingerprint_history
                (miner_address, fingerprint_hash, fingerprint_data, timestamp, block_height)
                VALUES (?, ?, ?, ?, ?)
            ''', (miner_address, fingerprint_hash, fingerprint_json, current_time, block_height))

            # Cleanup old entries for this miner
            self._cleanup_old_entries(conn, miner_address)

        return True

    def _cleanup_old_entries(self, conn, miner_address: str):
        # Keep only the most recent N entries per miner
        conn.execute('''
            DELETE FROM fingerprint_history
            WHERE miner_address = ? AND id NOT IN (
                SELECT id FROM fingerprint_history
                WHERE miner_address = ?
                ORDER BY timestamp DESC
                LIMIT ?
            )
        ''', (miner_address, miner_address, self.max_history))

    def get_miner_history(self, miner_address: str, limit: int = 10) -> List[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute('''
                SELECT fingerprint_hash, fingerprint_data, timestamp,
                       block_height, attestation_count
                FROM fingerprint_history
                WHERE miner_address = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (miner_address, limit)).fetchall()

        history = []
        for row in rows:
            entry = {
                'fingerprint_hash': row[0],
                'fingerprint_data': json.loads(row[1]),
                'timestamp': row[2],
                'block_height': row[3],
                'attestation_count': row[4]
            }
            history.append(entry)

        return history

    def validate_entropy_profile(self, miner_address: str,
                                new_fingerprint: Dict,
                                lookback_hours: int = 24) -> Tuple[bool, str]:
        cutoff_time = int(time.time()) - (lookback_hours * 3600)

        with sqlite3.connect(DB_PATH) as conn:
            historical_data = conn.execute('''
                SELECT fingerprint_data, timestamp
                FROM fingerprint_history
                WHERE miner_address = ? AND timestamp > ?
                ORDER BY timestamp DESC
                LIMIT 20
            ''', (miner_address, cutoff_time)).fetchall()

        if len(historical_data) < 3:
            return True, "Insufficient history for entropy validation"

        # Calculate entropy metrics
        entropy_scores = []
        hardware_consistency = True

        for row in historical_data:
            old_fp = json.loads(row[0])
            entropy_score = self._calculate_entropy_difference(new_fingerprint, old_fp)
            entropy_scores.append(entropy_score)

            # Check hardware consistency
            if not self._check_hardware_consistency(new_fingerprint, old_fp):
                hardware_consistency = False

        avg_entropy = sum(entropy_scores) / len(entropy_scores) if entropy_scores else 0

        # Validation thresholds
        if avg_entropy < 0.1:
            return False, f"Low entropy variance: {avg_entropy:.3f}"

        if not hardware_consistency:
            return False, "Hardware fingerprint inconsistency detected"

        if avg_entropy > 0.8:
            return False, f"Excessive entropy variance: {avg_entropy:.3f} (possible VM/emulator)"

        return True, f"Entropy profile valid (score: {avg_entropy:.3f})"

    def _calculate_entropy_difference(self, fp1: Dict, fp2: Dict) -> float:
        # Compare key fingerprint components
        entropy_factors = [
            'cpu_model', 'memory_total', 'disk_serial',
            'network_mac', 'system_uuid', 'motherboard_serial'
        ]

        differences = 0
        total_checks = 0

        for factor in entropy_factors:
            if factor in fp1 and factor in fp2:
                total_checks += 1
                if fp1[factor] != fp2[factor]:
                    differences += 1
                elif isinstance(fp1[factor], str) and isinstance(fp2[factor], str):
                    # Check string similarity for partial changes
                    similarity = self._string_similarity(fp1[factor], fp2[factor])
                    if similarity < 0.9:
                        differences += (1 - similarity)

        return differences / max(total_checks, 1)

    def _string_similarity(self, s1: str, s2: str) -> float:
        if not s1 or not s2:
            return 0.0
        if s1 == s2:
            return 1.0

        # Simple character-level similarity
        matches = sum(c1 == c2 for c1, c2 in zip(s1, s2))
        max_len = max(len(s1), len(s2))
        return matches / max_len if max_len > 0 else 0.0

    def _check_hardware_consistency(self, fp1: Dict, fp2: Dict) -> bool:
        # Core hardware should remain consistent
        stable_components = ['cpu_architecture', 'cpu_cores', 'motherboard_model']

        for component in stable_components:
            if component in fp1 and component in fp2:
                if fp1[component] != fp2[component]:
                    return False
        return True

    def get_network_entropy_stats(self) -> Dict:
        with sqlite3.connect(DB_PATH) as conn:
            # Active miners in last 24 hours
            active_miners = conn.execute('''
                SELECT COUNT(DISTINCT miner_address)
                FROM fingerprint_history
                WHERE timestamp > ?
            ''', (int(time.time()) - 86400,)).fetchone()[0]

            # Total fingerprint entries
            total_entries = conn.execute('''
                SELECT COUNT(*) FROM fingerprint_history
            ''').fetchone()[0]

            # Average attestations per fingerprint
            avg_attestations = conn.execute('''
                SELECT AVG(attestation_count) FROM fingerprint_history
            ''').fetchone()[0] or 0

        return {
            'active_miners_24h': active_miners,
            'total_fingerprint_entries': total_entries,
            'avg_attestations_per_entry': round(avg_attestations, 2),
            'database_size_kb': os.path.getsize(DB_PATH) // 1024 if os.path.exists(DB_PATH) else 0
        }

    def cleanup_old_data(self, days_to_keep: int = 30):
        cutoff_time = int(time.time()) - (days_to_keep * 86400)

        with sqlite3.connect(DB_PATH) as conn:
            deleted = conn.execute('''
                DELETE FROM fingerprint_history
                WHERE timestamp < ?
            ''', (cutoff_time,)).rowcount

        return deleted
