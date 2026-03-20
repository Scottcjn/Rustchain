// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
import threading
import requests
import hashlib
import random
import string
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import os
import re

DB_PATH = 'rustchain.db'
AUDIT_LOG_PATH = 'security_audit_results.json'

class SecurityAudit:
    def __init__(self, base_url='http://localhost:8080'):
        self.base_url = base_url
        self.results = []
        self.session = requests.Session()
        self.test_wallets = []

    def log_finding(self, severity, category, description, proof_of_concept=None, endpoint=None):
        finding = {
            'timestamp': datetime.now().isoformat(),
            'severity': severity,
            'category': category,
            'description': description,
            'endpoint': endpoint,
            'proof_of_concept': proof_of_concept
        }
        self.results.append(finding)
        print(f"[{severity}] {category}: {description}")

    def setup_test_data(self):
        """Create test wallets and initial balances"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Create test wallets
            test_addresses = ['test_wallet_1', 'test_wallet_2', 'test_wallet_admin']
            for addr in test_addresses:
                cursor.execute('''
                    INSERT OR IGNORE INTO wallets (address, balance, created_at)
                    VALUES (?, 1000.0, ?)
                ''', (addr, datetime.now().isoformat()))
                self.test_wallets.append(addr)

            conn.commit()

    def test_sql_injection(self):
        """Test for SQL injection vulnerabilities"""
        print("\n=== SQL Injection Testing ===")

        sql_payloads = [
            "'; DROP TABLE wallets; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM wallets --",
            "'; UPDATE wallets SET balance=999999 WHERE address='test_wallet_1'; --",
            "' OR 1=1 --",
            "admin'--",
            "' OR 'x'='x"
        ]

        test_endpoints = [
            '/wallet/balance',
            '/wallet/transfer',
            '/ledger/history',
            '/admin/users'
        ]

        for endpoint in test_endpoints:
            for payload in sql_payloads:
                try:
                    if endpoint == '/wallet/balance':
                        resp = self.session.get(f"{self.base_url}{endpoint}?address={payload}")
                    elif endpoint == '/wallet/transfer':
                        data = {
                            'from_address': payload,
                            'to_address': 'test_wallet_2',
                            'amount': 10
                        }
                        resp = self.session.post(f"{self.base_url}{endpoint}", json=data)
                    elif endpoint == '/ledger/history':
                        resp = self.session.get(f"{self.base_url}{endpoint}?address={payload}")
                    elif endpoint == '/admin/users':
                        resp = self.session.get(f"{self.base_url}{endpoint}?user={payload}")

                    if resp.status_code == 500 or 'error' in resp.text.lower():
                        if 'syntax error' in resp.text.lower() or 'sql' in resp.text.lower():
                            self.log_finding('HIGH', 'SQL Injection',
                                           f'SQL injection detected in {endpoint}',
                                           f'Payload: {payload}, Response: {resp.text[:200]}',
                                           endpoint)

                except Exception as e:
                    if 'sql' in str(e).lower() or 'syntax' in str(e).lower():
                        self.log_finding('HIGH', 'SQL Injection',
                                       f'SQL injection error in {endpoint}: {str(e)}',
                                       f'Payload: {payload}', endpoint)

    def test_authentication_bypass(self):
        """Test for authentication bypass vulnerabilities"""
        print("\n=== Authentication Bypass Testing ===")

        admin_endpoints = [
            '/admin/users',
            '/admin/system_stats',
            '/admin/reset_wallet',
            '/admin/mint_tokens'
        ]

        bypass_headers = [
            {'X-Admin': 'true'},
            {'Authorization': 'Bearer admin'},
            {'X-Real-IP': '127.0.0.1'},
            {'X-Forwarded-For': '127.0.0.1'},
            {'User-Agent': 'admin'},
            {'X-Original-URL': '/admin'},
            {'X-Override-URL': '/admin'}
        ]

        for endpoint in admin_endpoints:
            # Test without auth
            try:
                resp = self.session.get(f"{self.base_url}{endpoint}")
                if resp.status_code == 200:
                    self.log_finding('HIGH', 'Authentication Bypass',
                                   f'Admin endpoint {endpoint} accessible without auth',
                                   f'Status: {resp.status_code}, Response: {resp.text[:100]}',
                                   endpoint)
            except:
                pass

            # Test with bypass headers
            for headers in bypass_headers:
                try:
                    resp = self.session.get(f"{self.base_url}{endpoint}", headers=headers)
                    if resp.status_code == 200 and 'admin' in resp.text.lower():
                        self.log_finding('HIGH', 'Authentication Bypass',
                                       f'Header-based auth bypass on {endpoint}',
                                       f'Headers: {headers}, Response: {resp.text[:100]}',
                                       endpoint)
                except:
                    pass

    def test_race_conditions(self):
        """Test for race condition vulnerabilities in transfers"""
        print("\n=== Race Condition Testing ===")

        def concurrent_transfer(thread_id):
            data = {
                'from_address': 'test_wallet_1',
                'to_address': 'test_wallet_2',
                'amount': 100
            }
            try:
                resp = self.session.post(f"{self.base_url}/wallet/transfer", json=data)
                return f"Thread {thread_id}: {resp.status_code}"
            except Exception as e:
                return f"Thread {thread_id}: Error - {str(e)}"

        # Test concurrent transfers from same wallet
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(concurrent_transfer, i) for i in range(10)]
            results = [future.result() for future in futures]

        # Check if balance went negative
        try:
            resp = self.session.get(f"{self.base_url}/wallet/balance?address=test_wallet_1")
            if resp.status_code == 200:
                balance_data = resp.json()
                if balance_data.get('balance', 0) < 0:
                    self.log_finding('HIGH', 'Race Condition',
                                   'Negative balance achieved through concurrent transfers',
                                   f'Final balance: {balance_data.get("balance")}',
                                   '/wallet/transfer')
        except:
            pass

    def test_balance_manipulation(self):
        """Test for balance manipulation vectors"""
        print("\n=== Balance Manipulation Testing ===")

        # Test negative amount transfers
        negative_tests = [
            {'from_address': 'test_wallet_1', 'to_address': 'test_wallet_2', 'amount': -100},
            {'from_address': 'test_wallet_2', 'to_address': 'test_wallet_1', 'amount': -50},
            {'from_address': 'test_wallet_1', 'to_address': 'test_wallet_1', 'amount': 100}
        ]

        for test_data in negative_tests:
            try:
                resp = self.session.post(f"{self.base_url}/wallet/transfer", json=test_data)
                if resp.status_code == 200:
                    self.log_finding('HIGH', 'Balance Manipulation',
                                   f'Negative/self transfer accepted: {test_data}',
                                   f'Response: {resp.text}',
                                   '/wallet/transfer')
            except:
                pass

        # Test overflow conditions
        overflow_tests = [
            {'from_address': 'test_wallet_1', 'to_address': 'test_wallet_2', 'amount': 999999999999999999},
            {'from_address': 'test_wallet_1', 'to_address': 'test_wallet_2', 'amount': float('inf')},
            {'from_address': 'test_wallet_1', 'to_address': 'test_wallet_2', 'amount': -float('inf')}
        ]

        for test_data in overflow_tests:
            try:
                resp = self.session.post(f"{self.base_url}/wallet/transfer", json=test_data)
                if resp.status_code == 200:
                    self.log_finding('MEDIUM', 'Balance Manipulation',
                                   f'Overflow value accepted: {test_data["amount"]}',
                                   f'Response: {resp.text}',
                                   '/wallet/transfer')
            except:
                pass

    def test_admin_key_exposure(self):
        """Test for admin key exposure risks"""
        print("\n=== Admin Key Exposure Testing ===")

        # Check common config files
        config_files = [
            '/.env',
            '/config.json',
            '/settings.py',
            '/admin_keys.txt',
            '/.git/config',
            '/backup.sql'
        ]

        for file_path in config_files:
            try:
                resp = self.session.get(f"{self.base_url}{file_path}")
                if resp.status_code == 200 and len(resp.text) > 0:
                    if 'admin' in resp.text.lower() or 'key' in resp.text.lower() or 'secret' in resp.text.lower():
                        self.log_finding('CRITICAL', 'Admin Key Exposure',
                                       f'Sensitive config file exposed: {file_path}',
                                       f'Content preview: {resp.text[:200]}',
                                       file_path)
            except:
                pass

        # Check for debug endpoints
        debug_endpoints = [
            '/debug',
            '/status',
            '/health',
            '/info',
            '/version',
            '/env'
        ]

        for endpoint in debug_endpoints:
            try:
                resp = self.session.get(f"{self.base_url}{endpoint}")
                if resp.status_code == 200:
                    if any(keyword in resp.text.lower() for keyword in ['admin', 'secret', 'key', 'password']):
                        self.log_finding('HIGH', 'Information Disclosure',
                                       f'Debug endpoint leaks sensitive info: {endpoint}',
                                       f'Response: {resp.text[:200]}',
                                       endpoint)
            except:
                pass

    def test_ledger_bypass(self):
        """Test for ledger logging bypass vulnerabilities"""
        print("\n=== Ledger Bypass Testing ===")

        # Record initial ledger count
        initial_ledger_count = 0
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM ledger')
                initial_ledger_count = cursor.fetchone()[0]
        except:
            pass

        # Attempt various bypass methods
        bypass_attempts = [
            # Direct database manipulation attempt
            {'method': 'direct_db', 'data': None},
            # API parameter manipulation
            {'method': 'skip_ledger', 'data': {'from_address': 'test_wallet_1', 'to_address': 'test_wallet_2', 'amount': 50, 'skip_ledger': True}},
            {'method': 'bypass_flag', 'data': {'from_address': 'test_wallet_1', 'to_address': 'test_wallet_2', 'amount': 50, 'bypass': True}},
            {'method': 'admin_transfer', 'data': {'from_address': 'test_wallet_1', 'to_address': 'test_wallet_2', 'amount': 50, 'admin': True}}
        ]

        for attempt in bypass_attempts:
            if attempt['method'] == 'direct_db':
                try:
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute('UPDATE wallets SET balance = balance + 1000 WHERE address = ?', ('test_wallet_1',))
                        conn.commit()

                        # Check if ledger entry was created
                        cursor.execute('SELECT COUNT(*) FROM ledger')
                        new_count = cursor.fetchone()[0]

                        if new_count == initial_ledger_count:
                            self.log_finding('CRITICAL', 'Ledger Bypass',
                                           'Direct database manipulation bypasses ledger',
                                           'Updated wallet balance without ledger entry',
                                           'database')
                except:
                    pass
            else:
                try:
                    resp = self.session.post(f"{self.base_url}/wallet/transfer", json=attempt['data'])
                    if resp.status_code == 200:
                        # Check ledger count
                        with sqlite3.connect(DB_PATH) as conn:
                            cursor = conn.cursor()
                            cursor.execute('SELECT COUNT(*) FROM ledger')
                            new_count = cursor.fetchone()[0]

                            if new_count == initial_ledger_count:
                                self.log_finding('HIGH', 'Ledger Bypass',
                                               f'Transfer completed without ledger entry: {attempt["method"]}',
                                               f'Request data: {attempt["data"]}',
                                               '/wallet/transfer')
                except:
                    pass

    def generate_report(self):
        """Generate comprehensive security audit report"""
        report = {
            'audit_timestamp': datetime.now().isoformat(),
            'summary': {
                'total_findings': len(self.results),
                'critical': len([r for r in self.results if r['severity'] == 'CRITICAL']),
                'high': len([r for r in self.results if r['severity'] == 'HIGH']),
                'medium': len([r for r in self.results if r['severity'] == 'MEDIUM']),
                'low': len([r for r in self.results if r['severity'] == 'LOW'])
            },
            'findings': self.results,
            'recommendations': [
                'Implement parameterized queries for all SQL operations',
                'Add proper authentication checks to all admin endpoints',
                'Use database transactions with proper locking for concurrent operations',
                'Validate all input parameters including negative values and overflow conditions',
                'Remove or secure debug endpoints in production',
                'Ensure all balance changes are logged to the ledger atomically'
            ]
        }

        with open(AUDIT_LOG_PATH, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n=== SECURITY AUDIT COMPLETE ===")
        print(f"Total findings: {report['summary']['total_findings']}")
        print(f"Critical: {report['summary']['critical']}")
        print(f"High: {report['summary']['high']}")
        print(f"Medium: {report['summary']['medium']}")
        print(f"Low: {report['summary']['low']}")
        print(f"Report saved to: {AUDIT_LOG_PATH}")

        return report

    def run_full_audit(self):
        """Execute complete security audit"""
        print("Starting comprehensive security audit...")

        try:
            self.setup_test_data()
            self.test_sql_injection()
            self.test_authentication_bypass()
            self.test_race_conditions()
            self.test_balance_manipulation()
            self.test_admin_key_exposure()
            self.test_ledger_bypass()

            return self.generate_report()

        except Exception as e:
            self.log_finding('CRITICAL', 'Audit Error', f'Audit framework error: {str(e)}')
            return self.generate_report()

if __name__ == '__main__':
    audit = SecurityAudit()
    audit.run_full_audit()
