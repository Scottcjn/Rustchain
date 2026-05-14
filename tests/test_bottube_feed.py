#!/usr/bin/env python3
"""
Tests for BoTTube RSS/Atom Feed Generator
==========================================

Run with:
    python -m pytest tests/test_bottube_feed.py -v
    python tests/test_bottube_feed.py
"""

import sys
import time
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

# Add node directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "node"))

from bottube_feed import (
    RSSFeedBuilder,
    AtomFeedBuilder,
    create_rss_feed_from_videos,
    create_atom_feed_from_videos,
    _format_rfc822_dt,
    _format_atom_dt,
    _generate_tag_uri,
    _compute_guid,
)


class TestDateTimeFormatting(unittest.TestCase):
    """Test date/time formatting utilities."""

    def test_rfc822_format(self):
        """Test RFC 822 date formatting for RSS."""
        dt = datetime(2026, 3, 12, 10, 30, 0, tzinfo=timezone.utc)
        formatted = _format_rfc822_dt(dt)
        self.assertIn("2026", formatted)
        self.assertIn("Mar", formatted)
        self.assertIn("Thu", formatted)

    def test_rfc822_format_no_tz(self):
        """Test RFC 822 formatting adds UTC when no timezone."""
        dt = datetime(2026, 3, 12, 10, 30, 0)
        formatted = _format_rfc822_dt(dt)
        self.assertIn("+0000", formatted)

    def test_atom_format(self):
        """Test ISO 8601 date formatting for Atom."""
        dt = datetime(2026, 3, 12, 10, 30, 0, tzinfo=timezone.utc)
        formatted = _format_atom_dt(dt)
        self.assertEqual(formatted, "2026-03-12T10:30:00Z")

    def test_atom_format_no_tz(self):
        """Test Atom formatting adds UTC when no timezone."""
        dt = datetime(2026, 3, 12, 10, 30, 0)
        formatted = _format_atom_dt(dt)
        self.assertIn("Z", formatted)


class TestTagURI(unittest.TestCase):
    """Test TAG URI generation."""

    def test_tag_uri_format(self):
        """Test TAG URI format."""
        uri = _generate_tag_uri("https://bottube.ai", "video:123")
        self.assertTrue(uri.startswith("tag:"))
        self.assertIn("bottube.ai", uri)
        self.assertIn("video:123", uri)


class TestGUID(unittest.TestCase):
    """Test GUID computation."""

    def test_guid_with_id(self):
        """Test GUID generation with video ID."""
        video = {"id": "abc123"}
        guid = _compute_guid(video, "https://bottube.ai")
        self.assertEqual(guid, "https://bottube.ai/video/abc123")

    def test_guid_without_id(self):
        """Test GUID generation without video ID uses hash."""
        video = {"title": "Test", "agent": "bot", "created_at": "12345"}
        guid = _compute_guid(video, "https://bottube.ai")
        self.assertTrue(guid.startswith("https://bottube.ai/video/"))
        self.assertGreater(len(guid), 30)


