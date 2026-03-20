// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import time
import hashlib
import threading
import json
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

DB_PATH = 'rustchain_v2.db'

class SecurityTestHarness:
    def __init__(self):
        self.test_results = []
        self.logger = self._setup_logging()
        self.attack_scenarios = {
            'double_enrollment': self.test_double_enrollment,
            'late_attestation': self.test_late_attestation_injection,
            'multiplier_manipulation': self.test_multiplier_manipulation,
            'settlement_race': self.test_settlement_race_condition,
            'epoch_boundary': self.test_epoch_boundary_attacks
        }

    def _setup_logging(self):
        logger = logging.getLogger('security_harness')
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    @contextmanager
    def db_connection(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def create_test_environment(self):
        """Setup isolated test data"""
        with self.db_connection() as conn:
            # Create test miners
            test_miners = [
                ('test_miner_1', 'test_wallet_1', 1.5),
                ('test_miner_2', 'test_wallet_2', 2.0),
                ('test_miner_3', 'test_wallet_3', 1.0)
            ]

            for miner_id, wallet, multiplier in test_miners:
                conn.execute('''
                    INSERT OR REPLACE INTO miners (miner_id, wallet_address, hardware_multiplier, is_active)
                    VALUES (?, ?, ?, 1)
                ''', (miner_id, wallet, multiplier))

            conn.commit()

    def cleanup_test_environment(self):
        """Remove test data"""
        with self.db_connection() as conn:
            conn.execute("DELETE FROM miners WHERE miner_id LIKE 'test_%'")
            conn.execute("DELETE FROM attestations WHERE miner_id LIKE 'test_%'")
            conn.execute("DELETE FROM rewards WHERE miner_id LIKE 'test_%'")
            conn.commit()

    def test_double_enrollment(self) -> Dict[str, Any]:
        """Test if miner can enroll in same epoch multiple times"""
        self.logger.info("Testing double enrollment attack...")

        result = {
            'attack': 'double_enrollment',
            'success': False,
            'details': [],
            'vulnerability_level': 'LOW'
        }

        try:
            current_epoch = int(time.time() // 600)
            miner_id = 'test_miner_1'

            with self.db_connection() as conn:
                # First enrollment
                first_enrollment = conn.execute('''
                    INSERT INTO attestations (miner_id, epoch, attestation_hash, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (miner_id, current_epoch, hashlib.sha256(f"{miner_id}_{current_epoch}_1".encode()).hexdigest(), time.time()))

                # Attempt second enrollment
                try:
                    second_enrollment = conn.execute('''
                        INSERT INTO attestations (miner_id, epoch, attestation_hash, timestamp)
                        VALUES (?, ?, ?, ?)
                    ''', (miner_id, current_epoch, hashlib.sha256(f"{miner_id}_{current_epoch}_2".encode()).hexdigest(), time.time()))
                    conn.commit()

                    # Check if both exist
                    count = conn.execute(
                        'SELECT COUNT(*) FROM attestations WHERE miner_id = ? AND epoch = ?',
                        (miner_id, current_epoch)
                    ).fetchone()[0]

                    if count > 1:
                        result['success'] = True
                        result['vulnerability_level'] = 'HIGH'
                        result['details'].append(f"Miner enrolled {count} times in epoch {current_epoch}")

                except sqlite3.IntegrityError:
                    result['details'].append("Double enrollment blocked by database constraints")

        except Exception as e:
            result['details'].append(f"Test error: {str(e)}")

        return result

    def test_late_attestation_injection(self) -> Dict[str, Any]:
        """Test backdating attestations to previous epochs"""
        self.logger.info("Testing late attestation injection...")

        result = {
            'attack': 'late_attestation_injection',
            'success': False,
            'details': [],
            'vulnerability_level': 'LOW'
        }

        try:
            current_epoch = int(time.time() // 600)
            past_epoch = current_epoch - 2
            miner_id = 'test_miner_2'

            with self.db_connection() as conn:
                # Try to inject attestation for past epoch
                past_timestamp = (past_epoch + 1) * 600 - 60  # 1 minute before epoch end

                conn.execute('''
                    INSERT OR IGNORE INTO attestations (miner_id, epoch, attestation_hash, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (miner_id, past_epoch, hashlib.sha256(f"{miner_id}_{past_epoch}".encode()).hexdigest(), past_timestamp))

                # Check if settlement already processed
                settled = conn.execute('''
                    SELECT COUNT(*) FROM rewards WHERE epoch = ?
                ''', (past_epoch,)).fetchone()[0]

                if settled > 0:
                    result['details'].append(f"Epoch {past_epoch} already settled, injection blocked")
                else:
                    result['success'] = True
                    result['vulnerability_level'] = 'MEDIUM'
                    result['details'].append(f"Successfully injected attestation for past epoch {past_epoch}")

                conn.commit()

        except Exception as e:
            result['details'].append(f"Test error: {str(e)}")

        return result

    def test_multiplier_manipulation(self) -> Dict[str, Any]:
        """Test hardware multiplier manipulation beyond device spoofing"""
        self.logger.info("Testing multiplier manipulation...")

        result = {
            'attack': 'multiplier_manipulation',
            'success': False,
            'details': [],
            'vulnerability_level': 'LOW'
        }

        try:
            miner_id = 'test_miner_3'

            with self.db_connection() as conn:
                # Get original multiplier
                original = conn.execute(
                    'SELECT hardware_multiplier FROM miners WHERE miner_id = ?',
                    (miner_id,)
                ).fetchone()

                if original:
                    original_mult = original[0]

                    # Attempt direct database manipulation
                    conn.execute('''
                        UPDATE miners SET hardware_multiplier = ? WHERE miner_id = ?
                    ''', (10.0, miner_id))

                    # Check if change persisted
                    new_mult = conn.execute(
                        'SELECT hardware_multiplier FROM miners WHERE miner_id = ?',
                        (miner_id,)
                    ).fetchone()[0]

                    if new_mult != original_mult:
                        result['success'] = True
                        result['vulnerability_level'] = 'HIGH'
                        result['details'].append(f"Multiplier changed from {original_mult} to {new_mult}")

                        # Restore original
                        conn.execute('''
                            UPDATE miners SET hardware_multiplier = ? WHERE miner_id = ?
                        ''', (original_mult, miner_id))

                    conn.commit()

        except Exception as e:
            result['details'].append(f"Test error: {str(e)}")

        return result

    def test_settlement_race_condition(self) -> Dict[str, Any]:
        """Test concurrent reward claims during settlement"""
        self.logger.info("Testing settlement race conditions...")

        result = {
            'attack': 'settlement_race_condition',
            'success': False,
            'details': [],
            'vulnerability_level': 'LOW'
        }

        def claim_reward(miner_id, epoch):
            try:
                with self.db_connection() as conn:
                    # Simulate reward claim
                    existing = conn.execute(
                        'SELECT COUNT(*) FROM rewards WHERE miner_id = ? AND epoch = ?',
                        (miner_id, epoch)
                    ).fetchone()[0]

                    if existing == 0:
                        conn.execute('''
                            INSERT INTO rewards (miner_id, epoch, amount, timestamp)
                            VALUES (?, ?, ?, ?)
                        ''', (miner_id, epoch, 10.0, time.time()))
                        conn.commit()
                        return True
                return False
            except Exception:
                return False

        try:
            test_epoch = int(time.time() // 600) - 1
            miner_id = 'test_miner_1'

            # Concurrent claims
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(claim_reward, miner_id, test_epoch) for _ in range(5)]
                successful_claims = sum(1 for future in as_completed(futures) if future.result())

            if successful_claims > 1:
                result['success'] = True
                result['vulnerability_level'] = 'HIGH'
                result['details'].append(f"Multiple claims succeeded: {successful_claims}")
            else:
                result['details'].append("Race condition protection working")

        except Exception as e:
            result['details'].append(f"Test error: {str(e)}")

        return result

    def test_epoch_boundary_attacks(self) -> Dict[str, Any]:
        """Test attacks at epoch transitions"""
        self.logger.info("Testing epoch boundary attacks...")

        result = {
            'attack': 'epoch_boundary_attacks',
            'success': False,
            'details': [],
            'vulnerability_level': 'LOW'
        }

        try:
            current_time = time.time()
            current_epoch = int(current_time // 600)

            # Test attestation timing at boundary
            epoch_end = (current_epoch + 1) * 600
            time_to_boundary = epoch_end - current_time

            if time_to_boundary < 60:  # Within 1 minute of boundary
                miner_id = 'test_miner_2'

                with self.db_connection() as conn:
                    # Submit attestation right at boundary
                    boundary_time = epoch_end - 1
                    conn.execute('''
                        INSERT OR IGNORE INTO attestations (miner_id, epoch, attestation_hash, timestamp)
                        VALUES (?, ?, ?, ?)
                    ''', (miner_id, current_epoch, hashlib.sha256(f"boundary_{miner_id}".encode()).hexdigest(), boundary_time))

                    # Check if accepted
                    accepted = conn.execute(
                        'SELECT COUNT(*) FROM attestations WHERE miner_id = ? AND epoch = ? AND timestamp = ?',
                        (miner_id, current_epoch, boundary_time)
                    ).fetchone()[0]

                    if accepted > 0:
                        result['details'].append("Boundary attestation accepted")
                        # This might be expected behavior

                    conn.commit()
            else:
                result['details'].append("Not near epoch boundary, skipping timing test")

        except Exception as e:
            result['details'].append(f"Test error: {str(e)}")

        return result

    def generate_vulnerability_report(self, results: List[Dict[str, Any]]) -> str:
        """Generate detailed security report"""
        report = []
        report.append("=" * 80)
        report.append("RUSTCHAIN SECURITY TEST REPORT")
        report.append("=" * 80)
        report.append(f"Timestamp: {datetime.now().isoformat()}")
        report.append("")

        high_vulns = [r for r in results if r['vulnerability_level'] == 'HIGH']
        medium_vulns = [r for r in results if r['vulnerability_level'] == 'MEDIUM']
        low_vulns = [r for r in results if r['vulnerability_level'] == 'LOW']

        report.append("SUMMARY:")
        report.append(f"  High Risk Vulnerabilities: {len(high_vulns)}")
        report.append(f"  Medium Risk Vulnerabilities: {len(medium_vulns)}")
        report.append(f"  Low Risk/No Issues: {len(low_vulns)}")
        report.append("")

        for result in results:
            report.append("-" * 60)
            report.append(f"Attack: {result['attack'].upper()}")
            report.append(f"Success: {'YES' if result['success'] else 'NO'}")
            report.append(f"Risk Level: {result['vulnerability_level']}")
            report.append("Details:")
            for detail in result['details']:
                report.append(f"  - {detail}")
            report.append("")

        if high_vulns:
            report.append("=" * 80)
            report.append("CRITICAL VULNERABILITIES DETECTED!")
            report.append("Immediate action required.")

        return "\n".join(report)

    def run_full_security_audit(self) -> str:
        """Execute complete security test suite"""
        self.logger.info("Starting full security audit...")

        # Setup test environment
        self.create_test_environment()

        try:
            results = []

            # Run all attack scenarios
            for scenario_name, scenario_func in self.attack_scenarios.items():
                self.logger.info(f"Running {scenario_name}...")
                result = scenario_func()
                results.append(result)

                if result['success']:
                    self.logger.warning(f"Vulnerability found in {scenario_name}")
                else:
                    self.logger.info(f"No issues found in {scenario_name}")

            # Generate report
            report = self.generate_vulnerability_report(results)

            # Save report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"security_report_{timestamp}.txt"

            with open(report_filename, 'w') as f:
                f.write(report)

            self.logger.info(f"Security report saved to {report_filename}")
            return report

        finally:
            # Cleanup
            self.cleanup_test_environment()

    def run_specific_attack(self, attack_name: str) -> Dict[str, Any]:
        """Run specific attack scenario"""
        if attack_name not in self.attack_scenarios:
            raise ValueError(f"Unknown attack: {attack_name}")

        self.create_test_environment()
        try:
            return self.attack_scenarios[attack_name]()
        finally:
            self.cleanup_test_environment()

if __name__ == "__main__":
    harness = SecurityTestHarness()
    print(harness.run_full_security_audit())
