// SPDX-License-Identifier: MIT
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

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_scenarios_type ON scenarios(scenario_type)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_test_runs_scenario ON test_runs(scenario_id)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_false_positives_scenario ON false_positives(scenario_id)
            ''')

    def add_scenario(self, name: str, description: str, scenario_type: str,
                    config: Dict[str, Any], is_malicious: bool = False) -> int:
        """Add a new test scenario"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO scenarios (name, description, scenario_type, is_malicious, created_at, config_json)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, description, scenario_type, int(is_malicious),
                  int(time.time()), json.dumps(config)))
            return cursor.lastrowid

    def add_test_run(self, scenario_id: int, fleet_score: float, threshold: float,
                    penalty_triggered: bool, results: Dict[str, Any]) -> int:
        """Record a test run result"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO test_runs (scenario_id, fleet_score, penalty_triggered,
                                     threshold_used, timestamp, results_json)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (scenario_id, fleet_score, int(penalty_triggered), threshold,
                  int(time.time()), json.dumps(results)))
            return cursor.lastrowid

    def add_false_positive(self, test_run_id: int, scenario_id: int, severity: str,
                          impact_desc: str, proposed_fix: str = None) -> int:
        """Record a false positive detection"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO false_positives (test_run_id, scenario_id, severity,
                                           impact_description, proposed_fix, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (test_run_id, scenario_id, severity, impact_desc, proposed_fix, int(time.time())))
            return cursor.lastrowid

    def get_scenarios_by_type(self, scenario_type: str) -> List[Dict]:
        """Get all scenarios of a specific type"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, description, scenario_type, is_malicious,
                       created_at, config_json
                FROM scenarios
                WHERE scenario_type = ?
                ORDER BY created_at DESC
            ''', (scenario_type,))

            results = []
            for row in cursor.fetchall():
                scenario = {
                    'id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'scenario_type': row[3],
                    'is_malicious': bool(row[4]),
                    'created_at': row[5],
                    'config': json.loads(row[6])
                }
                results.append(scenario)
            return results

    def get_false_positives_report(self) -> Dict[str, Any]:
        """Generate comprehensive false positive report"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get false positives with scenario details
            cursor.execute('''
                SELECT fp.id, fp.severity, fp.impact_description, fp.proposed_fix,
                       s.name as scenario_name, s.description as scenario_desc,
                       tr.fleet_score, tr.threshold_used, tr.penalty_triggered,
                       fp.created_at
                FROM false_positives fp
                JOIN scenarios s ON fp.scenario_id = s.id
                JOIN test_runs tr ON fp.test_run_id = tr.id
                WHERE s.is_malicious = 0
                ORDER BY fp.created_at DESC
            ''')

            false_positives = []
            for row in cursor.fetchall():
                fp = {
                    'id': row[0],
                    'severity': row[1],
                    'impact_description': row[2],
                    'proposed_fix': row[3],
                    'scenario_name': row[4],
                    'scenario_description': row[5],
                    'fleet_score': row[6],
                    'threshold_used': row[7],
                    'penalty_triggered': bool(row[8]),
                    'created_at': datetime.fromtimestamp(row[9]).isoformat()
                }
                false_positives.append(fp)

            # Get summary statistics
            cursor.execute('''
                SELECT COUNT(*) as total_fps,
                       COUNT(CASE WHEN severity = 'HIGH' THEN 1 END) as high_severity,
                       COUNT(CASE WHEN severity = 'MEDIUM' THEN 1 END) as medium_severity,
                       COUNT(CASE WHEN severity = 'LOW' THEN 1 END) as low_severity
                FROM false_positives fp
                JOIN scenarios s ON fp.scenario_id = s.id
                WHERE s.is_malicious = 0
            ''')

            stats_row = cursor.fetchone()
            stats = {
                'total_false_positives': stats_row[0],
                'high_severity': stats_row[1],
                'medium_severity': stats_row[2],
                'low_severity': stats_row[3]
            }

            return {
                'report_generated_at': datetime.now().isoformat(),
                'summary_statistics': stats,
                'false_positives': false_positives
            }

    def get_threshold_analysis(self) -> Dict[str, Any]:
        """Analyze how different thresholds affect false positive rates"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT tr.threshold_used, tr.fleet_score, s.is_malicious,
                       CASE WHEN tr.fleet_score >= tr.threshold_used THEN 1 ELSE 0 END as would_penalize
                FROM test_runs tr
                JOIN scenarios s ON tr.scenario_id = s.id
                ORDER BY tr.threshold_used, tr.fleet_score
            ''')

            threshold_data = {}
            for row in cursor.fetchall():
                threshold = row[0]
                fleet_score = row[1]
                is_malicious = bool(row[2])
                would_penalize = bool(row[3])

                if threshold not in threshold_data:
                    threshold_data[threshold] = {
                        'legitimate_penalized': 0,
                        'legitimate_total': 0,
                        'malicious_caught': 0,
                        'malicious_total': 0
                    }

                if is_malicious:
                    threshold_data[threshold]['malicious_total'] += 1
                    if would_penalize:
                        threshold_data[threshold]['malicious_caught'] += 1
                else:
                    threshold_data[threshold]['legitimate_total'] += 1
                    if would_penalize:
                        threshold_data[threshold]['legitimate_penalized'] += 1

            # Calculate rates
            analysis = {}
            for threshold, data in threshold_data.items():
                false_positive_rate = 0
                true_positive_rate = 0

                if data['legitimate_total'] > 0:
                    false_positive_rate = data['legitimate_penalized'] / data['legitimate_total']

                if data['malicious_total'] > 0:
                    true_positive_rate = data['malicious_caught'] / data['malicious_total']

                analysis[threshold] = {
                    'false_positive_rate': false_positive_rate,
                    'true_positive_rate': true_positive_rate,
                    'legitimate_scenarios_tested': data['legitimate_total'],
                    'malicious_scenarios_tested': data['malicious_total']
                }

            return analysis

    def create_default_scenarios(self):
        """Create realistic test scenarios for fleet detection testing"""
        scenarios = [
            {
                'name': 'Corporate Mining Farm',
                'description': 'Large legitimate mining operation with 500+ miners in datacenter',
                'scenario_type': 'legitimate_large_scale',
                'is_malicious': False,
                'config': {
                    'miner_count': 500,
                    'location_variance': 'single_datacenter',
                    'timing_patterns': 'scheduled_maintenance',
                    'hardware_diversity': 'uniform_asics',
                    'network_topology': 'shared_gateway'
                }
            },
            {
                'name': 'Home Mining Pool',
                'description': 'Residential miners using same pool configuration',
                'scenario_type': 'legitimate_distributed',
                'is_malicious': False,
                'config': {
                    'miner_count': 50,
                    'location_variance': 'residential_distributed',
                    'timing_patterns': 'power_cost_optimization',
                    'hardware_diversity': 'mixed_consumer_gear',
                    'network_topology': 'residential_isps'
                }
            },
            {
                'name': 'University Research Cluster',
                'description': 'Academic institution with synchronized mining for research',
                'scenario_type': 'legitimate_institutional',
                'is_malicious': False,
                'config': {
                    'miner_count': 100,
                    'location_variance': 'campus_network',
                    'timing_patterns': 'research_schedule_aligned',
                    'hardware_diversity': 'research_grade_mixed',
                    'network_topology': 'institutional_gateway'
                }
            },
            {
                'name': 'Botnet Attack Simulation',
                'description': 'Malicious coordinated mining from compromised devices',
                'scenario_type': 'malicious_coordinated',
                'is_malicious': True,
                'config': {
                    'miner_count': 1000,
                    'location_variance': 'global_distributed',
                    'timing_patterns': 'synchronized_attacks',
                    'hardware_diversity': 'consumer_devices_varied',
                    'network_topology': 'random_residential'
                }
            }
        ]

        for scenario in scenarios:
            self.add_scenario(
                name=scenario['name'],
                description=scenario['description'],
                scenario_type=scenario['scenario_type'],
                config=scenario['config'],
                is_malicious=scenario['is_malicious']
            )

def init_fleet_scenarios_db():
    """Initialize database with default test scenarios"""
    db = FleetScenariosDB()

    # Check if scenarios already exist
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM scenarios')
        if cursor.fetchone()[0] == 0:
            db.create_default_scenarios()
            print("Created default fleet detection test scenarios")

    return db

if __name__ == "__main__":
    db = init_fleet_scenarios_db()
    print("Fleet scenarios database initialized")
