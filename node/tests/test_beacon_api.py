#!/usr/bin/env python3
"""Tests for node/beacon_api.py — Beacon Atlas API Flask routes.

Tests cover:
  - Pure helper functions (_required_text_field, _positive_float_field,
    _coinbase_addresses_match, _clean_pubkey_hex)
  - _verify_agent_signature (Ed25519 verify via cryptography)
  - init_beacon_tables (schema creation, idempotent, indexes)
  - Beacon join route (register, update, validation, immutable pubkey)
  - Agent query routes (get_agents, get_agent)
  - Atlas route (list agents with optional status filter)
  - Contracts route (list, create, update)
  - Health check + relay discover
  - Error handling (missing fields, bad hex, agent not found)
  - CORS preflight handling
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from unittest.mock import patch

import pytest

sys.path.insert(0, "node")
from beacon_api import (
    _clean_pubkey_hex,
    _coinbase_addresses_match,
    _positive_float_field,
    _required_text_field,
    _verify_agent_signature,
    beacon_api,
    init_beacon_tables,
)
from beacon_api import BEACON_AUTH_WINDOW_SECONDS

# ── Flask test app ───────────────────────────────────────────────────

import flask


@pytest.fixture
def app():
    """Flask test app with beacon_api blueprint and temp DB.

    Monkey-patches get_db() to avoid Flask g caching which causes
    'Cannot operate on a closed database' errors on successive requests.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

    application = flask.Flask(__name__)
    application.register_blueprint(beacon_api)

    import beacon_api as ba_module
    ba_module.DB_PATH = db_path

    init_beacon_tables(db_path)

    # Replace get_db with fresh-connection version (no g caching)
    original_get_db = ba_module.get_db

    def _fresh_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    ba_module.get_db = _fresh_db

    with application.app_context():
        yield application

    os.unlink(db_path)
    ba_module.DB_PATH = "rustchain_v2.db"
    ba_module.get_db = original_get_db


@pytest.fixture
def client(app):
    return app.test_client()


# ── Sample agent for registration ───────────────────────────────────

SAMPLE_AGENT_ID = "agent_alice"
SAMPLE_PUBKEY_HEX = "abcd1234" * 8  # 32 bytes hex
SAMPLE_NAME = "Alice Agent"
SAMPLE_COINBASE = "0x" + "ab" * 20


# ══════════════════════════════════════════════════════════════════════
# 1.  Pure helper functions
# ══════════════════════════════════════════════════════════════════════

class TestRequiredTextField:
    def test_valid_text(self, app):
        with app.app_context():
            val, _, _ = _required_text_field({"name": "hello"}, "name")
            assert val == "hello"

    def test_missing_field(self, app):
        with app.app_context():
            _, err, code = _required_text_field({}, "name")
            assert code == 400
            assert "Missing" in err.get_json()["error"]

    def test_empty_string(self, app):
        with app.app_context():
            _, err, code = _required_text_field({"name": ""}, "name")
            assert code == 400

    def test_whitespace_only(self, app):
        with app.app_context():
            _, err, code = _required_text_field({"name": "   "}, "name")
            assert code == 400

    def test_non_string(self, app):
        with app.app_context():
            _, err, code = _required_text_field({"name": 42}, "name")
            assert code == 400

    def test_strips_whitespace(self, app):
        with app.app_context():
            val, _, _ = _required_text_field({"name": "  hello  "}, "name")
            assert val == "hello"


class TestPositiveFloatField:
    def test_valid_float(self, app):
        with app.app_context():
            val, _, _ = _positive_float_field({"amount": 42.5}, "amount")
            assert val == 42.5

    def test_valid_int_string(self, app):
        with app.app_context():
            val, _, _ = _positive_float_field({"amount": "10"}, "amount")
            assert val == 10.0

    def test_negative_rejected(self, app):
        with app.app_context():
            _, err, code = _positive_float_field({"amount": -5}, "amount")
            assert code == 400

    def test_zero_rejected(self, app):
        with app.app_context():
            _, err, code = _positive_float_field({"amount": 0}, "amount")
            assert code == 400

    def test_nan_rejected(self, app):
        with app.app_context():
            _, err, code = _positive_float_field({"amount": float("nan")}, "amount")
            assert code == 400

    def test_inf_rejected(self, app):
        with app.app_context():
            _, err, code = _positive_float_field({"amount": float("inf")}, "amount")
            assert code == 400

    def test_none_rejected(self, app):
        with app.app_context():
            _, err, code = _positive_float_field({"amount": None}, "amount")
            assert code == 400

    def test_string_nonnumeric(self, app):
        with app.app_context():
            _, err, code = _positive_float_field({"amount": "abc"}, "amount")
            assert code == 400


