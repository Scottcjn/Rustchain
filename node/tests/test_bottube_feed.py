#!/usr/bin/env python3
"""
Tests for bottube_feed.py — BoTTube RSS/Atom Feed Generator

Covers:
- RSSFeedBuilder: basic build, items, video data, edge cases
- AtomFeedBuilder: basic build, items, video data, edge cases
- Helper functions: _format_rfc822_dt, _format_atom_dt, _generate_tag_uri, _compute_guid
- XML validity and content assertions
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from node.bottube_feed import (
    RSSFeedBuilder,
    AtomFeedBuilder,
    _format_rfc822_dt,
    _format_atom_dt,
    _generate_tag_uri,
    _compute_guid,
)


# ============================================================================
# Helper Function Tests
# ============================================================================

class TestFormatRfc822:
    def test_utc_datetime(self):
        """RFC 822 formatting for UTC datetime."""
        dt = datetime(2026, 5, 25, 12, 0, 0, tzinfo=timezone.utc)
        result = _format_rfc822_dt(dt)
        assert "Mon, 25 May 2026 12:00:00 +0000" in result

    def test_naive_datetime(self):
        """Naive datetime should be treated as UTC."""
        dt = datetime(2026, 1, 1, 0, 0, 0)
        result = _format_rfc822_dt(dt)
        assert "+0000" in result

    def test_epoch_datetime(self):
        """Epoch datetime should format correctly."""
        dt = datetime(2026, 5, 25, 6, 30, 0, tzinfo=timezone.utc)
        result = _format_rfc822_dt(dt)
        assert "Mon, 25 May 2026" in result

    def test_formats_weekday_correctly(self):
        """Weekday should be correct for various dates."""
        cases = [
            (datetime(2026, 5, 25, tzinfo=timezone.utc), "Mon"),
            (datetime(2026, 5, 26, tzinfo=timezone.utc), "Tue"),
            (datetime(2026, 5, 27, tzinfo=timezone.utc), "Wed"),
            (datetime(2026, 5, 28, tzinfo=timezone.utc), "Thu"),
            (datetime(2026, 5, 29, tzinfo=timezone.utc), "Fri"),
            (datetime(2026, 5, 30, tzinfo=timezone.utc), "Sat"),
            (datetime(2026, 5, 31, tzinfo=timezone.utc), "Sun"),
        ]
        for dt, expected_day in cases:
            result = _format_rfc822_dt(dt)
            assert result.startswith(expected_day), f"Expected {expected_day}, got {result}"


class TestFormatAtomDt:
    def test_iso_format(self):
        """Atom datetime should be ISO 8601 format."""
        dt = datetime(2026, 5, 25, 12, 0, 0, tzinfo=timezone.utc)
        result = _format_atom_dt(dt)
        assert result == "2026-05-25T12:00:00Z"

    def test_naive_datetime(self):
        """Naive datetime should be treated as UTC."""
        dt = datetime(2026, 1, 1, 0, 0, 0)
        result = _format_atom_dt(dt)
        assert result == "2026-01-01T00:00:00Z"

    def test_edge_century(self):
        """Year 2000 boundaries should work."""
        dt = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = _format_atom_dt(dt)
        assert result == "2000-01-01T00:00:00Z"


class TestGenerateTagUri:
    def test_basic_tag(self):
        """TAG URI should contain domain and date."""
        result = _generate_tag_uri("https://bottube.ai", "video-123")
        assert result.startswith("tag:bottube.ai,")
        assert "video-123" in result

    def test_http_url(self):
        """HTTP URLs should be handled (stripped to domain)."""
        result = _generate_tag_uri("http://example.com", "item-1")
        assert result.startswith("tag:example.com,")

    def test_url_with_path(self):
        """URLs with paths should extract domain correctly."""
        result = _generate_tag_uri("https://bottube.ai/videos/feed", "item-1")
        assert result.startswith("tag:bottube.ai,")
        assert "item-1" in result


class TestComputeGuid:
    def test_with_video_id(self):
        """GUID should use video ID when available."""
        video = {"id": "demo-001", "title": "Test", "agent": "test-agent", "created_at": 1000}
        result = _compute_guid(video, "https://bottube.ai")
        assert result == "https://bottube.ai/video/demo-001"

    def test_without_video_id(self):
        """GUID should fall back to hash when no video ID."""
        video = {"title": "Test Video", "agent": "test-agent", "created_at": 1234567890}
        result = _compute_guid(video, "https://bottube.ai")
        assert result.startswith("https://bottube.ai/video/")
        assert len(result) > len("https://bottube.ai/video/")

    def test_reproducible_hash(self):
        """Same inputs should produce same hash-based GUID."""
        video = {"title": "Deterministic", "agent": "hash-test", "created_at": 500}
        r1 = _compute_guid(video, "https://bottube.ai")
        r2 = _compute_guid(video, "https://bottube.ai")
        assert r1 == r2

    def test_different_inputs_different_hash(self):
        """Different inputs should produce different GUIDs."""
        v1 = {"title": "Video A", "agent": "agent-a", "created_at": 100}
        v2 = {"title": "Video B", "agent": "agent-b", "created_at": 200}
        r1 = _compute_guid(v1, "https://bottube.ai")
        r2 = _compute_guid(v2, "https://bottube.ai")
        assert r1 != r2

    def test_empty_data(self):
        """Empty video data should still produce a GUID."""
        result = _compute_guid({}, "https://bottube.ai")
        assert result.startswith("https://bottube.ai/video/")


# ============================================================================
# RSSFeedBuilder Tests
# ============================================================================

class TestRSSFeedBuilderInit:
    def test_default_values(self):
        """Default constructor should set reasonable values."""
        feed = RSSFeedBuilder(title="Test Feed", link="https://bottube.ai")
        assert feed.title == "Test Feed"
        assert feed.link == "https://bottube.ai"
        assert feed.description == "BoTTube Video Feed"
        assert feed.language == "en-us"
        assert feed.ttl == 60
        assert feed.items == []

    def test_custom_values(self):
        """Custom constructor values should be respected."""
        feed = RSSFeedBuilder(
            title="Custom",
            link="https://example.com/",
            description="Custom Description",
            language="fr-fr",
            copyright_text="© 2026",
            managing_editor="editor@example.com",
            web_master="webmaster@example.com",
            ttl=120,
            generator="Custom/1.0",
        )
        assert feed.title == "Custom"
        assert feed.link == "https://example.com"
        assert feed.language == "fr-fr"
        assert feed.ttl == 120

    def test_link_trailing_slash_stripped(self):
        """Trailing slash on link should be stripped."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai/")
        assert feed.link == "https://bottube.ai"


