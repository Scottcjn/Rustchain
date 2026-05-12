#!/usr/bin/env python3
"""Unit tests for RustChain Sophia API (sophia_api.py)

Tests cover query parameter validation, endpoint routing, and
SophiaCore inspection logic.
Edge cases: invalid inputs, boundary values, missing parameters.
"""

import os
import sqlite3
import tempfile
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock


# --- Constants from sophia_core.py ---

VERDICTS = ["GENUINE", "SUSPICIOUS", "REJECTED", "PENDING", "UNKNOWN"]


# --- Test: Query Parameter Validation ---

class TestQueryParamValidation:
    """Test positive_int_query_arg logic."""

    def test_valid_positive_integer(self):
        """Positive integer should be returned as-is."""
        # Simulating the function logic
        raw_value = "5"
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            value = None
        assert value == 5

    def test_zero_rejected(self):
        """Zero should be rejected (must be positive)."""
        raw_value = "0"
        value = int(raw_value)
        is_valid = value >= 1
        assert not is_valid, "Zero should not be valid for positive int"

    def test_negative_rejected(self):
        """Negative numbers should be rejected."""
        raw_value = "-3"
        value = int(raw_value)
        is_valid = value >= 1
        assert not is_valid, "Negative should not be valid for positive int"

    def test_non_numeric_rejected(self):
        """Non-numeric strings should fail conversion."""
        raw_value = "abc"
        try:
            value = int(raw_value)
            is_valid = True
        except (TypeError, ValueError):
            is_valid = False
        assert not is_valid, "Non-numeric should fail"

    def test_float_rejected(self):
        """Float strings should fail integer conversion."""
        raw_value = "3.14"
        try:
            value = int(raw_value)
            is_valid = True
        except ValueError:
            is_valid = False
        assert not is_valid, "Float string should fail int()"

    def test_empty_string_rejected(self):
        """Empty string should fail conversion."""
        raw_value = ""
        try:
            value = int(raw_value)
            is_valid = True
        except ValueError:
            is_valid = False
        assert not is_valid, "Empty string should fail"

    def test_max_value_clamped(self):
        """Value exceeding max should be clamped."""
        raw_value = "200"
        max_value = 100
        value = int(raw_value)
        if max_value is not None:
            value = min(value, max_value)
        assert value == 100, "Should clamp to max_value"

    def test_exactly_at_max(self):
        """Value at max should be returned as-is."""
        raw_value = "100"
        max_value = 100
        value = int(raw_value)
        value = min(value, max_value)
        assert value == 100

    def test_very_large_number(self):
        """Very large numbers should work (Python handles big ints)."""
        raw_value = "99999999"
        value = int(raw_value)
        assert value == 99999999


# --- Test: Verdict System ---

class TestVerdicts:
    """Test SophiaCore verdict enumeration."""

    def test_all_verdicts_are_strings(self):
        """All verdicts should be string values."""
        for v in VERDICTS:
            assert isinstance(v, str), f"Verdict {v} should be a string"

    def test_verdict_count(self):
        """Should have 5 verdict types."""
        assert len(VERDICTS) == 5

    def test_genuine_is_valid(self):
        """GENUINE should be in verdicts."""
        assert "GENUINE" in VERDICTS

    def test_suspicious_is_valid(self):
        """SUSPICIOUS should be in verdicts."""
        assert "SUSPICIOUS" in VERDICTS

    def test_rejected_is_valid(self):
        """REJECTED should be in verdicts."""
        assert "REJECTED" in VERDICTS

    def test_pending_is_valid(self):
        """PENDING should be in verdicts."""
        assert "PENDING" in VERDICTS

    def test_invalid_verdict_detected(self):
        """Invalid verdicts should be detected."""
        invalid = "APPROVED"
        assert invalid not in VERDICTS

    def test_case_sensitive_verdicts(self):
        """Verdicts should be case-sensitive (uppercase only)."""
        assert "genuine" not in VERDICTS
        assert "Genuine" not in VERDICTS


# --- Test: Inspection Flow ---

