# SPDX-License-Identifier: MIT
"""
Regression tests for input validation hardening — PR #4361
Tests use actual Flask app fixtures from each module.
"""

import pytest
import json
import sys
import os

# ─── Bridge ledger tests (#4340) ────────────────────────────

def test_bridge_ledger_rejects_malformed_limit():
    """#4340: /bridge/ledger returns 400 for limit=abc"""
    from flask import Flask
    from bridge.bridge_api import bridge_bp, register_bridge_routes

    app = Flask(__name__)
    app.config["TESTING"] = True
    register_bridge_routes(app)

    with app.test_client() as client:
        resp = client.get("/bridge/ledger?limit=abc")
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "error" in data
        assert "Invalid" in data.get("error", "")


def test_bridge_ledger_rejects_negative_limit():
    """#4340: /bridge/ledger returns 400 for limit=-1"""
    from flask import Flask
    from bridge.bridge_api import bridge_bp, register_bridge_routes

    app = Flask(__name__)
    app.config["TESTING"] = True
    register_bridge_routes(app)

    with app.test_client() as client:
        resp = client.get("/bridge/ledger?limit=-1")
        assert resp.status_code == 400


def test_bridge_ledger_rejects_negative_offset():
    """#4340: /bridge/ledger returns 400 for offset=-5"""
    from flask import Flask
    from bridge.bridge_api import bridge_bp, register_bridge_routes

    app = Flask(__name__)
    app.config["TESTING"] = True
    register_bridge_routes(app)

    with app.test_client() as client:
        resp = client.get("/bridge/ledger?offset=-5")
        assert resp.status_code == 400


def test_bridge_ledger_valid_params():
    """#4340: valid pagination returns 200 (DB may be missing, at least not 400)"""
    from flask import Flask
    from bridge.bridge_api import bridge_bp, register_bridge_routes

    app = Flask(__name__)
    app.config["TESTING"] = True
    register_bridge_routes(app)

    with app.test_client() as client:
        resp = client.get("/bridge/ledger?limit=10&offset=0")
        assert resp.status_code == 200


# ─── Faucet tests (#4348) ───────────────────────────────────

def test_faucet_rejects_array_json():
    """#4348: /faucet/drip rejects array JSON payload"""
    from faucet import app as faucet_app

    faucet_app.config["TESTING"] = True
    with faucet_app.test_client() as client:
        resp = client.post(
            "/faucet/drip",
            data='["wallet"]',
            content_type="application/json",
        )
        assert resp.status_code == 400


def test_faucet_rejects_null_json():
    """#4348: /faucet/drip rejects null JSON payload"""
    from faucet import app as faucet_app

    faucet_app.config["TESTING"] = True
    with faucet_app.test_client() as client:
        resp = client.post(
            "/faucet/drip",
            data="null",
            content_type="application/json",
        )
        assert resp.status_code == 400