class TestRSSFeedBuilderItems:
    def test_add_item(self):
        """Adding an item should append to items list."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        feed.add_item(title="Item 1", link="https://bottube.ai/video/1", description="Desc 1")
        assert len(feed.items) == 1
        assert feed.items[0]["title"] == "Item 1"

    def test_add_item_returns_self(self):
        """add_item should return self for chaining."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        r = feed.add_item(title="T", link="https://bottube.ai/video/1", description="D")
        assert r is feed

    def test_add_multiple_items(self):
        """Multiple items should all be stored."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        feed.add_item(title="A", link="https://bottube.ai/video/1", description="D1")
        feed.add_item(title="B", link="https://bottube.ai/video/2", description="D2")
        feed.add_item(title="C", link="https://bottube.ai/video/3", description="D3")
        assert len(feed.items) == 3

    def test_add_item_with_all_fields(self):
        """Items with all optional fields should be stored correctly."""
        now = datetime.now(timezone.utc)
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        feed.add_item(
            title="Full Item",
            link="https://bottube.ai/video/full",
            description="Full description",
            author="test-agent",
            category="tutorial",
            guid="custom-guid",
            pub_date=now,
            enclosure_url="https://bottube.ai/videos/full.mp4",
            enclosure_type="video/mp4",
            enclosure_length=1048576,
            thumbnail_url="https://bottube.ai/thumb.jpg",
        )
        item = feed.items[0]
        assert item["author"] == "test-agent"
        assert item["category"] == "tutorial"
        assert item["guid"] == "custom-guid"
        assert item["enclosure_url"] == "https://bottube.ai/videos/full.mp4"

    def test_add_video(self):
        """add_video should convert video dict to feed item."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        video = {
            "id": "demo-001",
            "title": "Test Video",
            "description": "A test video",
            "agent": "test-agent",
            "created_at": time.time(),
            "thumbnail_url": "https://bottube.ai/thumb.jpg",
            "video_url": "https://bottube.ai/video.mp4",
            "duration": 180,
            "tags": ["tutorial"],
        }
        feed.add_video(video)
        assert len(feed.items) == 1
        assert feed.items[0]["title"] == "Test Video"

    def test_add_video_without_id(self):
        """Videos without IDs should still work."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        feed.add_video({"title": "No ID Video", "agent": "test-agent"})
        assert len(feed.items) == 1
        assert feed.items[0]["guid"] != feed.items[0]["link"]


class TestRSSFeedBuilderBuild:
    def test_build_returns_string(self):
        """build() should return an XML string."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        result = feed.build()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_starts_with_xml_declaration(self):
        """RSS XML should start with XML declaration."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        result = feed.build()
        assert result.startswith('<?xml version="1.0" encoding="UTF-8"?>')

    def test_build_has_rss_root(self):
        """RSS XML should have <rss> root element."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        result = feed.build()
        assert "<rss version=\"2.0\"" in result
        assert "</rss>" in result

    def test_build_has_channel(self):
        """RSS XML should contain channel element."""
        feed = RSSFeedBuilder(title="Test Channel", link="https://bottube.ai")
        result = feed.build()
        assert "<channel>" in result
        assert "<title>Test Channel</title>" in result

    def test_build_includes_item(self):
        """RSS XML should contain item elements."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        feed.add_item(title="Item Title", link="https://bottube.ai/item", description="Desc")
        result = feed.build()
        assert "<item>" in result
        assert "<title>Item Title</title>" in result

    def test_build_includes_pubdate(self):
        """Items should contain pubDate element."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        feed.add_item(title="T", link="https://bottube.ai/item", description="D")
        result = feed.build()
        assert "<pubDate>" in result

    def test_build_does_not_include_empty_fields(self):
        """Optional fields should not appear when not provided."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        feed.add_item(title="T", link="https://bottube.ai/item", description="D")
        result = feed.build()
        assert "<author>" not in result
        assert "<category>" not in result
        assert "<enclosure" not in result

    def test_build_with_enclosure(self):
        """Items with enclosure should include <enclosure> element."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        feed.add_item(
            title="T",
            link="https://bottube.ai/item",
            description="D",
            enclosure_url="https://bottube.ai/video.mp4",
            enclosure_type="video/mp4",
            enclosure_length=1024000,
        )
        result = feed.build()
        assert "<enclosure" in result
        assert 'url="https://bottube.ai/video.mp4"' in result
        assert 'type="video/mp4"' in result
        assert 'length="1024000"' in result

    def test_build_with_thumbnail(self):
        """Items with thumbnail should include <media:thumbnail> element."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        feed.add_item(
            title="T",
            link="https://bottube.ai/item",
            description="D",
            thumbnail_url="https://bottube.ai/thumb.jpg",
        )
        result = feed.build()
        assert "<media:thumbnail" in result
        assert "https://bottube.ai/thumb.jpg" in result

    def test_build_bytes(self):
        """build_bytes() should return UTF-8 bytes."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        result = feed.build_bytes()
        assert isinstance(result, bytes)
        assert result.startswith(b'<?xml')

    def test_xml_is_well_formed(self):
        """Generated XML should look structurally valid (opening/closing tags match)."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        for i in range(3):
            feed.add_item(title=f"Item {i}", link=f"https://bottube.ai/item/{i}", description=f"D{i}")
        result = feed.build()
        assert result.count("<item>") == result.count("</item>")
        assert result.count("<channel>") == result.count("</channel>")
        assert result.count("<rss") == result.count("</rss>")

    def test_content_escaping(self):
        """XML-special characters in titles should be escaped."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        feed.add_item(title="AT&T <Special> & Co.", link="https://bottube.ai/item", description="D")
        result = feed.build()
        assert "AT&amp;T" in result
        assert "&lt;Special&gt;" in result
        assert "&amp;" in result
        # Should NOT contain raw special chars
        assert "<Special>" not in result


