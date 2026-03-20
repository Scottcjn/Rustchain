# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

DB_PATH = "fleet_scenarios.db"

class FleetScenariosDB:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scenarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    scenario_type TEXT NOT NULL,
                    is_malicious INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    config_json TEXT NOT NULL
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS test_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scenario_id INTEGER NOT NULL,
                    fleet_score REAL NOT NULL,
                    penalty_triggered INTEGER NOT NULL DEFAULT 0,
                    threshold_used REAL NOT NULL,
                    timestamp INTEGER NOT NULL,
                    results_json TEXT NOT NULL,
                    FOREIGN KEY (scenario_id) REFERENCES scenarios (id)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS false_positives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_run_id INTEGER NOT NULL,
                    scenario_id INTEGER NOT NULL,
                    severity TEXT NOT NULL,
                    impact_description TEXT NOT NULL,
                    proposed_fix TEXT,
                    verified INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (test_run_id) REFERENCES test_runs (id),
                    FOREIGN KEY (scenario_id) REFERENCES scenarios (id)
                )
            ''')

            conn.commit()

    def add_scenario(self, name: str, description: str, scenario_type: str,
                    is_malicious: bool, config: Dict[str, Any]) -> int:
        """Add a new test scenario"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                INSERT INTO scenarios (name, description, scenario_type, is_malicious, created_at, config_json)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, description, scenario_type, int(is_malicious), int(time.time()), json.dumps(config)))
            return cursor.lastrowid

    def add_test_run(self, scenario_id: int, fleet_score: float, penalty_triggered: bool,
                    threshold_used: float, results: Dict[str, Any]) -> int:
        """Record a test run result"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                INSERT INTO test_runs (scenario_id, fleet_score, penalty_triggered, threshold_used, timestamp, results_json)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (scenario_id, fleet_score, int(penalty_triggered), threshold_used, int(time.time()), json.dumps(results)))
            return cursor.lastrowid

    def add_false_positive(self, test_run_id: int, scenario_id: int, severity: str,
                          impact_description: str, proposed_fix: Optional[str] = None) -> int:
        """Record a false positive detection"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                INSERT INTO false_positives (test_run_id, scenario_id, severity, impact_description, proposed_fix, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (test_run_id, scenario_id, severity, impact_description, proposed_fix, int(time.time())))
            return cursor.lastrowid

    def get_false_positives_by_severity(self, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get false positives, optionally filtered by severity"""
        with sqlite3.connect(DB_PATH) as conn:
            if severity:
                cursor = conn.execute('''
                    SELECT fp.*, s.name as scenario_name, s.scenario_type
                    FROM false_positives fp
                    JOIN scenarios s ON fp.scenario_id = s.id
                    WHERE fp.severity = ?
                    ORDER BY fp.created_at DESC
                ''', (severity,))
            else:
                cursor = conn.execute('''
                    SELECT fp.*, s.name as scenario_name, s.scenario_type
                    FROM false_positives fp
                    JOIN scenarios s ON fp.scenario_id = s.id
                    ORDER BY fp.created_at DESC
                ''')

            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_scenario_stats(self) -> Dict[str, Any]:
        """Get comprehensive scenario testing statistics"""
        with sqlite3.connect(DB_PATH) as conn:
            # Total scenarios by type
            cursor = conn.execute('''
                SELECT scenario_type, COUNT(*) as count
                FROM scenarios
                GROUP BY scenario_type
            ''')
            scenario_counts = dict(cursor.fetchall())

            # False positive rate by scenario type
            cursor = conn.execute('''
                SELECT s.scenario_type,
                       COUNT(DISTINCT tr.id) as total_runs,
                       COUNT(DISTINCT fp.id) as false_positives
                FROM scenarios s
                LEFT JOIN test_runs tr ON s.id = tr.scenario_id
                LEFT JOIN false_positives fp ON tr.id = fp.test_run_id
                WHERE s.is_malicious = 0
                GROUP BY s.scenario_type
            ''')

            fp_rates = {}
            for scenario_type, total_runs, fps in cursor.fetchall():
                if total_runs > 0:
                    fp_rates[scenario_type] = fps / total_runs
                else:
                    fp_rates[scenario_type] = 0.0

            return {
                'scenario_counts': scenario_counts,
                'false_positive_rates': fp_rates,
                'total_scenarios': sum(scenario_counts.values())
            }
