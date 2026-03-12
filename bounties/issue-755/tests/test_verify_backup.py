#!/usr/bin/env python3
"""
Test suite for RustChain Backup Verification Tool

Tests cover:
- Hash verification
- SQLite readability checks
- Restore verification
- Batch processing
- Exit codes
"""

import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from verify_backup import (
    EXIT_BATCH_PARTIAL_FAILURE,
    EXIT_FILE_NOT_FOUND,
    EXIT_HASH_MISMATCH,
    EXIT_INVALID_BACKUP,
    EXIT_READABILITY_FAILED,
    EXIT_RESTORE_FAILED,
    EXIT_SUCCESS,
    BackupVerificationResult,
    check_sqlite_integrity,
    compute_sha256,
    load_expected_hash,
    verify_backup,
    verify_batch,
    verify_restore,
)


def create_test_database(path: str, tables: dict = None) -> str:
    """Create a test SQLite database with optional tables."""
    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    if tables:
        for table_name, columns in tables.items():
            create_sql = f"CREATE TABLE {table_name} ({columns})"
            cursor.execute(create_sql)
    else:
        # Default test tables
        cursor.execute(
            """
            CREATE TABLE blocks (
                id INTEGER PRIMARY KEY,
                height INTEGER,
                hash TEXT,
                timestamp INTEGER
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY,
                block_id INTEGER,
                sender TEXT,
                receiver TEXT,
                amount REAL
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE agents (
                id INTEGER PRIMARY KEY,
                agent_id TEXT,
                reputation INTEGER,
                last_active INTEGER
            )
        """
        )

    conn.commit()
    conn.close()
    return path


def create_hash_sidecar(db_path: str, custom_hash: str = None) -> str:
    """Create a .sha256 sidecar file for a database."""
    hash_path = f"{db_path}.sha256"

    if custom_hash:
        hash_value = custom_hash
    else:
        hash_value = compute_sha256(db_path)

    with open(hash_path, "w") as f:
        f.write(f"{hash_value}  {os.path.basename(db_path)}")

    return hash_path


class TestHashVerification(unittest.TestCase):
    """Test SHA-256 hash verification."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        create_test_database(self.db_path)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compute_hash(self):
        """Test hash computation."""
        hash1 = compute_sha256(self.db_path)
        hash2 = compute_sha256(self.db_path)
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)  # SHA-256 hex length

    def test_hash_mismatch(self):
        """Test detection of hash mismatch."""
        result = verify_backup(
            self.db_path,
            check_hash=True,
            check_readability=False,
            expected_hash="0" * 64,  # Wrong hash
        )
        self.assertFalse(result.hash_check_passed)
        self.assertIn("Hash mismatch", result.errors[0])

    def test_hash_match(self):
        """Test successful hash verification."""
        correct_hash = compute_sha256(self.db_path)
        result = verify_backup(
            self.db_path,
            check_hash=True,
            check_readability=False,
            expected_hash=correct_hash,
        )
        self.assertTrue(result.hash_check_passed)
        self.assertEqual(result.computed_hash, correct_hash)

    def test_load_sidecar_hash(self):
        """Test loading hash from sidecar file."""
        create_hash_sidecar(self.db_path)
        loaded_hash = load_expected_hash(self.db_path)
        computed_hash = compute_sha256(self.db_path)
        self.assertEqual(loaded_hash, computed_hash)

    def test_missing_sidecar(self):
        """Test behavior when sidecar is missing."""
        loaded_hash = load_expected_hash(self.db_path)
        self.assertIsNone(loaded_hash)


class TestReadabilityCheck(unittest.TestCase):
    """Test SQLite readability verification."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_valid_database(self):
        """Test readability check on valid database."""
        create_test_database(self.db_path)
        passed, errors, warnings = check_sqlite_integrity(self.db_path)
        self.assertTrue(passed)
        self.assertEqual(len(errors), 0)

    def test_empty_file(self):
        """Test readability check on empty file."""
        Path(self.db_path).touch()
        passed, errors, warnings = check_sqlite_integrity(self.db_path)
        self.assertFalse(passed)
        self.assertTrue(any("empty" in e.lower() for e in errors))

    def test_corrupted_file(self):
        """Test readability check on corrupted file."""
        with open(self.db_path, "wb") as f:
            f.write(b"This is not a SQLite database")
        passed, errors, warnings = check_sqlite_integrity(self.db_path)
        self.assertFalse(passed)

    def test_nonexistent_file(self):
        """Test readability check on nonexistent file."""
        passed, errors, warnings = check_sqlite_integrity(self.db_path)
        self.assertFalse(passed)


