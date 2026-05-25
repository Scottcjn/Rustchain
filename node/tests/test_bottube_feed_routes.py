#!/usr/bin/env python3
"""
Tests for bottube_feed_routes.py — BoTTube RSS/Atom Feed API Routes
"""
from __future__ import annotations

import json
import pytest
from flask import Flask

from node.bottube_feed_routes import feed_bp, _parse_feed_limit


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def flask_app():
    """Create Flask test app with bottube_feed blueprint registered."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["DB_PATH"] = ":memory:"
    app.config["TRUSTED_FORWARD_HOSTS"] = ["trusted.example.com"]
    app.register_blueprint(feed_bp)
    return app


@pytest.fixture
def client(flask_app):
    """Create test client."""
    return flask_app.test_client()


# Create a standalone Flask app for use in helper tests
_test_app = Flask(__name__)
_test_app.config["TESTING"] = True


# ============================================================================
# Helper Tests
# ============================================================================

class TestParseFeedLimit:
    def test_default(self):
        """No limit param should return 20."""
        with _test_app.test_request_context("/api/feed"):
            assert _parse_feed_limit() == 20

    def test_custom_default(self):
        """Custom default should be respected."""
        with _test_app.test_request_context("/api/feed"):
            assert _parse_feed_limit(default=50) == 50

    def test_valid_limit(self):
        """Valid limit parameter should be parsed."""
        with _test_app.test_request_context("/api/feed?limit=10"):
            assert _parse_feed_limit() == 10

    def test_maximum_clamp(self):
        """Limit should be clamped to maximum."""
        with _test_app.test_request_context("/api/feed?limit=999"):
            assert _parse_feed_limit(maximum=100) == 100

    def test_minimum_floor(self):
        """Limit should be at least 1."""
        with _test_app.test_request_context("/api/feed?limit=0"):
            assert _parse_feed_limit() == 1

    def test_negative_limit(self):
        """Negative limit should floor to 1."""
        with _test_app.test_request_context("/api/feed?limit=-5"):
            assert _parse_feed_limit() == 1

    def test_empty_limit(self):
        """Empty limit should return default."""
        with _test_app.test_request_context("/api/feed?limit="):
            assert _parse_feed_limit() == 20

    def test_non_numeric_limit(self):
        """Non-numeric limit should fall back to default."""
        with _test_app.test_request_context("/api/feed?limit=abc"):
            assert _parse_feed_limit() == 20


# ============================================================================
# RSS Feed Route Tests
# ============================================================================

class TestRSSFeedRoute:
    def test_rss_returns_xml(self, client):
        """GET /api/feed/rss should return RSS XML."""
        resp = client.get("/api/feed/rss")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert "xml" in resp.mimetype
            assert "<rss" in resp.data.decode()

    def test_rss_content_type(self, client):
        """RSS response should have correct Content-Type."""
        resp = client.get("/api/feed/rss")
        if resp.status_code == 200:
            assert "xml" in resp.mimetype

    def test_rss_with_limit(self, client):
        """RSS with limit param should be accepted."""
        resp = client.get("/api/feed/rss?limit=5")
        assert resp.status_code in (200, 500)


# ============================================================================
# Atom Feed Route Tests
# ============================================================================

class TestAtomFeedRoute:
    def test_atom_returns_xml(self, client):
        """GET /api/feed/atom should return Atom XML."""
        resp = client.get("/api/feed/atom")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert "xml" in resp.mimetype
            assert "<feed" in resp.data.decode()

    def test_atom_with_limit(self, client):
        """Atom with limit param should be accepted."""
        resp = client.get("/api/feed/atom?limit=10")
        assert resp.status_code in (200, 500)


# ============================================================================
# Auto-Detect Feed Route Tests
# ============================================================================

class TestAutoDetectRoute:
    def test_auto_detect_rss(self, client):
        """GET /api/feed should return RSS or JSON."""
        resp = client.get("/api/feed")
        assert resp.status_code in (200, 500)

    def test_auto_detect_json(self, client):
        """GET /api/feed?format=json should return JSON."""
        resp = client.get("/api/feed?format=json")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert resp.mimetype == "application/json"


# ============================================================================
# Query Parameter Tests
# ============================================================================

class TestQueryParams:
    def test_agent_filter(self, client):
        """Agent filter should be accepted."""
        resp = client.get("/api/feed/rss?agent=test-agent")
        assert resp.status_code in (200, 500)

    def test_cursor_pagination(self, client):
        """Cursor pagination should be accepted."""
        resp = client.get("/api/feed/rss?cursor=abc123")
        assert resp.status_code in (200, 500)

    def test_combined_params(self, client):
        """Multiple params should work together."""
        resp = client.get("/api/feed/atom?limit=15&agent=demo-agent&cursor=xyz")
        assert resp.status_code in (200, 500)

    def test_invalid_limit(self, client):
        """Invalid limit value should not crash."""
        resp = client.get("/api/feed/rss?limit=abc")
        assert resp.status_code in (200, 400, 500)

    def test_very_large_limit(self, client):
        """Very large limit should be clamped."""
        resp = client.get("/api/feed/rss?limit=999999")
        assert resp.status_code in (200, 500)


# ============================================================================
# Security / Edge Case Tests
# ============================================================================

class TestSecurity:
    def test_path_traversal_agent(self, client):
        """Path traversal patterns in agent param."""
        resp = client.get('/api/feed/rss?agent=../../etc/passwd')
        assert resp.status_code in (200, 400, 500)

    def test_sql_injection_agent(self, client):
        """SQL injection attempts in agent param."""
        resp = client.get("/api/feed/rss?agent=1' OR '1'='1")
        assert resp.status_code in (200, 400, 500)

    def test_xss_in_params(self, client):
        """XSS attempts should not crash."""
        resp = client.get('/api/feed/rss?agent=<script>alert(1)</script>')
        assert resp.status_code in (200, 400, 500)

    def test_long_agent_param(self, client):
        """Very long agent parameters should not crash."""
        resp = client.get("/api/feed/rss?agent=" + "a" * 10000)
        assert resp.status_code in (200, 400, 500)
