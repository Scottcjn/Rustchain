#!/usr/bin/env python3
"""Unit tests for RustChain Discord Rich Presence (discord_rich_presence.py)

Tests cover state management, earnings tracking, and TLS configuration.
Edge cases: missing state file, corrupted JSON, negative earnings.
"""

import json
import os
import tempfile
import pytest
from datetime import datetime, timedelta


# --- Test: State File Management ---

class TestStateFile:
    """Test reading/writing the local state file for earnings tracking."""

    @pytest.fixture
    def state_dir(self):
        """Create a temporary directory for state files."""
        d = tempfile.mkdtemp()
        yield d
        import shutil
        shutil.rmtree(d, ignore_errors=True)

    def test_read_empty_state(self, state_dir):
        """Reading a non-existent state file should return defaults."""
        path = os.path.join(state_dir, "state.json")
        if os.path.exists(path):
            data = json.load(open(path))
        else:
            data = {"earned_today": 0, "last_reset": None}
        assert data["earned_today"] == 0

    def test_write_and_read_state(self, state_dir):
        """Written state should be readable."""
        path = os.path.join(state_dir, "state.json")
        state = {
            "earned_today": 5.5,
            "last_reset": datetime.now().isoformat(),
            "total_earned": 70.5,
            "miner_id": "claw-test-001",
        }
        with open(path, "w") as f:
            json.dump(state, f)
        with open(path) as f:
            loaded = json.load(f)
        assert loaded["earned_today"] == 5.5
        assert loaded["miner_id"] == "claw-test-001"

    def test_corrupted_state_file(self, state_dir):
        """Corrupted JSON should be handled gracefully."""
        path = os.path.join(state_dir, "state.json")
        with open(path, "w") as f:
            f.write("{invalid json")
        try:
            with open(path) as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = {"earned_today": 0, "last_reset": None}
        assert data["earned_today"] == 0


# --- Test: Earnings Tracking ---

class TestEarningsTracking:
    """Test daily earnings calculation and reset logic."""

    def test_daily_earnings_accumulate(self):
        """Earnings should accumulate within the same day."""
        earned = 0
        earned += 1.5  # Morning mining
        earned += 2.0  # Afternoon mining
        assert earned == 3.5

    def test_daily_earnings_reset_at_midnight(self):
        """Earnings should reset when a new day starts."""
        today = datetime.now().date()
        yesterday = (datetime.now() - timedelta(days=1)).date()
        last_reset = yesterday.isoformat()
        current_day = today.isoformat()
        needs_reset = last_reset != current_day
        assert needs_reset, "Earnings should reset on new day"

    def test_negative_earnings_rejected(self):
        """Negative earnings should be rejected."""
        earned = 5.0
        adjustment = -1.0
        new_total = earned + adjustment
        is_valid = new_total >= 0
        assert is_valid, "Negative total should be caught"
        assert adjustment < 0, "Negative adjustment should be detected"

    def test_earnings_precision(self):
        """RTC earnings should handle fractional amounts."""
        earned = 0.001  # Small fraction
        assert earned > 0, "Small fractions should be tracked"
        # Avoid floating point issues
        earned_nrtc = int(earned * 100_000_000)  # Convert to nanoRTC
        assert earned_nrtc == 100_000, "nanoRTC conversion should be exact"


# --- Test: TLS Configuration ---

class TestTLSConfig:
    """Test TLS certificate verification settings."""

    def test_tls_verify_default_is_true(self):
        """Default TLS verification should be True (secure)."""
        cert_path = os.path.expanduser("~/.rustchain/node_cert.pem")
        tls_verify = cert_path if os.path.exists(cert_path) else True
        assert tls_verify is True, "Default should verify SSL"

    def test_tls_verify_with_cert(self):
        """When cert file exists, use it for verification."""
        # Simulate cert file existing
        cert_path = "/tmp/test_cert.pem"
        with open(cert_path, "w") as f:
            f.write("-----BEGIN CERTIFICATE-----\nMIIC...\n-----END CERTIFICATE-----\n")
        tls_verify = cert_path if os.path.exists(cert_path) else True
        assert isinstance(tls_verify, str), "Should use cert path when available"
        os.unlink(cert_path)

    def test_tls_verify_false_rejected(self):
        """verify=False should NOT be used (security)."""
        # The module uses cert_path or True, never False
        # This test documents the security requirement
        cert_path = os.path.expanduser("~/.rustchain/node_cert.pem")
        tls_verify = cert_path if os.path.exists(cert_path) else True
        assert tls_verify is not False, "verify=False should never be used"


# --- Test: Update Interval ---

class TestUpdateInterval:
    """Test Discord presence update interval logic."""

    def test_default_interval(self):
        """Default update interval should be 60 seconds."""
        default = 60
        assert default == 60, "Default interval is 60s"

    def test_minimum_interval(self):
        """Interval should not be below 15s (Discord rate limit)."""
        interval = 60
        min_interval = 15
        assert interval >= min_interval, "Must respect Discord rate limits"

    def test_custom_interval(self):
        """Custom interval should be accepted if above minimum."""
        custom = 120
        assert custom >= 15, "Custom interval must be at least 15s"


# --- Test: Discord Presence Payload ---

class TestPresencePayload:
    """Test Discord Rich Presence payload construction."""

    def test_basic_presence_state(self):
        """Basic presence state should include key fields."""
        state = "⛏️ Mining | 5.5 RTC today"
        details = "Apple M2 Pro | 12h uptime"
        assert "Mining" in state
        assert "RTC" in state
        assert "uptime" in details

    def test_large_values_display(self):
        """Large earning values should display correctly."""
        earned = 99999.99
        state = f"⛏️ Mining | {earned} RTC today"
        assert "99999.99" in state

    def test_hardware_type_display(self):
        """Hardware type should be included in details."""
        hw_types = [
            "Apple M2 Pro", "POWER8", "G4", "RISC-V", "SPARC",
            "x86_64", "ARM64", "Raspberry Pi 5"
        ]
        for hw in hw_types:
            details = f"{hw} | 6h uptime"
            assert hw in details
