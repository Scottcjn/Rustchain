#!/usr/bin/env python3
"""
Tests for BoTTube Embeddable Player Widget

Tests cover:
    - Embed endpoint (/embed/<video_id>)
    - oEmbed endpoint (/oembed)
    - Watch page (/watch/<video_id>)
    - Share > Embed UI functionality
"""

import json
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask

from bottube_embed import (
    embed_bp,
    watch_page,
    oembed,
    embed_player,
    init_embed_routes,
    _get_mock_video,
    _get_related_videos,
)


class TestEmbedEndpoints(unittest.TestCase):
    """Test suite for BoTTube embed endpoints."""

    def setUp(self):
        """Set up test Flask app."""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        init_embed_routes(self.app)
        self.client = self.app.test_client()

    def test_embed_player_exists(self):
        """Test that embed player endpoint exists and returns HTML."""
        response = self.client.get("/embed/demo-001")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"video", response.data.lower())
        self.assertIn(b"BoTTube", response.data)

    def test_embed_player_responsive(self):
        """Test that embed player includes responsive styling."""
        response = self.client.get("/embed/demo-001")
        self.assertEqual(response.status_code, 200)
        # Check for responsive CSS
        self.assertIn(b"width: 100%", response.data)
        self.assertIn(b"height: 100%", response.data)

    def test_embed_player_branding(self):
        """Test that embed player includes BoTTube branding."""
        response = self.client.get("/embed/demo-001")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"BoTTube", response.data)
        # Check for link back to full page
        self.assertIn(b"href=", response.data)

    def test_embed_player_not_found(self):
        """Test embed player returns 404 for non-existent video."""
        response = self.client.get("/embed/nonexistent-video")
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"Video Not Found", response.data)

    def test_embed_player_html5_video(self):
        """Test that embed player uses HTML5 video tag."""
        response = self.client.get("/embed/demo-001")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<video", response.data)
        self.assertIn(b"</video>", response.data)
        self.assertIn(b'<source src=', response.data)
        self.assertIn(b'type="video/mp4"', response.data)

    def test_embed_player_controls(self):
        """Test that video player has controls enabled."""
        response = self.client.get("/embed/demo-001")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"controls", response.data)

    def test_embed_player_autoplay(self):
        """Test that video player has autoplay enabled."""
        response = self.client.get("/embed/demo-001")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"autoplay", response.data)


