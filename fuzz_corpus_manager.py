// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import hashlib
import time
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

DB_PATH = 'fuzz_corpus.db'

class CrashSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class PayloadCategory(Enum):
    TYPE_CONFUSION = "type_confusion"
    MISSING_FIELDS = "missing_fields"
    OVERSIZED_VALUES = "oversized_values"
    BOUNDARY_TIMESTAMPS = "boundary_timestamps"
    NESTED_STRUCTURES = "nested_structures"
    BOOLEAN_MISMATCH = "boolean_mismatch"
    DICT_SHAPE_MISMATCH = "dict_shape_mismatch"
    MALFORMED_JSON = "malformed_json"
    ENCODING_ISSUES = "encoding_issues"
    OTHER = "other"

@dataclass
class CrashEntry:
    payload_hash: str
    payload_data: str
    category: PayloadCategory
    severity: CrashSeverity
    crash_type: str
    stack_trace: str
    timestamp: float
    minimized: bool = False
    regression_tested: bool = False
    notes: str = ""

class FuzzCorpusManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS crash_corpus (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload_hash TEXT UNIQUE NOT NULL,
                    payload_data TEXT NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    crash_type TEXT NOT NULL,
                    stack_trace TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    minimized INTEGER DEFAULT 0,
                    regression_tested INTEGER DEFAULT 0,
                    notes TEXT DEFAULT ''
                )
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_payload_hash
                ON crash_corpus(payload_hash)
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_category
                ON crash_corpus(category)
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_severity
                ON crash_corpus(severity)
            ''')

    def _compute_payload_hash(self, payload_data: str) -> str:
        return hashlib.sha256(payload_data.encode('utf-8')).hexdigest()

    def store_crash(self, payload_data: str, category: PayloadCategory,
                   severity: CrashSeverity, crash_type: str, stack_trace: str,
                   notes: str = "") -> bool:
        payload_hash = self._compute_payload_hash(payload_data)

        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute('''
                    INSERT INTO crash_corpus
                    (payload_hash, payload_data, category, severity, crash_type,
                     stack_trace, timestamp, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (payload_hash, payload_data, category.value, severity.value,
                      crash_type, stack_trace, time.time(), notes))
                return True
            except sqlite3.IntegrityError:
                return False

    def get_crash(self, payload_hash: str) -> Optional[CrashEntry]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT payload_hash, payload_data, category, severity, crash_type,
                       stack_trace, timestamp, minimized, regression_tested, notes
                FROM crash_corpus WHERE payload_hash = ?
            ''', (payload_hash,))

            row = cursor.fetchone()
            if not row:
                return None

            return CrashEntry(
                payload_hash=row[0],
                payload_data=row[1],
                category=PayloadCategory(row[2]),
                severity=CrashSeverity(row[3]),
                crash_type=row[4],
                stack_trace=row[5],
                timestamp=row[6],
                minimized=bool(row[7]),
                regression_tested=bool(row[8]),
                notes=row[9]
            )

    def list_crashes(self, category: Optional[PayloadCategory] = None,
                    severity: Optional[CrashSeverity] = None,
                    limit: int = 100) -> List[CrashEntry]:
        with sqlite3.connect(self.db_path) as conn:
            query = '''
                SELECT payload_hash, payload_data, category, severity, crash_type,
                       stack_trace, timestamp, minimized, regression_tested, notes
                FROM crash_corpus
            '''
            params = []

            conditions = []
            if category:
                conditions.append("category = ?")
                params.append(category.value)
            if severity:
                conditions.append("severity = ?")
                params.append(severity.value)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            crashes = []

            for row in cursor.fetchall():
                crashes.append(CrashEntry(
                    payload_hash=row[0],
                    payload_data=row[1],
                    category=PayloadCategory(row[2]),
                    severity=CrashSeverity(row[3]),
                    crash_type=row[4],
                    stack_trace=row[5],
                    timestamp=row[6],
                    minimized=bool(row[7]),
                    regression_tested=bool(row[8]),
                    notes=row[9]
                ))

            return crashes

    def mark_minimized(self, payload_hash: str, minimized_payload: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                UPDATE crash_corpus
                SET minimized = 1, payload_data = ?, notes = notes || '\nMinimized: ' || datetime('now')
                WHERE payload_hash = ?
            ''', (minimized_payload, payload_hash))
            return cursor.rowcount > 0

    def mark_regression_tested(self, payload_hash: str, test_result: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                UPDATE crash_corpus
                SET regression_tested = 1, notes = notes || '\nRegression tested: ' || ? || ' at ' || datetime('now')
                WHERE payload_hash = ?
            ''', (test_result, payload_hash))
            return cursor.rowcount > 0

    def get_stats(self) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM crash_corpus')
            total_crashes = cursor.fetchone()[0]

            cursor = conn.execute('''
                SELECT category, COUNT(*) FROM crash_corpus GROUP BY category
            ''')
            category_counts = dict(cursor.fetchall())

            cursor = conn.execute('''
                SELECT severity, COUNT(*) FROM crash_corpus GROUP BY severity
            ''')
            severity_counts = dict(cursor.fetchall())

            cursor = conn.execute('''
                SELECT COUNT(*) FROM crash_corpus WHERE minimized = 1
            ''')
            minimized_count = cursor.fetchone()[0]

            cursor = conn.execute('''
                SELECT COUNT(*) FROM crash_corpus WHERE regression_tested = 1
            ''')
            tested_count = cursor.fetchone()[0]

            return {
                'total_crashes': total_crashes,
                'category_breakdown': category_counts,
                'severity_breakdown': severity_counts,
                'minimized_count': minimized_count,
                'regression_tested_count': tested_count
            }

    def export_corpus(self, output_file: str, category: Optional[PayloadCategory] = None):
        crashes = self.list_crashes(category=category, limit=10000)
        export_data = {
            'metadata': {
                'exported_at': time.time(),
                'total_entries': len(crashes),
                'category_filter': category.value if category else None
            },
            'crashes': [asdict(crash) for crash in crashes]
        }

        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)

    def import_corpus(self, input_file: str) -> int:
        with open(input_file, 'r') as f:
            data = json.load(f)

        imported_count = 0
        for crash_data in data.get('crashes', []):
            success = self.store_crash(
                payload_data=crash_data['payload_data'],
                category=PayloadCategory(crash_data['category']),
                severity=CrashSeverity(crash_data['severity']),
                crash_type=crash_data['crash_type'],
                stack_trace=crash_data['stack_trace'],
                notes=crash_data.get('notes', '')
            )
            if success:
                imported_count += 1

        return imported_count

    def deduplicate_similar_crashes(self, similarity_threshold: float = 0.8) -> int:
        crashes = self.list_crashes(limit=10000)
        to_remove = set()

        for i, crash1 in enumerate(crashes):
            if crash1.payload_hash in to_remove:
                continue

            for crash2 in crashes[i+1:]:
                if crash2.payload_hash in to_remove:
                    continue

                if (crash1.crash_type == crash2.crash_type and
                    self._stack_trace_similarity(crash1.stack_trace, crash2.stack_trace) > similarity_threshold):
                    to_remove.add(crash2.payload_hash)

        if to_remove:
            with sqlite3.connect(self.db_path) as conn:
                placeholders = ','.join(['?' for _ in to_remove])
                conn.execute(f'''
                    DELETE FROM crash_corpus WHERE payload_hash IN ({placeholders})
                ''', list(to_remove))

        return len(to_remove)

    def _stack_trace_similarity(self, trace1: str, trace2: str) -> float:
        lines1 = set(trace1.strip().split('\n'))
        lines2 = set(trace2.strip().split('\n'))

        if not lines1 or not lines2:
            return 0.0

        intersection = len(lines1.intersection(lines2))
        union = len(lines1.union(lines2))

        return intersection / union if union > 0 else 0.0

    def get_regression_test_suite(self) -> List[Tuple[str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT payload_hash, payload_data FROM crash_corpus
                WHERE severity IN ('high', 'critical')
                ORDER BY timestamp DESC
            ''')

            return [(row[0], row[1]) for row in cursor.fetchall()]
