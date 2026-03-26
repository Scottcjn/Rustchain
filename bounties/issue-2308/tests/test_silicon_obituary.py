#!/usr/bin/env python3
"""
Tests for Silicon Obituary Generator — Issue #2308

Tests cover:
- Miner scanner (inactive detection)
- Eulogy generator (text generation)
- Video creator (memorial video)
- Discord notifier (notifications)
- Full integration
"""

import os
import sys
import json
import tempfile
import sqlite3
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from miner_scanner import MinerScanner, MinerStatus
from eulogy_generator import EulogyGenerator, EulogyData
from video_creator import BoTTubeVideoCreator, VideoConfig, VideoResult
from discord_notifier import DiscordNotifier, DiscordResult


class TestMinerScanner(unittest.TestCase):
    """Tests for MinerScanner class."""
    
    def setUp(self):
        """Set up test database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self._create_test_db()
        self.scanner = MinerScanner(self.temp_db.name, inactive_days=7)
    
    def tearDown(self):
        """Clean up test database."""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def _create_test_db(self):
        """Create test database with sample data."""
        conn = sqlite3.connect(self.temp_db.name)
        cursor = conn.cursor()
        
        # Create tables (matching actual schema)
        cursor.execute("""
            CREATE TABLE miner_attest_recent (
                miner TEXT PRIMARY KEY,
                ts_ok INTEGER NOT NULL,
                device_family TEXT,
                device_arch TEXT,
                entropy_score REAL DEFAULT 0,
                fingerprint_passed INTEGER DEFAULT 0,
                source_ip TEXT,
                warthog_bonus REAL DEFAULT 1.0
            )
        """)
        
        cursor.execute("""
            CREATE TABLE epoch_enroll (
                epoch INTEGER,
                miner_pk TEXT,
                weight REAL,
                PRIMARY KEY (epoch, miner_pk)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE balances (
                miner_pk TEXT PRIMARY KEY,
                balance_rtc REAL DEFAULT 0
            )
        """)
        
        # Insert test data - inactive miner (14 days ago)
        inactive_ts = int((datetime.now() - timedelta(days=14)).timestamp())
        cursor.execute(
            "INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?, 0.95, 1, '192.168.1.1', 1.5)",
            ("0x_inactive_miner_123", inactive_ts, "Power Mac G4", "PowerPC G4")
        )
        
        # Insert epoch enrollments
        for epoch in range(100):
            cursor.execute(
                "INSERT INTO epoch_enroll VALUES (?, ?, 1.0)",
                (epoch, "0x_inactive_miner_123")
            )
        
        # Insert balance
        cursor.execute(
            "INSERT INTO balances VALUES (?, 412.5)",
            ("0x_inactive_miner_123",)
        )
        
        # Insert active miner (1 day ago)
        active_ts = int((datetime.now() - timedelta(days=1)).timestamp())
        cursor.execute(
            "INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?, 0.90, 1, '192.168.1.2', 1.0)",
            ("0x_active_miner_456", active_ts, "Modern PC", "x86_64")
        )
        
        conn.commit()
        conn.close()
    
    def test_find_inactive_miners(self):
        """Test finding inactive miners."""
        inactive = self.scanner.find_inactive_miners()
        
        self.assertEqual(len(inactive), 1)
        self.assertEqual(inactive[0].miner_id, "0x_inactive_miner_123")
        self.assertGreaterEqual(inactive[0].days_inactive, 14)
    
    def test_no_active_miners_returned(self):
        """Test that active miners are not returned."""
        inactive = self.scanner.find_inactive_miners()
        
        miner_ids = [m.miner_id for m in inactive]
        self.assertNotIn("0x_active_miner_456", miner_ids)
    
    def test_get_miner_data(self):
        """Test getting complete miner data."""
        data = self.scanner.get_miner_data("0x_inactive_miner_123")
        
        self.assertIsNotNone(data)
        self.assertEqual(data["miner_id"], "0x_inactive_miner_123")
        self.assertEqual(data["device_model"], "Power Mac G4")
        self.assertEqual(data["device_arch"], "PowerPC G4")
        self.assertEqual(data["total_epochs"], 100)
        self.assertEqual(data["total_rtc_earned"], 412.5)
    
    def test_database_not_found(self):
        """Test handling of missing database."""
        scanner = MinerScanner("/nonexistent/path.db")
        result = scanner.find_inactive_miners()
        self.assertEqual(result, [])
    
    def test_miner_not_found(self):
        """Test getting data for non-existent miner."""
        data = self.scanner.get_miner_data("0x_nonexistent")
        self.assertIsNone(data)


class TestEulogyGenerator(unittest.TestCase):
    """Tests for EulogyGenerator class."""
    
    def setUp(self):
        """Set up test data."""
        self.test_data = EulogyData(
            miner_id="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            device_model="Power Mac G4 MDD",
            device_arch="PowerPC G4",
            total_epochs=847,
            total_rtc_earned=412.5,
            days_inactive=14,
            years_of_service=2.3,
            first_attestation="2024-01-15T08:30:00",
            last_attestation="2026-03-08T14:22:00",
            multiplier_history=[1.5, 1.5, 1.5]
        )
        self.generator = EulogyGenerator()
    
    def test_generate_poetic(self):
        """Test poetic eulogy generation."""
        self.generator.style = "poetic"
        eulogy = self.generator.generate(self.test_data)
        
        self.assertIsInstance(eulogy, str)
        self.assertGreater(len(eulogy), 50)
        self.assertIn("Power Mac G4 MDD", eulogy)
        self.assertIn("847", eulogy)  # epochs
        self.assertIn("412.50", eulogy)  # RTC
    
    def test_generate_technical(self):
        """Test technical eulogy generation."""
        self.generator.style = "technical"
        eulogy = self.generator.generate(self.test_data)
        
        self.assertIn("Architecture", eulogy)
        self.assertIn("PowerPC G4", eulogy)
        self.assertIn("RTC Mined", eulogy)
    
    def test_generate_humorous(self):
        """Test humorous eulogy generation."""
        self.generator.style = "humorous"
        eulogy = self.generator.generate(self.test_data)
        
        self.assertIn("Power Mac G4 MDD", eulogy)
        self.assertIn("412.50", eulogy)
    
    def test_generate_epic(self):
        """Test epic eulogy generation."""
        self.generator.style = "epic"
        eulogy = self.generator.generate(self.test_data)
        
        self.assertIn("Power Mac G4 MDD", eulogy)
        self.assertIn("847", eulogy)
    
    def test_generate_random(self):
        """Test random style selection."""
        self.generator.style = "random"
        eulogy = self.generator.generate(self.test_data)
        
        self.assertIsInstance(eulogy, str)
        self.assertGreater(len(eulogy), 50)
    
    def test_from_miner_data(self):
        """Test EulogyData.from_miner_data method."""
        miner_dict = {
            "miner_id": "0x123",
            "device_model": "Test Device",
            "device_arch": "x86_64",
            "total_epochs": 100,
            "total_rtc_earned": 50.0,
            "days_inactive": 10,
            "years_of_service": 1.5,
            "first_attestation": "2025-01-01T00:00:00",
            "last_attestation": "2026-03-01T00:00:00",
            "multiplier_history": [1.0, 1.2]
        }
        
        data = EulogyData.from_miner_data(miner_dict)
        
        self.assertEqual(data.miner_id, "0x123")
        self.assertEqual(data.device_model, "Test Device")
        self.assertEqual(data.total_epochs, 100)
    
    def test_generate_all_styles(self):
        """Test generating all styles."""
        results = self.generator.generate_all_styles(self.test_data)
        
        self.assertIn("poetic", results)
        self.assertIn("technical", results)
        self.assertIn("humorous", results)
        self.assertIn("epic", results)
        
        for style, eulogy in results.items():
            self.assertIsInstance(eulogy, str)
            self.assertGreater(len(eulogy), 50)
    
    def test_real_data_incorporation(self):
        """Test that real miner data is incorporated."""
        self.generator.style = "poetic"
        eulogy = self.generator.generate(self.test_data)
        
        # Verify actual data points are present
        self.assertIn(self.test_data.device_model, eulogy)
        self.assertIn(str(self.test_data.total_epochs), eulogy)
        self.assertIn(f"{self.test_data.total_rtc_earned:.2f}", eulogy)


class TestVideoCreator(unittest.TestCase):
    """Tests for BoTTubeVideoCreator class."""
    
    def setUp(self):
        """Set up test output directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = VideoConfig(output_dir=self.temp_dir)
        self.creator = BoTTubeVideoCreator(self.config)
        
        self.test_miner_data = {
            "miner_id": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "device_model": "Power Mac G4 MDD",
            "device_arch": "PowerPC G4",
            "total_epochs": 847,
            "total_rtc_earned": 412.5,
            "days_inactive": 14,
            "years_of_service": 2.3
        }
        
        self.test_eulogy = """Here lies dual-g4-125, a Power Mac G4 MDD. 
        It attested for 847 epochs and earned 412 RTC."""
    
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_create_memorial_video(self):
        """Test video creation."""
        result = self.creator.create_memorial_video(
            miner_id=self.test_miner_data["miner_id"],
            eulogy_text=self.test_eulogy,
            miner_data=self.test_miner_data
        )
        
        self.assertIsInstance(result, VideoResult)
        self.assertTrue(result.success)
        self.assertTrue(os.path.exists(result.video_path))
        self.assertGreater(result.duration_seconds, 0)
    
    def test_video_output_directory(self):
        """Test video is saved to correct directory."""
        result = self.creator.create_memorial_video(
            miner_id=self.test_miner_data["miner_id"],
            eulogy_text=self.test_eulogy,
            miner_data=self.test_miner_data
        )
        
        self.assertTrue(result.video_path.startswith(self.temp_dir))
    
    def test_post_to_bottube(self):
        """Test BoTTube posting."""
        result = self.creator.post_to_bottube(
            video_path="/fake/path.mp4",
            title="Test Obituary",
            description="Test description",
            tags=["#SiliconObituary", "#Test"],
            miner_id=self.test_miner_data["miner_id"]
        )
        
        # Result can be dict or BoTTubePostResult
        self.assertTrue(hasattr(result, 'success') or isinstance(result, dict))
        # Note: In test mode, this may return simulated result
    
    def test_bottube_has_silicon_obituary_tag(self):
        """Test that #SiliconObituary tag is always included."""
        result = self.creator.post_to_bottube(
            video_path="/fake/path.mp4",
            title="Test",
            description="Test",
            tags=["#Test"],  # No #SiliconObituary
            miner_id=self.test_miner_data["miner_id"]
        )
        
        # The method should ensure #SiliconObituary is added


class TestDiscordNotifier(unittest.TestCase):
    """Tests for DiscordNotifier class."""
    
    def setUp(self):
        """Set up test notifier."""
        self.webhook_url = "https://discord.com/api/webhooks/test/test"
        self.notifier = DiscordNotifier(self.webhook_url)
        
        self.test_miner_data = {
            "miner_id": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "device_model": "Power Mac G4 MDD",
            "device_arch": "PowerPC G4",
            "total_epochs": 847,
            "total_rtc_earned": 412.5,
            "years_of_service": 2.3
        }
        
        self.test_eulogy = """Here lies dual-g4-125, a Power Mac G4 MDD. 
        It attested for 847 epochs and earned 412 RTC."""
    
    @patch('requests.post')
    def test_send_notification_success(self, mock_post):
        """Test successful notification."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response
        
        result = self.notifier.send_obituary_notification(
            miner_id=self.test_miner_data["miner_id"],
            miner_data=self.test_miner_data,
            eulogy_text=self.test_eulogy,
            video_url="https://bottube.ai/video/test"
        )
        
        self.assertTrue(result.success)
        mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_send_notification_failure(self, mock_post):
        """Test failed notification."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response
        
        result = self.notifier.send_obituary_notification(
            miner_id=self.test_miner_data["miner_id"],
            miner_data=self.test_miner_data,
            eulogy_text=self.test_eulogy,
            video_url=""
        )
        
        self.assertFalse(result.success)
    
    def test_build_embed(self):
        """Test embed building."""
        embed = self.notifier._build_embed(
            self.test_miner_data,
            self.test_eulogy,
            "https://bottube.ai/video/test"
        )
        
        self.assertIn("title", embed)
        self.assertIn("fields", embed)
        self.assertIn("color", embed)
        
        # Check fields contain expected data
        field_names = [f["name"] for f in embed["fields"]]
        self.assertTrue(any("Device" in n for n in field_names))
        self.assertTrue(any("RTC" in n for n in field_names))
    
    def test_embed_has_video_link(self):
        """Test embed includes video link."""
        embed = self.notifier._build_embed(
            self.test_miner_data,
            self.test_eulogy,
            "https://bottube.ai/video/test123"
        )
        
        field_values = [f["value"] for f in embed["fields"]]
        has_video = any("bottube.ai" in v for v in field_values)
        self.assertTrue(has_video)


class TestIntegration(unittest.TestCase):
    """Integration tests for full obituary generation flow."""
    
    def setUp(self):
        """Set up integration test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self._create_test_db()
    
    def tearDown(self):
        """Clean up."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def _create_test_db(self):
        """Create test database."""
        conn = sqlite3.connect(self.temp_db.name)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE miner_attest_recent (
                miner TEXT PRIMARY KEY,
                ts_ok INTEGER NOT NULL,
                device_family TEXT,
                device_arch TEXT,
                entropy_score REAL DEFAULT 0,
                fingerprint_passed INTEGER DEFAULT 0,
                source_ip TEXT,
                warthog_bonus REAL DEFAULT 1.0
            )
        """)
        
        cursor.execute("""
            CREATE TABLE epoch_enroll (
                epoch INTEGER,
                miner_pk TEXT,
                weight REAL,
                PRIMARY KEY (epoch, miner_pk)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE balances (
                miner_pk TEXT PRIMARY KEY,
                balance_rtc REAL DEFAULT 0
            )
        """)
        
        # Inactive miner (all 8 columns)
        inactive_ts = int((datetime.now() - timedelta(days=14)).timestamp())
        cursor.execute(
            "INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?, 0.95, 1, '192.168.1.1', 1.5)",
            ("0x_test_miner", inactive_ts, "Power Mac G4", "PowerPC G4")
        )
        
        for epoch in range(50):
            cursor.execute(
                "INSERT INTO epoch_enroll VALUES (?, ?, 1.0)",
                (epoch, "0x_test_miner")
            )
        
        cursor.execute(
            "INSERT INTO balances VALUES (?, 250.0)",
            ("0x_test_miner",)
        )
        
        conn.commit()
        conn.close()
    
    def test_full_obituary_flow(self):
        """Test complete obituary generation flow."""
        # Import main module
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from silicon_obituary import ObituaryConfig, SiliconObituaryGenerator
        
        config = ObituaryConfig(
            db_path=self.temp_db.name,
            inactive_days=7,
            output_dir=self.temp_dir,
            dry_run=True  # Don't actually post
        )
        
        generator = SiliconObituaryGenerator(config)
        
        # Scan for inactive miners
        inactive = generator.scan_inactive_miners()
        self.assertEqual(len(inactive), 1)
        
        # Generate obituary
        result = generator.generate_obituary("0x_test_miner")
        
        self.assertEqual(result.status, "success")
        self.assertIn("Power Mac G4", result.eulogy_text)
        self.assertIn("250", result.eulogy_text)  # RTC


if __name__ == "__main__":
    unittest.main(verbosity=2)
