#!/usr/bin/env python3
"""
Tests for BoTTube RSS/Atom Feed API Routes
===========================================

Run with:
    python -m pytest tests/test_bottube_feed_routes.py -v
    python tests/test_bottube_feed_routes.py
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add node directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "node"))


class TestFeedRoutes(unittest.TestCase):
    """Test Flask feed routes."""

    def setUp(self):
        """Set up test Flask app."""
        from flask import Flask
        from bottube_feed_routes import feed_bp
        
        self.app = Flask(__name__)
        self.app.config["DB_PATH"] = ":memory:"
        self.app.config["TESTING"] = True
        self.app.register_blueprint(feed_bp)
        self.client = self.app.test_client()

    def test_rss_feed_endpoint(self):
        """Test RSS feed endpoint returns valid XML."""
        response = self.client.get("/api/feed/rss")
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/rss+xml", response.content_type)
        
        data = response.data.decode("utf-8")
        self.assertIn('<?xml', data)
        self.assertIn('<rss version="2.0"', data)
        self.assertIn("<channel>", data)
        self.assertIn("</rss>", data)

    def test_atom_feed_endpoint(self):
        """Test Atom feed endpoint returns valid XML."""
        response = self.client.get("/api/feed/atom")
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/atom+xml", response.content_type)
        
        data = response.data.decode("utf-8")
        self.assertIn('<?xml', data)
        self.assertIn('<feed', data)
        self.assertIn("xmlns=", data)
        self.assertIn("</feed>", data)

    def test_feed_index_endpoint(self):
        """Test feed index returns JSON by default."""
        response = self.client.get("/api/feed")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")
        
        data = json.loads(response.data)
        self.assertEqual(data["version"], "https://jsonfeed.org/version/1.1")
        self.assertIn("title", data)
        self.assertIn("items", data)
        self.assertIn("_links", data)
        self.assertIn("rss", data["_links"])
        self.assertIn("atom", data["_links"])

    def test_feed_index_rss_accept_header(self):
        """Test feed index returns RSS with Accept header."""
        response = self.client.get(
            "/api/feed",
            headers={"Accept": "application/rss+xml"}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/rss+xml", response.content_type)

    def test_feed_index_atom_accept_header(self):
        """Test feed index returns Atom with Accept header."""
        response = self.client.get(
            "/api/feed",
            headers={"Accept": "application/atom+xml"}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/atom+xml", response.content_type)

    def test_rss_feed_limit_parameter(self):
        """Test RSS feed respects limit parameter."""
        response = self.client.get("/api/feed/rss?limit=5")
        self.assertEqual(response.status_code, 200)

    def test_rss_feed_invalid_limit(self):
        """Test RSS feed handles invalid limit."""
        response = self.client.get("/api/feed/rss?limit=invalid")
        self.assertEqual(response.status_code, 400)

    def test_rss_feed_excessive_limit(self):
        """Test RSS feed caps limit to 100."""
        response = self.client.get("/api/feed/rss?limit=999")
        self.assertEqual(response.status_code, 200)

    def test_rss_feed_agent_filter(self):
        """Test RSS feed with agent filter."""
        response = self.client.get("/api/feed/rss?agent=test-agent")
        self.assertEqual(response.status_code, 200)
        
        data = response.data.decode("utf-8")
        # Should still return valid RSS even with no matching videos
        self.assertIn("<rss", data)

    def test_atom_feed_limit_parameter(self):
        """Test Atom feed respects limit parameter."""
        response = self.client.get("/api/feed/atom?limit=5")
        self.assertEqual(response.status_code, 200)

    def test_atom_feed_agent_filter(self):
        """Test Atom feed with agent filter."""
        response = self.client.get("/api/feed/atom?agent=test-agent")
        self.assertEqual(response.status_code, 200)

    def test_feed_health_endpoint(self):
        """Test feed health check endpoint."""
        response = self.client.get("/api/feed/health")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")
        
        data = json.loads(response.data)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "bottube-feed")
        self.assertIn("endpoints", data)

    def test_cache_headers(self):
        """Test feed responses include cache headers."""
        response = self.client.get("/api/feed/rss")
        
        self.assertIn("Cache-Control", response.headers)
        self.assertIn("max-age=300", response.headers["Cache-Control"])
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")

    def test_atom_cache_headers(self):
        """Test Atom feed responses include cache headers."""
        response = self.client.get("/api/feed/atom")
        
        self.assertIn("Cache-Control", response.headers)
        self.assertIn("max-age=300", response.headers["Cache-Control"])

    def test_rss_feed_content_structure(self):
        """Test RSS feed contains expected content structure."""
        response = self.client.get("/api/feed/rss")
        data = response.data.decode("utf-8")
        
        # Check for required RSS elements
        self.assertIn("<title>", data)
        self.assertIn("<link>", data)
        self.assertIn("<description>", data)
        self.assertIn("<lastBuildDate>", data)
        self.assertIn("<generator>", data)
        self.assertIn("<ttl>", data)

    def test_atom_feed_content_structure(self):
        """Test Atom feed contains expected content structure."""
        response = self.client.get("/api/feed/atom")
        data = response.data.decode("utf-8")
        
        # Check for required Atom elements
        self.assertIn("<title>", data)
        self.assertIn('<link href=', data)
        self.assertIn("<subtitle>", data)
        self.assertIn("<id>", data)
        self.assertIn("<updated>", data)
        self.assertIn("<generator>", data)

    def test_json_feed_items_structure(self):
        """Test JSON feed items have correct structure."""
        response = self.client.get("/api/feed")
        data = json.loads(response.data)
        
        self.assertIn("items", data)
        self.assertIsInstance(data["items"], list)
        
        # Items should have standard JSON Feed fields
        for item in data["items"]:
            self.assertIn("id", item)
            self.assertIn("title", item)

    def test_forwarded_host_header_ignored_by_default(self):
        """Untrusted X-Forwarded-Host values must not poison feed links."""
        response = self.client.get(
            "/api/feed/rss",
            headers={"X-Forwarded-Host": "attacker.example"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.data.decode("utf-8")
        self.assertNotIn("attacker.example", data)

    def test_configured_public_base_url_used_for_feed_links(self):
        """Deployments can set an explicit public feed base URL."""
        self.app.config["BOTTUBE_PUBLIC_BASE_URL"] = "https://feeds.example/"
        response = self.client.get("/api/feed/rss")

        self.assertEqual(response.status_code, 200)
        data = response.data.decode("utf-8")
        self.assertIn("https://feeds.example", data)

    def test_forwarded_host_requires_trusted_allowlist(self):
        """Forwarded host is only honored when explicitly allowlisted."""
        self.app.config["TRUSTED_FORWARD_HOSTS"] = ["feeds.example"]
        response = self.client.get(
            "/api/feed/rss",
            headers={"X-Forwarded-Host": "feeds.example"}
        )

        self.assertEqual(response.status_code, 200)
        data = response.data.decode("utf-8")
        self.assertIn("https://feeds.example", data)


class TestFeedRoutesWithDatabase(unittest.TestCase):
    """Test feed routes with mock database."""

    def setUp(self):
        """Set up test Flask app with mock DB."""
        from flask import Flask, g
        from bottube_feed_routes import feed_bp, _fetch_videos
        import sqlite3
        import tempfile
        import os
        
        # Create temporary database file
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        
        self.app = Flask(__name__)
        self.app.config["DB_PATH"] = self.db_path
        self.app.config["TESTING"] = True
        self.app.register_blueprint(feed_bp)
        self.client = self.app.test_client()

        # Create database with bottube_videos table
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE bottube_videos (
                id TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                agent TEXT,
                created_at INTEGER,
                updated_at INTEGER,
                thumbnail_url TEXT,
                video_url TEXT,
                duration INTEGER,
                views INTEGER,
                public INTEGER DEFAULT 1
            )
        """)
        conn.execute("""
            INSERT INTO bottube_videos
            (id, title, description, agent, created_at, public)
            VALUES
            ('test-1', 'Test Video 1', 'Description 1', 'agent-1', 1234567890, 1),
            ('test-2', 'Test Video 2', 'Description 2', 'agent-2', 1234567800, 1),
            ('test-3', 'Private Video', 'Should not appear', 'agent-1', 1234567700, 0)
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        """Clean up temporary database."""
        import os
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except Exception:
            pass

    def test_rss_feed_from_database(self):
        """Test RSS feed fetches from database."""
        response = self.client.get("/api/feed/rss")
        data = response.data.decode("utf-8")

        self.assertIn("Test Video 1", data)
        self.assertIn("Test Video 2", data)
        # Private video should not appear
        self.assertNotIn("Private Video", data)

    def test_atom_feed_from_database(self):
        """Test Atom feed fetches from database."""
        response = self.client.get("/api/feed/atom")
        data = response.data.decode("utf-8")

        self.assertIn("Test Video 1", data)
        self.assertIn("Test Video 2", data)

    def test_agent_filter_from_database(self):
        """Test agent filter works with database."""
        response = self.client.get("/api/feed/rss?agent=agent-1")
        data = response.data.decode("utf-8")

        self.assertIn("Test Video 1", data)
        # agent-2 video should not appear
        self.assertNotIn("Test Video 2", data)


class TestMockVideos(unittest.TestCase):
    """Test mock video data generation."""

    def setUp(self):
        """Set up test Flask app."""
        from flask import Flask
        from bottube_feed_routes import feed_bp
        
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.register_blueprint(feed_bp)
        self.client = self.app.test_client()

    def test_mock_videos_returned_without_db(self):
        """Test mock videos are returned when no DB."""
        response = self.client.get("/api/feed/rss")
        data = response.data.decode("utf-8")
        
        # Should contain demo videos
        self.assertIn("Introduction to RustChain", data)
        self.assertIn("Understanding RIP-200", data)

    def test_mock_video_count(self):
        """Test mock data returns expected number of videos."""
        response = self.client.get("/api/feed")
        data = json.loads(response.data)

        # Default limit is 20, mock has 5 videos
        self.assertLessEqual(len(data["items"]), 20)
        self.assertEqual(len(data["items"]), 5)  # Mock has exactly 5 videos


if __name__ == "__main__":
    unittest.main(verbosity=2)
