"""
Regression test for issue #5766:
Bridge admin callbacks crash on non-object JSON bodies.

Verifies that POST /api/bridge/void and POST /api/bridge/update-external
return HTTP 400 when given a JSON array body instead of a JSON object.
"""
import json
import os
import sys
import pytest

# ---------------------------------------------------------------------------
# Minimal Flask app fixture that registers only the bridge routes.
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create a minimal Flask app with bridge routes for testing."""
    from flask import Flask
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    app = Flask(__name__)
    app.config['TESTING'] = True

    # Set required env vars for the admin routes
    os.environ.setdefault('RC_ADMIN_KEY', 'test-admin-key')
    os.environ.setdefault('RC_BRIDGE_API_KEY', 'test-bridge-key')

    from node.bridge_api import register_bridge_routes
    register_bridge_routes(app)

    return app


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Regression tests — JSON array bodies must be rejected with 400.
# ---------------------------------------------------------------------------

class TestBridgeVoidNonObjectJSON:
    """POST /api/bridge/void must reject non-object JSON bodies."""

    def test_array_body_returns_400(self, client):
        """A JSON array like [\"a\", \"b\"] should not pass the body check."""
        resp = client.post(
            '/api/bridge/void',
            data=json.dumps(["not", "an", "object"]),
            content_type='application/json',
            headers={'X-Admin-Key': 'test-admin-key'},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'error' in body

    def test_null_body_returns_400(self, client):
        """A null/empty JSON body should be rejected."""
        resp = client.post(
            '/api/bridge/void',
            data='null',
            content_type='application/json',
            headers={'X-Admin-Key': 'test-admin-key'},
        )
        assert resp.status_code == 400

    def test_string_body_returns_400(self, client):
        """A plain JSON string should be rejected."""
        resp = client.post(
            '/api/bridge/void',
            data=json.dumps("just a string"),
            content_type='application/json',
            headers={'X-Admin-Key': 'test-admin-key'},
        )
        assert resp.status_code == 400

    def test_integer_body_returns_400(self, client):
        """A plain JSON integer should be rejected."""
        resp = client.post(
            '/api/bridge/void',
            data='42',
            content_type='application/json',
            headers={'X-Admin-Key': 'test-admin-key'},
        )
        assert resp.status_code == 400


class TestBridgeUpdateExternalNonObjectJSON:
    """POST /api/bridge/update-external must reject non-object JSON bodies."""

    def test_array_body_returns_400(self, client):
        resp = client.post(
            '/api/bridge/update-external',
            data=json.dumps(["not", "an", "object"]),
            content_type='application/json',
            headers={'X-API-Key': 'test-bridge-key'},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'error' in body

    def test_null_body_returns_400(self, client):
        resp = client.post(
            '/api/bridge/update-external',
            data='null',
            content_type='application/json',
            headers={'X-API-Key': 'test-bridge-key'},
        )
        assert resp.status_code == 400
