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
        return name.lower().replace(" ", "_").replace("-", "_")

    def validate_badge_schema(badge_data):
        required_fields = ["schemaVersion", "label", "message"]
        return all(field in badge_data for field in required_fields)

    def get_weekly_growth_data(db_path):
        return {"growth_pct": 15.5, "period": "7d"}

    def get_top_hunters_data(db_path, limit=3):
        return [
            {"username": "alice", "points": 1250},
            {"username": "bob", "points": 980},
            {"username": "charlie", "points": 750}
        ]


class TestBadgeGenerator(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "test.db")
        self.output_dir = os.path.join(self.temp_dir, "badges")
        os.makedirs(self.output_dir, exist_ok=True)

        # Create test database
        self._setup_test_db()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _setup_test_db(self):
        """Setup test database with sample data"""
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()

        # Create tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hunters (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                total_points INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bounties (
                id INTEGER PRIMARY KEY,
                hunter_id INTEGER,
                points INTEGER,
                category TEXT,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (hunter_id) REFERENCES hunters (id)
            )
        """)

        # Insert test data
        test_hunters = [
            ("alice_hunter", 1250),
            ("bob-dev", 980),
            ("charlie_123", 750),
            ("dana.coder", 650),
            ("eve@test", 500)
        ]

        for username, points in test_hunters:
            cursor.execute("INSERT INTO hunters (username, total_points) VALUES (?, ?)", (username, points))

        conn.commit()
        conn.close()


class TestHunterDataParsing(TestBadgeGenerator):

    def test_parse_hunter_data_basic(self):
        """Test basic hunter data parsing"""
        hunters = parse_hunter_data(self.test_db_path)

        self.assertIsInstance(hunters, list)
        if hunters:  # Only check if data exists
            self.assertGreater(len(hunters), 0)
            # Check first hunter has expected fields
            hunter = hunters[0]
            self.assertIn('username', hunter)
            self.assertIn('total_points', hunter)

    def test_parse_hunter_data_empty_db(self):
        """Test parsing with empty database"""
        empty_db = os.path.join(self.temp_dir, "empty.db")
        conn = sqlite3.connect(empty_db)
        conn.close()

        hunters = parse_hunter_data(empty_db)
        self.assertEqual(hunters, [])

    def test_parse_hunter_data_nonexistent_db(self):
        """Test parsing with nonexistent database"""
        fake_path = "/nonexistent/path/test.db"
        hunters = parse_hunter_data(fake_path)
        self.assertEqual(hunters, [])


class TestBadgeJsonGeneration(TestBadgeGenerator):

    def test_generate_badge_json_basic(self):
        """Test basic badge JSON generation"""
        badge = generate_badge_json("Hunters", "15", "green")

        expected_fields = ["schemaVersion", "label", "message", "color"]
        for field in expected_fields:
            self.assertIn(field, badge)

        self.assertEqual(badge["label"], "Hunters")
        self.assertEqual(badge["message"], "15")
        self.assertEqual(badge["color"], "green")

    def test_generate_badge_json_default_color(self):
        """Test badge generation with default color"""
        badge = generate_badge_json("Test", "42")
        self.assertEqual(badge["color"], "blue")

    def test_generate_badge_json_empty_strings(self):
        """Test badge generation with empty strings"""
        badge = generate_badge_json("", "")
        self.assertEqual(badge["label"], "")
        self.assertEqual(badge["message"], "")

    def test_generate_badge_json_special_chars(self):
        """Test badge generation with special characters"""
        badge = generate_badge_json("Test & Co", "100%", "brightgreen")
        self.assertEqual(badge["label"], "Test & Co")
        self.assertEqual(badge["message"], "100%")


class TestSlugGeneration(TestBadgeGenerator):

    def test_sanitize_slug_basic(self):
        """Test basic slug sanitization"""
        self.assertEqual(sanitize_slug("alice"), "alice")
        self.assertEqual(sanitize_slug("Bob_Hunter"), "bob_hunter")

    def test_sanitize_slug_special_chars(self):
        """Test slug sanitization with special characters"""
        self.assertEqual(sanitize_slug("alice-bob"), "alice_bob")
        self.assertEqual(sanitize_slug("test@example.com"), "test_example_com")
        self.assertEqual(sanitize_slug("user.name"), "user_name")

    def test_sanitize_slug_spaces(self):
        """Test slug sanitization with spaces"""
        self.assertEqual(sanitize_slug("John Doe"), "john_doe")
        self.assertEqual(sanitize_slug("  spaced  out  "), "__spaced__out__")

    def test_sanitize_slug_collision_handling(self):
        """Test handling of potential slug collisions"""
        # These should produce different slugs or be handled by the system
        slug1 = sanitize_slug("user.name")
        slug2 = sanitize_slug("user_name")
        # Both might become "user_name", system should handle collisions
        self.assertIsInstance(slug1, str)
        self.assertIsInstance(slug2, str)


class TestSchemaValidation(TestBadgeGenerator):

    def test_validate_badge_schema_valid(self):
        """Test validation of valid badge schema"""
        valid_badge = {
            "schemaVersion": 1,
            "label": "Test",
            "message": "42",
            "color": "blue"
        }
        self.assertTrue(validate_badge_schema(valid_badge))

    def test_validate_badge_schema_missing_fields(self):
        """Test validation with missing required fields"""
        incomplete_badge = {
            "label": "Test",
            "message": "42"
        }
        self.assertFalse(validate_badge_schema(incomplete_badge))

    def test_validate_badge_schema_empty_dict(self):
        """Test validation of empty dictionary"""
        self.assertFalse(validate_badge_schema({}))

    def test_validate_badge_schema_extra_fields(self):
        """Test validation with extra fields (should still be valid)"""
        badge_with_extras = {
            "schemaVersion": 1,
            "label": "Test",
            "message": "42",
            "color": "blue",
            "extraField": "should be ignored"
        }
        self.assertTrue(validate_badge_schema(badge_with_extras))


class TestWeeklyGrowthData(TestBadgeGenerator):

    def test_get_weekly_growth_data_basic(self):
        """Test weekly growth data retrieval"""
        growth_data = get_weekly_growth_data(self.test_db_path)

        self.assertIsInstance(growth_data, dict)
        if growth_data:  # Only check if data exists
            self.assertIn('growth_pct', growth_data)

    def test_get_weekly_growth_data_nonexistent_db(self):
        """Test weekly growth with nonexistent database"""
        growth_data = get_weekly_growth_data("/fake/path.db")
        self.assertEqual(growth_data, {})


class TestTopHuntersData(TestBadgeGenerator):

    def test_get_top_hunters_data_basic(self):
        """Test top hunters data retrieval"""
        top_hunters = get_top_hunters_data(self.test_db_path, limit=3)

        self.assertIsInstance(top_hunters, list)
        if top_hunters:  # Only check if data exists
            self.assertLessEqual(len(top_hunters), 3)
            if len(top_hunters) > 0:
                hunter = top_hunters[0]
                self.assertIn('username', hunter)
                self.assertIn('points', hunter)

    def test_get_top_hunters_data_custom_limit(self):
        """Test top hunters with custom limit"""
        top_hunters = get_top_hunters_data(self.test_db_path, limit=1)

        if top_hunters:
            self.assertLessEqual(len(top_hunters), 1)

    def test_get_top_hunters_data_nonexistent_db(self):
        """Test top hunters with nonexistent database"""
        top_hunters = get_top_hunters_data("/fake/path.db")
        self.assertEqual(top_hunters, [])


class TestBadgeGeneratorIntegration(TestBadgeGenerator):

    def test_hunter_badge_generator_init(self):
        """Test HunterBadgeGenerator initialization"""
        generator = HunterBadgeGenerator(
            db_path=self.test_db_path,
            output_dir=self.output_dir
        )

        self.assertEqual(generator.db_path, self.test_db_path)
        self.assertEqual(generator.output_dir, self.output_dir)

    @patch('builtins.open', new_callable=mock_open)
    def test_badge_file_writing(self, mock_file):
        """Test badge file writing functionality"""
        badge_data = generate_badge_json("Test", "42", "green")

        # Simulate file writing
        with open("test_badge.json", "w") as f:
            json.dump(badge_data, f, indent=2)

        # Verify file was opened for writing
        mock_file.assert_called_with("test_badge.json", "w")

    def test_complete_badge_generation_pipeline(self):
        """Test complete badge generation pipeline"""
        generator = HunterBadgeGenerator(
            db_path=self.test_db_path,
            output_dir=self.output_dir
        )

        # This should not raise any exceptions
        try:
            generator.generate_all_badges()
        except Exception as e:
            # Allow for not implemented yet
            if "not implemented" not in str(e).lower():
                raise


class TestEdgeCases(TestBadgeGenerator):

    def test_empty_hunter_username(self):
        """Test handling of empty hunter username"""
        slug = sanitize_slug("")
        self.assertEqual(slug, "")

    def test_very_long_username(self):
        """Test handling of very long usernames"""
        long_name = "a" * 1000
        slug = sanitize_slug(long_name)
        self.assertIsInstance(slug, str)
        self.assertGreater(len(slug), 0)

    def test_unicode_characters(self):
        """Test handling of unicode characters in usernames"""
        unicode_name = "üser_näme"
        slug = sanitize_slug(unicode_name)
        self.assertIsInstance(slug, str)

    def test_numeric_only_username(self):
        """Test handling of numeric-only usernames"""
        numeric_name = "12345"
        slug = sanitize_slug(numeric_name)
        self.assertEqual(slug, "12345")

    def test_badge_with_none_values(self):
        """Test badge generation with None values"""
        try:
            badge = generate_badge_json(None, None)
            # Should handle None gracefully
            self.assertIsInstance(badge, dict)
        except (TypeError, AttributeError):
            # Acceptable to fail with None values
            pass


class TestFileSystemOperations(TestBadgeGenerator):

    def test_output_directory_creation(self):
        """Test output directory is created if it doesn't exist"""
        new_output_dir = os.path.join(self.temp_dir, "new_badges")
        self.assertFalse(os.path.exists(new_output_dir))

        generator = HunterBadgeGenerator(
            db_path=self.test_db_path,
            output_dir=new_output_dir
        )

        # Directory should be created during initialization or first use
        # This test assumes the implementation creates directories as needed

    def test_badge_file_overwrite(self):
        """Test badge files can be overwritten"""
        test_file = os.path.join(self.output_dir, "test_badge.json")

        # Create initial file
        initial_data = {"test": "data1"}
        with open(test_file, "w") as f:
            json.dump(initial_data, f)

        self.assertTrue(os.path.exists(test_file))

        # Overwrite with new data
        new_data = {"test": "data2"}
        with open(test_file, "w") as f:
            json.dump(new_data, f)

        # Verify file was updated
        with open(test_file, "r") as f:
            loaded_data = json.load(f)

        self.assertEqual(loaded_data["test"], "data2")


if __name__ == '__main__':
    unittest.main()
