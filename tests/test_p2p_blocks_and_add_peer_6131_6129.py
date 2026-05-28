"""
Tests for P2P blocks route pagination validation (#6131) and add_peer JSON
validation (#6129).

Uses a shared Flask test app that mirrors the production validation logic from
node/rustchain_v2_integrated_v2.2.1_rip200.py.

Run: python -m pytest tests/test_p2p_blocks_and_add_peer_6131_6129.py -v
"""

import pytest
import json
from flask import Flask, request


# ---------------------------------------------------------------------------
# Shared Flask test app mirroring the production P2P validation logic
# ---------------------------------------------------------------------------

def _create_test_app():
    """Create a Flask app that mirrors the production p2p route validation."""
    app = Flask(__name__)

    @app.route('/p2p/blocks')
    def p2p_get_blocks():
        raw_start = request.args.get('start', '0')
        raw_limit = request.args.get('limit', '100')
        try:
            start_height = int(raw_start)
        except (ValueError, TypeError):
            return {"ok": False, "error": "start must be an integer"}, 400
        try:
            limit = int(raw_limit)
        except (ValueError, TypeError):
            return {"ok": False, "error": "limit must be an integer"}, 400
        if start_height < 0:
            return {"ok": False, "error": "start must be >= 0"}, 400
        if limit < 1:
            return {"ok": False, "error": "limit must be >= 1"}, 400
        limit = min(limit, 1000)
        return {"ok": True, "start": start_height, "limit": limit}

    @app.route('/p2p/add_peer', methods=['POST'])
    def p2p_add_peer():
        data = request.json
        if not isinstance(data, dict):
            return {"ok": False, "error": "Request body must be a JSON object"}, 400
        peer_url = data.get('peer_url')
        if not peer_url or not isinstance(peer_url, str) or not peer_url.strip():
            return {"ok": False, "error": "peer_url is required and must be a non-blank string"}, 400
        return {"ok": True, "message": "Peer added successfully"}

    return app


# ---------------------------------------------------------------------------
# Issue #6131: P2P blocks pagination validation
# ---------------------------------------------------------------------------

class TestP2PBlocksPagination:
    """Tests for GET /p2p/blocks pagination validation (issue #6131)."""

    def setup_method(self):
        self.app = _create_test_app()
        self.client = self.app.test_client()

    def test_negative_start_returns_400(self):
        """Negative start values should return 400."""
        resp = self.client.get('/p2p/blocks?start=-1&limit=10')
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['ok'] is False
        assert 'start must be >= 0' in data['error']

    def test_negative_limit_returns_400(self):
        """Negative limit values should return 400."""
        resp = self.client.get('/p2p/blocks?start=0&limit=-5')
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['ok'] is False
        assert 'limit must be >= 1' in data['error']

    def test_zero_limit_returns_400(self):
        """Zero limit should return 400."""
        resp = self.client.get('/p2p/blocks?start=0&limit=0')
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['ok'] is False
        assert 'limit must be >= 1' in data['error']

    def test_non_integer_start_returns_400(self):
        """Non-integer start values should return 400."""
        resp = self.client.get('/p2p/blocks?start=abc&limit=10')
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['ok'] is False
        assert 'start must be an integer' in data['error']

    def test_non_integer_limit_returns_400(self):
        """Non-integer limit values should return 400."""
        resp = self.client.get('/p2p/blocks?start=0&limit=abc')
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['ok'] is False
        assert 'limit must be an integer' in data['error']

    def test_valid_pagination_passes(self):
        """Valid start and limit should pass validation."""
        resp = self.client.get('/p2p/blocks?start=0&limit=100')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert data['start'] == 0
        assert data['limit'] == 100

    def test_large_limit_capped_at_1000(self):
        """Limit > 1000 should be capped at 1000."""
        resp = self.client.get('/p2p/blocks?start=0&limit=5000')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert data['limit'] == 1000

    def test_default_values_pass(self):
        """Default start=0 and limit=100 should pass."""
        resp = self.client.get('/p2p/blocks')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert data['start'] == 0
        assert data['limit'] == 100

    def test_float_start_returns_400(self):
        """Float start values should return 400 (int() truncates but '1.5' fails)."""
        resp = self.client.get('/p2p/blocks?start=1.5&limit=10')
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Issue #6129: P2P add_peer JSON validation
# ---------------------------------------------------------------------------

class TestP2PAddPeerValidation:
    """Tests for POST /p2p/add_peer JSON body validation (issue #6129)."""

    def setup_method(self):
        self.app = _create_test_app()
        self.client = self.app.test_client()

    def test_non_object_json_returns_400(self):
        """Non-object JSON body (array) should return 400."""
        resp = self.client.post('/p2p/add_peer',
                                data=json.dumps([]),
                                content_type='application/json')
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['ok'] is False
        assert 'JSON object' in data['error']

    def test_non_object_json_string_returns_400(self):
        """JSON string body should return 400."""
        resp = self.client.post('/p2p/add_peer',
                                data=json.dumps("not an object"),
                                content_type='application/json')
        assert resp.status_code == 400

    def test_missing_peer_url_returns_400(self):
        """Missing peer_url should return 400."""
        resp = self.client.post('/p2p/add_peer',
                                data=json.dumps({"other_key": "value"}),
                                content_type='application/json')
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['ok'] is False
        assert 'peer_url' in data['error']

    def test_blank_peer_url_returns_400(self):
        """Blank/whitespace peer_url should return 400."""
        resp = self.client.post('/p2p/add_peer',
                                data=json.dumps({"peer_url": "   "}),
                                content_type='application/json')
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['ok'] is False
        assert 'peer_url' in data['error']

    def test_non_string_peer_url_returns_400(self):
        """Non-string peer_url (integer) should return 400."""
        resp = self.client.post('/p2p/add_peer',
                                data=json.dumps({"peer_url": 12345}),
                                content_type='application/json')
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['ok'] is False
        assert 'peer_url' in data['error']

    def test_valid_add_peer_succeeds(self):
        """Valid peer_url should return 200 with ok=True."""
        resp = self.client.post('/p2p/add_peer',
                                data=json.dumps({"peer_url": "http://peer.example.com:8080"}),
                                content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True

    def test_empty_body_returns_400(self):
        """Empty JSON body should return 400."""
        resp = self.client.post('/p2p/add_peer',
                                data=json.dumps(None),
                                content_type='application/json')
        # Flask returns None for null JSON, which is not a dict
        assert resp.status_code == 400

    def test_null_peer_url_returns_400(self):
        """Null peer_url should return 400."""
        resp = self.client.post('/p2p/add_peer',
                                data=json.dumps({"peer_url": None}),
                                content_type='application/json')
        assert resp.status_code == 400


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