class TestRSSFeedBuilder(unittest.TestCase):
    """Test RSS feed builder."""

    def setUp(self):
        """Set up test fixtures."""
        self.builder = RSSFeedBuilder(
            title="Test Feed",
            link="https://example.com",
            description="Test Description"
        )

    def test_builder_initialization(self):
        """Test builder initializes with correct values."""
        self.assertEqual(self.builder.title, "Test Feed")
        self.assertEqual(self.builder.link, "https://example.com")
        self.assertEqual(self.builder.description, "Test Description")

    def test_add_item(self):
        """Test adding items to feed."""
        self.builder.add_item(
            title="Test Video",
            link="https://example.com/video/1",
            description="Test Description"
        )
        self.assertEqual(len(self.builder.items), 1)
        self.assertEqual(self.builder.items[0]["title"], "Test Video")

    def test_add_item_chain(self):
        """Test method chaining for add_item."""
        result = self.builder.add_item(
            title="Video 1",
            link="https://example.com/1",
            description="Desc 1"
        )
        self.assertIs(result, self.builder)

    def test_add_video(self):
        """Test adding video from data dict."""
        video = {
            "id": "vid123",
            "title": "My Video",
            "description": "Video description",
            "agent": "test-agent",
            "created_at": time.time() - 3600,
            "thumbnail_url": "https://example.com/thumb.jpg",
            "video_url": "https://example.com/video.mp4",
            "tags": ["test", "demo"],
        }
        self.builder.add_video(video)
        self.assertEqual(len(self.builder.items), 1)

    def test_add_video_with_datetime(self):
        """Test adding video with datetime created_at."""
        video = {
            "id": "vid123",
            "title": "My Video",
            "description": "Video description",
            "created_at": datetime.now(timezone.utc),
        }
        self.builder.add_video(video)
        self.assertEqual(len(self.builder.items), 1)

    def test_build_output(self):
        """Test RSS feed XML output."""
        self.builder.add_item(
            title="Test",
            link="https://example.com/1",
            description="Test desc"
        )
        xml = self.builder.build()
        
        self.assertIn('<?xml version="1.0" encoding="UTF-8"?>', xml)
        self.assertIn('<rss version="2.0"', xml)
        self.assertIn("<channel>", xml)
        self.assertIn("<title>Test Feed</title>", xml)
        self.assertIn("<item>", xml)
        self.assertIn("</rss>", xml)

    def test_build_bytes(self):
        """Test RSS feed bytes output."""
        self.builder.add_item(
            title="Test",
            link="https://example.com/1",
            description="Test desc"
        )
        xml_bytes = self.builder.build_bytes()
        self.assertIsInstance(xml_bytes, bytes)
        self.assertTrue(xml_bytes.startswith(b'<?xml'))

    def test_xml_escaping(self):
        """Test XML special characters are escaped."""
        self.builder.add_item(
            title="Test & Demo <Video>",
            link="https://example.com/1",
            description="Description with 'quotes' and \"double quotes\""
        )
        xml = self.builder.build()
        self.assertIn("&amp;", xml)
        self.assertIn("&lt;", xml)
        self.assertIn("&gt;", xml)

    def test_enclosure(self):
        """Test media enclosure in RSS item."""
        self.builder.add_item(
            title="Test",
            link="https://example.com/1",
            description="Test",
            enclosure_url="https://example.com/video.mp4",
            enclosure_type="video/mp4",
            enclosure_length=1234567
        )
        xml = self.builder.build()
        self.assertIn('enclosure', xml)
        self.assertIn('video.mp4', xml)
        self.assertIn('1234567', xml)

    def test_thumbnail(self):
        """Test media thumbnail extension."""
        self.builder.add_item(
            title="Test",
            link="https://example.com/1",
            description="Test",
            thumbnail_url="https://example.com/thumb.jpg"
        )
        xml = self.builder.build()
        self.assertIn("media:thumbnail", xml)