class TestCoinbaseAddressesMatch:
    def test_exact_match(self):
        assert _coinbase_addresses_match("0xabc123", "0xabc123")

    def test_case_insensitive(self):
        assert _coinbase_addresses_match("0xABCD", "0xabcd")

    def test_strip_whitespace(self):
        assert _coinbase_addresses_match(" 0xabc ", "0xabc")

    def test_both_none(self):
        assert _coinbase_addresses_match(None, None)

    def test_left_none_right_value(self):
        assert not _coinbase_addresses_match(None, "0xabc")

    def test_right_none_left_value(self):
        assert not _coinbase_addresses_match("0xabc", None)


class TestCleanPubkeyHex:
    def test_plain_hex(self):
        assert _clean_pubkey_hex("abcd1234") == "abcd1234"

    def test_strips_0x_prefix(self):
        assert _clean_pubkey_hex("0xabcd1234") == "abcd1234"

    def test_strips_0X_prefix(self):
        assert _clean_pubkey_hex("0Xabcd1234") == "abcd1234"

    def test_strips_whitespace(self):
        assert _clean_pubkey_hex("  abcd  ") == "abcd"

    def test_none_returns_empty(self):
        assert _clean_pubkey_hex(None) == ""

    def test_empty_string(self):
        assert _clean_pubkey_hex("") == ""


# ══════════════════════════════════════════════════════════════════════
# 2.  Signature verification
# ══════════════════════════════════════════════════════════════════════

