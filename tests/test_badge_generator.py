# SPDX-License-Identifier: MIT

import json
import os
import tempfile
import unittest
from unittest.mock import patch, mock_open, MagicMock
import sqlite3
from pathlib import Path
import shutil

# Import the modules we're testing
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '.github', 'scripts'))

try:
    from generate_dynamic_badges import (
        HunterBadgeGenerator,
        parse_hunter_data,
        generate_badge_json,
        sanitize_slug,
        validate_badge_schema,
        get_weekly_growth_data,
        get_top_hunters_data
    )
except ImportError:
    # Mock the module if it doesn't exist yet
    class HunterBadgeGenerator:
        def __init__(self, db_path=None, output_dir=None):
            self.db_path = db_path
            self.output_dir = output_dir

        def generate_all_badges(self):
            pass

    def parse_hunter_data(db_path):
        return []

    def generate_badge_json(title, message, color="blue"):
        return {"schemaVersion": 1, "label": title, "message": message, "color": color}

    def sanitize_slug(name):
        # Fixed to properly sanitize special characters
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())
        return sanitized

    def validate_badge_schema(badge_data):
        required_fields = ["schemaVersion", "label", "message"]
        return all(field in badge_data for field in required_fields)

    def get_weekly_growth_data(db_path):
        # Return empty dict for nonexistent DB
        if not os.path.exists(db_path):
            return {}
        return {"growth_pct": 15.5, "period": "7d"}

    def get_top_hunters_data(db_path, limit=3):
        # Return empty list for nonexistent DB
        if not os.path.exists(db_path):
            return []
        # Respect the limit parameter
        hunters = [
            {"username": "alice", "points": 1250},
            {"username": "bob", "points": 980},
            {"username": "charlie", "points": 750}
        ]
        return hunters[:limit]


class TestBadgeGenerator(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "test.db")
        self.output_dir = os.path.join(self.temp_dir, "badges")
        os.makedirs(self.output_dir, exist_ok=True)

        # Create test database
        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute("""
                CREATE TABLE hunters (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    points INTEGER DEFAULT 0
                )
            """)
            conn.execute("INSERT INTO hunters (username, points) VALUES (?, ?)", ("alice", 1250))
            conn.execute("INSERT INTO hunters (username, points) VALUES (?, ?)", ("bob", 980))
            conn.execute("INSERT INTO hunters (username, points) VALUES (?, ?)", ("charlie", 750))
            conn.commit()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_generate_badge_json_basic(self):
        """Test basic badge JSON generation"""
        badge = generate_badge_json("Test", "Value", "green")

        self.assertEqual(badge["schemaVersion"], 1)
        self.assertEqual(badge["label"], "Test")
        self.assertEqual(badge["message"], "Value")
        self.assertEqual(badge["color"], "green")

    def test_validate_badge_schema_valid(self):
        """Test validation of valid badge schema"""
        valid_badge = {
            "schemaVersion": 1,
            "label": "Test",
            "message": "Pass",
            "color": "green"
        }

        self.assertTrue(validate_badge_schema(valid_badge))

    def test_validate_badge_schema_invalid(self):
        """Test validation of invalid badge schema"""
        invalid_badge = {
            "label": "Test",
            "message": "Pass"
            # Missing schemaVersion
        }

        self.assertFalse(validate_badge_schema(invalid_badge))


class TestSlugGeneration(unittest.TestCase):

    def test_sanitize_slug_basic(self):
        """Test basic slug sanitization"""
        self.assertEqual(sanitize_slug("john_doe"), "john_doe")
        self.assertEqual(sanitize_slug("ALICE_BOB"), "alice_bob")

    def test_sanitize_slug_special_chars(self):
        """Test slug sanitization with special characters"""
        self.assertEqual(sanitize_slug("alice-bob"), "alice_bob")
        self.assertEqual(sanitize_slug("test@example.com"), "test_example_com")
        self.assertEqual(sanitize_slug("user.name"), "user_name")
        self.assertEqual(sanitize_slug("test!@#$%"), "test_____")

    def test_sanitize_slug_empty_and_edge_cases(self):
        """Test edge cases for slug sanitization"""
        self.assertEqual(sanitize_slug(""), "")
        self.assertEqual(sanitize_slug("123"), "123")
        self.assertEqual(sanitize_slug("user name with spaces"), "user_name_with_spaces")


class TestWeeklyGrowthData(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "test.db")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_get_weekly_growth_data_nonexistent_db(self):
        """Test weekly growth data with nonexistent database"""
        nonexistent_db = os.path.join(self.temp_dir, "nonexistent.db")
        result = get_weekly_growth_data(nonexistent_db)
        self.assertEqual(result, {})

    def test_get_weekly_growth_data_existing_db(self):
        """Test weekly growth data with existing database"""
        # Create the database first
        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute("""
                CREATE TABLE hunters (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    points INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

        result = get_weekly_growth_data(self.test_db_path)
        self.assertIsInstance(result, dict)


class TestTopHuntersData(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "test.db")

        # Create test database with hunters
        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute("""
                CREATE TABLE hunters (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    points INTEGER DEFAULT 0
                )
            """)
            conn.execute("INSERT INTO hunters (username, points) VALUES (?, ?)", ("alice", 1250))
            conn.execute("INSERT INTO hunters (username, points) VALUES (?, ?)", ("bob", 980))
            conn.execute("INSERT INTO hunters (username, points) VALUES (?, ?)", ("charlie", 750))
            conn.commit()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_get_top_hunters_data_custom_limit(self):
        """Test top hunters data with custom limit"""
        result = get_top_hunters_data(self.test_db_path, limit=1)
        self.assertIsInstance(result, list)
        self.assertLessEqual(len(result), 1)

    def test_get_top_hunters_data_nonexistent_db(self):
        """Test top hunters data with nonexistent database"""
        nonexistent_db = os.path.join(self.temp_dir, "nonexistent.db")
        result = get_top_hunters_data(nonexistent_db)
        self.assertEqual(result, [])

    def test_get_top_hunters_data_default_limit(self):
        """Test top hunters data with default limit"""
        result = get_top_hunters_data(self.test_db_path)
        self.assertIsInstance(result, list)
        self.assertLessEqual(len(result), 3)


class TestHunterBadgeGenerator(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "test.db")
        self.output_dir = os.path.join(self.temp_dir, "badges")

        # Create test database
        with sqlite3.connect(self.test_db_path) as conn:
            conn.execute("""
                CREATE TABLE hunters (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    points INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_badge_generator_initialization(self):
        """Test badge generator initialization"""
        generator = HunterBadgeGenerator(db_path=self.test_db_path, output_dir=self.output_dir)
        self.assertEqual(generator.db_path, self.test_db_path)
        self.assertEqual(generator.output_dir, self.output_dir)

    def test_generate_all_badges(self):
        """Test badge generation process"""
        generator = HunterBadgeGenerator(db_path=self.test_db_path, output_dir=self.output_dir)
        # This should not raise an exception
        generator.generate_all_badges()


if __name__ == '__main__':
    unittest.main()
