# SPDX-License-Identifier: MIT
#
# Fuzz Corpus Manager for RustChain attestation fuzzing.
#
# Crash storage, Jaccard dedup, severity tracking, import/export.
# Corpus design originally by LaphoqueRC (PR #1629).

import json
import hashlib
import sqlite3
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = "fuzz_corpus.db"


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
    """SQLite-backed crash corpus with Jaccard deduplication."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_database()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
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
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_payload_hash ON crash_corpus(payload_hash)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_category ON crash_corpus(category)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_severity ON crash_corpus(severity)"
            )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_hash(payload_data: str) -> str:
        return hashlib.sha256(payload_data.encode("utf-8")).hexdigest()

    def store_crash(
        self,
        payload_data: str,
        category: PayloadCategory,
        severity: CrashSeverity,
        crash_type: str,
        stack_trace: str,
        notes: str = "",
    ) -> bool:
        h = self._compute_hash(payload_data)
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute(
                    """INSERT INTO crash_corpus
                       (payload_hash, payload_data, category, severity,
                        crash_type, stack_trace, timestamp, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (h, payload_data, category.value, severity.value,
                     crash_type, stack_trace, time.time(), notes),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def get_crash(self, payload_hash: str) -> Optional[CrashEntry]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT payload_hash, payload_data, category, severity,
                          crash_type, stack_trace, timestamp, minimized,
                          regression_tested, notes
                   FROM crash_corpus WHERE payload_hash = ?""",
                (payload_hash,),
            ).fetchone()
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
            notes=row[9],
        )

    def list_crashes(
        self,
        category: Optional[PayloadCategory] = None,
        severity: Optional[CrashSeverity] = None,
        limit: int = 100,
    ) -> List[CrashEntry]:
        query = """SELECT payload_hash, payload_data, category, severity,
                          crash_type, stack_trace, timestamp, minimized,
                          regression_tested, notes
                   FROM crash_corpus"""
        params: list = []
        conditions: list = []
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

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            CrashEntry(
                payload_hash=r[0], payload_data=r[1],
                category=PayloadCategory(r[2]), severity=CrashSeverity(r[3]),
                crash_type=r[4], stack_trace=r[5], timestamp=r[6],
                minimized=bool(r[7]), regression_tested=bool(r[8]), notes=r[9],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Bookkeeping
    # ------------------------------------------------------------------

    def mark_minimized(self, payload_hash: str, minimized_payload: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """UPDATE crash_corpus
                   SET minimized = 1, payload_data = ?,
                       notes = notes || '\nMinimized: ' || datetime('now')
                   WHERE payload_hash = ?""",
                (minimized_payload, payload_hash),
            )
            return cur.rowcount > 0

    def mark_regression_tested(self, payload_hash: str, test_result: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """UPDATE crash_corpus
                   SET regression_tested = 1,
                       notes = notes || '\nRegression tested: '
                               || ? || ' at ' || datetime('now')
                   WHERE payload_hash = ?""",
                (test_result, payload_hash),
            )
            return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM crash_corpus").fetchone()[0]
            cats = dict(
                conn.execute(
                    "SELECT category, COUNT(*) FROM crash_corpus GROUP BY category"
                ).fetchall()
            )
            sevs = dict(
                conn.execute(
                    "SELECT severity, COUNT(*) FROM crash_corpus GROUP BY severity"
                ).fetchall()
            )
            minimized = conn.execute(
                "SELECT COUNT(*) FROM crash_corpus WHERE minimized = 1"
            ).fetchone()[0]
            tested = conn.execute(
                "SELECT COUNT(*) FROM crash_corpus WHERE regression_tested = 1"
            ).fetchone()[0]
        return {
            "total_crashes": total,
            "category_breakdown": cats,
            "severity_breakdown": sevs,
            "minimized_count": minimized,
            "regression_tested_count": tested,
        }

    # ------------------------------------------------------------------
    # Import / export
    # ------------------------------------------------------------------

    def export_corpus(self, output_file: str, category: Optional[PayloadCategory] = None):
        crashes = self.list_crashes(category=category, limit=10_000)
        crash_data = []
        for crash in crashes:
            item = asdict(crash)
            item["category"] = crash.category.value
            item["severity"] = crash.severity.value
            crash_data.append(item)
        data = {
            "metadata": {
                "exported_at": time.time(),
                "total_entries": len(crashes),
                "category_filter": category.value if category else None,
            },
            "crashes": crash_data,
        }
        with open(output_file, "w") as fh:
            json.dump(data, fh, indent=2)

    def import_corpus(self, input_file: str) -> int:
        with open(input_file) as fh:
            data = json.load(fh)
        count = 0
        for entry in data.get("crashes", []):
            ok = self.store_crash(
                payload_data=entry["payload_data"],
                category=PayloadCategory(entry["category"]),
                severity=CrashSeverity(entry["severity"]),
                crash_type=entry["crash_type"],
                stack_trace=entry["stack_trace"],
                notes=entry.get("notes", ""),
            )
            if ok:
                count += 1
        return count

    # ------------------------------------------------------------------
    # Jaccard deduplication
    # ------------------------------------------------------------------

    def deduplicate_similar(self, threshold: float = 0.8) -> int:
        """Remove crashes whose stack traces exceed Jaccard similarity *threshold*."""
        crashes = self.list_crashes(limit=10_000)
        to_remove: set = set()

        for i, c1 in enumerate(crashes):
            if c1.payload_hash in to_remove:
                continue
            for c2 in crashes[i + 1:]:
                if c2.payload_hash in to_remove:
                    continue
                if (c1.crash_type == c2.crash_type
                        and self._jaccard(c1.stack_trace, c2.stack_trace) > threshold):
                    to_remove.add(c2.payload_hash)

        if to_remove:
            placeholders = ",".join(["?"] * len(to_remove))
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    f"DELETE FROM crash_corpus WHERE payload_hash IN ({placeholders})",
                    list(to_remove),
                )
        return len(to_remove)

    @staticmethod
    def _jaccard(a: str, b: str) -> float:
        sa = set(a.strip().split("\n"))
        sb = set(b.strip().split("\n"))
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    # ------------------------------------------------------------------
    # Regression suite
    # ------------------------------------------------------------------

    def get_regression_suite(self) -> List[Tuple[str, str]]:
        """Return (hash, payload_data) pairs for high/critical crashes."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT payload_hash, payload_data FROM crash_corpus
                   WHERE severity IN ('high', 'critical')
                   ORDER BY timestamp DESC"""
            ).fetchall()
        return [(r[0], r[1]) for r in rows]