class TestAtomFeedBuilder(unittest.TestCase):
    """Test Atom feed builder."""

    def setUp(self):
        """Set up test fixtures."""
        self.builder = AtomFeedBuilder(
            title="Test Atom Feed",
            link="https://example.com",
            subtitle="Test Subtitle"
        )

    def test_builder_initialization(self):
        """Test builder initializes with correct values."""
        self.assertEqual(self.builder.title, "Test Atom Feed")
        self.assertEqual(self.builder.link, "https://example.com")
        self.assertEqual(self.builder.subtitle, "Test Subtitle")

    def test_add_entry(self):
        """Test adding entries to feed."""
        self.builder.add_entry(
            title="Test Entry",
            entry_id="urn:test:1",
            link="https://example.com/1",
            summary="Test Summary"
        )
        self.assertEqual(len(self.builder.entries), 1)
        self.assertEqual(self.builder.entries[0]["title"], "Test Entry")

    def test_add_entry_chain(self):
        """Test method chaining for add_entry."""
        result = self.builder.add_entry(
            title="Entry 1",
            entry_id="urn:1",
            link="https://example.com/1",
            summary="Summary 1"
        )
        self.assertIs(result, self.builder)

    def test_add_video(self):
        """Test adding video from data dict."""
        video = {
            "id": "vid123",
            "title": "My Video",
            "description": "Video description",
            "agent": "test-agent",
            "created_at": time.time() - 3600,
            "updated_at": time.time() - 1800,
            "thumbnail_url": "https://example.com/thumb.jpg",
            "video_url": "https://example.com/video.mp4",
            "tags": ["test", "demo"],
        }
        self.builder.add_video(video)
        self.assertEqual(len(self.builder.entries), 1)

    def test_build_output(self):
        """Test Atom feed XML output."""
        self.builder.add_entry(
            title="Test",
            entry_id="urn:test:1",
            link="https://example.com/1",
            summary="Test summary"
        )
        xml = self.builder.build()
        
        self.assertIn('<?xml version="1.0" encoding="UTF-8"?>', xml)
        self.assertIn('xmlns="http://www.w3.org/2005/Atom"', xml)
        self.assertIn("<feed", xml)
        self.assertIn("<title>Test Atom Feed</title>", xml)
        self.assertIn("<entry>", xml)
        self.assertIn("</feed>", xml)

    def test_build_bytes(self):
        """Test Atom feed bytes output."""
        self.builder.add_entry(
            title="Test",
            entry_id="urn:test:1",
            link="https://example.com/1",
            summary="Test"
        )
        xml_bytes = self.builder.build_bytes()
        self.assertIsInstance(xml_bytes, bytes)
        self.assertTrue(xml_bytes.startswith(b'<?xml'))

    def test_author_element(self):
        """Test author element in Atom."""
        builder = AtomFeedBuilder(
            title="Test",
            link="https://example.com",
            author_name="Test Author",
            author_email="test@example.com"
        )
        xml = builder.build()
        self.assertIn("<author>", xml)
        self.assertIn("<name>Test Author</name>", xml)
        self.assertIn("<email>test@example.com</email>", xml)

    def test_media_content(self):
        """Test media content extension."""
        self.builder.add_entry(
            title="Test",
            entry_id="urn:test:1",
            link="https://example.com/1",
            summary="Test",
            media_url="https://example.com/video.mp4",
            media_type="video/mp4"
        )
        xml = self.builder.build()
        self.assertIn("media:content", xml)
        self.assertIn("video.mp4", xml)

    def test_thumbnail_feed_is_well_formed_xml(self):
        """Test Atom feed with thumbnail parses as XML."""
        self.builder.add_entry(
            title="Test",
            entry_id="urn:test:1",
            link="https://example.com/1",
            summary="Test",
            thumbnail_url="https://example.com/thumb.jpg"
        )

        xml = self.builder.build()
        root = ET.fromstring(xml)
        thumbnail = root.find(
            ".//{http://search.yahoo.com/mrss/}thumbnail"
        )

        self.assertIsNotNone(thumbnail)
        self.assertEqual(thumbnail.attrib["url"], "https://example.com/thumb.jpg")


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""

    def test_create_rss_feed_from_videos(self):
        """Test RSS feed creation from video list."""
        videos = [
            {
                "id": "vid1",
                "title": "Video 1",
                "description": "Description 1",
                "created_at": time.time() - 3600,
            },
            {
                "id": "vid2",
                "title": "Video 2",
                "description": "Description 2",
                "created_at": time.time() - 7200,
            },
        ]
        
        rss = create_rss_feed_from_videos(
            videos=videos,
            base_url="https://bottube.ai",
            title="BoTTube Videos",
            limit=10
        )
        
        self.assertIn("<rss", rss)
        self.assertIn("Video 1", rss)
        self.assertIn("Video 2", rss)

    def test_create_atom_feed_from_videos(self):
        """Test Atom feed creation from video list."""
        videos = [
            {
                "id": "vid1",
                "title": "Video 1",
                "description": "Description 1",
                "created_at": time.time() - 3600,
            },
        ]
        
        atom = create_atom_feed_from_videos(
            videos=videos,
            base_url="https://bottube.ai",
            title="BoTTube Videos",
            limit=10
        )
        
        self.assertIn("<feed", atom)
        self.assertIn("Video 1", atom)

    def test_limit_applied(self):
        """Test that limit is applied correctly."""
        videos = [
            {"id": f"vid{i}", "title": f"Video {i}", "description": "Desc", "created_at": time.time()}
            for i in range(50)
        ]
        
        rss = create_rss_feed_from_videos(videos=videos, limit=10)
        # Count items
        item_count = rss.count("<item>")
        self.assertEqual(item_count, 10)


class TestFeedValidation(unittest.TestCase):
    """Test feed validation aspects."""

    def test_rss_has_atom_self_link(self):
        """Test RSS feed includes Atom self link for compatibility."""
        builder = RSSFeedBuilder(title="Test", link="https://example.com")
        builder.add_item(title="Test", link="https://example.com/1", description="Test")
        xml = builder.build()
        
        self.assertIn('atom:link', xml)
        self.assertIn('rel="self"', xml)
        self.assertIn("application/rss+xml", xml)

    def test_atom_has_self_link(self):
        """Test Atom feed includes self link."""
        builder = AtomFeedBuilder(title="Test", link="https://example.com")
        builder.add_entry(title="Test", entry_id="urn:1", link="https://example.com/1", summary="Test")
        xml = builder.build()
        
        self.assertIn('rel="self"', xml)
        self.assertIn("application/atom+xml", xml)

    def test_rss_has_media_namespace(self):
        """Test RSS feed includes media namespace."""
        builder = RSSFeedBuilder(title="Test", link="https://example.com")
        xml = builder.build()
        self.assertIn("xmlns:media=", xml)

    def test_atom_has_media_namespace(self):
        """Test Atom feed includes media namespace."""
        builder = AtomFeedBuilder(title="Test", link="https://example.com")
        xml = builder.build()
        self.assertIn("xmlns:media=", xml)


if __name__ == "__main__":
    unittest.main(verbosity=2)