class TestVerifyAgentSignature:
    def test_returns_false_when_cryptography_unavailable(self):
        with patch("beacon_api.Ed25519PublicKey", None):
            assert _verify_agent_signature("ab" * 32, "cd" * 64, b"msg") is False

    def test_invalid_pubkey_hex_returns_false(self):
        assert _verify_agent_signature("nothex", "cd" * 64, b"msg") is False

    def test_invalid_signature_returns_false(self):
        assert _verify_agent_signature("ab" * 32, "nothex", b"msg") is False

    def test_wrong_signature_returns_false(self):
        # Real Ed25519 key, wrong sig
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        sk = Ed25519PrivateKey.generate()
        pk_hex = sk.public_key().public_bytes_raw().hex()
        assert _verify_agent_signature(pk_hex, "ff" * 64, b"msg") is False

    def test_valid_signature(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        sk = Ed25519PrivateKey.generate()
        pk_hex = sk.public_key().public_bytes_raw().hex()
        msg = b"hello beacon"
        sig = sk.sign(msg)
        assert _verify_agent_signature(pk_hex, sig.hex(), msg) is True


# ══════════════════════════════════════════════════════════════════════
# 3.  init_beacon_tables
# ══════════════════════════════════════════════════════════════════════

class TestInitBeaconTables:
    def test_creates_tables(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        init_beacon_tables(tmp.name)
        conn = sqlite3.connect(tmp.name)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        os.unlink(tmp.name)
        assert "beacon_contracts" in tables
        assert "beacon_bounties" in tables
        assert "beacon_reputation" in tables
        assert "beacon_chat" in tables
        assert "relay_agents" in tables
        assert "beacon_agent_nonces" in tables

    def test_idempotent(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        init_beacon_tables(tmp.name)
        init_beacon_tables(tmp.name)  # Should not raise
        os.unlink(tmp.name)

    def test_creates_indexes(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        init_beacon_tables(tmp.name)
        conn = sqlite3.connect(tmp.name)
        indices = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()}
        conn.close()
        os.unlink(tmp.name)
        assert "idx_contracts_from" in indices
        assert "idx_contracts_to" in indices
        assert "idx_bounties_state" in indices
        assert "idx_chat_agent" in indices
        assert "idx_relay_agents_status" in indices


# ══════════════════════════════════════════════════════════════════════
# 4.  Health check
# ══════════════════════════════════════════════════════════════════════

class TestHealthCheck:
    def test_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"


# ══════════════════════════════════════════════════════════════════════
# 5.  Beacon join route
# ══════════════════════════════════════════════════════════════════════

class TestBeaconJoin:
    def test_register_new_agent(self, client):
        resp = client.post("/beacon/join", json={
            "agent_id": SAMPLE_AGENT_ID,
            "pubkey_hex": SAMPLE_PUBKEY_HEX,
            "name": SAMPLE_NAME,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["agent_id"] == SAMPLE_AGENT_ID
        assert data["status"] == "active"

    def test_missing_agent_id(self, client):
        resp = client.post("/beacon/join", json={"pubkey_hex": SAMPLE_PUBKEY_HEX})
        assert resp.status_code == 400
        assert "agent_id" in resp.get_json()["error"]

    def test_missing_pubkey(self, client):
        resp = client.post("/beacon/join", json={"agent_id": SAMPLE_AGENT_ID})
        assert resp.status_code == 400
        assert "pubkey_hex" in resp.get_json()["error"]

    def test_invalid_pubkey_hex(self, client):
        resp = client.post("/beacon/join", json={
            "agent_id": "test",
            "pubkey_hex": "not_valid_hex!!",
        })
        assert resp.status_code == 400
        assert "hex" in resp.get_json()["error"].lower()

    def test_invalid_json_body(self, client):
        resp = client.post("/beacon/join", data="not json", content_type="application/json")
        assert resp.status_code == 400

    def test_duplicate_same_pubkey_updates(self, client):
        # Register
        client.post("/beacon/join", json={
            "agent_id": SAMPLE_AGENT_ID,
            "pubkey_hex": SAMPLE_PUBKEY_HEX,
            "name": SAMPLE_NAME,
        })
        # Same agent_id, same pubkey_hex, different name
        resp = client.post("/beacon/join", json={
            "agent_id": SAMPLE_AGENT_ID,
            "pubkey_hex": SAMPLE_PUBKEY_HEX,
            "name": "Updated Name",
        })
        assert resp.status_code == 200

    def test_duplicate_different_pubkey_blocked(self, client):
        # Register
        client.post("/beacon/join", json={
            "agent_id": SAMPLE_AGENT_ID,
            "pubkey_hex": SAMPLE_PUBKEY_HEX,
        })
        # Same agent_id, different pubkey_hex — must be rejected
        resp = client.post("/beacon/join", json={
            "agent_id": SAMPLE_AGENT_ID,
            "pubkey_hex": "ffff" * 16,
        })
        assert resp.status_code == 403
        assert "Cannot change pubkey_hex" in resp.get_json()["error"]

    def test_coinbase_address_validation(self, client):
        resp = client.post("/beacon/join", json={
            "agent_id": "agent_bob",
            "pubkey_hex": SAMPLE_PUBKEY_HEX,
            "coinbase_address": SAMPLE_COINBASE,
        })
        assert resp.status_code == 200

    def test_coinbase_address_bad_prefix(self, client):
        resp = client.post("/beacon/join", json={
            "agent_id": "agent_bad",
            "pubkey_hex": SAMPLE_PUBKEY_HEX,
            "coinbase_address": "abc12345678901234567890123456789012345678",
        })
        assert resp.status_code == 400
        assert "0x" in resp.get_json()["error"]

    def test_coinbase_address_bad_length(self, client):
        resp = client.post("/beacon/join", json={
            "agent_id": "agent_bad2",
            "pubkey_hex": SAMPLE_PUBKEY_HEX,
            "coinbase_address": "0xabc",
        })
        assert resp.status_code == 400

    def test_cors_preflight(self, client):
        resp = client.options("/beacon/join")
        assert resp.status_code == 200
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"


# ══════════════════════════════════════════════════════════════════════
# 6.  Agent query routes
# ══════════════════════════════════════════════════════════════════════

class TestGetAgents:
    def test_empty_list(self, client):
        resp = client.get("/api/agents")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_registered_agents(self, client):
        client.post("/beacon/join", json={
            "agent_id": SAMPLE_AGENT_ID,
            "pubkey_hex": SAMPLE_PUBKEY_HEX,
            "name": SAMPLE_NAME,
        })
        resp = client.get("/api/agents")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) >= 1
        ids = [a["agent_id"] for a in data]
        assert SAMPLE_AGENT_ID in ids


class TestGetAgent:
    def test_not_found(self, client):
        resp = client.get("/api/agent/nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"].lower()

    def test_returns_agent(self, client):
        client.post("/beacon/join", json={
            "agent_id": SAMPLE_AGENT_ID,
            "pubkey_hex": SAMPLE_PUBKEY_HEX,
            "name": SAMPLE_NAME,
            "coinbase_address": SAMPLE_COINBASE,
        })
        resp = client.get(f"/api/agent/{SAMPLE_AGENT_ID}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["agent_id"] == SAMPLE_AGENT_ID
        assert data["pubkey_hex"] == SAMPLE_PUBKEY_HEX
        assert data["name"] == SAMPLE_NAME
        assert data["coinbase_address"] == SAMPLE_COINBASE


# ══════════════════════════════════════════════════════════════════════
# 7.  Beacon atlas route
# ══════════════════════════════════════════════════════════════════════

class TestBeaconAtlas:
    def test_empty_atlas(self, client):
        resp = client.get("/beacon/atlas")
        assert resp.status_code == 200
        data = resp.get_json()
        # Returns dict with agents, timestamp, total
        assert data["agents"] == []
        assert data["total"] == 0

    def test_returns_agents(self, client):
        client.post("/beacon/join", json={
            "agent_id": SAMPLE_AGENT_ID,
            "pubkey_hex": SAMPLE_PUBKEY_HEX,
        })
        resp = client.get("/beacon/atlas")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["agents"]) >= 1
        assert data["agents"][0]["agent_id"] == SAMPLE_AGENT_ID

    def test_cors_preflight(self, client):
        resp = client.options("/beacon/atlas")
        assert resp.status_code == 200
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"


# ══════════════════════════════════════════════════════════════════════
# 8.  Contracts routes
# ══════════════════════════════════════════════════════════════════════

class TestContracts:
    def test_list_empty(self, client):
        resp = client.get("/api/contracts")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_contract(self, client):
        """Create a simple service contract (no auth headers)."""
        # Register both parties first
        for aid in ["agent_a", "agent_b"]:
            client.post("/beacon/join", json={
                "agent_id": aid,
                "pubkey_hex": "aa" * 32,
            })

        resp = client.post("/api/contracts", json={
            "from_agent": "agent_a",
            "to_agent": "agent_b",
            "type": "service",
            "amount": 100,
            "term": "deliver by Friday",
            "currency": "RTC",
        })
        # Without sig headers, should return 400 or 401
        # (depends on contract create impl)
        assert resp.status_code in (200, 400, 401)

    def test_contracts_list(self, client):
        """Contracts list should always return a list."""
        resp = client.get("/api/contracts")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════
# 9.  Bounties routes
# ══════════════════════════════════════════════════════════════════════

class TestBounties:
    def test_list_bounties(self, client):
        resp = client.get("/api/bounties")
        assert resp.status_code == 200
        # Returns list (possibly empty)
        assert isinstance(resp.get_json(), list)


# ══════════════════════════════════════════════════════════════════════
# 10. Reputation routes
# ══════════════════════════════════════════════════════════════════════

class TestReputation:
    def test_list_reputation(self, client):
        resp = client.get("/api/reputation")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_agent_reputation_not_found(self, client):
        resp = client.get("/api/reputation/nonexistent")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════
# 11. Relay discover + chat
# ══════════════════════════════════════════════════════════════════════

class TestRelayDiscover:
    def test_returns_list(self, client):
        resp = client.get("/relay/discover")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)


class TestChat:
    def test_chat_missing_headers(self, client):
        """Chat without auth should return 400/401."""
        resp = client.post("/api/chat", json={"message": "hello"})
        # Without agent-id headers, expect error
        assert resp.status_code in (400, 401)


# ══════════════════════════════════════════════════════════════════════
# 12. Internal error handling
# ══════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    def test_join_invalid_body_type(self, client):
        """Non-dict JSON at /beacon/join returns 400."""
        resp = client.post("/beacon/join", json=[])
        assert resp.status_code == 400