# ============================================================================
# AtomFeedBuilder Tests
# ============================================================================

class TestAtomFeedBuilderInit:
    def test_default_values(self):
        """Default Atom builder should set reasonable values."""
        feed = AtomFeedBuilder(title="Atom Feed", link="https://bottube.ai")
        assert feed.title == "Atom Feed"
        assert feed.entries == []
        assert feed.link == "https://bottube.ai"
        assert feed.subtitle == "BoTTube Video Feed"
        assert feed.entries == []

    def test_custom_values(self):
        """Custom Atom constructor values should be respected."""
        feed = AtomFeedBuilder(
            title="Custom",
            link="https://example.com/",
            subtitle="Custom Subtitle",
            author_name="Custom Author",
            author_email="author@example.com",
        )
        assert feed.title == "Custom"
        assert feed.link == "https://example.com"
        assert feed.subtitle == "Custom Subtitle"
        assert feed.author_name == "Custom Author"


class TestAtomFeedBuilderBuild:
    def test_build_returns_string(self):
        """build() should return an XML string."""
        feed = AtomFeedBuilder(title="Atom Test", link="https://bottube.ai")
        result = feed.build()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_starts_with_xml_declaration(self):
        """Atom XML should start with XML declaration."""
        feed = AtomFeedBuilder(title="Test", link="https://bottube.ai")
        result = feed.build()
        assert result.startswith('<?xml version="1.0" encoding="UTF-8"?>')

    def test_build_has_feed_root(self):
        """Atom XML should have <feed> root element with correct namespace."""
        feed = AtomFeedBuilder(title="Test", link="https://bottube.ai")
        result = feed.build()
        assert "<feed" in result
        assert 'xmlns="http://www.w3.org/2005/Atom"' in result
        assert "</feed>" in result

    def test_build_has_feed_title(self):
        """Atom XML should contain feed title."""
        feed = AtomFeedBuilder(title="My Atom Feed", link="https://bottube.ai")
        result = feed.build()
        assert "<title>My Atom Feed</title>" in result

    def test_build_includes_entry(self):
        """Atom XML should contain entry elements."""
        feed = AtomFeedBuilder(title="Test", link="https://bottube.ai")
        feed.add_entry(title="Entry 1", entry_id="urn:video:1", link="https://bottube.ai/1", summary="Desc 1")
        result = feed.build()
        assert "<entry>" in result
        assert "<title>Entry 1</title>" in result

    def test_add_item_returns_self(self):
        """add_item should return self for chaining."""
        feed = AtomFeedBuilder(title="Test", link="https://bottube.ai")
        r = feed.add_entry(title="T", entry_id="urn:video:1", link="https://bottube.ai/t", summary="D")
        assert r is feed

    def test_add_video(self):
        """add_video should convert video dict to Atom entry."""
        feed = AtomFeedBuilder(title="Test", link="https://bottube.ai")
        video = {
            "id": "demo-001",
            "title": "Atom Video",
            "description": "Atom video description",
            "agent": "test-agent",
            "created_at": time.time(),
            "thumbnail_url": "https://bottube.ai/thumb.jpg",
            "video_url": "https://bottube.ai/video.mp4",
            "duration": 180,
            "tags": ["tutorial"],
        }
        feed.add_video(video)
        assert len(feed.entries) == 1
        assert feed.entries[0]["title"] == "Atom Video"

    def test_multiple_entries(self):
        """Multiple entries should all appear in the feed."""
        feed = AtomFeedBuilder(title="Test", link="https://bottube.ai")
        for i in range(5):
            feed.add_entry(title=f"Entry {i}", entry_id=f"urn:video:{i}", link=f"https://bottube.ai/{i}", summary=f"D{i}")
        result = feed.build()
        assert result.count("<entry>") == 5

    def test_xml_well_formed(self):
        """Generated Atom XML should have matching tags."""
        feed = AtomFeedBuilder(title="Test", link="https://bottube.ai")
        for i in range(3):
            feed.add_entry(title=f"E{i}", entry_id=f"urn:video:{i}", link=f"https://bottube.ai/{i}", summary=f"D{i}")
        result = feed.build()
        assert result.count("<entry>") == result.count("</entry>")
        assert result.count("<feed") == result.count("</feed>")

    def test_content_escaping(self):
        """XML-special chars in Atom content should be escaped."""
        feed = AtomFeedBuilder(title="Test", link="https://bottube.ai")
        feed.add_entry(title="A&B <Company>", entry_id="urn:video:1", link="https://bottube.ai/1", summary="D")
        result = feed.build()
        assert "A&amp;B" in result
        assert "&lt;Company&gt;" in result

    def test_build_bytes(self):
        """build_bytes() should return UTF-8 bytes."""
        feed = AtomFeedBuilder(title="Atom Test", link="https://bottube.ai")
        result = feed.build_bytes()
        assert isinstance(result, bytes)
        assert result.startswith(b'<?xml')


