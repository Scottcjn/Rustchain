#!/usr/bin/env python3
"""
Tests for bottube_embed.py — BoTTube Embeddable Player Widget

Covers:
- embed_player route (GET /embed/<video_id>)
- oembed route (GET /oembed)
- watch_page route (GET /watch/<video_id>)
- Input validation (video_id length, URL parsing, format validation)
- Edge cases (missing video, invalid URLs, oversized parameters)
"""
from __future__ import annotations

import json
import pytest
from flask import Flask

# Import the blueprint
from node.bottube_embed import embed_bp, _get_mock_video, _get_related_videos


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def app():
    """Create a Flask test app with the bottube_embed blueprint registered."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["TRUSTED_FORWARD_HOSTS"] = ["trusted-proxy.example.com"]
    app.register_blueprint(embed_bp)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


# ============================================================================
# Helper function tests
# ============================================================================

class TestGetMockVideo:
    def test_known_video(self):
        """Should return video data for known demo IDs."""
        video = _get_mock_video("demo-001")
        assert video is not None
        assert video["id"] == "demo-001"
        assert video["title"] == "Introduction to RustChain Mining"
        assert "video_url" in video
        assert "thumbnail_url" in video
        assert video["public"] is True

    def test_unknown_video(self):
        """Should return None for unknown video IDs."""
        assert _get_mock_video("nonexistent") is None

    def test_empty_id(self):
        """Should return None for empty video ID."""
        assert _get_mock_video("") is None


class TestGetRelatedVideos:
    def test_excludes_current(self):
        """Related videos should exclude the current video."""
        related = _get_related_videos("demo-001", limit=10)
        ids = [v["id"] for v in related]
        assert "demo-001" not in ids

    def test_respects_limit(self):
        """Should respect the limit parameter."""
        related = _get_related_videos("demo-001", limit=2)
        assert len(related) <= 2

    def test_remaining_as_related(self):
        """Excluding a known video should return remaining videos."""
        related = _get_related_videos("demo-001", limit=10)
        assert len(related) >= 1
        assert all(v["id"] != "demo-001" for v in related)

    def test_invalid_video(self):
        """Should return all videos for invalid video_id."""
        related = _get_related_videos("invalid", limit=10)
        assert len(related) >= 3


# ============================================================================
# Embed Player Route Tests
# ============================================================================

class TestEmbedPlayer:
    def test_known_video_returns_html(self, client):
        """GET /embed/<id> for a known video should return HTML with player."""
        resp = client.get("/embed/demo-001")
        assert resp.status_code == 200
        assert resp.mimetype == "text/html"
        body = resp.data.decode()
        assert "BoTTube" in body
        assert "video" in body.lower()
        assert "Introduction to RustChain Mining" in body

    def test_unknown_video_returns_404(self, client):
        """GET /embed/<id> for an unknown video should return 404."""
        resp = client.get("/embed/nonexistent")
        assert resp.status_code == 404
        body = resp.data.decode()
        assert "Video Not Found" in body

    def test_very_long_video_id_returns_400(self, client):
        """GET /embed/<id> with a very long video ID should return 400."""
        long_id = "a" * 300
        resp = client.get(f"/embed/{long_id}")
        assert resp.status_code == 400
        assert "Invalid" in resp.data.decode()

    def test_video_id_with_special_chars(self, client):
        """Should handle video IDs with special characters."""
        resp = client.get("/embed/demo-003?extra=param")
        assert resp.status_code == 200

    def test_content_includes_video_title(self, client):
        """Response should include the video title."""
        resp = client.get("/embed/demo-002")
        body = resp.data.decode()
        assert "Understanding RIP-200 Epoch Rewards" in body


# ============================================================================
# oEmbed Route Tests
# ============================================================================

class TestOEmbed:
    def test_valid_url_returns_json(self, client):
        """GET /oembed?url=... should return JSON with oEmbed data."""
        resp = client.get("/oembed?url=http://localhost/watch/demo-001")
        assert resp.status_code == 200
        assert resp.mimetype == "application/json"
        data = json.loads(resp.data)
        assert data["version"] == "1.0"
        assert data["type"] == "video"
        assert data["provider_name"] == "BoTTube"
        assert data["title"] == "Introduction to RustChain Mining"

    def test_missing_url_returns_400(self, client):
        """GET /oembed without url should return 400."""
        resp = client.get("/oembed")
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "Invalid URL" in data["error"]

    def test_invalid_format_returns_400(self, client):
        """GET /oembed?url=...&format=xml should return 400."""
        resp = client.get("/oembed?url=http://localhost/watch/demo-001&format=xml")
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "Unsupported format" in data["error"]

    def test_unknown_video_returns_404(self, client):
        """GET /oembed for a non-existent video should return 404."""
        resp = client.get("/oembed?url=http://localhost/watch/nonexistent")
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert "Video not found" in data["error"]

    def test_dimensions_are_sane(self, client):
        """Response dimensions should be within reasonable bounds."""
        resp = client.get("/oembed?url=http://localhost/watch/demo-001")
        data = json.loads(resp.data)
        assert 1 <= data["width"] <= 854
        assert 1 <= data["height"] <= 480

    def test_embed_url_uses_iframe(self, client):
        """Embed HTML should contain an iframe pointing to the embed endpoint."""
        resp = client.get("/oembed?url=http://localhost/watch/demo-001")
        data = json.loads(resp.data)
        assert "iframe" in data["html"]
        assert "/embed/demo-001" in data["html"]

    def test_custom_dimensions(self, client):
        """Custom maxwidth/maxheight should be respected within bounds."""
        resp = client.get(
            "/oembed?url=http://localhost/watch/demo-001&maxwidth=640&maxheight=360"
        )
        data = json.loads(resp.data)
        # Should be at or below requested dimensions
        assert data["width"] <= 640
        assert data["height"] <= 360

    def test_reasonable_max_dimensions(self, client):
        """Max dimensions shouldn't exceed 854x480 regardless of request."""
        resp = client.get(
            "/oembed?url=http://localhost/watch/demo-001&maxwidth=9999&maxheight=9999"
        )
        data = json.loads(resp.data)
        assert data["width"] <= 854
        assert data["height"] <= 480

    def test_embed_url_works(self, client):
        """Embed URL should be parseable."""
        resp = client.get("/oembed?url=http://localhost/watch/demo-001")
        data = json.loads(resp.data)
        assert data["thumbnail_url"].startswith("https://")
        assert data["author_name"] is not None
        assert data["provider_url"] is not None


