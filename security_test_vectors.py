// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
from typing import Dict, List, Any

DB_PATH = "blockchain.db"

class SecurityTestVectors:
    """Security test vector database for systematic vulnerability testing"""

    def __init__(self):
        self.init_test_vectors_db()
        self.load_attack_patterns()

    def init_test_vectors_db(self):
        """Initialize security test vectors database"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS security_test_vectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    description TEXT,
                    severity TEXT DEFAULT 'medium',
                    expected_result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vector_id INTEGER,
                    endpoint TEXT,
                    status_code INTEGER,
                    response_body TEXT,
                    vulnerability_found BOOLEAN DEFAULT 0,
                    notes TEXT,
                    tested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vector_id) REFERENCES security_test_vectors (id)
                )
            """)

            conn.commit()

    def load_attack_patterns(self):
        """Load comprehensive attack patterns into database"""
        attack_vectors = [
            # SQL Injection Vectors
            {
                "category": "sql_injection",
                "name": "union_select_bypass",
                "payload": "' UNION SELECT username, password FROM admin_keys --",
                "description": "UNION-based SQL injection to extract admin credentials",
                "severity": "critical"
            },
            {
                "category": "sql_injection",
                "name": "balance_manipulation",
                "payload": "'; UPDATE wallets SET balance = 999999 WHERE address = 'attacker_addr' --",
                "description": "Direct balance manipulation via SQL injection",
                "severity": "critical"
            },
            {
                "category": "sql_injection",
                "name": "ledger_bypass",
                "payload": "'; DELETE FROM pending_ledger WHERE wallet_from = 'target_wallet' --",
                "description": "Bypass pending ledger system by deleting entries",
                "severity": "high"
            },

            # Authentication Bypass
            {
                "category": "auth_bypass",
                "name": "admin_key_bruteforce",
                "payload": "admin123",
                "description": "Common admin key patterns for brute force",
                "severity": "high"
            },
            {
                "category": "auth_bypass",
                "name": "empty_admin_key",
                "payload": "",
                "description": "Empty admin key bypass attempt",
                "severity": "medium"
            },
            {
                "category": "auth_bypass",
                "name": "null_admin_key",
                "payload": "null",
                "description": "Null admin key bypass",
                "severity": "medium"
            },

            # Transfer Manipulation
            {
                "category": "transfer_bypass",
                "name": "negative_amount",
                "payload": json.dumps({"from": "victim", "to": "attacker", "amount": -1000}),
                "description": "Negative transfer amounts to reverse transactions",
                "severity": "high"
            },
            {
                "category": "transfer_bypass",
                "name": "zero_amount_spam",
                "payload": json.dumps({"from": "wallet1", "to": "wallet2", "amount": 0}),
                "description": "Zero amount transfers to spam system",
                "severity": "low"
            },
            {
                "category": "transfer_bypass",
                "name": "self_transfer_loop",
                "payload": json.dumps({"from": "wallet1", "to": "wallet1", "amount": 1000}),
                "description": "Self-transfer to create money from nothing",
                "severity": "critical"
            },

            # Race Conditions
            {
                "category": "race_condition",
                "name": "double_spend",
                "payload": json.dumps({"concurrent_transfers": 50, "same_wallet": True}),
                "description": "Rapid concurrent transfers from same wallet",
                "severity": "critical"
            },
            {
                "category": "race_condition",
                "name": "pending_ledger_race",
                "payload": json.dumps({"exploit_pending_window": True}),
                "description": "Race condition during pending ledger commit",
                "severity": "high"
            },

            # Input Validation Bypass
            {
                "category": "input_validation",
                "name": "oversized_amount",
                "payload": json.dumps({"amount": 99999999999999999999999999999}),
                "description": "Integer overflow in amount field",
                "severity": "high"
            },
            {
                "category": "input_validation",
                "name": "malicious_wallet_address",
                "payload": "<script>alert('xss')</script>",
                "description": "XSS payload in wallet address",
                "severity": "medium"
            },
            {
                "category": "input_validation",
                "name": "path_traversal_wallet",
                "payload": "../../../etc/passwd",
                "description": "Path traversal in wallet address",
                "severity": "medium"
            },

            # Endpoint Fuzzing
            {
                "category": "endpoint_fuzzing",
                "name": "malformed_json",
                "payload": '{"from":"wallet1","to":"wallet2","amount":}',
                "description": "Malformed JSON to trigger parser errors",
                "severity": "low"
            },
            {
                "category": "endpoint_fuzzing",
                "name": "extra_parameters",
                "payload": json.dumps({"from": "w1", "to": "w2", "amount": 100, "admin": True}),
                "description": "Extra parameters to bypass validation",
                "severity": "medium"
            },

            # Cryptographic Attacks
            {
                "category": "crypto_attack",
                "name": "weak_hash_collision",
                "payload": "collision_attempt_string_1",
                "description": "Attempt to create hash collisions",
                "severity": "high"
            },
            {
                "category": "crypto_attack",
                "name": "timing_attack_vector",
                "payload": json.dumps({"measure_response_time": True}),
                "description": "Timing attack to extract sensitive data",
                "severity": "medium"
            }
        ]

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            for vector in attack_vectors:
                cursor.execute("""
                    INSERT OR IGNORE INTO security_test_vectors
                    (category, name, payload, description, severity)
                    VALUES (?, ?, ?, ?, ?)
                """, (vector["category"], vector["name"], vector["payload"],
                     vector["description"], vector["severity"]))

            conn.commit()

    def get_vectors_by_category(self, category: str) -> List[Dict]:
        """Get all test vectors for a specific category"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM security_test_vectors WHERE category = ?
                ORDER BY severity DESC, name ASC
            """, (category,))

            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_critical_vectors(self) -> List[Dict]:
        """Get all critical severity test vectors"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM security_test_vectors
                WHERE severity = 'critical'
                ORDER BY category, name
            """)

            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def record_test_result(self, vector_id: int, endpoint: str,
                          status_code: int, response_body: str,
                          vulnerability_found: bool = False, notes: str = ""):
        """Record results of a security test"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO test_results
                (vector_id, endpoint, status_code, response_body,
                 vulnerability_found, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (vector_id, endpoint, status_code, response_body,
                  vulnerability_found, notes))
            conn.commit()

    def get_vulnerability_summary(self) -> Dict[str, Any]:
        """Generate summary of vulnerabilities found during testing"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Total vulnerabilities by severity
            cursor.execute("""
                SELECT sv.severity, COUNT(*) as count
                FROM test_results tr
                JOIN security_test_vectors sv ON tr.vector_id = sv.id
                WHERE tr.vulnerability_found = 1
                GROUP BY sv.severity
            """)
            severity_counts = dict(cursor.fetchall())

            # Vulnerabilities by category
            cursor.execute("""
                SELECT sv.category, COUNT(*) as count
                FROM test_results tr
                JOIN security_test_vectors sv ON tr.vector_id = sv.id
                WHERE tr.vulnerability_found = 1
                GROUP BY sv.category
            """)
            category_counts = dict(cursor.fetchall())

            # Most vulnerable endpoints
            cursor.execute("""
                SELECT endpoint, COUNT(*) as vuln_count
                FROM test_results
                WHERE vulnerability_found = 1
                GROUP BY endpoint
                ORDER BY vuln_count DESC
                LIMIT 5
            """)
            vulnerable_endpoints = cursor.fetchall()

            return {
                "severity_breakdown": severity_counts,
                "category_breakdown": category_counts,
                "vulnerable_endpoints": vulnerable_endpoints,
                "total_vulnerabilities": sum(severity_counts.values())
            }

    def export_test_vectors_json(self) -> str:
        """Export all test vectors as JSON for external tools"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM security_test_vectors")

            columns = [col[0] for col in cursor.description]
            vectors = [dict(zip(columns, row)) for row in cursor.fetchall()]

            return json.dumps(vectors, indent=2)

if __name__ == "__main__":
    # Initialize and load security test vectors
    vectors = SecurityTestVectors()
    print("Security test vector database initialized")

    # Display critical attack vectors
    critical = vectors.get_critical_vectors()
    print(f"\nLoaded {len(critical)} critical attack vectors:")

    for vector in critical:
        print(f"- {vector['category']}: {vector['name']}")