class TestOEmbedEndpoint(unittest.TestCase):
    """Test suite for oEmbed endpoint."""

    def setUp(self):
        """Set up test Flask app."""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        init_embed_routes(self.app)
        self.client = self.app.test_client()

    def test_oembed_exists(self):
        """Test that oEmbed endpoint exists."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")

    def test_oembed_valid_json(self):
        """Test that oEmbed returns valid JSON."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsNotNone(data)

    def test_oembed_required_fields(self):
        """Test that oEmbed response includes required fields."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001")
        data = response.get_json()
        
        required_fields = [
            "version", "type", "provider_name", "provider_url",
            "title", "width", "height", "html"
        ]
        
        for field in required_fields:
            self.assertIn(field, data, f"Missing required field: {field}")

    def test_oembed_version(self):
        """Test that oEmbed version is 1.0."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001")
        data = response.get_json()
        self.assertEqual(data["version"], "1.0")

    def test_oembed_type(self):
        """Test that oEmbed type is video."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001")
        data = response.get_json()
        self.assertEqual(data["type"], "video")

    def test_oembed_provider_name(self):
        """Test that provider name is BoTTube."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001")
        data = response.get_json()
        self.assertEqual(data["provider_name"], "BoTTube")

    def test_oembed_html_iframe(self):
        """Test that oEmbed HTML contains iframe."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001")
        data = response.get_json()
        self.assertIn("<iframe", data["html"])
        self.assertIn("</iframe>", data["html"])
        self.assertIn("src=", data["html"])
        self.assertIn("allowfullscreen", data["html"])

    def test_oembed_dimensions(self):
        """Test that oEmbed includes width and height."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001")
        data = response.get_json()
        self.assertIn("width", data)
        self.assertIn("height", data)
        self.assertIsInstance(data["width"], int)
        self.assertIsInstance(data["height"], int)

    def test_oembed_maxwidth_parameter(self):
        """Test that maxwidth parameter is respected."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001&maxwidth=640")
        data = response.get_json()
        self.assertLessEqual(data["width"], 640)

    def test_oembed_maxheight_parameter(self):
        """Test that maxheight parameter is respected."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001&maxheight=360")
        data = response.get_json()
        self.assertLessEqual(data["height"], 360)

    def test_oembed_rejects_non_positive_dimensions(self):
        """Test that non-positive dimensions do not produce invalid iframe sizes."""
        response = self.client.get(
            "/oembed?url=https://bottube.ai/watch/demo-001&maxwidth=-1&maxheight=0"
        )
        data = response.get_json()
        self.assertGreater(data["width"], 0)
        self.assertGreater(data["height"], 0)
        self.assertNotIn('width="-', data["html"])
        self.assertNotIn('height="0"', data["html"])

    def test_oembed_thumbnail(self):
        """Test that oEmbed includes thumbnail URL."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001")
        data = response.get_json()
        self.assertIn("thumbnail_url", data)
        self.assertIsNotNone(data["thumbnail_url"])

    def test_oembed_author(self):
        """Test that oEmbed includes author information."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001")
        data = response.get_json()
        self.assertIn("author_name", data)
        self.assertIn("author_url", data)

    def test_oembed_invalid_url(self):
        """Test oEmbed returns error for invalid URL."""
        response = self.client.get("/oembed?url=invalid-url")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_oembed_nonexistent_video(self):
        """Test oEmbed returns 404 for non-existent video."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_oembed_unsupported_format(self):
        """Test oEmbed returns error for unsupported format."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001&format=xml")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_oembed_watch_url(self):
        """Test oEmbed works with /watch/ URL."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001")
        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("html", data)

    def test_oembed_embed_url(self):
        """Test oEmbed works with /embed/ URL."""
        response = self.client.get("/oembed?url=https://bottube.ai/embed/demo-001")
        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("html", data)

    def test_oembed_ignores_untrusted_forwarded_host(self):
        """Untrusted forwarded hosts must not poison generated embed URLs."""
        response = self.client.get(
            "/oembed?url=https://bottube.ai/watch/demo-001",
            headers={"X-Forwarded-Host": "evil.example"},
            base_url="https://bottube.ai",
        )
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("https://bottube.ai/embed/demo-001", data["html"])
        self.assertNotIn("evil.example", data["html"])
        self.assertNotIn("evil.example", data["thumbnail_url"])

    def test_oembed_allows_trusted_forwarded_host(self):
        """Trusted forwarded hosts remain supported for proxy deployments."""
        self.app.config["TRUSTED_FORWARD_HOSTS"] = ["embed.bottube.ai"]

        response = self.client.get(
            "/oembed?url=https://bottube.ai/watch/demo-001",
            headers={"X-Forwarded-Host": "embed.bottube.ai"},
            base_url="https://internal.example",
        )
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("https://embed.bottube.ai/embed/demo-001", data["html"])


class TestWatchPage(unittest.TestCase):
    """Test suite for watch page with Share > Embed UI."""

    def setUp(self):
        """Set up test Flask app."""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        init_embed_routes(self.app)
        self.client = self.app.test_client()

    def test_watch_page_exists(self):
        """Test that watch page endpoint exists."""
        response = self.client.get("/watch/demo-001")
        self.assertEqual(response.status_code, 200)

    def test_watch_page_video_player(self):
        """Test that watch page includes video player."""
        response = self.client.get("/watch/demo-001")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<video", response.data)

    def test_watch_page_share_button(self):
        """Test that watch page includes Share button."""
        response = self.client.get("/watch/demo-001")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Share", response.data)

    def test_watch_page_embed_tab(self):
        """Test that watch page includes Embed tab."""
        response = self.client.get("/watch/demo-001")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Embed", response.data)

    def test_watch_page_size_presets(self):
        """Test that watch page includes size presets."""
        response = self.client.get("/watch/demo-001")
        self.assertEqual(response.status_code, 200)
        # Check for size preset buttons
        self.assertIn(b"560", response.data)
        self.assertIn(b"315", response.data)
        self.assertIn(b"640", response.data)
        self.assertIn(b"360", response.data)
        self.assertIn(b"854", response.data)
        self.assertIn(b"480", response.data)

    def test_watch_page_embed_code(self):
        """Test that watch page includes embed code textarea."""
        response = self.client.get("/watch/demo-001")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"embedCode", response.data)
        self.assertIn(b"iframe", response.data)

    def test_watch_page_copy_button(self):
        """Test that watch page includes copy button for embed code."""
        response = self.client.get("/watch/demo-001")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Copy", response.data)

    def test_watch_page_oembed_discovery(self):
        """Test that watch page includes oEmbed discovery link."""
        response = self.client.get("/watch/demo-001")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'application/json+oembed', response.data)
        self.assertIn(b"/oembed", response.data)

    def test_watch_page_not_found(self):
        """Test watch page returns 404 for non-existent video."""
        response = self.client.get("/watch/nonexistent-video")
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"Video Not Found", response.data)

    def test_watch_page_related_videos(self):
        """Test that watch page includes related videos."""
        response = self.client.get("/watch/demo-001")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Related Videos", response.data)


class TestHelperFunctions(unittest.TestCase):
    """Test suite for helper functions."""

    def test_get_mock_video_exists(self):
        """Test that mock video data is available."""
        video = _get_mock_video("demo-001")
        self.assertIsNotNone(video)
        self.assertEqual(video["id"], "demo-001")

    def test_get_mock_video_fields(self):
        """Test that mock video has required fields."""
        video = _get_mock_video("demo-001")
        required_fields = [
            "id", "title", "description", "video_url",
            "thumbnail_url", "agent", "public"
        ]
        for field in required_fields:
            self.assertIn(field, video, f"Missing field: {field}")

    def test_get_mock_video_not_found(self):
        """Test that mock video returns None for non-existent video."""
        video = _get_mock_video("nonexistent")
        self.assertIsNone(video)

    def test_get_related_videos_exists(self):
        """Test that related videos are available."""
        related = _get_related_videos("demo-001")
        self.assertIsInstance(related, list)
        self.assertGreater(len(related), 0)

    def test_get_related_videos_excludes_current(self):
        """Test that related videos exclude current video."""
        related = _get_related_videos("demo-001")
        for video in related:
            self.assertNotEqual(video["id"], "demo-001")

    def test_get_related_videos_limit(self):
        """Test that related videos respect limit parameter."""
        related = _get_related_videos("demo-001", limit=2)
        self.assertLessEqual(len(related), 2)


class TestEmbedIntegration(unittest.TestCase):
    """Integration tests for embed functionality."""

    def setUp(self):
        """Set up test Flask app."""
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        init_embed_routes(self.app)
        self.client = self.app.test_client()

    def test_full_embed_flow(self):
        """Test complete embed flow from watch to embed."""
        # 1. Access watch page
        watch_response = self.client.get("/watch/demo-001")
        self.assertEqual(watch_response.status_code, 200)
        
        # 2. Access embed page
        embed_response = self.client.get("/embed/demo-001")
        self.assertEqual(embed_response.status_code, 200)
        
        # 3. Access oEmbed endpoint
        oembed_response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001")
        self.assertEqual(oembed_response.status_code, 200)
        
        # 4. Verify oEmbed HTML contains embed URL
        oembed_data = oembed_response.get_json()
        self.assertIn("/embed/demo-001", oembed_data["html"])

    def test_embed_iframe_attributes(self):
        """Test that embed iframe has all required attributes."""
        response = self.client.get("/oembed?url=https://bottube.ai/watch/demo-001")
        data = response.get_json()
        html = data["html"]
        
        # Check for required iframe attributes
        self.assertIn('width="', html)
        self.assertIn('height="', html)
        self.assertIn('src="', html)
        self.assertIn('frameborder="0"', html)
        self.assertIn("allowfullscreen", html)

    def test_embed_responsive_sizing(self):
        """Test that embed supports different sizes."""
        sizes = [
            (560, 315),
            (640, 360),
            (854, 480),
        ]
        
        for maxwidth, maxheight in sizes:
            response = self.client.get(
                f"/oembed?url=https://bottube.ai/watch/demo-001&maxwidth={maxwidth}&maxheight={maxheight}"
            )
            data = response.get_json()
            self.assertLessEqual(data["width"], maxwidth)
            self.assertLessEqual(data["height"], maxheight)


if __name__ == "__main__":
    unittest.main(verbosity=2)