# ============================================================================
# Integration / Edge Case Tests
# ============================================================================

class TestEdgeCases:
    def test_empty_feed(self):
        """Empty feeds (no items) should still produce valid XML structure."""
        rss = RSSFeedBuilder(title="Empty", link="https://bottube.ai").build()
        atom = AtomFeedBuilder(title="Empty", link="https://bottube.ai").build()
        assert "<channel>" in rss and "</channel>" in rss
        assert "<feed" in atom and "</feed>" in atom
        assert "<item>" not in rss
        assert "<entry>" not in atom

    def test_special_characters_in_title(self):
        """Special Unicode characters should be handled."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        feed.add_item(
            title="Café résumé ñoño 🎉",
            link="https://bottube.ai/item",
            description="Special chars: éüñöä",
        )
        result = feed.build()
        assert "Café" in result
        assert "ñoño" in result

    def test_long_feed_many_items(self):
        """Feed with many items should build quickly."""
        feed = RSSFeedBuilder(title="Big Feed", link="https://bottube.ai")
        for i in range(25):
            feed.add_item(
                title=f"Long-running video #{i} with a very extended title for testing purposes",
                link=f"https://bottube.ai/video/long-running-{i}",
                description="A" * 200,
            )
        result = feed.build()
        assert result.count("<item>") == 25

    def test_rss_and_atom_consistency(self):
        """RSS and Atom feeds built from same video data should both be valid."""
        video = {
            "id": "demo-001",
            "title": "Consistency Check",
            "description": "Testing both formats",
            "agent": "test-agent",
            "created_at": time.time(),
        }
        rss = RSSFeedBuilder(title="Test", link="https://bottube.ai").add_video(video).build()
        atom = AtomFeedBuilder(title="Test", link="https://bottube.ai").add_video(video).build()
        assert "Consistency Check" in rss
        assert "Consistency Check" in atom
        assert "demo-001" in rss
        assert "demo-001" in atom

    def test_very_long_description(self):
        """Very long descriptions should be handled."""
        long_desc = "X" * 10000
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        feed.add_item(title="Long Desc", link="https://bottube.ai/item", description=long_desc)
        result = feed.build()
        assert long_desc in result

    def test_xml_special_chars_in_all_fields(self):
        """Multiple XML-special characters across fields should all be escaped."""
        feed = RSSFeedBuilder(title="Test", link="https://bottube.ai")
        feed.add_item(
            title="A < B > C & D",
            link="https://bottube.ai/item",
            description="Desc <with> special & chars",
            author="Author & Co.",
            category="cat & dog",
        )
        result = feed.build()
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result
        assert "<author>Author &amp; Co.</author>" in result
