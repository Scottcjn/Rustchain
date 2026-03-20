// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
import hashlib
from typing import Dict, List, Optional, Tuple

DB_PATH = 'rustchain.db'

class ArchValidator:
    def __init__(self):
        self.init_device_profiles()

    def init_device_profiles(self):
        """Initialize device profile database with known vintage hardware signatures"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Create device profiles table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS device_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    arch_family TEXT NOT NULL,
                    model TEXT NOT NULL,
                    cpu_signature TEXT NOT NULL,
                    expected_multiplier REAL NOT NULL,
                    reference_fingerprint TEXT,
                    validation_patterns TEXT,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
            ''')

            # Create validation history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS arch_validations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    miner_id TEXT NOT NULL,
                    device_profile_id INTEGER,
                    confidence_score REAL NOT NULL,
                    validation_result TEXT NOT NULL,
                    fingerprint_data TEXT,
                    timestamp INTEGER DEFAULT (strftime('%s', 'now')),
                    FOREIGN KEY (device_profile_id) REFERENCES device_profiles (id)
                )
            ''')

            # Seed with known vintage hardware profiles
            profiles = [
                ('powerpc', 'PowerMac G4', 'ppc7400', 3.5,
                 '{"cpu_endian":"big","cache_l1":32768,"fpu_precision":"double"}',
                 '{"memory_alignment":8,"bus_width":64,"instruction_set":"altivec"}'),
                ('powerpc', 'PowerMac G5', 'ppc970', 4.0,
                 '{"cpu_endian":"big","cache_l1":32768,"cache_l2":524288}',
                 '{"memory_alignment":16,"bus_width":128,"instruction_set":"altivec"}'),
                ('m68k', 'Quadra 950', '68040', 5.0,
                 '{"cpu_endian":"big","cache_l1":8192,"fpu_type":"68881"}',
                 '{"memory_alignment":4,"bus_width":32,"addressing":"24bit"}'),
                ('sparc', 'SPARCstation 20', 'supersparc', 4.2,
                 '{"cpu_endian":"big","cache_l1":20480,"mmu_type":"srmmu"}',
                 '{"memory_alignment":8,"bus_width":64,"instruction_set":"sparcv8"}'),
                ('mips', 'SGI Indy R5000', 'r5000', 3.8,
                 '{"cpu_endian":"big","cache_l1":32768,"cache_l2":1048576}',
                 '{"memory_alignment":8,"bus_width":64,"instruction_set":"mips4"}')
            ]

            cursor.execute('SELECT COUNT(*) FROM device_profiles')
            if cursor.fetchone()[0] == 0:
                for profile in profiles:
                    cursor.execute('''
                        INSERT INTO device_profiles
                        (arch_family, model, cpu_signature, expected_multiplier, reference_fingerprint, validation_patterns)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', profile)

            conn.commit()

    def validate_miner_attestation(self, miner_id: str, fingerprint_data: Dict) -> Tuple[float, str, Optional[int]]:
        """Cross-validate miner attestation against device profiles"""

        # Extract key fingerprint components
        arch_info = fingerprint_data.get('architecture', {})
        cpu_info = fingerprint_data.get('cpu_info', {})
        memory_info = fingerprint_data.get('memory_info', {})

        best_match = None
        highest_confidence = 0.0
        validation_result = "no_match"

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM device_profiles')
            profiles = cursor.fetchall()

            for profile in profiles:
                profile_id, arch_family, model, cpu_sig, expected_mult, ref_fp, val_patterns = profile[:7]

                confidence = self._calculate_confidence_score(
                    fingerprint_data,
                    json.loads(ref_fp) if ref_fp else {},
                    json.loads(val_patterns) if val_patterns else {},
                    arch_family
                )

                if confidence > highest_confidence:
                    highest_confidence = confidence
                    best_match = profile_id
                    if confidence >= 0.85:
                        validation_result = "authentic"
                    elif confidence >= 0.60:
                        validation_result = "probable"
                    else:
                        validation_result = "suspicious"

            # Log validation attempt
            cursor.execute('''
                INSERT INTO arch_validations
                (miner_id, device_profile_id, confidence_score, validation_result, fingerprint_data)
                VALUES (?, ?, ?, ?, ?)
            ''', (miner_id, best_match, highest_confidence, validation_result, json.dumps(fingerprint_data)))

            conn.commit()

        return highest_confidence, validation_result, best_match

    def _calculate_confidence_score(self, fingerprint: Dict, reference: Dict, patterns: Dict, arch_family: str) -> float:
        """Calculate confidence score based on fingerprint matching"""
        score = 0.0
        total_checks = 0

        # Architecture family check (30% weight)
        arch_info = fingerprint.get('architecture', {})
        if arch_info.get('family', '').lower() == arch_family.lower():
            score += 0.30
        total_checks += 0.30

        # CPU endianness check (20% weight)
        cpu_info = fingerprint.get('cpu_info', {})
        ref_endian = reference.get('cpu_endian')
        if ref_endian and cpu_info.get('endianness') == ref_endian:
            score += 0.20
        total_checks += 0.20

        # Cache size validation (15% weight)
        ref_cache = reference.get('cache_l1')
        actual_cache = cpu_info.get('cache_size_l1')
        if ref_cache and actual_cache:
            cache_ratio = min(actual_cache, ref_cache) / max(actual_cache, ref_cache)
            if cache_ratio >= 0.8:
                score += 0.15 * cache_ratio
        total_checks += 0.15

        # Memory alignment check (15% weight)
        expected_alignment = patterns.get('memory_alignment')
        actual_alignment = fingerprint.get('memory_info', {}).get('alignment')
        if expected_alignment and actual_alignment == expected_alignment:
            score += 0.15
        total_checks += 0.15

        # Bus width validation (10% weight)
        expected_bus = patterns.get('bus_width')
        actual_bus = fingerprint.get('system_info', {}).get('bus_width')
        if expected_bus and actual_bus == expected_bus:
            score += 0.10
        total_checks += 0.10

        # Instruction set compatibility (10% weight)
        expected_isa = patterns.get('instruction_set')
        actual_isa = cpu_info.get('instruction_set')
        if expected_isa and actual_isa and expected_isa.lower() in actual_isa.lower():
            score += 0.10
        total_checks += 0.10

        return score / total_checks if total_checks > 0 else 0.0

    def get_miner_validation_history(self, miner_id: str, limit: int = 10) -> List[Dict]:
        """Retrieve validation history for a specific miner"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT av.confidence_score, av.validation_result, av.timestamp,
                       dp.arch_family, dp.model, dp.expected_multiplier
                FROM arch_validations av
                LEFT JOIN device_profiles dp ON av.device_profile_id = dp.id
                WHERE av.miner_id = ?
                ORDER BY av.timestamp DESC
                LIMIT ?
            ''', (miner_id, limit))

            results = []
            for row in cursor.fetchall():
                results.append({
                    'confidence_score': row[0],
                    'validation_result': row[1],
                    'timestamp': row[2],
                    'arch_family': row[3],
                    'model': row[4],
                    'expected_multiplier': row[5]
                })

            return results

    def detect_suspicious_patterns(self, lookback_hours: int = 24) -> List[Dict]:
        """Identify potentially suspicious validation patterns"""
        cutoff_time = int(time.time()) - (lookback_hours * 3600)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Find miners with consistently low confidence scores
            cursor.execute('''
                SELECT miner_id, AVG(confidence_score) as avg_confidence, COUNT(*) as attempt_count
                FROM arch_validations
                WHERE timestamp > ?
                GROUP BY miner_id
                HAVING avg_confidence < 0.60 AND attempt_count >= 3
                ORDER BY avg_confidence ASC
            ''', (cutoff_time,))

            suspicious = []
            for row in cursor.fetchall():
                suspicious.append({
                    'miner_id': row[0],
                    'avg_confidence': row[1],
                    'attempt_count': row[2],
                    'risk_level': 'high' if row[1] < 0.40 else 'medium'
                })

            return suspicious

    def get_architecture_stats(self) -> Dict:
        """Get validation statistics by architecture family"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT dp.arch_family,
                       COUNT(*) as validation_count,
                       AVG(av.confidence_score) as avg_confidence,
                       COUNT(DISTINCT av.miner_id) as unique_miners
                FROM arch_validations av
                JOIN device_profiles dp ON av.device_profile_id = dp.id
                GROUP BY dp.arch_family
                ORDER BY validation_count DESC
            ''')

            stats = {}
            for row in cursor.fetchall():
                stats[row[0]] = {
                    'validation_count': row[1],
                    'avg_confidence': round(row[2], 3),
                    'unique_miners': row[3]
                }

            return stats
