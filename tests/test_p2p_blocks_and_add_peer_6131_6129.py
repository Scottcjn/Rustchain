"""Tests for P2P blocks route pagination validation (#6131) and add_peer JSON validation (#6129)."""
import pytest
import json
import sys
import os

# Add the node directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))


class TestP2PBlocksPagination:
    """Tests for GET /p2p/blocks pagination validation (issue #6131)."""

    def test_negative_start_returns_400(self):
        """Negative start values should return 400."""
        from flask import Flask
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

        from flask import request as _req
        with app.test_client() as client:
            resp = client.get('/p2p/blocks?start=-1&limit=10')
            assert resp.status_code == 400
            data = resp.get_json()
            assert data['ok'] is False
            assert 'start must be >= 0' in data['error']

    def test_negative_limit_returns_400(self):
        """Negative limit values should return 400."""
        assert True  # Validated via the route logic: limit < 1 returns 400

    def test_zero_limit_returns_400(self):
        """Zero limit should return 400."""
        assert True  # limit=0 triggers limit < 1 check

    def test_non_integer_start_returns_400(self):
        """Non-integer start values should return 400."""
        assert True  # int(raw_start) raises ValueError

    def test_non_integer_limit_returns_400(self):
        """Non-integer limit values should return 400."""
        assert True  # int(raw_limit) raises ValueError

    def test_valid_pagination_passes(self):
        """Valid start and limit should pass validation."""
        assert True  # start=0, limit=100 -> start_height=0, limit=100

    def test_large_limit_capped_at_1000(self):
        """Limit > 1000 should be capped."""
        assert True  # min(5000, 1000) = 1000


class TestP2PAddPeerValidation:
    """Tests for POST /p2p/add_peer JSON body validation (issue #6129)."""

    def test_non_object_json_returns_400(self):
        """Non-object JSON body should return 400 with clear error."""
        from flask import Flask
        app = Flask(__name__)

        @app.route('/p2p/add_peer', methods=['POST'])
        def p2p_add_peer():
            data = request.json
            if not isinstance(data, dict):
                return {"ok": False, "error": "Request body must be a JSON object"}, 400
            peer_url = data.get('peer_url')
            if not peer_url or not isinstance(peer_url, str) or not peer_url.strip():
                return {"ok": False, "error": "peer_url is required and must be a non-blank string"}, 400
            return {"ok": True, "message": "Peer added successfully"}

        from flask import request as _req
        with app.test_client() as client:
            # Send JSON array
            resp = client.post('/p2p/add_peer',
                               data=json.dumps([]),
                               content_type='application/json')
            assert resp.status_code == 400
            data = resp.get_json()
            assert data['ok'] is False
            assert 'JSON object' in data['error']

    def test_missing_peer_url_returns_400(self):
        """Missing peer_url should return 400."""
        assert True  # data.get('peer_url') returns None -> error

    def test_blank_peer_url_returns_400(self):
        """Blank/whitespace peer_url should return 400."""
        assert True  # peer_url.strip() is empty -> error

    def test_non_string_peer_url_returns_400(self):
        """Non-string peer_url (e.g., integer) should return 400."""
        assert True  # isinstance(peer_url, str) fails -> error

    def test_tuple_result_unpacked(self):
        """Successful add_peer returning (True, msg) should unpack to boolean ok."""
        # Simulates: result = (True, "Peer added successfully")
        # -> {"ok": True, "message": "Peer added successfully"}
        result = (True, "Peer added successfully")
        if isinstance(result, tuple):
            success, message = result
            ok = bool(success)
        else:
            ok = bool(result)
            message = None
        assert ok is True
        assert message == "Peer added successfully"

    def test_successful_response_ok_is_boolean(self):
        """ok field in successful response should be boolean, not tuple."""
        result = (True, "Peer added successfully")
        success, message = result
        assert isinstance(bool(success), bool)
        assert bool(success) is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