def test_faucet_rejects_null_wallet():
    """#4348: /faucet/drip rejects {wallet: null}"""
    from faucet import app as faucet_app

    faucet_app.config["TESTING"] = True
    with faucet_app.test_client() as client:
        resp = client.post(
            "/faucet/drip",
            data='{"wallet": null}',
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "error" in data


def test_faucet_rejects_integer_wallet():
    """#4348: /faucet/drip rejects {wallet: 123}"""
    from faucet import app as faucet_app

    faucet_app.config["TESTING"] = True
    with faucet_app.test_client() as client:
        resp = client.post(
            "/faucet/drip",
            data='{"wallet": 123}',
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "error" in data


# ─── Profile badge tests (#4346) ────────────────────────────

def test_badge_rejects_null_json():
    """#4346: /api/badge/create rejects null JSON"""
    from profile_badge_generator import app as badge_app

    badge_app.config["TESTING"] = True
    with badge_app.test_client() as client:
        resp = client.post(
            "/api/badge/create",
            data="null",
            content_type="application/json",
        )
        assert resp.status_code == 400


def test_badge_rejects_array_json():
    """#4346: /api/badge/create rejects array JSON"""
    from profile_badge_generator import app as badge_app

    badge_app.config["TESTING"] = True
    with badge_app.test_client() as client:
        resp = client.post(
            "/api/badge/create",
            data="[]",
            content_type="application/json",
        )
        assert resp.status_code == 400


# ─── Module smoke tests ─────────────────────────────────────

def test_bridge_module_imports():
    """#4340: bridge/bridge_api.py imports without error"""
    import bridge.bridge_api
    assert hasattr(bridge.bridge_api, "bridge_bp")


def test_beacon_module_imports():
    """#4344: node/beacon_api.py imports without error"""
    import node.beacon_api
    assert hasattr(node.beacon_api, "beacon_api")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_faucet_rejects_null_wallet():
    """#4348: /faucet/drip rejects {wallet: null}"""
    from faucet import app as faucet_app

    faucet_app.config["TESTING"] = True
    with faucet_app.test_client() as client:
        resp = client.post(
            "/faucet/drip",
            data='{"wallet": null}',
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "error" in data


def test_faucet_rejects_integer_wallet():
    """#4348: /faucet/drip rejects {wallet: 123}"""
    from faucet import app as faucet_app

    faucet_app.config["TESTING"] = True
    with faucet_app.test_client() as client:
        resp = client.post(
            "/faucet/drip",
            data='{"wallet": 123}',
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "error" in data


def test_badge_rejects_null_username():
    """#4346: /api/badge/create rejects {username: null}"""
    from profile_badge_generator import app as badge_app

    badge_app.config["TESTING"] = True
    with badge_app.test_client() as client:
        resp = client.post(
            "/api/badge/create",
            data='{"username": null}',
            content_type="application/json",
        )
        assert resp.status_code == 400


def test_badge_rejects_integer_username():
    """#4346: /api/badge/create rejects {username: 123}"""
    from profile_badge_generator import app as badge_app

    badge_app.config["TESTING"] = True
    with badge_app.test_client() as client:
        resp = client.post(
            "/api/badge/create",
            data='{"username": 123}',
            content_type="application/json",
        )
        assert resp.status_code == 400


def test_badge_rejects_null_wallet():
    """#4346: /api/badge/create rejects {username:'u', wallet: null}"""
    from profile_badge_generator import app as badge_app

    badge_app.config["TESTING"] = True
    with badge_app.test_client() as client:
        resp = client.post(
            "/api/badge/create",
            data='{"username": "testuser", "wallet": null}',
            content_type="application/json",
        )
        assert resp.status_code == 400


def test_badge_rejects_null_custom_message():
    """#4346: /api/badge/create rejects {username:'u', custom_message: null}"""
    from profile_badge_generator import app as badge_app

    badge_app.config["TESTING"] = True
    with badge_app.test_client() as client:
        resp = client.post(
            "/api/badge/create",
            data='{"username": "testuser", "custom_message": null}',
            content_type="application/json",
        )
        assert resp.status_code == 400


def test_faucet_rejects_boolean_wallet():
    """#4348: /faucet/drip rejects {wallet: true}"""
    from faucet import app as faucet_app

    faucet_app.config["TESTING"] = True
    with faucet_app.test_client() as client:
        resp = client.post(
            "/faucet/drip",
            data='{"wallet": true}',
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "error" in data


def test_faucet_rejects_array_wallet():
    """#4348: /faucet/drip rejects {wallet: []}"""
    from faucet import app as faucet_app

    faucet_app.config["TESTING"] = True
    with faucet_app.test_client() as client:
        resp = client.post(
            "/faucet/drip",
            data='{"wallet": []}',
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "error" in data


def test_badge_rejects_boolean_username():
    """#4346: /api/badge/create rejects {username: false}"""
    from profile_badge_generator import app as badge_app

    badge_app.config["TESTING"] = True
    with badge_app.test_client() as client:
        resp = client.post(
            "/api/badge/create",
            data='{"username": false}',
            content_type="application/json",
        )
        assert resp.status_code == 400


def test_badge_rejects_array_wallet():
    """#4346: /api/badge/create rejects {username:"u", wallet: []}"""
    from profile_badge_generator import app as badge_app

    badge_app.config["TESTING"] = True
    with badge_app.test_client() as client:
        resp = client.post(
            "/api/badge/create",
            data='{"username": "testuser", "wallet": []}',
            content_type="application/json",
        )
        assert resp.status_code == 400


def test_badge_rejects_dict_custom_message():
    """#4346: /api/badge/create rejects {username:"u", custom_message: {}}"""
    from profile_badge_generator import app as badge_app

    badge_app.config["TESTING"] = True
    with badge_app.test_client() as client:
        resp = client.post(
            "/api/badge/create",
            data='{"username": "testuser", "custom_message": {}}',
            content_type="application/json",
        )
        assert resp.status_code == 400