class TestRestoreVerification(unittest.TestCase):
    """Test restore verification."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        create_test_database(self.db_path)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_successful_restore(self):
        """Test successful restore verification."""
        success, error_msg = verify_restore(self.db_path)
        self.assertTrue(success)
        self.assertEqual(error_msg, "")

    def test_restore_corrupted(self):
        """Test restore detection of corruption."""
        # Corrupt the database
        with open(self.db_path, "r+b") as f:
            f.seek(100)
            f.write(b"CORRUPTED")

        success, error_msg = verify_restore(self.db_path)
        self.assertFalse(success)
        self.assertIn("integrity check", error_msg.lower())


class TestFullVerification(unittest.TestCase):
    """Test complete verification workflow."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "rustchain_backup.db")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_valid_backup_all_checks(self):
        """Test full verification on valid backup."""
        create_test_database(self.db_path)
        create_hash_sidecar(self.db_path)

        result = verify_backup(
            self.db_path,
            check_hash=True,
            check_readability=True,
            check_restore=False,
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(result.hash_check_passed)
        self.assertTrue(result.readability_check_passed)
        self.assertEqual(result.table_count, 3)
        self.assertIn("blocks", result.tables)
        self.assertIn("transactions", result.tables)
        self.assertIn("agents", result.tables)

    def test_file_not_found(self):
        """Test handling of missing file."""
        result = verify_backup("/nonexistent/path/backup.db")
        self.assertFalse(result.is_valid)
        self.assertIn("not found", result.errors[0].lower())

    def test_empty_file(self):
        """Test handling of empty file."""
        empty_path = os.path.join(self.temp_dir, "empty.db")
        Path(empty_path).touch()

        result = verify_backup(empty_path)
        self.assertFalse(result.is_valid)
        self.assertIn("empty", result.errors[0].lower())


class TestBatchVerification(unittest.TestCase):
    """Test batch verification."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

        # Create multiple test databases
        for i in range(3):
            db_path = os.path.join(self.temp_dir, f"backup_{i}.db")
            create_test_database(db_path)
            create_hash_sidecar(db_path)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_batch_all_valid(self):
        """Test batch verification with all valid backups."""
        results, exit_code = verify_batch(self.temp_dir, pattern="*.db")
        self.assertEqual(len(results), 3)
        self.assertEqual(exit_code, EXIT_SUCCESS)
        self.assertTrue(all(r.is_valid for r in results))

    def test_batch_no_matches(self):
        """Test batch verification with no matching files."""
        results, exit_code = verify_batch(self.temp_dir, pattern="*.nonexistent")
        self.assertEqual(exit_code, EXIT_FILE_NOT_FOUND)


class TestExitCodes(unittest.TestCase):
    """Test CLI exit codes."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.script_path = os.path.join(SCRIPTS_DIR, "verify_backup.py")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_exit_success(self):
        """Test exit code 0 for success."""
        db_path = os.path.join(self.temp_dir, "valid.db")
        create_test_database(db_path)

        result = subprocess.run(
            [sys.executable, self.script_path, db_path, "--no-hash"],
            capture_output=True,
        )
        self.assertEqual(result.returncode, EXIT_SUCCESS)

    def test_exit_file_not_found(self):
        """Test exit code 1 for missing file."""
        result = subprocess.run(
            [sys.executable, self.script_path, "/nonexistent.db", "--no-hash"],
            capture_output=True,
        )
        self.assertEqual(result.returncode, EXIT_FILE_NOT_FOUND)

    def test_exit_hash_mismatch(self):
        """Test exit code 2 for hash mismatch."""
        db_path = os.path.join(self.temp_dir, "test.db")
        create_test_database(db_path)

        result = subprocess.run(
            [
                sys.executable,
                self.script_path,
                db_path,
                "--expected-hash",
                "0" * 64,
            ],
            capture_output=True,
        )
        self.assertEqual(result.returncode, EXIT_HASH_MISMATCH)


class TestResultSerialization(unittest.TestCase):
    """Test result serialization."""

    def test_to_dict(self):
        """Test result serialization to dictionary."""
        result = BackupVerificationResult("/path/to/backup.db")
        result.hash_check_passed = True
        result.computed_hash = "abc123"
        result.expected_hash = "abc123"
        result.readability_check_passed = True
        result.table_count = 2
        result.tables = ["table1", "table2"]

        data = result.to_dict()

        self.assertEqual(data["backup_path"], "/path/to/backup.db")
        self.assertTrue(data["hash_check"]["passed"])
        self.assertEqual(data["readability_check"]["table_count"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