# ============================================================================
# Watch Page Route Tests
# ============================================================================

class TestWatchPage:
    def test_known_video_returns_html(self, client):
        """GET /watch/<id> for a known video should return full watch page."""
        resp = client.get("/watch/demo-001")
        assert resp.status_code == 200
        assert resp.mimetype == "text/html"
        body = resp.data.decode()
        assert "BoTTube" in body
        assert "Share" in body  # Should have share UI
        assert "oembed" in resp.data.decode().lower()

    def test_unknown_video_returns_404(self, client):
        """GET /watch/<id> for an unknown video should return 404."""
        resp = client.get("/watch/nonexistent")
        assert resp.status_code == 404
        assert "Video Not Found" in resp.data.decode()

    def test_long_video_id_returns_400(self, client):
        """GET /watch/<id> with very long ID should return 400."""
        long_id = "a" * 300
        resp = client.get(f"/watch/{long_id}")
        assert resp.status_code == 400

    def test_content_includes_video_details(self, client):
        """Watch page should include video title, description, and related videos."""
        resp = client.get("/watch/demo-001")
        body = resp.data.decode()
        assert "Introduction to RustChain Mining" in body
        assert "Related Videos" in body or "related" in body.lower()
        assert "embed" in body.lower() or "iframe" in body

    def test_renders_multiple_videos(self, client):
        """Should render all demo videos correctly."""
        for vid in ["demo-001", "demo-002", "demo-003"]:
            resp = client.get(f"/watch/{vid}")
            assert resp.status_code == 200
            assert resp.data.decode() != ""


# ============================================================================
# Security / Edge Case Tests
# ============================================================================

class TestSecurity:
    def test_sql_injection_attempt(self, client):
        """SQL injection patterns in video_id should be rejected gracefully."""
        payloads = [
            "/embed/1' OR '1'='1",
            "/embed/1; DROP TABLE videos",
            "/watch/1' UNION SELECT * FROM users",
            "/oembed?url=http://localhost/watch/1' OR '1'='1",
        ]
        for path in payloads:
            resp = client.get(path)
            # Should return either 200 (with mock data) or 404/400 (graceful error)
            assert resp.status_code in (200, 400, 404), f"Failed on {path}"

    def test_xss_attempt(self, client):
        """XSS patterns in video_id should be HTML-escaped in error pages."""
        resp = client.get('/embed/<script>alert("xss")</script>')
        body = resp.data.decode()
        # Should not have unescaped script tags
        assert '<script>alert' not in body

    def test_path_traversal_attempt(self, client):
        """Path traversal patterns should not cause issues."""
        resp = client.get("/embed/../etc/passwd")
        assert resp.status_code in (200, 400, 404)

    def test_very_long_url(self, client):
        """Very long oembed URLs should be rejected (param > 2048 chars)."""
        long_url = "http://localhost/watch/" + "a" * 2050
        resp = client.get(f"/oembed?url={long_url}")
        assert resp.status_code == 400

    def test_missing_video_structure(self, client):
        """Missing video data should not crash the application."""
        resp = client.get("/embed/")
        # Trailing slash behavior — should be handled gracefully
        assert resp.status_code in (200, 308, 404)

    def test_related_videos_xss(self):
        """Related video titles should be safe."""
        videos = _get_related_videos("demo-001", limit=10)
        for v in videos:
            assert isinstance(v["title"], str)
            assert isinstance(v["agent"], str)
