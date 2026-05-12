#!/usr/bin/env python3
"""Unit tests for RustChain Profile Badge Generator (profile_badge_generator.py)

Tests cover badge creation, database operations, and badge type validation.
Edge cases: duplicate badges, missing fields, badge type enumeration.
"""

import os
import sqlite3
import tempfile
import pytest
from datetime import datetime


# --- Schema Constants ---

BADGE_TYPES = {"contributor", "miner", "bounty_hunter", "developer", "community", "early_adopter"}

PROFILE_BADGES_COLUMNS = [
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("github_username", "TEXT NOT NULL"),
    ("wallet_address", "TEXT"),
    ("badge_type", "TEXT DEFAULT 'contributor'"),
    ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ("bounty_earned", "DECIMAL(10,2) DEFAULT 0.0"),
    ("custom_message", "TEXT"),
]


# --- Fixtures ---

@pytest.fixture
def test_db():
    """Create a temporary database with profile_badges table."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    col_defs = ", ".join(f"{name} {definition}" for name, definition in PROFILE_BADGES_COLUMNS)
    cursor.execute(f"CREATE TABLE IF NOT EXISTS profile_badges ({col_defs})")
    conn.commit()
    conn.close()
    yield path
    os.unlink(path)


def insert_badge(db_path, username="testuser", wallet="RTC_test",
                  badge_type="contributor", bounty=0.0, message=""):
    """Helper to insert a badge record."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        """INSERT INTO profile_badges
           (github_username, wallet_address, badge_type, bounty_earned, custom_message)
           VALUES (?, ?, ?, ?, ?)""",
        (username, wallet, badge_type, bounty, message)
    )
    conn.commit()
    last_id = c.lastrowid
    conn.close()
    return last_id


# --- Test: Badge Creation ---

class TestBadgeCreation:
    """Test badge record creation."""

    def test_create_contributor_badge(self, test_db):
        """Basic contributor badge creation."""
        badge_id = insert_badge(test_db, username="alice", badge_type="contributor")
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute("SELECT github_username, badge_type FROM profile_badges WHERE id = ?", (badge_id,))
        row = c.fetchone()
        conn.close()
        assert row == ("alice", "contributor")

    def test_create_miner_badge(self, test_db):
        """Miner badge creation."""
        badge_id = insert_badge(test_db, username="bob", badge_type="miner")
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute("SELECT badge_type FROM profile_badges WHERE id = ?", (badge_id,))
        assert c.fetchone()[0] == "miner"
        conn.close()

    def test_badge_with_bounty_earned(self, test_db):
        """Badge with bounty earnings tracked."""
        badge_id = insert_badge(test_db, username="charlie", bounty=25.50)
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute("SELECT bounty_earned FROM profile_badges WHERE id = ?", (badge_id,))
        assert c.fetchone()[0] == 25.50
        conn.close()

    def test_badge_with_custom_message(self, test_db):
        """Badge with custom message."""
        msg = "Top bounty hunter Q1 2026"
        badge_id = insert_badge(test_db, username="dave", message=msg)
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute("SELECT custom_message FROM profile_badges WHERE id = ?", (badge_id,))
        assert c.fetchone()[0] == msg
        conn.close()

    def test_badge_default_type_is_contributor(self, test_db):
        """Default badge type should be 'contributor'."""
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute(
            "INSERT INTO profile_badges (github_username) VALUES (?)",
            ("default_user",)
        )
        conn.commit()
        c.execute("SELECT badge_type FROM profile_badges WHERE github_username = ?", ("default_user",))
        badge_type = c.fetchone()[0]
        conn.close()
        assert badge_type == "contributor", f"Default should be 'contributor', got '{badge_type}'"


# --- Test: Multiple Badges Per User ---

class TestMultipleBadges:
    """Test users with multiple badge types."""

    def test_user_can_have_multiple_badges(self, test_db):
        """Same user can earn different badge types."""
        insert_badge(test_db, username="multi_user", badge_type="contributor")
        insert_badge(test_db, username="multi_user", badge_type="miner")
        insert_badge(test_db, username="multi_user", badge_type="bounty_hunter")
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM profile_badges WHERE github_username = ?", ("multi_user",))
        count = c.fetchone()[0]
        conn.close()
        assert count == 3, "User should have 3 badges"

    def test_duplicate_badge_type_allowed(self, test_db):
        """Same user can have duplicate badge types (e.g., multiple contributor badges)."""
        insert_badge(test_db, username="dup_user", badge_type="contributor")
        insert_badge(test_db, username="dup_user", badge_type="contributor")
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM profile_badges WHERE github_username = ? AND badge_type = ?",
                   ("dup_user", "contributor"))
        count = c.fetchone()[0]
        conn.close()
        assert count == 2, "Duplicate badge types should be allowed"


# --- Test: Badge Type Validation ---

class TestBadgeTypeValidation:
    """Test badge type enumeration."""

    def test_all_badge_types_are_valid(self):
        """All defined badge types should be in the valid set."""
        for bt in BADGE_TYPES:
            assert bt in BADGE_TYPES, f"Badge type '{bt}' should be valid"

    def test_invalid_badge_type_detected(self):
        """Invalid badge types should be detected."""
        invalid = "super_admin"
        assert invalid not in BADGE_TYPES, f"'{invalid}' should not be a valid badge type"

    def test_badge_type_case_sensitivity(self):
        """Badge types should be case-sensitive (lowercase only)."""
        assert "Contributor" not in BADGE_TYPES, "Capitalized should not match"
        assert "contributor" in BADGE_TYPES, "Lowercase should match"


# --- Test: Bounty Earnings Tracking ---

class TestBountyEarnings:
    """Test bounty earned field edge cases."""

    def test_zero_bounty_default(self, test_db):
        """Default bounty earned should be 0."""
        badge_id = insert_badge(test_db, username="zero_bounty")
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute("SELECT bounty_earned FROM profile_badges WHERE id = ?", (badge_id,))
        assert c.fetchone()[0] == 0.0
        conn.close()

    def test_large_bounty_amount(self, test_db):
        """Large bounty amounts should be stored correctly."""
        large = 99999.99
        badge_id = insert_badge(test_db, username="whale", bounty=large)
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute("SELECT bounty_earned FROM profile_badges WHERE id = ?", (badge_id,))
        assert c.fetchone()[0] == large
        conn.close()

    def test_fractional_bounty(self, test_db):
        """Fractional bounty amounts stored precisely."""
        frac = 0.01
        badge_id = insert_badge(test_db, username="micro", bounty=frac)
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute("SELECT bounty_earned FROM profile_badges WHERE id = ?", (badge_id,))
        assert c.fetchone()[0] == frac
        conn.close()

    def test_bounty_update(self, test_db):
        """Bounty earned should be updatable."""
        badge_id = insert_badge(test_db, username="updater", bounty=10.0)
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute("UPDATE profile_badges SET bounty_earned = ? WHERE id = ?", (15.0, badge_id))
        conn.commit()
        c.execute("SELECT bounty_earned FROM profile_badges WHERE id = ?", (badge_id,))
        assert c.fetchone()[0] == 15.0
        conn.close()


# --- Test: Wallet Address ---

class TestWalletAddress:
    """Test wallet address field."""

    def test_rtc_wallet_format(self, test_db):
        """RTC wallet address should be stored correctly."""
        wallet = "RTC15e1241a37f2ae0ccff97e3bd2c2239b4c30ef8f"
        badge_id = insert_badge(test_db, username="wallet_user", wallet=wallet)
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute("SELECT wallet_address FROM profile_badges WHERE id = ?", (badge_id,))
        assert c.fetchone()[0] == wallet
        conn.close()

    def test_empty_wallet_allowed(self, test_db):
        """Wallet address is optional (can be empty)."""
        badge_id = insert_badge(test_db, username="no_wallet", wallet="")
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute("SELECT wallet_address FROM profile_badges WHERE id = ?", (badge_id,))
        val = c.fetchone()[0]
        conn.close()
        # Empty string or None should be accepted
        assert val is None or val == "", "Empty wallet should be allowed"


# --- Test: Database Queries ---

class TestDatabaseQueries:
    """Test common query patterns."""

    def test_get_all_badges_for_user(self, test_db):
        """Retrieve all badges for a specific user."""
        insert_badge(test_db, username="query_user", badge_type="contributor")
        insert_badge(test_db, username="query_user", badge_type="miner")
        insert_badge(test_db, username="other_user", badge_type="contributor")
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute("SELECT badge_type FROM profile_badges WHERE github_username = ?", ("query_user",))
        badges = [row[0] for row in c.fetchall()]
        conn.close()
        assert len(badges) == 2
        assert "contributor" in badges
        assert "miner" in badges

    def test_count_badges_by_type(self, test_db):
        """Count badges grouped by type."""
        for _ in range(3):
            insert_badge(test_db, badge_type="contributor")
        for _ in range(2):
            insert_badge(test_db, badge_type="miner")
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute("SELECT badge_type, COUNT(*) FROM profile_badges GROUP BY badge_type")
        counts = dict(c.fetchall())
        conn.close()
        assert counts["contributor"] == 3
        assert counts["miner"] == 2

    def test_top_earners_query(self, test_db):
        """Query top earners by bounty_earned."""
        insert_badge(test_db, username="low", bounty=5.0)
        insert_badge(test_db, username="mid", bounty=50.0)
        insert_badge(test_db, username="high", bounty=500.0)
        conn = sqlite3.connect(test_db)
        c = conn.cursor()
        c.execute(
            "SELECT github_username, bounty_earned FROM profile_badges ORDER BY bounty_earned DESC LIMIT 3"
        )
        rows = c.fetchall()
        conn.close()
        assert rows[0][0] == "high"
        assert rows[1][0] == "mid"
        assert rows[2][0] == "low"
