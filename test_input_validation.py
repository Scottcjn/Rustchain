"""Regression tests for input validation hardening — PR #4361"""
import pytest
import json
from bridge.bridge_api import bridge_bp

def test_bridge_ledger_rejects_malformed_limit():
    """#4340: /bridge/ledger returns 400 for limit=abc"""
    with bridge_bp.test_client() as client:
        resp = client.get("/bridge/ledger?limit=abc")
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "error" in data

def test_bridge_ledger_rejects_negative_limit():
    """#4340: /bridge/ledger returns 400 for limit=-1"""
    with bridge_bp.test_client() as client:
        resp = client.get("/bridge/ledger?limit=-1")
        assert resp.status_code == 400

def test_bridge_ledger_rejects_negative_offset():
    """#4340: /bridge/ledger returns 400 for offset=-5"""
    with bridge_bp.test_client() as client:
        resp = client.get("/bridge/ledger?offset=-5")
        assert resp.status_code == 400

def test_bridge_ledger_accepts_valid_pagination():
    """#4340: valid pagination returns 200"""
    with bridge_bp.test_client() as client:
        resp = client.get("/bridge/ledger?limit=10&offset=0")
        assert resp.status_code == 200

def test_beacon_rejects_null_json():
    """#4344: null JSON returns 400"""
    import flask
    from node.beacon_api import app as beacon_app
    with beacon_app.test_client() as client:
        resp = client.post("/beacon/relationships",
                          data="null",
                          content_type="application/json")
        assert resp.status_code == 400

def test_beacon_rejects_array_json():
    """#4344: array JSON returns 400"""
    import flask
    from node.beacon_api import app as beacon_app
    with beacon_app.test_client() as client:
        resp = client.post("/beacon/relationships",
                          data='["not","an","object"]',
                          content_type="application/json")
        assert resp.status_code == 400

def test_faucet_rejects_array_json():
    """#4348: /faucet/drip rejects array JSON"""
    from faucet import app as faucet_app
    with faucet_app.test_client() as client:
        resp = client.post("/faucet/drip",
                          data='["wallet"]',
                          content_type="application/json")
        assert resp.status_code == 400

def test_faucet_rejects_null_json():
    """#4348: /faucet/drip rejects null JSON"""
    from faucet import app as faucet_app
    with faucet_app.test_client() as client:
        resp = client.post("/faucet/drip",
                          data="null",
                          content_type="application/json")
        assert resp.status_code == 400

def test_profile_badge_rejects_null_json():
    """#4346: badge generator rejects null JSON"""
    from profile_badge_generator import app as badge_app
    with badge_app.test_client() as client:
        resp = client.post("/api/badge/create",
                          data="null",
                          content_type="application/json")
        assert resp.status_code == 400

def test_profile_badge_rejects_array_json():
    """#4346: badge generator rejects array JSON"""
    from profile_badge_generator import app as badge_app
    with badge_app.test_client() as client:
        resp = client.post("/api/badge/create",
                          data='[]',
                          content_type="application/json")
        assert resp.status_code == 400

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