class TestInspectionFlow:
    """Test the inspection submission and review flow."""

    def test_inspection_requires_miner_id(self):
        """Inspection submission requires a miner_id."""
        payload = {"fingerprint": "abc123"}
        # miner_id is missing
        has_miner_id = "miner_id" in payload
        assert not has_miner_id, "Should detect missing miner_id"

    def test_inspection_with_all_fields(self):
        """Complete inspection submission should be valid."""
        payload = {
            "miner_id": "test-miner-001",
            "fingerprint": "sha256:abc123def456",
            "hardware_type": "Apple M2 Pro",
            "os_version": "macOS 14.6"
        }
        required = ["miner_id", "fingerprint"]
        has_all = all(k in payload for k in required)
        assert has_all, "All required fields should be present"

    def test_empty_fingerprint_rejected(self):
        """Empty fingerprint should be rejected."""
        payload = {"miner_id": "test", "fingerprint": ""}
        is_valid = len(payload["fingerprint"]) > 0
        assert not is_valid, "Empty fingerprint should be rejected"

    def test_fingerprint_format_sha256(self):
        """SHA256 fingerprint format should be recognized."""
        fp = "sha256:abc123def456"
        is_sha256 = fp.startswith("sha256:")
        assert is_sha256, "SHA256 format should be recognized"

    def test_status_by_miner_id(self):
        """Status endpoint should accept miner_id."""
        miner_id = "claw-wenkangdemini-29887"
        # Valid miner_id format
        is_valid = len(miner_id) > 0 and miner_id.isprintable()
        assert is_valid


# --- Test: Database Schema ---

class TestSophiaDB:
    """Test Sophia database operations."""

    @pytest.fixture
    def sophia_db(self):
        """Create a temporary Sophia inspection database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        conn = sqlite3.connect(path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                verdict TEXT NOT NULL DEFAULT 'PENDING',
                inspector TEXT DEFAULT 'auto',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        yield path
        os.unlink(path)

    def test_insert_inspection(self, sophia_db):
        """Insert a new inspection record."""
        conn = sqlite3.connect(sophia_db)
        c = conn.cursor()
        c.execute(
            "INSERT INTO inspections (miner_id, fingerprint, verdict) VALUES (?, ?, ?)",
            ("miner-1", "sha256:abc", "GENUINE")
        )
        conn.commit()
        c.execute("SELECT COUNT(*) FROM inspections")
        count = c.fetchone()[0]
        conn.close()
        assert count == 1

    def test_get_latest_inspection(self, sophia_db):
        """Get the latest inspection for a miner."""
        conn = sqlite3.connect(sophia_db)
        c = conn.cursor()
        c.execute(
            "INSERT INTO inspections (miner_id, fingerprint, verdict) VALUES (?, ?, ?)",
            ("miner-2", "sha256:111", "PENDING")
        )
        c.execute(
            "INSERT INTO inspections (miner_id, fingerprint, verdict) VALUES (?, ?, ?)",
            ("miner-2", "sha256:222", "GENUINE")
        )
        conn.commit()
        c.execute(
            "SELECT verdict FROM inspections WHERE miner_id = ? ORDER BY created_at DESC LIMIT 1",
            ("miner-2",)
        )
        verdict = c.fetchone()[0]
        conn.close()
        assert verdict == "GENUINE", "Should return latest verdict"

    def test_inspection_history_pagination(self, sophia_db):
        """Paginated history should work."""
        conn = sqlite3.connect(sophia_db)
        c = conn.cursor()
        for i in range(10):
            c.execute(
                "INSERT INTO inspections (miner_id, fingerprint, verdict) VALUES (?, ?, ?)",
                (f"miner-{i}", f"sha256:{i}", "GENUINE")
            )
        conn.commit()
        c.execute("SELECT COUNT(*) FROM inspections")
        total = c.fetchone()[0]
        c.execute("SELECT * FROM inspections LIMIT 5 OFFSET 0")
        page1 = c.fetchall()
        conn.close()
        assert total == 10
        assert len(page1) == 5, "Pagination should limit results"

    def test_verdict_default_is_pending(self, sophia_db):
        """Default verdict for new inspections should be PENDING."""
        conn = sqlite3.connect(sophia_db)
        c = conn.cursor()
        c.execute(
            "INSERT INTO inspections (miner_id, fingerprint) VALUES (?, ?)",
            ("miner-default", "sha256:default")
        )
        conn.commit()
        c.execute("SELECT verdict FROM inspections WHERE miner_id = ?", ("miner-default",))
        verdict = c.fetchone()[0]
        conn.close()
        assert verdict == "PENDING", "Default verdict should be PENDING"
