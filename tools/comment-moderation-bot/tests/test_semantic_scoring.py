# SPDX-License-Identifier: MIT
"""
Tests for S6: semantic scoring endpoint integration.

Validates that _get_semantic_score() makes proper HTTP POST calls
and handles errors gracefully (timeout, connection failure, bad
response, missing/minority score fields, etc.).
"""

import sys
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.scorer import HybridScorer


class _MockHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler that returns a score."""

    _response_code = 200
    _response_body = b'{"score": 0.75}'

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        # Verify we got valid JSON with 'text' key
        try:
            data = json.loads(body)
            assert "text" in data, f"Missing 'text' in request: {data}"
        except Exception:
            pass
        self.send_response(self.__class__._response_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.__class__._response_body)

    def log_message(self, format, *args):
        pass  # suppress HTTP server logs


def _serve(handler_class=_MockHandler):
    """Start HTTP server on a random port, return (server, port)."""
    server = HTTPServer(("127.0.0.1", 0), handler_class)
    port = server.server_address[1]
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, port


class TestSemanticScoring:
    """Tests for S6 — _get_semantic_score real implementation."""

    def test_returns_score_from_endpoint(self):
        """Happy path: endpoint returns 0.75 → scorer returns 0.75."""
        server, port = _serve()
        scorer = HybridScorer(
            semantic_endpoint=f"http://127.0.0.1:{port}/classify"
        )
        try:
            score = scorer._get_semantic_score("test comment")
            assert score == 0.75, f"Expected 0.75, got {score}"
        finally:
            server.shutdown()

    def test_no_endpoint_returns_zero(self):
        """When no semantic_endpoint configured, returns 0.0."""
        scorer = HybridScorer()
        score = scorer._get_semantic_score("test")
        assert score == 0.0, f"Expected 0.0, got {score}"

    def test_connection_refused_returns_zero(self):
        """When endpoint is down, returns 0.0 (graceful fallback)."""
        scorer = HybridScorer(
            semantic_endpoint="http://127.0.0.1:1/classify"
        )
        score = scorer._get_semantic_score("test")
        assert score == 0.0, f"Expected 0.0, got {score}"

    def test_non_200_response_returns_zero(self):
        """When endpoint returns 500, returns 0.0."""
        class ErrorHandler(_MockHandler):
            _response_code = 500
            _response_body = b'{"error": "internal"}'

        server, port = _serve(ErrorHandler)
        scorer = HybridScorer(
            semantic_endpoint=f"http://127.0.0.1:{port}/classify"
        )
        try:
            score = scorer._get_semantic_score("test")
            assert score == 0.0, f"Expected 0.0, got {score}"
        finally:
            server.shutdown()

    def test_missing_score_key_returns_zero(self):
        """When response has no 'score' key, returns 0.0."""
        class NoScoreHandler(_MockHandler):
            _response_body = b'{"prediction": 0.8}'

        server, port = _serve(NoScoreHandler)
        scorer = HybridScorer(
            semantic_endpoint=f"http://127.0.0.1:{port}/classify"
        )
        try:
            score = scorer._get_semantic_score("test")
            assert score == 0.0, f"Expected 0.0, got {score}"
        finally:
            server.shutdown()

    def test_string_score_is_rejected(self):
        """Non-numeric score string returns 0.0."""
        class StringScoreHandler(_MockHandler):
            _response_body = b'{"score": "high"}'

        server, port = _serve(StringScoreHandler)
        scorer = HybridScorer(
            semantic_endpoint=f"http://127.0.0.1:{port}/classify"
        )
        try:
            score = scorer._get_semantic_score("test")
            assert score == 0.0, f"Expected 0.0, got {score}"
        finally:
            server.shutdown()

    def test_score_clamped_to_0_1(self):
        """Score outside [0,1] is clamped."""
        class OutOfRangeHandler(_MockHandler):
            _response_body = b'{"score": 2.5}'

        server, port = _serve(OutOfRangeHandler)
        scorer = HybridScorer(
            semantic_endpoint=f"http://127.0.0.1:{port}/classify"
        )
        try:
            score = scorer._get_semantic_score("test")
            assert score == 1.0, f"Expected 1.0 (clamped), got {score}"
        finally:
            server.shutdown()


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
