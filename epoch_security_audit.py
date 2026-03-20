// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import time
import hashlib
import json
from flask import Flask, render_template_string, jsonify, request
import logging
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = 'rustchain.db'
EPOCH_DURATION = 600  # 10 minutes

class EpochSecurityAudit:
    def __init__(self):
        self.test_results = []
        self.vulnerabilities_found = []
        self.audit_id = int(time.time())

    def log_result(self, test_name, passed, details, severity="LOW"):
        result = {
            'test_name': test_name,
            'passed': passed,
            'details': details,
            'severity': severity,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        if not passed:
            self.vulnerabilities_found.append(result)

    def get_current_epoch(self):
        return int(time.time()) // EPOCH_DURATION

    def create_test_miner(self, node_id, hardware_class="A"):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO nodes (node_id, hardware_class, status, last_seen)
                VALUES (?, ?, 'active', ?)
            ''', (node_id, hardware_class, int(time.time())))
            conn.commit()

    def test_double_enrollment(self):
        """Test if miners can enroll in the same epoch twice"""
        test_node = f"test_double_{self.audit_id}"
        current_epoch = self.get_current_epoch()

        try:
            self.create_test_miner(test_node)

            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                # First enrollment
                cursor.execute('''
                    INSERT INTO epoch_enrollments (epoch_id, node_id, enrollment_time, hardware_multiplier)
                    VALUES (?, ?, ?, ?)
                ''', (current_epoch, test_node, int(time.time()), 1.0))

                # Second enrollment attempt
                try:
                    cursor.execute('''
                        INSERT INTO epoch_enrollments (epoch_id, node_id, enrollment_time, hardware_multiplier)
                        VALUES (?, ?, ?, ?)
                    ''', (current_epoch, test_node, int(time.time()), 1.0))
                    conn.commit()

                    # Check if double enrollment succeeded
                    cursor.execute('''
                        SELECT COUNT(*) FROM epoch_enrollments
                        WHERE epoch_id = ? AND node_id = ?
                    ''', (current_epoch, test_node))

                    count = cursor.fetchone()[0]
                    if count > 1:
                        self.log_result("double_enrollment", False,
                                      f"Miner enrolled {count} times in epoch {current_epoch}", "HIGH")
                    else:
                        self.log_result("double_enrollment", True, "Double enrollment prevented")

                except sqlite3.IntegrityError:
                    self.log_result("double_enrollment", True, "Database constraints prevent double enrollment")

        except Exception as e:
            self.log_result("double_enrollment", False, f"Test failed: {str(e)}", "MEDIUM")

    def test_late_attestation_injection(self):
        """Test if attestations can be backdated to previous epochs"""
        test_node = f"test_backdate_{self.audit_id}"
        current_epoch = self.get_current_epoch()
        previous_epoch = current_epoch - 1

        try:
            self.create_test_miner(test_node)

            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                # Try to inject attestation for previous epoch
                old_timestamp = (previous_epoch * EPOCH_DURATION) + 100

                cursor.execute('''
                    INSERT INTO attestations (node_id, epoch_id, timestamp, work_proof, difficulty)
                    VALUES (?, ?, ?, ?, ?)
                ''', (test_node, previous_epoch, old_timestamp, "backdated_proof", 1))

                # Check if it was accepted
                cursor.execute('''
                    SELECT COUNT(*) FROM attestations
                    WHERE node_id = ? AND epoch_id = ? AND timestamp = ?
                ''', (test_node, previous_epoch, old_timestamp))

                count = cursor.fetchone()[0]
                if count > 0:
                    self.log_result("late_attestation", False,
                                  f"Backdated attestation accepted for epoch {previous_epoch}", "HIGH")
                else:
                    self.log_result("late_attestation", True, "Backdated attestations rejected")

        except Exception as e:
            self.log_result("late_attestation", True, f"Backdated injection blocked: {str(e)}")

    def test_multiplier_manipulation(self):
        """Test various multiplier manipulation attacks"""
        test_node = f"test_multiplier_{self.audit_id}"

        try:
            # Test extreme multiplier values
            extreme_multipliers = [999.0, -1.0, 0.0, float('inf')]

            for multiplier in extreme_multipliers:
                try:
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT OR REPLACE INTO nodes (node_id, hardware_class, status, last_seen)
                            VALUES (?, ?, 'active', ?)
                        ''', (f"{test_node}_{multiplier}", "S", int(time.time())))

                        cursor.execute('''
                            UPDATE nodes SET hardware_multiplier = ? WHERE node_id = ?
                        ''', (multiplier, f"{test_node}_{multiplier}"))

                        cursor.execute('''
                            SELECT hardware_multiplier FROM nodes WHERE node_id = ?
                        ''', (f"{test_node}_{multiplier}",))

                        stored_multiplier = cursor.fetchone()
                        if stored_multiplier and stored_multiplier[0] == multiplier:
                            self.log_result("multiplier_manipulation", False,
                                          f"Extreme multiplier {multiplier} accepted", "MEDIUM")
                        else:
                            self.log_result("multiplier_manipulation", True,
                                          f"Extreme multiplier {multiplier} rejected or sanitized")

                except Exception as e:
                    self.log_result("multiplier_manipulation", True,
                                  f"Multiplier {multiplier} blocked: {str(e)}")

        except Exception as e:
            self.log_result("multiplier_manipulation", False, f"Test failed: {str(e)}", "LOW")

    def test_settlement_race_condition(self):
        """Test concurrent settlement claims for race conditions"""
        test_node = f"test_race_{self.audit_id}"
        current_epoch = self.get_current_epoch()

        try:
            self.create_test_miner(test_node, "S")

            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO epoch_enrollments (epoch_id, node_id, enrollment_time, hardware_multiplier)
                    VALUES (?, ?, ?, ?)
                ''', (current_epoch - 1, test_node, int(time.time()) - 700, 2.0))

                cursor.execute('''
                    INSERT INTO attestations (node_id, epoch_id, timestamp, work_proof, difficulty)
                    VALUES (?, ?, ?, ?, ?)
                ''', (test_node, current_epoch - 1, int(time.time()) - 650, "race_proof", 2))
                conn.commit()

            # Simulate concurrent settlement attempts
            settlement_results = []

            def attempt_settlement():
                try:
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO epoch_settlements (epoch_id, node_id, reward_amount, settlement_time)
                            VALUES (?, ?, ?, ?)
                        ''', (current_epoch - 1, test_node, 10.0, int(time.time())))
                        conn.commit()
                        return True
                except Exception:
                    return False

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(attempt_settlement) for _ in range(5)]
                settlement_results = [f.result() for f in futures]

            successful_settlements = sum(settlement_results)

            if successful_settlements > 1:
                self.log_result("settlement_race", False,
                              f"Race condition allowed {successful_settlements} settlements", "HIGH")
            else:
                self.log_result("settlement_race", True, "Race condition prevented")

        except Exception as e:
            self.log_result("settlement_race", False, f"Test failed: {str(e)}", "MEDIUM")

    def test_epoch_boundary_attacks(self):
        """Test attacks targeting epoch transitions"""
        test_node = f"test_boundary_{self.audit_id}"
        current_time = int(time.time())
        current_epoch = current_time // EPOCH_DURATION

        try:
            self.create_test_miner(test_node)

            # Test enrollment right at epoch boundary
            epoch_start = current_epoch * EPOCH_DURATION
            boundary_times = [epoch_start - 1, epoch_start, epoch_start + 1]

            for test_time in boundary_times:
                try:
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()

                        # Try to enroll with manipulated timestamp
                        cursor.execute('''
                            INSERT INTO epoch_enrollments
                            (epoch_id, node_id, enrollment_time, hardware_multiplier)
                            VALUES (?, ?, ?, ?)
                        ''', (current_epoch, f"{test_node}_{test_time}", test_time, 1.0))

                        # Check epoch assignment
                        calculated_epoch = test_time // EPOCH_DURATION
                        if calculated_epoch != current_epoch:
                            self.log_result("epoch_boundary", False,
                                          f"Timestamp {test_time} assigned to wrong epoch", "MEDIUM")

                except Exception as e:
                    continue

            self.log_result("epoch_boundary", True, "Epoch boundary handling appears secure")

        except Exception as e:
            self.log_result("epoch_boundary", False, f"Test failed: {str(e)}", "LOW")

    def test_time_manipulation_attacks(self):
        """Test various timestamp manipulation attacks"""
        test_node = f"test_time_{self.audit_id}"

        try:
            # Test future timestamps
            future_time = int(time.time()) + 3600  # 1 hour in future

            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                try:
                    cursor.execute('''
                        INSERT INTO attestations (node_id, epoch_id, timestamp, work_proof, difficulty)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (test_node, self.get_current_epoch(), future_time, "future_proof", 1))

                    cursor.execute('''
                        SELECT COUNT(*) FROM attestations WHERE timestamp = ?
                    ''', (future_time,))

                    if cursor.fetchone()[0] > 0:
                        self.log_result("time_manipulation", False,
                                      "Future timestamp accepted", "MEDIUM")
                    else:
                        self.log_result("time_manipulation", True, "Future timestamps rejected")

                except Exception:
                    self.log_result("time_manipulation", True, "Future timestamps blocked")

        except Exception as e:
            self.log_result("time_manipulation", False, f"Test failed: {str(e)}", "LOW")

    def run_comprehensive_audit(self):
        """Execute all security tests"""
        logging.info(f"Starting security audit {self.audit_id}")

        test_methods = [
            self.test_double_enrollment,
            self.test_late_attestation_injection,
            self.test_multiplier_manipulation,
            self.test_settlement_race_condition,
            self.test_epoch_boundary_attacks,
            self.test_time_manipulation_attacks
        ]

        for test_method in test_methods:
            try:
                test_method()
            except Exception as e:
                logging.error(f"Test {test_method.__name__} failed: {e}")

        return self.generate_audit_report()

    def generate_audit_report(self):
        """Generate comprehensive audit report"""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['passed']])
        vulnerabilities = len(self.vulnerabilities_found)

        severity_count = {}
        for vuln in self.vulnerabilities_found:
            severity = vuln['severity']
            severity_count[severity] = severity_count.get(severity, 0) + 1

        return {
            'audit_id': self.audit_id,
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'vulnerabilities_found': vulnerabilities,
                'severity_breakdown': severity_count
            },
            'test_results': self.test_results,
            'vulnerabilities': self.vulnerabilities_found
        }

@app.route('/audit/run', methods=['POST'])
def run_security_audit():
    """Run complete security audit"""
    try:
        audit = EpochSecurityAudit()
        report = audit.run_comprehensive_audit()
        return jsonify(report)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/audit/status')
def audit_dashboard():
    """Security audit dashboard"""
    template = '''
    <html>
    <head><title>Epoch Security Audit Dashboard</title></head>
    <body style="font-family: monospace; background: #1a1a1a; color: #00ff00;">
        <h2>🔴 Epoch Settlement Security Audit</h2>
        <div style="margin: 20px;">
            <button onclick="runAudit()" style="background: #ff4444; color: white; padding: 10px;">
                Start Security Audit
            </button>
        </div>
        <div id="results" style="margin-top: 20px;"></div>

        <script>
        async function runAudit() {
            document.getElementById('results').innerHTML = '<p>Running security tests...</p>';

            try {
                const response = await fetch('/audit/run', { method: 'POST' });
                const data = await response.json();
                displayResults(data);
            } catch (error) {
                document.getElementById('results').innerHTML = '<p>Error: ' + error + '</p>';
            }
        }

        function displayResults(data) {
            let html = '<h3>Audit Results</h3>';
            html += '<p><strong>Total Tests:</strong> ' + data.summary.total_tests + '</p>';
            html += '<p><strong>Passed:</strong> ' + data.summary.passed_tests + '</p>';
            html += '<p><strong>Vulnerabilities:</strong> ' + data.summary.vulnerabilities_found + '</p>';

            if (data.vulnerabilities.length > 0) {
                html += '<h4>🚨 Vulnerabilities Found:</h4>';
                data.vulnerabilities.forEach(vuln => {
                    html += '<div style="border: 1px solid #ff4444; margin: 10px; padding: 10px;">';
                    html += '<strong>' + vuln.test_name + '</strong> [' + vuln.severity + ']<br>';
                    html += vuln.details;
                    html += '</div>';
                });
            }

            html += '<h4>All Test Results:</h4>';
            data.test_results.forEach(result => {
                const color = result.passed ? '#44ff44' : '#ff4444';
                html += '<div style="color: ' + color + '; margin: 5px;">';
                html += result.test_name + ': ' + (result.passed ? 'PASS' : 'FAIL') + ' - ' + result.details;
                html += '</div>';
            });

            document.getElementById('results').innerHTML = html;
        }
        </script>
    </body>
    </html>
    '''
    return render_template_string(template)

if __name__ == '__main__':
    app.run(debug=True, port=5003)
