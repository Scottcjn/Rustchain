"""
Tests for the RustChain API rate limiter middleware.
"""

import time
import pytest
from flask import Flask

# Adjust path so the middleware package is importable
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from middleware.rate_limiter import (
    RateLimiter, InMemoryStore, TokenBucket, init_rate_limiter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(**limiter_kwargs):
    """Create a minimal Flask app with rate limiter attached."""
    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.route("/api/mine", methods=["POST"])
    def mine():
        return {"ok": True}

    @app.route("/epoch", methods=["GET"])
    def epoch():
        return {"epoch": 1}

    @app.route("/admin/status", methods=["GET"])
    def admin_status():
        return {"admin": True}

    @app.route("/health", methods=["GET"])
    def health():
        return {"healthy": True}

    init_rate_limiter(app, **limiter_kwargs)
    return app


# ---------------------------------------------------------------------------
# TokenBucket unit tests
# ---------------------------------------------------------------------------

class TestTokenBucket:
    def test_allows_up_to_capacity(self):
        bucket = TokenBucket(capacity=3, refill_rate=1.0)
        for _ in range(3):
            allowed, _ = bucket.consume()
            assert allowed

    def test_rejects_when_empty(self):
        bucket = TokenBucket(capacity=1, refill_rate=0.1)
        bucket.consume()  # drain
        allowed, retry = bucket.consume()
        assert not allowed
        assert retry > 0

    def test_refills_over_time(self):
        bucket = TokenBucket(capacity=2, refill_rate=100.0)  # fast refill
        bucket.consume()
        bucket.consume()
        # Wait a tiny bit for refill
        time.sleep(0.02)
        allowed, _ = bucket.consume()
        assert allowed


# ---------------------------------------------------------------------------
# InMemoryStore tests
# ---------------------------------------------------------------------------

class TestInMemoryStore:
    def test_basic_consume(self):
        store = InMemoryStore()
        allowed, _ = store.consume("ip:1", capacity=5, refill_rate=1.0)
        assert allowed

    def test_rate_limit_hit(self):
        store = InMemoryStore()
        for _ in range(3):
            store.consume("ip:2", capacity=3, refill_rate=0.01)
        allowed, retry = store.consume("ip:2", capacity=3, refill_rate=0.01)
        assert not allowed
        assert retry > 0

    def test_independent_keys(self):
        store = InMemoryStore()
        for _ in range(3):
            store.consume("ip:A", capacity=3, refill_rate=0.01)
        # ip:A is exhausted, but ip:B should still work
        allowed, _ = store.consume("ip:B", capacity=3, refill_rate=0.01)
        assert allowed


# ---------------------------------------------------------------------------
# Integration tests (Flask test client)
# ---------------------------------------------------------------------------

class TestRateLimiterMiddleware:
    def test_allows_normal_requests(self):
        app = _make_app(default_rate=100, default_window=60, default_burst=50)
        client = app.test_client()
        resp = client.get("/epoch")
        assert resp.status_code == 200

    def test_returns_429_on_excess(self):
        app = _make_app(
            default_rate=2, default_window=60, default_burst=2,
            endpoint_limits={"/epoch": (2, 60, 2)},
        )
        client = app.test_client()
        # Exhaust the bucket
        for _ in range(2):
            client.get("/epoch")
        resp = client.get("/epoch")
        assert resp.status_code == 429
        data = resp.get_json()
        assert data["error"] == "rate_limited"
        assert "Retry-After" in resp.headers

    def test_retry_after_header_is_positive_int(self):
        app = _make_app(
            default_rate=1, default_window=60, default_burst=1,
            endpoint_limits={},
        )
        client = app.test_client()
        client.get("/epoch")
        resp = client.get("/epoch")
        assert resp.status_code == 429
        assert int(resp.headers["Retry-After"]) >= 1

    def test_exempt_admin_path(self):
        app = _make_app(default_rate=1, default_window=60, default_burst=1)
        client = app.test_client()
        # Admin paths should never be limited
        for _ in range(5):
            resp = client.get("/admin/status")
            assert resp.status_code == 200

    def test_exempt_health_path(self):
        app = _make_app(default_rate=1, default_window=60, default_burst=1)
        client = app.test_client()
        for _ in range(5):
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_endpoint_specific_limits(self):
        app = _make_app(
            default_rate=100, default_window=60, default_burst=100,
            endpoint_limits={"/api/mine": (1, 60, 1)},
        )
        client = app.test_client()
        client.post("/api/mine")
        resp = client.post("/api/mine")
        assert resp.status_code == 429

    def test_different_endpoints_independent(self):
        app = _make_app(
            default_rate=100, default_window=60, default_burst=100,
            endpoint_limits={"/api/mine": (1, 60, 1)},
        )
        client = app.test_client()
        # Exhaust /api/mine
        client.post("/api/mine")
        resp = client.post("/api/mine")
        assert resp.status_code == 429
        # /epoch should still work (uses global limit)
        resp = client.get("/epoch")
        assert resp.status_code == 200

    def test_disabled_limiter(self):
        app = _make_app(enabled=False, default_rate=1, default_window=60, default_burst=1)
        client = app.test_client()
        for _ in range(10):
            resp = client.get("/epoch")
            assert resp.status_code == 200

    def test_x_ratelimit_headers_on_429(self):
        app = _make_app(
            default_rate=1, default_window=60, default_burst=1,
            endpoint_limits={},
        )
        client = app.test_client()
        client.get("/epoch")
        resp = client.get("/epoch")
        assert resp.status_code == 429
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Window" in resp.headers
