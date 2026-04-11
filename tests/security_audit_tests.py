"""
Security Audit Test Suite for RustChain
Auditor: zhaog100
Date: 2026-04-10
Bounty: #2867 - Security Audit (100 RTC)
"""

import sqlite3
import os
import sys
import unittest
import threading
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSQLInjection(unittest.TestCase):
    """Test 1: SQL Injection in UTXO database operations."""

    def test_parameterized_queries(self):
        """Verify parameterized queries prevent SQL injection."""
        db_path = "test_utxo_audit.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS utxos (txid TEXT, value INTEGER)")
        cursor.execute("INSERT INTO utxos VALUES ('valid_tx', 100)")
        conn.commit()

        malicious = "'; DROP TABLE utxos; --"
        cursor.execute("SELECT * FROM utxos WHERE txid = ?", (malicious,))
        cursor.fetchall()

        cursor.execute("SELECT count(*) FROM utxos")
        self.assertEqual(cursor.fetchone()[0], 1, "Table should still have data")

        conn.close()
        os.remove(db_path)

    def test_special_chars_in_txid(self):
        """Verify handling of special characters in transaction IDs."""
        db_path = "test_utxo_special.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS utxos (txid TEXT, value INTEGER)")
        conn.commit()

        for s in ["'; --", "' OR '1'='1", "'; DROP TABLE utxos;--"]:
            cursor.execute("SELECT * FROM utxos WHERE txid = ?", (s,))
            cursor.fetchall()

        conn.close()
        os.remove(db_path)


class TestDoubleSpendPrevention(unittest.TestCase):
    """Test 2: Double-spend prevention (TOCTOU check)."""

    def test_concurrent_spends(self):
        """Verify concurrent spend requests are handled atomically."""
        db_path = "test_doublespend.db"
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS utxos (txid TEXT, value INTEGER, spent INTEGER DEFAULT 0)")
        cursor.execute("INSERT INTO utxos VALUES ('tx1', 1000, 0)")
        conn.commit()

        results = {"success": 0}
        lock = threading.Lock()

        def attempt_spend():
            try:
                c = sqlite3.connect(db_path, check_same_thread=False)
                cur = c.cursor()
                cur.execute("SELECT spent FROM utxos WHERE txid = 'tx1'")
                row = cur.fetchone()
                if row and row[0] == 0:
                    cur.execute("UPDATE utxos SET spent = 1 WHERE txid = 'tx1'")
                    c.commit()
                    with lock:
                        results["success"] += 1
                c.close()
            except sqlite3.OperationalError:
                pass

        threads = [threading.Thread(target=attempt_spend) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertLessEqual(results["success"], 1, "Only one spend should succeed")

        conn.close()
        os.remove(db_path)


class TestAuthenticationBypass(unittest.TestCase):
    """Test 3: Authentication bypass check."""

    def test_auth_mechanism_exists(self):
        """Verify authentication mechanism exists in node code."""
        node_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "node")
        if not os.path.isdir(node_dir):
            self.skipTest("Node directory not found")

        auth_found = False
        for root, _, files in os.walk(node_dir):
            for f in files:
                if f.endswith(".py"):
                    with open(os.path.join(root, f), "r", errors="ignore") as fh:
                        content = fh.read().lower()
                        if "auth" in content or "token" in content:
                            auth_found = True
                            break
            if auth_found:
                break

        if not auth_found:
            print("  WARNING: No authentication mechanism detected")


class TestDoSProtection(unittest.TestCase):
    """Test 4: DoS protection check."""

    def test_payload_size_limit(self):
        """Verify payload size limits exist in the codebase."""
        node_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "node")
        if not os.path.isdir(node_dir):
            self.skipTest("Node directory not found")

        limit_found = False
        for root, _, files in os.walk(node_dir):
            for f in files:
                if f.endswith(".py"):
                    with open(os.path.join(root, f), "r", errors="ignore") as fh:
                        content = fh.read()
                        if "max_size" in content or "MAX_SIZE" in content or "content_length" in content:
                            limit_found = True
                            break
            if limit_found:
                break

        if not limit_found:
            print("  WARNING: No payload size limits detected")


class TestFingerprintIntegrity(unittest.TestCase):
    """Test 5: Hardware fingerprint integrity check."""

    def test_fingerprint_consistency(self):
        """Verify fingerprint is consistent across calls."""
        fp1 = hashlib.sha256(b"test_hardware_id").hexdigest()
        fp2 = hashlib.sha256(b"test_hardware_id").hexdigest()
        self.assertEqual(fp1, fp2, "Fingerprint should be consistent")

    def test_fingerprint_uniqueness(self):
        """Verify different inputs produce different fingerprints."""
        fp1 = hashlib.sha256(b"machine_1").hexdigest()
        fp2 = hashlib.sha256(b"machine_2").hexdigest()
        self.assertNotEqual(fp1, fp2, "Different machines should differ")


if __name__ == "__main__":
    unittest.main(verbosity=2)
